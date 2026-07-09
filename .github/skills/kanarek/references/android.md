# kanarek — Android / app / widgets / player

`kanarek/app`, package `com.kanarek`. Two products: a **news AppWidget** and a **radio/IPTV player** (its own AppWidget + a background `MediaSessionService`). The Compose activities (`MainActivity` = feeds, `PlayerActivity` = stations) are companions. Read this before touching either widget, the player, Compose UI, Gradle, or the lint baseline.

## Architecture map

```
kanarek/app/src/main/java/com/kanarek/
  MainActivity.kt              Compose: feed list, OPML import/export, AddSiteDialog (discover/scrape)
  data/
    NewsItem.kt                pure data class (title, link, image, fetched, …)
    FeedParser.kt              pure-Kotlin RSS/Atom parser (no Android deps; unit-tested)
    NewsRepository.kt          fetch path; backend-or-on-device; sends If-None-Match; holds DEFAULT feeds
    FeedCache.kt               per-URL last-good ETag+body store (cacheDir, SHA-1 key, "etag\nbody")
    Headlines.kt               news list model
    Opml.kt                    pure-Kotlin OPML 2.0 codec (parse xmlUrl / build); unit-tested
    SiteSubscribe.kt           pure-Kotlin helper mirroring Opml for add-by-URL
    Station.kt                 pure data class: a playable stream; id = stable hash of streamUrl;
                               optional userAgent/referrer per-stream headers
    M3uCodec.kt                pure-Kotlin M3U8 parse/build (EXTINF attrs + EXTVLCOPT); unit-tested
    Playlists.kt               pure-Kotlin named-playlist codec (#KANAREK-PLAYLIST:<name> markers)
    SettingsStore.kt           persisted settings (backend URL, feeds, stations, lastStationId)
  widget/
    KanarekWidgetProvider.kt   NEWS AppWidgetProvider; AdapterViewFlipper slideshow
    NewsRemoteViewsService.kt  RemoteViewsFactory; onDataSetChanged = keep-last-good
    PlayerWidgetProvider.kt    PLAYER AppWidgetProvider; transport controls; updatePeriodMillis=0
    WidgetImageCache.kt        LruCache (bytes) over on-disk JPEG cache; raw HttpURLConnection; SHARED
    WidgetRefreshWorker.kt     WorkManager periodic NEWS refresh; setRequiresBatteryNotLow(true)
    ArticleRedirectActivity.kt news PendingIntent trampoline → browser (Android 14+ safe)
  player/
    PlayerService.kt           MediaSessionService: one ExoPlayer + MediaSession for the app
  ui/
    PlayerActivity.kt          Compose station list + playback UI; binds PlayerService (LocalBinder)
  ui/theme/                    Compose theme (Kanarek*)
res/layout/widget.xml, widget_item.xml       news RemoteViews layouts (allowlisted views only)
res/layout/player_widget.xml                 player RemoteViews layout
res/xml/kanarek_widget_info.xml              news AppWidgetProviderInfo
res/xml/player_widget_info.xml               player AppWidgetProviderInfo (updatePeriodMillis=0)
res/values{,-pl,-night}/                     strings (PL+default), themes
app/src/main/assets/playlists/{tv,radio}.m3u8   bundled seed lists (NOT auto-loaded — see below)
app/lint-baseline.xml                         grandfathered warnings
```

Tests (`app/src/test/java/com/kanarek/data/`): `FeedParserTest`, `OpmlTest`, `M3uCodecTest`, `PlaylistsTest`, `HeadlinesTest` — plain JVM unit tests, JUnit 4.

## The news widget rules (where the crashes live)

The widget runs **in the launcher's process via RemoteViews** — most "normal" Android code doesn't apply. Three hard rules:

1. **Allowlisted views only.** `widget.xml`/`widget_item.xml` (and `player_widget.xml`) may use only RemoteViews-approved views. A scrim is an `ImageView src=@drawable/scrim`, never a bare `View` (crashes at inflation; surfaces as a `lintDebug` `RemoteViewLayout` error). No custom views, no arbitrary `ViewGroup`s.
2. **No implicit mutable PendingIntent.** News item clicks go through `ArticleRedirectActivity` (explicit fill-in intent → browser). Never hand a widget an implicit + mutable `PendingIntent` (illegal on Android 14+).
3. **Keep-last-good.** `NewsRemoteViewsService.onDataSetChanged` keeps the previous items on a failed/empty fetch. A blanked news widget on a flaky network is the bug to prevent.

Images: shared `WidgetImageCache` only (no Coil in any widget path). News refresh: `WidgetRefreshWorker` gates on battery/network/visibility — preserve those gates.

## The player rules

