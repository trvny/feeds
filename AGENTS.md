# AGENTS.md

Feedseek is the maintained project in this repository. The old monorepo split is still being completed.

- `feedseek/`: Python feed production, registry, tests, generated RSS/Atom/JSON output and static reader.
- `feeds-proxy/`: supporting Cloudflare Worker.
- `kanarek/`: frozen migration mirror pending Android release/signing cutover only. New Android and Worker development belongs in `trvny/kanarek`; the Worker is no longer maintained or deployed from this repository.

## Repository conventions

- Check `main`, open pull requests and recent changes before overlapping work.
- Prefer a usable native feed before adding a scraper.
- Keep one maintained source of truth per concern and use shared normalization/deduplication helpers instead of local copies.
- `feeds/` and `cache/` are generated output. Fix maintained source and regenerate rather than hand-editing them.
- One broken source must not prevent unrelated feeds from updating.
- A failed or empty fetch must not replace the last good feed with empty output.
- Keep secrets in provider/GitHub secret storage, never in feeds, caches, logs or examples.
- For unavoidable release/signing migration work under `kanarek/`, use `trvny/kanarek` as the source of truth and mirror only what the cutover requires.
- Treat `megalinter-reports/updated_sources` as suggestions: inspect the diff and apply only intended fixes.

## GitHub

Use `gptomek[bot]` for commits, comments, review replies and reactions when available. Open pull requests as `trvny` so automatic reviews run. Treat automated reviews as advisory and apply valid findings directly.

Keep one logical change per pull request. Truly trivial low-risk fixes may go directly to `main`. Merge only when relevant checks are green on the final head and actionable review threads are resolved; prefer squash merge.
