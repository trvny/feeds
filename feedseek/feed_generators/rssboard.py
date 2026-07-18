"""RSS Board feed: combined Atom from feed-format standards bodies — the RSS
Advisory Board, the Dublin Core Metadata Initiative, and JSON Feed.

The first two are plain RSS/Atom (multi_rss SOURCES). JSON Feed's own site
publishes only a JSON Feed 1.1 document (no RSS/Atom sibling), so it needs a
small bespoke parser (extra_scrapers) rather than feedparser.
"""

import argparse
import sys

import requests

from multi_rss import parse_date, run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "rssboard"

SOURCES = [
    ("RSS Advisory Board", "http://feeds.rssboard.org/rssboard", 15),
    ("Dublin Core (DCMI)", "https://www.dublincore.org/index.xml", 20),
]

JSONFEED_URL = "https://www.jsonfeed.org/feed.json"


def scrape_jsonfeed(known_links):
    """Parse the JSON Feed 1.1 document at jsonfeed.org into entry dicts."""
    label = "JSON Feed"
    entries = []
    try:
        resp = requests.get(
            JSONFEED_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"  [{label}] fetch/parse failed; continuing: {e}")
        return entries

    for item in data.get("items", []):
        try:
            link = item.get("url") or item.get("id") or ""
            if not link or link in known_links:
                continue
            title = sanitize_xml(item.get("title") or label)
            content = item.get("content_html") or item.get("content_text") or title
            date_obj = parse_date(item["date_published"]) if item.get("date_published") else None
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": sanitize_xml(content)[:2000],
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:  # one bad item never kills the run
            logger.warning(f"  [{label}] skipping malformed item: {e}")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="RSS Board",
        subtitle="Feed-format standards bodies: the RSS Advisory Board, the "
                 "Dublin Core Metadata Initiative, and JSON Feed.",
        blog_url="https://www.rssboard.org/",
        author="various",
        sources=SOURCES,
        extra_scrapers=[scrape_jsonfeed],
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the RSS Board Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
