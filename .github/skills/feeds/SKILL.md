---
name: feeds
description: Work on the travino/feeds project — add a new self-updating Atom/RSS feed (Python generator under feed_generators/, register in feeds.yaml, Makefile target), fix a broken/EMPTY/stale feed (re-point selectors, JSON paths, or API fields), or review generators and their XML output. Use whenever feeds come up at all — "add a feed", "scrape this site into RSS", "I want to follow this blog in my reader", "feed is broken", "selectors broke", a validate_feeds.py failure, "review feed", "audit feeds", or after creating/modifying a generator. Read the matching reference file before acting.
license: Complete terms in LICENSE.txt
---

# feeds (travino/feeds)

Python generators that turn sites *without* a usable native feed into clean Atom (or RSS) files. A GitHub Actions workflow runs every generator hourly and commits the refreshed `feeds/feed_<name>.xml` and `cache/<name>_posts.json`, so the raw GitHub URLs always serve fresh content.

```
.github/workflows/update-feeds.yml   # hourly: uv sync → run_all_feeds → validate → commit
feeds.yaml                           # registry; pydantic-validated source of truth (script: binds names)
Makefile                             # make feeds / feeds-full / validate / per-feed targets
feed_generators/
  reuters_news.py                    # TEMPLATE (proxy + cache); beatport_top100.py = JS/Cloudflare template
  run_all_feeds.py / models.py / utils.py / validate_feeds.py
feeds/feed_<name>.xml  +  cache/<name>_posts.json   # committed outputs
```

Load-bearing facts: **no Selenium** (JS-heavy sites use `__NEXT_DATA__`/JSON APIs/`curl_cffi` inside a requests-type generator); feeds are **Atom** by default (`fg.atom_file`); every generator exposes `main(full=False) -> bool` + a `--full` flag and is run as a subprocess; **never publish an empty feed** — zero entries → `return False`, write nothing, preserve the last good file.

## Working from claude.ai chat

The repo isn't on disk and `gh`/`make`/`uv` aren't available. Two ways to work:

- **github connector** (`github:get_file_contents`, `github:push_files`) — preferred for targeted edits to a generator, `feeds.yaml`, the `Makefile`, the README.
- **`git clone` in the bash sandbox** to actually run a generator or `validate_feeds.py`. Install deps with `pip install --break-system-packages ...` and invoke scripts directly (`python3 feed_generators/<name>.py --full`) — no `uv`/`make` here. No GitHub auth, so clone works only while the repo is **public**; if private, stay connector-only and verify via the Actions run. Never paste a token into chat.

Replace every `gh ...` call with the connector. After writing, re-read the file and check the Actions run; report the commit SHA/run result.

## Pick the task

| Task | Read |
|---|---|
| Add a feed — probe for a native feed first, pick a fetch strategy, write the generator (full contract + utils.py helpers + templates), register, validate | `references/add-feed.md` |
| Fix a broken feed — fetch the live source, find what the parser stopped matching, minimal edit, verify | `references/fix.md` |
| Review generators and XML output — parsing, error handling, cache/dedupe, feed-link conventions, empty/stale checks | `references/review.md` |

Read the reference fully before editing; the generator contract and conventions there are what keep the repo uniform.
