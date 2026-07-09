# Review kanarek (trvny/feeds — `kanarek/` subdir)

Two products in one app: a Kotlin/Compose Android **news widget** and an **IPTV/radio player** (`kanarek/app`, package `com.kanarek`), backed by an optional Cloudflare Worker (`kanarek/worker`, TypeScript) that proxies RSS/Atom → JSON and backs read-state via D1. Review **all touched halves together** and pay special attention to the widgets — most real bugs are RemoteViews crashes or blank-widget regressions that lint and a quick read won't catch.

Walk the invariants below. For each, state pass / fail / not-touched and cite the file. Lead with anything that crashes a widget at runtime or breaks the app↔worker contract; style nits last. Don't claim it compiles — point at CI.

## The load-bearing invariants

**1. RemoteViews allowlist (widget XML).**
`res/layout/widget.xml`, `widget_item.xml`, and `player_widget.xml` may only use views on the RemoteViews allowlist. A bare `View` (e.g. a scrim) crashes at inflation on the home screen — it must be an `ImageView` (`android:src=@drawable/scrim`, same `@id`). Flag any non-allowlisted view (`View`, custom views, most `ViewGroup` subclasses beyond the few permitted). Surfaces as a `lintDebug` `RemoteViewLayout` error; a true runtime risk, not noise.

**2. Immutable PendingIntents in both widgets.**
News item clicks use the `ArticleRedirectActivity` trampoline (explicit fill-in intent → browser). The **player widget** uses `FLAG_IMMUTABLE` broadcast/activity intents with a **unique `data` URI per action+widgetId** (`kanarek-player://<action>/<id>`) so `FLAG_UPDATE_CURRENT` can't collapse them. Flag any implicit+mutable `PendingIntent`, a missing/removed trampoline (news), a mutable flag or a shared `data` URI (player), or a missing `ArticleRedirectActivity` manifest entry.

**3. Keep-last-good (never blank the news widget).**
`NewsRemoteViewsService.onDataSetChanged` must preserve the previous item set on a transient fetch failure rather than clearing to empty. Flag any path that assigns an empty/failed result straight into the served list without a keep-last-good guard.

**4. Widget images: raw HttpURLConnection + shared WidgetImageCache, not Coil.**
Both widgets run in the launcher's process and do **not** use Coil. Image loading goes through the shared `WidgetImageCache` (in-memory `LruCache` over a small on-disk JPEG cache) fed by raw `HttpURLConnection` (the player's logo prefetch writes into the same cache). Flag any Coil/Glide in a widget path, or image loads that bypass `WidgetImageCache`.

**5. One player, two clients.**
Playback is a single `ExoPlayer` + `MediaSession` in `PlayerService` (a `MediaSessionService`, foreground `mediaPlayback`). `PlayerActivity` binds it via a plain same-process `LocalBinder`; the player widget drives it via service actions and the service pushes state back via `PlayerWidgetProvider.updateAll` (`updatePeriodMillis=0`, no polling). Flag a second player instance, a widget that tries to bind the service, a reintroduced poll, or unstable Media3 types leaking out of `PlayerService`'s public surface (the `@UnstableApi` opt-in is file-level on purpose).

**6. Per-stream headers threaded through playback.**
Media3 `MediaItem` has no per-item header field, so `PlayerService` keeps a `streamUrl`-keyed `streamHeaders` map (rebuilt every `setPlaylistInternal`) and a `ResolvingDataSource` over `DefaultHttpDataSource` injects `User-Agent`/`Referer` for streams that need them. `StationEditDialog` save must carry `Station.userAgent`/`referrer` through (gated on unchanged URL) or edits silently drop headers. Flag a dropped resolver, headers not repopulated on playlist change, or an edit path that rebuilds a bare `Station()`.

**7. Conditional GET / ETag stability.**
The Worker emits a **weak** ETag hashed over the item set **only** — the volatile `fetched` timestamp must be excluded. It honors `If-None-Match` with a bodyless `304` (RFC 7232 incl. `*` and weak compare); edge-cache key is the URL only. On device, `FeedCache` stores last-good ETag+body per URL and replays on `304`. Flag a tag that folds in `fetched`, a 304 with a body, or a device path that can't reuse the cached body.

