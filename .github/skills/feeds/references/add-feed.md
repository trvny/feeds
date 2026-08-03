# Add a Feedseek source

Work under `feedseek/`. Read root `AGENTS.md`, `feeds.yaml`, the current runner
and models, shared helpers, and at least one generator that uses the same fetch
strategy you need. Do not assume a historically named file is still the
canonical template.

## 1. Prefer a native feed

Before writing a generator, inspect the page's declared RSS/Atom links, common
feed paths, and official API or syndication documentation. Use the repository's
current discovery helper when available.

A native maintained feed is preferable to a scraper. Do not build a generator
merely to repackage an equivalent official feed unless the task requires a
combined or normalized output.

Do not bypass authentication, access controls, paywalls, or explicit technical
restrictions. If the only available path is not permitted or stable, document
that limitation instead of disguising it as a supported source.

## 2. Inspect the current contract

Read:

- `feed_generators/models.py` and `run_all_feeds.py`;
- `feed_generators/utils.py`;
- the relevant tests;
- a recent generator with the closest strategy;
- `feeds.yaml` and the current `Makefile` conventions.

Confirm from source:

- the required callable and CLI behavior,
- output and cache naming,
- registry fields,
- how failures propagate,
- which shared helpers own IDs, links, media, caching, sorting, and
  deduplication.

Do not copy Python-version, schedule, template, or Makefile requirements from
this reference without checking the repository.

## 3. Choose the lightest permitted fetch strategy

Prefer, in order:

1. official RSS/Atom or API;
2. stable server-rendered HTML;
3. embedded structured data supplied with the page;
4. a documented backing endpoint the project is permitted to call;
5. an existing project-supported HTTP client for compatibility with a public
   source.

Avoid browser automation unless the repository deliberately supports it and the
source permits it. Do not add a large runtime dependency for one feed when a
simpler supported source exists.

Record the fields available from the source: title, canonical link, publication
time, description, publisher, and image. Do not manufacture missing values.

## 4. Implement the generator

- Reuse shared HTTP, cache, normalization, entry-ID, media, and feed-link
  helpers.
- Keep parsing per-item isolated so one malformed record can be skipped.
- Normalize dates and preserve timezone meaning.
- Use canonical links and stable project entry IDs.
- Return failure and write nothing when fetching or parsing yields no usable
  entries. Preserve the last good committed output.
- Bound output size and network work consistently with comparable generators.
- For a combined source, use shared URL/title normalization and deduplication.

Add the generator and `feeds.yaml` registry entry together. The repository tests
also require every registered feed to have:

- a matching feed row in `feedseek/README.md`;
- the total feed count updated in both the root `README.md` and `README_pl.md`.

Update those maintained documentation files in the same change. Add a Makefile
target, `site/published_feeds.txt` entry, or `docs_sources.py` registration only
when the current project conventions and intended publication scope require it.

Do not hand-edit generated `feeds/`, `cache/`, or `docs/sources.md` as the
implementation. Regenerate them from maintained sources when the task includes
updated artifacts.

## 5. Validate

From `feedseek/`:

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

Run the new generator directly using the current CLI contract and test both an
ordinary run and any supported full-refresh mode. Inspect the generated XML:

- non-empty valid Atom or RSS;
- stable unique IDs and links;
- parseable dates;
- correct source and media metadata when available;
- no secret, cookie, session, or private response data;
- failure leaves the previous output untouched.

If live access is unavailable, test parsing against a small representative
fixture and state that live generation was not verified.

## 6. Deliver

Use one focused change for one logical source. Report:

- why a generator was needed instead of a native feed,
- fetch strategy and permitted data path,
- maintained files changed,
- generated artifacts intentionally refreshed,
- tests and live-source verification,
- commit or PR and workflow conclusion.
