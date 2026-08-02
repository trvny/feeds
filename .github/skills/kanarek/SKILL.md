---
name: kanarek
description: Work on the Kanarek Android news-widget and IPTV/radio-player app or its optional Cloudflare Worker in trvny/feeds/kanarek. Use for widget, Compose, Media3, M3U/OPML, feed parsing, Worker routes, caching, read state, discovery, scraping, deployment, or review tasks. Read the repository contract and the matching reference, then verify current versions, paths, bindings, and workflow commands from source instead of this skill.
license: Complete terms in LICENSE.txt
---

# Kanarek

Kanarek lives under `kanarek/` in the `trvny/feeds` monorepo:

- `app/`: Kotlin/Compose Android app with a news widget and an IPTV/radio
  player, including a player widget;
- `worker/`: optional TypeScript Cloudflare Worker for feed proxying,
  discovery/scraping, and synchronized state features.

Read the root `AGENTS.md` first. Then read only the matching reference:

| Task | Reference |
|---|---|
| Android, widgets, player, codecs, Gradle | `references/android.md` |
| Worker, routes, caching, bindings, deployment | `references/worker.md` |
| Review | `references/review.md` |

Repository files, manifests, version catalogs, Wrangler configuration, and
workflow YAML are the source of truth. Exact dependency versions, resource IDs,
default feeds, routes, and CI commands must not be copied from an old skill
without checking them.

## Stable invariants

- The Worker is optional. A blank backend configuration must keep on-device feed
  parsing functional.
- Both home-screen widgets use RemoteViews-safe layouts and immutable
  `PendingIntent`s.
- A transient feed failure must preserve the news widget's last good items.
- Widget images use the shared widget cache rather than an Activity-only image
  pipeline.
- Playback has one service-owned player. Activities and widgets are clients, not
  owners of additional player instances.
- Per-stream request headers must survive import, editing, persistence, and
  playback.
- Worker source failures are isolated; one broken feed must not sink the merged
  response.
- Conditional requests use a stable item-set ETag and a bodyless `304`; volatile
  fetch timestamps must not invalidate unchanged content.
- Pure feed, OPML, M3U, playlist, and model codecs stay free of Android
  dependencies so JVM tests can exercise them.
- File import/export uses the Storage Access Framework rather than broad storage
  permissions.
- Defaults shared by the app and Worker must stay synchronized when the source
  files show that the same setting is duplicated intentionally.

## Working method

- Inspect current `main`, open PRs, and recent changes before editing.
- Use the authenticated repository tools available in the current environment;
  discover their current names and capabilities rather than following old tool
  names from documentation.
- Keep app and Worker changes separate unless an interface or shared default
  requires both.
- Do not commit credentials, Cloudflare account identifiers, binding IDs, or
  private deployment metadata to instructions or examples.
- Do not bypass Wrangler configuration or the repository deployment workflow
  with a hand-built Cloudflare API deployment. Deploy only when explicitly
  requested and authorized.
- Branch for substantive app or Worker work. Truly trivial documentation fixes
  may follow the repository's direct-to-main rule.

## Validation

Use the commands currently defined by the relevant project and workflows.
Typical narrow checks are:

```bash
cd kanarek
./gradlew testPlayDebugUnitTest
cd worker
npm ci
npm run typecheck
npm test
```

Read the active Android and Worker workflow files before claiming the full CI
matrix. A local edit, connector write, or successful typecheck is not proof of a
successful deployment or device behavior.

## Completion

Report the affected half, changed files, observed tests or CI, commit or PR, and
anything requiring a physical Android device or live Worker verification. Keep
feature documentation current only when a durable user-facing behavior or
project assumption changed.
