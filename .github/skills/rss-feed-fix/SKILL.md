---
name: rss-feed-fix
description: Fix a broken feed generator in the travino/feeds project — fetch the live source, find what the parser stopped matching (CSS selectors, the __NEXT_DATA__ JSON path, or an API field), update it, and verify. Use when a feed is EMPTY or stale, after a validate_feeds.py failure, or when asked to "fix feed", "feed is broken", or "selectors broke".
---

# RSS Feed Fix (travino/feeds)

> **In claude.ai chat.** The repo isn't checked out on disk here, and `gh`/`make`/`uv` aren't available as authed tools. Two ways to work:
> - **Read/write via the github connector** (`github:get_file_contents`, `github:create_or_update_file`, `github:push_files`) — preferred for targeted edits to a generator, `feeds.yaml`, the `Makefile`, and the README.
> - **Or `git clone` in the bash sandbox** when you need to actually run a generator or `validate_feeds.py`. Install deps with `pip install --break-system-packages ...` (there's no `uv`/`make` here — invoke the script directly, e.g. `python3 feed_generators/<name>.py --full`). The sandbox can run `git`/`python3`/`curl` but starts empty and **has no GitHub auth** — so the clone only works while the repo is **public** (`git clone https://github.com/travino/feeds`). **If the repo is private**, the connector still works fine; stay connector-only — read files via `github:*`, push, and verify by watching the Actions run rather than running locally. Don't paste a token into the chat to force a clone.
> Replace every `gh ...` call (e.g. `gh workflow run`, `gh api`) with the github connector — `gh` has no token in chat. After writing, verify by re-reading the file and checking the Actions run; report the commit SHA/run result.


A generator stopped producing items. The fetch still works but the **parse** step no longer matches the source. Find the break, make a minimal edit, verify, done.

This repo has **no Selenium** — don't reach for it. If a page now renders client-side, the fix is to switch the fetch to the strategies below, not to spin up a browser.

## Input

The feed name (`reuters`) or script filename (`reuters_news.py`). If neither given, run `uv run feed_generators/validate_feeds.py` and look for `EMPTY`/`STALE` feeds.

## Workflow

### 1. Find the generator

Map name → script via the `script:` field in `feeds.yaml` (don't guess the filename — it varies). Read the whole script. Note `FEED_NAME`, `BLOG_URL`, the fetch function, and the parse function (`parse_feed`, `parse_posts`, `extract_tracks`, …) with every selector / JSON path / field it touches.

### 2. Fetch the live source

Match how the generator fetches. Use `curl`, not WebFetch (which strips class names).

```bash
# Plain page:
curl -s -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137 Safari/537.36" "{BLOG_URL}" -o /tmp/feed_fix_live.html
```

If `curl` 403s but the generator uses `curl_cffi`, reproduce with impersonation instead:

```bash
python3 -c "from curl_cffi import requests as r; open('/tmp/feed_fix_live.html','w').write(r.get('{BLOG_URL}', impersonate='chrome', timeout=30).text)"
```

A near-empty body means the content moved to JavaScript. Don't give up — check for a `<script id="__NEXT_DATA__">` blob or a backing JSON API (see [Fetch strategies](#fetch-strategies)) and re-point the generator at that.

### 3. Diagnose

For an HTML scraper, test each selector against the saved file:

```bash
python3 -c "
from bs4 import BeautifulSoup
soup = BeautifulSoup(open('/tmp/feed_fix_live.html').read(), 'html.parser')
for sel in ['article.foo', 'h2 a', 'time[datetime]']:   # the generator's actual selectors
    print(f'{len(soup.select(sel)):4d}  {sel}')
"
```

Zero matches = broken. Find the replacement by surveying the structure:

```bash
python3 -c "
from collections import Counter
from bs4 import BeautifulSoup
soup = BeautifulSoup(open('/tmp/feed_fix_live.html').read(), 'html.parser')
c = Counter((t.name, ' '.join(t['class'])) for t in soup.find_all(True) if t.get('class'))
for (tag, cls), n in sorted(c.items(), key=lambda x:-x[1])[:30]:
    print(f'{n:4d}  <{tag} class=\"{cls}\">')
"
```

For a `__NEXT_DATA__` generator (e.g. `beatport_top100.py`), the break is usually the JSON walk, not a selector — dump the structure and find where the array moved:

```bash
python3 -c "
import json; from bs4 import BeautifulSoup
soup = BeautifulSoup(open('/tmp/feed_fix_live.html').read(), 'lxml')
data = json.loads(soup.find('script', id='__NEXT_DATA__').string)
print(list(data['props']['pageProps'].keys()))
"
```

For a proxy/API generator (`reuters_news.py`, `daily_digest.py`), the source URL or response shape changed — inspect the raw response.

### 4. Fix

Minimal targeted edits. Change only the selectors / JSON path / field access — leave `FEED_NAME`, `BLOG_URL`, output filename, and all the cache/merge/feed logic untouched. Common scraper replacements:

| Field | Old | Likely new |
|---|---|---|
| wrapper | `article.{class}` | new class on `article`/`div` |
| link | `a[itemprop="url"]` | `h2 a`, `header a`, `a.{class}` |
| description | `meta[itemprop="description"]` | `.summary`, `.excerpt`, `p.{class}` |
| date | `time[datetime]` | usually stable |

### 5. Confirm the empty guard exists

`main()` must skip writing when there's nothing to write, so a broken run never clobbers the last good feed. Pattern (see `reuters_news.py`):

```python
if not new_entries:
    logger.warning("No entries parsed — skipping write to avoid an empty feed")
    return False
```

It belongs **after** parsing/merge and **before** `save_cache` / `save_atom_feed`. Add it if missing.

### 6. Verify

```bash
# Parser against the saved HTML:
python3 -c "
import sys; sys.path.insert(0, 'feed_generators')
from {module} import {parse_fn}
posts = {parse_fn}(open('/tmp/feed_fix_live.html').read())
print(len(posts), 'posts'); [print(' ', p['title'][:60]) for p in posts[:3]]
"

# Full generator (script from feeds.yaml), then validate:
uv run feed_generators/{script}
uv run feed_generators/validate_feeds.py
```

5+ posts and no `EMPTY` for the target = fixed. Still zero? Back to Step 3 — likely client-rendered; switch fetch strategy.

### 7. Report

Short table: each selector/path, old → new. Note any guard added. Confirm validation passes.

## Fetch strategies

When a site moves behind JavaScript or bot protection, re-point the fetch — no browser needed:

- **`__NEXT_DATA__` / embedded JSON** — Next.js/SPA ships its data in a `<script>` blob. Parse the HTML, `json.loads` it, walk it. (`beatport_top100.py`)
- **JSON API** — call the backing endpoint directly. (`daily_digest.py`, `openweather.py`)
- **`curl_cffi`** — Cloudflare/TLS-fingerprint 403s. `requests.get(url, impersonate="chrome")`. (`beatport_top100.py`)
- **News proxy** — site blocks automation entirely; pull via Google News RSS and republish. (`reuters_news.py`)

## Notes

- Never change `FEED_NAME`, `BLOG_URL`, or the output filename — selectors/paths only.
- If the structure changed so much that nothing maps cleanly, stop and report — a rewrite needs sign-off.
- Output is Atom (`fg.atom_file`); the `rel="self"` link is filled from the repo slug automatically — not your concern in a fix.
- `rm /tmp/feed_fix_live.html` when done.
