/**
 * feedy news Worker
 *
 * Routes
 *   GET /?feeds=<url,url,...>&limit=20
 *     -> { items: [{ title, link, summary, image, date, source }], count, fetched }
 *     Fetches/parses RSS+Atom, merges, de-dupes, sorts newest-first. Conditional
 *     GET via a weak ETag over the item set (304 when nothing changed).
 *
 *   GET /discover?url=<page>
 *     -> { feeds: [{ url, title, type }], count }
 *     Finds a site's native feed when it isn't obvious: reads
 *     <link rel="alternate" type="application/rss+xml|atom+xml"> from the page
 *     head, and (only if none are advertised) probes a few common feed paths.
 *
 *   GET /scrape?url=<page>[&item=<sel>&title=<sel>&link=<sel>&image=<sel>&summary=<sel>]
 *     -> Atom XML
 *     Turns a site WITHOUT a native feed into Atom, extracted at the edge with
 *     HTMLRewriter (no DOM, no headless browser). With no selectors it
 *     auto-detects the repeating item block. Emits Atom (not JSON) on purpose,
 *     so the resulting /scrape URL drops into the app's feed list and works in
 *     both on-device and backend modes, and round-trips through OPML unchanged.
 *
 *   GET /health -> { ok: true }
 *
 * Cloudflare infra, all free-tier safe:
 *   - Cache API (caches.default): fast per-colo layer in front of every route.
 *   - Workers KV (optional binding SCRAPE_KV): durable cross-colo layer for
 *     /discover and /scrape so a cold cache doesn't re-hit origin sites. Writes
 *     are gated to cache-miss + non-empty + TTL'd, to stay well under the free
 *     1k-writes/day cap; if the binding is absent the code degrades to Cache-API
 *     only. No D1/R2/Browser-Rendering/AI: scrape config lives in the URL, so the
 *     Worker stays stateless and within CPU limits.
 */

export interface Env {
  /** Optional comma-separated default feeds when the request omits ?feeds= */
  DEFAULT_FEEDS?: string;
  /** Optional comma-separated allowlist of host suffixes. Empty = allow any. */
  ALLOWED_HOSTS?: string;
  /** Optional KV namespace for durable discover/scrape caching. Absent = Cache-API only. */
  SCRAPE_KV?: KVNamespace;
}

export interface NewsItem {
  title: string;
  link: string;
  summary: string;
  image: string | null;
  date: string | null;
  source: string;
}

const FEED_TIMEOUT_MS = 6000;
const PAGE_TIMEOUT_MS = 6000;
const CACHE_TTL_S = 300;
const DISCOVER_KV_TTL_S = 86_400; // 24h
const SCRAPE_KV_TTL_S = 3_600; // 1h
const MAX_FEEDS = 12;
const HARD_LIMIT = 60;
const MAX_HTML_BYTES = 1_200_000; // cap buffered HTML to bound CPU/memory
const MAX_SCRAPE_ITEMS = 30;
const MAX_DISCOVERED = 10;

/** Repeating-block selectors tried in order when ?item= is omitted. */
const SCRAPE_CANDIDATES = ["article", "[class*=post]", "[class*=entry]", "[class*=card]", "main li"];
/** Common feed paths probed only when a page advertises no <link alternate>. */
const FEED_PATHS = ["/feed", "/feed/", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml"];

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "content-type, accept, if-none-match",
  "access-control-expose-headers": "etag",
};

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (req.method !== "GET") return json({ error: "method not allowed" }, 405);

    const url = new URL(req.url);
    if (url.pathname === "/health") return json({ ok: true });
    if (url.pathname === "/discover") return handleDiscover(url, env, ctx);
    if (url.pathname === "/scrape") return handleScrape(req, url, env, ctx);
    return handleFeeds(req, url, env, ctx);
  },
};

// --- /?feeds= : RSS/Atom merge (unchanged behavior) ---

