# kanarek — historia i stan (import z travino/feedy)

feedget powstał jako samodzielne repo `travino/feedy` (pierwotnie „fidy”) i został
wchłonięty do monorepo `travino/feeds` z zachowaną historią. To skrót najważniejszych
rzeczy — pełna historia commitów żyje po imporcie i w archiwum `travino/feedy`.

Aplikacja (pakiet, nazwa, worker, ikona) przeszła później drugi rebranding: `feedy`/`feedget`
→ **Kanarek** (pakiet `com.feedy` → `com.kanarek`, worker `feedget` → `kanarek`,
patrz najnowszy wpis w „Zrobione" niżej). Katalog monorepo tez przemianowany `feedget/` -> `kanarek/`; pelna migracja infra (D1, worker) - patrz najnowszy wpis.

## Co to jest
Natywny androidowy widget (resizable, auto-rotating slideshow newsów) + companion app
do zarządzania feedami + odtwarzacz radia/IPTV w tle z własnym widżetem + opcjonalny worker TS
na Cloudflare (RSS/Atom → JSON na krawędzi).
Stack: Kotlin/Compose (Material 3), App Widgets (AdapterViewFlipper + RemoteViewsService),
Media3 (ExoPlayer + MediaSession), DataStore, WorkManager, Coil. AGP 9.2 / Kotlin 2.4 / Gradle 9.6,
compileSdk 37 / minSdk 26.

## Zrobione (chronologicznie)
- **Discover stations** (worker `/stations/search` + app): przeszukiwanie katalogu Radio Browser
  (~50k stacji radiowych, keyless, community-maintained) zamiast ręcznego kuratorstwa listy.
  Worker proxy'uje zapytanie przez kilka mirrorów (de1/nl1/at1, fallback po kolei), cachuje wynik
  (Cache API 5 min + opcjonalne KV 6h — katalog zmienia się wolno) i mapuje wiersze Radio Browser
  na kształt `Station` (`name`/`streamUrl`/`logoUrl`/`groupTitle`; `group` = pierwszy tag; wiersze
  bez `url_resolved` są odrzucane — `hidebroken=true` już filtruje martwe strumienie po stronie
  Radio Browser). W apce nowa ikona lupy w `PlayerActivity` otwiera `StationSearchDialog` (szukaj
  po nazwie, wyniki z logo/grupą, "Add" per wynik, "Already added" gdy stream URL już jest na
  liście) — `StationDirectory.kt` odpytuje `/stations/search` (bez fallbacku on-device, katalog
  istnieje tylko za workerem). Czysto addytywne — istniejący import/eksport M3U i ręczne dodawanie
  bez zmian. Testy: `mapRadioBrowserStations` (pure function) w `stations.test.ts`.
- **Fix „Nie można dodać widżetu” (news widget)**: `initialLayout` wskazywał na
  `@layout/widget` — pełny `AdapterViewFlipper` z `autoAdvanceViewId`. Launcher inflatuje
  `initialLayout` we własnym procesie **przed** podpięciem adaptera, a goły collection-view
  z auto-advance część launcherów odrzuca („Nie można dodać”). Nowy lekki placeholder
  `widget_loading.xml` (FrameLayout + TextView, same allowlistowane widoki) jako
  `initialLayout`; prawdziwy flipper i tak leci w `onUpdate` przez `setRemoteAdapter`,
  więc stan związany bez zmian. `previewLayout`/`autoAdvanceViewId` nietknięte.
  Nieweryfikowalne w CI (dodawanie widgetu w launcherze) — jeśli dalej wywala, potrzebny
  logcat + launcher/wersja Androida.
- **Grupowanie playera po `group-title`**: płaska lista stacji w `PlayerActivity` dostaje
  collapsowalne sekcje po `Station.groupTitle` (sticky headers, licznik na sekcję,
  sentinel „Bez grupy”). Sekcjonuje **tylko** gdy jest >1 grupa — radio / ręcznie dodane
  bez grup zostają płaską listą jak dotąd (zero regresji). Sekcje startują **zwinięte**:
  zaimportowany `tv.m3u8` z setkami kanałów otwiera się jako krótka lista nagłówków grup
  zamiast niekończącego się scrolla. Model/`M3uCodec` bez zmian — `groupTitle` już był
  parsowany i round-tripowany; to czysto UI. Pure-Kotlin helper `groupStations` (bez
  Android deps). Follow-up do rozważenia: auto-rozwijanie grupy z aktualnie graną stacją.
- **targetSdk 35 → 36** (API 36 / Android 16): `compileSdk` już był 37, więc bump to
  jeden wiersz w `app/build.gradle.kts`. Delta wnosi tylko predictive-back domyślnie
  włączony (Compose `BackHandler`/`OnBackInvokedCallback` — kompatybilne) i pełne
  usunięcie opt-outu z edge-to-edge; e2e i tak było wymuszone od targetSdk 35, więc
  żadnej roboty z insetami. Domyka deadline Google Play (API 36 ~sierpień 2026).
- Ekran startowy + i18n + seed playlist (UX pierwszego uruchomienia): nowa `HomeActivity`
  jest teraz launcherem — prosty wybór dwóch kafli (Wiadomości / Radio i TV), zamiast
  lądowania od razu w formularzu konfiguracji feedów. `MainActivity` i `PlayerActivity`
  schodzą na `exported=false` (odpalane jawnym intentem z Home). Wszystkie stringi
  `MainActivity` (łącznie z całym AddSiteDialog) wyciągnięte z zahardkodowanego angielskiego
  do `values/` + `values-pl/` — naprawia miks językowy (ekran feedów był EN, player PL).
  Przycisk „Zapisz” dostał Toast potwierdzenia (wcześniej zapisywał po cichu, wyglądał na
  martwy — preview jest pod ekranem). Pusty player pokazuje przyciski „Wczytaj przykładowe
  TV/Radio”, które ładują wbudowane `assets/playlists/{tv,radio}.m3u8` (nadal user-initiated,
  invariant „assets nie są auto-seedowane” trzyma). `adjustResize` dodane do aktywności
  z klawiaturą (edge-to-edge/IME).
- feedget -> kanarek (domkniecie): katalog `feedget/` -> `kanarek/` (ostatni relikt starej
  nazwy) + wszystkie sciezki (workflowy, dependabot, lintery, README). Pelna migracja
  infrastruktury: D1 `feedget-state` -> `kanarek-state` (nowe id, stara baza byla pusta),
  worker redeploy jako `kanarek` (`feedget.travny.workers.dev` -> `kanarek.travny.workers.dev`;
  `DEFAULT_BACKEND` juz wskazywal na kanarka). Po deployu: skasowac stary worker `feedget`
  i baze `feedget-state`. Pakiet `com.kanarek` — juz wczesniej.
- feedy/feedget → Kanarek: pełny rebranding — pakiet `com.feedy`→`com.kanarek`,
  klasy (`FeedyWidgetProvider`→`KanarekWidgetProvider`, `FeedyTheme`→`KanarekTheme`, ...),
  string zasoby, worker `feedget`→`kanarek` (nowy URL `kanarek.travny.workers.dev`),
  nowa ikona (kanarek zamiast domyślnego szablonu Android Studio). Katalog monorepo
  `feedget/` i baza D1 `feedget-state` zostają bez zmian (infrastruktura, nie branding)
- fidy → feedy: pełny rename pakietu/aplikacji/workera (#14)
- Widget + slideshow, companion app, parser RSS/Atom (pure-Kotlin)
- OPML import/export (SAF, bez uprawnień storage) (#21)
- Hardening widgetu: dwupoziomowy cache obrazków (LRU + ~12 MB on-disk),
  battery-not-low constraint, keep-last-good na pustym/błędnym fetchu (#22)
- Conditional GET ETag/304: worker emituje słaby ETag po zbiorze itemów (nie po
  timestampie), app wysyła If-None-Match i reżywa cache na 304 (#23)
- Subscribe-no-RSS: worker /discover (native feed z <link> + sondowanie ścieżek)
  i /scrape (HTMLRewriter, bez headless), w app dialog „Add site (no RSS needed)” (#24)
- lint baseline (grandfather istniejących ostrzeżeń); testy FeedParser/OPML (JUnit)
  + worker parser/etag/atom (Vitest), oba w CI (#28)
- Miniatury + favikony w kartach (Coil w app, raw cache w widgecie), favikon per
  źródło z DDG→Google CDN, RSS-glyph fallback gdy brak ikony; worker /scrape bierze
  og:image/twitter:image i lazy data-src/srcset zamiast śmieciowego pierwszego <img>
- Headlines mode: pure-Kotlin ranker (recency + obrazek + waga top-źródła +
  korroboracja przez podobieństwo tytułów), edytowalna lista top-źródeł w app,
  toggle w app i widget factory; domyślnie OFF (pełny widok). Testy `HeadlinesTest`
- Worker: `/?feeds=...&format=atom|rss` — ta sama scalona lista itemów, tylko
  wyrenderowana przez pakiet `feed` zamiast ręcznie sklejanego XML. Czysto
  addytywne — brak `?format=` (albo `format=json`) to wciąż identyczna
  odpowiedź JSON co zawsze; nie rusza `buildAtom`/`/scrape`.
- Player (radio/IPTV): drugi ekran (`PlayerActivity`) + `Station`/`M3uCodec` (pure-Kotlin,
  mirror Opml, testy `M3uCodecTest`) do importu/eksportu/edycji playlist M3U/M3U8. Odtwarzanie
  w tle przez `PlayerService` (Media3 `MediaSessionService` + `ExoPlayer` + `media3-exoplayer-hls`
  dla strumieni IPTV), z powiadomieniem/kontrolkami na ekranie blokady. Drugi widżet
  (`PlayerWidgetProvider`) pokazuje bieżącą stację + play/pauza/dalej/wstecz, aktualizowany na
  żywo przez serwis (bez pollingu); logo stacji idzie przez współdzielony `WidgetImageCache` —
  fetch sieciowy w tle w serwisie, render w widgecie tylko z cache
- Bundlowany `tv.m3u8` (merge dwóch wklejonych list IPTV, dedup po URL; #20) obok
  istniejącego `radio.m3u8` — ładowane teraz przez przyciski „Wczytaj przykładowe”
  w pustym stanie playera (nie auto-seed); wcześniej jedyna droga to ręczny „Import M3U” przez SAF
- Per-stream headers (#21): `Station.userAgent`/`referrer`, parsowane przez `M3uCodec` z
  atrybutów `user-agent=`/`referrer=` w `#EXTINF` i z linii `#EXTVLCOPT:http-user-agent=`/
  `http-referrer=`. `PlayerService` wpina je do `ExoPlayer` przez `ResolvingDataSource`
  (nagłówki dobierane just-in-time per URL) — bez tego 11 strumieni z bundlowanego `tv.m3u8`
  (TVP1/TVP2 z referrerem `vod.tvp.pl`, AMC Europe, BBC Brit/Earth @Poland) 403-owało po
  imporcie. Przy okazji naprawiony też martwy URL TVP1 (stary pre-rename
  `raw.githubusercontent.com/travino/tvpi/...` → 404), teraz `tvpi.travny.workers.dev/tvp1.m3u`.
  Follow-up: `StationEditDialog` nie przepisywał `userAgent`/`referrer` przy zapisie edycji —
  edycja nazwy/logo/grupy na zaimportowanej stacji z headerami po cichu je gubiła; teraz
  przepuszczane bez zmian, dopóki URL się nie zmienił

## Nakładka z feedseek
Worker /scrape i generatory feedseek robią to samo „strona → Atom” — różnymi drogami
(TS on-demand vs Python wsadowo). Naturalny kierunek: feedseek emituje sources.json
(site → feed URL / selektor), które /discover czyta zanim zacznie sondować ścieżki.

## Do zrobienia / na horyzoncie
- Migracja na built-in Kotlin przed AGP 10 (teraz opt-out: android.builtInKotlin=false
  + android.newDsl=false, by trzymać kotlin.android i compose-compiler na tej samej wersji)
- Wrapper jar nie jest commitowany — CI regeneruje (lokalnie `gradle wrapper`)
- Authenticated feeds (subskrypcje per-user) — odłożone, wymagają przechwycenia
  endpointów XHR z zalogowanej sesji
- Player: reordering/drag-and-drop playlisty, grupy jako sekcje/zakładki w liście,
  Android Auto (MediaSession jest już exported, ale nie testowane w samochodzie)
- Player: `tv.m3u8`/`radio.m3u8` ładowane teraz przez przyciski „Wczytaj przykładowe”
  w pustym stanie (nie auto-seed). Do rozważenia: grupowanie zaimportowanych setek kanałów
  (tv.m3u8 jest duży, sporo geo-blokad/martwych) w sekcje/zakładki po `group-title`

## Logo kanałów z iptv-org (`/logos`)

- Worker: nowy route `GET /logos?ids=<tvg-id,...>` — pobiera raz na dobę katalog
  `logos.json` iptv-org (~7 MB, ~43 tys. wpisów), redukuje go do zwartej mapy
  `{ channelId: url }` (najlepszy wariant: in_use > poziom kanału > format PNG/SVG >
  większa szerokość), trzyma w KV (cross-colo) + memo per-isolate, serwuje wycinki po id.
  Best-effort: brak danych → puste `logos`, nigdy wyjątek.
- App: `Station.tvgId` (M3U `tvg-id`) jako klucz dopasowania; `M3uCodec` parsuje i zapisuje
  `tvg-id`, edycja stacji przenosi go dalej (jak nagłówki). `StationLogos` (na wzór
  `StationDirectory`) uzupełnia brakujące `logoUrl` przez Worker `/logos` przy imporcie M3U
  i wczytaniu przykładowej playlisty — stacje z własnym logo zostają nietknięte.
- EPG świadomie **poza tym zakresem**: `guides.json` iptv-org to tylko katalog źródeł
  (dla kanałów PL `sources: []`), realny program to pipeline grabbera iptv-org/epg albo
  zewnętrzny XMLTV — osobna decyzja, nie ten PR.

## Jedno okno: pager + szuflada (feat/one-window-ui)

- `HomeActivity` przestała być wybierakiem dwóch osobnych Activity — jest teraz jedynym
  oknem aplikacji: `ReaderScreen` i `PlayerScreen` jako strony `HorizontalPager` (swipe
  lewo/prawo), dolny `NavigationBar` (Wiadomości / Radio & TV) i wysuwana szuflada
  (hamburger w górnym pasku obu stron) z pozycjami: Wiadomości, Radio & TV, Zamknij
  aplikację. `MainActivity` i `PlayerActivity` skasowane; ich Compose'owe wnętrza żyją
  dalej jako `ui/ReaderScreen.kt` i `ui/PlayerScreen.kt`. Widget playera deep-linkuje
  do strony playera (`EXTRA_PAGE`, `launchMode=singleTop`). Ustawienia czytnika bez
  zmian — za zębatką u góry strony wiadomości.
- Poprawki wygrzebane przy okazji przeglądu:
  - `usesCleartextTraffic=true` — playlisty IPTV/radio mają dziesiątki URL-i `http://`
    (strumienie i loga); targetSdk 28+ blokował je po cichu, stacje „nie grały".
  - Dodanie stacji o istniejącym URL nie mnoży już duplikatu id (crash LazyColumn
    na zdublowanym kluczu) — `distinctBy { it.id }` w ścieżce zapisu dialogu.
  - Edycja/usunięcie stacji nie zatrzymuje już grającego strumienia: `setPlaylist`
    zachowuje bieżącą stację i stan odtwarzania, o ile stacja przetrwała edycję.
  - Usunięcie ostatniej stacji czyści player (stop + clear + pusty stan widgetu)
    zamiast zostawiać grający strumień bez żadnej kontrolki w UI.
  - Martwa akcja `com.kanarek.action.OPEN` wyleciała z manifestu.

## TV/radio rozróżnialne + now playing + favicon fallback (feat/kind-icons-nowplaying)

- **Ikonki rodzaju**: wiersz stacji i pasek now-playing dostały glif telewizora (TV) albo
  radia (RADIO) — `UNKNOWN` świadomie bez glifu, żeby nie zgadywać. Chipy filtra TV/Radio
  noszą te same ikonki.
- **Now playing (ICY)**: `PlayerService` czyta in-stream `StreamTitle` (SHOUTcast/Icecast)
  z `onMetadata` → `IcyInfo` i publikuje jako `PlayerUiState.nowPlaying`; pasek dolny
  pokazuje utwór pod nazwą stacji (fallback: group title). Czyszczone przy każdej zmianie
  stacji, żeby stary tytuł nie wisiał pod nową.
- **Favicon fallback** (`data/Favicons.kt`, pure Kotlin + testy): stacja bez logo pożycza
  faviconę hosta strumienia — łańcuch własne logo → Google s2 → DuckDuckGo → glif z zasobów,
  w UI (`StationLogo` przechodzi łańcuch po onError) i w widgecie playera (podmiana w
  `pushWidget`, prefetch przez wspólny `WidgetImageCache`).

## Radio/TV jako osobne zakładki, nie miksowana lista (feat/kind-tabs)

- Filtr TV/Radio nad listą stacji był chipami nad jedną wspólną listą (łącznie z opcją
  „Wszystko" mieszającą oba rodzaje). Zamienione na prawdziwe zakładki (`TabRow`): Radio,
  TV, i Inne (dla stacji bez rozpoznanego rodzaju) — każda pokazuje wyłącznie swoją listę,
  bez opcji miksującej wszystko naraz. Zakładki pojawiają się tylko gdy lista faktycznie
  miesza więcej niż jeden rodzaj; czysto-radiowa lub czysto-TV lista zostaje płaską listą
  jak dotąd.
- Wybrana zakładka podąża za tym, co faktycznie gra: przełączenie na kanał TV podczas
  przeglądania zakładki Radio automatycznie przeskakuje na TV, żeby widoczna lista zawsze
  zgadzała się z tym, co leci z głośników. Zakładka trzyma się też poprawnego stanu, gdy
  stacje danego rodzaju znikają z listy (np. usunięcie ostatniej stacji radiowej).
- Nowy string `filter_other` (PL: „Inne") dla zakładki nieotagowanych stacji.
- **Google Cast (2026‑07)** — przesyłanie radia/TV na Chromecasty i telewizory: flavory
  `play` (Cast SDK) / `foss` (bez GMS, dla F‑Droida), `CastPlayer` z Media3 przejmuje playlistę
  od lokalnego ExoPlayera na czas sesji (`PlayerService.switchTo`), picker urządzeń w czystym
  Compose po `MediaRouter`. Nagłówki per-stream (UA/Referer) nie działają na odbiorniku —
  ograniczenie architektury Cast.
