<div align="center">

# Feedseek 📡

**Samoodświeżające się feedy RSS/Atom dla stron, które nie udostępniają sensownego feedu.**

[![pages](https://img.shields.io/github/deployments/trvny/feedseek/github-pages?label=pages&logo=github&logoColor=white&style=flat-square)](https://trvny.github.io/feedseek/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feedseek/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&style=flat-square)](https://github.com/trvny/feedseek/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-92-d6541a?style=flat-square&logo=rss&logoColor=white)](feeds.yaml)
[![license](https://img.shields.io/github/license/trvny/feedseek?style=flat-square)](LICENSE)

[**📡 Feedy**](https://trvny.github.io/feedseek/) · [**📖 Czytnik**](https://trvny.github.io/feedseek/reader/) · [**🗂 Rejestr**](feeds.yaml)  
**Polski** · [English](README.md)

</div>

Feedseek wyszukuje lub buduje feedy, normalizuje wpisy, usuwa duplikaty i publikuje wynik przez GitHub Pages. Workflow aktualizuje źródła co dwie godziny, a awaria jednego serwisu nie powinna wywracać pozostałych.

## Jak to działa

```text
feeds.yaml (92 źródeł)
   │
   ▼
pobranie / parsowanie / normalizacja / deduplikacja
   │
   ├──▶ feeds/*.xml + *.json
   └──▶ strona + czytnik
             │
             ▼
     trvny.github.io/feedseek/
```

- Najpierw używamy działającego natywnego RSS/Atom, scraper jest planem B.
- Nie nadpisujemy ostatniego dobrego wyniku pustym feedem po awarii źródła.
- Identyfikatory wpisów pozostają stabilne, a duplikaty są usuwane po znormalizowanym URL/tytule.
- Wygenerowane `feeds/` i `cache/` są oddzielone od utrzymywanego kodu generatorów.

## Układ repozytorium

```text
feedseek/
├── feed_generators/   # generatory i wspólne narzędzia
├── feeds/             # wygenerowane XML/JSON
├── site/              # GitHub Pages + czytnik
├── feeds-proxy/       # pomocniczy Worker Cloudflare
└── .github/workflows/ # generowanie, publikacja i testy
```


### Kanarek się wyprowadził

Androidowy czytnik/player mieszka już w **[trvny/kanarek](https://github.com/trvny/kanarek)** — razem z Workerem, CI, CodeQL i ścieżką release/podpisywania. Mirror `kanarek/` i kopia feedów pod starymi adresami zostały stąd usunięte; `feeds/` to jedyne miejsce publikacji.

## Development

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

Pełny rejestr i notatki implementacyjne są w `README.md` i `docs/`.

## Licencja

MIT obejmuje oryginalny kod i dokumentację. Treść feedów, artykuły, obrazy, nazwy i znaki towarowe należą do ich właścicieli; patrz [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md).

## Mini news

<!--README_FEED:START-->
- [Bakteria w wodzie! Zjeżdżalnia na Basenach Letnich w Chrzanowie zamknięta - Przelom.pl](https://news.google.com/atom/articles/CBMiuwFBVV95cUxQUHJJa3pnenhMdWVWTngwS0E5NFN4YV9PVFduVHdoQWlkQkFmUlRkQ05Fa0k4SjNWeWtfMnloeUIxN2pEbV9laTlLNlREWEJJQ3VMRzlFdU1EcEQ1ZWNlLTBCQzc4LW93eTUwRzUya0g2bEpVeGltdGZmVFV6Vkk2VngxLURfTVA2Y2tmdFdDTWR4aFhnSmVxem9PY3M4U2FvX2NGWEJBNXhSb0xMM3NqaUZLanBSTE8yY0w0?oc=5)
- [iPhone Ultra w polskich sklepach? Nie mamy dobrych wiadomości](https://antyweb.pl/iphone-ultra-w-polskich-sklepach-nie-mamy-dobrych-wiadomosci)
- [Tajemnicza śmierć seniorki spod Oświęcimia. Niepokojące doniesienia - Fakt](https://news.google.com/atom/articles/CBMivwFBVV95cUxQZzRXYkRFMWJUbHpvUVZ3UmRDVHVBZzFBWUVNa2VuR2tWVzE5ekx5V0hoMlpnbjIwSmtULWE2Wjd3bVJtdlRlVmlaMjV6aDVhMTJ2NTVJMFNIRjVzWHFZV2hlQmRtTGZmODlNLVVsNXU2cXpGRlZaeHBBQ3lfUEJCY2lmSzdnaXJ3VUlkakJIN3NfYkNxbFNSV3hWRWk5SDNyTGRJMTMzWGZhcHIwMTZLVmVNcmM4cTRkWTJGWDZINA?oc=5)
- [Kennedy Center board votes to inscribe Trump's name on building](https://www.reuters.com/world/us/kennedy-center-board-votes-inscribe-trumps-name-building-2026-08-13/)
- [US could not verify Israeli warnings of Iran plots against Trump, sources say](https://www.reuters.com/world/middle-east/us-could-not-verify-israeli-warnings-iran-plots-against-trump-sources-say-2026-08-13/)
- [Sandisk forecasts mid-to-high-teens revenue growth through 2030](https://www.reuters.com/business/sandisk-forecasts-mid-to-high-teens-revenue-growth-through-2030-2026-08-13/)
<!--README_FEED:END-->

## Cytat z szuflady

<!--STARTS_HERE_QUOTE_README-->
<i>❝“Software is a gas; it expands to fill its container.”— Nathan Myhrvold❞</i>
<!--ENDS_HERE_QUOTE_README-->
