/**
 * kanarek news Worker
 *
 * Routes
 *   GET /?feeds=<url,url,...>&limit=20
 *     -> { items: [{ title, link, summary, image, date, source, author }], count, fetched }
 *     Fetches/parses RSS, Atom, RDF, and JSON Feed (via feedsmith), merges,
 *     de-dupes, sorts newest-first. Conditional GET via a weak ETag over the
 *     item set (304 when nothing changed).
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
 *   GET /?feeds=...&format=atom|rss|jsonfeed
 *     -> Atom/RSS XML, or a spec JSON Feed 1.1 document (application/feed+json),
 *     of the same merged, deduped, sorted item set.
 *     Purely additive: default (no ?format=, or format=json) is byte-identical
 *     to the JSON path above, untouched. Lets the merged output itself be
 *     subscribed to in an external reader.
 *
 *   GET /stations/search?q=<n>&country=<cc>&tag=<genre>&limit=<n>
 *     -> { stations: [{ name, streamUrl, logoUrl, groupTitle }], count, fetched }
 *     Proxies station search to the Radio Browser API (radio-browser.info, ~50k+
 *     community-checked internet radio stations, no key required) so the app's
 *     station-search dialog isn't limited to the hand-bundled seed playlists.
 *     At least one of q/country/tag is required. Broken streams are filtered
 *     server-side (hidebroken=true) and results are ranked by click popularity.
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

import { generateAtomFeed, generateRssFeed, generateJsonFeed, parseFeed as parseFeedSmith } from "feedsmith";

export interface Env {
  /** Optional comma-separated default feeds when the request omits ?feeds= */
  DEFAULT_FEEDS?: string;
  /** Optional comma-separated allowlist of host suffixes. Empty = allow any. */
  ALLOWED_HOSTS?: string;
  /** Optional KV namespace for durable discover/scrape caching. Absent = Cache-API only. */
  SCRAPE_KV?: KVNamespace;
  /** Optional D1 database for per-device read-state, subscriptions, and pairing. Absent = /state and /pair return 503. */
  STATE_DB?: D1Database;
}

export interface NewsItem {
  title: string;
  link: string;
  summary: string;
  image: string | null;
  date: string | null;
  source: string;
  /** Per-article byline from dc:creator, when the feed provides one (distinct from `source`, the feed's own title). */
  author: string | null;
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
const MAX_READ_IDS = 2000; // LRU cap on the read-state id set per device
const MAX_SUBS = 500; // cap on per-device subscriptions
const MAX_DELTA_IDS = 400; // bound add/remove per request (keeps D1 batch well under 1000 stmts)
const STATE_MAX_BODY = 512_000; // reject oversized state payloads
const PAIR_TTL_S = 300; // pairing code lifetime
const PAIR_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"; // Crockford-ish, no ambiguous chars

/** Repeating-block selectors tried in order when ?item= is omitted. */
const SCRAPE_CANDIDATES = ["article", "[class*=post]", "[class*=entry]", "[class*=card]", "main li"];
/** Common feed paths probed only when a page advertises no <link alternate>. */
const FEED_PATHS = ["/feed", "/feed/", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml"];

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, PUT, OPTIONS",
  "access-control-allow-headers": "content-type, accept, if-none-match, authorization",
  "access-control-expose-headers": "etag",
};

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });

    const url = new URL(req.url);

    // Per-device state + pairing (own method handling, must precede the GET-only guard).
    if (url.pathname === "/state/read") return handleReadState(req, env);
    if (url.pathname === "/state/subs") return handleSubsState(req, env);
    if (url.pathname === "/pair") return handlePairCreate(req, env);
    if (url.pathname.startsWith("/pair/")) return handlePairClaim(req, url, env);

    if (req.method !== "GET") return json({ error: "method not allowed" }, 405);

    if (url.pathname === "/health") return json({ ok: true });
    if (url.pathname === "/discover") return handleDiscover(url, env, ctx);
    if (url.pathname === "/scrape") return handleScrape(req, url, env, ctx);
    if (url.pathname === "/stations/search") return handleStationsSearch(url, env, ctx);
    if (url.pathname === "/logos") return handleLogos(url, env, ctx);
    return handleFeeds(req, url, env, ctx);
  },
};