async function handleFeeds(req: Request, url: URL, env: Env, ctx: ExecutionContext): Promise<Response> {
  const inm = req.headers.get("if-none-match");

  const cache = caches.default;
  const cacheKey = new Request(url.toString());
  const cached = await cache.match(cacheKey);
  if (cached) {
    const tag = cached.headers.get("etag");
    if (tag && inm && etagMatches(inm, tag)) return notModified(tag);
    return cached;
  }

  const feedsParam = url.searchParams.get("feeds") || env.DEFAULT_FEEDS || "";
  const limit = clamp(parseInt(url.searchParams.get("limit") || "20", 10) || 20, 1, HARD_LIMIT);

  const feeds = feedsParam.split(",").map((s) => s.trim()).filter(Boolean).slice(0, MAX_FEEDS);
  if (!feeds.length) return json({ error: "no feeds supplied (use ?feeds=url1,url2)" }, 400);

  const valid: string[] = [];
  for (const f of feeds) {
    try {
      const h = new URL(f);
      if (h.protocol !== "https:" && h.protocol !== "http:") continue;
      if (!hostAllowed(h.hostname, env)) continue;
      valid.push(f);
    } catch { /* skip malformed */ }
  }
  if (!valid.length) return json({ error: "no valid/allowed feeds" }, 400);

  const results = await Promise.allSettled(valid.map((f) => fetchFeed(f)));
  const items: NewsItem[] = [];
  for (const r of results) if (r.status === "fulfilled") items.push(...r.value);

  const merged = dedupe(items)
    .sort((a, b) => (Date.parse(b.date || "") || 0) - (Date.parse(a.date || "") || 0))
    .slice(0, limit);

  const etag = await weakEtag(JSON.stringify(merged));

  const res = json({ items: merged, count: merged.length, fetched: new Date().toISOString() });
  res.headers.set("cache-control", `public, max-age=${CACHE_TTL_S}`);
  res.headers.set("etag", etag);
  ctx.waitUntil(cache.put(cacheKey, res.clone()));

  if (inm && etagMatches(inm, etag)) return notModified(etag);
  return res;
}

// --- /discover : find a site's native feed ---

async function handleDiscover(url: URL, env: Env, ctx: ExecutionContext): Promise<Response> {
  const page = (url.searchParams.get("url") || "").trim();
  let pageHost: string;
  try {
    const u = new URL(page);
    if (u.protocol !== "https:" && u.protocol !== "http:") throw new Error("scheme");
    pageHost = u.hostname;
  } catch {
    return json({ error: "bad or missing ?url=" }, 400);
  }
  if (!hostAllowed(pageHost, env)) return json({ error: "host not allowed" }, 403);

  const cache = caches.default;
  const cacheKey = new Request(url.toString());
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const kvKey = `disc:${page}`;
  if (env.SCRAPE_KV) {
    const stored = await env.SCRAPE_KV.get(kvKey);
    if (stored) {
      const res = json(JSON.parse(stored));
      res.headers.set("cache-control", `public, max-age=${CACHE_TTL_S}`);
      ctx.waitUntil(cache.put(cacheKey, res.clone()));
      return res;
    }
  }

  let feeds: { url: string; title: string; type: string }[] = [];
  try {
    const html = await fetchHtml(page);
    feeds = await discoverFeedLinks(page, html);
    if (!feeds.length) feeds = await probeFeedPaths(page, env);
  } catch { /* return whatever we have (possibly none) */ }

  feeds = dedupeBy(feeds, (f) => f.url).slice(0, MAX_DISCOVERED);
  const payload = { feeds, count: feeds.length };

  if (env.SCRAPE_KV && feeds.length) {
    ctx.waitUntil(env.SCRAPE_KV.put(kvKey, JSON.stringify(payload), { expirationTtl: DISCOVER_KV_TTL_S }));
  }
  const res = json(payload);
  res.headers.set("cache-control", `public, max-age=${CACHE_TTL_S}`);
  ctx.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}

async function discoverFeedLinks(pageUrl: string, html: string): Promise<{ url: string; title: string; type: string }[]> {
  const found: { url: string; title: string; type: string }[] = [];
  await new HTMLRewriter()
    .on("link", {
      element(el) {
        const rel = (el.getAttribute("rel") || "").toLowerCase();
        if (!rel.includes("alternate")) return;
        const type = (el.getAttribute("type") || "").toLowerCase();
        if (!/(rss|atom|xml)/.test(type)) return;
        const href = el.getAttribute("href");
        if (!href) return;
        found.push({ url: absolutize(href, pageUrl), title: el.getAttribute("title") || "", type });
      },
    })
    .transform(new Response(html))
    .arrayBuffer();
  return found;
}

async function probeFeedPaths(pageUrl: string, env: Env): Promise<{ url: string; title: string; type: string }[]> {
  const origin = new URL(pageUrl).origin;
  const checks = FEED_PATHS.map(async (p) => {
    const candidate = origin + p;
    if (!hostAllowed(new URL(candidate).hostname, env)) return null;
    try {
      const head = await fetchText(candidate, 1500);
      if (/<rss[\s>]|<feed[\s>]/i.test(head)) {
        const type = /<feed[\s>]/i.test(head) ? "application/atom+xml" : "application/rss+xml";
        return { url: candidate, title: "", type };
      }
    } catch { /* ignore */ }
    return null;
  });
  const settled = await Promise.allSettled(checks);
  const out: { url: string; title: string; type: string }[] = [];
  for (const s of settled) if (s.status === "fulfilled" && s.value) out.push(s.value);
  return out;
}

