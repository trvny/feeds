// ── constants ────────────────────────────
const SCHEMA_V = 1;
const NS = 'fs:';
const FEED_TIMEOUT_MS = 15000;
const OPML_TIMEOUT_MS = 15000;
const ITEM_LIMIT = 250;
const RSS_FALLBACK = "data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%3E%3Crect%20width='24'%20height='24'%20rx='5'%20fill='%23d6541a'/%3E%3Ccircle%20cx='7'%20cy='17'%20r='2'%20fill='%23fff'/%3E%3Cpath%20d='M5%2011a8%208%200%200%201%208%208h2.6A10.6%2010.6%200%200%200%205%208.4z'%20fill='%23fff'/%3E%3Cpath%20d='M5%205a14%2014%200%200%201%2014%2014h2.6A16.6%2016.6%200%200%200%205%202.4z'%20fill='%23fff'/%3E%3C/svg%3E";
const FAVS_MAX = 500;

// ── storage layer ────────────────────────────
const ls = {
  get: k => { try{ return localStorage.getItem(NS+k); }catch(e){ return null; } },
  set: (k,v) => { try{ localStorage.setItem(NS+k,v); return true; }catch(e){ return false; } },
  del: k => { try{ localStorage.removeItem(NS+k); return true; }catch(e){ return false; } },
};

// one-time migration of bare keys from the previous version
(function migrate(){
  try{
    const oldProxy = localStorage.getItem('proxy');
    const oldOpml  = localStorage.getItem('opml');
    const oldSnap  = localStorage.getItem('snap');
    if(oldProxy || oldOpml){
      const existing = JSON.parse(ls.get('cfg')||'{}');
      if(oldProxy && !existing.proxy) existing.proxy = oldProxy;
      if(oldOpml  && !existing.opml)  existing.opml  = oldOpml;
      ls.set('cfg', JSON.stringify(existing));
      localStorage.removeItem('proxy');
      localStorage.removeItem('opml');
    }
    if(oldSnap && !ls.get('snap')){
      ls.set('snap', oldSnap);
      localStorage.removeItem('snap');
    }
  }catch(e){}
})();

// ── config ────────────────────────────
let savedCfg = {};
try{ savedCfg = JSON.parse(ls.get('cfg')||'{}'); }catch(e){}
const cfg = {
  proxy: savedCfg.proxy || '',
  opml:  savedCfg.opml  || '../subscriptions.opml',
  favs:  savedCfg.favs !== false,
  thumbs: savedCfg.thumbs !== false,
};
function saveCfg(){
  ls.set('cfg', JSON.stringify({proxy:cfg.proxy, opml:cfg.opml, favs:cfg.favs, thumbs:cfg.thumbs}));
}

// ── subscription overlay ────────────────────────────
function loadOverlay(){
  try{
    const o = JSON.parse(ls.get('overlay')||'{}');
    return { removed: Array.isArray(o.removed)?o.removed:[],
             added:   Array.isArray(o.added)?o.added:[] };
  }catch(e){ return {removed:[], added:[]}; }
}
function saveOverlay(){ ls.set('overlay', JSON.stringify({removed:overlay.removed, added:overlay.added})); }
let overlay = loadOverlay();

// ── snapshot (feed cache) ────────────────────────
function loadSnap(){
  try{
    const s = JSON.parse(ls.get('snap')||'null');
    if(!s || s._v !== SCHEMA_V || !Array.isArray(s.items)) return null;
    return s;
  }catch(e){ return null; }
}
function saveSnap(items){
  let remaining = items;
  while(remaining.length){
    const payload = JSON.stringify({_v:SCHEMA_V, t:Date.now(), items:remaining});
    if(ls.set('snap', payload)) return;
    remaining = remaining.slice(0, Math.floor(remaining.length/2));
  }
}

