#!/usr/bin/env python3
"""Report published feeds whose <icon> does not actually resolve to an image.

Why this exists: every feed declares an <icon>, but nothing ever checked that
the URL answers. On 11.08.2026 seventeen of ninety were dead — some 404, some
403, some a 200 with an empty body — and the failure is invisible from inside
the repo: the XML looks complete, validate_feeds.py passes, and the only symptom
is a letter avatar in the reader. The site does not show it either, because
site/build_site.py carries its own fallback chain in the browser, so a feed can
look fine there and blank in a reader.

Deliberately a manual tool, not part of validate_feeds.py: it needs the network
and talks to third-party icon proxies, so wiring it into the scheduled run would
let someone else's outage fail a build that produced perfectly good feeds.

    python tools/check_feed_icons.py            # report every feed
    python tools/check_feed_icons.py --broken   # only the ones to fix

Exits 1 when something is broken, so it is still usable as a manual gate.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
ATOM = "{http://www.w3.org/2005/Atom}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    )
}
# Enough bytes to tell a real image from an error page without pulling the file.
SNIFF_BYTES = 1024
MIN_IMAGE_BYTES = 40


def declared_icon(xml_path: Path) -> str:
    try:
        return (ET.parse(xml_path).getroot().findtext(f"{ATOM}icon") or "").strip()
    except ET.ParseError:
        return ""


def probe(url: str) -> tuple[bool, str]:
    """Return (ok, note). An HTML body counts as broken: several sites answer
    200 with their 404 page, which a status check alone would call healthy."""
    if not url:
        return False, "brak <icon>"
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=15, stream=True, allow_redirects=True
        )
        content_type = (response.headers.get("content-type") or "").split(";")[0].lower()
        body = next(response.iter_content(SNIFF_BYTES), b"")
        response.close()
    except requests.RequestException as exc:
        return False, type(exc).__name__

    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    if "html" in content_type or body[:15].lower().lstrip().startswith(b"<!doctype htm"):
        return False, "strona HTML zamiast obrazka"
    if len(body) < MIN_IMAGE_BYTES:
        return False, f"pusta odpowiedz ({len(body)} B)"
    return True, f"{content_type or 'nieznany typ'}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--broken", action="store_true", help="list only feeds that need fixing"
    )
    args = parser.parse_args()

    feeds = sorted((ROOT / "feeds").glob("feed_*.xml"))
    if not feeds:
        print("no generated feeds found", file=sys.stderr)
        return 1

    names = [path.stem.removeprefix("feed_") for path in feeds]
    icons = [declared_icon(path) for path in feeds]

    # One probe per distinct URL: feeds sharing a proxy should not be fetched twice.
    unique = sorted({icon for icon in icons if icon})
    with ThreadPoolExecutor(max_workers=12) as pool:
        verdicts = dict(zip(unique, pool.map(probe, unique)))

    broken = []
    for name, icon in zip(names, icons):
        ok, note = verdicts.get(icon, (False, "brak <icon>"))
        if not ok:
            broken.append((name, icon, note))
        elif not args.broken:
            print(f"  OK    {name:26s} {note}")

    if broken:
        print(f"\n{len(broken)} z {len(names)} feedow ma niedzialajaca ikone:\n")
        for name, icon, note in broken:
            print(f"  ZLE   {name:26s} {note}")
            print(f"        {icon or '(nic nie zadeklarowano)'}")
        print(
            "\nNaprawa: dopisz domene do utils.VERIFIED_ICONS (trafi przez Google S2,\n"
            "ktory sam sie naprawia), albo podaj icon= w generatorze."
        )
        return 1

    print(f"\nWszystkie {len(names)} feedow maja dzialajaca ikone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
