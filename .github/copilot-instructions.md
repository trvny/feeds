# Copilot instructions for feedseek

Feedseek generates self-updating RSS/Atom feeds for ~95 sites that lack a usable native feed. Python generators fetch/parse/normalize/deduplicate entries and write `feeds/feed_<name>.xml` (+ JSON Feed sidecars) with per-feed state in `cache/<name>_posts.json`. Scheduled workflow refreshes feeds every 2h. Repo is ~96% Python, plus `feeds-proxy/`, a small Cloudflare Worker (JS + TS typecheck only).

## Environment and commands (validated paths)

Python **>= 3.14** is required (`requires-python = ">=3.14"`); a bare `python` on PATH will usually fail. **Everything runs through `uv`**. Always use the locked forms:

```bash
make install                                       # uv sync --locked  (fails if uv.lock is stale -> run `make lock`)
uv run --locked python -m unittest discover -s tests   # the test suite (unittest, no pytest)
uv run --locked feed_generators/validate_feeds.py      # validate all generated feeds (same as `make validate`)
uv run --locked feed_generators/run_all_feeds.py --feed <name>   # run ONE generator (fast; `make feeds` runs all ~95, ~12 min, hits the live web — avoid unless needed)
uv run --locked feed_generators/docs_sources.py        # regenerate docs/sources.md after registry changes
```

- `uv sync --locked` before anything else; `--locked` never refreshes `uv.lock` as a side effect. After editing `pyproject.toml` deps, run `uv lock` explicitly.
- Tests add `feed_generators/` to `sys.path` themselves; run them from the repo root as above. Full suite runs offline and is fast.
- `feeds-proxy/` (only if you touch it): `cd feeds-proxy && npm ci && npm run typecheck` (Node 24, `tsc --noEmit`). `npm run deploy` is Cloudflare's job, not yours.
- Timeouts: per-generator subprocess timeout is 480s (`FEEDSEEK_GENERATOR_TIMEOUT`); the scheduled job allows 69 min. Local single-feed runs finish in seconds.

## CI checks your PR must pass

- `.github/workflows/mega-linter.yml` (on PR): unittest suite + `validate_feeds.py` + MegaLinter (python flavor). Blocking linters for Python: **ruff** (`E4,E7,E9,F`, line-length 120, target py314 — config `.github/linters/.ruff.toml`), **black** (line-length 120, py314), **isort**, **bandit**. Pylint/mypy findings are non-blocking (disabled-errors). Also markdownlint, yamllint, prettier (YAML), djLint/htmlhint, actionlint, zizmor, TruffleHog. Match black/ruff 120-col style when writing Python. MegaLinter's `APPLY_FIXES` suggestions land in `megalinter-reports/updated_sources` — treat as suggestions, apply only intended fixes. `feeds/`, `cache/`, `feeds-proxy/`, `assets/icons/` are excluded from linting.
- `worker-ci.yml`: only on `feeds-proxy/**` changes — `npm ci && npm run typecheck`.
- `codeql.yml`: actions/JS-TS/Python analysis.
- `update-feeds.yml` is schedule/main-push only; it won't run on your PR.

## Layout (maintained source vs generated output)

- `feed_generators/` — maintained code. One `<name>.py` per feed exposing `main(full: bool)`. Shared helpers to reuse instead of writing local copies: `utils.py` (HTTP `fetch_page`, `load_cache`/`save_cache`, `merge_entries`, `dedupe_entries`, `normalize_link`, `save_atom_feed`, `setup_feed_links`, `add_entry_media`, atomic writes), `models.py` (`FeedConfig`, `load_feed_registry`), `multi_rss.py`, `enrich.py`, `jsonfeed.py`, `media_ext.py`. Orchestration: `run_all_feeds.py`, `invoke_generator.py`, `validate_feeds.py`, `docs_sources.py`, `normalize_feed_self_links.py`.
- `feeds.yaml` — the source registry (name -> script/type/blog_url/enabled). `run_all_feeds.py` discovers generators from it.
- `feeds/` and `cache/` — **generated output, committed but not maintained source.** Never hand-edit; fix the generator and regenerate. A failed/empty fetch must never overwrite last-good output (atomic writes in `utils.py` enforce this; keep it that way). One broken feed must not break others (subprocess isolation in `run_all_feeds.py`).
- `tests/` — unittest files, one per concern (`test_<feed>.py` plus infrastructure tests).
- `site/` — static Pages site + browser reader (`build_site.py`, `make_favicon.py`, `make_opml.py`, `reader.*`, `published_feeds.txt`). `public/` is build output, gitignored.
- `tools/` — manual diagnostics (`check_sources.py`, `check_feed_icons.py`, `restore_cache_archive.py`).
- `docs/` — `architecture.md` (pipeline), `feeds.md` (per-feed notes), `cache.md` (cache/R2 contract), `sources.md` (generated).
- Root: `Makefile` (per-feed targets like `make feeds_reuters`), `pyproject.toml`, `uv.lock`, `README.md`, `README_pl.md`, `AGENTS.md`. Linter configs live in `.github/linters/`.

## Tests that will bite you

`tests/test_registry_docs.py` cross-checks the registry against docs: every `feeds.yaml` entry must have an existing generator script **and** a `feed_<name>.xml` row in the `README.md` table; the feed-count badges in `README.md` and `README_pl.md` plus the `registry-count` marker in `README_pl.md` must all equal the registry size; `site/published_feeds.txt` may only reference registered feeds. Adding/removing a feed means updating all of: `feeds.yaml`, generator script, both READMEs (rows + badges), optionally `site/published_feeds.txt` — then run the test suite and `make validate`.

## Hard rules

- Prefer a usable native RSS/Atom source over a new scraper.
- One maintained source of truth per concern; reuse shared normalization/dedup helpers.
- Feed `rel="self"` URLs derive from `GITHUB_REPOSITORY`; don't hard-code repo URLs (`RSS_REPO_SLUG` overrides locally).
- Never commit secrets. API keys come from env (`OPENWEATHER_API_KEY`, `VISUALCROSSING_API_KEY`, `UNSPLASH_ACCESS_KEY`, `THEYSAIDSO_API_KEY`, `ANYCRAP_API_KEY`); generators must degrade gracefully without them.
- Cloudflare contract is fixed: `feeds-proxy` deploys via Workers Builds (Actions only typechecks it); cache backup is R2 bucket `feedseek-cache`, object `snapshots/cache.tar.gz`. Don't recreate bindings or edit `deploy-cloudflare-pages.yml` (dormant fallback).