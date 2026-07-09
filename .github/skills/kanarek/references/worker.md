# kanarek — Cloudflare Worker

`kanarek/worker`, TypeScript, a single `src/index.ts` fetch handler. It proxies RSS/Atom → JSON at the edge so the news widget can refresh cheaply, adds feed discovery + scraping, and backs per-device read-state/subscriptions/pairing via D1. Deployed at **`kanarek.travny.workers.dev`** (script name `kanarek`). The app works without it (on-device parse), so the feed proxy must stay an optional, drop-in accelerator — same item shape, same behavior.

## Routes

- **`/?feeds=<url,url>`** (or `DEFAULT_FEEDS`) — fetch each feed, parse, merge, return JSON items. Each source runs under its **own guard**; one bad feed can't sink the response. Emits a **weak ETag** (see below).
- **`/health`** — liveness.
- **`/discover?url=<page>`** — read `<link rel="alternate" type="application/rss+xml|atom+xml">` from the page head; fall back to probing common feed paths (`/feed`, `/rss`, `/atom.xml`, …).
- **`/scrape?url=<page>`** — extract repeating item blocks via `HTMLRewriter` with auto-detected selectors and **emit Atom XML**, so a scraped source flows through discovery → app exactly like a native feed. Results cache in KV (`SCRAPE_KV`).
- **`/state`, `/pair`** — per-device read-state, subscriptions, and pairing, backed by D1 (`STATE_DB`). Write-heavy (every mark-read), which is why it's D1 not KV. **If the D1 binding is absent these return `503`; the rest of the Worker is unaffected** — keep that graceful degradation.

## Conditional GET (the load-bearing bit)

- The ETag is **weak** and hashed over the **item set only** — exclude the volatile `fetched`/now timestamp so unchanged news yields a **stable** tag.
- Honor `If-None-Match` with a **bodyless `304`**; RFC 7232 matching must handle `*`, comma lists, and weak comparison.
- Edge-cache key is the **URL only** (don't fold in headers that vary per request).
- Expose `ETag` via CORS so the device can read it. The device side (`FeedCache`) stores last-good ETag+body per URL and replays the body on `304`.

Breaking any of these silently disables 304s (timestamp in the tag) or corrupts caching — verify with the Vitest suite.

## Config & bindings

`worker/wrangler.jsonc` (`compatibility_date` currently `2026-06-01`):

- vars `DEFAULT_FEEDS` and `ALLOWED_HOSTS`. `DEFAULT_FEEDS` is **kept in parity with the app's `NewsRepository`** and currently carries six sources: Google News PL, Euronews PL, Antyweb, plus three feedseek raw feeds (`raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/{feed_wikipedia_pl,feed_daily_digest,feed_jbzd}.xml`).
- KV `SCRAPE_KV` → `id: 1534e989ac23449fab8e18abc2bc250d` (durable `/discover`+`/scrape` cache; Worker also runs fine on Cache API alone).
- D1 `STATE_DB` → **`database_name: kanarek-state`**, `database_id: e3de16b1-9c52-4992-aac4-be07eef70cc2`, `migrations_dir: migrations` (`0001_state.sql`).
- Plain fetch handler, no Node APIs — `compatibility_date` bumps are low-risk.
- Secrets, if any are added, live in Worker secrets, never committed, never sent to the device.

## Local checks (sandbox)

```
git clone … && cd feeds
npm --prefix kanarek/worker ci
npx --prefix kanarek/worker tsc --noEmit
npm --prefix kanarek/worker test        # Vitest
```
`wrangler unstable_dev` smoke tests work for hitting live routes. CI: `worker-ci.yml` runs `tsc` + Vitest.

## Deploy without wrangler

The sandbox has no CF token for `wrangler deploy`, but `Cloudflare:execute` can deploy directly:

1. Bundle: `esbuild kanarek/worker/src/index.ts --bundle --format=esm --platform=neutral --target=es2022 --minify`.
2. base64 the output; inside the execute fn `atob()` it.
3. Multipart **PUT** `/accounts/{accountId}/workers/scripts/kanarek` with the script as the ESM module part and **metadata** carrying bindings: KV `SCRAPE_KV` = `1534e989ac23449fab8e18abc2bc250d`, D1 `STATE_DB` = `kanarek-state` / `e3de16b1-9c52-4992-aac4-be07eef70cc2`, plain-text vars `DEFAULT_FEEDS` / `ALLOWED_HOSTS`, `main_module` = the module name.
4. **POST** `/accounts/{accountId}/workers/scripts/kanarek/subdomain` `{enabled:true}` for workers.dev exposure.
5. Smoke-test `/health`, `/?feeds=…`, `/discover`, `/scrape` live.

Account `d29db89a330417194726eb69450a4668`, subdomain `travny`. `workers_list` confirms deployment; `kv_namespaces_list` lists KV; `d1_databases_list` lists D1. The pre-rename Worker `feedget` and DB `feedget-state` are dead post-migration — if they still exist in the CF dashboard they can be deleted.

## Changing default feeds

A default-feed change is a **two-file commit**: the app's `NewsRepository` defaults **and** the Worker's `DEFAULT_FEEDS` (`worker/wrangler.jsonc`, plus the deploy metadata if you redeploy). They must match. Keep `kanarek/README.md` current.
