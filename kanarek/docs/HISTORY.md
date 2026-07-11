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
