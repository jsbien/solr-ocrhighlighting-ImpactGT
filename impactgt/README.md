# IMPACT GT word and glyph search experiment

This experiment uses the unmodified Solr OCR Highlighting plugin to search historical word transcriptions and individual glyphs and highlight search hits on scans. PAGE XML remains the authoritative source. The first single-page prototype has been tested locally, including a browser interface without IIIF. Normalized transcriptions and alternative readings are deferred.

## Prerequisites

Docker Engine and Compose, Python 3, Pillow (for visual verification), wget and curl. The tested Solr image is 10.1 and the plugin version is 0.11.0. Commands below assume a Debian/Linux shell and the repository root as working directory unless otherwise noted. Use sudo for Docker if required.

## 1. Obtain the repository and plugin

```sh
git clone -b web-interface https://github.com/jsbien/solr-ocrhighlighting-ImpactGT.git
cd solr-ocrhighlighting-ImpactGT
mkdir -p impactgt/plugins
wget -P impactgt/plugins https://github.com/dbmdz/solr-ocrhighlighting/releases/download/0.11.0/solr-ocrhighlighting-0.11.0.jar
sudo docker pull solr:10.1
```

The Compose configuration mounts the individual plugin JAR in /opt/solr/lib. Solr 10 ignores the older XML lib directive. Mounting a directory under /var/solr/data/lib also caused a permissions failure in the initial experiment.

## 2. Sample data and optional ALTO regeneration

The sample directory contains the original PAGE 2010-03-19 XML (pc-00433094.xml), the original TIFF scan (00433094.tif, 1846 × 2212 pixels), a compatibility-transformed PAGE file (pc-00433094.compat2019.xml), and the generated ALTO file (pc-00433094.alto.xml).

The file pc-00433094.page2019.xml records an unsuccessful migration attempt using ocr-fileformat: despite its filename, it remains PAGE 2010. Do not use it as PAGE 2019 input.

The working compatibility script converts nested Point elements to a points attribute and updates the namespace and schema location. It is not a comprehensive schema migration or validation tool.

The ALTO file is already committed. Regeneration is optional:

```sh
python3 -m venv ~/.venvs/page-to-alto
source ~/.venvs/page-to-alto/bin/activate
python3 -m pip install ocrd_page_to_alto Pillow
python3 scripts/page2010_to_2019.py sample/pc-00433094.xml sample/pc-00433094.compat2019.xml
page-to-alto --alto-version 4.2 sample/pc-00433094.compat2019.xml -O sample/pc-00433094.alto.xml
```

The missing Border/PrintSpace warning is expected. Exact Python dependency versions were not recorded in the original experiment.

Observed conversion results:

| Element | Original PAGE | ALTO |
|---|---:|---:|
| Page | 1 | 1 |
| Text regions / blocks | 4 | 4 |
| Text lines | 36 | 36 |
| Words / Strings | 352 | 352 |
| Glyphs | 1769 | 0 |

All 352 word transcriptions, their XML sequence, and rectangular bounding boxes (min/max of original polygon coordinates) were identical. Glyphs are not preserved by this converter and remain available in the original PAGE source. Complete PAGE 2019 schema conformance has not been established.

## 3. Generate glyph-level MiniOCR (optional)

The original PAGE XML also contains 1,769 glyphs with 80 distinct transcriptions. In this sample, each glyph is transcribed with exactly one Unicode code point.

The committed file sample/pc-00433094.glyphs.miniocr can be regenerated directly from PAGE 2010:

```sh
python3 scripts/page_to_glyph_miniocr.py \
    sample/pc-00433094.xml \
    sample/pc-00433094.glyphs.miniocr
```

Expected output: Glyphs converted: 1769.

Each PAGE Glyph becomes a MiniOCR word element with its own bounding rectangle. Page, region and line hierarchy and XML glyph order are retained; original word boundaries are not represented. Glyph order sometimes differs from visual reading order (for example, dołek becomes dołke). This does not affect individual glyph queries, but sequence queries require further investigation. Empty and whitespace-containing glyph transcriptions are rejected by this prototype converter.

