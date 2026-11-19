#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then
    echo "Usage: bash glyph-browser/setup_site.sh /path/to/glyph-browser-data" >&2
    exit 2
fi
here="$(cd -- "$(dirname -- "$0")" && pwd)"
data="$1"
for item in inventory.json books.json pages.json; do
    test -f "$data/$item" || { echo "Missing $data/$item" >&2; exit 1; }
done
mkdir -p "$data/vendor"
fetch() {
    local url="$1" dest="$2"
    if [ ! -s "$dest" ]; then
        curl -fL --retry 2 -o "$dest.tmp" "$url"
        mv "$dest.tmp" "$dest"
    fi
}
fetch "https://cdn.jsdelivr.net/npm/openseadragon@6.1.1/build/openseadragon/openseadragon.min.js" "$data/vendor/openseadragon.min.js"
fetch "https://raw.githubusercontent.com/psb1558/Junicode-font/586bf02302229d3c2507f9daf261cbe614e273c1/webfiles/JunicodeVF-Roman.woff2" "$data/vendor/JunicodeVF-Roman.woff2"
cp "$here/site/"{index.html,style.css,browser.js} "$data/"
echo "Browser installed in $data"
echo "Serve this directory locally with python3 -m http.server."
