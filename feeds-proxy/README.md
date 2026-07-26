# feeds-proxy

Minimal HTTPS-only CORS proxy: `GET /?url=https://...` fetches the target and
re-serves it with CORS headers for an allowlisted origin and a 15-minute edge
cache.

Used as the optional "CORS proxy prefix" in feedseek's browser reader
(`feedseek/site/reader.html`) for feeds whose origin doesn't send CORS
headers. Not tied to feedseek or kanarek specifically — either one, or
anything else in the account, can point at it.

## Access control

Served with `access-control-allow-origin: *` this is an open proxy: anyone can
point it at anything. So the CORS grant is limited to an allowlist —
`https://trvny.github.io` plus `localhost`/`127.0.0.1` for local development —
and the origin is echoed back rather than starred, with `vary: origin` so the
edge cache stays correct per caller.

A browser always sends `Origin` on a cross-origin fetch, so a request without
one is not the reader. Those are rejected unless they carry the `PROXY_TOKEN`
secret as `?token=`, which keeps command-line and server-side use possible:

```
npx wrangler secret put PROXY_TOKEN
curl "https://feeds-proxy.travny.workers.dev/?token=<secret>&url=https://example.com/feed"
```

With no secret set, tokenless non-browser requests simply get `403`.

This replaces the Cloudflare Access policy that was in front of the Worker —
Access returned its sign-in page to the reader instead of the feed, and a
service token can't help a browser client because the secret would have to ship
in public JavaScript. Remove the Access application for
`feeds-proxy.travny.workers.dev` before deploying this, or nothing reaches the
Worker at all.

## Behavior

- Origin not on the allowlist, or absent without a valid token → `403`
- No `url` param, or non-`https://` target → `400`
- Upstream fetch fails or times out (8s) → `502`
- Otherwise: passes through status + body, sets `access-control-allow-origin` to
  the calling origin and `cache-control: public, max-age=900`, and defaults
  content-type to `application/xml; charset=utf-8` when upstream doesn't send one

## Deploy

```
npm install
npm run deploy
```

Live at `feeds-proxy.travny.workers.dev`.
