# Review Kanarek

Review the touched app and Worker areas together when a shared contract or
default crosses the boundary. Read the actual diff, nearby implementation,
root `AGENTS.md`, and the relevant Android or Worker reference before judging.

Lead with findings that can crash a widget, break playback, lose user data,
expose secrets, or break the app/Worker contract. Do not fill a template with
style findings merely to look busy.

## Review checklist

Mark each relevant item pass, fail, or not touched and cite the file and line.

### Widgets

- Widget layouts use only RemoteViews-supported classes.
- News and player widget intents are explicit and immutable; player actions stay
  uniquely identifiable.
- News refresh preserves last-known-good items on transient failure.
- Widget image loading goes through the shared widget cache.
- Refresh scheduling remains bounded and respects current constraints.

### Playback

- A single service owns the player and media session.
- Activities and widgets control the service rather than creating another
  player.
- The player widget receives pushed state instead of polling.
- Foreground-service, notification, and media permissions remain coherent.
- Per-stream user-agent/referrer values survive import, editing, persistence,
  playlist replacement, and request resolution.
- Unstable Media3 types do not leak unnecessarily across the service boundary.

### Feed and cache behavior

- Worker sources fail independently; one bad feed cannot abort all results.
- ETags exclude volatile fetch timestamps and unchanged content can produce a
  bodyless `304` that the device can reuse.
- Discovery and scraping remain bounded, host-restricted, and compatible with
  the normal feed path.
- Optional Worker or D1 bindings fail locally without disabling on-device feed
  parsing or unrelated routes.
- App and Worker defaults remain synchronized where the source deliberately
  duplicates them.

### Data and files

- Feed, OPML, M3U, playlist, and related model codecs remain JVM-testable when
  that is an existing design property.
- M3U import/export round-trips supported metadata and stable station identity.
- User file access uses the Storage Access Framework rather than broad storage
  permissions or guessed paths.
- User-facing default and Polish strings stay in parity.

### Build and configuration

- Dependency and toolchain versions come from the current version catalog,
  Gradle files, properties, wrapper, and workflows. Do not compare against
  version numbers copied into old instructions.
- The current built-in Kotlin and Compose setup remains internally consistent.
- New lint errors are fixed rather than hidden in the baseline.
- Worker vars and bindings come from `wrangler.jsonc`; secret values and private
  Cloudflare identifiers are not copied into app code, docs, skills, logs, or
  PR text.
- Deployment changes use the repository's Wrangler configuration and workflow,
  not a reconstructed direct API request.

## Validation and output

Read the active Android and Worker workflow files to identify the real CI
matrix. Cite observed checks on the final head SHA. A local typecheck or green
unit test does not prove launcher, playback, notification, device, or live
Worker behavior.

For each finding include severity, exact location, impact, and the smallest
practical fix. End with:

- verdict,
- checks observed,
- physical or live verification still missing,
- unresolved review threads or repository-rule limitations.
