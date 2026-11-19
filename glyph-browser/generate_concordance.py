#!/usr/bin/env python3
"""Generate a static concordance of original PAGE glyph occurrences."""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import json
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from aletheia_names import NAMES, SOURCE


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def text(element):
    return element.findtext("{*}TextEquiv/{*}Unicode")


def bbox(element):
    coords = element.find("{*}Coords")
    if coords is None:
        return None
    if coords.get("points"):
        points = [tuple(map(int, pair.split(",")))
                  for pair in coords.get("points").split()]
    else:
        points = [(int(p.get("x")), int(p.get("y")))
                  for p in coords.findall("{*}Point")]
    if not points:
        return None
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs), max(ys)]


def page_id(page):
    return PurePosixPath(page.get("imageFilename", "").replace("\\", "/")).stem


def compile_page(page, pid, lists, diagnostics):
    parents = {c: p for p in page.iter() for c in p}
    glyphs = list(page.findall(".//{*}Glyph"))
    by_word = defaultdict(list)
    for g in glyphs:
        p = parents.get(g)
        while p is not None and p.tag.rsplit("}", 1)[-1] != "Word":
            p = parents.get(p)
        by_word[p].append(g)

    details = {}
    for word, group in by_word.items():
        if word is None:
            diagnostics["glyphs_without_word"] += len(group)
            for g in group:
                details[g] = (None, None, None, None)
            continue
        label = text(word)
        parts = [text(g) for g in group]
        aligned = (label is not None and all(parts) and "".join(parts) == label)
        if not aligned:
            diagnostics["words_without_exact_alignment"] += 1
            diagnostics["glyphs_without_exact_word_span"] += len(group)
        offset = 0
        for i, (g, part) in enumerate(zip(group, parts)):
            span = [offset, offset + len(part)] if aligned else None
            details[g] = (label, word.get("id"), i, span)
            offset += len(part or "")

    counts = Counter()
    ids = set()
    width, height = int(page.get("imageWidth")), int(page.get("imageHeight"))
    for ordinal, g in enumerate(glyphs):
        value = text(g)
        gid = g.get("id")
        if not gid:
            diagnostics["missing_glyph_id"] += 1
        elif gid in ids:
            diagnostics["duplicate_glyph_id_within_page"] += 1
        ids.add(gid)
        if not value:
            diagnostics["missing_or_empty"] += 1
            continue
        word, wid, index, span = details[g]
        box = bbox(g)
        if box is None or box[0] == box[2] or box[1] == box[3]:
            diagnostics["missing_or_degenerate_box"] += 1
        if box is not None and (box[0] < 0 or box[1] < 0
                                or box[2] > width or box[3] > height):
            diagnostics["box_outside_image"] += 1
        lists[value].append({
            "page_id": pid, "glyph_id": gid, "page_glyph_index": ordinal,
            "word_id": wid, "word": word, "word_glyph_index": index,
            "word_span": span, "bbox": box,
        })
        counts[value] += 1
    return counts, len(glyphs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archives", nargs="+", type=Path)
    for arg in ("inventory", "books", "pages", "output"):
        p.add_argument("--" + arg, required=True, type=Path)
    a = p.parse_args()
    report, books, pages = load(a.inventory), load(a.books), load(a.pages)
    if a.output.exists() and (not a.output.is_dir() or any(a.output.iterdir())):
        p.error("Output directory must be new or empty")
    for pid, page in pages.items():
        if page["page_id"] != pid or page["book_id"] not in books:
            raise ValueError(f"Invalid metadata for {pid}")

    members, zips, page_data = {}, {}, {}
    lists = defaultdict(list)
    diagnostics = Counter()
    archive_counts = defaultdict(Counter)
    with ExitStack() as stack:
        # Identify pages by authoritative PAGE imageFilename, not ZIP member name.
        for path in a.archives:
            if path.name in zips:
                raise ValueError(f"Duplicate archive basename {path.name}")
            z = stack.enter_context(ZipFile(path))
            zips[path.name] = z
            for item in z.infolist():
                if item.is_dir() or not item.filename.lower().endswith(".xml"):
                    continue
                with z.open(item) as f:
                    found = ET.parse(f).getroot().findall(".//{*}Page")
                if len(found) != 1:
                    raise ValueError(f"{path.name}:{item.filename}: expected one Page")
                pid = page_id(found[0])
                if not pid or pid in members:
                    raise ValueError(f"Missing or duplicate page ID: {pid!r}")
                members[pid] = (path.name, item)
        if set(pages) != set(members):
            raise ValueError(f"Metadata mismatch: missing={sorted(set(pages)-set(members))}; "
                             f"extra={sorted(set(members)-set(pages))}")
        order = sorted(pages, key=lambda pid: (
            pages[pid]["book_id"], pages[pid]["sequence_in_subset"], pid))
        for i, pid in enumerate(order, 1):
            archive, item = members[pid]
            with zips[archive].open(item) as f:
                page = ET.parse(f).getroot().find(".//{*}Page")
            counts, total = compile_page(page, pid, lists, diagnostics)
            archive_counts[archive].update(counts)
            page_data[pid] = {
                **pages[pid], "archive": archive, "xml_member": item.filename,
                "image_filename": page.get("imageFilename"),
                "width": int(page.get("imageWidth")), "height": int(page.get("imageHeight")),
                "physical_order": i, "glyph_count": total,
            }
            if i % 50 == 0 or i == len(order):
                print(f"Processed {i}/{len(order)} pages", flush=True)

    expected = {e["transcription"]: e for e in report["inventory"]}
    actual = {v: len(rows) for v, rows in lists.items()}
    if actual != {v: e["count"] for v, e in expected.items()}:
        raise ValueError("Concordance frequencies do not match inventory")
    for v, e in expected.items():
        by_archive = {name: c[v] for name, c in archive_counts.items() if c[v]}
        if by_archive != e["by_archive"]:
            raise ValueError(f"Archive frequency mismatch for {v!r}")
    total = sum(p["glyph_count"] for p in page_data.values())
    if total != sum(v["glyphs"] for v in report["archives"].values()):
        raise ValueError("Total PAGE glyph element count differs from inventory")

    a.output.mkdir(parents=True, exist_ok=True)
    dest = a.output / "occurrences"
    dest.mkdir()
    entries = []
    for value, e in sorted(expected.items(), key=lambda item: tuple(map(ord, item[0]))):
        key = "-".join(f"{ord(c):04X}" for c in value)
        chars = []
        for c, description in zip(value, e["characters"]):
            char = dict(description)
            if ord(c) in NAMES:
                char.update(name=NAMES[ord(c)], name_source=SOURCE)
            chars.append(char)
        entries.append({
            "key": key, "transcription": value, "codepoints": e["codepoints"],
            "characters": chars, "count": e["count"], "by_archive": e["by_archive"],
            "occurrences": f"occurrences/{key}.json",
        })
        write(dest / f"{key}.json", lists[value])
    write(a.output / "inventory.json", entries)
    write(a.output / "pages.json", page_data)
    write(a.output / "books.json", books)
    summary = {
        "pages": len(page_data), "books": len(books),
        "distinct_glyph_transcriptions": len(entries),
        "glyph_occurrences": sum(actual.values()), "glyph_elements": total,
        "diagnostics": dict(diagnostics),
        "order": "book_id, sequence_in_subset, page_id, PAGE XML glyph order",
        "frequency_check": "matches inventory including per-archive frequencies",
        "word_span_units": "zero-based Unicode code points, end exclusive; null if not aligned",
        "bbox_units": "original image pixels, left/top/right/bottom; null if unavailable",
    }
    write(a.output / "build-report.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
