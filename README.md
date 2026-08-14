<div align="center">

<img src="assets/banner-feedseek.svg" alt="Feedseek" width="960">

# Feedseek 📡

**Self-updating RSS/Atom feeds for sites that do not provide a useful native feed.**

[![pages](https://img.shields.io/github/deployments/trvny/feedseek/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feedseek/)
[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feedseek/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feedseek/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-92-d6541a?style=flat-square&logo=rss&logoColor=white)](feeds.yaml)
[![last commit](https://img.shields.io/github/last-commit/trvny/feedseek?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feedseek/commits/main)
[![license](https://img.shields.io/github/license/trvny/feedseek?color=d6541a&style=flat-square)](LICENSE)
<a href="https://deepwiki.com/trvny/feedseek"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki"></a>
<a href="https://doi.org/10.5281/zenodo.21868714"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.21868714.svg" alt="DOI"></a>

[**📡 Feeds**](https://trvny.github.io/feedseek/) · [**📖 Reader**](https://trvny.github.io/feedseek/reader/) · [**🗂 Registry**](feeds.yaml) · [**🧭 Internals**](docs/architecture.md)  
[Polski](README_pl.md) · **English**

</div>

Feedseek discovers or builds feeds, normalizes entries, deduplicates them and publishes the generated output through GitHub Pages. The scheduled workflow refreshes sources every two hours, while source failures are isolated so one broken site does not sink the rest.

Native RSS/Atom is preferred whenever it is useful; scraping and API adapters fill the gaps. A failed or empty fetch does not replace the last known-good feed.

## Feeds

- **Browse and subscribe:** [trvny.github.io/feedseek](https://trvny.github.io/feedseek/)
- **Registry:** [`feeds.yaml`](feeds.yaml)
- **Generated XML/JSON:** [`feeds/`](feeds/)
- **Source inventory:** [`docs/sources.md`](docs/sources.md)
- **Per-feed notes:** [`docs/feeds.md`](docs/feeds.md)

## Documentation

- [Pipeline, local usage and repository layout](docs/architecture.md)
- [Per-feed sources and design trade-offs](docs/feeds.md)
- [Cache behavior and maintenance](docs/cache.md)
- [Generated source inventory](docs/sources.md)

The Android reader/player for these feeds lives in **[trvny/kanarek](https://github.com/trvny/kanarek)**.

## License

MIT covers the original code and documentation. Feed content, articles, images, names and third-party trademarks remain the property of their respective owners; see [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md).

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

## Other stuff

[![kanarek](https://github.com/trvny/.github/blob/main/assets/profile/pin-kanarek.svg)](https://github.com/trvny/kanarek) [![tvpi](https://github.com/trvny/.github/blob/main/assets/profile/pin-tvpi.svg)](https://github.com/trvny/tvpi)
