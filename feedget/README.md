# fidy

A native **Android home-screen widget** that runs a resizable, auto-rotating slideshow of your
news feeds — plus a small companion app to pick the feeds. Pull RSS/Atom from anywhere; fidy
merges, de-dupes, sorts newest-first, and flips through the stories with images, source, and
timestamps. Tap a card to open the article.

## Features

- **Resizable widget** — `resizeMode="horizontal|vertical"`; drag any corner. Target cell 3×2,
  resizes from 1×1 up to 4×4. Layout scales with the box.
- **Dynamic slideshow** — an `AdapterViewFlipper` auto-advances through fetched headlines
  (launcher auto-advance + self-starting flipper, with fade transitions). A refresh button
  re-pulls on demand.
- **Bring your own feeds** — comma-separated RSS 2.0 / Atom URLs, set in the companion app and
  stored in DataStore. Defaults to Hacker News + The Verge.
- **Rich cards** — article image (`media:content` / `enclosure` / inline `<img>`), source label,
  relative time, headline + summary over a gradient scrim.
- **Resilient** — each feed is isolated (one bad URL can't sink the rest); images are downscaled
  to stay under the RemoteViews binder limit; periodic 30-min background refresh via WorkManager.
- **Companion app** — Jetpack Compose (Material 3, dynamic color) to edit feeds and preview the
  current headlines.

## Stack

Kotlin · Jetpack Compose (Material 3) · App Widgets (`AdapterViewFlipper` + `RemoteViewsService`)
· DataStore · WorkManager · Coil. AGP 9.2 / Kotlin 2.4, `compileSdk`/`targetSdk` 35, `minSdk` 26,
JVM 17. Versions are centralized in `gradle/libs.versions.toml`. No Hilt/Room — deliberately lean
for a single-screen app.

## Layout

```
app/src/main/java/com/fidy/
  MainActivity.kt              companion Compose screen (feeds + preview)
  data/
    NewsItem.kt                model
    FeedParser.kt              RSS/Atom parser (pure Kotlin, no Android deps)
    NewsRepository.kt          fetch · merge · dedupe · sort
    SettingsStore.kt           DataStore settings (feeds, interval)
  widget/
    FidyWidgetProvider.kt      AppWidgetProvider — wires the slideshow, refresh, item taps
    NewsRemoteViewsService.kt  RemoteViewsService + factory — builds the cards, loads images
    WidgetRefreshWorker.kt     periodic background refresh
  ui/theme/                    Compose theme
res/
  layout/widget.xml            flipper + empty view + refresh button
  layout/widget_item.xml       one news card
  xml/fidy_widget_info.xml     appwidget-provider (resizeMode, autoAdvance, sizes)
```

## Build & run

```bash
# Generate the Gradle wrapper jar once (Android Studio does this automatically on import):
gradle wrapper --gradle-version 8.13

./gradlew assembleDebug          # build the debug APK
./gradlew installDebug           # install on a connected device/emulator
```

Then long-press the home screen → Widgets → **fidy**, drop it, and drag a corner to resize.
Open the fidy app to change the feed list.

## Notes

- The Gradle wrapper **jar** isn't committed (it's a binary). CI regenerates it; locally run the
  `gradle wrapper` command above or just open the project in Android Studio.
- The CI workflow (`.github/workflows/android-ci.yml`) couldn't be pushed by the bot that scaffolded
  this repo (it lacked the GitHub *workflows* permission). Add it manually — it builds and lints on
  every push/PR.
- Slideshow auto-advance relies on the launcher honoring `autoAdvanceViewId`; most do. The flipper
  also self-starts (`autoStart` + `flipInterval`) as a fallback.
- Written and reviewed but **not compiled here** — run `./gradlew assembleDebug` (or watch CI) to
  confirm the build on your machine.

## License

MIT
