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

## CI gates

- `lint.yml`'s `Gate MegaLinter` step fails whenever `has_updated_sources` is `1`. Combined with
  `APPLY_FIXES: all`, that means *any* file a formatter would touch turns the build red, even when
  every linter reports zero errors. Formatting is not advisory here; it gates the build.
- CI never writes formatting back: `APPLY_FIXES_EVENT: none` in `lint.yml`, plus `contents: read` on
  the job, so the token could not push even if MegaLinter tried. Formatting must land in the commit —
  run black, isort and ktlint before pushing, or take the fixed copies from the reports artifact.
- **Never apply `megalinter-reports/updated_sources` wholesale.** In that artifact `README.md` is
  MegaLinter's own project README, banner and OX Security badges included, not this repository's.
  Copying the tree over the working tree destroys the real one. Copy per file and skip `README.md`.
- `.github/linters/.flake8` sets `max-line-length = 120` and delegates E501 to black, but there is no
  black config, so black runs at its default 88. Adding `[tool.black]` would settle which width wins;
  until then the two disagree.

## Code Review Rules

- Respect the `feedseek/` and `kanarek/` boundary; cross-project changes need a clear reason.
- Don't flag formatting in review; CI reports it. Note that CI only *reports* it — see CI gates.
- Flag consequential correctness, security, lifecycle, regressions, data-loss, or compatibility risks.
- Flag changes that can abort the batch, emit invalid RSS/Atom, or churn unchanged entries.
- Preserve normalized URL/title deduplication and per-source failure isolation.
