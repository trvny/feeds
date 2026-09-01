const FETCH_TIMEOUT_MS = 8000;
const MAX_REDIRECTS = 3;
const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;
const BODYLESS_STATUSES = new Set([101, 204, 205, 304]);
const PROXY_ORIGIN = "https://feeds.trfny.com";
const ROBOTS = "User-agent: *\nAllow: /index.md\nAllow: /llms.txt\nAllow: /llms-full.txt\nDisallow: /\n";
const INDEX_MD = `# Feedseek fetch proxy\n\n> Constrained HTTPS fetch helper used by the Feedseek Reader.\n\nThe proxy accepts a public HTTPS target through the \`url\` query parameter. It blocks private-looking hosts, non-HTTPS targets, unsafe redirects and oversized responses.\n\n- [Feedseek](${"https://trvny.github.io/feedseek/"})\n- [Concise LLM guide](${PROXY_ORIGIN}/llms.txt)\n- [Full LLM guide](${PROXY_ORIGIN}/llms-full.txt)\n- [Source](https://github.com/trvny/feedseek/tree/main/feeds-proxy)\n`;
const LLMS = `# Feedseek fetch proxy\n\n> Constrained public HTTPS fetch helper for Feedseek's browser Reader.\n\n## Resources\n\n- [Proxy overview](${PROXY_ORIGIN}/index.md): Markdown description and security boundaries.\n- [Feedseek site](https://trvny.github.io/feedseek/index.md): main feed directory.\n- [Full proxy guide](${PROXY_ORIGIN}/llms-full.txt): complete proxy documentation.\n- [Source](https://github.com/trvny/feedseek/tree/main/feeds-proxy): implementation and tests.\n`;
const LLMS_FULL = `# Feedseek fetch proxy full documentation\n\nSource: ${PROXY_ORIGIN}/\n\nDescription: Complete LLM-oriented guide to the constrained Feedseek Reader fetch proxy.\n\n## Contract\n\nGET requests with a \`url=https://...\` query parameter fetch a public HTTPS resource for the Reader. Responses are size-bounded and redirects are followed only after each target is revalidated.\n\n## Security boundaries\n\nThe proxy rejects non-HTTPS schemes, credentials in URLs, non-standard ports, localhost/private-looking names and direct IP literals. Redirects are capped and revalidated. Responses are capped at 2 MiB. It is not intended as a general open proxy.\n\n## Search indexing\n\nProxied upstream payloads are returned with X-Robots-Tag noindex,nofollow so the proxy cannot become an indexed duplicate of the source feed.\n\n## Related\n\n- [Feedseek](https://trvny.github.io/feedseek/index.md)\n- [Source](https://github.com/trvny/feedseek/tree/main/feeds-proxy)\n`;


const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, HEAD, OPTIONS",
  "access-control-allow-headers": "accept, content-type",
};

const SECURITY_HEADERS = {
  "x-content-type-options": "nosniff",
  "content-security-policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'",
  "referrer-policy": "no-referrer",
};

/**
 * @param {string} message
 * @param {number} status
 */
