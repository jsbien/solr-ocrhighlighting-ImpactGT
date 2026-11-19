#!/usr/bin/env python3
"""Convert master TIFFs directly from the original ZIPs into browser PNGs."""
import argparse
from collections import defaultdict
from contextlib import ExitStack
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
from zipfile import ZipFile

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--data", required=True, type=Path,
                        help="Generated glyph-browser-data directory")
    parser.add_argument("--overwrite", action="store_true",
                        help="Regenerate existing PNGs")
    args = parser.parse_args()

    pages = json.loads((args.data / "pages.json").read_text(encoding="utf-8"))
    by_archive = defaultdict(list)
    for pid, page in pages.items():
        if not re.fullmatch(r"[0-9]+", pid) or page["page_id"] != pid:
            raise ValueError(f"Invalid page ID: {pid!r}")
        gt = page["archive"]
        if not gt.endswith("_GT.ZIP"):
            raise ValueError(f"Unexpected GT archive name: {gt}")
        master = gt.removesuffix("_GT.ZIP") + "_MasterFiles.ZIP"
        by_archive[master].append((pid, page))

    paths = {p.name: p for p in args.archives}
    if len(paths) != len(args.archives) or set(paths) != set(by_archive):
        parser.error(f"Expected master archives: {', '.join(sorted(by_archive))}")

    output = args.data / "images"
    output.mkdir(exist_ok=True)
    converted = skipped = 0
    total = len(pages)
    report = {"pages": total, "converted": 0, "reused": 0,
              "mode_conversions": {}, "source_modes": {}}
    with ExitStack() as stack:
        jobs = []
        for name, entries in sorted(by_archive.items()):
            z = stack.enter_context(ZipFile(paths[name]))
            members = defaultdict(list)
            for info in z.infolist():
                if not info.is_dir():
                    p = PurePosixPath(info.filename)
                    if p.suffix.lower() in (".tif", ".tiff"):
                        members[p.stem].append(info)
            for pid, page in entries:
                if len(members[pid]) != 1:
                    raise ValueError(f"{name}: expected exactly one TIFF for {pid}")
                jobs.append((z, members[pid][0], pid, page))
        for i, (z, member, pid, page) in enumerate(jobs, 1):
            target = output / f"{pid}.png"
            size = (page["width"], page["height"])
            with z.open(member) as f, Image.open(f) as im:
                if im.size != size:
                    raise ValueError(f"{pid}: TIFF {im.size} != PAGE {size}")
                if getattr(im, "n_frames", 1) != 1:
                    raise ValueError(f"{pid}: multipage TIFF requires review")
                mode = im.mode
                report["source_modes"][mode] = report["source_modes"].get(mode, 0) + 1
                if target.exists() and not args.overwrite:
                    valid = False
                    try:
                        with Image.open(target) as existing:
                            valid = existing.format == "PNG" and existing.size == size
                            existing.verify()
                    except (OSError, SyntaxError):
                        valid = False
                    if not valid:
                        raise ValueError(f"Invalid existing PNG: {target}; use --overwrite")
                    skipped += 1
                else:
                    # PNG cannot represent every TIFF mode. Handle common
                    # display conversions explicitly; do not silently reduce
                    # high-bit-depth or floating-point image data.
                    if mode in ("1", "L", "LA", "P", "RGB", "RGBA", "I;16"):
                        image = im
                    elif mode in ("CMYK", "YCbCr"):
                        image = im.convert("RGB")
                    elif mode in ("I;16B", "I;16L"):
                        image = im.convert("I;16")
                    else:
                        raise ValueError(f"{pid}: unsupported TIFF mode {mode!r}")
                    if image.mode != mode:
                        key = f"{mode} -> {image.mode}"
                        report["mode_conversions"][key] = report["mode_conversions"].get(key, 0) + 1
                    # Atomic replacement: interruption cannot leave a partial
                    # PNG at the final filename.
                    tmp = None
                    try:
                        with tempfile.NamedTemporaryFile(dir=output, suffix=".png",
                                                         delete=False) as temp:
                            tmp = Path(temp.name)
                        image.save(tmp, format="PNG", compress_level=6)
                        with Image.open(tmp) as check:
                            if check.size != size:
                                raise ValueError(f"{pid}: output dimensions changed")
                            check.verify()
                        tmp.replace(target)
                    finally:
                        if tmp is not None:
                            tmp.unlink(missing_ok=True)
                    converted += 1
            if i % 25 == 0 or i == total or pid == "00437021":
                print(f"{i}/{total}: {pid} ({converted} converted, {skipped} reused)",
                      flush=True)
    report["converted"] = converted
    report["reused"] = skipped
    report["png_bytes"] = sum((output / f"{pid}.png").stat().st_size for pid in pages)
    (args.data / "image-build-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