// --- /?feeds= : RSS/Atom merge; default JSON unchanged, optional format=atom|rss ---

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

  const format = (url.searchParams.get("format") || "json").toLowerCase();
  const etag = await weakEtag(JSON.stringify(merged));

  const res =
    format === "atom" || format === "rss"
      ? renderMergedFeed(merged, format, url)
      : format === "jsonfeed"
        ? renderMergedJsonFeed(merged, url)
        : json({ items: merged, count: merged.length, fetched: new Date().toISOString() });
  res.headers.set("cache-control", `public, max-age=${CACHE_TTL_S}`);
  res.headers.set("etag", etag);
  ctx.waitUntil(cache.put(cacheKey, res.clone()));

  if (inm && etagMatches(inm, etag)) return notModified(etag);
  return res;
}

/** Renders the same merged item set as Atom/RSS XML via feedsmith's generators (additive; JSON path above is untouched). */
export function renderMergedFeed(merged: NewsItem[], format: "atom" | "rss", url: URL): Response {
  const now = new Date();
  const body =
    format === "atom"
      ? generateAtomFeed({
          id: url.toString(),
          title: "kanarek — combined feed",
          subtitle: "Merged output of the source feeds passed to this Worker",
          updated: now,
          generator: { text: "kanarek-news" },
          links: [{ href: url.origin, rel: "alternate" }, { href: url.toString(), rel: "self" }],
          entries: merged.map((it) => atomEntry(it, now)),
        })
      : generateRssFeed({
          title: "kanarek — combined feed",
          description: "Merged output of the source feeds passed to this Worker",
          link: url.origin,
          generator: "kanarek-news",
          lastBuildDate: now,
          items: merged.map((it) => rssItem(it, now)),
        });
  const contentType = format === "atom" ? "application/atom+xml; charset=utf-8" : "application/rss+xml; charset=utf-8";

  return new Response(body, { headers: { ...CORS, "content-type": contentType } });
}

/** NewsItem -> feedsmith Atom entry (merged-feed export and, via buildAtom below, /scrape share this shape). */
function atomEntry(it: NewsItem, fallbackDate: Date) {
  const byline = it.author || it.source;
  return {
    id: it.link,
    title: it.title,
    updated: it.date ? new Date(it.date) : fallbackDate,
    links: [{ href: it.link, rel: "alternate" }],
    summary: it.summary || undefined,
    authors: byline ? [{ name: byline }] : undefined,
    media: it.image ? { contents: [{ url: it.image }] } : undefined,
  };
}

/** NewsItem -> feedsmith RSS item. */
function rssItem(it: NewsItem, fallbackDate: Date) {
  const byline = it.author || it.source;
  return {
    title: it.title,
    link: it.link,
    description: it.summary || undefined,
    guid: { value: it.link, isPermaLink: true },
    pubDate: it.date ? new Date(it.date) : fallbackDate,
    authors: byline ? [byline] : undefined,
    media: it.image ? { contents: [{ url: it.image }] } : undefined,
  };
}

/** Renders the merged item set as a spec JSON Feed 1.1 document (?format=jsonfeed) via feedsmith's generateJsonFeed. */
export function renderMergedJsonFeed(merged: NewsItem[], url: URL): Response {
  const doc = generateJsonFeed({
    title: "kanarek — combined feed",
    home_page_url: url.origin,
    feed_url: url.toString(),
    items: merged.map((it) => {
      const byline = it.author || it.source;
      return {
        id: it.link,
        url: it.link,
        title: it.title,
        content_html: it.summary || "",
        ...(it.date ? { date_published: new Date(it.date) } : {}),
        ...(it.image ? { image: it.image } : {}),
        ...(byline ? { authors: [{ name: byline }] } : {}),
      };
    }),
  });
  return new Response(JSON.stringify(doc), {
    headers: { ...CORS, "content-type": "application/feed+json; charset=utf-8" },
  });
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
  // Page-level social image: used as a fallback for any item that has no usable <img>.
  const ogImage = extractOgImage(html, pageUrl);
  const fill = (items: ScrapeItem[]) => {
    if (!ogImage) return items;
    for (const it of items) if (!it.image) it.image = ogImage;
    return items;
  };
  if (itemSel) return fill(await extractItems(html, itemSel, pageUrl));
  let best: ScrapeItem[] = [];
  for (const sel of SCRAPE_CANDIDATES) {
    const got = await extractItems(html, sel, pageUrl);
    if (got.length > best.length) best = got;
    if (best.length >= 5) break; // good enough; stop spending CPU
  }
  return fill(best);
}

