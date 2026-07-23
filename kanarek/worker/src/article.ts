import type { Env } from "./index";

export interface CleanArticle {
  url: string;
  title: string;
  author: string | null;
  image: string | null;
  content: string;
  wordCount: number;
}

export interface ArticleCandidate {
  title: string;
  blocks: string[];
}

export class ArticleNoiseGate {
  private depth = 0;

  enter(): void {
    this.depth += 1;
  }

  leave(): void {
    this.depth = Math.max(0, this.depth - 1);
  }

  get isBlocked(): boolean {
    return this.depth > 0;
  }
}

export function canStartArticleCandidate(noiseGate: ArticleNoiseGate): boolean {
  return !noiseGate.isBlocked;
}

const ARTICLE_TIMEOUT_MS = 7_000;
const ARTICLE_CACHE_TTL_S = 600;
const MAX_ARTICLE_HTML_BYTES = 1_500_000;
const MAX_ARTICLE_CHARS = 60_000;
const MAX_ARTICLE_BLOCKS = 240;
const MIN_ARTICLE_CHARS = 220;
const MAX_REDIRECTS = 3;

const ARTICLE_SELECTORS = [
  '[itemprop="articleBody"]',
  "article",
  ".article-body",
  ".article__body",
  ".article-content",
  ".post-content",
  ".entry-content",
  ".story-body",
  '[class*="article-body"]',
  '[class*="article-content"]',
  '[class*="story-body"]',
  "main",
];

const NOISE_SELECTORS = [
  "script",
  "style",
  "noscript",
  "svg",
  "iframe",
  "form",
  "button",
  "nav",
  "footer",
  "aside",
  '[class*="advert"]',
  '[id*="advert"]',
  '[class*="ad-slot"]',
  '[id*="ad-slot"]',
  '[class*="sponsor"]',
  '[class*="promo"]',
  '[class*="related"]',
  '[class*="recommend"]',
  '[class*="newsletter"]',
  '[class*="subscribe"]',
  '[class*="social"]',
  '[class*="share"]',
  '[class*="comment"]',
  '[class*="cookie"]',
  '[class*="paywall"]',
];

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "content-type, accept",
};

/**
 * Fetches a public article and returns only inert, plain-text reader content.
 * No source HTML, script, iframe, form, or inline styling is returned to clients.
 */
export async function handleArticle(_req: Request, endpoint: URL, env: Env, ctx: ExecutionContext): Promise<Response> {
  const rawTarget = (endpoint.searchParams.get("url") || "").trim();
  const target = safeArticleUrl(rawTarget, env.ALLOWED_HOSTS || "");
  if (!target) return json({ error: "bad, private, or disallowed article URL" }, 400);

  const cache = caches.default;
  const cacheKey = new Request(endpoint.toString(), { method: "GET" });
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  try {
    const { html, finalUrl } = await fetchArticleHtml(target.toString(), env.ALLOWED_HOSTS || "");
    const article = await extractArticleDocument(html, finalUrl);
    if (!article || article.content.length < MIN_ARTICLE_CHARS) {
      return json({ error: "article body not found" }, 422);
    }

    const response = json(article);
    response.headers.set("cache-control", `public, max-age=${ARTICLE_CACHE_TTL_S}`);
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown error";
    return json({ error: `article fetch failed: ${message}` }, 502);
  }
}

export async function extractArticleDocument(html: string, pageUrl: string): Promise<CleanArticle | null> {
  const metadata = extractMetadata(html, pageUrl);
  const jsonLd = extractJsonLdArticle(html, pageUrl);
  if (jsonLd && jsonLd.content.length >= MIN_ARTICLE_CHARS) {
    return finalizeArticle({
      url: pageUrl,
      title: jsonLd.title || metadata.title,
      author: jsonLd.author || metadata.author,
      image: jsonLd.image || metadata.image,
      content: jsonLd.content,
    });
  }

  const candidates: ArticleCandidate[] = [];
  for (const selector of ARTICLE_SELECTORS) {
    candidates.push(...await extractCandidates(html, selector));
    const best = pickBestArticleCandidate(candidates);
    if (best && best.blocks.join(" ").length >= 2_000 && best.blocks.length >= 5) break;
  }

  const best = pickBestArticleCandidate(candidates);
  if (!best) return null;
  const content = cleanBlocks(best.blocks).join("\n\n").slice(0, MAX_ARTICLE_CHARS).trim();
  if (content.length < MIN_ARTICLE_CHARS) return null;

  return finalizeArticle({
    url: pageUrl,
    title: best.title || metadata.title,
    author: metadata.author,
    image: metadata.image,
    content,
  });
}

