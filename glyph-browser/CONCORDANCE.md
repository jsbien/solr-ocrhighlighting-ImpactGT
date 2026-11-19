# Static concordance generation

Run from the repository root on the machine holding the detailed GT archives.
The existing glyph-inventory.json is sufficient. Save the previously extracted
books.json and pages.json in the same local working directory as the archives.

```bash
work="$HOME/Cykat-recovery/IMPACT-GT-detailed"
python3 glyph-browser/generate_concordance.py \
  "$work/PSNC_POLISH_ANTIQUA_GT.ZIP" \
  "$work/PSNC_POLISH_GOTHIC_GT.ZIP" \
  --inventory "$work/glyph-inventory.json" \
  --books "$work/books.json" \
  --pages "$work/pages.json" \
  --output "$work/glyph-browser-data"
```

Expected totals: 478 pages, 27 publications, 194 distinct transcriptions,
641612 glyph occurrences. The output directory must be new or empty.
The generator verifies exact frequency agreement with the inventory, overall
and per archive. It also verifies page metadata coverage.

Outputs: inventory.json, books.json, pages.json, build-report.json,
and one occurrences/<hex-key>.json per glyph transcription (including
multicodepoint keys such as 007A-0304). Each occurrence retains original page ID,
glyph ID, enclosing word transcription and ID, glyph positions in the PAGE XML
and original-image pixel bounding box. A word_span is included only if
concatenating the source glyph transcriptions exactly reproduces the word; it
is null otherwise. Offsets are Unicode code points, not UTF-16 code units.
Bounding boxes are min/max of the original polygon coordinates.

Default ordering is lexical book ID, sequence_in_subset, page ID and
PAGE XML glyph order. Inter-book order is provisional; split-scan ordering
flags in pages.json are retained. Repeated glyphs in a word remain independent.

Names for the nine formerly unidentified PUA values come from Special
Characters in Aletheia (PRImA, 2011-12-02, pp. 3, 4, 6, 9). F51E retains
the existing explicit MUFI mapping for naming. No code points are replaced.

All generated data remain local. Do not publish the data indiscriminately:
historical publication restrictions still need investigation. The generator
does not require images or Solr. Full corpus testing must be performed locally;
review build-report.json before implementation of the browser.

## Known PAGE identifier exception

The first corpus run found PAGE imageFilename stem `00437021_B` where the
metadata expects `00437021`. The generator accepts this explicit alias only if
the XML member stem (after an optional `pc-` prefix) and the metadata agree.
It preserves the original imageFilename and page_image_id in pages.json and
logs the exception in build-report.json. No other suffixes are stripped.
The corresponding master image filename and dimensions still need verification
before displaying its glyph coordinates.