/** First og:image / twitter:image in the page head, absolutized — or null. */
function extractOgImage(html: string, pageUrl: string): string | null {
  const head = html.slice(0, 60_000); // meta tags live near the top
  const res = [
    /<meta[^>]+property=["']og:image(?::url)?["'][^>]+content=["']([^"']+)["']/i,
    /<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image(?::url)?["']/i,
    /<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)["']/i,
    /<meta[^>]+content=["']([^"']+)["'][^>]+name=["']twitter:image["']/i,
  ];
  for (const re of res) {
    const m = head.match(re);
    if (m && m[1].trim()) return absolutize(decode(m[1]).trim(), pageUrl);
  }
  return null;
}

/** Reject sharing icons, sprites, tracking pixels, and inline data URIs. */
function usableImg(src: string | null): string | null {
  if (!src) return null;
  const s = src.trim();
  if (!s || s.startsWith("data:")) return null;
  if (/\b(sprite|icon|logo|avatar|placeholder|blank|pixel|1x1|spacer)\b/i.test(s)) return null;
  return s;
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
      element(el) {
        if (!cur || cur.image) return;
        // Lazy-loaded images often keep a placeholder in src and the real URL in data-*/srcset.
        const cand = el.getAttribute("data-src")
          || el.getAttribute("data-original")
          || firstFromSrcset(el.getAttribute("srcset") || el.getAttribute("data-srcset"))
          || el.getAttribute("src");
        cur.image = usableImg(cand);
      },
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

// --- /stations/search : Radio Browser (radio-browser.info) station discovery ---

/** Mirror servers tried in order; the first one that answers within the timeout wins. */
const RADIO_MIRRORS = ["de1.api.radio-browser.info", "nl1.api.radio-browser.info", "at1.api.radio-browser.info"];
const RADIO_TIMEOUT_MS = 5000;
const RADIO_KV_TTL_S = 21_600; // 6h — station rosters barely churn, unlike news
const MAX_STATION_RESULTS = 30;

// iptv-org logo catalog (~7 MB; channel -> many logo variants). Reduced to a compact
// { channelId: bestUrl } map, memoized per-isolate and persisted in KV cross-colo so the
// big file is parsed rarely. Logos change slowly; a stale-ish map is acceptable.
const IPTV_ORG_LOGOS = "https://iptv-org.github.io/api/logos.json";
const IPTV_LOGO_TTL_S = 86_400; // 24h KV lifetime for the built map
const IPTV_LOGO_MEMO_MS = 3_600_000; // 1h in-isolate memo
const IPTV_LOGO_FETCH_TIMEOUT_MS = 15_000; // the catalog is large
const IPTV_LOGO_MAP_KEY = "iptv:logomap";
const MAX_LOGO_IDS = 200;

export interface StationResult {
  name: string;
  streamUrl: string;
  logoUrl: string | null;
  groupTitle: string | null;
}

async function handleStationsSearch(url: URL, env: Env, ctx: ExecutionContext): Promise<Response> {
  const q = (url.searchParams.get("q") || "").trim().slice(0, 100);
  const country = (url.searchParams.get("country") || "").trim().slice(0, 2).toUpperCase();
  const tag = (url.searchParams.get("tag") || "").trim().slice(0, 60);
  const limit = clamp(parseInt(url.searchParams.get("limit") || "20", 10) || 20, 1, MAX_STATION_RESULTS);
  if (!q && !country && !tag) return json({ error: "supply at least one of q=, country=, tag=" }, 400);

  const cache = caches.default;
  const cacheKey = new Request(url.toString());
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const kvKey = `radio:${q}:${country}:${tag}:${limit}`;
  if (env.SCRAPE_KV) {
    const stored = await env.SCRAPE_KV.get(kvKey);
    if (stored) {
      const res = json(JSON.parse(stored));
      res.headers.set("cache-control", `public, max-age=${CACHE_TTL_S}`);
      ctx.waitUntil(cache.put(cacheKey, res.clone()));
      return res;
    }
  }

  const params = new URLSearchParams({ limit: String(limit), hidebroken: "true", order: "clickcount", reverse: "true" });
  if (q) params.set("name", q);
  if (country) params.set("countrycode", country);
  if (tag) params.set("tag", tag);

  let stations: StationResult[] = [];
  for (const mirror of RADIO_MIRRORS) {
    try {
      stations = await fetchRadioBrowser(mirror, params);
      break; // first mirror that answers wins
    } catch {
      /* try the next mirror */
    }
  }

  const payload = { stations, count: stations.length, fetched: new Date().toISOString() };
  if (env.SCRAPE_KV && stations.length) {
    ctx.waitUntil(env.SCRAPE_KV.put(kvKey, JSON.stringify(payload), { expirationTtl: RADIO_KV_TTL_S }));
  }
  const res = json(payload);
  res.headers.set("cache-control", `public, max-age=${CACHE_TTL_S}`);
  ctx.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}

interface RadioBrowserStation {
  name?: string;
  url_resolved?: string;
  favicon?: string;
  tags?: string;
}

/** Radio Browser rows -> the app's Station shape. Only rows with a resolved stream URL are
 *  usable (hidebroken=true filters dead streams server-side, but url_resolved can still be
 *  empty for a few rows); group = first tag, matching M3U's group-title convention. */
export function mapRadioBrowserStations(data: RadioBrowserStation[]): StationResult[] {
  const out: StationResult[] = [];
  for (const s of data) {
    if (!s.url_resolved) continue;
    out.push({
      name: (s.name || "").trim().slice(0, 120) || "Untitled station",
      streamUrl: s.url_resolved,
      logoUrl: s.favicon || null,
      groupTitle: (s.tags || "").split(",")[0]?.trim().slice(0, 40) || null,
    });
  }
  return out;
}

async function fetchRadioBrowser(mirror: string, params: URLSearchParams): Promise<StationResult[]> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), RADIO_TIMEOUT_MS);
  try {
    const res = await fetch(`https://${mirror}/json/stations/search?${params.toString()}`, {
      signal: ctrl.signal,
      headers: { "user-agent": "kanarek/1.0 (+https://github.com/trvny/feeds)" },
      cf: { cacheTtl: CACHE_TTL_S, cacheEverything: true },
    });
    if (!res.ok) throw new Error(`${mirror}: HTTP ${res.status}`);
    const data = (await res.json()) as RadioBrowserStation[];
    return mapRadioBrowserStations(data);
  } finally {
    clearTimeout(t);
  }
}

// --- /logos : iptv-org channel logos, resolved by tvg-id (== iptv-org channel id) ---

export interface IptvLogo {
  channel: string;
  feed: string | null;
  in_use: boolean;
  width?: number;
  format?: string | null;
  url: string;
}

const LOGO_FORMAT_RANK: Record<string, number> = { PNG: 0, SVG: 1, WEBP: 2, AVIF: 3, JPEG: 4, GIF: 5, APNG: 6 };

/** Lower is better: prefer in-use, channel-level (no feed), then friendlier formats. */
function logoScore(l: IptvLogo): number {
  let s = 0;
  if (!l.in_use) s += 100;
  if (l.feed) s += 10;
  s += LOGO_FORMAT_RANK[(l.format || "").toUpperCase()] ?? 9;
  return s;
}

/** Reduce raw logos.json to one best URL per channel id. Pure; unit-tested. */
export function buildLogoMap(logos: IptvLogo[]): Record<string, string> {
  const best: Record<string, { score: number; width: number; url: string }> = {};
  for (const l of logos) {
    if (!l || !l.channel || !l.url) continue;
    const score = logoScore(l);
    const width = l.width || 0;
    const cur = best[l.channel];
    if (!cur || score < cur.score || (score === cur.score && width > cur.width)) {
      best[l.channel] = { score, width, url: l.url };
    }
  }
  const out: Record<string, string> = {};
  for (const k in best) out[k] = best[k].url;
  return out;
}

let LOGO_MEMO: { at: number; map: Record<string, string> } | null = null;

async function getLogoMap(env: Env, ctx: ExecutionContext): Promise<Record<string, string>> {
  const now = Date.now();
  if (LOGO_MEMO && now - LOGO_MEMO.at < IPTV_LOGO_MEMO_MS) return LOGO_MEMO.map;

  if (env.SCRAPE_KV) {
    const stored = await env.SCRAPE_KV.get(IPTV_LOGO_MAP_KEY);
    if (stored) {
      const map = JSON.parse(stored) as Record<string, string>;
      LOGO_MEMO = { at: now, map };
      return map;
    }
  }

  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), IPTV_LOGO_FETCH_TIMEOUT_MS);
  let map: Record<string, string> = {};
  try {
    const res = await fetch(IPTV_ORG_LOGOS, {
      signal: ctrl.signal,
      headers: { "user-agent": "kanarek/1.0 (+https://github.com/trvny/feeds)", accept: "application/json" },
      cf: { cacheTtl: IPTV_LOGO_TTL_S, cacheEverything: true },
    });
    if (res.ok) map = buildLogoMap((await res.json()) as IptvLogo[]);
  } catch {
    /* leave map empty -> caller degrades to "no logo", never throws */
  } finally {
    clearTimeout(t);
  }

  if (Object.keys(map).length) {
    LOGO_MEMO = { at: now, map };
    if (env.SCRAPE_KV) ctx.waitUntil(env.SCRAPE_KV.put(IPTV_LOGO_MAP_KEY, JSON.stringify(map), { expirationTtl: IPTV_LOGO_TTL_S }));
  }
  return map;
}

