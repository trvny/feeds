# Testing Patterns

## Core Sections (Required)

### 1) Test Stack and Commands

- Primary test framework: Python standard-library `unittest` on CPython >=3.14; Node.js 24 built-in `node:test` for reader/Worker JavaScript.
- Assertion/mocking tools: `unittest.TestCase`, `unittest.mock`, Node `assert/strict`, and explicit `globalThis.fetch` replacement in Worker tests.
- Commands:

```bash
uv run --locked python -m unittest discover -s tests
uv run --locked python -m unittest tests.test_registry_docs
node --test site/test/*.test.js
cd feeds-proxy && npm test
```

No coverage command is configured.

### 2) Test Layout

- Python tests are centralized in `tests/` and named `test_*.py`; the repository currently contains 55 such files.
- Reader tests live under `site/test/`; Worker tests live under `feeds-proxy/test/`; both use `*.test.js`.
- There is no shared Python fixture/bootstrap file. Individual tests adjust `sys.path` or patch dependencies when needed.
- CI runs the complete Python suite before generation in `.github/workflows/update-feeds.yml`; reader and Worker checks have separate path-filtered workflows.

### 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | yes | Normalization, identity, cache behavior, metadata refresh, source parsers | Most tests are deterministic and local |
| Integration | yes, repository-local | Registry-to-README consistency, generated metadata paths, Worker request/response behavior | Uses files and mocked boundaries rather than live third parties |
| E2E | no dedicated suite | Full live-source generation through Pages/Worker | Scheduled production generation is operational validation, not a deterministic E2E test suite |

### 4) Mocking and Isolation Strategy

- Python tests use `unittest.mock` to replace subprocesses, HTTP-facing helpers or module behavior. `test_run_all_feeds.py` patches `subprocess.run` to exercise timeout/failure semantics.
- Worker tests replace `globalThis.fetch` and call the exported `fetch` handler directly with synthetic Requests.
- Reader tests load browser utility code into a `vm` context with mocked `window`, `localStorage` and fetch.
- Generator runtime itself isolates sources in subprocesses, so testable failure semantics mirror production architecture.
- Common failure mode to guard against: a single hung/empty/broken source accidentally blocking the batch or replacing a good artifact. Several tests target those invariants directly.

### 5) Coverage and Quality Signals

- Coverage tool + threshold: none configured.
- Current reported coverage: not measured by repository CI.
- Quality signals: 55 Python test files, dedicated reader/Worker tests, Ruff/MegaLinter and CodeQL workflows, plus feed artifact validation after generation.
- Known gap: not every one of the 98 registered source adapters has a dedicated source-specific test file; shared invariants carry much of the regression protection.
- XML and JSON Feed 1.1 are both publication-gated; source-dependent richness remains intentionally outside the universal validator.

### 6) Evidence

- `tests/test_run_all_feeds.py`
- `tests/test_registry_docs.py`
- `site/test/reader-fetch.test.js`
- `feeds-proxy/test/index.test.js`
- `.github/workflows/update-feeds.yml`
- `.github/workflows/reader-ci.yml`
- `.github/workflows/worker-ci.yml`
- `feed_generators/validate_feeds.py`
