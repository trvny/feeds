# External Integrations

## Core Sections (Required)

### 1) Integration Inventory

| System | Type (API/DB/Queue/etc) | Purpose | Auth model | Criticality | Evidence |
|--------|---------------------------|---------|------------|-------------|----------|
| Native RSS/Atom feeds and public web pages | HTTP upstreams | Primary source material for generators and enrichment | Usually none | high | `feed_generators/multi_rss.py`, `feed_generators/utils.py` |
| Source-specific APIs | HTTP APIs | Weather, quotes, images and other feed-specific data | GitHub Actions secrets where required | medium/high per feed | `.github/workflows/update-feeds.yml`, `feed_generators/openweather.py`, `feed_generators/visualcrossing.py`, `feed_generators/unsplash.py`, `feed_generators/theysaidso.py` |
| Google News | RSS + internal HTTP endpoint | Discovery path for hard-to-scrape publishers and wrapper-link resolution | No account; fixed consent-state cookie | medium | `feed_generators/google_news.py` |
| Article pages / Open Graph / JSON-LD | HTTP pages | Backfill missing entry images and dimensions | none | medium | `feed_generators/article_image.py` |
| feedsearch.dev | HTTP API | Manual fallback feed discovery when local crawler is unavailable/empty | none | low | `feed_generators/discover.py` |
| GitHub repository + raw content | Git hosting/CDN | Source of truth, scheduled commits and `rel=self` feed URLs | GitHub Actions token for writes | high | `.github/workflows/update-feeds.yml`, `feed_generators/utils.py` |
| GitHub Pages | Static hosting | Public feed directory, XML/JSON artifacts and reader | GitHub deployment workflow | high | `.github/workflows/deploy-pages.yml`, `site/build_site.py` |
| Cloudflare R2 | Object storage | Private backup of persistent generation cache | Cloudflare API token/account ID | medium | `.github/workflows/update-feeds.yml`, `docs/cache.md` |
| Cloudflare Workers | Edge runtime | Optional HTTPS CORS proxy for the browser reader | Deployment account config; public read endpoint | medium | `feeds-proxy/wrangler.jsonc`, `feeds-proxy/src/index.js` |
| Google S2 / DuckDuckGo icons | HTTP asset services | Favicon fallback/resolution | none | low | `feed_generators/utils.py`, `site/build_site.py` |

### 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| `cache/*.json` | Incremental entry state, durable IDs and settled enrichment results | `feed_generators/utils.py` and source adapters | Stale/corrupt cache can affect dedupe/history; loaders fall back safely and writes are atomic | `feed_generators/utils.py` |
| `feeds/*.xml` + `feeds/*.json` | Published feed artifacts | shared feed writers and `jsonfeed.py` | Generated output must not be hand-edited | `feed_generators/utils.py`, `feed_generators/jsonfeed.py` |
| R2 `feedseek-cache/snapshots/cache.tar.gz` | Off-repo cache recovery snapshot | scheduled GitHub Actions workflow | Backup is best-effort and intentionally skipped above the size ceiling | `.github/workflows/update-feeds.yml` |

No database, queue or event bus is present in the repository.

### 3) Secrets and Credentials Handling

- Credentials are injected from GitHub Actions secrets; repository instructions explicitly prohibit committing secrets to feeds, caches, logs or examples.
- Feed/API secrets currently referenced by the scheduled workflow include `OPENWEATHER_API_KEY`, `VISUALCROSSING_API_KEY`, `UNSPLASH_ACCESS_KEY`, `THEYSAIDSO_API_KEY` and `ANYCRAP_API_KEY`.
- R2 access uses `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
- Hardcoding check: no secret value was identified in the inspected maintained configuration. `google_news.py` contains a fixed consent-state cookie, documented as non-personalized rather than an account credential.
- Rotation/lifecycle: `[TODO]` no repository policy documents rotation intervals for third-party API credentials.

### 4) Reliability and Failure Behavior

- HTTP calls generally use explicit per-request timeouts; `run_all_feeds.py` adds a 480-second default wall-clock limit per generator.
- Image and Google News enrichment have per-run count, wall-clock and retry-attempt budgets and are non-fatal.
- The top-level generator loop is failure-isolated and continues after a source failure; empty/failing source runs preserve last-known-good output.
- R2 restore/backup is best-effort (`continue-on-error`) and falls back to committed cache state.
- `feeds-proxy` allows only HTTPS targets, revalidates redirects, caps redirects at 3, response bodies at 2 MiB and upstream time at 8 seconds.
- No general circuit-breaker abstraction is present; source-specific retry/backoff varies by adapter.

### 5) Observability for Integrations

- Python integration paths use standard logging; top-level generation relays each child process's stdout/stderr with the feed name.
- Feed validation writes non-OK results to `GITHUB_STEP_SUMMARY` when available.
- Worker observability is enabled in `wrangler.jsonc` with 1% head sampling; persistent invocation logs are disabled.
- There is no repository-wide metrics or distributed-tracing layer for the Python generation pipeline.

### 6) Evidence

- `.github/workflows/update-feeds.yml`
- `feed_generators/utils.py`
- `feed_generators/multi_rss.py`
- `feed_generators/google_news.py`
- `feed_generators/article_image.py`
- `feed_generators/discover.py`
- `feeds-proxy/src/index.js`
- `feeds-proxy/wrangler.jsonc`
