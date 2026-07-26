"""Audio.com.pl feed: the Polish hi-fi / hi-end / home-cinema portal.

The site publishes one native RSS feed at ``/rss`` (300 items) plus a ``/testy``
section that the feed never touches. Both need help before they are usable:

  * ``/rss`` carries **no ``<pubDate>`` at all**, and its ``?dzial=`` parameter
    is ignored (``?dzial=muzyka``, ``?dzial=testy`` and the bare URL all return
    byte-identical documents), so there is no per-section feed to subscribe to.
    Items are labelled here by their own URL path instead: Aktualności, Muzyka
    and Vademecum.
  * ``/testy`` — the equipment reviews, and the reason most people read the site
    — is absent from the feed entirely. The section index server-renders every
    review as ``/testy/<category>/<subcategory>/<id>-<slug>`` with its title and
    thumbnail in the card, so it is scraped from the index without fetching each
    review page.

Dating: neither source exposes a date, so entries are stamped on first sight
and the JSON cache preserves that stamp (the repo's usual first-seen approach).
Within one ingest the stamps step backwards by position so the source's own
ordering survives — the RSS is newest-first, and reviews are ordered by their
numeric id, which increases over time.
"""

import argparse
import re
import sys
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from multi_rss import get_html, run
from utils import sanitize_xml

FEED_NAME = "audio"

BLOG_URL = "https://audio.com.pl/"
RSS_URL = "https://audio.com.pl/rss"
TESTY_URL = "https://audio.com.pl/testy"

RSS_CAP = 120
TESTY_CAP = 60

# Reviews live at /testy/<category>/<subcategory>/<numeric-id>-<slug>; the
# section, category and subcategory index pages must not become entries.
_REVIEW_RE = re.compile(r"^/testy/[a-z0-9-]+/[a-z0-9-]+/(\d+)-[a-z0-9-]+$")

# The feed mixes three sections, distinguishable only by the article URL.
_SECTION_LABELS = {
    "aktualnosci": "Aktualności",
    "muzyka": "Muzyka",
    "vademecum": "Vademecum",
}

# A handful of feed items carry a broken self-referential link
# (``/rss/<id>-<slug>``) instead of their section path; those URLs 404, and the
# real path can't be reconstructed because the section has a dozen possible
# subsections. Such items are dropped rather than published as dead links.
_BROKEN_LINK_RE = re.compile(r"^https?://[^/]*audio\.com\.pl/rss/")

PER_SOURCE_QUOTA = {
    "": 60,
    "Testy": 80,
}


def _stamp(index):
    """First-seen timestamp that preserves the source's own ordering."""
    return datetime.now(UTC) - timedelta(seconds=index)


def _section_label(link):
    parts = [p for p in link.split("audio.com.pl/", 1)[-1].split("/") if p]
    return _SECTION_LABELS.get(parts[0] if parts else "", "Audio.com.pl")


def scrape_rss(known_links):
    """Parse the native /rss feed, labelling items by their section."""
    xml = get_html(RSS_URL)
    if not xml:
        return []
    soup = BeautifulSoup(xml, "xml")
    entries = []
    for position, item in enumerate(soup.find_all("item")[:RSS_CAP]):
        try:
            link_el = item.find("link")
            link = link_el.get_text(strip=True) if link_el else ""
            if not link or link in known_links or _BROKEN_LINK_RE.match(link):
                continue
            title_el = item.find("title")
            title = sanitize_xml(title_el.get_text(strip=True)) if title_el else ""
            if not title:
                continue
            desc_el = item.find("description")
            description = (
                sanitize_xml(BeautifulSoup(desc_el.get_text(), "html.parser").get_text(" ", strip=True))
                if desc_el
                else ""
            )
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": _stamp(position),
                    "description": description[:500] or title,
                    "source": _section_label(link),
                }
            )
        except Exception:  # one malformed item must not stop the feed
            continue
    return entries


def scrape_testy(known_links):
    """Scrape the /testy index, which the native feed never covers.

    Cards are ordered by review id, so the newest reviews are taken first and
    the id doubles as the ordering key.
    """
    html = get_html(TESTY_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")

    found = {}
    for anchor in soup.find_all("a", href=True):
        match = _REVIEW_RE.match(anchor["href"].split("?")[0].split("#")[0])
        if not match:
            continue
        link = urljoin(BLOG_URL, anchor["href"])
        title = sanitize_xml(anchor.get_text(" ", strip=True))
        image = None
        img = anchor.find("img")
        if img:
            src = img.get("src") or img.get("data-src")
            if src:
                image = urljoin(BLOG_URL, src)
        # The same review appears more than once on the index (a thumbnail card
        # and a text link); keep whichever occurrence carries a title, and
        # prefer one that also carries an image.
        existing = found.get(link)
        if existing and (existing.get("title") or not title):
            if image and not existing.get("image"):
                existing["image"] = image
            continue
        found[link] = {
            "id": int(match.group(1)),
            "title": title,
            "link": link,
            "image": image,
        }

    entries = []
    ordered = sorted(found.values(), key=lambda item: item["id"], reverse=True)
    for position, card in enumerate(ordered[:TESTY_CAP]):
        if card["link"] in known_links or not card["title"]:
            continue
        entries.append(
            {
                "title": card["title"],
                "link": card["link"],
                "date": _stamp(position),
                "description": card["title"],
                "source": "Testy",
                "image": card["image"],
            }
        )
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Audio.com.pl",
        subtitle="Polski portal hi-fi, hi-end i kina domowego: aktualności "
        "sprzętowe i branżowe, recenzje płyt i newsy muzyczne, "
        "vademecum, oraz testy sprzętu z sekcji /testy.",
        blog_url=BLOG_URL,
        author="Audio.com.pl",
        sources=(),
        extra_scrapers=[scrape_rss, scrape_testy],
        max_entries=320,
        per_source_cap=PER_SOURCE_QUOTA,
        language="pl",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Audio.com.pl Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
