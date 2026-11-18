const $ = id => document.getElementById(id);
const ns = "http://www.w3.org/2000/svg";
let active = null, start = 0, total = 0, serial = 0;
function zoom() {
  $("sheet").style.width = $("zoom").value + "%";
}
async function search(offset) {
  const token = ++serial;
  $("status").textContent = "Searching…";
  $("result").hidden = true;
  try {
    const params = new URLSearchParams({...active, start: offset});
    const response = await fetch("/api/search?" + params);
    const data = await response.json();
    if (token !== serial) return;
    if (!response.ok) throw new Error(data.error || "Search failed");
    total = data.total; start = data.start;
    if (!data.docs.length) {
      $("status").textContent = "No matching pages.";
      return;
    }
    const doc = data.docs[0];
    $("status").textContent = total + " matching pages; " + doc.boxes.length + " highlight boxes on this page (returned by Solr).";
    $("page").textContent = (start + 1) + " / " + total + " — " + doc.id;
    $("previous").disabled = start === 0;
    $("next").disabled = start + 1 >= total;
    const sheet = $("sheet");
    sheet.replaceChildren();
    const image = new Image();
    image.alt = "Scan " + doc.id;
    image.src = "/scan/" + encodeURIComponent(doc.id);
    sheet.append(image);
    image.onerror = () => { if(token === serial) $("status").textContent += " Scan could not be loaded."; };
    if (doc.dimensions) {
      const svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", "0 0 " + doc.dimensions.join(" "));
      svg.setAttribute("aria-label", "Search highlights");
      for (const box of doc.boxes) {
        const rect = document.createElementNS(ns, "rect");
        for (const key of ["x","y","width","height"]) rect.setAttribute(key, box[key]);
        const title = document.createElementNS(ns, "title");
        title.textContent = box.text;
        rect.append(title);
        svg.append(rect);
      }
      svg.style.display = $("show").checked ? "" : "none";
      sheet.append(svg);
    }
    zoom();
    $("result").hidden = false;
  } catch (error) {
    if (token === serial) $("status").textContent = error.message;
  }
}
$("search").addEventListener("submit", event => {
  event.preventDefault();
  active = {mode: $("mode").value, q: $("query").value};
  search(0);
});
$("mode").addEventListener("change", () => {
  $("hint").textContent = $("mode").value === "glyphs" ? "One glyph or Unicode notation, e.g. U+EADA." : "Exact indexed word, case-sensitive.";
  $("query").value = $("mode").value === "glyphs" ? "U+EADA" : "Aniołem";
});
$("previous").onclick = () => search(start - 1);
$("next").onclick = () => search(start + 1);
$("zoom").oninput = zoom;
$("show").onchange = () => {
  const svg = $("sheet").querySelector("svg");
  if (svg) svg.style.display = $("show").checked ? "" : "none";
};