**8. Per-source isolation + scraped == native + D1 optional.**
The Worker fetches each feed under its own guard so one bad source can't sink the response. `/scrape` extracts repeating blocks (`HTMLRewriter`) and **emits Atom**; `/discover` finds native feeds — so scraped/discovered sources flow through the app identically to native. `/state` + `/pair` (D1 `STATE_DB`) must degrade to `503` when the binding is absent, not crash. Flag a bare `Promise.all` without per-source try/catch, a scrape path returning bespoke JSON instead of Atom, or a `/state`/`/pair` path that hard-fails without D1.

**9. Default-feed parity.**
The `DEFAULT_FEEDS` set (currently six: Google News PL, Euronews PL, Antyweb + three feedseek raw feeds) must match between the app's `NewsRepository` defaults and the Worker's `wrangler.jsonc` (mirrored in any deploy metadata). Flag a default added/changed on one side only.

**10. Data codecs stay pure Kotlin.**
`FeedParser.kt`, `Opml.kt`, `SiteSubscribe.kt`, `NewsItem.kt`, `M3uCodec.kt`, `Playlists.kt`, `Station.kt` must have **no Android imports** (`android.*`/`androidx.*`/Compose/`Context`) so they stay JVM-unit-testable (`FeedParserTest`/`OpmlTest`/`M3uCodecTest`/`PlaylistsTest` run as plain unit tests). `M3uCodec` must round-trip UA/referrer through both `#EXTINF` attrs and `#EXTVLCOPT`, and `Station.id` must stay `hash(streamUrl)`. Flag Android deps leaking in, a broken round-trip, or an unstable id.

**11. OPML/M3U/file access via SAF.**
OPML and M3U import/export use the Storage Access Framework (`OpenDocument`/`CreateDocument` contracts) — **no** `READ/WRITE_EXTERNAL_STORAGE`. Flag a storage permission request or direct filesystem path access. (Player perms `FOREGROUND_SERVICE`/`_MEDIA_PLAYBACK`/`POST_NOTIFICATIONS`/`WAKE_LOCK` are expected.)

**12. AGP 9 built-in-Kotlin opt-out + Gradle hygiene.**
`kanarek/gradle.properties` must keep **both** `android.builtInKotlin=false` **and** `android.newDsl=false`; the build applies explicit `kotlin.android` + `org.jetbrains.kotlin.plugin.compose` plugins (AGP 9 does **not** auto-supply the Compose compiler). JDK 17 is the intentional ceiling; `compileSdk 37`; `targetSdk 35` (API-36 Play bump pending, not done); Gradle 9.6.0 across workflows; Media3 `1.10.1`. Versions only via `gradle/libs.versions.toml`. Flag a dropped flag (classic failure is setting only one), a hardcoded version, or a JDK/Gradle/SDK drift.

**13. Lint baseline: warnings grandfathered, errors enforced.**
`app/lint-baseline.xml` grandfathers existing warnings while errors stay failing. Don't disable lint, don't promote real errors into the baseline, regenerate with `:app:updateLintBaseline` (verbatim). Flag a baseline that now swallows a genuine error (e.g. a new `RemoteViewLayout`).

**14. Strings: PL + default parity; secrets server-side.**
User-facing strings live in `res/values/strings.xml` with a `res/values-pl/` translation; flag hardcoded strings or a key in one locale only. Backend/feed config stays in Worker vars/KV/D1; nothing beyond the backend-URL hint ships to the device. Run `github:run_secret_scanning` on changed files; flag any committed key.

## Output

Order findings by blast radius: widget-crash / contract breaks first (1, 2, 3, 5, 6, 7, 8, 12), then correctness (4, 9, 10, 11, 13), then parity/style (14). For each: invariant, pass/fail/not-touched, file:line, and the minimal fix. End with the build signal you can actually cite (CI run + commit SHA) — never a bare "looks correct, compiles."
