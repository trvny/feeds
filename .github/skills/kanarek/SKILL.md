---
name: kanarek
description: Work on the kanarek app in trvny/feeds (the `kanarek/` subdir) — a Kotlin/Compose Android home-screen news widget AND an IPTV/radio player (package com.kanarek), plus a Cloudflare Worker RSS/Atom-to-JSON proxy + read-state backend. Review a change/PR against the load-bearing invariants, fix the news widget or the player, work on the Worker (routes, KV, D1, discover/scrape, conditional GET), deploy the Worker, change default feeds, add a station/playlist, or do general Android/Kotlin/Compose work. Use whenever kanarek or feedget comes up — "review kanarek", "the widget is blank/stale/crashing", "player won't play", "add a channel/station", "fix the M3U parse", "deploy the worker", any RemoteViews/AppWidget/Media3/ExoPlayer/Compose/Gradle change, /discover /scrape /state /pair work, ETag/304 or per-stream header questions — even when the request just names a file or class. NOT for feedseek/ feed generators (use the feeds skill). Read the matching reference file before acting.
license: Complete terms in LICENSE.txt
---

# kanarek (trvny/feeds — `kanarek/` subdir)

Formerly **feedget/feedy**; rebranded to **kanarek** (PR #23, merged) once it grew from a pure RSS widget into a news reader **plus** an IPTV/radio player. Two products in one app, two halves under the subdir:

- **`app/`** — Kotlin/Jetpack Compose Android app, package `com.kanarek`. It ships **two home-screen AppWidgets**: the **news widget** (`KanarekWidgetProvider`, an `AdapterViewFlipper` RSS/Atom slideshow) and the **player widget** (`PlayerWidgetProvider`, transport controls for the radio/IPTV player). The Compose activities are companions: `MainActivity` = feed management (add/remove, OPML, add-site-by-discovery); `PlayerActivity` = station list + playback UI.
- **`worker/`** — a Cloudflare Worker (`src/index.ts`, TypeScript) that proxies RSS/Atom → JSON at the edge, does `/discover` + `/scrape`, and now also backs per-device read-state/subscriptions/pairing via D1 (`/state`, `/pair`). Optional: the app parses feeds on-device if no backend is set. Deployed at **`kanarek.travny.workers.dev`**.

**Naming.** Fully renamed on `main`: brand, package (`com.kanarek`), classes (`Kanarek*`), the Worker (`kanarek`), the on-disk directory (`kanarek/`), and the D1 database (`kanarek-state`). Only historical prose in `kanarek/docs/HISTORY.md` and old chats/PRs still say `feedget`/`feedy` — treat those as history, not current paths.

It lives **inside the `trvny/feeds` monorepo**. Workflows are at repo-root `.github/workflows/` (`android-ci`, `worker-ci`, `deploy-cloudflare`, `release`, …) and scope to this subdir via `working-directory: kanarek`. The old `trvny/feedy` and `trvny/fidy` repos redirect here; package history is `com.fidy` → `com.feedy` → `com.kanarek`.

The invariants in one breath: **two RemoteViews widgets** (news + player) — widget XML uses only RemoteViews-approved views (no bare `View`; ImageView scrim) and **only immutable PendingIntents** (news uses an `ArticleRedirectActivity` trampoline; the player widget uses `FLAG_IMMUTABLE` broadcast/activity intents with a unique per-action `data` URI) — both are real crashes, not lint noise; **keep-last-good** — a transient news fetch failure preserves the previous items, never blanks the news widget; widget image paths are **raw `HttpURLConnection` + shared `WidgetImageCache`, not Coil** (both widgets share it); **one player for the app** — a single `ExoPlayer` + `MediaSession` in `PlayerService` (a `MediaSessionService`, foreground `mediaPlayback`), the Activity binds via a plain same-process `LocalBinder`, the widget drives it via service actions and the service pushes state back to widgets; **per-stream headers** — Media3 has no per-item header field, so `PlayerService` keeps a `streamUrl`-keyed side-table read by a `ResolvingDataSource` (needed for geo/hotlink streams); **conditional GET** — a weak ETag over the item-set only (excluding the volatile `fetched` timestamp), honored as a 304 on both Worker and device (`FeedCache`); **per-source isolation** in the Worker and scraped sources **emit Atom** so they behave like native feeds; **default-feed parity** between `NewsRepository` and the Worker's `DEFAULT_FEEDS`; data codecs (`FeedParser`, `Opml`, `SiteSubscribe`, `M3uCodec`, `Playlists`) stay **pure Kotlin** (no Android imports, JVM-unit-tested); OPML/M3U I/O via **SAF** (no storage permission); **AGP 9 built-in-Kotlin opt-out** (`android.builtInKotlin=false` **and** `android.newDsl=false`, explicit `kotlin.android` + `compose` plugins, JDK 17 ceiling, compileSdk 37, Gradle 9.6.0); versions only via `gradle/libs.versions.toml`; **lint baseline** grandfathers warnings while errors stay enforced; PL + default string parity; backend/feed config stays in Worker vars/KV/D1, never shipped beyond the backend-URL hint.

## Working from claude.ai chat

The repo isn't on disk and Gradle/`wrangler`/an emulator aren't available — you can't build, run, lint, or render either widget. Two ways to work:

- **github connector** (`github:get_file_contents`, `github:push_files`, `github:create_or_update_file`) — preferred. Read before you write; branch (don't commit to `main`) for app/worker changes; keep paired edits in one commit (e.g. a default-feed change touches both `NewsRepository` and `worker/wrangler.jsonc`). The connector **does have `workflow` scope** (verified June 2026) — it can write repo-root `.github/workflows/*.yml` directly. Run `github:run_secret_scanning` on anything that could carry a key. Blob-SHA, not commit-SHA, for `create_or_update_file` updates; re-fetch before each update.
- **`git clone` in the bash sandbox** for Worker-only checks: `npm --prefix kanarek/worker ci && npx --prefix kanarek/worker tsc --noEmit && npm --prefix kanarek/worker test` (Vitest). Android can't be built here reliably (sandbox `sdkmanager` hangs; even hand-installed, Gradle OOMs at ~3.9 GB). Point Android build signal at CI.

**Deploying the Worker** doesn't need wrangler: bundle `src/index.ts` with `esbuild --bundle --format=esm --platform=neutral --target=es2022 --minify`, base64 it, and `Cloudflare:execute` a multipart PUT to `/accounts/{id}/workers/scripts/kanarek` with bindings in metadata (KV `SCRAPE_KV` = `1534e989ac23449fab8e18abc2bc250d`, D1 `STATE_DB` = `kanarek-state`/`e3de16b1-9c52-4992-aac4-be07eef70cc2`, plus `DEFAULT_FEEDS`/`ALLOWED_HOSTS` vars), then POST `.../subdomain {enabled:true}`. Account `d29db89a330417194726eb69450a4668`, subdomain `travny`.

Never claim it compiles — point build signal at CI (`android-ci.yml`: `lintDebug assembleDebug testDebugUnitTest`; `worker-ci.yml`: `tsc` + Vitest) and report commit SHA + run conclusion. Keep `kanarek/README.md` and `kanarek/docs/HISTORY.md` current with any feature change.

## Pick the task

| Task | Read |
|---|---|
| Review a change/PR against the load-bearing invariants | `references/review.md` |
| News widget or player widget blank/stale/crashing, player playback, Compose/Media3 work, AGP 9 / Gradle, lint baseline, OPML/M3U | `references/android.md` |
| Worker work — routes, KV, D1 (`/state` `/pair`), `/discover` & `/scrape`, conditional GET, default feeds, deploy | `references/worker.md` |

Read the reference fully before editing; the invariants are enforced nowhere else.
