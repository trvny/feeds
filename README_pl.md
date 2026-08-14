<div align="center">

# Feedseek 📡

**Samoodświeżające się feedy RSS/Atom dla stron, które nie udostępniają sensownego feedu.**

[![pages](https://img.shields.io/github/deployments/trvny/feeds/github-pages?label=pages&logo=github&logoColor=white&style=flat-square)](https://trvny.github.io/feeds/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/update-feeds.yml)
[![license](https://img.shields.io/github/license/trvny/feeds?style=flat-square)](LICENSE)

[**📡 Feedy**](https://trvny.github.io/feeds/) · [**📖 Czytnik**](https://trvny.github.io/feeds/reader/) · [**🗂 Rejestr**](feedseek/feeds.yaml)  
**Polski** · [English](README.md)

</div>

Feedseek wyszukuje lub buduje feedy, normalizuje wpisy, usuwa duplikaty i publikuje wynik przez GitHub Pages. Workflow aktualizuje źródła co dwie godziny, a awaria jednego serwisu nie powinna wywracać pozostałych.

## Jak to działa

```text
feeds.yaml
   │
   ▼
pobranie / parsowanie / normalizacja / deduplikacja
   │
   ├──▶ feeds/*.xml + *.json
   └──▶ strona + czytnik
             │
             ▼
     trvny.github.io/feeds/
```

- Najpierw używamy działającego natywnego RSS/Atom, scraper jest planem B.
- Nie nadpisujemy ostatniego dobrego wyniku pustym feedem po awarii źródła.
- Identyfikatory wpisów pozostają stabilne, a duplikaty są usuwane po znormalizowanym URL/tytule.
- Wygenerowane `feeds/` i `cache/` są oddzielone od utrzymywanego kodu generatorów.

## Układ repozytorium

```text
feeds/
├── feedseek/          # kod Feedseek, rejestr, testy i wygenerowane wyniki
├── feeds-proxy/       # pomocniczy Worker Cloudflare
├── kanarek/           # tymczasowa kopia na czas rozdzielania repo
└── .github/workflows/ # generowanie, publikacja i testy
```

`feedseek/` docelowo staje się rootem repo wraz z wygaszaniem starego układu monorepo.

### Kanarek się wyprowadził

Androidowy czytnik/player mieszka już w **[trvny/kanarek](https://github.com/trvny/kanarek)**. Katalog `kanarek/` tutaj jest zamrożoną pozostałością migracji do czasu przepięcia sekretów release/Cloudflare. Nowe prace nad Kanarkiem robimy w jego własnym repo.

## Development

```bash
cd feedseek
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

Pełny rejestr i notatki implementacyjne są w `feedseek/README.md` i `feedseek/docs/`.

## Licencja

MIT obejmuje oryginalny kod i dokumentację. Treść feedów, artykuły, obrazy, nazwy i znaki towarowe należą do ich właścicieli; patrz [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md).

## Mini news

<!--README_FEED:START-->
<!--README_FEED:END-->

## Cytat z szuflady

<!--STARTS_HERE_QUOTE_README-->
<!--ENDS_HERE_QUOTE_README-->
