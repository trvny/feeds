# AGENTS.md

This is a monorepo with two separate projects:

- `feedseek/`: Python feed generators and static reader;
- `kanarek/`: Kotlin/Compose Android app and optional Cloudflare Worker.

Respect that boundary. A cross-project change needs a clear reason.

## Before changing anything

- Check current `main`, open pull requests, and recent changes.
- Read nearby project documentation and existing implementations before adding
  another generator, parser, screen, or backend path.
- Do not assume generated feeds, caches, or artifacts are maintained sources.

## Feedseek

- Python dependencies and commands are managed with `uv` from `feedseek/`.
- Generators live in `feedseek/feed_generators/`.
- Preserve normalized URL/title deduplication, stable entries, and per-source
  failure isolation. One bad source or item must not abort the batch.
- Do not hand-edit `feedseek/feeds/` or `feedseek/cache/` as the implementation
  of a fix. Change the generator and regenerate only when required.
- Validate changes with the existing unit tests and feed validator:

```bash
cd feedseek
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

## Kanarek

- `kanarek/app/` is the Android app; `kanarek/worker/` is the optional Worker.
- A blank backend configuration must retain on-device feed parsing. Do not make
  the Worker mandatory by accident.
- Use the narrow relevant checks:

```bash
cd kanarek
./gradlew testPlayDebugUnitTest
cd worker && npm ci && npm test
```

Consult `kanarek/docs/` and the relevant workflow for broader Android, lint, or
release validation.

## MegaLinter and formatting

- The active workflow is `.github/workflows/mega-linter.yml`.
- `.github/linters/.mega-linter.yml` enables `APPLY_FIXES: all`, but the workflow
  sets `APPLY_FIXES_EVENT: none` and checks out with read-only repository
  permissions. CI may produce corrected copies and reports; it does not write
  them back to the branch.
- The final `Gate MegaLinter` step fails when the MegaLinter step did not
  succeed. Do not rely on old `lint.yml`, `has_updated_sources`, or formatter
  auto-commit behavior.
- Never copy `megalinter-reports/updated_sources` wholesale over the repository.
  Apply relevant files individually and inspect each diff.
- Python line length is 120 in `feedseek/pyproject.toml` and the Flake8 config.
  Do not add a competing root formatter configuration.

## Review and GitHub workflow

- Keep one logical change per pull request. Truly trivial low-risk edits may go
  directly to `main`.
- Treat Codex as review-only. Do not ask it to implement, commit, push, update
  branches, or resolve conflicts. A usage-limit or stale bot result is not a
  code failure.
- Do not create token-driven self-modifying workflows to patch PR branches.
- Merge only after relevant checks are green on the final head commit and
  actionable review threads are resolved. Prefer squash merge.
- Keep pull-request descriptions, comments, and changelogs brief.

When reviewing, prioritize consequential correctness, security, lifecycle,
data-loss, compatibility, invalid RSS/Atom output, and unnecessary churn. Do
not manufacture findings for formatting that CI already reports.
