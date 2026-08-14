<div align="center">

# Feedseek 📡

**Self-updating RSS/Atom feeds for sites that do not provide a useful feed.**

[![pages](https://img.shields.io/github/deployments/trvny/feeds/github-pages?label=pages&logo=github&logoColor=white&style=flat-square)](https://trvny.github.io/feeds/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/update-feeds.yml)
[![license](https://img.shields.io/github/license/trvny/feeds?style=flat-square)](LICENSE)

[**📡 Feeds**](https://trvny.github.io/feeds/) · [**📖 Reader**](https://trvny.github.io/feeds/reader/) · [**🗂 Registry**](feedseek/feeds.yaml)  
[Polski](README_pl.md) · **English**

</div>

Feedseek discovers or builds feeds, normalizes entries, deduplicates them and publishes the generated RSS/Atom output through GitHub Pages. The update workflow runs every two hours and isolates source failures so one broken site does not sink the rest.

## How it works

```text
feeds.yaml
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

The Android reader/player now lives in **[trvny/kanarek](https://github.com/trvny/kanarek)**. The `kanarek/` subtree here is frozen migration baggage while the remaining release/Cloudflare deployment secrets are cut over; new Kanarek development belongs in its own repository.

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
<!--README_FEED:END-->

## Quote from the drawer

<!--STARTS_HERE_QUOTE_README-->
<!--ENDS_HERE_QUOTE_README-->
