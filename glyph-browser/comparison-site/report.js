"use strict";
const $=id=>document.getElementById(id);
const state={report:null,pages:{},books:{},refs:[],start:0,pair:null,row:null,edit:null,page:null};
const labels={identical:"Identyczne",whitespace_only:"Tylko białe znaki",nfc_only:"Tylko NFC",whitespace_and_nfc:"Białe znaki i NFC",different:"Inne różnice",paragraph_only_region:"Tylko paragrafowa",detailed_only_region:"Tylko szczegółowa",missing_text_one:"Brak tekstu w jednej wersji",missing_text_both:"Brak tekstu w obu wersjach",missing_public_page:"Brak strony paragrafowej",ambiguous_public_page:"Niejednoznaczne dopasowanie",error:"Błąd odczytu",detailed_pages:"Strony szczegółowe",matched_pages:"Strony wspólne",matched_regions:"Wspólne regiony",pages_all_region_texts_identical:"Strony z identycznymi tekstami",region_polygon_sequence_mismatch:"Inna sekwencja wierzchołków"};
const label=s=>labels[s]||s;
let viewer;
async function read(path){const r=await fetch(path);if(!r.ok)throw Error(path+": "+r.status);return r.json();}
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function visible(s){return s===""?"∅":s.replace(/ /g,"␠").replace(/\n/g,"↵").replace(/\t/g,"⇥");}
function codes(s){return Array.from(s,c=>"U+"+c.codePointAt(0).toString(16).toUpperCase().padStart(4,"0")).join(" ");}
function button(text,click){const n=el("button",text,"entry");n.onclick=click;return n;}
function renderPairs(){
 const q=$("query").value.toLowerCase().trim();
 let entries=state.report.changes.map((p,i)=>({...p,i})).filter(p=>!q||[p.before,p.after,visible(p.before),visible(p.after),codes(p.before),codes(p.after)].some(s=>s.toLowerCase().includes(q)));
 if($("sort").value==="code")entries.sort((a,b)=>codes(a.before).localeCompare(codes(b.before))||codes(a.after).localeCompare(codes(b.after)));
 const fragment=document.createDocumentFragment();
 for(const p of entries){const n=button(undefined,()=>{state.pair=p.i;setRefs(p.refs,visible(p.before)+" → "+visible(p.after));renderPairs();});
 n.classList.add("pair");n.setAttribute("aria-current",String(state.pair===p.i));
 const t=el("span");t.append(el("span",visible(p.before)+" → "+visible(p.after),"glyph"),el("span",codes(p.before)+" → "+codes(p.after),"code"));
 n.append(t,el("span",String(p.count)));fragment.append(n);}
 $("pairs").replaceChildren(fragment);
}
function setRefs(refs,title){state.refs=refs;state.start=0;$("match-title").textContent=title;renderMatches();}
function renderMode(){
 const mode=$("mode").value;$("pair-panel").hidden=mode!=="pairs";$("region-panel").hidden=mode!=="regions";
 if(mode==="pairs"){if(state.pair!==null){const p=state.report.changes[state.pair];setRefs(p.refs,visible(p.before)+" → "+visible(p.after));}else setRefs([],"Wybierz parę zmian");}
 else if(mode==="regions"){const c=$("category").value;setRefs((state.report.categories[c]||[]).map(i=>[i,null]),label(c));}
 else setRefs(state.report.page_report.map((p,i)=>p.status!=="matched"?[-1,i]:null).filter(Boolean),"Niedopasowane strony");
}
function renderMatches(){
 const end=Math.min(state.start+60,state.refs.length);$("range").textContent=state.refs.length?(state.start+1)+"–"+end+" / "+state.refs.length:"0";
 $("prev").disabled=state.start===0;$("next").disabled=end>=state.refs.length;
 const f=document.createDocumentFragment();
 for(const [i,j] of state.refs.slice(state.start,end)){
 if(i===-1){const p=state.report.page_report[j];f.append(button(p.page_id+" · "+label(p.status),()=>{state.row=null;state.edit=null;showMissing(p);}));continue;}
 const r=state.report.rows[i];const p=state.pages[r.page_id]||{};
 const n=button(undefined,()=>{state.row=i;state.edit=j;renderMatches();showRow(r,j);});
 n.setAttribute("aria-current",String(state.row===i&&state.edit===j));
 n.append(el("span",[p.book_id,r.page_id,r.region_id].filter(Boolean).join(" · ")));
 const edit=j===null?null:r.edits[j];
 n.append(el("span",edit?visible(edit.paragraph)+" → "+visible(edit.detailed)+" · "+label(r.status):label(r.status),"code"));f.append(n);
 }$("matches").replaceChildren(f);
}
function renderText(id,text,edits,side,selected){
 const target=$(id);target.replaceChildren();
 if(text===null||text===undefined){target.append(el("span","[brak regionu lub transkrypcji]","empty"));return;}
 const chars=Array.from(text);let pos=0;
 edits.forEach((e,i)=>{const [a,b]=e[side+"_offset"];target.append(document.createTextNode(chars.slice(pos,a).join("")));
 const m=el("mark",a===b?"∅":chars.slice(a,b).join(""),i===selected?"active":"");m.title=codes(chars.slice(a,b).join(""))||(side==="paragraph"?"wstawienie":"usunięcie");target.append(m);pos=b;});
 target.append(document.createTextNode(chars.slice(pos).join("")));
 if(selected!==null){const active=target.querySelector("mark.active");if(active)active.scrollIntoView({block:"nearest",inline:"nearest"});}
}
function showRow(r,j){
 const p=state.pages[r.page_id]||{};const b=state.books[p.book_id]?.metadata||{};
 $("meta").textContent=[b.Title||p.book_id,r.page_id,r.region_id,r.paragraph_file,label(r.status)].filter(Boolean).join(" · ");
 renderText("before",r.paragraph_text,r.edits||[],"paragraph",j);
 renderText("after",r.detailed_text,r.edits||[],"detailed",j);
 openPage(r.page_id);
}
function showMissing(p){$("meta").textContent=p.page_id+" · "+label(p.status);$("before").textContent=p.error||"Brak dopasowania";$("after").textContent=(p.candidates||[]).join("\n");openPage(p.page_id);}
function boxes(zoom){
 viewer.clearOverlays();const item=viewer.world.getItemAt(0);
 if(!item||state.row===null)return;
 const r=state.report.rows[state.row];if(r.page_id!==state.page)return;
 const expected=state.pages[state.page];const dim=item.getContentSize();
 if(dim.x!==expected.width||dim.y!==expected.height){$("image-status").textContent="Niezgodne wymiary obrazu";return;}
 const valid=b=>Array.isArray(b)&&b.length===4&&b[2]>b[0]&&b[3]>b[1];
 const bs=[[r.paragraph_box,"para"],[r.detailed_box,"detail"]].filter(([b])=>valid(b));
 for(const [b,cls] of bs)viewer.addOverlay({element:el("div",undefined,"overlay "+cls),location:item.imageToViewportRectangle(b[0],b[1],b[2]-b[0],b[3]-b[1]),checkResize:false});
 $("image-status").textContent=bs.length?"Wyróżniony region, nie pojedynczy znak":"Brak współrzędnych regionu";
 if(zoom&&bs.length){const x=Math.min(...bs.map(([b])=>b[0])),y=Math.min(...bs.map(([b])=>b[1]));const rr=Math.max(...bs.map(([b])=>b[2])),bb=Math.max(...bs.map(([b])=>b[3]));viewer.viewport.fitBounds(item.imageToViewportRectangle(x,y,rr-x,bb-y));}
}
function openPage(pid){
 const url=new URL("../images/"+pid+".png",document.baseURI).href;
 const item=viewer.world.getItemAt(0);
 if(state.page===pid&&item&&item.source.url===url){boxes(true);return;}
 state.page=pid;viewer.clearOverlays();$("image-status").textContent="Wczytywanie…";viewer.open({type:"image",url});
}
async function init(){
 [state.report,state.pages,state.books]=await Promise.all([read("report.json"),read("../pages.json"),read("../books.json")]);
 viewer=OpenSeadragon({id:"viewer",showNavigationControl:false,animationTime:.2,maxZoomPixelRatio:4});
 viewer.addHandler("open",()=>{const item=viewer.world.getItemAt(0);if(!item||item.source.url!==new URL("../images/"+state.page+".png",document.baseURI).href)return;viewer.viewport.goHome(true);$("image-status").textContent="";boxes(true);});
 viewer.addHandler("open-failed",()=>{$("image-status").textContent="Nie udało się wczytać obrazu";});
 $("home").onclick=()=>{if(viewer.world.getItemCount())viewer.viewport.goHome();};$("focus").onclick=()=>boxes(true);
 for(const [k,v] of Object.entries(state.report.summary.counts)){const n=el("div",undefined,"stat");n.append(el("span",label(k)),el("b",String(v)));$("stats").append(n);}
 for(const [k,v] of Object.entries(state.report.categories)){const n=el("option",label(k)+" ("+v.length+")");n.value=k;$("category").append(n);}
 $("mode").onchange=$("category").onchange=renderMode;$("query").oninput=$("sort").onchange=renderPairs;
 $("prev").onclick=()=>{state.start-=60;renderMatches();};$("next").onclick=()=>{state.start+=60;renderMatches();};
 renderPairs();renderMode();
}
init().catch(e=>{$("meta").textContent=e.message;console.error(e);});
