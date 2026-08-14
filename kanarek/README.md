**English** | [Polski](README_pl.md)

<div align="center">

<img src="https://raw.githubusercontent.com/trvny/feeds/refs/heads/main/assets/icons/kanarek.svg" alt="Kanarek" width="96">

# Kanarek

**Android news reader and widget with a background radio/IPTV player.**

[![android CI](https://img.shields.io/github/actions/workflow/status/trvny/feeds/android-ci.yml?label=legacy%20android%20CI&logo=android&logoColor=white&color=FFC107&style=flat-square)](https://github.com/trvny/feeds/actions/workflows/android-ci.yml)
[![worker CI](https://img.shields.io/github/actions/workflow/status/trvny/kanarek/worker-ci.yml?label=worker%20CI&logo=cloudflare&logoColor=white&color=FFC107&style=flat-square)](https://github.com/trvny/kanarek/actions/workflows/worker-ci.yml)
[![Kotlin](https://img.shields.io/badge/Kotlin-2.4.10-FFC107?style=flat-square&logo=kotlin&logoColor=white)](gradle/libs.versions.toml)
[![license](https://img.shields.io/github/license/trvny/feeds?color=FFC107&style=flat-square)](../LICENSE)

</div>

> **Moved:** active Kanarek development, Worker deployment and current documentation live in [trvny/kanarek](https://github.com/trvny/kanarek). This copy remains temporarily only for the old Android release/signing path.

Kanarek combines two tools in one native application:

- an RSS/Atom reader with an auto-rotating home-screen news widget,
- a background internet radio and IPTV player with its own transport-control widget.

An optional Cloudflare Worker accelerates fetching and provides additional network features. It is not required: ordinary RSS/Atom feeds can be parsed directly on the device.

## Highlights

### News

- resizable slideshow widget with manual navigation and per-widget settings,
- custom RSS 2.0 and Atom sources with OPML import and export,
- local search, source filters, and an optional headline-ranking mode,
- read state, saved articles, and optional offline clean text,
- clean article preview when a trusted Worker backend is configured,
- optional new-story notifications with quiet hours,
- last-known-good stories stay visible when an individual source temporarily fails.

### Radio and IPTV

- background Media3/ExoPlayer playback with system media controls,
- M3U/M3U8 import, export, and editing,
- radio, television, channel groups, favorites, and now-playing metadata,
- station discovery through the Radio Browser directory,
- missing channel logos filled through iptv-org and favicon fallbacks,
- playlist-provided `User-Agent` and `Referer` support,
- Google Cast in the `play` flavor; the `foss` flavor is Google-services-free.

## Install

Historical APKs are still published under the old [GitHub Releases](https://github.com/trvny/feeds/releases). Future releases belong to [trvny/kanarek](https://github.com/trvny/kanarek/releases).

- `play`: includes Google Cast support,
- `foss`: GMS-free build intended for FOSS and F-Droid environments.

The minimum supported system is Android 8.0 (API 26).

## Quick start

1. Install the preferred APK flavor.
2. Open Kanarek and choose **News** or **Radio & TV**.
3. Add RSS/Atom sources or import an OPML file.
4. Add stations manually, search the radio directory, or import an M3U/M3U8 playlist.
5. Long-press the Android home screen, open **Widgets**, and add either Kanarek widget.

The Backend URL may remain blank: regular feed refreshes stay on-device, while feed discovery, station search, and logo lookup can use Kanarek's built-in default service. Set your own Worker URL only when you want normal feed refreshes routed through that Worker or operator-controlled features such as clean-reader extraction and synchronized state.

## Documentation

Current documentation is maintained in [trvny/kanarek](https://github.com/trvny/kanarek/tree/main/docs). The files below are retained only with this temporary mirror:

- [Architecture](docs/ARCHITECTURE.md)
- [Build, tests, and CI](docs/DEVELOPMENT.md)
- [Cloudflare Worker and API](docs/WORKER.md)
- [Project history](docs/HISTORY.md)

## Development

Use [trvny/kanarek](https://github.com/trvny/kanarek) for development. This mirror should only be touched when the remaining signing/release cutover explicitly requires it.

## License

The project is available under the terms described in [LICENSE](../LICENSE).
