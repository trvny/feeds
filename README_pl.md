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

**Polski** · [English](README.md)  

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
- [Muzyczna niedziela w Chrzanowie i Wygiełzowie. Wyrostek, filmowe przeboje i Janosik w skansenie - Przelom.pl](https://news.google.com/atom/articles/CBMiwgFBVV95cUxQakE4NzZHR0gzN2h6VGZudUpKX0dPWjRBWm4yR0lYX09fVEgyMklySmFDYzhMN2NXcHlBcXFvOG9kYTB2Z0d3SjZUalIwdzJ1M1gtUHF3b3dxOXBtZ0xTZXhlb19LcXNMSGcySHBtVGFiWElJaUltbmVvQmgxcmlJVkx5RlRCSEVTaVRhWm5OSllyYmM5ZkZvRkFsQnRGX1BTNExTLWVvVll2dXRiWjFVZS1JcGkwVUM4UTJhdjQwZ21yQQ?oc=5)
- [Mieszkańcy krytykują przebudowę ul. Chrzanowskiej - Przelom.pl](https://news.google.com/atom/articles/CBMimwFBVV95cUxOLTRpajJHSEhodVN2bU5MRUwwdDJRNHl3SDE4UzZMSzJ4Q0pFTThoWWxocVRGazN4eUtoa3ZmTWRHUkRFUVNzbmlFRkdQWnBmTGNBYTU5V1hPQzlGMUdwTEhFNGp5blVxcnpYSGt2cE9zOHRlRG5DSzRHYnE2RlVuY3ZyX2wtaWttYlBSMXlTY0djVmxWYlJnSXBEQQ?oc=5)
- [Alex Jones gets Sandy Hook family's Texas verdict reduced on appeal](https://www.reuters.com/legal/government/alex-jones-gets-sandy-hook-familys-texas-verdict-reduced-appeal-2026-08-21/)
- [Polski podatek tokenowy: ile więcej płacisz za AI, bo piszesz po polsku](https://promptowy.com/polski-podatek-tokenowy-ile-drozej-ai/)
- [US EPA to extend renewable fuel standard compliance deadline for refiners](https://www.reuters.com/business/energy/epa-extends-renewable-fuel-standard-compliance-deadline-refiners-2026-08-21/)
- [Supreme Court lets Trump continue work on White House ballroom for now](https://www.reuters.com/world/supreme-court-lets-trump-continue-work-white-house-ballroom-now-2026-08-21/)
<!--README_FEED:END-->

## 💬 Cytat z szuflady

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝That men do not learn very much from the lessons of history is the most important of all the lessons that history has to teach. — Aldous Huxley❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->

## Other stuff

[![kanarek](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-kanarek.svg)](https://github.com/trvny/kanarek) [![tvpi](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-tvpi.svg)](https://github.com/trvny/tvpi)
