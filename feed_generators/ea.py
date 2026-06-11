"""Electronic Arts feed: combined Atom from EA.com pages.

Sources (none have native RSS; all are scraped):
  * EA News PL (ea.com/pl-pl/news) — server-rendered ``<ea-tile>`` cards
    with ISO dates in ``eyebrow-secondary-text``
  * EA Research & Technology (ea.com/technology) — same ``<ea-tile>``
    markup, relative links, "Mar 21, 2025"-style dates; nav tiles carry
    no date and are skipped
  * EA Sports News PL (ea.com/pl-pl/ea-studios/ea-sports/news) — same
    ``<ea-tile>`` markup
  * EA Sports FC 26 News PL (ea.com/pl/games/ea-sports-fc/fc-26/news) —
    Next.js page; items live in ``__NEXT_DATA__`` under
    ``props.pageProps.newsDataFallback.items`` (title, summary, slug,
    publishingDate)
"""

import argparse
import json
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml

FEED_NAME = "ea"

TILE_PAGES = [
    ("EA News PL", "https://www.ea.com/pl-pl/news"),
    ("EA Research & Technology", "https://www.ea.com/technology"),
    ("EA Sports News PL", "https://www.ea.com/pl-pl/ea-studios/ea-sports/news"),
]

FC26_URL = "https://www.ea.com/pl/games/ea-sports-fc/fc-26/news"


def scrape_tile_pages(known_links):
    """Article cards from EA's server-rendered ``<ea-tile>`` pages.

    A tile is an article only when it has both a date
    (``eyebrow-secondary-text``) and an ``<ea-cta>`` link; undated tiles
    are site navigation and are skipped.
    """
    entries = []
    for label, page_url in TILE_PAGES:
        html = get_html(page_url)
        if html is None:
            continue
        soup = BeautifulSoup(html, "html.parser")
        count = 0
        for tile in soup.find_all("ea-tile"):
            date_str = tile.get("eyebrow-secondary-text")
            cta = tile.find("ea-cta")
            link = cta.get("link-url") if cta else None
            if not date_str or not link:
                continue
            link = urljoin(page_url, link)
            if link in known_links:
                continue
            title = sanitize_xml(
                (tile.get("tooltip") or tile.get("title-text") or "").strip()
            )
            if not title:
                continue
            copy = tile.find("ea-tile-copy")
            description = sanitize_xml(copy.get_text(" ", strip=True)) if copy else ""
            entries.append({
                "title": title,
                "link": link,
                "date": parse_date(date_str),
                "description": description or title,
                "source": label,
            })
            count += 1
        print_log(label, count)
    return entries


def scrape_fc26(known_links):
    """FC 26 news items from the page's ``__NEXT_DATA__`` JSON."""
    entries = []
    html = get_html(FC26_URL)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None:
        print_log("EA Sports FC 26 News PL", 0, note="__NEXT_DATA__ missing")
        return entries
    try:
        data = json.loads(script.get_text())
        items = data["props"]["pageProps"]["newsDataFallback"]["items"]
    except (ValueError, KeyError, TypeError) as e:
        print_log("EA Sports FC 26 News PL", 0, note=f"JSON shape changed: {e}")
        return entries
    count = 0
    for item in items:
        slug = (item.get("slug") or "").strip()
        title = sanitize_xml((item.get("title") or "").strip())
        if not slug or not title:
            continue
        link = f"{FC26_URL}/{slug}"
        if link in known_links:
            continue
        date = parse_date(item["publishingDate"]) if item.get("publishingDate") else None
        summary = sanitize_xml((item.get("summary") or "").strip())
        entries.append({
            "title": title,
            "link": link,
            "date": date,
            "description": summary or title,
            "source": "EA Sports FC 26 News PL",
        })
        count += 1
    print_log("EA Sports FC 26 News PL", count)
    return entries


def print_log(label, count, note=None):
    from multi_rss import logger
    if note:
        logger.warning(f"  [{label}] {note}")
    logger.info(f"  [{label}] {count} new entries")


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Electronic Arts",
        subtitle="Combined EA feed: EA News (PL), EA Research & Technology, "
                 "EA Sports News (PL), and EA Sports FC 26 News (PL).",
        blog_url="https://www.ea.com/pl-pl/news",
        author="Electronic Arts",
        extra_scrapers=(scrape_tile_pages, scrape_fc26),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Electronic Arts Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
