# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python, with a small JavaScript surface for the reader and Worker | `pyproject.toml`, `site/`, `feeds-proxy/` |
| Runtime + version | CPython >=3.14; CI pins Python 3.14. Reader/Worker CI pins Node.js 24 | `pyproject.toml`, `.github/workflows/update-feeds.yml`, `.github/workflows/reader-ci.yml`, `.github/workflows/worker-ci.yml` |
| Package manager | uv for Python; npm for `feeds-proxy` | `uv.lock`, `Makefile`, `feeds-proxy/package-lock.json` |
| Module/build system | Script-oriented Python project (`package = false`), static-site build scripts, ES modules for the Worker | `pyproject.toml`, `site/build_site.py`, `feeds-proxy/package.json` |

### 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| beautifulsoup4 | 4.15.0 locked | HTML/XML parsing and extraction | `pyproject.toml`, `uv.lock`, `feed_generators/multi_rss.py` |
| curl-cffi | 0.16.1 locked | Browser-like HTTP fallback for origins that reject plain Requests | `pyproject.toml`, `uv.lock`, `feed_generators/multi_rss.py` |
| feedgen2 | 2.0.1 locked | Atom/RSS generation and extensions | `pyproject.toml`, `uv.lock`, `feed_generators/utils.py` |
| feedparser | 6.0.14 locked | Feed normalization/parsing, including XML-to-JSON Feed conversion | `pyproject.toml`, `uv.lock`, `feed_generators/jsonfeed.py` |
| lxml | 6.1.2 locked | XML/HTML support | `pyproject.toml`, `uv.lock` |
| pydantic | 2.13.4 locked | Validation of `feeds.yaml` registry entries | `pyproject.toml`, `uv.lock`, `feed_generators/models.py` |
| python-dateutil / pytz | 2.9.0.post0 / 2026.3.post1 locked | Date parsing and timezone normalization | `uv.lock`, `feed_generators/multi_rss.py`, `feed_generators/utils.py` |
| PyYAML | 6.0.3 locked | `feeds.yaml` loading | `uv.lock`, `feed_generators/models.py` |
| Requests | 2.34.2 locked | Primary HTTP client | `uv.lock`, `feed_generators/utils.py` |

The Worker has no runtime npm dependency. Its development toolchain locks TypeScript 7.0.2 and Wrangler 4.125.0 in `feeds-proxy/package-lock.json`.

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| uv | Reproducible Python environment and locked commands | `Makefile`, `uv.lock` |
| Ruff 0.16.4 | Python linting; target `py314`, line length 120 | `.github/linters/.ruff.toml`, `uv.lock` |
| unittest | Python tests and mocking via the standard library | `tests/`, `.github/workflows/update-feeds.yml` |
| Node.js `node:test` | Reader and Worker tests | `site/test/`, `feeds-proxy/test/` |
| Wrangler 4.125.0 | Worker typecheck/dry-run/deploy tooling | `feeds-proxy/package.json`, `feeds-proxy/package-lock.json` |
| MegaLinter / CodeQL | Repository lint and static/security analysis | `.github/workflows/mega-linter.yml`, `.github/workflows/codeql.yml` |

### 4) Key Commands

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/run_all_feeds.py
uv run --locked feed_generators/validate_feeds.py
node --test site/test/*.test.js
cd feeds-proxy && npm ci && npm run check
```

### 5) Environment and Config

- Config sources: `feeds.yaml`, `pyproject.toml`, `uv.lock`, `.github/workflows/update-feeds.yml`, `feeds-proxy/wrangler.jsonc`.
- Secret-backed feed inputs used by the scheduled workflow: `OPENWEATHER_API_KEY`, `VISUALCROSSING_API_KEY`, `UNSPLASH_ACCESS_KEY`, `THEYSAIDSO_API_KEY`, `ANYCRAP_API_KEY`, plus `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` for R2.
- Optional runtime knobs include `RSS_REPO_SLUG`, `FEEDSEEK_GENERATOR_TIMEOUT`, image/Google News lookup budgets, weather location settings, and source-specific IMGW settings.
- Deployment/runtime constraints: Python 3.14 in feed CI, Node.js 24 in reader/Worker CI, and Worker compatibility date `2026-07-14`.

### 6) Evidence

- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `.github/workflows/update-feeds.yml`
- `feeds-proxy/package.json`
- `feeds-proxy/wrangler.jsonc`
