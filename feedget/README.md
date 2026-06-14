# fidy

A native **Android home-screen widget** that runs a resizable, auto-rotating slideshow of your
news feeds — plus a small companion app to pick the feeds, and an optional Cloudflare Worker that
turns RSS/Atom into clean JSON at the edge. Pull feeds from anywhere; fidy merges, de-dupes, sorts
newest-first, and flips through the stories with images, source, and timestamps. Tap a card to open
the article.

## Features

- **Resizable widget** — `resizeMode="horizontal|vertical"`; drag any corner. Target cell 3×2,
  resizes from 1×1 up to 4×4. Layout scales with the box.
- **Dynamic slideshow** — an `AdapterViewFlipper` auto-advances through fetched headlines
  (launcher auto-advance + self-starting flipper, with fade transitions). A refresh button
  re-pulls on demand.
- **Bring your own feeds** — comma-separated RSS 2.0 / Atom URLs, set in the companion app and
  stored in DataStore. Defaults to Hacker News + The Verge.
- **Optional edge backend** — deploy `worker/` to a Cloudflare Worker and point the app at it; the
  device then pulls pre-parsed JSON from a shared edge cache instead of parsing XML on-device.
- **Rich cards** — article image (`media:content` / `enclosure` / inline `<img>`), source label,
  relative time, headline + summary over a gradient scrim.
- **Resilient** — each feed is isolated (one bad URL can't sink the rest); images are downscaled
  to stay under the RemoteViews binder limit; periodic 30-min background refresh via WorkManager.

## Stack

Kotlin · Jetpack Compose (Material 3, dynamic color) · App Widgets (`AdapterViewFlipper` +
`RemoteViewsService`) · DataStore · WorkManager · Coil. AGP 9.2 / Kotlin 2.4, `compileSdk`/`targetSdk`
35, `minSdk` 26, JVM 17. Worker: TypeScript on Cloudflare Workers. Versions are centralized in
`gradle/libs.versions.toml`. No Hilt/Room — deliberately lean for a single-screen app.

## Layout

```
app/src/main/java/com/fidy/
  MainActivity.kt              companion Compose screen (feeds, backend URL, preview)
  data/
    NewsItem.kt                model
    FeedParser.kt              RSS/Atom parser (pure Kotlin, no Android deps)
    NewsRepository.kt          fetch · merge · dedupe · sort (on-device or via the Worker)
    SettingsStore.kt           DataStore settings (feeds, backend URL, interval)
  widget/
    FidyWidgetProvider.kt      AppWidgetProvider — wires the slideshow, refresh, item taps
    NewsRemoteViewsService.kt  RemoteViewsService + factory — builds the cards, loads images
    WidgetRefreshWorker.kt     periodic background refresh
  ui/theme/                    Compose theme
worker/                        Cloudflare Worker: RSS/Atom → JSON (CORS, edge-cached)
ci/                            CI workflows staged for you to move into .github/workflows/
```

## Build & run (app)

```bash
# Generate the Gradle wrapper jar once (Android Studio does this automatically on import):
gradle wrapper --gradle-version 8.13

./gradlew assembleDebug          # build the debug APK
./gradlew installDebug           # install on a connected device/emulator
```

Then long-press the home screen → Widgets → **fidy**, drop it, and drag a corner to resize.
Open the fidy app to change the feed list.

## Optional: deploy the Worker

```bash
cd worker
npm install
npx wrangler deploy        # prints https://fidy-news.<account>.workers.dev
```

Paste that URL into the app's **Backend URL** field and save. The widget and preview will then pull
from the Worker. Endpoints:

```
GET /?feeds=<url,url,...>&limit=20
  → { "items": [ { "title","link","summary","image","date","source" } ], "count", "fetched" }
GET /health → { "ok": true }
```

Configure `DEFAULT_FEEDS` / `ALLOWED_HOSTS` in `worker/wrangler.jsonc`.

## CI / Actions

The workflow files are in `ci/` (the bot that scaffolded this repo lacked permission to write to
`.github/workflows/`). Activate them with:

```bash
mkdir -p .github/workflows
git mv ci/android-ci.yml ci/worker-ci.yml ci/release.yml .github/workflows/
git rm ci/README.md && git commit -m "Enable CI workflows" && git push
```

- **android-ci.yml** — build + lint, upload the debug APK artifact (push/PR to main).
- **worker-ci.yml** — typecheck the Worker on `worker/**` changes.
- **release.yml** — on a `v*` tag, build the APK and attach it to a GitHub Release.

## Notes

- The Gradle wrapper **jar** isn't committed (binary). CI regenerates it; locally run the
  `gradle wrapper` command above or open in Android Studio.
- Slideshow auto-advance relies on the launcher honoring `autoAdvanceViewId`; most do. The flipper
  also self-starts (`autoStart` + `flipInterval`) as a fallback.
- Written and reviewed but **not compiled here** — run `./gradlew assembleDebug` (or watch CI) to
  confirm the build on your machine.

## License

MIT
