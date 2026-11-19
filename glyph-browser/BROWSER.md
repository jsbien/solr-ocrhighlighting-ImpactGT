# Local static glyph browser

The first UI prototype reads the generated concordance and original-resolution
PNG images. No Solr, Flask or IIIF is required.

From the repository root, after generating the concordance and preparing images:

```sh
work="$HOME/Cykat-recovery/IMPACT-GT-detailed"
bash glyph-browser/setup_site.sh "$work/glyph-browser-data"
python3 -m http.server 8081 --bind 127.0.0.1 --directory "$work/glyph-browser-data"
```

Open http://127.0.0.1:8081/. Stop the server with Ctrl+C.
Setup copies three source files and downloads pinned OpenSeadragon 6.1.1 and
Junicode VF Roman from GitHub/jsDelivr. Rerun setup to refresh the interface;
existing nonempty dependency files are reused. After setup no external network
connection is needed by the browser. The data directory is outside Git.

Navigation: select a transcription in the inventory, then click an individual
occurrence, return via the back button. Physical ordering is the default;
alphabetical uses Polish locale collation. Pagination renders 100 occurrences
at a time, and an Antiqua/Gothic selector is available. The right-hand pane
remains visible when navigating. Words use the unmodified source transcriptions.
Inline highlighting in the word label is only applied for exact alignment.
For other words an XML glyph index is shown and the actual image position
is used, where available. PUA values are not remapped for display: unsupported
or reassigned code points may not render faithfully in the current Junicode.
No usable bounding box means no image overlay. The page scan is loaded on demand.

This UI has not yet been tested with the full local dataset. In particular
verify U+EADA, Y (repeated glyphs in SCYENCYA), U+F51C, U+FFFD and
U+007A U+0304. Check repeated selection on the same page, navigation between
pages and zooming. There is no textual search beyond filtering the inventory.
Do not expose this server publicly or commit the generated corpus until the
historical redistribution restrictions are resolved.
