#!/usr/bin/env python3
"""Prepare a local interactive report from an existing paragraph comparison."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json
import shutil
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from contextlib import ExitStack

from compare_paragraphs import extract


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
                    encoding="utf-8")


def box(regions, rid):
    region = regions.get(rid)
    if not region or not region["points"]:
        return None
    xs, ys = zip(*region["points"])
    result = [min(xs), min(ys), max(xs), max(ys)]
    return result if result[2] > result[0] and result[3] > result[1] else None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archives", nargs="+", type=Path)
    p.add_argument("--paragraphs", required=True, type=Path)
    p.add_argument("--comparison", required=True, type=Path)
    p.add_argument("--data", required=True, type=Path,
                   help="Existing glyph-browser-data, with images and vendor assets")
    a = p.parse_args()
    summary = load(a.comparison / "summary.json")
    page_report = load(a.comparison / "pages.json")
    pages = load(a.data / "pages.json")
    for required in ["books.json", "vendor/openseadragon.min.js",
                     "vendor/JunicodeVF-Roman.woff2"]:
        if not (a.data / required).is_file():
            p.error(f"Missing existing browser asset: {required}")
    rows = [json.loads(line) for line in
            (a.comparison / "differences.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    grouped = defaultdict(list)
    for i, row in enumerate(rows):
        grouped[row["page_id"]].append(i)
    paths = {path.name: path for path in a.archives}
    diag = Counter()
    with ExitStack() as stack:
        archives = {name: stack.enter_context(ZipFile(path)) for name, path in paths.items()}
        for number, (pid, indices) in enumerate(grouped.items(), 1):
            row = rows[indices[0]]
            detail_size, detail = None, {}
            para_size, para = None, {}
            with archives[row["detailed_archive"]].open(row["detailed_member"]) as f:
                detail_size, detail = extract(ET.parse(f).getroot(), pid)
            para_size, para = extract(ET.parse(a.paragraphs / row["paragraph_file"]).getroot(), pid)
            page = pages[pid]
            expected = (str(page["width"]), str(page["height"]))
            for i in indices:
                r = rows[i]
                rid = r["region_id"]
                # Preserve separate boxes; never locate a changed character
                # by guessing from its offset in the region transcription.
                r["detailed_box"] = box(detail, rid) if detail_size == expected else None
                r["paragraph_box"] = box(para, rid) if para_size == expected else None
                if not r["detailed_box"] and not r["paragraph_box"]:
                    diag["no_usable_region_box"] += 1
                for region, key in [(detail, "detailed_text"), (para, "paragraph_text")]:
                    if (region.get(rid) or {}).get("text") != r.get(key):
                        raise ValueError(f"Input transcription changed since comparison: {pid}/{rid}")
            if number % 50 == 0:
                print(f"Prepared regions on {number}/{len(grouped)} pages", flush=True)
    pairs = defaultdict(list)
    categories = defaultdict(list)
    for i, row in enumerate(rows):
        categories[row["status"]].append(i)
        for j, edit in enumerate(row.get("edits", [])):
            pairs[(edit["paragraph"], edit["detailed"])].append([i, j])
    changes = [{"before": before, "after": after, "count": len(refs), "refs": refs}
               for (before, after), refs in sorted(
                   pairs.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    output = a.data / "comparison"
    output.mkdir(exist_ok=True)
    for name in ["index.html", "report.css", "report.js"]:
        shutil.copyfile(Path(__file__).parent / "comparison-site" / name, output / name)
    write(output / "report.json", {"summary": summary, "rows": rows,
          "changes": changes, "categories": dict(categories),
          "page_report": page_report, "diagnostics": dict(diag)})
    print(f"Prepared {len(rows)} region records, {len(changes)} change pairs.")
    print("Open http://127.0.0.1:8081/comparison/ with the existing local server.")


if __name__ == "__main__":
    main()
