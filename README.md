<div align="center">

# Feedseek 📡

**Self-updating RSS/Atom feeds for sites that do not provide a useful feed.**

[![pages](https://img.shields.io/github/deployments/trvny/feeds/github-pages?label=pages&logo=github&logoColor=white&style=flat-square)](https://trvny.github.io/feeds/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-92-d6541a?style=flat-square&logo=rss&logoColor=white)](feedseek/feeds.yaml)
[![license](https://img.shields.io/github/license/trvny/feeds?style=flat-square)](LICENSE)

[**📡 Feeds**](https://trvny.github.io/feeds/) · [**📖 Reader**](https://trvny.github.io/feeds/reader/) · [**🗂 Registry**](feedseek/feeds.yaml)  
[Polski](README_pl.md) · **English**

</div>

Feedseek discovers or builds feeds, normalizes entries, deduplicates them and publishes the generated RSS/Atom output through GitHub Pages. The update workflow runs every two hours and isolates source failures so one broken site does not sink the rest.

## How it works

```text
feeds.yaml (92 sources)
   │
   ▼
fetch / parse / normalize / deduplicate
   │
   ├──▶ feeds/*.xml + *.json
   └──▶ static site + reader
             │
             ▼
     trvny.github.io/feeds/
```

- Prefer a usable native RSS/Atom feed before scraping.
- Preserve the last good output when a source fails or returns no usable entries.
- Keep entry identity stable and deduplicate by normalized URL/title.
- Generated `feeds/` and `cache/` data stays separate from maintained generators.

## Repository layout

```text
feeds/
├── feedseek/          # Feedseek source, registry, tests and generated output
├── feeds-proxy/       # supporting Cloudflare Worker
├── kanarek/           # temporary legacy mirror during the split
└── .github/workflows/ # generation, publishing and checks
```

`feedseek/` is becoming the repository root as the old monorepo layout is retired.

### Kanarek moved

The Android reader/player now lives in **[trvny/kanarek](https://github.com/trvny/kanarek)**. Its Cloudflare Worker is deployed from the new repository; the `kanarek/` subtree here remains frozen only until the release/signing path is cut over. New Kanarek development belongs in its own repository.

## Development

```bash
cd feedseek
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked feed_generators/validate_feeds.py
```

See `feedseek/README.md` and `feedseek/docs/` for the full feed registry and implementation notes.

## License

MIT for the original code and documentation. Feed content, articles, images, names and third-party trademarks remain the property of their respective owners; see [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md).

## Mini news

<!--README_FEED:START-->
- [Bakteria w wodzie! Zjeżdżalnia na Basenach Letnich w Chrzanowie zamknięta - Przelom.pl](https://news.google.com/atom/articles/CBMiuwFBVV95cUxQUHJJa3pnenhMdWVWTngwS0E5NFN4YV9PVFduVHdoQWlkQkFmUlRkQ05Fa0k4SjNWeWtfMnloeUIxN2pEbV9laTlLNlREWEJJQ3VMRzlFdU1EcEQ1ZWNlLTBCQzc4LW93eTUwRzUya0g2bEpVeGltdGZmVFV6Vkk2VngxLURfTVA2Y2tmdFdDTWR4aFhnSmVxem9PY3M4U2FvX2NGWEJBNXhSb0xMM3NqaUZLanBSTE8yY0w0?oc=5)
- [iPhone Ultra w polskich sklepach? Nie mamy dobrych wiadomości](https://antyweb.pl/iphone-ultra-w-polskich-sklepach-nie-mamy-dobrych-wiadomosci)
- [Tajemnicza śmierć seniorki spod Oświęcimia. Niepokojące doniesienia - Fakt](https://news.google.com/atom/articles/CBMivwFBVV95cUxQZzRXYkRFMWJUbHpvUVZ3UmRDVHVBZzFBWUVNa2VuR2tWVzE5ekx5V0hoMlpnbjIwSmtULWE2Wjd3bVJtdlRlVmlaMjV6aDVhMTJ2NTVJMFNIRjVzWHFZV2hlQmRtTGZmODlNLVVsNXU2cXpGRlZaeHBBQ3lfUEJCY2lmSzdnaXJ3VUlkakJIN3NfYkNxbFNSV3hWRWk5SDNyTGRJMTMzWGZhcHIwMTZLVmVNcmM4cTRkWTJGWDZINA?oc=5)
- [Kennedy Center board votes to inscribe Trump's name on building](https://www.reuters.com/world/us/kennedy-center-board-votes-inscribe-trumps-name-building-2026-08-13/)
- [US could not verify Israeli warnings of Iran plots against Trump, sources say](https://www.reuters.com/world/middle-east/us-could-not-verify-israeli-warnings-iran-plots-against-trump-sources-say-2026-08-13/)
- [Sandisk forecasts mid-to-high-teens revenue growth through 2030](https://www.reuters.com/business/sandisk-forecasts-mid-to-high-teens-revenue-growth-through-2030-2026-08-13/)
<!--README_FEED:END-->

## Quote from the drawer

<!--STARTS_HERE_QUOTE_README-->
<i>❝“Software is a gas; it expands to fill its container.”— Nathan Myhrvold❞</i>
<!--ENDS_HERE_QUOTE_README-->
