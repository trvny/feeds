/**
 * feedy news Worker
 *
 * GET /?feeds=<url,url,...>&limit=20
 *   → { items: [{ title, link, summary, image, date, source }], count, fetched }
 *
 * - Fetches each feed with a per-feed timeout; one bad feed never sinks the rest.
 * - Parses RSS 2.0 and Atom without a DOM (Workers have no DOMParser).
 * - Merges, de-dupes by link, sorts newest-first, caps to `limit`.
 * - CORS-open (it's a public read proxy) and edge-cached for a few minutes.
 */

export interface Env {
  /** Optional comma-separated default feeds when the request omits ?feeds= */
  DEFAULT_FEEDS?: string;
  /** Optional comma-separated allowlist of host suffixes. Empty = allow any. */
  ALLOWED_HOSTS?: string;
}

interface NewsItem {
  title: string;
  link: string;
  summary: string;
  image: string | null;
  date: string | null;
  source: string;
}

const FEED_TIMEOUT_MS = 6000;
const CACHE_TTL_S = 300;
const MAX_FEEDS = 12;
const HARD_LIMIT = 60;

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "content-type, accept",
};

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (req.method !== "GET") return json({ error: "method not allowed" }, 405);

    const url = new URL(req.url);
    if (url.pathname === "/health") return json({ ok: true });

    // Edge cache keyed by full URL.
    const cache = caches.default;
    const cacheKey = new Request(url.toString(), req);
    const cached = await cache.match(cacheKey);
    if (cached) return cached;

    const feedsParam = url.searchParams.get("feeds") || env.DEFAULT_FEEDS || "";
    const limit = clamp(parseInt(url.searchParams.get("limit") || "20", 10) || 20, 1, HARD_LIMIT);

    const feeds = feedsParam.split(",").map((s) => s.trim()).filter(Boolean).slice(0, MAX_FEEDS);
    if (!feeds.length) return json({ error: "no feeds supplied (use ?feeds=url1,url2)" }, 400);

    const allow = (env.ALLOWED_HOSTS || "").split(",").map((s) => s.trim()).filter(Boolean);
    const valid: string[] = [];
    for (const f of feeds) {
      try {
        const h = new URL(f);
        if (h.protocol !== "https:" && h.protocol !== "http:") continue;
        if (allow.length && !allow.some((a) => h.hostname.endsWith(a))) continue;
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

    const res = json({ items: merged, count: merged.length, fetched: new Date().toISOString() });
    res.headers.set("cache-control", `public, max-age=${CACHE_TTL_S}`);
    ctx.waitUntil(cache.put(cacheKey, res.clone()));
    return res;
  },
};

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

function parseFeed(xml: string): NewsItem[] {
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
  // Prefer rel="alternate"; fall back to first <link href>.
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

function stripTags(s: string): string { return s.replace(/<[^>]+>/g, " ").replace(/\s+/g, " "); }
function decode(s: string): string {
  return s
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/&apos;/g, "'")
    .replace(/&#x2F;/gi, "/").replace(/&nbsp;/g, " ")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&amp;/g, "&");
}
function normDate(s: string): string | null {
  const t = Date.parse(textOf(s));
  return Number.isFinite(t) ? new Date(t).toISOString() : null;
}
function hostOf(link: string): string { try { return new URL(link).hostname.replace(/^www\./, ""); } catch { return ""; } }

function dedupe(items: NewsItem[]): NewsItem[] {
  const seen = new Set<string>();
  return items.filter((it) => { if (seen.has(it.link)) return false; seen.add(it.link); return true; });
}

function clamp(n: number, lo: number, hi: number): number { return Math.min(hi, Math.max(lo, n)); }
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...CORS },
  });
}
