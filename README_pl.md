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
- [Krzeszowice zyskają nowe miejsce dla młodych. Budowa trwa - krzeszowiceone.pl](https://news.google.com/atom/articles/CBMiqgFBVV95cUxPQUd0U1huc1J2bThOZzcySHUzSVdlUEZCZ29jV1ZfYURLZWNTeDZ3YmtMRy0wZ2pKTllUR1lmUktRekIxNG5mMmY5QWNIR3otWjJ0ajNIN0NMT2ZaN2JqM0VvcVBYVXpxeXpCczR3R2txU0ZTTXoxRFozZGdpT2NhVEJ2aWZ6cWlHZDJ3WEo0dEJHMXM5TWJSTnBtWTNLd0NfWTA1aEtlLXJDQdIBrwFBVV95cUxNTHJKUEMzRmJfNW0xOUIxWlhCc28wbTJ4QkpLdWtaRlF0X1JUaFdoOEg4Ylg5VkwzRzctZXNLaDN2VUgyTkdSSGhjSzJXTld2cFZyS1hoaUNQRm0zODhFQThYQ1Fwb3pKYW8xVGdJUWxNR296THBoX2JuQkFtdnptQ1ZVdVR2YTJhQ09NdDgzMUZrNnZOb1dFMERzNHBFQUUwRGVjbktoM29ta1R0U2dj?oc=5)
- [Święto plonów w Lgocie! Barwny korowód i wspólna zabawa mieszkańców \(WIDEO,ZDJĘCIA\) - Przelom.pl](https://news.google.com/atom/articles/CBMixAFBVV95cUxOd0NQVmd2NlJfR3lXZ1VwdDhWd3lUUXdRRHNneHNNbDFkUWVxWkg0M3BnTDRNVVZWOE5feXZFUFJIaVc3QlNGdlVsdG81UWhHR050cHNkelYydmtXYnR5M2pNWThySDlYeUJYZFFwRHctSnlLbGFjeGMxRnJVXzdLQ3BBZ0l5eXAzQ0VmOEVrUklNdFVXdmdZcnByLTIyOXpIOW1BcldqemQtbGJCcWxNT2Fqa0Q3d1IxU1k2YnNKdWJ2aE5B?oc=5)
- [Landslide at Guinea landfill kills 30, government says](https://www.reuters.com/business/environment/landslide-guinea-landfill-kills-30-government-says-2026-08-23/)
- [Przegląd AI: 23 sierpnia 2026](https://promptowy.com/przeglad-ai-2026-08-23/)
- [Zamknięcie dnia: Alibaba stawia wszystko na AI, Nvidia podnosi stawkę](https://promptowy.com/zamkniecie-dnia-alibaba-stawia-wszystko-na-ai-nvidia-podnosi-stawke/)
- [Norris wins Dutch GP as Antonelli stretches his F1 lead](https://www.reuters.com/sports/formula1/norris-wins-dutch-gp-complete-mclaren-hat-trick-2026-08-23/)
<!--README_FEED:END-->

## 💬 Cytat z szuflady

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝Don'T Find Fault, Find A Remedy. — Henry Ford❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->

## Other stuff

[![kanarek](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-kanarek.svg)](https://github.com/trvny/kanarek) [![tvpi](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-tvpi.svg)](https://github.com/trvny/tvpi)
