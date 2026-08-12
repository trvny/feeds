# Kanarek architecture

Kanarek is one Android application with two main surfaces:

- a news reader and resizable news slideshow widget,
- a background radio/IPTV player and transport-control widget.

The optional Cloudflare Worker accelerates feed parsing and adds discovery, scraping, clean-reader extraction, station search, logo lookup, and synchronized state. The app still parses ordinary RSS/Atom feeds on-device when no backend is configured.

## Components

| Component | Stack |
|---|---|
| App (`app/`) | Kotlin, Jetpack Compose, App Widgets, Media3/ExoPlayer, DataStore, WorkManager, Coil |
| Worker (`worker/`) | TypeScript, Cloudflare Workers, Cache API, optional KV and D1 |

```text
HomeActivity: ReaderScreen <-> PlayerScreen
(swipe pager, bottom navigation, drawer)
          |
          v
NewsRepository ---- on-device fallback: FeedParser (pure Kotlin)
          |
          | GET /?feeds=...       Worker: merge, dedupe, sort
          | <-------------------- JSON / Atom / RSS / JSON Feed
          |                       ETag/304, D1 state, KV/cache
          v
KanarekWidgetProvider

PlayerScreen
          |
          v
PlayerService (ExoPlayer + MediaSession) ---> PlayerWidgetProvider
```

## Design rules

### Backend remains optional

A blank backend URL keeps regular feeds working through the pure-Kotlin `FeedParser`. The Worker is an optimization and a source of additional features, not a hard dependency.

### Failure isolation and last-known-good data

One broken feed or stream must not sink the remaining sources. A transient news refresh failure preserves the previous successful item set instead of blanking the widget.

### Conditional requests

The Worker computes a weak `ETag` from the stable item set, excluding the volatile fetch timestamp. The app returns it through `If-None-Match` and reuses `FeedCache` on `304 Not Modified`.

### Testable codecs

`FeedParser`, `Opml`, `M3uCodec`, `Headlines`, and related codecs contain no Android imports. They are tested directly on the JVM without an emulator.

### RemoteViews constraints

Both widgets use only launcher-safe RemoteViews classes. Widget image loading uses the shared on-disk `WidgetImageCache`; it does not use Coil inside the launcher process.

`WidgetRemoteViewsTest` builds both providers' `RemoteViews` and applies every widget layout under Robolectric. This catches invalid views, resources, formatting, and PendingIntent wiring before a launcher reports an opaque "Can't add widget" failure.

### One playback engine

`PlayerService` owns one ExoPlayer and MediaSession for the app process. The Activity binds to the service, while the player widget sends service actions and receives pushed playback state.

Per-stream `User-Agent` and `Referer` values are stored beside the station and injected through Media3's resolving data source.

### Portable import and export

OPML and M3U/M3U8 operations use Android's Storage Access Framework, so Kanarek does not request broad storage permission.

## Stack and versions

- Kotlin 2.4.10 and Jetpack Compose Material 3
- Android Gradle Plugin 9.3.1 and Gradle 9.6.1
- `compileSdk` 37, `targetSdk` 36, `minSdk` 26
- JVM 17
- Media3 ExoPlayer, HLS, MediaSession, and optional CastPlayer
- DataStore, WorkManager, and Coil
- TypeScript Cloudflare Worker

Versions are centralized in `gradle/libs.versions.toml`. The project uses AGP's built-in Kotlin and modern DSL. It deliberately avoids Hilt and Room.

## Source layout

```text
app/src/main/java/com/kanarek/
  HomeActivity.kt                 main navigation shell
  data/
    NewsItem.kt                   news model
    FeedParser.kt                 RSS/Atom parser
    NewsRepository.kt             fetch, merge, dedupe, sort
    FeedCache.kt                  ETag/body cache
    Headlines.kt                  headline ranking
    Opml.kt                       OPML import/export
    Station.kt                    radio/IPTV station model
    M3uCodec.kt                   M3U/M3U8 codec
    Favicons.kt                   station-logo fallback
    StationDirectory.kt           Radio Browser integration
    StationLogos.kt               iptv-org logo lookup
    SiteSubscribe.kt              feed discovery and scraping
    SettingsStore.kt              DataStore settings
  cast/                           play/foss Cast implementations
  player/
    PlayerService.kt              playback and MediaSession
  ui/
    ReaderScreen.kt               reader and feed management
    PlayerScreen.kt               station library and playback UI
  widget/
    KanarekWidgetProvider.kt      news widget
    NewsRemoteViewsService.kt     news cards
    WidgetRefreshWorker.kt        periodic refresh
    PlayerWidgetProvider.kt       player widget
worker/
  src/index.ts                    Worker routes and feed processing
```

Further reading:

- [Development](DEVELOPMENT.md)
- [Worker and API](WORKER.md)
- [Dependabot alert triage](DEPENDABOT_TRIAGE.md)
- [Project history](HISTORY.md)
