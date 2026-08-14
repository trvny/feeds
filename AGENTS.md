# AGENTS.md

- `feed_generators/`: Python generators and shared feed helpers.
- `feeds.yaml`: source registry.
- `feeds/` and `cache/`: generated output.
- `site/`: static site and reader.
- `feeds-proxy/`: supporting Cloudflare Worker that remains in this repository.
- `docs/repository-split-overview*.md`: archived overview of the former monorepo layout.

## Repository conventions

- Check `main`, open pull requests and recent changes before overlapping work.
- Prefer a usable native feed before adding a scraper.
- Keep one maintained source of truth per concern and use shared normalization/deduplication helpers instead of local copies.
- Fix maintained sources and regenerate `feeds/` / `cache/` rather than hand-editing generated output.
- One broken source must not prevent unrelated feeds from updating.
- A failed or empty fetch must not replace the last good feed with empty output.
- Keep secrets in provider/GitHub secret storage, never in feeds, caches, logs or examples.
- The Android app and its Worker live in `trvny/kanarek`; nothing about them belongs here any more. `feeds/` is the single published location — do not reintroduce a mirrored copy under another path.
- Treat `megalinter-reports/updated_sources` as suggestions: inspect the diff and apply only intended fixes.

## Cloudflare

- `feeds-proxy` is deployed by Cloudflare Workers Builds from `feeds-proxy/`; GitHub Actions only checks it.
- Feedseek's persistent generation-cache backup is the private R2 bucket `feedseek-cache`, object `snapshots/cache.tar.gz`; keep that storage contract stable across repository renames.
- `.github/workflows/deploy-cloudflare-pages.yml` is dormant direct-upload fallback infrastructure and uses the `feedseek` Pages project name.
- After a GitHub repository rename, verify the Cloudflare Builds repository connection for `feeds-proxy`; do not recreate KV/R2/D1 resources just because a GitHub slug changed.

## GitHub

Keep one logical change per pull request. Truly trivial low-risk fixes may go directly to `main`. Merge only when relevant checks are green on the final head and actionable review threads are resolved; prefer squash merge.
