const FETCH_TIMEOUT_MS = 8000;

export default {
  /** @param {Request} req */
  async fetch(req) {
    const u = new URL(req.url).searchParams.get('url');
    if (!u || !/^https:\/\//.test(u)) return new Response('bad url', { status: 400 });
    let r;
    try {
      r = await fetch(u, {
        headers: { 'user-agent': 'feedseek-reader/1.0' },
        redirect: 'follow',
        signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
      });
    }
    catch (/** @type {any} */ e) {
      const msg = e && e.name === 'TimeoutError' ? 'upstream timeout' : 'fetch failed';
      return new Response(msg, { status: 502 });
    }
    const h = new Headers();
    h.set('content-type', r.headers.get('content-type') || 'application/xml; charset=utf-8');
    h.set('access-control-allow-origin', '*');
    h.set('cache-control', 'public, max-age=900');
    return new Response(r.body, { status: r.status, headers: h });
  }
};