function finalizeArticle(article: Omit<CleanArticle, "wordCount">): CleanArticle {
  const content = article.content.slice(0, MAX_ARTICLE_CHARS).trim();
  return {
    ...article,
    title: normalizeText(article.title).slice(0, 240),
    author: article.author ? normalizeText(article.author).slice(0, 160) || null : null,
    content,
    wordCount: content ? content.split(/\s+/).filter(Boolean).length : 0,
  };
}

export function extractJsonLdArticle(html: string, pageUrl: string): Omit<CleanArticle, "url" | "wordCount"> | null {
  const scriptPattern = /<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let match: RegExpExecArray | null;
  let visited = 0;
  while ((match = scriptPattern.exec(html)) && visited < 24) {
    visited += 1;
    let root: unknown;
    try {
      root = JSON.parse(match[1].trim());
    } catch {
      continue;
    }

    const stack: unknown[] = [root];
    let nodes = 0;
    while (stack.length && nodes < 300) {
      nodes += 1;
      const node = stack.pop();
      if (Array.isArray(node)) {
        stack.push(...node.slice(0, 80));
        continue;
      }
      if (!node || typeof node !== "object") continue;
      const object = node as Record<string, unknown>;
      const body = typeof object.articleBody === "string" ? normalizeContent(object.articleBody) : "";
      if (body.length >= MIN_ARTICLE_CHARS) {
        return {
          title: firstString(object.headline, object.name),
          author: extractAuthor(object.author),
          image: extractImage(object.image, pageUrl),
          content: body.slice(0, MAX_ARTICLE_CHARS),
        };
      }
      for (const value of Object.values(object)) {
        if (value && typeof value === "object") stack.push(value);
      }
    }
  }
  return null;
}

export function cleanBlocks(blocks: string[]): string[] {
  const output: string[] = [];
  const seen = new Set<string>();
  let chars = 0;
  for (const raw of blocks) {
    const text = normalizeText(raw);
    if (text.length < 20) continue;
    if (isBoilerplateBlock(text)) continue;
    const key = text.toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const remaining = MAX_ARTICLE_CHARS - chars;
    if (remaining <= 0 || output.length >= MAX_ARTICLE_BLOCKS) break;
    const clipped = text.slice(0, remaining);
    output.push(clipped);
    chars += clipped.length + 2;
  }
  return output;
}

export function pickBestArticleCandidate(candidates: ArticleCandidate[]): ArticleCandidate | null {
  let best: ArticleCandidate | null = null;
  let bestScore = -1;
  for (const candidate of candidates) {
    const blocks = cleanBlocks(candidate.blocks);
    const chars = blocks.reduce((sum, block) => sum + block.length, 0);
    if (chars < MIN_ARTICLE_CHARS) continue;
    const substantial = blocks.filter((block) => block.length >= 80).length;
    const score = chars + substantial * 120 + Math.min(blocks.length, 20) * 20;
    if (score > bestScore) {
      best = { title: normalizeText(candidate.title), blocks };
      bestScore = score;
    }
  }
  return best;
}

export function isSafeArticleUrl(raw: string, allowedHosts = ""): boolean {
  return safeArticleUrl(raw, allowedHosts) !== null;
}

function safeArticleUrl(raw: string, allowedHosts: string): URL | null {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  if (url.username || url.password) return null;
  const host = url.hostname.toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
  if (!host || host === "localhost" || host.endsWith(".localhost")) return null;
  if (/\.(?:local|internal|lan|home|test|invalid|example)$/.test(host)) return null;
  // Literal IPs are unnecessary for ordinary news links and make SSRF filtering brittle.
  if (host.includes(":") || /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host)) return null;
  return hostAllowed(host, allowedHosts) ? url : null;
}

