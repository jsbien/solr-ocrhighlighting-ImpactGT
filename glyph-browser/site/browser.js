"use strict";
const $ = id => document.getElementById(id);
const state = {inventory: [], books: {}, pages: {}, glyph: null, rows: [],
    filtered: [], start: 0, selection: null, pageId: null, request: 0};
const pageSize = 100;
const collator = new Intl.Collator("pl", {sensitivity: "variant", numeric: false});
let viewer;

async function data(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(path + ": HTTP " + r.status);
    return r.json();
}
function node(tag, text, className) {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (className) e.className = className;
    return e;
}
function names(entry) {
    return entry.characters.map(c => c.name).join(" + ");
}
function count(n) { return n.toLocaleString("en-US"); }
function renderInventory() {
    const q = $("filter").value.trim().toLowerCase();
    const fragment = document.createDocumentFragment();
    for (const entry of state.inventory) {
        if (q && ![entry.transcription, entry.codepoints, entry.key, names(entry)]
            .some(t => t.toLowerCase().includes(q))) continue;
        const button = node("button", undefined, "entry inventory-row");
        button.type = "button";
        button.append(node("span", entry.transcription, "transcription"));
        const meta = node("span");
        meta.append(node("span", entry.codepoints + " · " + count(entry.count), "code"),
                    node("span", names(entry), "name"));
        button.append(meta);
        button.addEventListener("click", () => selectGlyph(entry));
        fragment.append(button);
    }
    $("inventory").replaceChildren(fragment);
}
async function selectGlyph(entry) {
    const request = ++state.request;
    state.glyph = entry;
    state.rows = [];
    state.filtered = [];
    state.start = 0;
    $("inventory-panel").hidden = true;
    $("occurrence-panel").hidden = false;
    $("selected-glyph").textContent = entry.codepoints;
    $("selected-name").textContent = names(entry);
    $("occurrences").textContent = "Loading occurrences…";
    $("range").textContent = "";
    $("previous").disabled = $("next").disabled = true;
    try {
        const rows = await data(entry.occurrences);
        if (request !== state.request) return;
        if (rows.length !== entry.count) throw new Error("Occurrence count differs from inventory");
        state.rows = rows;
        applyOrder();
    } catch (e) {
        if (request === state.request) $("occurrences").textContent = e.message;
    }
}
function applyOrder() {
    const group = $("group").value;
    state.filtered = state.rows.filter(row => !group ||
        state.pages[row.page_id].archive === "PSNC_POLISH_" + group + "_GT.ZIP");
    if ($("sort").value === "alphabetical") {
        state.filtered.sort((a,b) => collator.compare(a.word || "", b.word || "") ||
          state.pages[a.page_id].physical_order - state.pages[b.page_id].physical_order ||
          a.page_glyph_index - b.page_glyph_index);
    }
    state.start = 0;
    renderOccurrences();
}
function renderOccurrences() {
    const end = Math.min(state.start + pageSize, state.filtered.length);
    $("range").textContent = state.filtered.length ?
        count(state.start + 1) + "–" + count(end) + " / " + count(state.filtered.length) : "0 / 0";
    $("previous").disabled = state.start === 0;
    $("next").disabled = end >= state.filtered.length;
    const fragment = document.createDocumentFragment();
    for (const row of state.filtered.slice(state.start, end)) {
        const button = node("button", undefined, "entry");
        button.type = "button";
        button.setAttribute("aria-current", String(state.selection === row));
        const word = node("span", undefined, "transcription");
        if (row.word !== null && row.word_span) {
            const chars = Array.from(row.word);
            const [a,b] = row.word_span;
            word.append(document.createTextNode(chars.slice(0,a).join("")),
                node("mark", chars.slice(a,b).join("")),
                document.createTextNode(chars.slice(b).join("")));
        } else {
            word.textContent = row.word ?? "(No word transcription)";
        }
        button.append(word);
        const p = state.pages[row.page_id];
        let detail = p.book_id + " · " + row.page_id;
        if (row.word_glyph_index !== null) detail += " · glyph " + (row.word_glyph_index + 1);
        if (!row.word_span) detail += " · unaligned";
        if (!validBox(row.bbox)) detail += " · no usable box";
        button.append(node("span", detail, "detail"));
        button.addEventListener("click", () => {
            state.selection = row;
            renderOccurrences();
            displayPage(row.page_id, true);
        });
        fragment.append(button);
    }
    $("occurrences").replaceChildren(fragment);
}
function validBox(b) {
    return Array.isArray(b) && b.length === 4 && b.every(Number.isFinite) &&
        b[2] > b[0] && b[3] > b[1];
}
function updateOverlay(zoom) {
    viewer.clearOverlays();
    const item = viewer.world.getItemAt(0);
    const row = state.selection;
    if (!item || !row || row.page_id !== state.pageId) return;
    if (!validBox(row.bbox)) {
        $("image-status").textContent = "This glyph has no usable bounding box.";
        return;
    }
    const p = state.pages[row.page_id];
    if (item.getContentSize().x !== p.width || item.getContentSize().y !== p.height) {
        $("image-status").textContent = "Image dimensions differ from PAGE; highlight suppressed.";
        return;
    }
    const [x,y,r,b] = row.bbox;
    const location = item.imageToViewportRectangle(x,y,r-x,b-y);
    viewer.addOverlay({element:node("div",undefined,"glyph-overlay"),location,
        checkResize:false});
    $("image-status").textContent = "Glyph " + (row.glyph_id || row.page_glyph_index);
    if (zoom) {
        const w = Math.min(p.width, Math.max(p.width * .28,(r-x)*10));
        const h = Math.min(p.height, Math.max(p.height * .12,(b-y)*5));
        const cx = (x+r)/2, cy = (y+b)/2;
        viewer.viewport.fitBounds(item.imageToViewportRectangle(
            Math.max(0,Math.min(p.width-w,cx-w/2)),
            Math.max(0,Math.min(p.height-h,cy-h/2)),w,h));
    }
}
function displayPage(pid, zoom) {
    const p = state.pages[pid];
    const meta = state.books[p.book_id]?.metadata || {};
    $("page-title").textContent = meta.Title || p.book_id;
    $("page-info").textContent = [p.book_id,p.original_filename,pid,
        meta["Publication Details / Year"]].filter(v=>v!==null&&v!==undefined&&v!=="").join(" · ");
    const samePage = state.pageId === pid;
    state.pageId = pid;
    if (samePage && viewer.world.getItemCount() > 0) {
        updateOverlay(zoom);
        return;
    }
    $("image-status").textContent = "Loading page " + pid + "…";
    viewer.clearOverlays();
    viewer.open({type:"image",url:new URL("images/"+pid+".png",document.baseURI).href});
}
async function init() {
    if (!window.OpenSeadragon) throw new Error("OpenSeadragon is missing; run setup_site.sh.");
    viewer = OpenSeadragon({id:"viewer",showNavigationControl:false,
        showNavigator:false,animationTime:.25,visibilityRatio:.5,minZoomImageRatio:.5,
        maxZoomPixelRatio:4});
    viewer.addHandler("open", () => {
        const item = viewer.world.getItemAt(0);
        const url = new URL("images/"+state.pageId+".png",document.baseURI).href;
        if (!item || item.source.url !== url) return;
        viewer.viewport.goHome(true);
        $("image-status").textContent = "";
        updateOverlay(true);
    });
    viewer.addHandler("open-failed", e => {
        $("image-status").textContent = "Image failed to load: " + (e.message || "");
    });
    $("filter").addEventListener("input",renderInventory);
    $("back").onclick = () => {
        ++state.request;
        $("occurrence-panel").hidden = true;
        $("inventory-panel").hidden = false;
        $("filter").focus();
    };
    $("sort").onchange = $("group").onchange = applyOrder;
    $("previous").onclick = () => {state.start -= pageSize; renderOccurrences();};
    $("next").onclick = () => {state.start += pageSize; renderOccurrences();};
    $("zoom-in").onclick = () => {viewer.viewport.zoomBy(1.5);viewer.viewport.applyConstraints();};
    $("zoom-out").onclick = () => {viewer.viewport.zoomBy(1/1.5);viewer.viewport.applyConstraints();};
    $("home").onclick = () => viewer.viewport.goHome();
    $("focus").onclick = () => updateOverlay(true);
    [state.inventory,state.pages,state.books] = await Promise.all(
        [data("inventory.json"),data("pages.json"),data("books.json")]);
    $("summary").textContent = count(state.inventory.length) + " transcriptions · " +
        count(state.inventory.reduce((n,g)=>n+g.count,0))+" glyphs · "+
        count(Object.keys(state.pages).length)+" pages";
    renderInventory();
    const first = Object.values(state.pages).sort((a,b)=>a.physical_order-b.physical_order)[0];
    if (first) displayPage(first.page_id,false);
}
init().catch(e => {$("summary").textContent = e.message; console.error(e);});
