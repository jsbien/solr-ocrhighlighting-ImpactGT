# IMPACT GT Glyph Browser — inventory stage

This is a static glyph browsing experiment, separate from the Solr search interface.
The first step inventories original glyph transcriptions in the detailed PAGE XML.
Run the following on the machine holding the source data. No archives or generated
reports need to be committed to GitHub.

From the repository root (Debian/Linux, Python 3, curl):

```sh
work="$HOME/Cykat-recovery/IMPACT-GT-detailed"
curl -fL -o "$work/mufiexport.csv" \
  https://raw.githubusercontent.com/jsbien/MUFI_data/5bdde0c6bf597ec8c73ad1cee1b0d022bb69bdcc/data/csv/mufiexport.csv
python3 glyph-browser/generate_inventory.py \
  "$work/PSNC_POLISH_ANTIQUA_GT.ZIP" \
  "$work/PSNC_POLISH_GOTHIC_GT.ZIP" \
  --mufi "$work/mufiexport.csv" \
  --output "$work/glyph-inventory.json"
```

The report contains original glyph transcriptions (including multiple-code-point
sequences, if present), Unicode/MUFI names, frequencies per archive, up to
three occurrence examples for each transcription, and basic structural diagnostics.
Expected archive page counts are 186 Antiqua and 292 Gothic. The script does not
need TIFF images, Solr or the bibliographic metadata.

MUFI snapshot: jsbien/MUFI_data commit 5bdde0c6bf597ec8c73ad1cee1b0d022bb69bdcc.
U+F51E is explicitly mapped to current MUFI U+E8AF for naming only. Other
same-code MUFI matches are provisional identifications; unmapped PUA gets
a temporary name such as IMPACT PUA F500. No normalization or code-point
replacement is performed. Missing or empty glyph transcriptions are counted
separately; if multiple TextEquiv elements exist, the first is used as in the
earlier MiniOCR experiment.

The full source corpus is not available in the development environment;
the first run on the original archives is a validation step. Review the report
before proceeding to concordance generation or deployment. Bibliographic metadata,
Junicode, OpenSeadragon and the browser interface are subsequent stages.
