# IMPACT GT word-level search experiment

This experiment uses the unmodified Solr OCR Highlighting plugin to index historical word transcriptions and highlight search hits on scans. PAGE XML remains the authoritative source. Glyph indexing and normalized transcriptions are deferred.

## Prerequisites

Docker Engine and Compose, Python 3, Pillow (for visual verification), wget and curl. The tested Solr image is 10.1 and the plugin version is 0.11.0. Commands below assume a Debian/Linux shell and the repository root as working directory unless otherwise noted. Use sudo for Docker if required.

## 1. Obtain the repository and plugin

```sh
git clone -b page-alto-experiment https://github.com/jsbien/solr-ocrhighlighting-ImpactGT.git
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

## 3. Start Solr

```sh
sudo docker compose -f impactgt/compose.yaml up -d
sudo docker compose -f impactgt/compose.yaml logs --tail=80 solr
curl -s 'http://localhost:8983/solr/impactgt/select?q=*:*&wt=json'
```

The core is named impactgt. The administration interface is at http://localhost:8983/solr/. Port 8983 is bound to localhost only; this is not a public deployment. The sample directory is mounted read-only at /data inside the container. The index is stored in a persistent Compose volume.

## 4. Index the sample

```sh
curl -s -X POST 'http://localhost:8983/solr/impactgt/update?commit=true' \
  -H 'Content-Type: application/json' \
  --data-binary '[{"id":"00433094","source":"IMPACT-GT","ocr_text":"/data/pc-00433094.alto.xml"}]'
```

The OCR field stores an external file reference. The OCR file must remain accessible to Solr during indexing and highlighting. Both index and query analyzers use WhitespaceTokenizerFactory with no lowercasing, stemming or normalization.

## 5. Search and request OCR highlighting

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

## 6. Visual verification

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

## 7. Stop or restart

```sh
sudo docker compose -f impactgt/compose.yaml down
sudo docker compose -f impactgt/compose.yaml up -d
```

The index survives these commands. Core configuration is copied at initial creation; editing the repository configuration does not automatically change the existing core. For this disposable single-page experiment only, after ensuring that no valuable index data is present, use down -v followed by up -d and repeat indexing to rebuild from scratch. The -v option deletes the Compose-managed index volume.

## Limitations and future work

- This is a single-page prototype, not a general-purpose image viewer.
- The first snippet region returned by Solr has an unusually large vertical extent; individual highlights were visually correct, but snippet cropping warrants investigation.
- Normalized transcriptions, alternatives and glyph-level indexing are not implemented.
- Corpus-scale performance and generalization to other PAGE files have not been evaluated.
- The Python visualization script accepts a Solr query fragment, not arbitrary safely escaped literal text.
- No changes to the upstream Java plugin were required.

## References

- [Solr OCR Highlighting](https://github.com/dbmdz/solr-ocrhighlighting)
- [OCR-D/page-to-alto](https://github.com/OCR-D/page-to-alto)
- [ALTO standard](https://www.loc.gov/standards/alto/)
