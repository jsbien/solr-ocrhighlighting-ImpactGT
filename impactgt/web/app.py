"""Local experimental search interface; no IIIF required."""
import io
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image

app = Flask(__name__)
SAMPLE = Path(__file__).resolve().parents[2] / "sample"
SOLR = "http://127.0.0.1:8983/solr/impactgt/select"
FIELDS = {"words": "ocr_text", "glyphs": "ocr_glyphs"}


def literal_query(text, mode):
    if mode == "glyphs" and re.fullmatch(r"U\+[0-9a-fA-F]{1,6}", text, re.I):
        text = chr(int(text[2:], 16))
    if not text or any(c.isspace() for c in text) or (mode == "glyphs" and len(text) != 1):
        raise ValueError("Enter one word or one glyph (or U+EADA).")
    if any(0xD800 <= ord(c) <= 0xDFFF for c in text):
        raise ValueError("Invalid Unicode scalar value.")
    return text


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/search")
def search():
    mode = request.args.get("mode", "words")
    if mode not in FIELDS:
        return jsonify(error="Unknown search mode"), 400
    try:
        text = literal_query(request.args.get("q", "").strip(), mode)
        start = max(0, int(request.args.get("start", "0")))
    except (ValueError, OverflowError) as exc:
        return jsonify(error=str(exc)), 400
    field = FIELDS[mode]
    # The term parser searches a literal indexed term, including punctuation.
    params = {"q": "{!term f=" + field + " v=$term}", "term": text,
              "fl": "id", "hl": "true", "hl.ocr.fl": field,
              "hl.snippets": 100, "rows": 1, "start": start, "wt": "json"}
    # Provide an explicit escaped phrase query for the highlighter.
    params["hl.q"] = field + ':"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'
    try:
        with urlopen(SOLR + "?" + urlencode(params), timeout=30) as response:
            data = json.load(response)
    except HTTPError as exc:
        return jsonify(error="Solr: " + exc.read().decode("utf-8", "replace")[:2000]), 502
    except (URLError, TimeoutError, ValueError) as exc:
        return jsonify(error="Solr unavailable: " + str(exc)), 502
    docs = []
    for doc in data["response"]["docs"]:
        docid = doc["id"]
        snippets = data.get("ocrHighlighting", {}).get(docid, {}).get(field, {}).get("snippets", [])
        boxes = []
        dimensions = None
        for snippet in snippets:
            for group in snippet["highlights"]:
                for hit in group:
                    region = snippet["regions"][hit["parentRegionIdx"]]
                    page = snippet["pages"][region["pageIdx"]]
                    dimensions = [page["width"], page["height"]]
                    boxes.append({"x": region["ulx"] + hit["ulx"],
                                  "y": region["uly"] + hit["uly"],
                                  "width": hit["lrx"] - hit["ulx"],
                                  "height": hit["lry"] - hit["uly"],
                                  "text": hit["text"]})
        docs.append({"id": docid, "dimensions": dimensions, "boxes": boxes})
    return jsonify(total=data["response"]["numFound"], start=start, docs=docs, term=text)


@lru_cache(maxsize=8)
def png_bytes(path, mtime):
    with Image.open(path) as image:
        output = io.BytesIO()
        image.convert("RGB").save(output, "PNG")
        return output.getvalue()


@app.get("/scan/<docid>")
def scan(docid):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", docid):
        return jsonify(error="Invalid page identifier"), 400
    for suffix in (".png", ".tif", ".tiff"):
        path = SAMPLE / (docid + suffix)
        if path.is_file():
            if suffix == ".png":
                return send_file(path, mimetype="image/png")
            return send_file(io.BytesIO(png_bytes(str(path), path.stat().st_mtime_ns)),
                             mimetype="image/png")
    return jsonify(error="Scan not found"), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
