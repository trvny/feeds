# Kanarek development

## Requirements

- Android Studio or command-line Android SDK
- JDK 17
- Gradle 9.7.0
- Node.js and npm for the Worker

Dependency versions live in `gradle/libs.versions.toml`.

The Gradle wrapper JAR is not committed. Android Studio regenerates it when importing the project, or run:

```bash
gradle wrapper --gradle-version 9.7.0
```

## Build and install

Run commands from `kanarek/`:

```bash
./gradlew assembleDebug
./gradlew installPlayDebug
```

`assembleDebug` builds both product flavors:

- `play`: includes the proprietary Google Cast sender SDK,
- `foss`: GMS-free and suitable for F-Droid builds.

Flavor-specific commands include:

```bash
./gradlew assemblePlayDebug
./gradlew assembleFossDebug
./gradlew assembleFossRelease
```

After installation, long-press the Android home screen, open **Widgets**, and add either the Kanarek news widget or the radio/TV player widget.

## Tests

App logic and widget inflation:

```bash
./gradlew testPlayDebugUnitTest
```

Worker typecheck and tests:

```bash
cd worker
npm install
npm run typecheck
npm test
```

The JVM suite covers feed parsing, entity decoding, image precedence, date normalization, OPML round-trips, headline ranking, M3U/M3U8 parsing, per-stream headers, favicon fallback, and widget RemoteViews inflation.

The Worker suite covers feed parsing, conditional ETags, output formats, Radio Browser mapping, iptv-org logo selection, discovery/scraping, and state-related helpers.

## Continuous integration

Repository workflows live in `.github/workflows/` and use `kanarek/` as their working directory where appropriate.

- `android-ci.yml`: builds play and foss debug APKs, runs Android lint and JVM tests.
- `worker-ci.yml`: TypeScript typecheck and Vitest tests for Worker changes.
- `release.yml`: builds signed release APKs from a matching `kanarek-v<versionName>` tag. A manual run publishes `main` and derives the tag from the app version.
- MegaLinter workflow: lint and secret scanning.
- Dependabot workflows: dependency updates and eligible automatic merges.

Android build output should be verified through CI when the local environment cannot provide the required SDK and Gradle setup.

## Android notes

- The player requests notification permission on Android 13+ when needed for notification and lock-screen controls. Playback itself can continue without the visible notification permission.
- Slideshow auto-advance depends partly on launcher support for `autoAdvanceViewId`; the flipper also starts itself as a fallback.
- Widget layouts must contain only RemoteViews-supported classes.
- Widget PendingIntents remain immutable. The news widget uses an activity trampoline for article links.
- Widget images use raw network fetching and the shared `WidgetImageCache`, not Coil.
- A failed news refresh keeps the last successful item set.
- Default feed changes must stay synchronized between the app and the Worker.
- Pure data codecs should remain free of Android imports so they can run in JVM tests.

## Release flavors

The release workflow produces:

- `kanarek-<version>.apk` for the play flavor,
- `kanarek-<version>-foss.apk` for the GMS-free flavor.

`kanarek/app/build.gradle.kts` is the version source of truth. Before a new release, bump `versionName` and increase `versionCode`, then merge that change to `main`. Release tags use `kanarek-v<versionName>`; tag-triggered runs reject mismatches. A manual **Release** workflow run always publishes `main` and creates the tag from `versionName` when needed.

Further reading:

- [Architecture](ARCHITECTURE.md)
- [Worker and API](WORKER.md)
- [Project history](HISTORY.md)
