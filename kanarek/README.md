[![Gradle Badge](https://img.shields.io/badge/Gradle-02303A?logo=gradle&logoColor=fff&style=flat)](https://gradle.org)

<div align="center">

<img src="https://raw.githubusercontent.com/trvny/feeds/refs/heads/main/assets/icons/kanarek.svg" alt="Kanarek" width="96">

# Kanarek

**News slideshow widget + background radio/IPTV player for Android**, with an optional
Cloudflare Worker edge backend.

[![android CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/android-ci.yml?label=android%20CI&logo=android&logoColor=white&color=FFC107&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/android-ci.yml)
[![worker CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/worker-ci.yml?label=worker%20CI&logo=cloudflare&logoColor=white&color=FFC107&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/worker-ci.yml)
[![Kotlin](https://img.shields.io/badge/Kotlin-2.4.0-FFC107?style=flat-square&logo=kotlin&logoColor=white)](gradle/libs.versions.toml)
[![license](https://img.shields.io/github/license/trvny/feeds?color=FFC107&style=flat-square)](../LICENSE)
[![last commit](https://img.shields.io/github/last-commit/trvny/feeds?color=FFC107&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/commits/main)

</div>

---

A native **Android home-screen widget** that runs a resizable, auto-rotating slideshow of your
news feeds — plus a small companion app to pick the feeds, a **background radio/IPTV player** with
its own home-screen widget, and an optional Cloudflare Worker that turns RSS/Atom into clean JSON
at the edge. Pull feeds from anywhere; Kanarek merges, de-dupes, sorts newest-first, and flips
through the stories with images, source, and timestamps. Tap a card to open the article.

## Architecture

| component | stack |
|---|---|
| 📱 App (`app/`) | ![Kotlin](https://img.shields.io/badge/-Kotlin-7F52FF?style=flat-square&logo=kotlin&logoColor=white) ![Compose](https://img.shields.io/badge/-Jetpack%20Compose-4285F4?style=flat-square&logo=jetpackcompose&logoColor=white) ![Media3](https://img.shields.io/badge/-Media3%2FExoPlayer-4285F4?style=flat-square&logo=android&logoColor=white) |
| ☁️ Worker (`worker/`) | ![TypeScript](https://img.shields.io/badge/-TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white) ![Cloudflare Workers](https://img.shields.io/badge/-Workers-F38020?style=flat-square&logo=cloudflareworkers&logoColor=white) ![D1](https://img.shields.io/badge/-D1-F38020?style=flat-square&logo=cloudflare&logoColor=white) ![KV](https://img.shields.io/badge/-KV-F38020?style=flat-square&logo=cloudflare&logoColor=white) |

```text
   HomeActivity — one window: ReaderScreen ⇄ PlayerScreen
   (swipe pager · bottom nav · drawer)
             │
             ▼
   NewsRepository ──── on-device fallback: FeedParser (pure Kotlin)
             │
             │  GET /?feeds=...   ──▶   Worker: merge · dedupe · sort
             │  ◀── JSON or Atom  ──    weak ETag/304, D1 read-state,
             │      weak ETag/304       KV discover/scrape cache,
             ▼                          Cache API edge cache
   KanarekWidgetProvider (home-screen slideshow)
                                        │ fetch
                                        ▼
                          RSS/Atom feeds, IPTV/radio streams

   PlayerScreen (M3U/M3U8 playlists)
             │
             ▼
   PlayerService (ExoPlayer + MediaSession)  ──▶  PlayerWidgetProvider
```

- **On-device fallback** — no backend URL set? `NewsRepository` parses RSS/Atom itself
  (`FeedParser`, pure Kotlin). The Worker is an optimization, not a hard dependency.
- **Per-source isolation** — one dead feed or 403'd stream can't sink the rest; the widget
  keeps the last-known-good set on a transient failure instead of going blank.
- **Conditional GET both ways** — the Worker emits a weak `ETag` over the item set (not the
  volatile `fetched` timestamp); the app sends it back as `If-None-Match` and reuses its cache
  on `304` (`FeedCache`).
- **Pure-Kotlin codecs** — `FeedParser`, `Opml`, `M3uCodec`, `Headlines` have zero Android
  imports, so they're JVM-unit-tested directly (`testDebugUnitTest`), no emulator needed.

## Features

- **Resizable widget** — `resizeMode="horizontal|vertical"`; drag any corner. Target cell 3×2,
  resizes from 1×1 up to 4×4. Layout scales with the box.
- **Dynamic slideshow** — an `AdapterViewFlipper` auto-advances through fetched headlines
  (launcher auto-advance + self-starting flipper, with fade transitions). A refresh button
  re-pulls on demand.
- **Bring your own feeds** — comma-separated RSS 2.0 / Atom URLs, set in the companion app and
  stored in DataStore. Defaults to Google News (PL), Euronews (PL), and Antyweb.
- **Subscribe to sites without RSS** — in the app, tap **Add site (no RSS needed)**, paste a URL,
  and **Find feed**: the Worker first looks for a native RSS/Atom the site doesn't surface in its
  reader UI, and if there's none, scrapes the page into Atom at the edge (`HTMLRewriter`, no
  headless browser — same "no Selenium" rule as the [trvny/feeds](https://github.com/trvny/feeds)
  generators). Either path yields an ordinary feed URL that drops into the list, works on-device or
  via the Worker, and exports to OPML like any other.
- **OPML import/export** — bring a feed list in from any reader (Feedly, Inoreader, …) or hand
  Kanarek's list back out, via the standard `xmlUrl` outline format. Import merges and de-dupes;
  export names a file you choose. Uses the Storage Access Framework, so no storage permission.
- **Optional edge backend** — deploy `worker/` to a Cloudflare Worker and point the app at it; the
  device then pulls pre-parsed JSON from a shared edge cache instead of parsing XML on-device. The
  Worker answers conditional GETs (`ETag` / `If-None-Match` → `304`) and the app sends the stored
  `ETag` back, so a refresh that finds no new stories gets a bodyless 304 and keeps the
  last-known-good cards instead of re-downloading the full payload.
- **Rich cards** — article image (`media:content` / `enclosure` / inline `<img>`), source label,
  relative time, headline + summary over a gradient scrim.
- **Headlines mode** — an optional toggle that narrows the showcase/widget to the hottest stories
  instead of everything. Ranking (`Headlines`, pure-Kotlin, unit-tested) scores each item by
  recency (exponential decay), whether it has an image, a weight for sources you mark as **top**
  (tap the source chips in the app), and **cross-source corroboration** — the same story surfacing
  from several distinct feeds is the strongest signal. Off by default; flip it off any time for the
  full firehose. Favicons fall back to a bundled RSS glyph when neither CDN has an icon.
- **Resilient** — each feed is isolated (one bad URL can't sink the rest); images are downscaled
  to stay under the RemoteViews binder limit; periodic 30-min background refresh via WorkManager.

## Player (radio & TV)

A second page (**Radio i TV** — swipe left from the reader or tap it in the bottom bar; the
**Kanarek — radio & TV player** home-screen widget deep-links straight to it) turns Kanarek into a background player for internet radio and IPTV:

- **M3U/M3U8 playlists** — add stations by hand (name, stream URL, logo, group) or **import** an
  existing `.m3u`/`.m3u8` file; **export** your list back out the same way. `M3uCodec` (pure
  Kotlin, unit-tested, mirrors `Opml`) reads/writes the common `#EXTINF` extension
  (`tvg-logo`, `group-title`) and is also the on-disk encoding — so persistence and import/export
  share one format.
- **Discover stations** — tap the search icon on the player screen to search the community
  [Radio Browser](https://api.radio-browser.info) directory (~50k internet radio stations) instead
  of hand-curating a list. The Worker's `/stations/search` proxies the query, picks a live mirror,
  and caches the result; hits map straight onto `Station` (`group` = first tag) and add with one
  tap, same as any imported station.
- **Channel logos from iptv-org** — imported playlists and bundled seeds often ship a `tvg-id`
  but no `tvg-logo`. On import, Kanarek fills those gaps: `StationLogos` sends the tvg-ids to the
  Worker's `/logos`, which resolves them against the iptv-org channel catalog (best in-use,
  channel-level, PNG/SVG variant). Stations that already carry a logo are left untouched, and a
  failed lookup just leaves the fallback glyph — it never blocks the import.
- **Favicon fallback** — a station with no logo at all (typical for hand-added or Radio
  Browser radios) borrows its stream host's favicon via the Google s2 / DuckDuckGo icon
  services (`Favicons`, pure Kotlin, unit-tested): own logo → Google favicon → DDG favicon →
  bundled glyph, in both the app UI and the player widget.
- **TV vs radio, visibly** — every station row (and the now-playing bar) carries a small
  television or radio glyph for its kind. Once the list actually mixes more than one kind, Radio
  and TV (and Other, for untagged imports) become real **tabs** — each shows only its own list, so
  listening and watching never share a scroll position or blend into one mixed view. Switching to
  a TV channel while browsing the Radio tab jumps you over to TV automatically, so the list on
  screen always matches what's playing. TV gets the video surface, radio stays audio-only.
- **Now playing (ICY)** — internet radios announce the current track in-stream
  (SHOUTcast/Icecast `StreamTitle`); `PlayerService` surfaces it and the now-playing bar shows
  it under the station name (falling back to the group title when the stream is silent about it).
- **Per-stream headers** — some IPTV sources 403 without a specific `User-Agent` and/or `Referer`.
  `M3uCodec` reads those from `#EXTVLCOPT:http-user-agent=` / `#EXTVLCOPT:http-referrer=` lines
  (or the equivalent `user-agent=`/`referrer=` `#EXTINF` attributes) into `Station.userAgent` /
  `Station.referrer`, and `PlayerService` applies them per request via a `ResolvingDataSource` —
  so a mixed playlist can have some stations needing custom headers and others not, all through
  one `ExoPlayer`.
- **Background playback** — one `ExoPlayer` + `MediaSession` (`PlayerService`, Media3) per app
  process, so playback and the system's lock-screen/notification controls survive the Activity.
  Handles both direct audio streams (radio, mp3/aac/icecast) and HLS (`.m3u8` IPTV streams —
  `media3-exoplayer-hls`) via the same playlist.
- **Home-screen widget** — current station's logo + name and play/pause/next/prev, pushed live by
  `PlayerService` (not polled). The widget only ever reads images from the shared on-disk cache
  (`WidgetImageCache`, reused from the news widget); the network fetch runs on a background
  dispatcher in the service and re-pushes the widget once the logo lands.
- Needs the runtime notification permission on Android 13+ to show playback controls in the
  notification/lock screen — Kanarek asks for it the first time you open the player screen.

## Stack

Kotlin · Jetpack Compose (Material 3, dynamic color) · App Widgets (`AdapterViewFlipper` +
`RemoteViewsService`) · Media3 (`ExoPlayer` + `MediaSession`, background radio/IPTV playback) ·
DataStore · WorkManager · Coil. AGP 9.2 / Kotlin 2.4.0 / Gradle 9.6.0, `compileSdk` 37 /
`targetSdk` 36, `minSdk` 26, JVM 17. Worker: TypeScript on Cloudflare Workers. Versions are
centralized in `gradle/libs.versions.toml`. No Hilt/Room — deliberately lean. (AGP 9 enables
built-in Kotlin by default; we opt out with `android.builtInKotlin=false` +
`android.newDsl=false` to keep `kotlin.android` and the Compose compiler plugin pinned to the same
Kotlin version. Migrate to built-in Kotlin before AGP 10.)

## Layout

```text
app/src/main/java/com/kanarek/
  HomeActivity.kt              the one window: nav drawer + bottom bar + swipe pager (reader ⇄ player)
  data/
    NewsItem.kt                model
    FeedParser.kt              RSS/Atom parser (pure Kotlin, no Android deps)
    Headlines.kt               headline ranker (recency · image · top-source · corroboration; pure Kotlin)
    NewsRepository.kt          fetch · merge · dedupe · sort (on-device or via the Worker)
    FeedCache.kt               on-disk ETag/body cache for backend conditional GET
    Opml.kt                    OPML 2.0 import/export (pure Kotlin, no Android deps)
    Station.kt                 radio/IPTV station model (incl. optional per-stream headers + tvg-id)
    M3uCodec.kt                M3U/M3U8 import/export + on-disk encoding (pure Kotlin, no Android deps)
    Favicons.kt                favicon-based logo fallback chain (pure Kotlin, no Android deps)
    StationDirectory.kt        Radio Browser search via the Worker's /stations/search proxy
    StationLogos.kt            fills missing station logos from iptv-org via the Worker's /logos proxy
    SiteSubscribe.kt           "add a site without RSS" — calls the Worker's /discover + /scrape
    SettingsStore.kt           DataStore settings (feeds, backend URL, interval, headlines, top sources, stations)
  player/
    PlayerService.kt           MediaSessionService — ExoPlayer + MediaSession, background playback,
                                per-stream header injection via ResolvingDataSource, ICY now-playing
  ui/
    ReaderScreen.kt            reader page: story list + settings face (feeds, OPML, backend URL)
    PlayerScreen.kt            player page: station list (Radio/TV/Other tabs), add/edit/import/export, now-playing bar
    theme/                      Compose theme
  widget/
    KanarekWidgetProvider.kt      AppWidgetProvider — wires the slideshow, refresh, item taps
    NewsRemoteViewsService.kt  RemoteViewsService + factory — builds the cards, loads images
    WidgetRefreshWorker.kt     periodic background refresh
    PlayerWidgetProvider.kt    AppWidgetProvider — current station + play/pause/next/prev
worker/                        Cloudflare Worker: RSS/Atom → JSON (CORS, edge-cached)
.github/workflows/             CI: android-ci, worker-ci, release (+ lint, claude)
```

## Build & run (app)

```bash
# Generate the Gradle wrapper jar once (Android Studio does this automatically on import):
gradle wrapper --gradle-version 9.6.0

./gradlew assembleDebug          # build the debug APK
./gradlew installDebug           # install on a connected device/emulator
```

Then long-press the home screen → Widgets → **Kanarek**, drop it, and drag a corner to resize.
Open the Kanarek app to change the feed list (gear icon on the reader page), or use **Import
OPML** / **Export OPML** to move a list in or out. For radio/TV, swipe to the **Radio i TV** page
(or tap it in the bottom bar), or add the **Kanarek — radio & TV player** widget separately.

## Tests

Pure-logic unit tests, no device or emulator needed:

```bash
./gradlew testDebugUnitTest      # app: FeedParser + OPML + Headlines + M3U (JVM JUnit)
cd worker && npm install && npm test   # worker: parse/decode/etag/atom (Vitest)
```

`FeedParserTest` / `OpmlTest` / `HeadlinesTest` / `M3uCodecTest` / `FaviconsTest` cover RSS+Atom
parsing, entity decoding, image precedence, date normalization, OPML round-trips, headline ranking
(recency, image, top-source, and cross-source corroboration), M3U/M3U8 parsing + round-trips
(including quoted attributes with embedded commas, and `#EXTVLCOPT` per-stream header lines), and
the favicon logo-fallback chain; the Worker suite exercises the same parser plus the
conditional-GET `ETag` matcher, Atom serializer, the Radio Browser → `Station` field mapping used
by `/stations/search`, and the iptv-org logo ranking behind `/logos`. Both run in CI.

## Optional: deploy the Worker

```bash
cd worker
npm install
npx wrangler deploy        # prints https://kanarek.<account>.workers.dev
```

Paste that URL into the app's **Backend URL** field and save. The widget and preview will then pull
from the Worker. Endpoints:

```text
GET /?feeds=<url,url,...>&limit=20
  → { "items": [ { "title","link","summary","image","date","source" } ], "count", "fetched" }
GET /?feeds=<url,url,...>&format=atom|rss
  → Atom/RSS XML of the same merged, deduped, sorted set  # subscribe to it in any reader
GET /discover?url=<page>
  → { "feeds": [ { "url","title","type" } ], "count" }   # native RSS/Atom the page advertises
GET /scrape?url=<page>[&item=<css>]
  → Atom XML                                              # for pages with no native feed
GET /stations/search?q=<n>&country=<ISO2>&tag=<genre>&limit=30
  → { "stations": [ { "name","streamUrl","logoUrl","groupTitle" } ], "count", "fetched" }
  # proxies the Radio Browser directory (~50k stations); results map onto the app's Station shape
GET /logos?ids=<tvg-id,tvg-id,...>
  → { "logos": { "<tvg-id>": "<url>" }, "fetched" }       # iptv-org channel logos, by tvg-id (max 200)
  # reduces iptv-org's ~7MB logos.json to one best url per channel, cached in KV + Cache API
GET /health → { "ok": true }
```

`format=atom|rss` is purely additive — omit it (or pass `format=json`) and you get the exact same
JSON the app has always consumed. It renders the merged item set via the
[`feed`](https://github.com/jpmonette/feed) package instead of hand-rolled XML, so the combined feed
itself can be dropped into an external reader.

`/discover` reads `<link rel="alternate" type="application/rss+xml|atom+xml">` from the page head and,
only when none are advertised, probes a few common paths (`/feed`, `/rss`, `/atom.xml`, …). `/scrape`
extracts the repeating item block with `HTMLRewriter` (auto-detected, or override with `&item=`) and
emits **Atom** — so a scraped source is just another feed URL, working in both app modes and through
OPML. Both honor `ALLOWED_HOSTS` and reuse the same edge-cache + weak-`ETag`/`304` path as the feed
endpoint.

The list response carries a weak `ETag` computed over the item set (not the per-request `fetched`
timestamp, so identical news yields an identical tag). Send it back as `If-None-Match` and the Worker
replies `304 Not Modified` with no body when nothing changed. `ETag` is CORS-exposed and
`If-None-Match` is allowed, so browser clients benefit too.

Configure `DEFAULT_FEEDS` / `ALLOWED_HOSTS` in `worker/wrangler.jsonc`.

The **Add site (no RSS needed)** flow needs a Worker. If you've set a Backend URL it uses that;
otherwise it falls back to `NewsRepository.DEFAULT_BACKEND` — point that constant at your deployed
Worker (`app/.../data/NewsRepository.kt`). Leaving the app's Backend URL blank keeps normal feeds
parsed on-device while still using the default host only for discover/scrape.

Optionally bind a **KV** namespace (`SCRAPE_KV`, commented in `wrangler.jsonc`) to give `/discover`
and `/scrape` a durable cross-colo cache so a cold edge cache doesn't re-hit origin sites. The Worker
runs fine without it (Cache API only); writes are gated to cache-miss + TTL'd, so it stays well inside
the KV free tier.

## CI / Actions

Workflows live in `.github/workflows/`:

- **android-ci.yml** — build + lint + JVM unit tests (`testDebugUnitTest`), upload the debug APK
  artifact (push/PR to main).
- **worker-ci.yml** — typecheck + Vitest unit tests (`npm test`) on `worker/**` changes.
- **release.yml** — on a `v*` tag, build the APK and attach it to a GitHub Release.
- **super-linter.yml** — lint + secret scan.
- **claude.yml** — Claude Code action (needs an `ANTHROPIC_API_KEY` secret).
- **dependabot** — weekly Gradle / npm / GitHub-Actions updates; minor & patch PRs auto-merge
  once checks pass (`dependabot-automerge.yml`).

## Notes

- The Gradle wrapper **jar** isn't committed (binary). CI installs Gradle (via
  `gradle/actions/setup-gradle`) and regenerates the wrapper; locally run the `gradle wrapper`
  command above or open in Android Studio.
- Slideshow auto-advance relies on the launcher honoring `autoAdvanceViewId`; most do. The flipper
  also self-starts (`autoStart` + `flipInterval`) as a fallback.
- The player's notification/lock-screen controls need `POST_NOTIFICATIONS` granted on Android 13+;
  without it, playback still works, the system just won't show the notification.
- Written and reviewed but **not compiled here** — run `./gradlew assembleDebug` (or watch CI) to
  confirm the build on your machine.
