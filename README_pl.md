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
- [Bakteria w wodzie! Zjeżdżalnia na Basenach Letnich w Chrzanowie zamknięta - Przelom.pl](https://news.google.com/atom/articles/CBMiuwFBVV95cUxQUHJJa3pnenhMdWVWTngwS0E5NFN4YV9PVFduVHdoQWlkQkFmUlRkQ05Fa0k4SjNWeWtfMnloeUIxN2pEbV9laTlLNlREWEJJQ3VMRzlFdU1EcEQ1ZWNlLTBCQzc4LW93eTUwRzUya0g2bEpVeGltdGZmVFV6Vkk2VngxLURfTVA2Y2tmdFdDTWR4aFhnSmVxem9PY3M4U2FvX2NGWEJBNXhSb0xMM3NqaUZLanBSTE8yY0w0?oc=5)
- [iPhone Ultra w polskich sklepach? Nie mamy dobrych wiadomości](https://antyweb.pl/iphone-ultra-w-polskich-sklepach-nie-mamy-dobrych-wiadomosci)
- [Tajemnicza śmierć seniorki spod Oświęcimia. Niepokojące doniesienia - Fakt](https://news.google.com/atom/articles/CBMivwFBVV95cUxQZzRXYkRFMWJUbHpvUVZ3UmRDVHVBZzFBWUVNa2VuR2tWVzE5ekx5V0hoMlpnbjIwSmtULWE2Wjd3bVJtdlRlVmlaMjV6aDVhMTJ2NTVJMFNIRjVzWHFZV2hlQmRtTGZmODlNLVVsNXU2cXpGRlZaeHBBQ3lfUEJCY2lmSzdnaXJ3VUlkakJIN3NfYkNxbFNSV3hWRWk5SDNyTGRJMTMzWGZhcHIwMTZLVmVNcmM4cTRkWTJGWDZINA?oc=5)
- [Kennedy Center board votes to inscribe Trump's name on building](https://www.reuters.com/world/us/kennedy-center-board-votes-inscribe-trumps-name-building-2026-08-13/)
- [US could not verify Israeli warnings of Iran plots against Trump, sources say](https://www.reuters.com/world/middle-east/us-could-not-verify-israeli-warnings-iran-plots-against-trump-sources-say-2026-08-13/)
- [Sandisk forecasts mid-to-high-teens revenue growth through 2030](https://www.reuters.com/business/sandisk-forecasts-mid-to-high-teens-revenue-growth-through-2030-2026-08-13/)
<!--README_FEED:END-->

## 💬 Cytat z szuflady

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝“Software is a gas; it expands to fill its container.”— Nathan Myhrvold❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->


# Other stuff

[![tvpi](https://github-stats-extended.vercel.app/api/pin?username=trvny&repo=trvny%2Ftvpi&theme=yeblu)](https://github.com/trvny/tvpi)