Two fields in the same Solr document share a reference to the same scanned page:

| Field | OCR format | Search unit |
|---|---|---|
| ocr_text | ALTO 4.2 | Word |
| ocr_glyphs | MiniOCR | Individual glyph |

Both fields use the same text_ocr field type and whitespace tokenizer.

## 4. Start Solr

```sh
sudo docker compose -f impactgt/compose.yaml up -d
sudo docker compose -f impactgt/compose.yaml logs --tail=80 solr
curl -s 'http://localhost:8983/solr/impactgt/select?q=*:*&wt=json'
```

The core is named impactgt. The administration interface is at http://localhost:8983/solr/. Port 8983 is bound to localhost only; this is not a public deployment. The sample directory is mounted read-only at /data inside the container. The index is stored in a persistent Compose volume.

## 5. Index the sample

```sh
curl -s -X POST 'http://localhost:8983/solr/impactgt/update?commit=true' \
  -H 'Content-Type: application/json' \
  --data-binary '[{"id":"00433094","source":"IMPACT-GT","ocr_text":"/data/pc-00433094.alto.xml","ocr_glyphs":"/data/pc-00433094.glyphs.miniocr"}]'
```

Both OCR fields store external file references. These files must remain accessible to Solr during indexing and highlighting. If reusing a core created before the glyph experiment, check whether ocr_glyphs exists before indexing. The current version-controlled schema defines both fields; an older running core can be upgraded through the Schema API (see below), or a disposable experimental index can be rebuilt as described in the restart section.

To add the field only if it is absent from an existing core:

```sh
curl -s -X POST 'http://localhost:8983/solr/impactgt/schema' \
  -H 'Content-Type: application/json' \
  --data-binary '{"add-field":{"name":"ocr_glyphs","type":"text_ocr","stored":true,"indexed":true,"multiValued":false}}'
```

Repeat the indexing command after adding the field. Both index and query analyzers use WhitespaceTokenizerFactory with no lowercasing, stemming or normalization.

## 6. Search and request OCR highlighting

```sh
curl -sG 'http://localhost:8983/solr/impactgt/select' \
  --data-urlencode 'q=ocr_text:Aniołem' \
  --data-urlencode 'fl=id' \
  --data-urlencode 'hl=true' \
  --data-urlencode 'hl.ocr.fl=ocr_text' \
  --data-urlencode 'wt=json' | python3 -m json.tool

curl -sG 'http://localhost:8983/solr/impactgt/select' \
  --data-urlencode "q=ocr_text:$(python3 -c 'print("Augu\ueadayna")')" \
  --data-urlencode 'fl=id' \
  --data-urlencode 'hl=true' \
  --data-urlencode 'hl.ocr.fl=ocr_text' | python3 -m json.tool
```

Both queries returned one document and one highlighted occurrence in the experiment. The second word contains Private Use Area character U+EADA. Absolute page coordinates are obtained by adding the parent region's upper-left coordinates to the highlight rectangle.

Expected absolute rectangles (left, top, right, bottom):

- Aniołem: (503, 165, 698, 209)
- Augu[U+EADA]yna: (793, 162, 1023, 219)

### Individual glyph search

```sh
curl -sG 'http://localhost:8983/solr/impactgt/select' \
  --data-urlencode "q=ocr_glyphs:$(python3 -c 'print("\ueada")')" \
  --data-urlencode 'fl=id' \
  --data-urlencode 'hl=true' \
  --data-urlencode 'hl.ocr.fl=ocr_glyphs' \
  --data-urlencode 'hl.snippets=100' | python3 -m json.tool
```

For U+EADA, the observed response contained one matching document, one snippet and 18 individual highlight boxes, matching the independently counted PAGE glyph frequency. The numTotal value counts snippets here, not individual glyph occurrences. Absolute highlight coordinates are calculated in the same manner as for words.