function text(message, status) {
  return new Response(message, {
    status,
    headers: {
      ...CORS_HEADERS,
      ...SECURITY_HEADERS,
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

/** @param {string} hostname */
function isBlockedHostname(hostname) {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  if (!host || host === "localhost" || host.endsWith(".localhost")) return true;
  if (host.endsWith(".local") || host.endsWith(".internal") || host.endsWith(".home") || host.endsWith(".lan")) return true;
  if (host.includes(":")) return true;
  if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(host)) return true;
  return false;
}

/**
 * @param {string} value
 * @param {string | URL | undefined} [base]
 */
function parseTarget(value, base) {
  let target;
  try {
    target = new URL(value, base);
  } catch {
    throw new Error("bad url");
  }

  if (target.protocol !== "https:" || target.username || target.password) throw new Error("bad url");
  if (target.port && target.port !== "443") throw new Error("bad url");
  if (isBlockedHostname(target.hostname)) throw new Error("blocked host");
  return target;
}

/** @param {URL} initialUrl */
async function fetchWithRedirects(initialUrl) {
  let target = initialUrl;

  for (let redirects = 0; redirects <= MAX_REDIRECTS; redirects++) {
    const response = await fetch(target, {
      headers: {
        "user-agent": "feedseek-reader/2.0",
        accept: "application/atom+xml, application/rss+xml, application/xml, text/xml, application/json, text/plain, text/html;q=0.8, */*;q=0.1",
      },
      redirect: "manual",
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });

    if (![301, 302, 303, 307, 308].includes(response.status)) return response;
    if (redirects === MAX_REDIRECTS) throw new Error("too many redirects");

    const location = response.headers.get("location");
    if (!location) throw new Error("bad redirect");
    target = parseTarget(location, target);
  }

  throw new Error("too many redirects");
}

/** @param {Response} response */
async function readLimited(response) {
  if (BODYLESS_STATUSES.has(response.status) || !response.body) return null;

  const declared = Number(response.headers.get("content-length") || 0);
  if (declared > MAX_RESPONSE_BYTES) throw new Error("response too large");

  const reader = response.body.getReader();
  /** @type {Uint8Array[]} */
  const chunks = [];
  let size = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      size += value.byteLength;
      if (size > MAX_RESPONSE_BYTES) {
        await reader.cancel("response too large");
        throw new Error("response too large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

/** @type {Record<string, {body: string, contentType: string, maxAge: number}>} */
const DISCOVERY = {
  "/robots.txt": { body: ROBOTS, contentType: "text/plain; charset=utf-8", maxAge: 86400 },
  "/index.md": { body: INDEX_MD, contentType: "text/markdown; charset=utf-8", maxAge: 3600 },
  "/llms.txt": { body: LLMS, contentType: "text/plain; charset=utf-8", maxAge: 3600 },
  "/llms-full.txt": { body: LLMS_FULL, contentType: "text/plain; charset=utf-8", maxAge: 3600 },
};

/** @param {Request} request @param {URL} requestUrl */
function discoveryResponse(request, requestUrl) {
  const discovery = DISCOVERY[requestUrl.pathname];
  if (!discovery || (request.method !== "GET" && request.method !== "HEAD")) return null;
  const { body, contentType, maxAge } = discovery;
  return new Response(request.method === "HEAD" ? null : body, {
    headers: {
      ...CORS_HEADERS,
      ...SECURITY_HEADERS,
      "content-type": contentType,
      "cache-control": `public, max-age=${maxAge}`,
    },
  });
}

/** @param {URL} requestUrl */
async function proxyResponse(requestUrl) {
  const raw = requestUrl.searchParams.get("url");
  if (!raw) return text("bad url", 400);

  let target;
  try {
    target = parseTarget(raw);
  } catch (error) {
    const blocked = error instanceof Error && error.message === "blocked host";
    return text(blocked ? "blocked host" : "bad url", blocked ? 403 : 400);
  }

  let upstream;
  try {
    upstream = await fetchWithRedirects(target);
  } catch (error) {
    const message = error instanceof Error && error.name === "TimeoutError"
      ? "upstream timeout"
      : error instanceof Error
        ? error.message
        : "fetch failed";
    return text(message, 502);
  }

  let body;
  try {
    body = await readLimited(upstream);
  } catch (error) {
    return text(error instanceof Error ? error.message : "fetch failed", 502);
  }

  const headers = new Headers({ ...CORS_HEADERS, ...SECURITY_HEADERS });
  headers.set("content-type", upstream.headers.get("content-type") || "application/xml; charset=utf-8");
  headers.set("cache-control", upstream.ok ? "public, max-age=900" : "no-store");
  headers.set("x-robots-tag", "noindex, nofollow");
  return new Response(body, { status: upstream.status, headers });
}

export default {
  /** @param {Request} request */
  async fetch(request) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS_HEADERS });
    const requestUrl = new URL(request.url);
    const discovery = discoveryResponse(request, requestUrl);
    if (discovery) return discovery;
    if (request.method !== "GET") return text("method not allowed", 405);
    return proxyResponse(requestUrl);
  },
};
