# AGENTS.md

- `feed_generators/`: Python generators and shared feed helpers.
- `feeds.yaml`: source registry.
- `feeds/` and `cache/`: generated output.
- `site/`: static site and reader.
- `feeds-proxy/`: supporting Cloudflare Worker that remains in this repository.

## Repository conventions

- Check `main`, open pull requests and recent changes before overlapping work.
- Prefer a usable native feed before adding a scraper.
- Keep one maintained source of truth per concern and use shared normalization/deduplication helpers instead of local copies.
- Fix maintained sources and regenerate `feeds/` / `cache/` rather than hand-editing generated output.
- One broken source must not prevent unrelated feeds from updating.
- A failed or empty fetch must not replace the last good feed with empty output.
- Keep secrets in provider/GitHub secret storage, never in feeds, caches, logs or examples.
- The Android reader/player lives in `trvny/kanarek`; no app code belongs here. `feeds/` is the single published location — never mirror it under a second path.
- Treat `megalinter-reports/updated_sources` as suggestions: inspect the diff and apply only intended fixes.

## Cloudflare

- `feeds-proxy` is deployed by Cloudflare Workers Builds from `feeds-proxy/`; GitHub Actions only checks it.
- Feedseek's persistent generation-cache backup is the private R2 bucket `feedseek-cache`, object `snapshots/cache.tar.gz`; keep that storage contract stable.
- `.github/workflows/deploy-cloudflare-pages.yml` is dormant direct-upload fallback infrastructure and uses the `feedseek` Pages project name.
- Cloudflare binds all of this by account and numeric repository id, never by slug. A GitHub rename does not break the Builds connection and is never a reason to recreate KV/R2/D1 resources; the `repo_name` shown in the build config is a cached label.

## GitHub

Keep one logical change per pull request. Truly trivial low-risk fixes may go directly to `main`. Merge only when relevant checks are green on the final head and actionable review threads are resolved; prefer squash merge.
