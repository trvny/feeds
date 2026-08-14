# Review Feedseek generators

Review the maintained generator, its registry entry, shared helpers, tests, and
representative generated XML. Resolve names through the current `feeds.yaml`;
do not guess filenames or contracts from old instructions.

Prioritize defects that can erase a last-good feed, publish invalid XML, duplicate
reader entries, expose secrets, or abort unrelated sources. If a change is
sound, say so without manufacturing style findings.

## Generator checklist

### Fetch and failure behavior

- Network calls have bounded timeouts and check status/content as appropriate.
- Retries or fallbacks are proportionate and do not hide permanent errors.
- The fetch strategy matches how the permitted source currently exposes data.
- A failed fetch or zero usable entries returns failure and writes no destructive
  feed or cache replacement.
- One malformed item and, for combined feeds, one malformed source are isolated.
- Credentials, cookies, private API responses, and secret values never enter
  logs, feeds, caches, fixtures, or documentation.

### Parsing and normalization

- Selectors or JSON paths are based on observed source structure and are not
  unnecessarily tied to volatile generated classes.
- Dates are parsed with correct timezone meaning.
- Missing optional values remain missing rather than being invented.
- Canonical links are normalized through shared helpers.
- Multi-source generators use shared URL/title deduplication instead of local
  canonicalization that can drift.

### Identity, cache, and ordering

- Entry IDs use the project's stable ID helper rather than a raw mutable link.
- Cache loading, merge, sort, cap, serialization, and full-refresh behavior
  match current shared helpers and comparable generators.
- Re-running unchanged input does not churn IDs, order, or output unnecessarily.
- Cache failure does not turn into silent data loss.

### Feed structure and media

- The generator uses the current shared feed-link and extension helpers.
- Atom or RSS output includes the required feed/channel and entry/item fields.
- Self and alternate links point to the intended feed and source.
- Images, enclosures, publisher/source metadata, and descriptions use supported
  project helpers and remain valid XML.
- Text is escaped and invalid control characters are removed.

### Registry and generated artifacts

- The `feeds.yaml` entry points to an existing script and uses current schema
  fields.
- Any Makefile or generated source-document registration follows current
  conventions rather than an old template.
- Generated feed, cache, and documentation changes are explained by maintained
  source changes and have been inspected individually.

## Output review

Check representative XML for:

- at least one usable item when the source is healthy,
- unique stable IDs and links,
- parseable dates and non-empty titles,
- expected source and media metadata,
- no accidental stale placeholder or debug content,
- no secret or session data.

Use the repository validator for project-specific empty and stale rules instead
of hardcoding thresholds here.

## Validation

From the repository root:

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

Run affected generators when live access is permitted. Cite observed CI on the
final head commit when reviewing a PR. Distinguish live-source verification,
fixture parsing, and static review.

## Findings

For each actionable finding include severity, exact location, impact, and the
smallest fix. End with a brief verdict, checks observed, and anything that could
not be verified because of network, credentials, or source availability.
