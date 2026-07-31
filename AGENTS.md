# Repository

Monorepo:
- `feedseek/`: Python feed generators and static reader.
- `kanarek/`: Android app and Cloudflare Worker.

### feedseek

- Python + `uv`; generators live in `feed_generators/`.
- Do not edit generated feeds or cache unless required.

### kanarek

- `app/`: Kotlin/Compose Android. `worker/`: TypeScript/Cloudflare. Tests: `./gradlew testPlayDebugUnitTest`. `cd worker && npm install && npm test`.
- Keep the Worker optional; blank backend must retain on-device feed parsing.

## Workflow

- Check `main` and open PRs before duplicating work.
- Run the narrow relevant tests; report anything not run.
- Keep PR descriptions and changelogs brief.
- Address actionable Codex review findings before merge.
- Treat Codex as review-only: do not ask it to implement, commit, push, or update PR branches. Apply fixes directly with GitHub tools.
- Do not create token-driven self-modifying workflows to patch PR branches. Use normal commits, validate the final head SHA, and do not treat Codex usage-limit failures or stale bot checks as code failures.

## Code Review Rules

- Respect the `feedseek/` and `kanarek/` boundary; cross-project changes need a clear reason.
- Leave formatting to CI.
- Flag consequential correctness, security, lifecycle, regressions, data-loss, or compatibility risks.
- Flag changes that can abort the batch, emit invalid RSS/Atom, or churn unchanged entries.
- Preserve normalized URL/title deduplication and per-source failure isolation.
