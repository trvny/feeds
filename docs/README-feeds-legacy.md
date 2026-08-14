<div align="center">

<img src="assets/banner.png" alt="trvny/feeds" width="820">

**Feedseek + Kanarek 🐤: feed production and consumption in one monorepo.**
Feedseek scrapes sites without RSS, generates Atom feeds and publishes them on GitHub Pages. Kanarek reads feeds in a native Android app and home-screen widgets.

[![pages](https://img.shields.io/github/deployments/trvny/feeds/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feeds/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-92-d6541a?style=flat-square&logo=rss&logoColor=white)](feedseek/feeds.yaml)
[![last commit](https://img.shields.io/github/last-commit/trvny/feeds?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/commits/main)
[![license](https://img.shields.io/github/license/trvny/feeds?color=d6541a&style=flat-square)](LICENSE)
<a href="https://deepwiki.com/trvny/feeds"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki"></a> <a href="https://doi.org/10.5281/zenodo.21868714"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.21868714.svg" alt="DOI"></a>  
[**📡 Site**](https://trvny.github.io/feeds/) · [**📖 Reader**](https://trvny.github.io/feeds/reader/) · [**🗂 Feed registry**](feedseek/README.md#feeds-)  
[Polski](README_pl.md) · **English**

</div>

---

# Feedseek + Kanarek 🐤

<div align="center">
<strong>🚪 Main lobby</strong>
</div>

<br>

<table>
<tr>
<td align="center" valign="top" width="50%">
<br>
<a href="kanarek/"><img src="assets/icons/kanarek.svg" width="112" height="112" alt="Kanarek"></a>
<h2><a href="kanarek/">🐤 Kanarek</a></h2>
<strong>Read feeds and watch streams</strong>
<p>A native Android app and widgets with a news reader and radio/IPTV player.</p>
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
<strong>Produce and publish feeds</strong>
<p>RSS/Atom generators refreshed every two hours and published on GitHub Pages.</p>
<a href="feedseek#rss--atom-feeds-"><strong>FEEDSEEK →</strong></a>
<br><br>
<a href="feedseek/README.md#feeds-">Registry</a> · <a href="https://trvny.github.io/feeds/">Site</a> · <a href="https://trvny.github.io/feeds/reader/">Reader</a>
<br><br>
<img src="https://img.shields.io/badge/-Python-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=fff&style=flat" alt="uv">
<a href="https://github.com/trvny/feeds"> <img src="https://img.shields.io/badge/-Pages-222222?style=flat&logo=githubpages&logoColor=white" alt="GitHub Pages"></a>
<br><br>
</td>
</tr>
</table>

Both do the same thing, `site → Atom`, but from opposite sides. `feedseek` runs **in batches through CI**, while `kanarek/worker` works **on demand at the edge** (`/discover` + `/scrape` → `RSS→JSON`).

## ⚙️ How it works

```text
                  feeds.yaml (92 sources)
                         │
   ┌─────────────────────┴─────────────────────┐
   │  feedseek — GitHub Actions, every 2 h      │
   │  scrape → parse → dedup → Atom XML          │
   └─────────────────────┬─────────────────────┘
                         │  publish
                         ▼
          trvny.github.io/feeds/  ──▶  /reader/  (OPML reader)
                         │
                         │  consumption
                         ▼
          kanarek — Android app/widget  ◀──  worker (RSS→JSON)
```

- **Failure isolation**: one broken source does not block the rest.
- **Hash-gated `updated`**: unchanged entries do not churn feed timestamps.
- **Deduplication** by normalized URL and title across sources.
- **Bot protection**: `curl_cffi` with Chrome impersonation handles Cloudflare, Akamai and DataDome.

## 🗂 Structure

```text
feeds/
├── feedseek/          # RSS/Atom generators + static reader
│   ├── feed_generators/
│   ├── feeds.yaml     # source registry
│   ├── feeds/         # generated XML files (CI)
│   └── site/          # build_site.py + reader.html
├── kanarek/           # Android app + Cloudflare Worker
└── .github/workflows/ # CI for both projects via working-directory
```

The history of both original projects (`feeds` + `kanarek`) was preserved during consolidation into the monorepo.

## 📄 [License](LICENSE)

[![License](https://www.shieldcn.dev/github/license/trvny/feeds.svg?variant=branded&size=xm&mode=light&theme=neutral&font=jetbrains-mono)](https://spdx.org/licenses/MIT)

The MIT license covers the original code and documentation. Feed content, articles,
images, streams, names and third-party trademarks remain the property of their
respective owners: [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md).

## 📰 Mini news

<!--README_FEED:START-->
- [Bakteria w wodzie! Zjeżdżalnia na Basenach Letnich w Chrzanowie zamknięta - Przelom.pl](https://news.google.com/atom/articles/CBMiuwFBVV95cUxQUHJJa3pnenhMdWVWTngwS0E5NFN4YV9PVFduVHdoQWlkQkFmUlRkQ05Fa0k4SjNWeWtfMnloeUIxN2pEbV9laTlLNlREWEJJQ3VMRzlFdU1EcEQ1ZWNlLTBCQzc4LW93eTUwRzUya0g2bEpVeGltdGZmVFV6Vkk2VngxLURfTVA2Y2tmdFdDTWR4aFhnSmVxem9PY3M4U2FvX2NGWEJBNXhSb0xMM3NqaUZLanBSTE8yY0w0?oc=5)
- [iPhone Ultra w polskich sklepach? Nie mamy dobrych wiadomości](https://antyweb.pl/iphone-ultra-w-polskich-sklepach-nie-mamy-dobrych-wiadomosci)
- [Tajemnicza śmierć seniorki spod Oświęcimia. Niepokojące doniesienia - Fakt](https://news.google.com/atom/articles/CBMivwFBVV95cUxQZzRXYkRFMWJUbHpvUVZ3UmRDVHVBZzFBWUVNa2VuR2tWVzE5ekx5V0hoMlpnbjIwSmtULWE2Wjd3bVJtdlRlVmlaMjV6aDVhMTJ2NTVJMFNIRjVzWHFZV2hlQmRtTGZmODlNLVVsNXU2cXpGRlZaeHBBQ3lfUEJCY2lmSzdnaXJ3VUlkakJIN3NfYkNxbFNSV3hWRWk5SDNyTGRJMTMzWGZhcHIwMTZLVmVNcmM4cTRkWTJGWDZINA?oc=5)
- [Kennedy Center board votes to inscribe Trump's name on building](https://www.reuters.com/world/us/kennedy-center-board-votes-inscribe-trumps-name-building-2026-08-13/)
- [US could not verify Israeli warnings of Iran plots against Trump, sources say](https://www.reuters.com/world/middle-east/us-could-not-verify-israeli-warnings-iran-plots-against-trump-sources-say-2026-08-13/)
- [Sandisk forecasts mid-to-high-teens revenue growth through 2030](https://www.reuters.com/business/sandisk-forecasts-mid-to-high-teens-revenue-growth-through-2030-2026-08-13/)
<!--README_FEED:END-->

## 💬 Quote from the drawer

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝“Software is a gas; it expands to fill its container.”— Nathan Myhrvold❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->


# Other stuff

[![tvpi](https://github-stats-extended.vercel.app/api/pin?username=trvny&repo=trvny%2Ftvpi&theme=yeblu)](https://github.com/trvny/tvpi)