// ── favicon cache ──────────────────────────
let favsCache = {};
try{ favsCache = JSON.parse(ls.get('favs')||'{}'); }catch(e){}
function saveFavsCache(){
  const keys = Object.keys(favsCache);
  if(keys.length > FAVS_MAX){
    const pruned = {};
    keys.slice(-FAVS_MAX).forEach(k => pruned[k] = favsCache[k]);
    favsCache = pruned;
  }
  ls.set('favs', JSON.stringify(favsCache));
}
function makeFav(h){
  if(!cfg.favs || !h) return null;
  const img=document.createElement('img');
  img.className='fav';
  img.loading='lazy';
  img.alt='';
  const remember=state=>{ favsCache[h]=state; saveFavsCache(); };
  const useFallback=()=>{ img.onerror=null; img.onload=null; img.src=RSS_FALLBACK; remember('x'); };
  const useGoogle=()=>{
    img.onerror=useFallback;
    img.onload=()=>remember('g');
    img.src=`https://www.google.com/s2/favicons?domain=${encodeURIComponent(h)}&sz=32`;
  };
  const state=favsCache[h];
  if(state==='x') img.src=RSS_FALLBACK;
  else if(state==='g') useGoogle();
  else{
    img.onerror=useGoogle;
    img.onload=()=>remember('ddg');
    img.src=`https://icons.duckduckgo.com/ip3/${encodeURIComponent(h)}.ico`;
  }
  return img;
}

// ── feed parsing ───────────────────────────
const $ = s => document.querySelector(s);
let ITEMS = [], FILTER = null, FAILED = [], SOURCES = [], LOADED = 0, FEEDS = [];
let STATUS_ERROR = '', activeRun = null, runVersion = 0;

function safeHttpUrl(value, base=document.baseURI){
  try{
    const u=new URL(String(value||'').trim(), base);
    return u.protocol==='http:' || u.protocol==='https:' ? u.href : '';
  }catch(e){ return ''; }
}
function prox(u){ return cfg.proxy ? cfg.proxy + encodeURIComponent(u) : u; }
function txt(el,...names){
  const wanted=new Set(names.map(n=>n.toLowerCase().replace(/^.*:/,'')));
  for(const c of el.children){
    const local=c.tagName.toLowerCase().replace(/^.*:/,'');
    if(wanted.has(local) && c.textContent.trim()) return c.textContent.trim();
  }
  return '';
}
function lnk(el){
  for(const c of el.children){
    const t=c.tagName.toLowerCase().replace(/^.*:/,'');
    if(t==='link'){
      const href=c.getAttribute('href');
      if(href && (c.getAttribute('rel')||'alternate')==='alternate') return href;
      if(c.textContent.trim()) return c.textContent.trim();
    }
  }
  return txt(el,'guid');
}
function clean(s){
  if(!s) return '';
  s=s.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
  return s.length>180 ? s.slice(0,180).replace(/\s+\S*$/,'')+'…' : s;
}
function host(url){ try{ return new URL(url).hostname; }catch(e){ return ''; } }
function mediaImg(n, base){
  const kids=n.getElementsByTagName('*');
  const local=e=>e.tagName.toLowerCase().replace(/^.*:/,'');
  for(const e of kids){
    if(local(e)==='thumbnail'){
      const u=safeHttpUrl(e.getAttribute('url'),base); if(u) return u;
    }
  }
  for(const e of kids){
    if(local(e)==='content'){
      const t=e.getAttribute('type')||'', m=e.getAttribute('medium')||'';
      const u=safeHttpUrl(e.getAttribute('url'),base);
      if(u && (m==='image'||t.startsWith('image'))) return u;
    }
  }
  for(const e of kids){
    if(local(e)==='enclosure'){
      const t=e.getAttribute('type')||'', u=safeHttpUrl(e.getAttribute('url'),base);
      if(u && t.startsWith('image')) return u;
    }
  }
  const body=txt(n,'encoded','content','description','summary');
  const m=body && body.match(/<img[^>]+src=["']([^"']+)["']/i);
  return m ? safeHttpUrl(m[1],base) : '';
}
function parseFeed(xml, source, feedUrl){
  const doc=new DOMParser().parseFromString(xml,'text/xml');
  if(doc.querySelector('parsererror')) throw new Error('bad xml');
  return [...doc.querySelectorAll('item, entry')].map(n=>{
    const d=txt(n,'pubdate','published','updated','date');
    const ts=d ? Date.parse(d) : NaN;
    const title=txt(n,'title')||'(untitled)';
    let desc=clean(txt(n,'description','summary','content','encoded'));
    if(desc && desc.toLowerCase()===title.toLowerCase()) desc='';
    return {source, title, desc, url:safeHttpUrl(lnk(n),feedUrl),
            ts:isNaN(ts)?0:ts, img:mediaImg(n,feedUrl)};
  }).filter(i=>i.title && i.url);
}
function rel(ts){
  if(!ts) return '';
  const s=Math.max(0,(Date.now()-ts)/1000);
  if(s<3600) return Math.max(1,Math.round(s/60))+'m';
  if(s<86400) return Math.round(s/3600)+'h';
  if(s<604800) return Math.round(s/86400)+'d';
  return new Date(ts).toLocaleDateString(undefined,{month:'short',day:'numeric'});
}

