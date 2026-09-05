"""Atom feed scraped from the 1337x trending page."""

import argparse
import sys
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup
from multi_rss import get_html, run
from utils import normalize_link, sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "1337x"
SITE_URL = "https://1337x.to/"
BLOG_URL = urljoin(SITE_URL, "trending")
MAX_ENTRIES = 200

# 1337x is currently under aggressive anti-bot protection. Keep the canonical
# URL first, then one official mirror and Feedseek's constrained fetch proxy.
FETCH_URLS = (
    BLOG_URL,
    "https://x1337x.cc/trending",
    f"https://feeds.trfny.com/?{urlencode({'url': BLOG_URL})}",
)


def _cell_text(row, selector):
    cell = row.select_one(selector)
    return sanitize_xml(cell.get_text(" ", strip=True)) if cell else ""


def _size_text(row):
    cell = row.select_one("td.coll-4")
    if not cell:
        return ""
    clone = BeautifulSoup(str(cell), "html.parser")
    for nested in clone.select(".seeds, .leeches"):
        nested.decompose()
    return sanitize_xml(clone.get_text(" ", strip=True))


def _category_for(table):
    heading = table.find_previous(["h1", "h2"])
    if not heading:
        return "Trending"
    label = sanitize_xml(heading.get_text(" ", strip=True))
    marker = " Torrents download list"
    if marker.lower() in label.lower():
        return label[: label.lower().index(marker.lower())].strip() or "Trending"
    return label or "Trending"


def parse_trending(document, known_links=()):
    """Extract canonical torrent links and useful listing metadata."""
    soup = (
        document
        if isinstance(document, BeautifulSoup)
        else BeautifulSoup(document or "", "html.parser")
    )
    seen = {normalize_link(link) for link in known_links}
    entries = []

    for table in soup.select("table.table-list"):
        category = _category_for(table)
        for row in table.select("tbody tr"):
            anchor = row.select_one('td.coll-1.name a[href^="/torrent/"]')
            if not anchor:
                continue

            link = normalize_link(urljoin(SITE_URL, anchor.get("href", "")))
            title = sanitize_xml(anchor.get_text(" ", strip=True))
            if not link or not title or link in seen:
                continue

            seeds = _cell_text(row, "td.coll-2")
            leeches = _cell_text(row, "td.coll-3")
            uploaded = _cell_text(row, "td.coll-date")
            size = _size_text(row)
            uploader = _cell_text(row, "td.coll-5")
            facts = [
                f"Category: {category}",
                f"Seeds: {seeds}" if seeds else "",
                f"Leeches: {leeches}" if leeches else "",
                f"Size: {size}" if size else "",
                f"Listed: {uploaded}" if uploaded else "",
                f"Uploader: {uploader}" if uploader else "",
            ]
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": None,
                    "description": " · ".join(filter(None, facts)),
                    "source": f"1337x / {category}",
                }
            )
            seen.add(link)

    return entries


def scrape_1337x(known_links):
    for url in FETCH_URLS:
        html = get_html(url, retry_delay=1)
        if not html:
            continue
        entries = parse_trending(html, known_links)
        if entries:
            logger.info("1337x trending scrape via %s: %d entries", url, len(entries))
            return entries[:MAX_ENTRIES]
    logger.warning("1337x trending page unavailable or blocked")
    return []


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="1337x Trending Torrents",
        subtitle="Trending torrents listed by 1337x, with category, swarm, size, and uploader metadata.",
        blog_url=BLOG_URL,
        author="1337x",
        extra_scrapers=(scrape_1337x,),
        max_entries=MAX_ENTRIES,
        per_source_cap=MAX_ENTRIES,
        language="en",
        full=full,
        dedupe_title_field=None,
        image_backfill=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the 1337x trending Atom feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
