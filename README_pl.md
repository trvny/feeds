<div align="center">

<img src="assets/banner-feedseek.svg" alt="Feedseek" width="960">

<img src="assets/icons/favicon-96x96.png" alt="Feedseek" width="72">

# Feedseek 📡

**Samoodświeżające się feedy RSS/Atom dla stron, które nie udostępniają sensownego natywnego feedu.**

[![pages](https://img.shields.io/github/deployments/trvny/feedseek/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feedseek/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feedseek/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feedseek/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-95-d6541a?style=flat-square&logo=rss&logoColor=white)](feeds.yaml)
[![last commit](https://img.shields.io/github/last-commit/trvny/feedseek?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feedseek/commits/main)
[![license](https://img.shields.io/github/license/trvny/feedseek?color=d6541a&style=flat-square)](LICENSE)  
<a href="https://deepwiki.com/trvny/feedseek"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki"></a>

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9?style=flat-square&logo=uv&logoColor=white)
[![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-222222?style=flat-square&logo=githubpages&logoColor=white)](https://trvny.github.io/feedseek/)

**Polski** · [English](README.md) · [简体中文](README_zh.md)  

[**📡 Feedy**](https://trvny.github.io/feedseek/) · [**📖 Czytnik**](https://trvny.github.io/feedseek/reader/) · [**🗂 Rejestr**](feeds.yaml) · [**🧭 Technicznie**](docs/architecture.md)  

</div>

Feedseek wyszukuje albo buduje feedy, normalizuje wpisy, usuwa duplikaty i publikuje wynik przez GitHub Pages. Harmonogram odświeża źródła co dwie godziny, a awaria jednego serwisu nie powinna wywracać pozostałych.

Jeśli istnieje użyteczny natywny RSS/Atom, ma pierwszeństwo. Scrapery i adaptery API uzupełniają braki. Nieudane albo puste pobranie nie zastępuje ostatniego poprawnego feedu.

## Feedy

<!-- registry-count: feeds.yaml (95 źródeł) -->
Pełna tabela źródeł i bezpośrednich plików feedów znajduje się w [angielskim README](README.md#feeds-), a wygodniejszy interfejs do przeglądania i subskrypcji na [stronie Feedseek](https://trvny.github.io/feedseek/).

- **Rejestr:** [`feeds.yaml`](feeds.yaml)
- **Wygenerowane XML/JSON:** [`feeds/`](feeds/)
- **Indeks źródeł:** [`docs/sources.md`](docs/sources.md)
- **Notatki o poszczególnych feedach:** [`docs/feeds.md`](docs/feeds.md)

## Dokumentacja

- [Pipeline, enrichment, użycie lokalne i układ repozytorium](docs/architecture.md)
- [Źródła i kompromisy poszczególnych feedów](docs/feeds.md)
- [Działanie i utrzymanie cache](docs/cache.md)
- [Wygenerowany indeks źródeł](docs/sources.md)

Androidowy czytnik/player tych feedów to osobny projekt: **[trvny/kanarek](https://github.com/trvny/kanarek)**.

## [Licencja](LICENSE)

[![Licencja](https://www.shieldcn.dev/github/license/trvny/feedseek.svg?variant=branded&size=xm&mode=light&theme=neutral&font=jetbrains-mono)](https://spdx.org/licenses/MIT)  [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md)

## 📰 Mininewsy

<!--README_FEED:START-->
- [Urban Word of the Day — grebo](https://www.urbandictionary.com/define.php?term=grebo&defid=1975218)
- [How to Engage with New Media: A Strategic Guide for Nonprofit Organizations](https://carnegieendowment.org/research/2026/08/how-to-engage-with-new-media-a-strategic-guide-for-nonprofit-organizations)
- [Urban Word of the Day — board chow](https://www.urbandictionary.com/define.php?term=board%20chow&defid=2568411)
- [Wielkie czyszczenie na Netflix. 30 filmów zniknie za kilka dni](https://antyweb.pl/wielkie-czyszczenie-na-netflix-30-filmow-zniknie-za-kilka-dni)
- [Jesienne porządki z Parkside. Szybsza praca w ogrodzie i domu](https://antyweb.pl/jesienne-porzadki-z-parkside-szybsza-praca-w-ogrodzie-i-domu)
- [Weekend w Chrzanowie i okolicy. Zobacz najciekawsze imprezy i wydarzenia 28 - 30 sierpnia - Gazeta Krakowska](https://news.google.com/atom/articles/CBMiywFBVV95cUxNbkxZVXZYZW92ZzRlSFh4UElqdUxZQTN4S3ZYbFU5d09XaGFRN3l4ZVVwSXBkUU5fZXBLZkFpMnMteE5tRTFDbUJxQ0dGeC1aQnRoQmhtd25iaEt5QWlrR2hGVjNFUk91WEpfZldsRkFvR25nY0lvQ2YtSF9ZSzZqVXlDYjBjMFZ6MVB0OVFUSjluRVgtVS0zRW1YaDhGcll4NTRPWVpSRHdqYWlyUnV4bnBxTEdlMGp4V2NZVWY0bkN5S1ZzY3hrbk1Pcw?oc=5)
<!--README_FEED:END-->

## 💬 Cytat z szuflady

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝The worst breach of U.S. military computers in history happened when someone picked up a memory stick (infected by a foreign intelligence agency) they found in the parking lot and plugged it into their computer, which was attached to United States Central Command.❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->

## Other stuff

[![kanarek](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-kanarek.svg)](https://github.com/trvny/kanarek) [![tvpi](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-tvpi.svg)](https://github.com/trvny/tvpi)
