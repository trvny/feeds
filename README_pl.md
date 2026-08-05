<div align="center">

<img src="assets/banner.png" alt="trvny/feeds" width="820">

**Feedseek + Kanarek 🐤: produkcja i konsumpcja feedów w jednym monorepo.**
Feedseek scrapuje strony bez RSS, generuje Atom i publikuje go na GitHub Pages, a Kanarek czyta feedy w natywnej aplikacji i widżecie na Androida.

[![pages](https://img.shields.io/github/deployments/trvny/feeds/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feeds/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-92-d6541a?style=flat-square&logo=rss&logoColor=white)](feedseek/feeds.yaml)
[![last commit](https://img.shields.io/github/last-commit/trvny/feeds?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/commits/main)
[![license](https://img.shields.io/github/license/trvny/feeds?color=d6541a&style=flat-square)](LICENSE)
<a href="https://deepwiki.com/trvny/feeds"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki"></a>  
[**📡 Strona**](https://trvny.github.io/feeds/) · [**📖 Czytnik**](https://trvny.github.io/feeds/reader/) · [**🗂 Rejestr feedów**](feedseek/README.md#feeds-)  
**Polski** · [English](README.md)

</div>

---

# Feedseek + Kanarek 🐤

<div align="center">
<strong>🚪 Hol główny</strong>
</div>

<br>

<table>
<tr>
<td align="center" valign="top" width="50%">
<br>
<a href="kanarek/"><img src="assets/icons/kanarek.svg" width="112" height="112" alt="Kanarek"></a>
<h2><a href="kanarek/">🐤 Kanarek</a></h2>
<strong>Czytaj feedy i oglądaj streamy</strong>
<p>Natywna aplikacja i widżety na Androida z czytnikiem wiadomości oraz odtwarzaczem radia/IPTV.</p>
<a href="kanarek/"><strong>KANAREK →</strong></a>
<br><br>
<a href="kanarek#readme">Readme</a> · <a href="https://github.com/trvny/feeds/releases/latest">App</a> · <a href="kanarek/worker/">Worker</a>
<br><br>
<img src="https://img.shields.io/badge/-Kotlin-7F52FF?style=flat&logo=kotlin&logoColor=white" alt="Kotlin">
<img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=fff&style=flat" alt="TypeScript">
<img src="https://img.shields.io/badge/-Worker-F38020?style=flat&logo=cloudflare&logoColor=white" alt="Cloudflare Worker">
<br><br>
</td>
<td align="center" valign="top" width="50%">
<br>
<a href="feedseek/"><img src="assets/icons/android-chrome-192x192.png" width="112" height="112" alt="Feedseek"></a>
<h2><a href="feedseek/">📡 Feedseek</a></h2>
<strong>Produkuj i publikuj feedy</strong>
<p>Generatory RSS/Atom, odświeżane co 2 h i publikowane na GitHub Pages.</p>
<a href="feedseek#rss--atom-feeds-"><strong>FEEDSEEK →</strong></a>
<br><br>
<a href="feedseek/README.md#feeds-">Rejestr</a> · <a href="https://trvny.github.io/feeds/">Strona</a> · <a href="https://trvny.github.io/feeds/reader/">Czytnik</a>
<br><br>
<img src="https://img.shields.io/badge/-Python-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=fff&style=flat" alt="uv">
<a href="https://github.com/trvny/feeds"> <img src="https://img.shields.io/badge/-Pages-222222?style=flat&logo=githubpages&logoColor=white" alt="GitHub Pages"></a>
<br><br>
</td>
</tr>
</table>

Oba robią to samo: `strona → Atom`, tylko z dwóch stron. `feedseek` działa **wsadowo w CI**, a `kanarek/worker` **on-demand na krawędzi** (`/discover` + `/scrape` → `RSS→JSON`).

## ⚙️ Jak to działa

```text
                  feeds.yaml (92 źródeł)
                         │
   ┌─────────────────────┴─────────────────────┐
   │  feedseek — GitHub Actions, co 2 h         │
   │  scrape → parse → dedup → Atom XML          │
   └─────────────────────┬─────────────────────┘
                         │  publish
                         ▼
          trvny.github.io/feeds/  ──▶  /reader/  (czytnik OPML)
                         │
                         │  konsumpcja
                         ▼
          kanarek — widżet/apka Android  ◀──  worker (RSS→JSON)
```

- **Izolacja błędów** — jedno padnięte źródło nie blokuje reszty.
- **Hash-gated `updated`** — feed nie „mieli”, gdy wpis się nie zmienił.
- **Dedup** po znormalizowanym URL-u i tytule (cross-source).
- **Bot-protection** — `curl_cffi` + impersonacja Chrome ogarnia Cloudflare/Akamai/DataDome.

## 🗂 Struktura

```text
feeds/
├── feedseek/          # generatory RSS/Atom + statyczny czytnik
│   ├── feed_generators/
│   ├── feeds.yaml     # rejestr źródeł
│   ├── feeds/         # wygenerowane XML-e (CI)
│   └── site/          # build_site.py + reader.html
├── kanarek/           # apka Android + Cloudflare Worker
└── .github/workflows/ # CI obu projektów (przez working-directory)
```

Historia obu projektów (`feeds` + `kanarek`) została zachowana po konsolidacji do monorepo.

## 📄 [Licencja](LICENSE)

[![License](https://www.shieldcn.dev/github/license/trvny/feeds.svg?variant=branded&size=xm&mode=light&theme=neutral&font=jetbrains-mono)](https://spdx.org/licenses/MIT)

Licencja MIT obejmuje oryginalny kod i dokumentację. Treści z feedów, artykuły,
obrazy, streamy, nazwy i znaki zewnętrznych podmiotów pozostają własnością ich
autorów: [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md).

## 📰 Mininewsy

<!--README_FEED:START-->
- [How Populist Middle Powers Are—and Are Not—Reshaping Global Politics](https://carnegieendowment.org/research/2026/08/how-populist-middle-powers-areand-are-notreshaping-global-politics)
- [Trump administration to impose 15% tariff in polysilicon probe meant to counter China](https://news.google.com/rss/articles/CBMirgFBVV95cUxON0ctWlNTcE9CNEpzbmE4cXRCdFVEU2k2dVpMNjc0M0xLQU1hSWR2MmgwZjdXenNzVnlSM0dGUWVmVlJzUGJ1b3kxV0NReVNqRFItdHlqbzcwR085cmJ5NFRBRlNWTXBRLXRRcmh1Uzl0Wmo2N2d3Wjd1MmpKNkN6Umo4bHlZdFhsbUZYWTVFeGhBUjVCZ3pyNy1EYkVFaWMzVC1ZSzRlQnVYS21LZWc?oc=5)
- [US Senate confirms Schwartz as CDC director](https://news.google.com/rss/articles/CBMiigFBVV95cUxPdUlSeHMyTFMzMzBSYXp5UHJJZ2dQTEZJYTJ5c1dtdWZHaXJ0WUNMRnVIRkpJY2c5dlRWcVdybmVPbFhJcHZ1XzBaZHRPWUJlY181eDItTEtraEY3d0V6dGJRVE9ReXFJcnktcGJEY25nRWtTbGFpRzQ5UXZXSkVVRWJZYTNrM21fQ0E?oc=5)
- [Etsy lays off 12% of workforce as part of restructuring plan](https://news.google.com/rss/articles/CBMiqgFBVV95cUxOYWh3SWlrVGlSZDBVdnBWajVZS3N1ejdBVVN6SlY2V3JIdVRQOVc2VGFtX1Y1MHNsblFON3pWVkhZbHU4WmtoQWZWNlZJQUZLMDlkMTEyNDBycEd1Y3BMMXRHUDNnSHZMNHdFY3FycS12R080bTZ5TEVfQmFzOE1ONzJ5WlpMS0trVFV6T3lpRFo2WVRiSUpOWW5hZDlZczgtdnhYeEVZRnBrQQ?oc=5)
- [ZKKM Chrzanów uruchamia nową linię i zwiększa liczbę połączeń - Przelom.pl](https://news.google.com/atom/articles/CBMirwFBVV95cUxQdDkxMHY5VUR3VW5RZmZLWGxPaXRjZ1Z4U2QxbDZNYS1uLWl6Q1oyUVRlUHEtQTh3QmI5VHFrUEtQNVYxZmo0dTIyT0NUWkExeEVQTmprQlBtZ1RBdm54c1Nfa1FiZG05OUQ0dkU0bTg5cFpvVEx6VTY0NWxBZWprMGtsd0dTYkRERmUwckZZOU1ad2JyWi1LdnJkX0tVT2tLRldWNTdJZXJ5UUZqWi1J?oc=5)
- [EXCLUSIVE: Iran threatens to hit Gulf states if US launches new strikes](https://news.google.com/rss/articles/CBMisAFBVV95cUxPajFnaXk0anVrT2IwaV9XMDBma0pMQU53ZF9LRUJiT01nWjJsdG5FZXhwUjNtZFp2Yy1NV3Q4dFRIeUxzV1pCWk9RMVVZNk1UbWxxMFdiNEdNTG5KSVBVWTRCaWFJSFNlT3RiMFF6RWtqN2pnRThTUU9GaHNfelhwV3RZTXdfMzJwUk1aVlFXZ0FBNk1qWFFmd2xIRWNVWVpmQl9DSkE2NnhMaXlJZ2FFeQ?oc=5)
<!--README_FEED:END-->

## 💬 Cytat z szuflady

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝“There are only two things wrong with C++:  The initial concept and the implementation.”— Bertrand Meyer❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->


# Other stuff

[![tvpi](https://github-stats-extended.vercel.app/api/pin?username=trvny&repo=trvny%2Ftvpi&theme=yeblu)](https://github.com/trvny/tvpi)
