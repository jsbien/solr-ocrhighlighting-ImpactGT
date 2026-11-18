# Local web interface

No IIIF service is needed. This Flask application queries the existing impactgt Solr core and displays PNG/TIFF scans with SVG overlays. Run from the repository root:

```sh
python3 -m venv ~/.venvs/impactgt-web
source ~/.venvs/impactgt-web/bin/activate
python3 -m pip install -r impactgt/web/requirements.txt
python3 impactgt/web/app.py
```

Open http://127.0.0.1:8080/. Solr must already be running and the page indexed. For glyph mode, the core must contain the ocr_glyphs field and the document must reference the generated glyph MiniOCR file. See the word experiment README for the initial setup. To index both fields once the glyph schema and MiniOCR are available:

```sh
curl -s -X POST 'http://localhost:8983/solr/impactgt/update?commit=true' \
 -H 'Content-Type: application/json' \
 --data-binary '[{"id":"00433094","source":"IMPACT-GT","ocr_text":"/data/pc-00433094.alto.xml","ocr_glyphs":"/data/pc-00433094.glyphs.miniocr"}]'
```

Test Aniołem in Words mode and U+EADA in Glyphs mode. Expected results on the sample are respectively 1 and 18 highlight boxes. Queries are literal indexed terms; phrase and sequence queries are outside this prototype. Counts represent returned boxes, not necessarily exhaustive occurrence counts. One page is displayed at a time, assuming a single scan per Solr document and pixel-based coordinates. TIFF conversion is cached in memory. This is a local development server, not a public deployment. The term-query/highlighter combination needs runtime verification against the installed plugin.