function hostAllowed(host: string, allowedHosts: string): boolean {
  const allow = allowedHosts.split(",").map((value) => value.trim().toLowerCase().replace(/^\./, "").replace(/\.$/, "")).filter(Boolean);
  return !allow.length || allow.some((suffix) => host === suffix || host.endsWith(`.${suffix}`));
}

async function fetchArticleHtml(initialUrl: string, allowedHosts: string): Promise<{ html: string; finalUrl: string }> {
  let current = initialUrl;
  for (let redirect = 0; redirect <= MAX_REDIRECTS; redirect += 1) {
    const safe = safeArticleUrl(current, allowedHosts);
    if (!safe) throw new Error("redirect target is not public or allowed");

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), ARTICLE_TIMEOUT_MS);
    try {
      const response = await fetch(safe.toString(), {
        signal: controller.signal,
        redirect: "manual",
        headers: {
          "user-agent": "kanarek/1.0 (+https://github.com/trvny/feeds)",
          accept: "text/html, application/xhtml+xml",
        },
      });

      if (response.status >= 300 && response.status < 400) {
        const location = response.headers.get("location");
        if (!location) throw new Error(`redirect ${response.status} without location`);
        current = new URL(location, safe).toString();
        continue;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const contentType = (response.headers.get("content-type") || "").toLowerCase();
      if (contentType && !contentType.includes("text/html") && !contentType.includes("application/xhtml+xml")) {
        throw new Error("article response is not HTML");
      }
      return { html: await readCapped(response, MAX_ARTICLE_HTML_BYTES), finalUrl: safe.toString() };
    } finally {
      clearTimeout(timeout);
    }
  }
  throw new Error("too many redirects");
}

async function extractCandidates(html: string, rootSelector: string): Promise<ArticleCandidate[]> {
  const candidates: ArticleCandidate[] = [];
  const noiseGate = new ArticleNoiseGate();
  let current: ArticleCandidate | null = null;
  let active: { text: string; title: boolean } | null = null;

  const flushBlock = (token?: { text: string; title: boolean }) => {
    if (!current || !active || (token && active !== token)) return;
    const text = normalizeText(active.text);
    if (text) {
      if (active.title && !current.title) current.title = text;
      else current.blocks.push(text);
    }
    active = null;
  };
  const flushCandidate = () => {
    flushBlock();
    if (current) candidates.push(current);
    current = null;
  };

  let rewriter = new HTMLRewriter().on(rootSelector, {
    element(element) {
      // A nested article inside an excluded aside/promo is still part of that excluded subtree.
      // Do not clear the enclosing suppression state or start a candidate for it.
      if (!canStartArticleCandidate(noiseGate)) return;
      flushCandidate();
      current = { title: "", blocks: [] };
      element.onEndTag(() => flushCandidate());
    },
  });

  for (const noise of NOISE_SELECTORS) {
    rewriter = rewriter.on(`${rootSelector} ${noise}`, {
      element(element) {
        noiseGate.enter();
        element.onEndTag(() => noiseGate.leave());
        element.remove();
      },
    });
  }

  const capture = (selector: string, title: boolean) => {
    rewriter = rewriter.on(`${rootSelector} ${selector}`, {
      element(element) {
        if (!current || noiseGate.isBlocked) return;
        flushBlock();
        const token = { text: "", title };
        active = token;
        element.onEndTag(() => flushBlock(token));
      },
      text(text) {
        if (!noiseGate.isBlocked && current && active) active.text += text.text;
      },
    });
  };

  capture("h1", true);
  capture("h2", false);
  capture("h3", false);
  capture("p", false);
  capture("blockquote", false);
  capture("li", false);

  await rewriter.transform(new Response(html)).arrayBuffer();
  flushCandidate();
  return candidates;
}

function extractMetadata(html: string, pageUrl: string): { title: string; author: string | null; image: string | null } {
  const head = html.slice(0, 120_000);
  const title = meta(head, "property", "og:title") || meta(head, "name", "twitter:title") || tagText(head, "title");
  const author = meta(head, "name", "author") || meta(head, "property", "article:author") || null;
  const imageRaw = meta(head, "property", "og:image") || meta(head, "name", "twitter:image");
  return {
    title: normalizeText(decodeEntities(title)),
    author: author ? normalizeText(decodeEntities(author)) || null : null,
    image: imageRaw ? absolutize(decodeEntities(imageRaw), pageUrl) : null,
  };
}

