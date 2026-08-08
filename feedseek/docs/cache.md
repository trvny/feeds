# Feedseek cache

Feedseek keeps per-source JSON state in `feedseek/cache`. The scheduled workflow
mirrors that directory to the private Cloudflare R2 bucket `feedseek-cache` as
`snapshots/cache.tar.gz`.

The migration is intentionally staged:

1. The workflow restores a valid R2 snapshot when available.
2. The tracked cache remains the seed and fallback if Cloudflare credentials,
   the bucket, or the snapshot are unavailable.
3. Each run uploads a fresh deterministic archive after generation.
4. Cache files should stop being committed only after a real scheduled run has
   created and restored a valid R2 snapshot.

The existing `CLOUDFLARE_API_TOKEN` must include Workers R2 Storage read/write
access for the account in `CLOUDFLARE_ACCOUNT_ID`. The workflow creates the
bucket on first use when the token permits it.

R2 failures are non-fatal during this first phase. Feed generation and the
repository-backed last-known-good state continue to work unchanged.

## Size is bounded by an entry limit

Nothing capped cache growth until 2026-08-08. Every entry ever seen was kept:
4chan reached **21 109 entries (7.9 MB) to publish a 200-entry feed**, and pap
held entries back to April 2021. The directory was 49.9 MB across 91 files and
82 335 entries, growing every two hours.

`save_cache` now keeps the newest `DEFAULT_CACHE_LIMIT` (2000) entries and drops
the oldest. Entries arrive sorted ascending by date, so this is a tail slice —
but `sort_posts_for_feed` parks dateless entries *after* the dated ones, so they
are split out and always kept rather than displacing recent items.

2000 is deliberately generous. Every accumulator feed is far below it (the
largest, `beatport_top100`, holds 200), so none of them lose published history.
It trims 7 of 91 caches. Pass `limit=` to `save_cache` for a feed that needs a
deeper dedup window, or `limit=None` to opt out entirely.

This also protects the backup: the upload step keeps the *previous* snapshot and
only warns once the cache exceeds `FEEDSEEK_CACHE_MAX_BYTES` (128 MB). Unbounded
growth was on course to disable the R2 backup without failing any run.

## Why the cache is not simply untracked

Removing `feedseek/cache` from git looks obvious — R2 already holds it and the
restore step overwrites the working copy at the start of every run. It was
attempted and abandoned, because the directory turns out to be load-bearing in
three unrelated ways:

1. **Eight generators accumulate history rather than refetching it.**
   `daily_quote` merges today's quote into the cached entries; against an empty
   cache it republishes its 43-entry feed with one entry. The same holds for
   `daily_digest`, `openweather`, `visualcrossing`, `open_meteo`,
   `nexusmods_news` and friends. These are daily snapshots of sources that no
   longer serve the old values, so the truncation is permanent — and it would be
   committed, because `feedseek/feeds/` is tracked.
2. **Local runs have no R2 restore.** `make feeds` and direct generator
   invocations in a fresh clone would hit exactly the case above, and a workflow
   guard cannot protect them.
3. **`validate_feeds._registry_coverage` uses cache presence** to tell a
   brand-new feed (`PENDING`) from a lost artifact (`MISSING`). With no cache
   anywhere, deleting an established feed's XML passes validation.

Any future attempt needs all three addressed first. Capping entry counts, above,
solves the size problem without touching any of them.
