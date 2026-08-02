# Kanarek Android app

The Android project lives in `kanarek/`. Read the current source tree rather
than relying on a class list copied into this reference.

Before changing Android behavior, inspect:

- `app/src/main/AndroidManifest.xml`;
- the touched widget provider, RemoteViews service, player service, repository,
  codec, and Compose screen;
- `app/src/main/res/layout/` and `app/src/main/res/xml/` for widget changes;
- `gradle/libs.versions.toml`, Gradle build files, and `gradle.properties` for
  toolchain changes;
- `.github/workflows/android-ci.yml` for the current CI command.

## News and player widgets

RemoteViews execute under launcher constraints. Preserve these rules:

- Use only RemoteViews-supported layout classes. Treat lint findings about
  unsupported widget views as runtime risks.
- Use explicit immutable `PendingIntent`s. Keep each player action uniquely
  identifiable so `FLAG_UPDATE_CURRENT` does not collapse controls.
- Keep the news-click trampoline when it is required to turn a fill-in intent
  into a safe browser launch.
- Preserve last-known-good items when a transient refresh fails or returns an
  unusable result. A temporary network failure must not blank a working widget.
- Route widget images through the shared widget cache. Do not introduce an
  Activity-oriented image pipeline into a RemoteViews path without proving it
  works in the widget process.
- Keep refresh work bounded and respect the current battery, network, and
  visibility constraints.

## Player ownership

- Keep one player and media session owned by the playback service.
- Activities and widgets control that service; do not create another player per
  screen or widget.
- Keep the service eligible for foreground media playback and preserve required
  manifest permissions and notification behavior.
- The player widget should receive pushed state rather than polling on a timer.
- Keep unstable Media3 implementation types behind the service boundary.

## Per-stream headers and playlists

User agent and referrer data must survive the full path:

1. M3U parsing,
2. model and persistence,
3. station editing,
4. playlist replacement,
5. request construction in the player.

Preserve stable station identity on re-import. Keep the M3U parser and builder
compatible with formats the project already accepts, and cover round-trips with
JVM tests.

## Pure codecs and file access

Feed, OPML, M3U, playlist, and related model codecs should remain pure Kotlin
where the current tests depend on that property. Do not add Android or Compose
dependencies to a codec merely for convenient I/O.

Use the Storage Access Framework for user-selected import and export. Do not add
broad storage permissions or assume a stable filesystem path.

## Build configuration

The version catalog, Gradle properties, wrapper/workflow configuration, and
module build files are the source of truth. Do not copy exact AGP, Kotlin,
Gradle, SDK, or Media3 versions into skills. When changing one layer, check all
places that intentionally pin or coordinate it.

Preserve the project's current built-in Kotlin and Compose setup unless the task
is an explicit, documented toolchain migration. Keep dependency versions in the
version catalog rather than scattering literals through module files.

Treat the lint baseline as a record of accepted existing findings, not a bin for
new errors. Regenerate it only as part of a reviewed lint change and inspect the
diff.

## Localization and secrets

Keep default and Polish string resources synchronized for user-facing keys.
Backend credentials and private feed configuration remain server-side; the app
must not contain Cloudflare credentials, tokens, or private binding metadata.

## Validation

Use the active CI command from `.github/workflows/android-ci.yml`. At the time of
this reference, the relevant command is:

```bash
cd kanarek
./gradlew assemblePlayDebug assembleFossDebug testPlayDebugUnitTest lintPlayDebug --stacktrace
```

If the workflow changes, follow the workflow rather than this copied command.
Report emulator, launcher, notification, playback, or device-specific behavior
as physically tested or unverified. Do not infer device success from a compile.
