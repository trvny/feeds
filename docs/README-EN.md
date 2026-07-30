<div align="center">

<img src="../assets/banner.png" alt="trvny/feeds" width="820">

**Feedseek + Kanarek 🐤: feed production and consumption in one monorepo.**
Feedseek scrapes sites without RSS, generates Atom feeds and publishes them on GitHub Pages. Kanarek reads feeds in a native Android app and home-screen widgets.

[![pages](https://img.shields.io/github/deployments/trvny/feeds/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feeds/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-91-d6541a?style=flat-square&logo=rss&logoColor=white)](../feedseek/feeds.yaml)
[![last commit](https://img.shields.io/github/last-commit/trvny/feeds?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/commits/main)
[![license](https://img.shields.io/github/license/trvny/feeds?color=d6541a&style=flat-square)](../LICENSE)  
[**📡 Site**](https://trvny.github.io/feeds/) · [**📖 Reader**](https://trvny.github.io/feeds/reader/) · [**🗂 Feed registry**](../feedseek/README.md#feeds-)  
[Polski](../README.md) · **English**

</div>

---

## Feedseek + Kanarek 🐤

<div align="center">
<strong>🚪 Main lobby</strong>
</div>

<br>

<table>
<tr>
<td align="center" valign="top" width="50%">
<br>
<a href="../kanarek/"><img src="../assets/icons/kanarek.svg" width="112" height="112" alt="Kanarek"></a>
<h2><a href="../kanarek/">🐤 Kanarek</a></h2>
<strong>Read feeds and watch streams</strong>
<p>A native Android app and widgets with a news reader and background radio/IPTV player.</p>
<a href="../kanarek/"><strong>ENTER THE APP →</strong></a>
<br><br>
<a href="../kanarek/README.md">README</a> · <a href="../kanarek/app/">App</a> · <a href="../kanarek/worker/">Worker</a>
<br><br>
<img src="https://img.shields.io/badge/-Kotlin-7F52FF?style=flat&logo=kotlin&logoColor=white" alt="Kotlin">
<img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=fff&style=flat" alt="TypeScript">
<img src="https://img.shields.io/badge/-Worker-F38020?style=flat&logo=cloudflare&logoColor=white" alt="Cloudflare Worker">
<br><br>
</td>
<td align="center" valign="top" width="50%">
<br>
<a href="../feedseek/"><img src="../assets/icons/android-chrome-192x192.png" width="112" height="112" alt="Feedseek"></a>
<h2><a href="../feedseek/">📡 Feedseek</a></h2>
<strong>Produce and publish feeds</strong>
<p>RSS/Atom generators for sites without a useful native feed, refreshed every two hours and published on GitHub Pages.</p>
<a href="../feedseek/"><strong>ENTER THE FEEDS →</strong></a>
<br><br>
<a href="https://trvny.github.io/feeds/">Site</a> · <a href="https://trvny.github.io/feeds/reader/">Reader</a> · <a href="../feedseek/README.md#feeds-">Registry</a>
<br><br>
<img src="https://img.shields.io/badge/-Python-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=fff&style=flat" alt="uv">
<img src="https://img.shields.io/badge/-Pages-222222?style=flat&logo=githubpages&logoColor=white" alt="GitHub Pages">
<br><br>
</td>
</tr>
</table>

Both turn `site → Atom`, but from opposite sides. `feedseek` runs **in batches through CI**, while `kanarek/worker` works **on demand at the edge** (`/discover` + `/scrape` → `RSS→JSON`).

## ⚙️ How it works

```text
                  feeds.yaml (91 sources)
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

- **Failure isolation** — one broken source does not block the rest.
- **Hash-gated `updated`** — unchanged entries do not churn feed timestamps.
- **Deduplication** by normalized URL and title across sources.
- **Bot protection** — `curl_cffi` with Chrome impersonation handles Cloudflare, Akamai and DataDome.

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

## 📄 [License](../LICENSE)

![License](https://www.shieldcn.dev/github/license/trvny/tvpi.svg?variant=branded&size=xm&mode=light&theme=neutral&font=jetbrains-mono)