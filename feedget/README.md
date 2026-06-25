# feedy

A native **Android home-screen widget** that runs a resizable, auto-rotating slideshow of your
news feeds — plus a small companion app to pick the feeds, and an optional Cloudflare Worker that
turns RSS/Atom into clean JSON at the edge. Pull feeds from anywhere; feedy merges, de-dupes, sorts
newest-first, and flips through the stories with images, source, and timestamps. Tap a card to open
the article.

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
  headless browser — same "no Selenium" rule as the [travino/feeds](https://github.com/travino/feeds)
  generators). Either path yields an ordinary feed URL that drops into the list, works on-device or
  via the Worker, and exports to OPML like any other.
- **OPML import/export** — bring a feed list in from any reader (Feedly, Inoreader, …) or hand
  feedy's list back out, via the standard `xmlUrl` outline format. Import merges and de-dupes;
  export names a file you choose. Uses the Storage Access Framework, so no storage permission.
- **Optional edge backend** — deploy `worker/` to a Cloudflare Worker and point the app at it; the
  device then pulls pre-parsed JSON from a shared edge cache instead of parsing XML on-device. The
  Worker answers conditional GETs (`ETag` / `If-None-Match` → `304`) and the app sends the stored
  `ETag` back, so a refresh that finds no new stories gets a bodyless 304 and keeps the
  last-known-good cards instead of re-downloading the full payload.
- **Rich cards** — article image (`media:content` / `enclosure` / inline `<img>`), source label,
  relative time, headline + summary over a gradient scrim.
- **Resilient** — each feed is isolated (one bad URL can't sink the rest); images are downscaled
  to stay under the RemoteViews binder limit; periodic 30-min background refresh via WorkManager.

## Stack

Kotlin · Jetpack Compose (Material 3, dynamic color) · App Widgets (`AdapterViewFlipper` +
`RemoteViewsService`) · DataStore · WorkManager · Coil. AGP 9.2 / Kotlin 2.4.0 / Gradle 9.6.0,
`compileSdk` 37 / `targetSdk` 35, `minSdk` 26, JVM 17. Worker: TypeScript on Cloudflare Workers. Versions
are centralized in `gradle/libs.versions.toml`. No Hilt/Room — deliberately lean for a single-screen
app. (AGP 9 enables built-in Kotlin by default; we opt out with `android.builtInKotlin=false` +
`android.newDsl=false` to keep `kotlin.android` and the Compose compiler plugin pinned to the same
Kotlin version. Migrate to built-in Kotlin before AGP 10.)

## Layout

```
app/src/main/java/com/feedy/
  MainActivity.kt              companion Compose screen (feeds, OPML, backend URL, preview)
  data/
    NewsItem.kt                model
    FeedParser.kt              RSS/Atom parser (pure Kotlin, no Android deps)
    NewsRepository.kt          fetch · merge · dedupe · sort (on-device or via the Worker)
    FeedCache.kt               on-disk ETag/body cache for backend conditional GET
    Opml.kt                    OPML 2.0 import/export (pure Kotlin, no Android deps)
    SiteSubscribe.kt           "add a site without RSS" — calls the Worker's /discover + /scrape
    SettingsStore.kt           DataStore settings (feeds, backend URL, interval)
  widget/
    FeedyWidgetProvider.kt      AppWidgetProvider — wires the slideshow, refresh, item taps
    NewsRemoteViewsService.kt  RemoteViewsService + factory — builds the cards, loads images
    WidgetRefreshWorker.kt     periodic background refresh
  ui/theme/                    Compose theme
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

Then long-press the home screen → Widgets → **feedy**, drop it, and drag a corner to resize.
Open the feedy app to change the feed list, or use **Import OPML** / **Export OPML** to move a
list in or out.

## Tests

Pure-logic unit tests, no device or emulator needed:

```bash
./gradlew testDebugUnitTest      # app: FeedParser + OPML (JVM JUnit)
cd worker && npm install && npm test   # worker: parse/decode/etag/atom (Vitest)
```

`FeedParserTest` / `OpmlTest` cover RSS+Atom parsing, entity decoding, image precedence,
date normalization and OPML round-trips; the Worker suite exercises the same parser plus the
conditional-GET `ETag` matcher and Atom serializer. Both run in CI.

## Optional: deploy the Worker

```bash
cd worker
npm install
npx wrangler deploy        # prints https://feedy-news.<account>.workers.dev
```

Paste that URL into the app's **Backend URL** field and save. The widget and preview will then pull
from the Worker. Endpoints:

```
GET /?feeds=<url,url,...>&limit=20
  → { "items": [ { "title","link","summary","image","date","source" } ], "count", "fetched" }
GET /discover?url=<page>
  → { "feeds": [ { "url","title","type" } ], "count" }   # native RSS/Atom the page advertises
GET /scrape?url=<page>[&item=<css>]
  → Atom XML                                              # for pages with no native feed
GET /health → { "ok": true }
```

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
- Written and reviewed but **not compiled here** — run `./gradlew assembleDebug` (or watch CI) to
  confirm the build on your machine.

## License

[MIT](LICENSE)
