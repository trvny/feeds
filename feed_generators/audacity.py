"""Audacity® feed: official updates plus the wider MuseHub ecosystem.

Uses native RSS for the Audacity forum and MuseHub blog. The Audacity blog has
no feed, while MuseHub's product catalogue exposes a server-rendered New
Products page, so those two sources are scraped with small card parsers.
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from multi_rss import get_html, parse_date, run
from utils import sanitize_xml

FEED_NAME = "audacity"
AUDACITY_BLOG_URL = "https://www.audacityteam.org/blog/"
AUDACITY_FORUM_URL = "https://forum.audacityteam.org/latest.rss"
MUSEHUB_BLOG_URL = "https://blog.musehub.com/feed/"
MUSEHUB_PRODUCTS_URL = "https://www.musehub.com/pl-pl/new-products"

SOURCES = [
    ("Audacity Forum", AUDACITY_FORUM_URL, 60),
    ("MuseHub Blog", MUSEHUB_BLOG_URL, 30),
]


def _first_seen(position: int) -> datetime:
    """Preserve source ordering for dateless new-product cards."""
    return datetime.now(UTC) - timedelta(seconds=position)


def scrape_audacity_blog(known_links: set[str]) -> list[dict]:
    """Parse dated blog cards from Audacity's server-rendered blog index."""
    html = get_html(AUDACITY_BLOG_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].split("?", 1)[0].split("#", 1)[0]
        if not href.startswith("/blog/"):
            continue
        title_el = anchor.find("h4")
        date_el = anchor.find("small")
        if not title_el or not date_el:
            continue
        link = urljoin(AUDACITY_BLOG_URL, href)
        if link in known_links or link in seen:
            continue
        title = sanitize_xml(title_el.get_text(" ", strip=True))
        date = parse_date(date_el.get_text(" ", strip=True))
        if not title or date is None:
            continue
        desc_el = anchor.find("p")
        description = (
            sanitize_xml(desc_el.get_text(" ", strip=True)) if desc_el else title
        )
        img = anchor.find("img")
        image = urljoin(AUDACITY_BLOG_URL, img.get("src")) if img and img.get("src") else None
        seen.add(link)
        entries.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "description": description[:500] or title,
                "source": "Audacity Blog",
                "image": image,
            }
        )
    return entries


def scrape_musehub_products(known_links: set[str]) -> list[dict]:
    """Turn MuseHub's ordered New Products cards into first-seen entries."""
    html = get_html(MUSEHUB_PRODUCTS_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for position, article in enumerate(soup.find_all("article")[:40]):
        title_el = article.find("h3")
        link_el = article.find("a", href=True)
        if not title_el or not link_el:
            continue
        link = urljoin(MUSEHUB_PRODUCTS_URL, link_el["href"])
        if link in known_links:
            continue
        title = sanitize_xml(title_el.get_text(" ", strip=True))
        if not title:
            continue
        paragraphs = [
            sanitize_xml(p.get_text(" ", strip=True))
            for p in article.find_all("p")
            if p.get_text(" ", strip=True)
        ]
        description = max(paragraphs, key=len, default=title)
        img = article.find("img")
        image = img.get("src") if img and img.get("src") else None
        entries.append(
            {
                "title": title,
                "link": link,
                "date": _first_seen(position),
                "description": description[:500] or title,
                "source": "MuseHub New Products",
                "image": image,
            }
        )
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Audacity®",
        subtitle="Audacity blog and forum updates, plus MuseHub news and newly listed audio tools.",
        blog_url=AUDACITY_BLOG_URL,
        author="Audacity / MuseHub",
        sources=SOURCES,
        extra_scrapers=[scrape_audacity_blog, scrape_musehub_products],
        max_entries=240,
        per_source_cap=60,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Audacity® Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
