# Coding Conventions

## Core Sections (Required)

### 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Files | `snake_case.py` for Python; hyphenated config/workflow names where conventional | `entry_identity.py`, `update-feeds.yml` | `feed_generators/`, `.github/workflows/` |
| Functions/methods | `snake_case`; private helpers use leading `_` | `normalize_link()`, `_item_date()` | `feed_generators/utils.py`, `feed_generators/multi_rss.py` |
| Types/interfaces | `PascalCase` Python classes | `FeedConfig` | `feed_generators/models.py` |
| Constants/env vars | `UPPER_SNAKE_CASE` | `GENERATOR_TIMEOUT`, `FEEDSEEK_IMAGE_LOOKUPS` | `feed_generators/run_all_feeds.py`, `feed_generators/article_image.py` |

### 2) Formatting and Linting

- Formatter: Black is wired through MegaLinter with line length 120 and target `py314`; isort uses the Black profile with the same line length.
- Linter: Ruff with line length 120 and target `py314`; selected Python rules are `E4`, `E7`, `E9`, `F`, with `E402` ignored.
- Repository-level linting is driven by MegaLinter and configs under `.github/linters/`.
- Run commands: CI via `.github/workflows/mega-linter.yml` is the repository-wide lint/format gate; Ruff can be reproduced with `uv run --locked ruff check --config .github/linters/.ruff.toml <paths>`.

### 3) Import and Module Conventions

- Representative Python modules group standard-library imports before third-party and local imports.
- The project is not installed as a Python package (`tool.uv.package = false`); generator scripts import sibling modules directly.
- Tests that need generator modules add `feed_generators/` to `sys.path`, which is why `E402` is intentionally ignored in the Ruff config.
- No public barrel/export layer is present.

### 4) Error and Logging Conventions

- Source/network failures are normally logged and isolated rather than promoted into unrelated feed failures. Fatal generator status is still surfaced truthfully by the top-level run.
- Shared enrichment treats missing images/resolved links as quality degradation, not an outage, and catches exceptions around those optional paths.
- Logging uses Python `logging` with timestamp, level and message; generator subprocess stdout/stderr is relayed with the feed name by `run_all_feeds.py`.
- Secrets belong in provider/GitHub secret storage and must not be committed to feeds, caches, logs or examples.

### 5) Testing Conventions

- Python tests live in `tests/test_*.py` and use standard-library `unittest` plus `unittest.mock` where external/process behavior needs isolation.
- Reader and Worker tests use Node's built-in `node:test` under component-local `test/` directories.
- Coverage expectation: no coverage tool or threshold is configured in the repository.

### 6) Evidence

- `.github/linters/.ruff.toml`
- `.github/linters/pyproject.toml`
- `.github/linters/.isort.cfg`
- `.github/linters/.mega-linter.yml`
- `.github/workflows/mega-linter.yml`
- `AGENTS.md`
- `feed_generators/run_all_feeds.py`
- `feed_generators/enrich.py`
- `tests/test_run_all_feeds.py`
