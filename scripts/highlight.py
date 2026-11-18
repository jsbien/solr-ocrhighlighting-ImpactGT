#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent.parent
SAMPLE = BASE / "sample"

SOLR = "http://localhost:8983/solr/impactgt/select"

query = sys.argv[1]
field = sys.argv[2] if len(sys.argv) > 2 else "ocr_text"

params = {
    "q": f"{field}:{query}",
    "fl": "id",
    "hl": "true",
    "hl.ocr.fl": field,
    "wt": "json",
}

with urlopen(SOLR + "?" + urlencode(params)) as response:
    result = json.load(response)

print("Matching documents:", result["response"]["numFound"])

for docid, fields in result.get("ocrHighlighting", {}).items():

    for suffix in (".png", ".tif", ".tiff"):
        filename = SAMPLE / (docid + suffix)
        if filename.exists():
            break
    else:
        print("Image not found:", docid)
        continue

    image = Image.open(filename).convert("RGBA")
    overlay = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(overlay)

    count = 0

    for snippet in fields[field]["snippets"]:
        for group in snippet["highlights"]:
            for hit in group:
                region = snippet["regions"][hit["parentRegionIdx"]]

                x1 = region["ulx"] + hit["ulx"]
                y1 = region["uly"] + hit["uly"]
                x2 = region["ulx"] + hit["lrx"]
                y2 = region["uly"] + hit["lry"]

                draw.rectangle(
                    (x1, y1, x2, y2),
                    fill=(255, 255, 0, 90),
                    outline=(255, 0, 0, 255),
                    width=3
                )

                print(repr(hit["text"]), (x1, y1, x2, y2))
                count += 1

    output = SAMPLE / (docid + ".highlighted.png")

    Image.alpha_composite(image, overlay).convert("RGB").save(output)

    print("Highlights drawn:", count)
    print("Output:", output)
