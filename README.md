<div align="center">

<img src="assets/banner.png" alt="trvny/feeds" width="820">

**Feedseek + Kanarek 🐤: produkcja i konsumpcja feedów w jednym monorepo.**
Feedseek scrapuje strony bez RSS, generuje Atom i publikuje go na GitHub Pages, a Kanarek czyta feedy w natywnej aplikacji i widżecie na Androida.

[![pages](https://img.shields.io/github/deployments/trvny/feeds/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feeds/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-53-d6541a?style=flat-square&logo=rss&logoColor=white)](feedseek/feeds.yaml)
[![last commit](https://img.shields.io/github/last-commit/trvny/feeds?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/commits/main)
[![license](https://img.shields.io/github/license/trvny/feeds?color=d6541a&style=flat-square)](LICENSE)  
[**📡 Strona**](https://trvny.github.io/feeds/) · [**📖 Czytnik**](https://trvny.github.io/feeds/reader/) · [**🗂 Rejestr feedów**](feedseek/README.md#feeds-)  
**Polski** · [English](docs/README-EN.md)

</div>

---

## Feedseek + Kanarek 🐤

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
<a href="kanarek/"><strong>WEJDŹ DO APLIKACJI →</strong></a>
<br><br>
<a href="kanarek/README.md">README</a> · <a href="kanarek/app/">Aplikacja</a> · <a href="kanarek/worker/">Worker</a>
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
<p>Generatory RSS/Atom dla stron bez użytecznego feeda, odświeżane co 2 h i publikowane na GitHub Pages.</p>
<a href="feedseek/"><strong>WEJDŹ DO FEEDÓW →</strong></a>
<br><br>
<a href="https://trvny.github.io/feeds/">Strona</a> · <a href="https://trvny.github.io/feeds/reader/">Czytnik</a> · <a href="feedseek/README.md#feeds-">Rejestr</a>
<br><br>
<img src="https://img.shields.io/badge/-Python-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=fff&style=flat" alt="uv">
<img src="https://img.shields.io/badge/-Pages-222222?style=flat&logo=githubpages&logoColor=white" alt="GitHub Pages">
<br><br>
</td>
</tr>
</table>

Oba robią to samo: `strona → Atom`, tylko z dwóch stron. `feedseek` działa **wsadowo w CI**, a `kanarek/worker` **on-demand na krawędzi** (`/discover` + `/scrape` → `RSS→JSON`).

## ⚙️ Jak to działa

```text
                  feeds.yaml (53 źródła)
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

![License](https://www.shieldcn.dev/github/license/trvny/tvpi.svg?variant=branded&size=xm&mode=light&theme=neutral&font=jetbrains-mono)

## 📰 Mininewsy

<!--README_FEED:START-->
- [Marka Cashify od lipca funkcjonuje jako kantor kryptowalut online w oparciu o przepisy MiCA](https://pap-mediaroom.pl/biznes-i-finanse/marka-cashify-od-lipca-funkcjonuje-jako-kantor-kryptowalut-online-w-oparciu-o)
- [Erste Letnie Brzmienia 2026 ruszają już dzisiaj. Kraków otwiera letnią trasę przez pięć miast](https://pap-mediaroom.pl/biznes-i-finanse/erste-letnie-brzmienia-2026-ruszaja-juz-dzisiaj-krakow-otwiera-letnia-trase-przez)
- [Humanoid pozyskuje 152 mln USD przy wycenie na kwotę 1,35 mld USD po przeprowadzeniu rundy finansowania, stając się pierwszym europejskim jednorożcem wyspecjalizowanym w robotach…](https://pap-mediaroom.pl/biznes-i-finanse/humanoid-pozyskuje-152-mln-usd-przy-wycenie-na-kwote-135-mld-usd-po)
- [Fresha przyspiesza ekspansję w Europie, otwierając nowe biuro w Warszawie i powołując Macieja Walczewskiego na stanowisko dyrektora generalnego na Europę Wschodnią](https://pap-mediaroom.pl/biznes-i-finanse/fresha-przyspiesza-ekspansje-w-europie-otwierajac-nowe-biuro-w-warszawie-i)
- [Mikropoświadczenia - nowa waluta umiejętności](https://pap-mediaroom.pl/polityka-i-spoleczenstwo/mikroposwiadczenia-nowa-waluta-umiejetnosci)
<!--README_FEED:END-->

## 💬 Cytat z szuflady

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝Coincidence is God's way of remaining anonymous. — Albert Einstein❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->
