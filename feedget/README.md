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
- **OPML import/export** — bring a feed list in from any reader (Feedly, Inoreader, …) or hand
  feedy's list back out, via the standard `xmlUrl` outline format. Import merges and de-dupes;
  export names a file you choose. Uses the Storage Access Framework, so no storage permission.
- **Optional edge backend** — deploy `worker/` to a Cloudflare Worker and point the app at it; the
  device then pulls pre-parsed JSON from a shared edge cache instead of parsing XML on-device.
- **Rich cards** — article image (`media:content` / `enclosure` / inline `<img>`), source label,
  relative time, headline + summary over a gradient scrim.
- **Resilient** — each feed is isolated (one bad URL can't sink the rest); images are downscaled
  to stay under the RemoteViews binder limit; periodic 30-min background refresh via WorkManager.

## Stack

Kotlin · Jetpack Compose (Material 3, dynamic color) · App Widgets (`AdapterViewFlipper` +
`RemoteViewsService`) · DataStore · WorkManager · Coil. AGP 9.2 / Kotlin 2.3.10 / Gradle 9.4.1,
`compileSdk` 36 / `targetSdk` 35, `minSdk` 26, JVM 17. Worker: TypeScript on Cloudflare Workers. Versions
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
    Opml.kt                    OPML 2.0 import/export (pure Kotlin, no Android deps)
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
gradle wrapper --gradle-version 9.4.1

./gradlew assembleDebug          # build the debug APK
./gradlew installDebug           # install on a connected device/emulator
```

Then long-press the home screen → Widgets → **feedy**, drop it, and drag a corner to resize.
Open the feedy app to change the feed list, or use **Import OPML** / **Export OPML** to move a
list in or out.

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
GET /health → { "ok": true }
```

Configure `DEFAULT_FEEDS` / `ALLOWED_HOSTS` in `worker/wrangler.jsonc`.

## CI / Actions

Workflows live in `.github/workflows/`:

- **android-ci.yml** — build + lint, upload the debug APK artifact (push/PR to main).
- **worker-ci.yml** — typecheck the Worker on `worker/**` changes.
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
