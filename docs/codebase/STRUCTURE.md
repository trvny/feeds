# Codebase Structure

## Core Sections (Required)

### 1) Top-Level Map

| Path | Purpose | Evidence |
|------|---------|----------|
| `feed_generators/` | Per-source adapters plus shared parsing, normalization, cache, identity, enrichment and rendering helpers | `feed_generators/run_all_feeds.py`, `feed_generators/utils.py` |
| `feeds.yaml` | Maintained registry selecting generator script, source URL, type and enabled state | `feed_generators/models.py` |
| `feeds/` | Generated public XML and JSON Feed artifacts | `feed_generators/utils.py`, `feed_generators/jsonfeed.py` |
| `cache/` | Generated incremental/last-known state used across scheduled runs | `feed_generators/utils.py`, `docs/cache.md` |
| `site/` | Static Pages builder, browser reader, feed allowlist and OPML assets | `site/build_site.py`, `site/reader.js`, `site/published_feeds.txt` |
| `feeds-proxy/` | Independent Cloudflare Worker used as the reader's optional CORS proxy | `feeds-proxy/README.md`, `feeds-proxy/src/index.js` |
| `tests/` | Python repository and feed-pipeline tests | `tests/test_run_all_feeds.py`, `tests/test_registry_docs.py` |
| `.github/` | Feed scheduling, Pages deploy, reader/Worker CI, linting, dependency and security automation | `.github/workflows/` |
| `docs/` | Maintained architecture/feed/cache notes plus generated source inventory | `docs/architecture.md`, `docs/feeds.md`, `docs/cache.md` |

### 2) Entry Points

- Main runtime entry: `feed_generators/run_all_feeds.py`.
- Generator adapter: `feed_generators/invoke_generator.py` loads each registered source script and normalizes historical `main()` signatures/results.
- Static-site entry: `site/build_site.py` produces `public/` for GitHub Pages.
- Worker entry: `feeds-proxy/src/index.js` exports the Cloudflare Worker `fetch` handler.
- Manual scouting entry: `feed_generators/discover.py` finds native feed candidates and is not part of the scheduled pipeline.
- Entry selection: `run_all_feeds.py` loads `feeds.yaml` through `feed_generators/models.py` and executes enabled generator scripts in isolated subprocesses.

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| Registry/orchestration | Feed declarations, validation, dispatch and failure accounting | Source-specific scraping rules |
| Shared generator core | HTTP helpers, normalization, dedupe, cache, identity, enrichment, feed serialization | One-off copies of the same logic inside adapters |
| Per-source generators | Source URLs, parsing quirks and source-specific transforms | Hand-maintained generated feed/cache output |
| Generated state | XML/JSON feed files and cache snapshots | Maintained source logic |
| Site/reader | Static publication, discovery metadata, browser reading behavior | Feed generation business logic |
| `feeds-proxy` | HTTPS CORS proxy behavior and its tests/config | Feed source registry or Python pipeline state |

### 4) Naming and Organization Rules

- Python files and functions use `snake_case`, for example `run_all_feeds.py`, `normalize_link()` and `save_cache()`.
- Generator names align with registry/output names: `<name>.py`, `feeds/feed_<name>.xml`, `feeds/feed_<name>.json`, `cache/<name>_posts.json`.
- Python tests live in `tests/` and use `test_*.py`; JavaScript tests use `*.test.js` under component-local `test/` directories.
- The Python tree is script-oriented rather than packaged. Modules import nearby helpers directly, and tests insert `feed_generators/` into `sys.path` where necessary.

### 5) Evidence

- `feeds.yaml`
- `feed_generators/run_all_feeds.py`
- `feed_generators/invoke_generator.py`
- `feed_generators/utils.py`
- `site/build_site.py`
- `feeds-proxy/src/index.js`
