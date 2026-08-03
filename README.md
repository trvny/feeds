<div align="center">

<img src="assets/banner.png" alt="trvny/feeds" width="820">

**Feedseek + Kanarek 🐤: feed production and consumption in one monorepo.**
Feedseek scrapes sites without RSS, generates Atom feeds and publishes them on GitHub Pages. Kanarek reads feeds in a native Android app and home-screen widgets.

[![pages](https://img.shields.io/github/deployments/trvny/feeds/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feeds/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-92-d6541a?style=flat-square&logo=rss&logoColor=white)](feedseek/feeds.yaml)
[![last commit](https://img.shields.io/github/last-commit/trvny/feeds?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/commits/main)
[![license](https://img.shields.io/github/license/trvny/feeds?color=d6541a&style=flat-square)](LICENSE)
<a href="https://deepwiki.com/trvny/feeds"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki"></a>  
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
- ["To nie będzie bimbrownia". Inwestor stanowczo odpowiada mieszkańcom - Przelom.pl](https://news.google.com/atom/articles/CBMisgFBVV95cUxPeWJIRnpQaW4wUUhxV0lGSE0xdklPZ0hleGxZYVhlQUdvcHdzSzFJR2NjRHlsVmJWVFpRa1J3X0lER3BOR3JVSkRodl9QMzN2UHlleWtZRlRyT2p3UU9OYkZQNUtDX3ltMUZTc3VWY1ZxRTZNbU1mbFB1bXdnbDRORC1ZX2hsYzd1eHNYVW9Tb3pzRlYtaEp5WWZLM254V09OZDZrdEw4MWlyVFBZN3NtTjFR?oc=5)
- [FIFA has scrapped $20 billion World Cup sell-off plan, New York Post reports](https://news.google.com/rss/articles/CBMiuwFBVV95cUxNbXdUU2FsekNqTWc1TWdVd09xUXpTTXNScnVjczNNcGVzbERTWmVwOWNGMGlOd2J2dWQwem4yOU4yb0Y0VThodnEzcWJTRjRBZjI2RUhsNDdNXzNtMmVCa2tBNVp2U3lraTE2ZjFObG9WYThxaGJBWVpTSjE2YV9TTnAwNWVXT0d0MjVTcWJlRUs2bjN5bUJzVEU0bG5NNlZ0X1pwSUZPRTF3TjN2QjNWWDRGeWR6SzhTd1pn?oc=5)
- [US bars imports from 43 more companies over China's alleged forced labor involving Uyghurs](https://news.google.com/rss/articles/CBMiwgFBVV95cUxOSzRCdVNpdm4wZldHbEt1WTduUnNQTnh6N2didEJVLTQ5RjBYSGtQemRacGtrRFdjOUt0Ukh0X0lyLS03cDA2YVRWd3piM3V6N1VZZkprcU52QzBJWW10XzRvTnZQUnBwTURxbkJabXduaV82Q0wyd2xWQW5DNERZM2poRlAtM2xmV0tNSGt4LWc0RkVhSTRSQktmeWRfMjlrR0pGQW93Nm9OUnoteEU4b3RQSWxNN2NZaEwxbHdSYUVQdw?oc=5)
- [Exxon, Chevron warn of continued high fuel prices from Iran war](https://news.google.com/rss/articles/CBMiqgFBVV95cUxNMjdEbTVuZzlMdmNabW90dk04NEdXMUdBUFNzR2FpcDJYZE9RWnlQdXFNV1NtZkVWZ2J1M0dzTXhwVGJFYlNsUkp2d211bFB4eXRQQXk3RWJ5c1hBZ1BUYnF3VXNiSzFweUpEaktkOUsyLVBISHlZY2dneU5RTnkyeXNTejVUZlpJa3hURjFsMGZkSVUxVUw4QUg0N3pqZjg0UlZVdTNGSG9kZw?oc=5)
- [US, Israel planning to bombard energy-related targets in Iran, CBS reports](https://news.google.com/rss/articles/CBMivAFBVV95cUxQNXpvc21vbVJNVjc3NWg0ZnppblFCM3dmQXFVVTNhc1A1YkhoSTA4Q0tFZ0hQbFN0WUdtRlBza0J1dzBFenk3NW85U0ZWLXA0N1llLVFCNUdmRy1JU2NzOTE2bTFTdmlYUXdZNUphTE1uSE84ZXA0WjBYNkUtX2NBbWpUS08taFBRc0xNdGtoV0F6SHpfdU15dFB1WllYNnVwQkxFWThYelpLZnQyRml2Q0MwLVZ2blFDWl9raA?oc=5)
- [EXCLUSIVE: OpenAI finds evidence other AI agents escaped containment as it widens hacking probe](https://news.google.com/rss/articles/CBMivAFBVV95cUxQYTc2SUhrNmVER0NvNW9nZHBwbklFMlA0eTNSRFZETXpfSWpVYU1wOUhaMDRLUnRVSEhtRzByeEktX2FEX1ZzaThNMnpZMW9JdVZDZkVRTEQ4UjdlakFPVXZTUjZaM2JOUkhpN1BxeEU4bWJuSjNkUldBNXRVWDkyYWVXVUlKM0VEZU5wZklfX2FJRkQ0bmVybTIyY0xpbHd6aGtIVmZ3YU5ocGdsdFlNeXdOQlBXOUsyZnZtZA?oc=5)
<!--README_FEED:END-->

## 💬 Quote from the drawer

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝The person I like most is the one who points out my defects. — Umar ibn Al-Khattāb (R.A)❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->


# Other stuff

[![tvpi](https://github-stats-extended.vercel.app/api/pin?username=trvny&repo=trvny%2Ftvpi&theme=yeblu)](https://github.com/trvny/tvpi)
