---
name: feeds
description: "Work on Feedseek generators under trvny/feeds/feedseek: add, repair, or review RSS/Atom sources, registry entries, generated output, caching, deduplication, validation, and update workflow behavior. Use for broken, empty, stale, or new feeds. Read the repository contract and matching reference, then verify the current generator contract and workflow from source."
license: Complete terms in LICENSE.txt
---

# Feedseek

This skill covers `feedseek/`, the Python feed-generator half of the
`trvny/feeds` monorepo. It does not cover the Android/Worker project under
`kanarek/`.

Read root `AGENTS.md`, then the matching reference:

| Task | Reference |
|---|---|
| Add a source or generator | `references/add-feed.md` |
| Repair a broken, empty, or stale generator | `references/fix.md` |
| Review generators and output | `references/review.md` |

The current source of truth is:

- `feedseek/feeds.yaml` for registered generators;
- `feedseek/feed_generators/models.py` and `run_all_feeds.py` for the executable
  contract;
- `feedseek/feed_generators/utils.py` for shared cache, link, ID, media, and
  deduplication behavior;
- `feedseek/pyproject.toml`, `uv.lock`, and `Makefile` for commands;
- `.github/workflows/update-feeds.yml` and `mega-linter.yml` for automation;
- current working generators and tests, not a named template remembered by this
  skill.

## Stable invariants

- Discover and prefer a usable native feed before writing a scraper.
- A failed fetch or zero parsed entries must not overwrite the last good feed
  with an empty file.
- One malformed item or source should not abort unrelated items or sources.
- Entry identity must remain stable across runs and harmless URL changes.
- Multi-source feeds use the shared URL/title normalization and deduplication
  helpers instead of local variants.
- Generated files under `feedseek/feeds/`, `feedseek/cache/`, and generated
  documentation are outputs, not the implementation of a fix.
- Secrets remain in workflow or provider secret storage and never enter feeds,
  caches, logs, examples, or skills.

## Working method

- Check current `main`, open PRs, recent changes, and the latest update workflow
  result before diagnosing stale output.
- Use the authenticated repository and web tools available in the current
  environment. Do not assume old connector names, local binaries, or a specific
  sandbox.
- Reproduce the generator's actual fetch method. Inspect live source structure
  or API output before changing selectors or paths.
- Make the smallest source or parser change that explains the failure.
- Do not promise that raw feed URLs are fresh merely because a schedule exists;
  observe the latest successful generation and commit.

## Validation

From `feedseek/`, use the repository environment:

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

Run the affected generator directly and inspect its output when network access
and source terms permit it. The active workflow may publish successful partial
updates and still fail its health gate, so read both the committed diff and the
final job conclusion.

## Completion

Report the source, root cause, changed maintained files, generated outputs if
intentionally refreshed, tests, workflow result, and any live-source limitation.
Keep the change focused; do not mix Feedseek and Kanarek work without a clear
shared reason.
