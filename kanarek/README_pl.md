[English](README.md) | **Polski**

<div align="center">

<img src="https://raw.githubusercontent.com/trvny/feeds/refs/heads/main/assets/icons/kanarek.svg" alt="Kanarek" width="96">

# Kanarek

**Czytnik i widżet wiadomości oraz odtwarzacz radia/IPTV dla Androida.**

[![android CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/android-ci.yml?label=android%20CI&logo=android&logoColor=white&color=FFC107&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/android-ci.yml)
[![worker CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/worker-ci.yml?label=worker%20CI&logo=cloudflare&logoColor=white&color=FFC107&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/worker-ci.yml)
[![Kotlin](https://img.shields.io/badge/Kotlin-2.4.10-FFC107?style=flat-square&logo=kotlin&logoColor=white)](gradle/libs.versions.toml)
[![license](https://img.shields.io/github/license/trvny/feeds?color=FFC107&style=flat-square)](../LICENSE)

</div>

Kanarek łączy dwa narzędzia w jednej natywnej aplikacji:

- czytnik RSS/Atom z automatycznym pokazem wiadomości i widżetem ekranu głównego,
- odtwarzacz radia internetowego i IPTV działający w tle, również z własnym widżetem.

Opcjonalny Cloudflare Worker przyspiesza pobieranie i dodaje funkcje sieciowe. Nie jest wymagany: zwykłe kanały RSS/Atom mogą być przetwarzane bezpośrednio na urządzeniu.

## Najważniejsze funkcje

### Wiadomości

- skalowalny widżet z pokazem slajdów, ręczną nawigacją i osobnymi ustawieniami każdego egzemplarza,
- własne źródła RSS 2.0 i Atom, import oraz eksport OPML,
- wyszukiwanie wiadomości, filtrowanie źródeł i tryb najważniejszych nagłówków,
- oznaczanie jako przeczytane, zapisywanie artykułów oraz opcjonalny tekst offline,
- podgląd czystej treści artykułu przy skonfigurowanym Workerze,
- opcjonalne powiadomienia o nowych wiadomościach z godzinami ciszy,
- zachowanie ostatnich poprawnych wiadomości, gdy pojedyncze źródło chwilowo nie działa.

### Radio i IPTV

- odtwarzanie w tle przez Media3/ExoPlayer z kontrolkami systemowymi,
- import, eksport i edycja playlist M3U/M3U8,
- radio, telewizja, grupy kanałów, ulubione stacje i metadane aktualnego utworu,
- wyszukiwanie stacji w katalogu Radio Browser,
- uzupełnianie brakujących logotypów kanałów przez iptv-org i favikony,
- obsługa `User-Agent` oraz `Referer` zapisanych w playliście,
- Google Cast w wariancie `play`; wariant `foss` nie wymaga usług Google.

## Instalacja

Gotowe pliki APK są publikowane w [GitHub Releases](https://github.com/trvny/feeds/releases).

- `play`: zawiera obsługę Google Cast,
- `foss`: wariant bez GMS, przeznaczony dla środowisk FOSS i F-Droid.

Minimalna wersja systemu to Android 8.0 (API 26).

## Szybki start

1. Zainstaluj wybrany wariant APK.
2. Otwórz Kanarka i wybierz **Wiadomości** albo **Radio i TV**.
3. Dodaj własne źródła RSS/Atom lub zaimportuj OPML.
4. Dodaj stacje ręcznie, wyszukaj radio albo zaimportuj playlistę M3U/M3U8.
5. Przytrzymaj ekran główny Androida, otwórz **Widżety** i dodaj wybrany widżet Kanarka.

Adres Workera można zostawić pusty. Ustaw go tylko wtedy, gdy chcesz korzystać z odkrywania feedów, scrapowania stron, czystego czytnika, katalogu stacji, synchronizacji stanu lub wspólnego cache na krawędzi.

## Dokumentacja

- [Architektura](docs/ARCHITECTURE.md)
- [Budowanie, testy i CI](docs/DEVELOPMENT.md)
- [Cloudflare Worker i API](docs/WORKER.md)
- [Historia projektu](docs/HISTORY.md)

## Rozwój

Najkrótsza ścieżka lokalna:

```bash
gradle wrapper --gradle-version 9.6.1
./gradlew assembleDebug
./gradlew testPlayDebugUnitTest
```

Szczegóły środowiska, wariantów, testów i workflowów są w [dokumencie developerskim](docs/DEVELOPMENT.md).

## Licencja

Projekt jest udostępniany na warunkach licencji opisanej w [LICENSE](../LICENSE).
