# Feedseek internals

Feedseek turns native feeds, public APIs and carefully selected web pages into stable RSS/Atom output. The public README stays focused on using the project; implementation details live here.

## Pipeline

```text
feeds.yaml
   │
   ▼
fetch / parse / normalize / deduplicate
   │
   ├──▶ feeds/*.xml + *.json
   ├──▶ cache/                 last-known state
   └──▶ site/                  GitHub Pages + reader
             │
             ▼
     trvny.github.io/feedseek/
```

The defaults are intentionally conservative:

- prefer a usable native RSS/Atom feed before scraping;
- isolate source failures so one broken site does not block unrelated feeds;
- never replace the last good output with an empty result after a failed fetch;
- keep entry identity stable and hash-gate `updated` timestamps so unchanged items do not churn;
- deduplicate by normalized URL/title where sources overlap;
- keep generated `feeds/` and `cache/` data separate from maintained generator code.

## Link and image enrichment

Before a generator writes its feed it can call `enrich_entries()` from `feed_generators/enrich.py`.

- **Links:** Google News wrapper URLs can be resolved to the real article URL while the wrapper remains the stable entry identity.
- **Images:** images already present in feed HTML are reused first; missing images can be filled from article Open Graph metadata.

Both paths are bounded and cache settled hits and misses, so repeated scheduled runs do not keep paying for the same lookup. The runtime knobs retained from the original README are:

- `FEEDSEEK_IMAGE_LOOKUPS=40` and `FEEDSEEK_GNEWS_LOOKUPS=40` cap lookups per feed/run;
- `FEEDSEEK_IMAGE_SECONDS=25` and `FEEDSEEK_GNEWS_SECONDS=25` cap time spent on each enrichment path;
- setting a lookup budget to `0` skips that enrichment path for the run.

## Local usage

Requires [uv](https://docs.astral.sh/uv/) or an equivalent Python environment using `pyproject.toml`.

```bash
make install        # install dependencies
make feeds          # generate all feeds incrementally
make feeds-full     # rebuild from scratch, ignoring the cache
make validate       # validate generated feeds
```

For the direct commands used by the repository checks:

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

In CI, feed `rel="self"` URLs are derived from `GITHUB_REPOSITORY`, so repository renames do not require hard-coded URL edits.

## Adding a feed

1. Create `feed_generators/<name>.py` exposing `main(full: bool)` and writing `feeds/feed_<name>.xml`.
2. Register it in `feeds.yaml`.
3. Reuse shared HTTP, normalization, cache and feed helpers instead of creating local copies.
4. Add the source/feed row to the registry table in `README.md`; tests keep that table aligned with `feeds.yaml`.
5. Update the feed-count badges in both READMEs and the `registry-count` marker in `README_pl.md`; tests compare all three with `feeds.yaml`.
6. Add it to `site/published_feeds.txt` when it should appear on the public site.
7. Optionally add a per-feed Make target when a convenient dedicated or `*_full` command is useful.
8. Run the relevant tests and `make validate`.

`run_all_feeds.py` reads `feeds.yaml`, so the scheduled workflow discovers registered generators automatically.

## Repository layout

```text
.
├── .github/workflows/update-feeds.yml   # generate + validate + publish every 2 h
├── feeds.yaml                           # source registry
├── feed_generators/                     # maintained generators + shared helpers
├── feeds/                               # generated RSS/Atom + JSON output
├── cache/                               # incremental state / last-known data
├── site/                                # GitHub Pages site and reader
├── feeds-proxy/                         # supporting Cloudflare Worker
├── tools/                               # manual diagnostics
└── docs/
    ├── architecture.md                  # this file
    ├── feeds.md                         # per-feed background and trade-offs
    ├── sources.md                       # generated source inventory
    └── cache.md                         # cache behavior and maintenance
```

For source-specific implementation notes see [feeds.md](feeds.md). For the generated source inventory see [sources.md](sources.md), and for cache details see [cache.md](cache.md).