async function handleLogos(url: URL, env: Env, ctx: ExecutionContext): Promise<Response> {
  const ids = (url.searchParams.get("ids") || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, MAX_LOGO_IDS);
  if (!ids.length) return json({ error: "supply ids=<tvg-id,...>" }, 400);

  const cache = caches.default;
  const cacheKey = new Request(url.toString());
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const map = await getLogoMap(env, ctx);
  const logos: Record<string, string> = {};
  for (const id of ids) {
    const u = map[id];
    if (u) logos[id] = u;
  }

  const res = json({ logos, fetched: new Date().toISOString() });
  res.headers.set("cache-control", `public, max-age=${CACHE_TTL_S}`);
  ctx.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
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
      headers: { "user-agent": "kanarek/1.0 (+https://github.com/trvny/feeds)", accept: "text/html, application/xhtml+xml, application/xml, text/xml" },
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
      headers: { "user-agent": "kanarek/1.0 (+https://github.com/trvny/feeds)", accept: "application/rss+xml, application/atom+xml, application/xml, text/xml" },
      cf: { cacheTtl: CACHE_TTL_S, cacheEverything: true },
    });
    if (!res.ok) throw new Error(`${feedUrl}: HTTP ${res.status}`);
    const xml = await res.text();
    return parseFeed(xml);
  } finally {
    clearTimeout(t);
  }
}

