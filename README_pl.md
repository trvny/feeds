<div align="center">

<img src="assets/banner-feedseek.svg" alt="Feedseek" width="960">

<img src="assets/icons/favicon-96x96.png" alt="Feedseek" width="72">

# Feedseek 📡

**Samoodświeżające się feedy RSS/Atom dla stron, które nie udostępniają sensownego natywnego feedu.**

[![pages](https://img.shields.io/github/deployments/trvny/feedseek/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feedseek/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feedseek/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feedseek/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-94-d6541a?style=flat-square&logo=rss&logoColor=white)](feeds.yaml)
[![last commit](https://img.shields.io/github/last-commit/trvny/feedseek?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feedseek/commits/main)
[![license](https://img.shields.io/github/license/trvny/feedseek?color=d6541a&style=flat-square)](LICENSE)  
<a href="https://deepwiki.com/trvny/feedseek"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki"></a>
<a href="https://doi.org/10.5281/zenodo.21701033"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.21701033.svg" alt="DOI"></a>

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9?style=flat-square&logo=uv&logoColor=white)
[![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-222222?style=flat-square&logo=githubpages&logoColor=white)](https://trvny.github.io/feedseek/)

**Polski** · [English](README.md)  

[**📡 Feedy**](https://trvny.github.io/feedseek/) · [**📖 Czytnik**](https://trvny.github.io/feedseek/reader/) · [**🗂 Rejestr**](feeds.yaml) · [**🧭 Technicznie**](docs/architecture.md)  

</div>

Feedseek wyszukuje albo buduje feedy, normalizuje wpisy, usuwa duplikaty i publikuje wynik przez GitHub Pages. Harmonogram odświeża źródła co dwie godziny, a awaria jednego serwisu nie powinna wywracać pozostałych.

Jeśli istnieje użyteczny natywny RSS/Atom, ma pierwszeństwo. Scrapery i adaptery API uzupełniają braki. Nieudane albo puste pobranie nie zastępuje ostatniego poprawnego feedu.

## Feedy

<!-- registry-count: feeds.yaml (94 źródeł) -->
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
- [Family says Massachusetts mother who killed children struggled with mental illness](https://www.reuters.com/legal/government/massachusetts-woman-searched-online-postpartum-psychosis-days-before-killing-2026-08-17/)
- [Incident with GitHub.com](https://www.githubstatus.com/incidents/zkxwbgr0cnmx)
- [Tylko jeden oferent na budowę parkingu za ponad 20 mln zł w Trzebini - Przelom.pl](https://news.google.com/atom/articles/CBMivAFBVV95cUxPNFM4eEg4d0g1UkVPRlVHZ2RSUjE4ckt6U19mQ296S3FmaUxPcW1TeTA0NnM1MVNiTGVDR0JGakl3QUxvLW0wOW8zZFBvY1p5TzcwRGp6REJpWVZVb3JRRlBmQjlhSHNwZ1lyTENNMFpvWFNYdHZZdUVOWm84Y194UzIzMm1rSkp2N3A3eE9FSzF3WVpXVEdqbFQ1TVc4VHNrTUpKOFFpd2xqMzhUUmZNZGxKdEVNSUtVczNsaw?oc=5)
- [EXCLUSIVE: Trump approval falls to 33%, lowest of his presidency, Reuters/Ipsos poll finds](https://www.reuters.com/world/us/trump-approval-falls-33-lowest-his-presidency-reutersipsos-poll-finds-2026-08-17/)
- [Susza hydrologiczna – woda, której nie widać - jaw.pl](https://news.google.com/atom/articles/CBMiYEFVX3lxTE5ITmJxdU1JWkpSQndSUWEybVNzQjNtaDRNRmtld0Ewc05QZmkxekFmQzBHM1dFcTc4cEV0azJBX0c1NThQbEtkT0ZBYm9mbnNJbVhMRGhBOWRLVTNwVWRrTg?oc=5)
- [How a soldier’s video diary from Ukraine’s front line became a Reuters documentary](https://www.reuters.com/world/ukraine-russia-war/how-soldiers-video-diary-ukraines-front-line-became-reuters-documentary-2026-08-17/)
<!--README_FEED:END-->

## 💬 Cytat z szuflady

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝Stay is a charming word in a friend's vocabulary. — Louisa May Alcott❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->

## Other stuff

[![kanarek](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-kanarek.svg)](https://github.com/trvny/kanarek) [![tvpi](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-tvpi.svg)](https://github.com/trvny/tvpi)
