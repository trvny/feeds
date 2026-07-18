# feeds-proxy

Minimal HTTPS-only CORS proxy: `GET /?url=https://...` fetches the target and
re-serves it with `access-control-allow-origin: *` and a 15-minute edge cache.

Used as the optional "CORS proxy prefix" in feedseek's browser reader
(`feedseek/site/reader.html`) for feeds whose origin doesn't send CORS
headers. Not tied to feedseek or kanarek specifically — either one, or
anything else in the account, can point at it.

## Behavior

- No `url` param, or non-`https://` target → `400`
- Upstream fetch fails or times out (8s) → `502`
- Otherwise: passes through status + body, forces `access-control-allow-origin: *`
  and `cache-control: public, max-age=900`, defaults content-type to
  `application/xml; charset=utf-8` when upstream doesn't send one

## Deploy

```
npm install
npm run deploy
```

Live at `feeds-proxy.travny.workers.dev`.
