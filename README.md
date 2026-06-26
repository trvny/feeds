# travino/feeds — monorepo

Producent i konsument feedów w jednym repo.

| katalog | co to | stack |
|---|---|---|
| [`feedseek/`](feedseek/) | generatory RSS/Atom — scrapują strony bez feedów, CI co 2 h, publikacja na GitHub Pages | Python (uv) |
| [`feedget/`](feedget/) | natywny widget + apka Android do czytania feedów, plus worker RSS→JSON na krawędzi | Kotlin/Compose · Cloudflare Worker (TS) |

Oba scrapują „strona → Atom": `feedseek` wsadowo w CI, `feedget/worker` on-demand
na krawędzi (`/discover` + `/scrape`). Historia obu projektów zachowana.

Workflowy obu projektów żyją w `.github/workflows/` (ścieżki przez `working-directory`).
