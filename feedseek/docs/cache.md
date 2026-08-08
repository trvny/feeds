# Feedseek cache

Feedseek keeps per-source JSON state in `feedseek/cache`. The private Cloudflare
R2 bucket `feedseek-cache` holds it as `snapshots/cache.tar.gz`, and that
snapshot is now the store rather than a mirror.

The staged migration is complete:

1. ~~The workflow restores a valid R2 snapshot when available.~~ Done.
2. ~~The tracked cache remains the seed and fallback.~~ Retired — see below.
3. ~~Each run uploads a fresh deterministic archive after generation.~~ Done.
4. ~~Cache files should stop being committed only after a real scheduled run has
   created and restored a valid R2 snapshot.~~ **Condition met and verified on
   2026-08-08**: `snapshots/cache.tar.gz` exists (13.6 MB) and three consecutive
   scheduled runs logged `Restored Feedseek cache from R2.` with no
   `No usable R2 snapshot` or `Cloudflare credentials unavailable` warning.

`feedseek/cache/` is therefore gitignored and no longer committed. It had been
written back every two hours — 88 files per run — while the restore step
replaced it from R2 at the start of the next run anyway, so the commits only
duplicated what R2 already held.

Note that untracking stops the growth but does not shrink the ~196 MB already in
history; that would need a history rewrite, which invalidates every clone.

## If the R2 snapshot cannot be restored, the run now fails

**R2 failures are no longer non-fatal.** That changed together with removing the
seed, and the reason matters: the cache is not merely a speed-up. Eight
generators *accumulate* history instead of refetching it — `daily_quote`,
`daily_digest`, `openweather`, `visualcrossing`, `open_meteo`,
`nexusmods_news` and friends merge today's item into the cached entries. Run
`daily_quote` against an empty cache and its 43-entry feed is republished with
one entry. Those entries are daily snapshots of sources that no longer serve the
old values, so the loss is permanent — and it would be committed, because
`feedseek/feeds/` is still tracked.

So the restore step exits non-zero when it cannot restore, before anything is
generated. Stale feeds during an R2 outage are strictly better than truncated
ones.

To bootstrap an empty bucket, dispatch the workflow with
`allow_empty_cache: true`. That is the only way past the guard, and it does
exactly what the guard prevents, so use it only when the history is expendable.

The cache directory itself never needs to exist in git — `get_cache_dir()`
creates it on demand, as does the restore step.

The existing `CLOUDFLARE_API_TOKEN` must include Workers R2 Storage read/write
access for the account in `CLOUDFLARE_ACCOUNT_ID`. The workflow creates the
bucket on first use when the token permits it.