The player is **one** `ExoPlayer` + `MediaSession` living in `PlayerService` (a `MediaSessionService`, `foregroundServiceType=mediaPlayback`), so playback and the system media notification/lock-screen controls survive with no Activity. Invariants:

- **Single engine, two clients.** `PlayerActivity` binds the service directly via a plain same-process `LocalBinder` (no MediaController/SessionToken round-trip). The **player widget can't hold a live binder** — it drives playback through service actions (`ACTION_TOGGLE`/`NEXT`/`PREV`), and `PlayerService` pushes state back out via `PlayerWidgetProvider.updateAll`. Don't make the widget bind, and don't spin up a second player.
- **Player-widget PendingIntents are immutable.** `PlayerWidgetProvider` uses `FLAG_IMMUTABLE` broadcast/activity intents with a **unique `data` URI per action+widgetId** (`kanarek-player://<action>/<id>`) so `FLAG_UPDATE_CURRENT` doesn't collapse them. `updatePeriodMillis=0` — the widget never polls; the service pushes. Don't reintroduce a poll or a mutable intent.
- **Per-stream headers via side-table + resolver.** Media3's `MediaItem` has no per-item request-headers field. `PlayerService` keeps a `streamUrl`-keyed `streamHeaders` map, repopulated on every `setPlaylistInternal`, and a `ResolvingDataSource` wrapping `DefaultHttpDataSource` reads it to inject `User-Agent`/`Referer` for streams that need them (geo/hotlink). `Station.userAgent`/`referrer` carry these; keep the resolver wired as the player's `MediaSourceFactory`.
- **`@UnstableApi` opt-in is file-level, deliberately.** `PlayerService` is annotated at the file level, **not** the class — so external references (Activity, widget) don't each need their own opt-in. Keep the service's public surface plain (our own types), don't leak unstable Media3 types out of it.
- **Assets are not auto-seeded.** `assets/playlists/tv.m3u8` + `radio.m3u8` ship but reach the app **only** via manual "Import M3U" (SAF). There's no first-run seeding — don't assume stations exist on a fresh install.
- **Editing a station must preserve its headers.** `StationEditDialog`'s save path must carry `userAgent`/`referrer` through (gated on the URL being unchanged), or a header pinned to a stream is silently dropped on any edit — a real regression (see PR #22).

Codecs `M3uCodec`/`Playlists` stay pure Kotlin (mirror `Opml`): `M3uCodec.parse` reads `tvg-logo`/`group-title`/`user-agent`/`referrer` from `#EXTINF` attrs plus `#EXTVLCOPT:http-user-agent=`/`http-referrer=`(`referer=`) as fallback; `build` serializes **both** forms back out for VLC compatibility; `id = hash(streamUrl)` so re-import never mints a new identity.

## Build / toolchain (do not regress)

- **AGP 9 with built-in Kotlin opted OUT.** `kanarek/gradle.properties` keeps **both** `android.builtInKotlin=false` **and** `android.newDsl=false`. Setting only one is the classic failure (first `kotlin.android` rejected; then "Compose Compiler Gradle plugin is required" — AGP 9 doesn't auto-supply it). The build applies explicit `kotlin.android` + `org.jetbrains.kotlin.plugin.compose` plugins.
- **JDK 17** is the deliberate ceiling (Android compile target), not a lag — don't "upgrade" it.
- **compileSdk 37**; **targetSdk 35** (API-36 Play deadline ~Aug 2026 is a known open item — a bump is pending, not done); **Gradle 9.6.0** pinned across CI (`android-ci`, `release`); Kotlin 2.x; Media3 (exoplayer + exoplayer-hls + session) `1.10.1`.
- **Versions only via `gradle/libs.versions.toml`** (`libs.*`). No hardcoded versions in `app/build.gradle.kts`.
- **Lint baseline**: `app/lint-baseline.xml` grandfathers warnings; errors stay enforced. Regenerate verbatim with `:app:updateLintBaseline`; never hand-edit to silence a real error.
- **Player perms**: `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MEDIA_PLAYBACK`, `POST_NOTIFICATIONS`, `WAKE_LOCK` — expected, don't strip.

## Working in chat

You can't build/run/emulate here. Use the **github connector**; branch, don't commit to `main`; keep paired edits in one commit. The connector **has `workflow` scope** — it can write repo-root `.github/workflows/*.yml` directly. For `create_or_update_file` updates, pass the current **blob** SHA (re-fetch first). Point compile/lint signal at `android-ci.yml` (`lintDebug assembleDebug testDebugUnitTest`) and report the run conclusion + commit SHA — never claim it compiles.

Sandbox note: Android can't be built reliably here (`sdkmanager` hangs; even hand-installed, Gradle OOMs at ~3.9 GB RAM). Treat CI as the build.

Keep `kanarek/README.md` and `kanarek/docs/HISTORY.md` current with any feature change (standing instruction).
