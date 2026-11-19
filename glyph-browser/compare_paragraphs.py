#!/usr/bin/env python3
"""Compare region-level transcriptions of two IMPACT PAGE collections."""
import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import ZipFile


def canonical_id(name):
    return PurePosixPath(name.replace("\\", "/")).stem.removeprefix("pc-")


def extract(root, pid):
    page = root.find(".//{*}Page")
    if page is None:
        raise ValueError("No PAGE element")
    image_id = canonical_id(page.get("imageFilename", ""))
    if image_id != pid and (pid, image_id) != ("00437021", "00437021_B"):
        raise ValueError(f"Filename {pid} disagrees with imageFilename {image_id}")
    regions = {}
    for el in page.findall(".//{*}TextRegion"):
        rid = el.get("id")
        if not rid or rid in regions:
            raise ValueError(f"Missing or duplicate TextRegion id: {rid!r}")
        coords = el.find("{*}Coords")
        points = None
        if coords is not None:
            if coords.get("points"):
                points = [tuple(map(int, p.split(","))) for p in coords.get("points").split()]
            else:
                points = [(int(p.get("x")), int(p.get("y")))
                          for p in coords.findall("{*}Point")]
        texts = el.findall("{*}TextEquiv/{*}Unicode")
        if len(texts) > 1:
            raise ValueError(f"Multiple region Unicode transcriptions: {rid}")
        regions[rid] = {"type": el.get("type"), "points": points,
                        "text": (texts[0].text or "") if texts else None}
    return (page.get("imageWidth"), page.get("imageHeight")), regions


def ws(s):
    return re.sub(r"\s+", " ", s).strip()


def nfc(s):
    return unicodedata.normalize("NFC", s)


def compare(a, b):
    if a is None or b is None:
        return "missing_text_both" if a is None and b is None else "missing_text_one"
    if a == b:
        return "identical"
    if ws(a) == ws(b):
        return "whitespace_only"
    if nfc(a) == nfc(b):
        return "nfc_only"
    if nfc(ws(a)) == nfc(ws(b)):
        return "whitespace_and_nfc"
    return "different"


def codepoints(s):
    return ["U+%04X" % ord(c) for c in s]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archives", nargs="+", type=Path)
    p.add_argument("--paragraphs", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if not args.paragraphs.is_dir():
        p.error("Paragraph repository directory does not exist")
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        p.error("Output must be new or empty")
    public = defaultdict(list)
    for path in sorted(args.paragraphs.rglob("*.xml")):
        if ".git" not in path.relative_to(args.paragraphs).parts:
            public[canonical_id(path.name)].append(path)

    args.output.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    changes = Counter()
    seen = set()
    page_reports = []
    with (args.output / "differences.jsonl").open("w", encoding="utf-8") as out:
        def record(row):
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
        for archive in args.archives:
            with ZipFile(archive) as z:
                for member in z.infolist():
                    if member.is_dir() or not member.filename.lower().endswith(".xml"):
                        continue
                    pid = canonical_id(member.filename)
                    if pid in seen:
                        raise ValueError(f"Duplicate detailed page ID: {pid}")
                    seen.add(pid)
                    stats["detailed_pages"] += 1
                    row = {"page_id": pid, "detailed_archive": archive.name,
                           "detailed_member": member.filename}
                    candidates = public.get(pid, [])
                    if len(candidates) != 1:
                        status = "missing_public_page" if not candidates else "ambiguous_public_page"
                        stats[status] += 1
                        page_reports.append({**row, "status": status,
                            "candidates": [str(f.relative_to(args.paragraphs)) for f in candidates]})
                        continue
                    path = candidates[0]
                    row["paragraph_file"] = str(path.relative_to(args.paragraphs))
                    try:
                        with z.open(member) as f:
                            detail_size, detail = extract(ET.parse(f).getroot(), pid)
                        para_size, para = extract(ET.parse(path).getroot(), pid)
                    except (ET.ParseError, ValueError, TypeError) as e:
                        stats["page_parse_or_identifier_error"] += 1
                        page_reports.append({**row, "status": "error", "error": str(e)})
                        continue
                    stats["matched_pages"] += 1
                    local = Counter()
                    same_size = detail_size == para_size
                    if not same_size:
                        stats["page_dimension_mismatch"] += 1
                    for rid in sorted(set(detail) | set(para)):
                        a, b = para.get(rid), detail.get(rid)
                        if a is None or b is None:
                            status = "detailed_only_region" if a is None else "paragraph_only_region"
                            local[status] += 1
                            record({**row, "region_id": rid, "status": status,
                                    "paragraph_text": a["text"] if a else None,
                                    "detailed_text": b["text"] if b else None})
                            continue
                        local["matched_regions"] += 1
                        status = compare(a["text"], b["text"])
                        local[status] += 1
                        same_type = a["type"] == b["type"]
                        same_polygon = a["points"] == b["points"]
                        if not same_type:
                            local["region_type_mismatch"] += 1
                        if not same_polygon:
                            local["region_polygon_sequence_mismatch"] += 1
                        if status != "identical" or not same_type or not same_polygon or not same_size:
                            edits = []
                            if a["text"] is not None and b["text"] is not None and a["text"] != b["text"]:
                                x, y = a["text"], b["text"]
                                # Descriptive diff, not a minimum-edit-distance metric.
                                for op, i, j, k, l in SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
                                    if op != "equal":
                                        before, after = x[i:j], y[k:l]
                                        edits.append({"op": op, "paragraph_offset": [i,j],
                                            "detailed_offset": [k,l], "paragraph": before,
                                            "detailed": after, "paragraph_codes": codepoints(before),
                                            "detailed_codes": codepoints(after)})
                                        changes[(before, after)] += 1
                            record({**row, "region_id": rid, "status": status,
                                    "paragraph_type": a["type"], "detailed_type": b["type"],
                                    "same_polygon_sequence": same_polygon, "same_page_dimensions": same_size,
                                    "paragraph_text": a["text"], "detailed_text": b["text"], "edits": edits})
                    stats.update(local)
                    page_reports.append({**row, "status": "matched", "same_dimensions": same_size,
                                         "paragraph_regions": len(para), "detailed_regions": len(detail),
                                         "counts": dict(local)})
                    if local["matched_regions"] == len(para) == len(detail) == local["identical"] and same_size:
                        stats["pages_all_region_texts_identical"] += 1
                    if stats["matched_pages"] % 50 == 0:
                        print(f"Compared {stats['matched_pages']} pages", flush=True)

    report = {"paragraph_xml_files": sum(map(len, public.values())),
              "counts": dict(stats),
              "most_frequent_diff_segments": [
                  {"paragraph": a, "detailed": b, "paragraph_codes": codepoints(a),
                   "detailed_codes": codepoints(b), "count": n}
                  for (a, b), n in changes.most_common(30)]}
    for name, value in (("summary.json", report), ("pages.json", page_reports)):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    # TSV is deliberately escaped so invisible characters are visible in a terminal.
    with (args.output / "changes.tsv").open("w", encoding="utf-8") as f:
        f.write("count\tparagraph_json\tdetailed_json\tparagraph_codes\tdetailed_codes\n")
        for (a, b), n in changes.most_common():
            f.write("\t".join([str(n), json.dumps(a, ensure_ascii=False),
                              json.dumps(b, ensure_ascii=False), " ".join(codepoints(a)),
                              " ".join(codepoints(b))]) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
