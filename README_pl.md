<div align="center">

<img src="assets/banner-feedseek.svg" alt="Feedseek" width="960">

<img src="assets/icons/favicon-96x96.png" alt="Feedseek" width="72">

# Feedseek 📡

**Samoodświeżające się, ulepszane feedy RSS/Atom + JSON: zarówno tam, gdzie feedu brakuje, jak i tam, gdzie natywny da się zrobić lepiej.**

[![pages](https://img.shields.io/github/deployments/trvny/feedseek/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feedseek/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feedseek/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feedseek/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-104-d6541a?style=flat-square&logo=rss&logoColor=white)](feeds.yaml)
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

Feedseek nie jest tylko generatorem dla stron, które nie mają feedu. Natywny RSS/Atom jest wartościowym źródłem wejściowym, ale nie nietykalnym produktem końcowym: jeśli materiał źródłowy na to pozwala, Feedseek normalizuje i wzbogaca go do stabilniejszej, pełniejszej, bogatszej semantycznie i bardziej interoperacyjnej postaci, publikując obok XML także JSON Feed 1.1.

Celem jest wykorzystywanie możliwości RSS, Atom i JSON Feed tak dobrze, jak pozwalają dane źródłowe: trwałe identyfikatory, kanoniczne linki, prawdziwe daty publikacji i aktualizacji, użyteczne metadane, pochodzenie, kategorie oraz media. Scrapery i adaptery API uzupełniają braki natywnych źródeł. Nieudane albo puste pobranie nie zastępuje ostatniego poprawnego feedu.

## Feedy

<!-- registry-count: feeds.yaml (104 źródeł) -->
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

Androidowy czytnik/player tych feedów to osobny projekt: **[twojstar/kanarek](https://github.com/twojstar/kanarek)**.

## [Licencja](LICENSE)

[![Licencja](https://www.shieldcn.dev/github/license/trvny/feedseek.svg?variant=branded&size=xm&mode=light&theme=neutral&font=jetbrains-mono)](https://spdx.org/licenses/MIT)  [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md)

## 📰 Mininewsy

<!--README_FEED:START-->
- [How to Engage with New Media: A Strategic Guide for Nonprofit Organizations](https://carnegieendowment.org/research/2026/08/how-to-engage-with-new-media-a-strategic-guide-for-nonprofit-organizations)
- [Powiatowi społecznicy spotkają się w Libiążu - Przelom.pl - portal ziemi chrzanowskiej](https://news.google.com/atom/articles/CBMilgFBVV95cUxQcEhKWlVWS1hZNE9yNGtrTVhmU29Jd2pxTEk2SFlIb2xybWxDVW9ybi1FLUVRanVjZERONVl5V2Y5WEhuZkVKRlM5V0FyVmI5aDNyYlZoSTJHZFNMemlWczZIRExSQnF2amNPVENBemo4UGRMekVKUUlCODVwWjBSRmE4MHI2dDljZGtGTHNsRVEtZ2hMWGc?oc=5)
- [W Puszczy Dulowskiej powstanie rezerwat? Jest oficjalny wniosek - Przelom.pl - portal ziemi chrzanowskiej](https://news.google.com/atom/articles/CBMiuwFBVV95cUxNVmFGeGRzUF9JWjVoSVFpREs3cmY0U2ZZQ1VLc05VSlI2NUs2X05kM292YnVNdGpGR3VmVktDaHhodDVLd1k4eHNkOU9DdVRxbllhcV9YSzU3ZVk0VXlOVm1Fang5a0dMNEE5b29ZY0ZwUzQ4a3ZudEtlLXd0dGZKVDlSWmEwVXhGSHo5a2cxQVlELWdtSjI3R2hkTHdUMW42TWtYS0pzQUNsbS1TTENNdEdqV3UydzlJb1kw?oc=5)
- [To będzie wyjątkowy dzień dla psów i ich właścicieli. Krzeszowice szykują akcję - Przelom.pl - portal ziemi chrzanowskiej](https://news.google.com/atom/articles/CBMiwgFBVV95cUxPMUFWanRpTDdQeU8tWE9KeXhEWDg5ZlN2eGtnczAzb1RkQXphbXJuLTZianZubnZoYS1DdUxfTW1VNkp0NjA2VVNQSGFWTTRVbTAwTlVrZFg4bkFnWWY3TmNvdlAwSHFEUk1qakcyODJCcF92RDNDejdxTk4wOTdFZkw3M0FGRTFUd3lweGxySjhfckFodUhzTmR5X3B0Y0kxQzRuZEJ5QTJHT2c1RWhhRl9sZGZuMDlOQ1NTYnhQYzdDUQ?oc=5)
- [Uwaga! Zamknięta droga w Libiążu - Przelom.pl - portal ziemi chrzanowskiej](https://news.google.com/atom/articles/CBMihAFBVV95cUxOMnRqekw1a1owUDVVZjVVSXpMRXhVSUtwUnNMUzB0SG5acDVzZDVINW1kWlIydTBHTDRyWTFBazd5R295VXVKQnlsZWljVTJ1Rkt6TUxGenpoV3F3TnQxMFM2eWt1X0h2bE51czBwSVdldER6S3kwNHdrSTllbWt2RnJoTDc?oc=5)
- [To oni będą ratować mieszkańców! Czterech nowych strażaków w Chrzanowie - Przelom.pl - portal ziemi chrzanowskiej](https://news.google.com/atom/articles/CBMiuAFBVV95cUxOcHRLczZTTTNJeEtjSDhuUDJFRWNqM0k2Ym9uSFhMcVBxSGFEX00waHM0NF9nbmczcDRFbFpXOGdzcjg5eWpHUjVnYlJBV2RVdnZ1ZEoxODZfN3dJbkJBQnU2NXZuejI0ZVRxQkwweGVRZzR1VmhpMkItV3E0a3VSQzRwWTAzY29MbkVuM3EyX29zdktXV2JMaVctNGVGMUpTb3Y5ZV9SM3lLSmFycU1Za1B3akZJYnd3?oc=5)
<!--README_FEED:END-->

## 💬 Cytat z szuflady

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝“Code generation, like drinking alcohol, is good in moderation.”— Alex Lowe❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->

## Other stuff

[![kanarek](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-kanarek.svg)](https://github.com/twojstar/kanarek) [![tvpi](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-tvpi.svg)](https://github.com/trvny/tvpi)