// --- /scrape : site without a feed -> Atom ---

async function handleScrape(req: Request, url: URL, env: Env, ctx: ExecutionContext): Promise<Response> {
  const page = (url.searchParams.get("url") || "").trim();
  let pageHost: string;
  try {
    const u = new URL(page);
    if (u.protocol !== "https:" && u.protocol !== "http:") throw new Error("scheme");
    pageHost = u.hostname;
  } catch {
    return json({ error: "bad or missing ?url=" }, 400);
  }
  if (!hostAllowed(pageHost, env)) return json({ error: "host not allowed" }, 403);

  const inm = req.headers.get("if-none-match");
  const cache = caches.default;
  const cacheKey = new Request(url.toString());
  const cached = await cache.match(cacheKey);
  if (cached) {
    const tag = cached.headers.get("etag");
    if (tag && inm && etagMatches(inm, tag)) return notModified(tag);
    return cached;
  }

  const itemSel = (url.searchParams.get("item") || "").trim();
  const selfUrl = url.toString();
  const kvKey = `scr:${selfUrl}`;

  let atom: string | null = null;
  if (env.SCRAPE_KV) atom = await env.SCRAPE_KV.get(kvKey);

  if (!atom) {
    try {
      const html = await fetchHtml(page);
      const items = await pickItems(html, itemSel, page);
      if (!items.length) return json({ error: "no items found; pass &item=<css-selector>" }, 422);
      atom = buildAtom({
        title: pageHost.replace(/^www\./, ""),
        pageUrl: page,
        selfUrl,
        items,
        updated: new Date().toISOString(),
      });
      if (env.SCRAPE_KV) {
        ctx.waitUntil(env.SCRAPE_KV.put(kvKey, atom, { expirationTtl: SCRAPE_KV_TTL_S }));
      }
    } catch (e) {
      return json({ error: `scrape failed: ${(e as Error).message}` }, 502);
    }
  }

  const etag = await weakEtag(atom);
  const res = new Response(atom, {
    headers: {
      "content-type": "application/atom+xml; charset=utf-8",
      "cache-control": `public, max-age=${CACHE_TTL_S}`,
      etag,
      ...CORS,
    },
  });
  ctx.waitUntil(cache.put(cacheKey, res.clone()));
  if (inm && etagMatches(inm, etag)) return notModified(etag);
  return res;
}

export interface ScrapeItem { title: string; link: string; summary: string; image: string | null; }

/** Use the given selector, or auto-detect by trying candidates and keeping the best yield. */
async function pickItems(html: string, itemSel: string, pageUrl: string): Promise<ScrapeItem[]> {
  if (itemSel) return extractItems(html, itemSel, pageUrl);
  let best: ScrapeItem[] = [];
  for (const sel of SCRAPE_CANDIDATES) {
    const got = await extractItems(html, sel, pageUrl);
    if (got.length > best.length) best = got;
    if (best.length >= 5) break; // good enough; stop spending CPU
  }
  return best;
}

async function extractItems(html: string, itemSel: string, pageUrl: string): Promise<ScrapeItem[]> {
  const items: ScrapeItem[] = [];
  let cur: { title: string; linkText: string; link: string; summary: string; image: string | null } | null = null;
  let capTitle = false;
  let capSummary = false;
  let capLinkText = false;

  const push = () => {
    if (!cur) return;
    const title = (cur.title.trim() || cur.linkText.trim()).replace(/\s+/g, " ").slice(0, 200);
    const link = absolutize(cur.link, pageUrl);
    if (title && link && items.length < MAX_SCRAPE_ITEMS) {
      items.push({
        title,
        link,
        summary: cur.summary.trim().replace(/\s+/g, " ").slice(0, 280),
        image: cur.image ? absolutize(cur.image, pageUrl) : null,
      });
    }
    cur = null;
    capTitle = capSummary = capLinkText = false;
  };

  const heading = {
    element() { if (cur && !cur.title) capTitle = true; },
    text(t: Text) { if (cur && capTitle) { cur.title += t.text; if (t.lastInTextNode) capTitle = false; } },
  };

  await new HTMLRewriter()
    .on(itemSel, {
      element(el) {
        push();
        cur = { title: "", linkText: "", link: "", summary: "", image: null };
        el.onEndTag(() => push());
      },
    })
    .on(`${itemSel} a`, {
      element(el) {
        if (!cur || cur.link) return;
        cur.link = el.getAttribute("href") || "";
        if (!cur.linkText) {
          capLinkText = true;
          el.onEndTag(() => { capLinkText = false; });
        }
      },
      text(t) { if (cur && capLinkText) cur.linkText += t.text; },
    })
    .on(`${itemSel} h1`, heading)
    .on(`${itemSel} h2`, heading)
    .on(`${itemSel} h3`, heading)
    .on(`${itemSel} img`, {
      element(el) { if (cur && !cur.image) cur.image = el.getAttribute("src") || el.getAttribute("data-src") || null; },
    })
    .on(`${itemSel} p`, {
      element() { if (cur && !cur.summary && !capSummary) capSummary = true; },
      text(t) { if (cur && capSummary) { cur.summary += t.text; if (t.lastInTextNode) capSummary = false; } },
    })
    .transform(new Response(html))
    .arrayBuffer(); // drive the stream so the handlers above run

  push(); // flush a trailing open item if its end tag never fired
  return items;
}

