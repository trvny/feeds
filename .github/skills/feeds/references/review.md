# RSS Feed Review (trvny/feeds)




Audit feed generators and their output for correctness, robustness, and project conventions. The generator project is `feedseek/` inside the `trvny/feeds` monorepo; all paths below are under `feedseek/`.

## Instructions

1. **Scope** — all generators by default, or a named one.
2. **Read** the generator(s), their `feedseek/feeds/feed_*.xml`, and `feedseek/feed_generators/utils.py` (the shared helpers everything must reuse).
3. Resolve names via the `script:` field in `feeds.yaml` — filenames vary.
4. **Evaluate** against the checklists. Cite `file_path:line_number` for every finding.
5. If clean, say so briefly.

Context that drives the review: there is **no Selenium** here (don't flag its absence or expect driver handling); feeds are **Atom** by default (`fg.atom_file`); generators run as subprocesses via `run_all_feeds.py` and must expose `main(full=False) -> bool` + a `--full` flag.

## Generator review

### Parsing

- Selectors / JSON paths specific enough to survive minor redesigns, but not so brittle they pin to one generated class?
- Prefer semantic targets (`article`, `h2 a`, `__NEXT_DATA__` keys) over random hashed classnames where possible.
- Per-item parsing wrapped in `try/except` so one bad item is skipped, not fatal.

### Fetch & error handling

- `fetch_page` (or `curl_cffi`) called with a `timeout`; HTTP errors raised/checked.
- Transient failures retried with backoff; alternate source URLs tried before giving up (see `reuters.py`).
- Cloudflare/403 sites use `curl_cffi` with `impersonate="chrome"` and degrade if it's missing.
- **Empty guard**: `main` returns `False` (writing nothing) when fetch fails or zero entries parse — never overwrites the last good feed with an empty one.
- Returns `bool` and the `__main__` block does `sys.exit(0 if main(...) else 1)`.

### Feed links (convention)

Use `utils.setup_feed_links(fg, blog_url, feed_name)`. Flag any generator that sets links by hand. It must yield `rel="self"` **first** (the raw GitHub feed URL, built from the repo slug — never hardcoded) and `rel="alternate"` **last** (the source site). feedgen requires that order.

### Cache & dedupe

- Cache loaded before merge (or bypassed when `full=True`).
- New entries merged + deduped by `link` via `merge_entries`; ordered via `sort_posts_for_feed` (which sorts **ascending** on purpose — feedgen reverses on write, so output is newest-first; when capping to `MAX_ENTRIES`, keep the **tail**).
- Cache written to `cache/<feed_name>_posts.json` via `save_cache`; cached ISO dates restored with `deserialize_entries`.

**Two dedupe layers — don't conflate them:**
- *Cache layer* — `merge_entries` keys on **exact-string `link`** (`id_field`). Fine within one source across runs; useless across sources, where the same story arrives under a different URL.
- *Cross-source layer* — when a generator merges **multiple** sources, exact `link` is not enough. The shared engine is `utils.dedupe_entries` (called by `multi_rss.run()`, and directly by generators that build their own combined list, e.g. `google_blogs.py`): dedupes by **normalized URL OR normalized title**. Route multi-source merges through it — flag any generator that hand-rolls its own canonicalization instead of importing `utils.normalize_link`/`normalize_title`.
- Canonicalization must do **both**: strip tracking params (`utm_*`, `gclid`, `fbclid`, …) **and** normalize scheme→https + drop `www.`/trailing slash/`index.html`. Miss either half and variants of one story survive as dups. `utils.normalize_link` does both in one pass — that's the reference implementation; a generator-local reimplementation is a WARN even if it currently works, since it'll silently diverge on the next edit.

### Strategy fit

Right fetch strategy for how the site serves content: plain `requests`+BeautifulSoup (HTML present), `__NEXT_DATA__`/JSON (SPA), direct JSON API, `curl_cffi` (bot-protected), or news proxy (blocks automation). Flag a heavy HTML scrape where a clean API or embedded JSON exists.

### Entry IDs & media (MRSS)

- `setup_feed_extensions(fg)` called once, before any `fg.add_entry()` — required for the checks below to do anything.
- `<id>` is `make_entry_id(feed_name, link)`, a stable tag URI — **not** the raw link (`fe.id(link)`). This is a real bug, not style: a raw-link id breaks a reader's read/subscribed state whenever the source re-canonicalizes its URLs.
- If the source has a per-item image, it's attached via `add_entry_media(fe, image_url, ...)` — not feedgen's own `fe.enclosure()` (a feedgen 1.0.0 bug silently drops `rel`/`type`/`length` from it).
- If the generator combines multiple sources, per-item provenance is set via `set_entry_source(fe, source)` (`dc:creator`), not left to `<category>` alone.

## XML output review

`validate_feeds.py` accepts both Atom (`<entry>`) and RSS (`<item>`); most feeds here are Atom.

### Structure

- **Atom**: `<feed>` has `<title>`, `<id>`, `<link rel="self">` (raw feed URL) and `<link rel="alternate">` (blog). Each `<entry>` has `<id>`, `<title>`, `<link>`, and `<updated>`/`<published>`.
- **RSS** (if `save_rss_feed` used): `<channel>` has `<title>`/`<link>`/`<description>`; each `<item>` has `<title>`/`<link>`/`<pubDate>`.

### Content

- 0 items → EMPTY (broken parser or a missing guard that let an empty write through).
- Newest item > 60 days → STALE (source dried up or parser silently broke).
- No duplicate `<link>`/`<id>` across entries.
- Dates parse (Atom ISO-8601 / RSS RFC-2822); titles non-empty.

### Encoding

- XML declares `encoding="utf-8"`; control chars stripped (`sanitize_xml`); entities escaped in titles/descriptions.

## Output

Per finding:

```
[SEVERITY] file_path:line_number — description
```

`ERROR` (broken/will fail) · `WARN` (fragile/convention) · `INFO` (suggestion).

End with:

| Feed | Generator | XML | Issues |
|------|-----------|-----|--------|
| name | OK/WARN/ERROR | OK/WARN/ERROR | brief note |
