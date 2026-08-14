# Repair a Feedseek generator

Work under `feedseek/`. A stale or empty feed can mean a parser defect, a fetch
failure, a missing secret, a source outage, or a workflow problem. Diagnose the
layer before editing selectors.

## 1. Establish the failure

- Check the latest `update-feeds` run and final health gate.
- Check whether a new feed/cache commit landed despite a failed job; the
  workflow may publish successful partial updates.
- Run the validator and identify the exact feed and reason.
- Resolve the feed name to its current script through `feeds.yaml`.
- Read the whole generator, shared helpers it uses, and relevant tests.

Do not diagnose freshness from the schedule alone.

## 2. Reproduce the actual fetch

Use the same client, headers, endpoint, and parsing path as the generator. Save a
small representative response or fixture when permitted.

Distinguish:

- transport or DNS failure,
- authentication or quota failure,
- blocked or changed endpoint,
- unexpected status or content type,
- client-rendered page with data moved to structured JSON,
- parser selector or JSON-path drift,
- date normalization or validation failure.

Do not add browser automation or bot-control evasion merely because one HTTP
request fails. Use only fetch methods already supported by the project and
permitted by the source.

## 3. Make the smallest evidence-based fix

- Change the source URL, selector, field mapping, or JSON path that the observed
  response proves is wrong.
- Preserve feed identity, output/cache naming, stable entry IDs, merge behavior,
  and shared helpers unless those are the root cause.
- Keep per-item isolation so one malformed record is skipped.
- Preserve the empty-output guard: a failed or zero-entry run writes neither a
  replacement feed nor destructive cache state.
- For multi-source generators, preserve per-source isolation and shared
  normalization/deduplication.
- Do not rewrite the generator merely because another style looks cleaner.

If the source no longer offers a permitted stable data path, disable or document
the source rather than shipping a fragile workaround as a repair.

## 4. Verify

From the repository root:

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

Run the affected generator directly using the CLI supported by its current
contract. Confirm:

- usable non-empty entries are parsed,
- titles, links, IDs, dates, source, and media are valid,
- one malformed item does not abort the run,
- failure leaves the previous output intact,
- generated XML validates,
- no credentials or private response data enter output or logs.

A local parser fixture proves parsing, not live network access. State which was
verified.

## 5. Deliver

Report the failing layer, observed old and new source shape, minimal maintained
files changed, generated artifacts intentionally refreshed, tests, workflow
result, and any source-access limitation. Avoid a long selector inventory when
one precise root cause explains the fix.
