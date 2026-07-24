const FETCH_TIMEOUT_MS = 8000;
const MAX_REDIRECTS = 3;
const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;
const BODYLESS_STATUSES = new Set([101, 204, 205, 304]);

const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "accept, content-type",
};

const SECURITY_HEADERS = {
  "x-content-type-options": "nosniff",
  "content-security-policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'",
  "referrer-policy": "no-referrer",
};

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

function isBlockedHostname(hostname) {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  if (!host || host === "localhost" || host.endsWith(".localhost")) return true;
  if (host.endsWith(".local") || host.endsWith(".internal") || host.endsWith(".home") || host.endsWith(".lan")) return true;
  if (host.includes(":")) return true;
  if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(host)) return true;
  return false;
}

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

async function readLimited(response) {
  if (BODYLESS_STATUSES.has(response.status) || !response.body) return null;

  const declared = Number(response.headers.get("content-length") || 0);
  if (declared > MAX_RESPONSE_BYTES) throw new Error("response too large");

  const reader = response.body.getReader();
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
  async fetch(request) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS_HEADERS });
    if (request.method !== "GET") return text("method not allowed", 405);

    const raw = new URL(request.url).searchParams.get("url");
    if (!raw) return text("bad url", 400);

    let target;
    try {
      target = parseTarget(raw);
    } catch (error) {
      const blocked = error.message === "blocked host";
      return text(blocked ? "blocked host" : "bad url", blocked ? 403 : 400);
    }

    let upstream;
    try {
      upstream = await fetchWithRedirects(target);
    } catch (error) {
      const message = error && error.name === "TimeoutError" ? "upstream timeout" : error.message || "fetch failed";
      return text(message, 502);
    }

    let body;
    try {
      body = await readLimited(upstream);
    } catch (error) {
      return text(error.message || "fetch failed", 502);
    }

    const headers = new Headers({ ...CORS_HEADERS, ...SECURITY_HEADERS });
    headers.set("content-type", upstream.headers.get("content-type") || "application/xml; charset=utf-8");
    headers.set("cache-control", upstream.ok ? "public, max-age=900" : "no-store");
    return new Response(body, { status: upstream.status, headers });
  },
};
