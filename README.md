<div align="center">

<img src="assets/banner.png" alt="trvny/feeds" width="820">

**Producent i konsument feedów w jednym monorepo.** Scrapuje strony bez RSS, generuje Atom,
publikuje na GitHub Pages i czyta — w przeglądarce albo natywnym widżecie na Androida.

[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/update-feeds.yml)
[![pages](https://img.shields.io/github/deployments/trvny/feeds/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feeds/)
[![feeds](https://img.shields.io/badge/feeds-53-d6541a?style=flat-square&logo=rss&logoColor=white)](feedseek/feeds.yaml)
[![last commit](https://img.shields.io/github/last-commit/trvny/feeds?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/commits/main)
[![license](https://img.shields.io/github/license/trvny/feeds?color=d6541a&style=flat-square)](LICENSE)

[**📡 Strona**](https://trvny.github.io/feeds/) · [**📖 Czytnik**](https://trvny.github.io/feeds/reader/) · [**🗂 Rejestr feedów**](feedseek/feeds.yaml)

</div>

---

## 📦 Co siedzi w środku

| katalog | co to robi | stack |
|---|---|---|
| 🛰️ [`feedseek/`](feedseek/) | generatory **RSS/Atom** — scrapują strony bez natywnego feeda, CI odświeża co 2 h, wynik leci na GitHub Pages + statyczny czytnik OPML | ![Python](https://img.shields.io/badge/-Python-3776AB?style=flat-square&logo=python&logoColor=white) ![uv Badge](https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=fff&style=flat-square) |
| 📱 [`feedget/`](feedget/) | natywny **widżet + apka na Androida** do czytania feedów, plus worker `RSS→JSON` na krawędzi | ![Kotlin](https://img.shields.io/badge/-Kotlin-7F52FF?style=flat-square&logo=kotlin&logoColor=white) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=fff&style=flat-square) ![Cloudflare](https://img.shields.io/badge/-Worker-F38020?style=flat-square&logo=cloudflare&logoColor=white) |

Oba robią to samo — `strona → Atom` — tylko z dwóch stron:
`feedseek` **wsadowo w CI**, `feedget/worker` **on-demand na krawędzi** (`/discover` + `/scrape`).

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
            feedget — widżet/apka Android  ◀──  worker (RSS→JSON)
```

- **Izolacja błędów** — jedno padnięte źródło nie blokuje reszty.
- **Hash-gated `updated`** — feed nie „mieli" gdy wpis się nie zmienił.
- **Dedup** po znormalizowanym URL-u i tytule (cross-source).
- **Bot-protection** — `curl_cffi` + impersonacja Chrome ogarnia Cloudflare/Akamai/DataDome.

## 🚀 Szybki start

```bash
# wygeneruj pojedynczy feed lokalnie
cd feedseek/feed_generators
RSS_REPO_SLUG=trvny/feeds python3 <generator>.py --full

# waliduj wszystkie XML-e
python3 validate_feeds.py
```

Dodanie nowego feeda: generator w `feedseek/feed_generators/`, wpis w
[`feedseek/feeds.yaml`](feedseek/feeds.yaml), cel w `Makefile` — resztę (XML + cache)
dorobi CI przy następnym przebiegu.

## 🗂 Struktura

```text
feeds/
├── feedseek/          # generatory RSS/Atom + statyczny czytnik
│   ├── feed_generators/
│   ├── feeds.yaml     # rejestr źródeł
│   ├── feeds/         # wygenerowane XML-e (CI)
│   └── site/          # build_site.py + reader.html
├── feedget/           # apka Android + Cloudflare Worker
└── .github/workflows/ # CI obu projektów (przez working-directory)
```

· historia obu projektów (`feeds` + `feedy`) zachowana po konsolidacji do monorepo.

## 📄 Licencja

[MIT](LICENSE)