// --- Feed parsing (feedsmith: RSS / Atom / RDF / JSON Feed, namespace-aware) ---

// feedsmith replaces the old regex parser: one universal parseFeed that detects
// the format, normalizes custom namespace prefixes (media:, dc:) to canonical
// keys, tolerates malformed/undeclared-namespace feeds, and — the new bit —
// reads JSON Feed 1.1 as well, so the feedseek .json siblings flow through the
// same merge path as XML. NewsItem shape and this export's signature are
// unchanged except for the added `author` field, so the app + tests see
// identical behavior for RSS/Atom otherwise.
//
// Two things tapped on top of the base fields:
//   - author -> NewsItem.author (per-article byline; `source` stays the feed's own title).
//     Sourced from RSS/RDF's dc:creator namespace, or the native `authors[]` construct
//     that Atom's <author><name> and JSON Feed's `authors` both normalize to identically.
//   - content:encoded -> folded into the same summary fallback chain as Atom's
//     bare <content> and JSON Feed's content_text/content_html, for RSS feeds
//     that ship a full body but no/short <description>.

export function parseFeed(input: string): NewsItem[] {
  let feed: FsFeed;
  try {
    feed = parseFeedSmith(input).feed as FsFeed;
  } catch {
    return []; // garbage in -> empty out (per-source isolation)
  }
  const source = decode(stripTags(String(feed?.title || ""))).trim();
  const entries: FsEntry[] = feed?.entries || feed?.items || [];
  const items: NewsItem[] = [];
  for (const e of entries) {
    const title = decode(stripTags(String(e?.title || ""))).trim();
    const link = pickLink(e);
    if (!title || !link) continue;
    const summaryRaw = firstStr(e?.summary, e?.description, e?.content_text, contentStr(e?.content), e?.content_html);
    const authorRaw = firstStr(e?.dc?.creator, e?.authors?.[0]?.name);
    items.push({
      title,
      link: decode(link).trim(),
      summary: stripTags(decode(stripTags(summaryRaw))).trim().slice(0, 280),
      image: pickImage(e),
      date: normDate(firstStr(e?.published, e?.pubDate, e?.updated, e?.date_published, e?.date_modified, e?.date)),
      source: source || hostOf(link),
      author: authorRaw ? decode(stripTags(authorRaw)).trim() || null : null,
    });
  }
  return items;
}

