# feedget — historia i stan (import z travino/feedy)

feedget powstał jako samodzielne repo `travino/feedy` (pierwotnie „fidy”) i został
wchłonięty do monorepo `travino/feeds` z zachowaną historią. To skrót najważniejszych
rzeczy — pełna historia commitów żyje po imporcie i w archiwum `travino/feedy`.

## Co to jest
Natywny androidowy widget (resizable, auto-rotating slideshow newsów) + companion app
do zarządzania feedami + opcjonalny worker TS na Cloudflare (RSS/Atom → JSON na krawędzi).
Stack: Kotlin/Compose (Material 3), App Widgets (AdapterViewFlipper + RemoteViewsService),
DataStore, WorkManager, Coil. AGP 9.2 / Kotlin 2.4 / Gradle 9.6, compileSdk 37 / minSdk 26.

## Zrobione (chronologicznie)
- fidy → feedy: pełny rename pakietu/aplikacji/workera (#14)
- Widget + slideshow, companion app, parser RSS/Atom (pure-Kotlin)
- OPML import/export (SAF, bez uprawnień storage) (#21)
- Hardening widgetu: dwupoziomowy cache obrazków (LRU + ~12 MB on-disk),
  battery-not-low constraint, keep-last-good na pustym/błędnym fetchu (#22)
- Conditional GET ETag/304: worker emituje słaby ETag po zbiorze itemów (nie po
  timestampie), app wysyła If-None-Match i reużywa cache na 304 (#23)
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