Regression targets from the original PAGE data (only U+EADA has a recorded full API result):

| Code point | Expected glyph occurrences |
|---|---:|
| U+EADA | 18 |
| U+EBA2 | 15 |
| U+EBA6 | 1 |
| U+F51E | 3 |
| U+EEC5 | 3 |

## 7. Visual verification

If the virtual environment and Pillow were not installed in step 2:

```sh
python3 -m venv ~/.venvs/page-to-alto
source ~/.venvs/page-to-alto/bin/activate
python3 -m pip install Pillow
```

```sh
source ~/.venvs/page-to-alto/bin/activate
python3 scripts/highlight.py Aniołem
xdg-open sample/00433094.highlighted.png
python3 scripts/highlight.py "$(python3 -c 'print("Augu\ueadayna")')"
xdg-open sample/00433094.highlighted.png
```

The script draws translucent yellow rectangles with red borders. It selects the PNG scan if available, otherwise TIFF, and overwrites the generated highlighted PNG on each run. The original scan is unchanged. Both test words were visually verified in the original experiment.

For glyph highlighting, pass the optional field argument:

```sh
python3 scripts/highlight.py "$(python3 -c 'print("\ueada")')" ocr_glyphs
xdg-open sample/00433094.highlighted.png
```

The glyph visualization was also reported to work in the local experiment.

## 8. Browser interface (no IIIF)

With Solr running and the sample indexed in both fields:

```sh
python3 -m venv ~/.venvs/impactgt-web
source ~/.venvs/impactgt-web/bin/activate
python3 -m pip install -r impactgt/web/requirements.txt
python3 impactgt/web/app.py
```

Open http://127.0.0.1:8080/ in a browser. The Flask server runs locally and provides a search proxy and scan delivery. The HTML/JavaScript frontend draws the returned highlight boxes as SVG overlays on the scan. TIFF files are converted to PNG on demand and cached in memory. No separate IIIF infrastructure is needed.

The interface provides Words and Glyphs modes, literal case-sensitive queries, Unicode code point notation (e.g. U+EADA), zoom, highlight visibility and navigation between matching pages. The original single-page browser prototype was reported to work locally; systematic browser regression tests have not yet been recorded.

Try Aniołem in Words mode and U+EADA in Glyphs mode. Expected results are respectively one and 18 highlight boxes. Counts displayed by the interface refer to returned highlight boxes, which need not be exhaustive for larger result sets.

See [web/README.md](web/README.md) for additional details. Stop the Flask development server with Ctrl+C; this does not stop Solr.

## 9. Stop or restart

```sh
sudo docker compose -f impactgt/compose.yaml down
sudo docker compose -f impactgt/compose.yaml up -d
```

The index survives these commands. Core configuration is copied at initial creation; editing the repository configuration does not automatically change the existing core. For this disposable single-page experiment only, after ensuring that no valuable index data is present, use down -v followed by up -d and repeat indexing to rebuild from scratch. The -v option deletes the Compose-managed index volume.

## Limitations and future work

- This is a single-page proof of concept, not a production deployment or general-purpose image viewer.
- The first snippet region returned by Solr has an unusually large vertical extent; individual highlights were visually correct, but snippet cropping warrants investigation.
- Normalized transcriptions and alternative readings are not implemented.
- Glyph sequence searches require a suitable reading order and explicit treatment of word boundaries.
- Glyph indexing and browser display have been demonstrated on one page; punctuation queries, all expected glyph frequencies, and multi-page navigation still need systematic testing.
- Corpus-scale performance and generalization to other PAGE files have not been evaluated.
- The Python visualization script accepts a Solr query fragment, not arbitrary safely escaped literal text.
- No changes to the upstream Java plugin were required.

## References

- [Solr OCR Highlighting](https://github.com/dbmdz/solr-ocrhighlighting)
- [OCR-D/page-to-alto](https://github.com/OCR-D/page-to-alto)
- [ALTO standard](https://www.loc.gov/standards/alto/)
