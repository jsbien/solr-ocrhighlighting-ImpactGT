#!/usr/bin/env python3
"""Inventory original PAGE glyph transcriptions directly from GT ZIP archives."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path, PurePosixPath
import unicodedata as ud
import xml.etree.ElementTree as ET
from zipfile import ZipFile


# Documented corpus-specific assignment, not a change to source text.
MUFI_OVERRIDES = {0xF51E: 0xE8AF}


def codepoints(value):
    return " ".join(f"U+{ord(c):04X}" for c in value)


def load_mufi(path):
    names = {}
    if path is not None:
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                if not row or not row[0].strip():
                    continue
                try:
                    cp = int(row[0], 16)
                except ValueError:
                    continue  # header, if present
                if len(row) < 10:
                    raise ValueError(f"Invalid MUFI export row: {row!r}")
                name = row[9].strip()
                if cp in names and names[cp] != name:
                    raise ValueError(f"Conflicting MUFI names for U+{cp:04X}")
                names[cp] = name
    return names


def describe(c, mufi):
    cp = ord(c)
    if ud.category(c) != "Co":
        name = ud.name(c, None)
        return {"code": codepoints(c), "name": name or codepoints(c),
                "name_source": "Unicode" if name else "unnamed Unicode"}
    target = MUFI_OVERRIDES.get(cp, cp)
    if target in mufi:
        result = {"code": codepoints(c), "name": mufi[target],
                  "name_source": "MUFI (explicit mapping)" if target != cp
                  else "MUFI (same code; identity not independently verified)"}
        if target != cp:
            result["current_mufi_code"] = f"U+{target:04X}"
        return result
    return {"code": codepoints(c), "name": f"IMPACT PUA {cp:04X}",
            "name_source": "provisional"}


def scan(path, counts, examples, issues, seen):
    total = Counter()
    with ZipFile(path) as z:
        members = sorted(n for n in z.namelist() if n.lower().endswith(".xml"))
        for member in members:
            with z.open(member) as f:
                root = ET.parse(f).getroot()
            pages = root.findall(".//{*}Page")
            if len(pages) != 1:
                raise ValueError(f"{path.name}:{member}: expected one PAGE element")
            page = pages[0]
            page_id = PurePosixPath(page.get("imageFilename", "").replace("\\", "/")).stem
            if not page_id:
                raise ValueError(f"{path.name}:{member}: no imageFilename")
            if page_id in seen:
                issues.append({"kind": "duplicate_page_id", "page_id": page_id,
                               "archive": path.name, "file": member})
            seen.add(page_id)
            total["pages"] += 1
            # Parent map preserves the actual Word transcription, not a
            # reconstruction from the (occasionally misordered) glyphs.
            parents = {child: parent for parent in page.iter() for child in parent}
            glyphs = page.findall(".//{*}Glyph")
            if not glyphs:
                issues.append({"kind": "no_glyphs", "page_id": page_id,
                               "archive": path.name, "file": member})
            for glyph in glyphs:
                total["glyphs"] += 1
                alternatives = glyph.findall("{*}TextEquiv")
                value = glyph.findtext("{*}TextEquiv/{*}Unicode")
                if len(alternatives) > 1:
                    total["glyphs_with_multiple_text_equiv"] += 1
                if value is None or value == "":
                    total["missing_or_empty"] += 1
                    continue
                if any(c.isspace() for c in value):
                    total["whitespace_containing"] += 1
                if len(value) != 1:
                    total["multi_codepoint"] += 1
                counts[value][path.name] += 1
                if len(examples[value]) < 3:
                    parent = parents.get(glyph)
                    while parent is not None and parent.tag.rsplit("}", 1)[-1] != "Word":
                        parent = parents.get(parent)
                    examples[value].append({
                        "page_id": page_id,
                        "glyph_id": glyph.get("id"),
                        "word_id": parent.get("id") if parent is not None else None,
                        "word": parent.findtext("{*}TextEquiv/{*}Unicode")
                        if parent is not None else None,
                    })
    return dict(total)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", type=Path, nargs="+")
    parser.add_argument("--mufi", required=True, type=Path,
                        help="MUFI_data/data/csv/mufiexport.csv")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    mufi = load_mufi(args.mufi)
    counts = defaultdict(Counter)
    examples = defaultdict(list)
    issues = []
    seen = set()
    summaries = {}
    for path in args.archives:
        if path.name in summaries:
            parser.error(f"Archive basename repeated: {path.name}")
        summaries[path.name] = scan(path, counts, examples, issues, seen)
        print(path.name, summaries[path.name])
    entries = []
    for value in sorted(counts, key=lambda s: tuple(map(ord, s))):
        entries.append({
            "transcription": value,
            "codepoints": codepoints(value),
            "characters": [describe(c, mufi) for c in value],
            "count": sum(counts[value].values()),
            "by_archive": dict(counts[value]),
            "examples": examples[value],
        })
    unknown = sorted({c["code"] for e in entries for c in e["characters"]
                      if c["name_source"] == "provisional"})
    report = {
        "unicode_database_version": ud.unidata_version,
        "mufi_file": args.mufi.name,
        "archives": summaries,
        "unique_page_ids": len(seen),
        "distinct_glyph_transcriptions": len(entries),
        "provisionally_named_pua": unknown,
        "issues": issues,
        "inventory": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"Unique pages: {len(seen)}; distinct glyph transcriptions: {len(entries)}")
    print("Provisionally named PUA:", ", ".join(unknown) or "(none)")
    print("Report:", args.output)


if __name__ == "__main__":
    main()
