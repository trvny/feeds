const FETCH_TIMEOUT_MS = 8000;
const MAX_REDIRECTS = 3;
const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;
const BODYLESS_STATUSES = new Set([101, 204, 205, 304]);

// Only these origins get a CORS grant. The proxy exists for feedseek's browser
// reader; served with `access-control-allow-origin: *` it is an open proxy that
// anyone can point at anything, which is what put it behind Cloudflare Access
// in the first place. An allowlist keeps the reader working without that.
const ALLOWED_ORIGINS = new Set([
  "https://trvny.github.io",
]);
const LOCAL_ORIGIN_RE = /^http:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?$/;

/**
 * Echo the request origin when it is allowed, or null.
 * @param {string | null} origin
 */
function allowOrigin(origin) {
  if (!origin) return null;
  if (ALLOWED_ORIGINS.has(origin) || LOCAL_ORIGIN_RE.test(origin)) return origin;
  return null;
}

/**
 * Per-origin CORS headers. `vary` matters because the response is edge-cached
 * and the allow-origin value now differs between callers.
 * @param {string | null} origin
 */
function corsHeaders(origin) {
  return {
    "access-control-allow-origin": origin || "null",
    "access-control-allow-methods": "GET, OPTIONS",
    "access-control-allow-headers": "accept, content-type",
    vary: "origin",
  };
}

const SECURITY_HEADERS = {
  "x-content-type-options": "nosniff",
  "content-security-policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'",
  "referrer-policy": "no-referrer",
};

/**
 * @param {string} message
 * @param {number} status
 * @param {string | null} [origin]
 */
function text(message, status, origin = null) {
  return new Response(message, {
    status,
    headers: {
      ...corsHeaders(origin),
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

export default {
  /**
   * @param {Request} request
   * @param {{ PROXY_TOKEN?: string }} env
   */
  async fetch(request, env) {
    const origin = allowOrigin(request.headers.get("origin"));

    if (request.method === "OPTIONS") {
      if (!origin) return text("forbidden origin", 403);
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }
    if (request.method !== "GET") return text("method not allowed", 405, origin);

    const requestUrl = new URL(request.url);

    // A browser always sends Origin on a cross-origin fetch, so a request
    // without one is not the reader. Those are only served when they carry the
    // PROXY_TOKEN secret, which keeps command-line and server-side use possible
    // without leaving the proxy open. Set it with:
    //   npx wrangler secret put PROXY_TOKEN
    if (!origin) {
      const token = requestUrl.searchParams.get("token");
      if (!env.PROXY_TOKEN || token !== env.PROXY_TOKEN) return text("forbidden origin", 403);
    }

    const raw = requestUrl.searchParams.get("url");
    if (!raw) return text("bad url", 400, origin);

    let target;
    try {
      target = parseTarget(raw);
    } catch (error) {
      const blocked = error instanceof Error && error.message === "blocked host";
      return text(blocked ? "blocked host" : "bad url", blocked ? 403 : 400, origin);
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
      return text(message, 502, origin);
    }

    let body;
    try {
      body = await readLimited(upstream);
    } catch (error) {
      return text(error instanceof Error ? error.message : "fetch failed", 502, origin);
    }

    const headers = new Headers({ ...corsHeaders(origin), ...SECURITY_HEADERS });
    headers.set("content-type", upstream.headers.get("content-type") || "application/xml; charset=utf-8");
    headers.set("cache-control", upstream.ok ? "public, max-age=900" : "no-store");
    return new Response(body, { status: upstream.status, headers });
  },
};