// --- shared fetch helpers ---

async function fetchHtml(pageUrl: string): Promise<string> {
  return fetchText(pageUrl, PAGE_TIMEOUT_MS);
}

async function fetchText(target: string, timeoutMs: number): Promise<string> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(target, {
      signal: ctrl.signal,
      headers: { "user-agent": "feedy/1.0 (+https://github.com/travino/feedy)", accept: "text/html, application/xhtml+xml, application/xml, text/xml" },
      cf: { cacheTtl: CACHE_TTL_S, cacheEverything: true },
    });
    if (!res.ok) throw new Error(`${target}: HTTP ${res.status}`);
    return await readCapped(res, MAX_HTML_BYTES);
  } finally {
    clearTimeout(t);
  }
}

async function readCapped(res: Response, maxBytes: number): Promise<string> {
  const reader = res.body?.getReader();
  if (!reader) return res.text();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value) {
      chunks.push(value);
      total += value.length;
      if (total >= maxBytes) { await reader.cancel(); break; }
    }
  }
  return new TextDecoder().decode(concat(chunks));
}

function concat(chunks: Uint8Array[]): Uint8Array {
  let len = 0;
  for (const c of chunks) len += c.length;
  const out = new Uint8Array(len);
  let off = 0;
  for (const c of chunks) { out.set(c, off); off += c.length; }
  return out;
}

async function fetchFeed(feedUrl: string): Promise<NewsItem[]> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), FEED_TIMEOUT_MS);
  try {
    const res = await fetch(feedUrl, {
      signal: ctrl.signal,
      headers: { "user-agent": "feedy/1.0 (+https://github.com/travino/feedy)", accept: "application/rss+xml, application/atom+xml, application/xml, text/xml" },
      cf: { cacheTtl: CACHE_TTL_S, cacheEverything: true },
    });
    if (!res.ok) throw new Error(`${feedUrl}: HTTP ${res.status}`);
    const xml = await res.text();
    return parseFeed(xml);
  } finally {
    clearTimeout(t);
  }
}

// --- XML parsing (regex-based; good enough for well-formed RSS/Atom) ---

export function parseFeed(xml: string): NewsItem[] {
  const source = textOf(first(xml, "title")) || "";
  const isAtom = /<feed[\s>]/i.test(xml) && /<entry[\s>]/i.test(xml);
  const blocks = isAtom ? blocksOf(xml, "entry") : blocksOf(xml, "item");
  const items: NewsItem[] = [];
  for (const b of blocks) {
    const title = textOf(first(b, "title"));
    const link = isAtom ? atomLink(b) : textOf(first(b, "link"));
    if (!title || !link) continue;
    const summaryRaw = textOf(first(b, isAtom ? "summary" : "description")) || textOf(first(b, "content"));
    items.push({
      title: decode(stripTags(title)).trim(),
      link: decode(link).trim(),
      summary: stripTags(decode(stripTags(summaryRaw))).trim().slice(0, 280),
      image: imageOf(b),
      date: normDate(textOf(first(b, isAtom ? "updated" : "pubDate")) || textOf(first(b, "published")) || textOf(first(b, "date"))),
      source: decode(stripTags(source)).trim() || hostOf(link),
    });
  }
  return items;
}

