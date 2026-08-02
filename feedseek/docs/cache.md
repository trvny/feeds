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