// ── OPML helpers ───────────────────────────
function decodeXmlAttr(value){
  return String(value).replace(/&(?:#(x[0-9a-f]+|[0-9]+)|amp|quot|apos|lt|gt);/gi,(entity,numeric)=>{
    if(numeric){
      const radix=numeric[0].toLowerCase()==='x'?16:10;
      const digits=radix===16?numeric.slice(1):numeric;
      const code=Number.parseInt(digits,radix);
      try{ return Number.isFinite(code)?String.fromCodePoint(code):entity; }catch(e){ return entity; }
    }
    return ({'&amp;':'&','&quot;':'"','&apos;':"'",'&lt;':'<','&gt;':'>'})[entity.toLowerCase()]||entity;
  });
}
function parseOpml(text, base=document.baseURI){
  const src=String(text??'');
  if(/<!doctype|<!entity/i.test(src)) throw new Error('unsupported xml');
  const feeds=[];
  for(const match of src.matchAll(/<outline\b[^>]*>/gi)){
    const attrs={};
    for(const attr of match[0].matchAll(/([:\w.-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g)){
      attrs[attr[1].toLowerCase()]=decodeXmlAttr(attr[2]??attr[3]??'');
    }
    const xmlUrl=safeHttpUrl(attrs.xmlurl,base);
    if(xmlUrl) feeds.push({title:attrs.title||attrs.text||'feed',xmlUrl});
  }
  return feeds;
}
function opmlOutlineCount(text){
  try{ return parseOpml(text).length; }catch(e){ return 0; }
}
function buildOpml(feeds){
  const esc=s=>String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const body=feeds.map(f=>
    `    <outline type="rss" text="${esc(f.title)}" title="${esc(f.title)}" xmlUrl="${esc(f.xmlUrl)}"/>`
  ).join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<opml version="2.0">\n  <head><title>feed·seek subscriptions</title></head>\n  <body>\n${body}\n  </body>\n</opml>\n`;
}

// ── data loading ──────────────────────────
async function fetchText(url, options={}, timeoutMs=FEED_TIMEOUT_MS){
  const controller=new AbortController();
  const parent=options.signal;
  const abort=()=>controller.abort();
  if(parent){
    if(parent.aborted) abort();
    else parent.addEventListener('abort',abort,{once:true});
  }
  const timer=setTimeout(abort,timeoutMs);
  try{
    const r=await fetch(url,{...options,signal:controller.signal});
    if(!r.ok) throw new Error(String(r.status));
    return await r.text();
  }finally{
    clearTimeout(timer);
    if(parent) parent.removeEventListener('abort',abort);
  }
}
async function loadFeed(f, signal){
  const xml=await fetchText(prox(f.xmlUrl),{redirect:'follow',signal},FEED_TIMEOUT_MS);
  return parseFeed(xml,f.title,f.xmlUrl);
}
function fairLimit(items, limit){
  if(items.length<=limit) return items;
  const chosen=[], seenSources=new Set(), chosenUrls=new Set();
  for(const item of items){
    if(!seenSources.has(item.source)){
      chosen.push(item); seenSources.add(item.source); chosenUrls.add(item.url);
      if(chosen.length===limit) return chosen;
    }
  }
  for(const item of items){
    if(!chosenUrls.has(item.url)){
      chosen.push(item); chosenUrls.add(item.url);
      if(chosen.length===limit) break;
    }
  }
  return chosen.sort((a,b)=>b.ts-a.ts);
}
function setProgress(done,total,version){
  if(version===runVersion) $('#prog').style.width=(done/total*100)+'%';
}
async function run(){
  const version=++runVersion;
  if(activeRun) activeRun.abort();
  const controller=new AbortController();
  activeRun=controller;
  STATUS_ERROR='';
  $('#refresh').disabled=true;
  $('#refresh').setAttribute('aria-busy','true');
  if(!ITEMS.length) setMessage('Loading…');

  try{
    const customOpml=ls.get('customOpml');
    let feeds;
    try{
      let opmlText, opmlBase=document.baseURI;
      if(customOpml) opmlText=customOpml;
      else{
        opmlBase=new URL(cfg.opml,document.baseURI).href;
        opmlText=await fetchText(opmlBase,{cache:'no-cache',signal:controller.signal},OPML_TIMEOUT_MS);
      }
      feeds=parseOpml(opmlText,opmlBase);
    }catch(e){
      if(version!==runVersion || controller.signal.aborted) return;
      FEEDS=[]; LOADED=0; FAILED=[];
      STATUS_ERROR=customOpml ? 'Imported OPML is invalid.' : 'Could not load subscriptions.opml.';
      render();
      return;
    }

    const rm=new Set(overlay.removed.map(x=>safeHttpUrl(x)).filter(Boolean));
    feeds=feeds.filter(f=>!rm.has(f.xmlUrl));
    const have=new Set(feeds.map(f=>f.xmlUrl));
    for(const a of overlay.added){
      const xmlUrl=safeHttpUrl(a.xmlUrl);
      if(xmlUrl && !have.has(xmlUrl)){
        feeds.push({title:a.title||xmlUrl,xmlUrl}); have.add(xmlUrl);
      }
    }
    if(!feeds.length){
      if(version!==runVersion) return;
      ITEMS=[]; FEEDS=[]; FAILED=[]; SOURCES=[]; LOADED=0; FILTER=null;
      STATUS_ERROR='No feeds in the OPML yet.';
      render();
      return;
    }

    let done=0;
    const results=await Promise.allSettled(feeds.map(async f=>{
      try{ return await loadFeed(f,controller.signal); }
      finally{ done++; setProgress(done,feeds.length,version); }
    }));
    if(version!==runVersion || controller.signal.aborted) return;

    const nextItems=[], nextFailed=[];
    results.forEach((res,i)=>{
      if(res.status==='fulfilled') nextItems.push(...res.value);
      else nextFailed.push(feeds[i].title);
    });
    const seen=new Set();
    const deduped=nextItems.filter(i=>!seen.has(i.url)&&seen.add(i.url)).sort((a,b)=>b.ts-a.ts);
    const limited=fairLimit(deduped,ITEM_LIMIT);

    ITEMS=limited;
    FAILED=nextFailed;
    SOURCES=[...new Set(ITEMS.map(i=>i.source))].sort();
    LOADED=feeds.length-nextFailed.length;
    FEEDS=feeds;
    if(FILTER && !SOURCES.includes(FILTER)) FILTER=null;
    saveSnap(ITEMS);
    render();
  }catch(e){
    if(version===runVersion && !controller.signal.aborted){
      console.error(e);
      STATUS_ERROR='Unexpected reader error.';
      render();
    }
  }finally{
    finishRun(version);
  }
}
function finishRun(version){
  if(version!==runVersion) return;
  activeRun=null;
  $('#prog').style.width='0';
  $('#refresh').disabled=false;
  $('#refresh').removeAttribute('aria-busy');
}

// ── rendering ──────────────────────────
function setMessage(text){
  const msg=document.createElement('div');
  msg.className='msg';
  msg.textContent=text;
  $('#list').replaceChildren(msg);
}
function render(){
  const sources=SOURCES.length?SOURCES:[...new Set(ITEMS.map(i=>i.source))].sort();
  if(FILTER && !sources.includes(FILTER)) FILTER=null;

  const chipFrag=document.createDocumentFragment();
  for(const source of ['All',...sources]){
    const button=document.createElement('button');
    button.className='chip'+(((FILTER===null&&source==='All')||FILTER===source)?' on':'');
    button.dataset.source=source;
    button.textContent=source;
    chipFrag.appendChild(button);
  }
  $('#chips').replaceChildren(chipFrag);

  const shown=FILTER?ITEMS.filter(i=>i.source===FILTER):ITEMS;
  $('#count').textContent=`${shown.length} items · ${LOADED||sources.length} feeds`+(FAILED.length?` · ${FAILED.length} failed`:'');
  const listFrag=document.createDocumentFragment();
  for(const item of shown){
    const url=safeHttpUrl(item.url); if(!url) continue;
    const link=document.createElement('a');
    link.className='item'; link.href=url; link.target='_blank'; link.rel='noopener';
    const text=document.createElement('div'); text.className='itxt';
    const source=document.createElement('div'); source.className='src';
    const fav=makeFav(host(url)); if(fav) source.appendChild(fav);
    source.appendChild(document.createTextNode(item.source||'feed'));
    const title=document.createElement('div'); title.className='t'; title.textContent=item.title||'(untitled)';
    text.append(source,title);
    if(item.desc){ const desc=document.createElement('div'); desc.className='desc'; desc.textContent=item.desc; text.appendChild(desc); }
    const meta=document.createElement('div'); meta.className='meta'; meta.textContent=rel(item.ts); text.appendChild(meta);
    link.appendChild(text);
    if(cfg.thumbs && item.img){
      const imgUrl=safeHttpUrl(item.img,url);
      if(imgUrl){
        const thumb=document.createElement('img'); thumb.className='thumb'; thumb.loading='lazy'; thumb.alt=''; thumb.src=imgUrl;
        thumb.onerror=()=>thumb.remove(); link.appendChild(thumb);
      }
    }
    listFrag.appendChild(link);
  }
  if(!shown.length && STATUS_ERROR){
    const msg=document.createElement('div'); msg.className='msg'; msg.textContent=STATUS_ERROR; listFrag.appendChild(msg);
  }else if(STATUS_ERROR){
    const warn=document.createElement('div'); warn.className='warn'; warn.textContent=STATUS_ERROR; listFrag.appendChild(warn);
  }
  if(FAILED.length){
    const warn=document.createElement('div'); warn.className='warn';
    warn.textContent=`⚠ ${FAILED.length} feed(s) failed${cfg.proxy?'':' — set a CORS proxy in ⚙'}`;
    listFrag.appendChild(warn);
  }
  if(!listFrag.childNodes.length){
    const msg=document.createElement('div'); msg.className='msg'; msg.textContent='Nothing here.'; listFrag.appendChild(msg);
  }
  $('#list').replaceChildren(listFrag);
}

// ── events ─────────────────────────
document.addEventListener('click',e=>{
  const c=e.target.closest('.chip');
  if(c){ FILTER=c.dataset.source==='All'?null:c.dataset.source; render(); }
});
$('#refresh').onclick=()=>void run();
$('#gear').onclick=()=>{
  $('#proxy').value=cfg.proxy;
  $('#opml').value=cfg.opml;
  $('#showfavs').checked=cfg.favs;
  $('#showthumbs').checked=cfg.thumbs;
  const custom=ls.get('customOpml');
  $('#importStatus').textContent=custom
    ? `Using imported file (${opmlOutlineCount(custom)} feeds) instead of the OPML URL.`
    : '';
  $('#clearImport').style.display=custom?'':'none';
  renderManage();
  $('#settings').showModal();
};
$('#importOpml').onclick=()=>$('#opmlFile').click();
$('#opmlFile').onchange=async e=>{
  const file=e.target.files[0]; e.target.value='';
  if(!file) return;
  const text=await file.text();
  const n=opmlOutlineCount(text);
  if(!n){ $('#importStatus').textContent='Invalid OPML file — no valid HTTP(S) feeds found.'; return; }
  ls.set('customOpml',text);
  $('#importStatus').textContent=`Imported ${file.name} (${n} feeds) — using this instead of the OPML URL.`;
  $('#clearImport').style.display='';
  $('#settings').close();
  void run();
};
$('#exportOpml').onclick=()=>{
  if(!FEEDS.length){ $('#importStatus').textContent='No feeds loaded yet — refresh first.'; return; }
  const blob=new Blob([buildOpml(FEEDS)],{type:'text/x-opml+xml'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a'); a.href=url; a.download='subscriptions.opml';
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
};
$('#clearImport').onclick=()=>{
  ls.del('customOpml');
  $('#importStatus').textContent='';
  $('#clearImport').style.display='none';
  $('#settings').close();
  void run();
};
function renderManage(){
  const el=$('#manageList');
  if(!FEEDS.length){
    const empty=document.createElement('div');
    empty.style.cssText='color:var(--mut);font-size:12px;padding:6px 0';
    empty.textContent='No feeds loaded — hit ↻ first.';
    el.replaceChildren(empty); return;
  }
  const frag=document.createDocumentFragment();
  FEEDS.forEach((f,i)=>{
    const row=document.createElement('div'); row.className='mrow';
    const title=document.createElement('span'); title.className='mt'; title.textContent=f.title||f.xmlUrl;
    const remove=document.createElement('button'); remove.type='button'; remove.className='mx'; remove.dataset.index=String(i); remove.title='Remove'; remove.textContent='✕';
    row.append(title,remove); frag.appendChild(row);
  });
  el.replaceChildren(frag);
}
$('#manageList').onclick=e=>{
  const b=e.target.closest('.mx'); if(!b) return;
  const index=Number(b.dataset.index), f=FEEDS[index]; if(!f) return;
  if(overlay.added.some(a=>a.xmlUrl===f.xmlUrl)) overlay.added=overlay.added.filter(a=>a.xmlUrl!==f.xmlUrl);
  else if(!overlay.removed.includes(f.xmlUrl)) overlay.removed.push(f.xmlUrl);
  FEEDS.splice(index,1);
  saveOverlay(); renderManage(); void run();
};
$('#addFeed').onclick=()=>{
  const t=$('#addTitle').value.trim(), raw=$('#addUrl').value.trim();
  if(!raw) return;
  const u=safeHttpUrl(raw);
  if(!u){ $('#importStatus').textContent='Feed URL must be a valid http(s):// URL.'; return; }
  if(FEEDS.some(f=>f.xmlUrl===u)){ $('#addTitle').value=''; $('#addUrl').value=''; return; }
  overlay.removed=overlay.removed.filter(x=>x!==u);
  overlay.added=overlay.added.filter(a=>a.xmlUrl!==u);
  overlay.added.push({title:t||u,xmlUrl:u});
  saveOverlay();
  FEEDS.push({title:t||u,xmlUrl:u});
  $('#addTitle').value=''; $('#addUrl').value=''; $('#importStatus').textContent='';
  renderManage(); void run();
};
$('#cancel').onclick=()=>$('#settings').close();
$('#save').onclick=()=>{
  cfg.proxy=$('#proxy').value.trim();
  cfg.opml=$('#opml').value.trim()||'../subscriptions.opml';
  cfg.favs=$('#showfavs').checked;
  cfg.thumbs=$('#showthumbs').checked;
  saveCfg();
  $('#settings').close();
  void run();
};

// ── init ──────────────────────────
const snap=loadSnap();
if(snap && snap.items.length){ ITEMS=snap.items; render(); }
void run();
