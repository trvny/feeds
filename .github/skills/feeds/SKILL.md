---
name: feeds
description: Work on the trvny/feeds monorepo's feed generators (the feedseek/ subdir) — add a new self-updating Atom/RSS feed (Python generator under feedseek/feed_generators/, register in feedseek/feeds.yaml, Makefile target), fix a broken/EMPTY/stale feed (re-point selectors, JSON paths, or API fields), or review generators and their XML output. Use whenever feeds come up at all — "add a feed", "scrape this site into RSS", "I want to follow this blog in my reader", "feed is broken", "selectors broke", a validate_feeds.py failure, "review feed", "audit feeds", or after creating/modifying a generator. Read the matching reference file before acting.
license: Complete terms in LICENSE.txt
---

# feeds (trvny/feeds → feedseek/)

`trvny/feeds` is a **monorepo**. This skill covers `feedseek/` — Python generators that turn sites *without* a usable native feed into clean Atom (or RSS) files. A GitHub Actions workflow runs every generator **every 2 hours** and commits the refreshed `feedseek/feeds/feed_<n>.xml` and `feedseek/cache/<n>_posts.json`; a separate Pages deploy publishes the built site. The raw GitHub URLs always serve fresh content.

```
.github/workflows/            # repo-root; scope to subdirs via working-directory
  update-feeds.yml            # every 2h, cwd feedseek: uv sync -> run_all_feeds -> validate -> commit feeds+cache
  deploy-pages.yml            # after update-feeds: build feedseek/site -> GitHub Pages
feedseek/                     # <- this skill lives here
  feeds.yaml                  # registry; pydantic-validated source of truth (script: binds names)
  Makefile                    # make feeds / feeds-full / validate / per-feed targets
  feed_generators/
    reuters.py           # TEMPLATE (proxy + cache, MRSS + tag-URI id); beatport_top100.py = JS/Cloudflare template
    multi_rss.py             # shared combined-feed pipeline (SOURCES tuples + extra_scrapers -> run())
    utils.py                 # shared helpers: cache, links, dedupe, MRSS/media, entry IDs
    media_ext.py             # feedgen extension: MRSS bits (community/license/embed) + the enclosure workaround
    discover.py              # manual scouting tool: find native feed URLs before writing a generator
    docs_sources.py          # regenerates docs/sources.md from a REGISTRY dict + drift-checks it against feeds.yaml
    run_all_feeds.py / models.py / validate_feeds.py
  feeds/feed_<n>.xml  +  cache/<n>_posts.json   # committed outputs
  docs/sources.md              # generated per-feed source list (docs_sources.py) — don't hand-edit
  site/build_site.py          # static site builder (GitHub Pages)
kanarek/                      # OTHER half of the monorepo -- NOT this skill (see below)
```

Load-bearing facts: **no Selenium** (JS-heavy sites use `__NEXT_DATA__`/JSON APIs/`curl_cffi` inside a requests-type generator); feeds are **Atom** by default (`fg.atom_file`); every generator exposes `main(full=False) -> bool` + a `--full` flag and is run as a subprocess; **never publish an empty feed** — zero entries -> `return False`, write nothing, preserve the last good file; entry `<id>` is a stable **RFC 4151 tag URI** via `utils.make_entry_id(feed_name, link)`, not the raw link — the link can move without a reader losing the entry's read/subscribed state.

## Not this skill: kanarek/

`kanarek/` (formerly `feedget/`) is the Kotlin/Compose Android news-widget-and-IPTV-player app + its Cloudflare Worker (RSS->JSON on the edge, plus read-state/sync). Different stack, different skill: use the **kanarek** skill for anything under `kanarek/` — Android/Kotlin/Gradle work, the Worker (TS), routes, KV/D1, `/discover` `/scrape` `/state` `/pair`, deploys.

Stay in this skill only for the Python feed generators under `feedseek/`.

## Working from claude.ai chat

The repo isn't on disk and `gh`/`make`/`uv` aren't available. Two ways to work:

- **github connector** (`github:get_file_contents`, `github:push_files`) — preferred for targeted edits. Every path is under `feedseek/` now: `feedseek/feed_generators/<name>.py`, `feedseek/feeds.yaml`, `feedseek/Makefile`, `feedseek/README.md`.
- **`git clone` in the bash sandbox** to actually run a generator or `validate_feeds.py`. `cd feedseek` first, install deps with `pip install --break-system-packages ...`, and invoke scripts directly (`python3 feed_generators/<name>.py --full`) — no `uv`/`make` here. No GitHub auth, so clone works only while the repo is **public**; if private, stay connector-only and verify via the Actions run. Never paste a token into chat.

Replace every `gh ...` call with the connector. After writing, re-read the file and check the Actions run; report the commit SHA/run result.

## Pick the task

| Task | Read |
|---|---|
| Add a feed — probe for a native feed first, pick a fetch strategy, write the generator (full contract + utils.py helpers + templates), register, validate | `references/add-feed.md` |
| Fix a broken feed — fetch the live source, find what the parser stopped matching, minimal edit, verify | `references/fix.md` |
| Review generators and XML output — parsing, error handling, cache/dedupe, feed-link conventions, empty/stale checks | `references/review.md` |

Read the reference fully before editing; the generator contract and conventions there are what keep the repo uniform.