function meta(html: string, attribute: "name" | "property", value: string): string {
  const escaped = value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const first = new RegExp(`<meta[^>]+${attribute}=["']${escaped}["'][^>]+content=["']([^"']+)["']`, "i").exec(html);
  if (first?.[1]) return first[1];
  const second = new RegExp(`<meta[^>]+content=["']([^"']+)["'][^>]+${attribute}=["']${escaped}["']`, "i").exec(html);
  return second?.[1] || "";
}

function tagText(html: string, tag: string): string {
  const match = new RegExp(`<${tag}[^>]*>([^<]{1,500})</${tag}>`, "i").exec(html);
  return match?.[1] || "";
}

function extractAuthor(value: unknown): string | null {
  if (typeof value === "string") return normalizeText(value) || null;
  if (Array.isArray(value)) {
    for (const item of value) {
      const author = extractAuthor(item);
      if (author) return author;
    }
    return null;
  }
  if (value && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return firstString(object.name, object.alternateName) || null;
  }
  return null;
}

function extractImage(value: unknown, pageUrl: string): string | null {
  if (typeof value === "string" && value.trim()) return absolutize(value.trim(), pageUrl);
  if (Array.isArray(value)) {
    for (const item of value) {
      const image = extractImage(item, pageUrl);
      if (image) return image;
    }
    return null;
  }
  if (value && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return extractImage(object.url ?? object.contentUrl, pageUrl);
  }
  return null;
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return normalizeText(value);
  }
  return "";
}

function normalizeContent(raw: string): string {
  const paragraphs = raw.replace(/\r/g, "\n").split(/\n{2,}|(?<=[.!?])\s{2,}/).map(normalizeText);
  const cleaned = cleanBlocks(paragraphs);
  return cleaned.join("\n\n").slice(0, MAX_ARTICLE_CHARS).trim();
}

function normalizeText(raw: string): string {
  return decodeEntities(raw).replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
}

function isBoilerplateBlock(text: string): boolean {
  if (text.length > 260) return false;
  return /^(?:reklama|advertisement|sponsored|promoted|materiał sponsorowany|czytaj także|zobacz także|read also|related articles?|recommended|udostępnij|share(?: this)?|subskrybuj|subscribe|sign up|newsletter|zaakceptuj cookies|accept cookies|privacy settings|ustawienia prywatności|komentarze|comments?)\b/i.test(text)
    || /^(?:facebook|x|twitter|instagram|linkedin|whatsapp|telegram)(?:\s+share)?$/i.test(text);
}

function decodeEntities(raw: string): string {
  return raw
    .replace(/&nbsp;/gi, " ")
    .replace(/&quot;/gi, '"')
    .replace(/&apos;|&#0?39;/gi, "'")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&#(\d+);/g, (_, value) => safeCodePoint(Number(value)))
    .replace(/&#x([0-9a-f]+);/gi, (_, value) => safeCodePoint(Number.parseInt(value, 16)))
    .replace(/&amp;/gi, "&");
}

function safeCodePoint(value: number): string {
  try {
    return Number.isFinite(value) ? String.fromCodePoint(value) : "";
  } catch {
    return "";
  }
}

function absolutize(raw: string, base: string): string {
  try {
    return new URL(raw, base).toString();
  } catch {
    return raw;
  }
}

async function readCapped(response: Response, maxBytes: number): Promise<string> {
  const reader = response.body?.getReader();
  if (!reader) return (await response.text()).slice(0, maxBytes);
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!value) continue;
    const remaining = maxBytes - total;
    if (value.length > remaining) {
      if (remaining > 0) chunks.push(value.subarray(0, remaining));
      await reader.cancel();
      break;
    }
    chunks.push(value);
    total += value.length;
    if (total >= maxBytes) {
      await reader.cancel();
      break;
    }
  }
  const out = new Uint8Array(chunks.reduce((sum, chunk) => sum + chunk.length, 0));
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return new TextDecoder().decode(out);
}

function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { ...CORS, "content-type": "application/json; charset=utf-8" },
  });
}
