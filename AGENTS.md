# AGENTS.md

This is a monorepo with two separate projects:

- `feedseek/`: Python feed generators and static reader;
- `kanarek/`: Kotlin/Compose Android app and optional Cloudflare Worker.

Keep that boundary clear; cross-project changes should have a concrete reason.

## Before changing anything

- When work could overlap ongoing changes, check `main`, open pull requests, and
  recent commits first.
- Read nearby project documentation and existing implementations before adding
  another generator, parser, screen, or backend path.
- Treat generated feeds, caches, and artifacts as outputs rather than maintained
  source.

## Feedseek

- Python dependencies and commands are managed with `uv` from `feedseek/`.
- Generators live in `feedseek/feed_generators/`.
- Preserve normalized URL/title deduplication, stable entries, and per-source
  failure isolation so one bad source or item does not abort the batch.
- Fix generator behavior in maintained source, then regenerate
  `feedseek/feeds/` or `feedseek/cache/` when needed.
- Validate changes with the existing unit tests and feed validator:

```bash
cd feedseek
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

## Kanarek

- `kanarek/app/` is the Android app; `kanarek/worker/` is the optional Worker.
- A blank backend configuration keeps on-device feed parsing; preserve that
  optional-Worker behavior.
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
- `.github/linters/.mega-linter.yml` enables `APPLY_FIXES: all`, while the
  workflow sets `APPLY_FIXES_EVENT: none` and uses read-only repository
  permissions. CI can produce corrected copies and reports without writing them
  back to the branch.
- The final `Gate MegaLinter` step is the authoritative CI gate for that run.
- Apply useful files from `megalinter-reports/updated_sources` selectively after
  inspecting each diff rather than copying the directory wholesale.
- Python line length is 120 in `feedseek/pyproject.toml` and the Flake8 config;
  keep formatter configuration consistent with that source of truth.

## Review and GitHub workflow

- When available, use `gptomek[bot]` for commits, comments, review replies, and
  reactions. Open pull requests as `trvny` so external automatic reviews are
  triggered.
- Prefer one logical change per pull request. Truly trivial low-risk edits can
  go directly to `main`.
- Let automatic Codex review handle review when available; treat its findings as
  advisory and apply the useful ones directly. Usage-limit or stale bot results
  are not code failures.
- Avoid token-driven self-modifying workflows whose main purpose is patching PR
  branches.
- Merge after relevant checks are green on the final head commit and actionable
  review threads are resolved. Prefer squash merge.
- Keep pull-request descriptions, comments, and changelogs brief.

When reviewing, prioritize consequential correctness, security, lifecycle,
data-loss, compatibility, invalid RSS/Atom output, and unnecessary churn. Leave
pure formatting findings to CI when it already reports them.