function blocksOf(xml: string, tag: string): string[] {
  const re = new RegExp(`<${tag}[\\s>][\\s\\S]*?</${tag}>`, "gi");
  return xml.match(re) || [];
}
function first(xml: string, tag: string): string | null {
  const m = xml.match(new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)</${tag}>`, "i"));
  return m ? m[1] : null;
}
function textOf(s: string | null): string {
  if (!s) return "";
  const cdata = s.match(/<!\[CDATA\[([\s\S]*?)\]\]>/);
  return (cdata ? cdata[1] : s).trim();
}
function atomLink(block: string): string {
  const alt = block.match(/<link[^>]*rel=["']alternate["'][^>]*href=["']([^"']+)["']/i)
           || block.match(/<link[^>]*href=["']([^"']+)["'][^>]*rel=["']alternate["']/i)
           || block.match(/<link[^>]*href=["']([^"']+)["']/i);
  return alt ? alt[1] : "";
}
function imageOf(block: string): string | null {
  const candidates = [
    /<media:content[^>]*url=["']([^"']+)["']/i,
    /<media:thumbnail[^>]*url=["']([^"']+)["']/i,
    /<enclosure[^>]*url=["']([^"']+\.(?:jpg|jpeg|png|webp|gif)[^"']*)["']/i,
    /<image>[\s\S]*?<url>([\s\S]*?)<\/url>/i,
    /<img[^>]*src=["']([^"']+)["']/i,
  ];
  for (const re of candidates) {
    const m = block.match(re);
    if (m) return decode(m[1]).trim();
  }
  return null;
}

export function stripTags(s: string): string { return s.replace(/<[^>]+>/g, " ").replace(/\s+/g, " "); }
export function decode(s: string): string {
  return s
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/&apos;/g, "'")
    .replace(/&#x2F;/gi, "/").replace(/&nbsp;/g, " ")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&amp;/g, "&");
}
export function normDate(s: string): string | null {
  const t = Date.parse(textOf(s));
  return Number.isFinite(t) ? new Date(t).toISOString() : null;
}
function hostOf(link: string): string { try { return new URL(link).hostname.replace(/^www\./, ""); } catch { return ""; } }

// --- Atom serialization (for /scrape) ---

export function buildAtom(o: { title: string; pageUrl: string; selfUrl: string; items: ScrapeItem[]; updated: string }): string {
  const entries = o.items.map((it) => [
    "  <entry>",
    `    <title>${xmlEscape(it.title)}</title>`,
    `    <link rel="alternate" href="${xmlEscape(it.link)}"/>`,
    `    <id>${xmlEscape(it.link)}</id>`,
    `    <updated>${o.updated}</updated>`,
    it.summary ? `    <summary>${xmlEscape(it.summary)}</summary>` : "",
    it.image ? `    <media:content url="${xmlEscape(it.image)}"/>` : "",
    "  </entry>",
  ].filter(Boolean).join("\n")).join("\n");

  return [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">',
    `  <title>${xmlEscape(o.title)}</title>`,
    `  <link rel="alternate" href="${xmlEscape(o.pageUrl)}"/>`,
    `  <link rel="self" href="${xmlEscape(o.selfUrl)}"/>`,
    `  <id>${xmlEscape(o.selfUrl)}</id>`,
    `  <updated>${o.updated}</updated>`,
    entries,
    "</feed>",
  ].join("\n");
}

export function xmlEscape(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// --- misc helpers ---

export function hostAllowed(host: string, env: Env): boolean {
  const allow = (env.ALLOWED_HOSTS || "").split(",").map((s) => s.trim()).filter(Boolean);
  return !allow.length || allow.some((a) => host.endsWith(a));
}

export function absolutize(href: string, base: string): string {
  try { return new URL(href, base).toString(); } catch { return href; }
}

export function dedupe(items: NewsItem[]): NewsItem[] {
  const seen = new Set<string>();
  return items.filter((it) => { if (seen.has(it.link)) return false; seen.add(it.link); return true; });
}
export function dedupeBy<T>(arr: T[], key: (x: T) => string): T[] {
  const seen = new Set<string>();
  return arr.filter((x) => { const k = key(x); if (seen.has(k)) return false; seen.add(k); return true; });
}

export function clamp(n: number, lo: number, hi: number): number { return Math.min(hi, Math.max(lo, n)); }

// --- Conditional GET helpers ---

async function weakEtag(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(s));
  const hex = [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `W/"${hex.slice(0, 16)}"`;
}

export function etagMatches(ifNoneMatch: string, etag: string): boolean {
  if (ifNoneMatch.trim() === "*") return true;
  const norm = (t: string) => t.trim().replace(/^W\//, "");
  const want = norm(etag);
  return ifNoneMatch.split(",").some((t) => norm(t) === want);
}

function notModified(etag: string): Response {
  return new Response(null, {
    status: 304,
    headers: { etag, "cache-control": `public, max-age=${CACHE_TTL_S}`, ...CORS },
  });
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...CORS },
  });
}