/** Minimal structural view over feedsmith's normalized object (fields we read). */
interface FsMedia { contents?: Array<{ url?: string }>; thumbnails?: Array<{ url?: string }> }
interface FsEntry {
  title?: string; link?: string; url?: string; links?: Array<{ href?: string; rel?: string }>;
  summary?: string; description?: string; content?: unknown; content_text?: string; content_html?: string;
  published?: string; pubDate?: string; updated?: string; date?: string; date_published?: string; date_modified?: string;
  image?: string; media?: FsMedia; enclosures?: Array<{ url?: string; type?: string }>;
  /** Dublin Core namespace (v2 shape: singular fields). RSS/RDF only. */
  dc?: { creator?: string };
  /** Native author construct: Atom's <author><name> and JSON Feed's `authors`. Both normalize
   *  to the same { name } array shape, so one field covers both formats. */
  authors?: Array<{ name?: string }>;
}
interface FsFeed { title?: string; entries?: FsEntry[]; items?: FsEntry[] }

function firstStr(...vals: unknown[]): string {
  for (const v of vals) if (typeof v === "string" && v.trim()) return v;
  return "";
}
/** Atom's bare <content> parses as a string; RSS/RDF's content:encoded namespace parses as
 *  { encoded }. Handles both so content:encoded actually reaches the summary fallback chain
 *  instead of silently dropping out (the old asText() only accepted strings). */
function contentStr(c: unknown): string {
  if (typeof c === "string") return c;
  if (c && typeof c === "object" && typeof (c as { encoded?: unknown }).encoded === "string") {
    return (c as { encoded: string }).encoded;
  }
  return "";
}
function pickLink(e: FsEntry): string {
  if (typeof e?.link === "string" && e.link) return e.link;      // RSS / RDF
  if (typeof e?.url === "string" && e.url) return e.url;          // JSON Feed
  const links = Array.isArray(e?.links) ? e.links : [];          // Atom
  const alt =
    links.find((l) => l?.rel === "alternate" && l?.href) ||
    links.find((l) => l?.href && l.rel !== "self") ||
    links.find((l) => l?.href);
  return alt?.href || "";
}
function pickImage(e: FsEntry): string | null {
  const mc = e?.media?.contents?.find((c) => c?.url);
  if (mc?.url) return decode(mc.url).trim();
  const mt = e?.media?.thumbnails?.find((t) => t?.url);
  if (mt?.url) return decode(mt.url).trim();
  if (typeof e?.image === "string" && e.image) return decode(e.image).trim(); // JSON Feed
  for (const en of Array.isArray(e?.enclosures) ? e.enclosures : []) {
    if (!en?.url) continue;
    const type = String(en.type || "");
    if (type.startsWith("image/")) return decode(en.url).trim();
    // typeless enclosure: keep the old image-extension gate (parity)
    if (!type && /\.(?:jpe?g|png|webp|gif)/i.test(en.url)) return decode(en.url).trim();
  }
  return null;
}

