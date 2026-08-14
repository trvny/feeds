---
name: feedseek
description: Work on Feedseek under trvny/feeds/feedseek: add, repair or review RSS/Atom sources, registry entries, generated output, caching, deduplication, validation and update workflow behavior. Use for broken, empty, stale or new feeds. Read the repository contract and matching reference, then verify the current generator contract and workflow from source.
license: MIT
---

# Feedseek

Feedseek is the maintained project in `trvny/feeds`; during the repository split its source still lives under `feedseek/` and will later become the repository root.

Read root `AGENTS.md`, then the matching reference:

| Task | Reference |
|---|---|
| Add a source or generator | `references/add-feed.md` |
| Repair a broken, empty or stale generator | `references/fix.md` |
| Review generators and output | `references/review.md` |

Current sources of truth:

- `feeds.yaml` for registered generators;
- `feed_generators/models.py` and `run_all_feeds.py` for the executable contract;
- `feed_generators/utils.py` for shared cache, link, ID, media and deduplication behavior;
- `pyproject.toml`, `uv.lock` and `Makefile` for commands;
- `.github/workflows/update-feeds.yml` and `mega-linter.yml` for automation;
- current working generators/tests, not a remembered template.

## Stable invariants

- Discover and prefer a usable native feed before writing a scraper.
- A failed fetch or zero parsed entries must not overwrite the last good feed with an empty file.
- One malformed item/source should not abort unrelated items/sources.
- Entry identity remains stable across runs and harmless URL changes.
- Multi-source feeds use shared URL/title normalization and deduplication helpers.
- `feeds/`, `cache/` and generated documentation are outputs, not the implementation of a fix.
- Secrets stay in workflow/provider secret storage.

## Validation

From `feedseek/`:

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

Run the affected generator directly and inspect its output when network access permits. The update workflow may publish successful partial updates and still fail its health gate, so read both the committed diff and final job conclusion.
