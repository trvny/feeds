"""Mozilla feed: combined Atom from Mozilla's native feeds — the Mozilla blog,
the Firefox Nightly blog, the Add-ons blog, Mozilla Hacks, the Thunderbird
blog, Planet Mozilla (community firehose), and the Firefox Nightly release
notes — plus shipped Firefox release notes pulled from Mozilla's
product-details API.

Only the Nightly channel exposes a release-notes feed; the release-channel
desktop and Android notes have none. So the latest shipped desktop builds
(``major``/``stability`` categories) and the current Android build are read
from product-details (``firefox.json`` / ``mobile_versions.json``) and linked
to their release-notes pages, dated by their published date.
"""

import argparse
import sys
from datetime import datetime, timezone

import requests

from multi_rss import parse_date, run

FEED_NAME = "mozilla"

SOURCES = [
    ("Mozilla Blog", "https://blog.mozilla.org/feed/", 40),
    ("Firefox Nightly", "https://blog.nightly.mozilla.org/feed/", 40),
    ("Add-ons Blog", "https://addons.mozilla.org/blog/feed.xml", 40),
    ("Mozilla Hacks", "https://hacks.mozilla.org/feed/", 40),
    ("Thunderbird Blog", "https://blog.thunderbird.net/feed/", 40),
    ("Planet Mozilla", "https://planet.mozilla.org/atom.xml", 40),
    ("Nightly Release Notes", "https://www.firefox.com/en-US/firefox/nightly/notes/feed/", 40),
]

PD = "https://product-details.mozilla.org/1.0/"
DESKTOP_NOTES = "https://www.firefox.com/en-US/firefox/{v}/releasenotes/"
ANDROID_NOTES = "https://www.firefox.com/en-US/firefox/android/{v}/releasenotes/"


def scrape_releases(known_links):
    """Latest shipped Firefox releases from Mozilla's product-details API,
    linked to their release-notes pages. Desktop ``major``/``stability``
    builds come dated from ``firefox.json``; the current Android build is
    dated by matching its version there, falling back to first-seen."""
    entries = []
    try:
        releases = requests.get(PD + "firefox.json", timeout=30).json().get("releases", {})
    except Exception:
        releases = {}

    ver_date, desktop = {}, []
    for key, meta in releases.items():
        ver = key.split("firefox-", 1)[-1]
        date = parse_date(meta["date"]) if meta.get("date") else None
        if date:
            ver_date[ver] = date
        if date and meta.get("category") in ("major", "stability"):
            desktop.append((ver, date))

    desktop.sort(key=lambda x: x[1])
    for ver, date in desktop[-8:]:
        link = DESKTOP_NOTES.format(v=ver)
        if link in known_links:
            continue
        entries.append({
            "title": f"Firefox {ver}",
            "link": link,
            "date": date,
            "description": f"Firefox {ver} release notes.",
            "source": "Release Notes",
        })

    try:
        android = requests.get(PD + "mobile_versions.json", timeout=30).json().get("version")
    except Exception:
        android = None
    if android:
        link = ANDROID_NOTES.format(v=android)
        if link not in known_links:
            entries.append({
                "title": f"Firefox for Android {android}",
                "link": link,
                "date": ver_date.get(android) or datetime.now(timezone.utc),
                "description": f"Firefox for Android {android} release notes.",
                "source": "Android Release Notes",
            })
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Mozilla",
        subtitle="Combined Mozilla feed: the Mozilla, Firefox Nightly, Add-ons, "
                 "Hacks and Thunderbird blogs, Planet Mozilla, Nightly release "
                 "notes, and shipped Firefox desktop and Android release notes.",
        blog_url="https://blog.mozilla.org/",
        author="Mozilla",
        sources=SOURCES,
        extra_scrapers=(scrape_releases,),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Mozilla Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
