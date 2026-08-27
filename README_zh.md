<div align="center">

<img src="assets/banner-feedseek.svg" alt="Feedseek" width="960">

<img src="assets/icons/favicon-96x96.png" alt="Feedseek" width="72">

# Feedseek 📡

**为缺少实用原生 feed 的网站生成并自动更新 RSS/Atom。**

[![feeds CI](https://img.shields.io/github/actions/workflow/status/trvny/feedseek/update-feeds.yml?label=feeds%20CI&logo=githubactions&logoColor=white&color=d6541a&style=flat-square)](https://github.com/trvny/feedseek/actions/workflows/update-feeds.yml)
[![feeds](https://img.shields.io/badge/feeds-95-d6541a?style=flat-square&logo=rss&logoColor=white)](feeds.yaml)
[![pages](https://img.shields.io/github/deployments/trvny/feedseek/github-pages?label=pages&logo=github&logoColor=white&color=d6541a&style=flat-square)](https://trvny.github.io/feedseek/)
[![last commit](https://img.shields.io/github/last-commit/trvny/feedseek?color=d6541a&logo=git&logoColor=white&style=flat-square)](https://github.com/trvny/feedseek/commits/main)
[![license](https://img.shields.io/github/license/trvny/feedseek?color=d6541a&style=flat-square)](LICENSE)  
<a href="https://deepwiki.com/trvny/feedseek"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki"></a>

[![GitHubPages](https://img.shields.io/badge/github.io-222222?style=for-the-badge&logo=githubpages&logoColor=white)](https://trvny.github.io/feedseek/)  
![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![uv](https://img.shields.io/badge/uv-DE5FE9?style=flat-square&logo=uv&logoColor=white)

[Polski](README_pl.md) · [English](README.md) · **简体中文**  

[**📡 Feeds**](https://trvny.github.io/feedseek/) · [**📖 Reader**](https://trvny.github.io/feedseek/reader/) · [**🗂 Registry**](feeds.yaml) · [**🧭 Internals**](docs/architecture.md)  

</div>

Feedseek 会发现已有 feed，或在必要时构建新的 feed；随后统一条目格式、去重，并通过 GitHub Pages 发布结果。计划工作流每两小时刷新来源，同时把单个来源的故障隔离开，避免一个网站出问题拖垮全部 feed。

只要原生 RSS/Atom 足够好，就优先使用原生源；其余情况由抓取器和 API adapter 补齐。失败或空的抓取结果不会覆盖最后一次成功生成的 feed。

灵感来自 [Olshansk/rss-feeds](https://github.com/Olshansk/rss-feeds) 与 [rss-bridge/rss-bridge](https://github.com/rss-bridge/rss-bridge)。

## Feeds ![XML](https://img.shields.io/badge/XML-005FAD?logo=xml&logoColor=fff&style=plastic)

Feed 列表会持续变化，因此中文 README 不复制整张动态表。当前完整清单请直接查看：

- [Feeds 页面](https://trvny.github.io/feedseek/)
- [源注册表 `feeds.yaml`](feeds.yaml)
- [自动生成的来源清单](docs/sources.md)

每个输出 feed 都可以从 GitHub Pages 或仓库中的 `feeds/` 目录访问。网站 favicon 在渲染时从 Google favicon 服务或 DuckDuckGo 获取，不会把这些图片提交进仓库。

## 文档

- [流水线、enrichment、本地使用方式与仓库结构](docs/architecture.md)
- [各 feed 的来源与设计取舍](docs/feeds.md)
- [缓存行为与维护](docs/cache.md)
- [自动生成的来源清单](docs/sources.md)

这些 feed 对应的 Android 阅读器/播放器位于 **[trvny/kanarek](https://github.com/trvny/kanarek)**。

## [许可证](LICENSE)

[![License](https://www.shieldcn.dev/github/license/trvny/feedseek.svg?variant=branded&size=xm&mode=light&theme=neutral&font=jetbrains-mono)](https://spdx.org/licenses/MIT)    [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md)

## 📰 小新闻

<!--README_FEED:START-->
- [Urban Word of the Day — grebo](https://www.urbandictionary.com/define.php?term=grebo&defid=1975218)
- [How to Engage with New Media: A Strategic Guide for Nonprofit Organizations](https://carnegieendowment.org/research/2026/08/how-to-engage-with-new-media-a-strategic-guide-for-nonprofit-organizations)
- [Urban Word of the Day — board chow](https://www.urbandictionary.com/define.php?term=board%20chow&defid=2568411)
- [Wielkie czyszczenie na Netflix. 30 filmów zniknie za kilka dni](https://antyweb.pl/wielkie-czyszczenie-na-netflix-30-filmow-zniknie-za-kilka-dni)
- [Jesienne porządki z Parkside. Szybsza praca w ogrodzie i domu](https://antyweb.pl/jesienne-porzadki-z-parkside-szybsza-praca-w-ogrodzie-i-domu)
- [Weekend w Chrzanowie i okolicy. Zobacz najciekawsze imprezy i wydarzenia 28 - 30 sierpnia - Gazeta Krakowska](https://news.google.com/atom/articles/CBMiywFBVV95cUxNbkxZVXZYZW92ZzRlSFh4UElqdUxZQTN4S3ZYbFU5d09XaGFRN3l4ZVVwSXBkUU5fZXBLZkFpMnMteE5tRTFDbUJxQ0dGeC1aQnRoQmhtd25iaEt5QWlrR2hGVjNFUk91WEpfZldsRkFvR25nY0lvQ2YtSF9ZSzZqVXlDYjBjMFZ6MVB0OVFUSjluRVgtVS0zRW1YaDhGcll4NTRPWVpSRHdqYWlyUnV4bnBxTEdlMGp4V2NZVWY0bkN5S1ZzY3hrbk1Pcw?oc=5)
<!--README_FEED:END-->

## 💬 抽屉里的引语

<!-- markdownlint-disable MD033 -->
<!--STARTS_HERE_QUOTE_README-->
<i>❝The worst breach of U.S. military computers in history happened when someone picked up a memory stick (infected by a foreign intelligence agency) they found in the parking lot and plugged it into their computer, which was attached to United States Central Command.❞</i>
<!--ENDS_HERE_QUOTE_README-->
<!-- markdownlint-enable MD033 -->

## 其他项目

[![kanarek](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-kanarek.svg)](https://github.com/trvny/kanarek) [![tvpi](https://raw.githubusercontent.com/trvny/.github/main/assets/profile/pin-tvpi.svg)](https://github.com/trvny/tvpi)
