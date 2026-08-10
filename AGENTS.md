# AGENTS.md

This repository contains two largely independent projects. Identify the target
before going deep:

- `feedseek/` is Python feed production: source parsing, deduplication and
  generated RSS/Atom output.
- `kanarek/` is the Android app: Kotlin/Compose, with an optional Cloudflare
  Worker alongside it.

- Kanarek's Worker is optional. An empty backend configuration must keep
  on-device feed parsing functional.
- `feedseek/feeds/` and `feedseek/cache/` are derived outputs. Fix maintained
  source and regenerate instead of treating generated files as the implementation.
- MegaLinter can expose corrected copies under
  `megalinter-reports/updated_sources`, but CI does not write them back. Apply
  only inspected files or diffs.

## GitHub

When available, use `gptomek[bot]` for GitHub side effects, but open pull
requests as `trvny` so automatic reviews run. Prefer one logical change per PR;
trivial low-risk fixes can go directly to `main`.
