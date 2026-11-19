# Comparison with paragraph-level IMPACT PAGE

Run locally from the repository root:

```bash
work="$HOME/Cykat-recovery/IMPACT-GT-detailed"
python3 glyph-browser/compare_paragraphs.py \
  "$work/PSNC_POLISH_ANTIQUA_GT.ZIP" \
  "$work/PSNC_POLISH_GOTHIC_GT.ZIP" \
  --paragraphs "$HOME/git/groundtruth-pol" \
  --output "$work/paragraph-comparison"
```

Uses Python standard library only. No input files are changed.
Matches page filename stems, with optional pc- prefix removed, and checks
PAGE imageFilename (including the known 00437021_B exception). Ambiguous
or missing pages are reported, not silently selected. Pairs TextRegions by
ID; checks dimensions, exact sequence of polygon vertices, and region type.
Does not attempt spatial matching of unmatched region IDs. Includes headers,
catchwords and page numbers, not only regions of type paragraph.
Compares direct TextEquiv/Unicode strings, not child words or glyphs.
Missing Unicode is distinct from an empty Unicode element. Exact equality
compares parsed XML character data (XML line endings are normalized by the
parser). Secondary mutually exclusive categories test whitespace collapse
and NFC independently and together. No PUA or punctuation substitutions.

Outputs summary.json, pages.json, differences.jsonl (original texts and edit
segments for nonidentical pairs and unmatched regions), changes.tsv (frequency
of descriptive diff segments, with code points). SequenceMatcher is descriptive,
not a minimum-edit-distance algorithm; changes can group adjacent characters.
Polygon sequence differences need not imply different geometric outlines.
Output must be new or empty. Keep generated reports local; they include
source transcriptions. Full corpus execution remains to be tested locally.
