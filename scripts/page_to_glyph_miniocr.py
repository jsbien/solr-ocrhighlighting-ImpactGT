#!/usr/bin/env python3

import sys
import xml.etree.ElementTree as ET

source = ET.parse(sys.argv[1]).getroot()
ocr = ET.Element("ocr")

count = 0

for page in source.findall(".//{*}Page"):
    p = ET.SubElement(ocr, "p", {
        "xml:id": source.get("pcGtsId"),
        "wh": f"{page.get('imageWidth')} {page.get('imageHeight')}"
    })

    for region in page.findall(".//{*}TextRegion"):
        b = ET.SubElement(p, "b")

        for line in region.findall("{*}TextLine"):
            l = ET.SubElement(b, "l")

            for glyph in line.findall(".//{*}Glyph"):
                text = glyph.findtext("{*}TextEquiv/{*}Unicode")

                if not text or any(c.isspace() for c in text):
                    raise ValueError(
                        f"Unsupported glyph transcription: {text!r}"
                    )

                points = glyph.findall("{*}Coords/{*}Point")

                xs = [int(pt.get("x")) for pt in points]
                ys = [int(pt.get("y")) for pt in points]

                x, y = min(xs), min(ys)
                width = max(xs) - x
                height = max(ys) - y

                w = ET.SubElement(l, "w", {
                    "x": f"{x} {y} {width} {height}"
                })

                w.text = text
                w.tail = " "
                count += 1

            l.tail = " "

ET.ElementTree(ocr).write(sys.argv[2], encoding="utf-8")

print("Glyphs converted:", count)