function first(xml: string, tag: string): string | null {
  const m = xml.match(new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)</${tag}>`, "i"));
  return m ? m[1] : null;
}
function textOf(s: string | null): string {
  if (!s) return "";
  // CDATA unwrap via indexOf; the regex form was polynomial-ReDoS on unclosed input.
  const open = s.indexOf("<![CDATA[");
  if (open !== -1) {
    const close = s.indexOf("]]>", open + 9);
    if (close !== -1) return s.slice(open + 9, close).trim();
  }
  return s.trim();
}
export function stripTags(s: string): string { return s.replace(/<[^<>]+>/g, " ").replace(/\s+/g, " "); }
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

/** Turns extracted page items into Atom XML via feedsmith's generateAtomFeed (escaping/namespaces handled by the library). */
export function buildAtom(o: { title: string; pageUrl: string; selfUrl: string; items: ScrapeItem[]; updated: string }): string {
  const updated = new Date(o.updated);
  return generateAtomFeed({
    id: o.selfUrl,
    title: o.title,
    updated,
    links: [{ href: o.pageUrl, rel: "alternate" }, { href: o.selfUrl, rel: "self" }],
    entries: o.items.map((it) => ({
      id: it.link,
      title: it.title,
      updated,
      links: [{ href: it.link, rel: "alternate" }],
      summary: it.summary || undefined,
      media: it.image ? { contents: [{ url: it.image }] } : undefined,
    })),
  });
}

// --- misc helpers ---

export function hostAllowed(host: string, env: Env): boolean {
  const allow = (env.ALLOWED_HOSTS || "").split(",").map((s) => s.trim()).filter(Boolean);
  return !allow.length || allow.some((a) => host.endsWith(a));
}

/** First URL from a srcset attribute (the smallest candidate), or null. */
function firstFromSrcset(srcset: string | null): string | null {
  if (!srcset) return null;
  const first = srcset.split(",")[0]?.trim().split(/\s+/)[0];
  return first || null;
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

// --- Per-device state (read-state + subscriptions) and pairing ---
//
// Identity = an opaque device token the client generates once and sends as
// `Authorization: Bearer <tok>`. The token IS the identity; the Worker never
// validates it beyond shape and uses it as the row key. Read-state is keyed by
// the raw item `link` (same key /?feeds= dedupes on), so "read" matches across
// worker, app, and reader without any shared normalization.
//
// Backed by D1 (not KV): read-state is write-heavy, and D1's per-row writes are
// relational so concurrent devices upsert their own marks instead of clobbering
// a shared blob. Pairing codes live here too with an explicit expires_at +
// lazy delete, so no second store and no cleanup cron.

interface ReadDelta { add?: string[]; remove?: string[]; }

const SCHEMA = [
  "CREATE TABLE IF NOT EXISTS read_state (token TEXT NOT NULL, item_id TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (token, item_id))",
  "CREATE INDEX IF NOT EXISTS idx_read_token_ts ON read_state (token, ts)",
  "CREATE TABLE IF NOT EXISTS subs_state (token TEXT PRIMARY KEY, feeds TEXT NOT NULL, ts INTEGER NOT NULL)",
  "CREATE TABLE IF NOT EXISTS pair_state (code TEXT PRIMARY KEY, token TEXT NOT NULL, expires_at INTEGER NOT NULL)",
];
let schemaReady = false; // per-isolate guard; CREATE IF NOT EXISTS is idempotent

async function ensureSchema(db: D1Database): Promise<void> {
  if (schemaReady) return;
  await db.batch(SCHEMA.map((s) => db.prepare(s)));
  schemaReady = true;
}

/** Bearer token: base64url, 22-64 chars (>=128-bit). Null when absent/malformed. */
export function parseBearer(authHeader: string | null): string | null {
  const m = /^Bearer\s+([A-Za-z0-9_-]{22,64})$/.exec((authHeader || "").trim());
  return m ? m[1] : null;
}

/** 6-char pairing code from a non-ambiguous alphabet. */
export function genPairCode(rnd: () => number = Math.random): string {
  let s = "";
  for (let i = 0; i < 6; i++) s += PAIR_ALPHABET[Math.floor(rnd() * PAIR_ALPHABET.length)];
  return s;
}

/** Coerce to a deduped, length-capped string-id list; drops non-strings/empties. */
export function cleanIds(v: unknown, cap: number): string[] {
  if (!Array.isArray(v)) return [];
  const out: string[] = [];
  const seen = new Set<string>();
  for (const x of v) {
    if (typeof x !== "string" || !x || seen.has(x)) continue;
    seen.add(x); out.push(x);
    if (out.length >= cap) break;
  }
  return out;
}

async function readBody(req: Request): Promise<unknown> {
  const raw = await req.text();
  if (raw.length > STATE_MAX_BODY) throw new Error("payload too large");
  return raw ? JSON.parse(raw) : {};
}

function noStore(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...CORS },
  });
}

async function handleReadState(req: Request, env: Env): Promise<Response> {
  if (!env.STATE_DB) return noStore({ error: "state backend unavailable" }, 503);
  const tok = parseBearer(req.headers.get("authorization"));
  if (!tok) return noStore({ error: "unauthorized" }, 401);
  const db = env.STATE_DB;
  await ensureSchema(db);

  if (req.method === "GET") {
    const { results } = await db
      .prepare("SELECT item_id, ts FROM read_state WHERE token = ? ORDER BY ts DESC LIMIT ?")
      .bind(tok, MAX_READ_IDS)
      .all<{ item_id: string; ts: number }>();
    const ids = (results ?? []).map((r) => r.item_id);
    const ts = (results ?? []).reduce((m, r) => Math.max(m, r.ts), 0);
    return noStore({ ids, ts });
  }
  if (req.method === "POST") {
    let delta: ReadDelta;
    try { delta = (await readBody(req)) as ReadDelta; }
    catch (e) { return noStore({ error: String((e as Error).message || "bad request") }, 400); }
    const add = cleanIds(delta.add, MAX_DELTA_IDS);
    const remove = cleanIds(delta.remove, MAX_DELTA_IDS);
    const now = Date.now();
    const stmts: D1PreparedStatement[] = [];
    for (const id of remove) {
      stmts.push(db.prepare("DELETE FROM read_state WHERE token = ? AND item_id = ?").bind(tok, id));
    }
    for (const id of add) {
      if (remove.includes(id)) continue;
      stmts.push(db.prepare("INSERT OR REPLACE INTO read_state (token, item_id, ts) VALUES (?, ?, ?)").bind(tok, id, now));
    }
    // LRU cap: keep the newest MAX_READ_IDS for this token
    stmts.push(db.prepare(
      "DELETE FROM read_state WHERE token = ?1 AND item_id NOT IN (SELECT item_id FROM read_state WHERE token = ?1 ORDER BY ts DESC LIMIT ?2)"
    ).bind(tok, MAX_READ_IDS));
    if (stmts.length) await db.batch(stmts);
    return noStore(null, 204);
  }
  return noStore({ error: "method not allowed" }, 405);
}

async function handleSubsState(req: Request, env: Env): Promise<Response> {
  if (!env.STATE_DB) return noStore({ error: "state backend unavailable" }, 503);
  const tok = parseBearer(req.headers.get("authorization"));
  if (!tok) return noStore({ error: "unauthorized" }, 401);
  const db = env.STATE_DB;
  await ensureSchema(db);

  if (req.method === "GET") {
    const row = await db.prepare("SELECT feeds, ts FROM subs_state WHERE token = ?").bind(tok).first<{ feeds: string; ts: number }>();
    const feeds = row ? safeJsonArray(row.feeds) : [];
    return noStore({ feeds, ts: row?.ts ?? 0 });
  }
  if (req.method === "PUT") {
    let body: { feeds?: unknown };
    try { body = (await readBody(req)) as { feeds?: unknown }; }
    catch (e) { return noStore({ error: String((e as Error).message || "bad request") }, 400); }
    const feeds = cleanIds(body.feeds, MAX_SUBS);
    const ts = Date.now();
    await db.prepare("INSERT OR REPLACE INTO subs_state (token, feeds, ts) VALUES (?, ?, ?)").bind(tok, JSON.stringify(feeds), ts).run();
    return noStore({ feeds, ts });
  }
  return noStore({ error: "method not allowed" }, 405);
}

async function handlePairCreate(req: Request, env: Env): Promise<Response> {
  if (!env.STATE_DB) return noStore({ error: "state backend unavailable" }, 503);
  if (req.method !== "POST") return noStore({ error: "method not allowed" }, 405);
  const tok = parseBearer(req.headers.get("authorization"));
  if (!tok) return noStore({ error: "unauthorized" }, 401);
  const db = env.STATE_DB;
  await ensureSchema(db);
  const now = Date.now();
  const code = genPairCode();
  await db.batch([
    db.prepare("DELETE FROM pair_state WHERE expires_at < ?").bind(now), // opportunistic cleanup
    db.prepare("INSERT OR REPLACE INTO pair_state (code, token, expires_at) VALUES (?, ?, ?)").bind(code, tok, now + PAIR_TTL_S * 1000),
  ]);
  return noStore({ code, expires: PAIR_TTL_S });
}

async function handlePairClaim(req: Request, url: URL, env: Env): Promise<Response> {
  if (!env.STATE_DB) return noStore({ error: "state backend unavailable" }, 503);
  if (req.method !== "GET") return noStore({ error: "method not allowed" }, 405);
  const db = env.STATE_DB;
  await ensureSchema(db);
  const code = url.pathname.slice("/pair/".length).toUpperCase();
  if (!/^[0-9A-Z]{6}$/.test(code)) return noStore({ error: "bad code" }, 400);
  const row = await db.prepare("SELECT token, expires_at FROM pair_state WHERE code = ?").bind(code).first<{ token: string; expires_at: number }>();
  if (!row || row.expires_at < Date.now()) return noStore({ error: "expired or unknown code" }, 404);
  await db.prepare("DELETE FROM pair_state WHERE code = ?").bind(code).run(); // one-time
  return noStore({ token: row.token });
}

function safeJsonArray(s: string): string[] {
  try { const v = JSON.parse(s); return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []; }
  catch { return []; }
}


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
