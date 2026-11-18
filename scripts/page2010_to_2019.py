#!/usr/bin/env python3

import sys
import xml.etree.ElementTree as ET

OLD = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2010-03-19"
NEW = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("", NEW)
ET.register_namespace("xsi", XSI)

tree = ET.parse(sys.argv[1])
root = tree.getroot()

# Check the source namespace.
if root.tag != f"{{{OLD}}}PcGts":
    raise ValueError("Expected PAGE XML 2010-03-19")

# Convert coordinate representations.
converted = 0
for coords in root.iter(f"{{{OLD}}}Coords"):
    points = coords.findall(f"{{{OLD}}}Point")
    if points:
        coords.set("points", " ".join(
            f"{p.attrib['x']},{p.attrib['y']}"
            for p in points
        ))
        for p in points:
            coords.remove(p)
        converted += 1

# Update the namespace.
for elem in root.iter():
    if elem.tag.startswith(f"{{{OLD}}}"):
        elem.tag = elem.tag.replace(OLD, NEW, 1)

root.set(
    f"{{{XSI}}}schemaLocation",
    f"{NEW} {NEW}/pagecontent.xsd"
)

tree.write(sys.argv[2],
           encoding="UTF-8",
           xml_declaration=True)

print(f"Converted {converted} coordinate elements")
