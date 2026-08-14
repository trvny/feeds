"""V2EX feed: combined Atom from V2EX tab feeds, node JSON feeds, and
sspai.com (少数派), a Chinese tech/productivity outlet frequently
cross-posted on V2EX.

Native feeds (multi_rss SOURCES): sspai.com, V2EX Creative tab, V2EX Play
tab. V2EX's Hot tab (feed/tab/hot.xml) was requested but is dropped: it
consistently returns HTTP 200 with a 0-byte body (checked twice, including
with a cache-busting query param — not a caching artifact, the endpoint
itself is broken upstream).

JSON Feed sources (extra_scrapers, no RSS/Atom equivalent — V2EX's per-node
feeds are only published as JSON Feed 1.1): the Claude, Android, and Reddit
V2EX nodes.

Dedup: the same story is routinely cross-posted across V2EX tabs and nodes
(e.g. a Claude-node post also surfacing in the Creative or Play tab).
multi_rss.run() already dedupes the merged set by normalized URL/title
(utils.dedupe_entries) after every source and scraper has run, so no extra
handling is needed here — that's the "look out for duplicates" ask.
"""

import argparse
import sys

import requests

from multi_rss import parse_date, run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "v2ex"

SOURCES = [
    ("sspai.com", "https://sspai.com/feed", 20),
    ("V2EX Creative", "https://www.v2ex.com/feed/tab/creative.xml", 40),
    ("V2EX Play", "https://www.v2ex.com/feed/tab/play.xml", 40),
]

# (label, JSON Feed url)
JSON_NODES = [
    ("V2EX Claude", "https://www.v2ex.com/feed/claude.json"),
    ("V2EX Android", "https://www.v2ex.com/feed/android.json"),
    ("V2EX Reddit", "https://www.v2ex.com/feed/reddit.json"),
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}


def scrape_v2ex_json_nodes(known_links):
    """Fetch each V2EX node's JSON Feed 1.1 document. Per-node isolated."""
    entries = []
    for label, url in JSON_NODES:
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"  [{label}] fetch/parse failed; continuing: {e}")
            continue

        count = 0
        for item in data.get("items", []):
            try:
                link = item.get("url") or item.get("id") or ""
                if not link or link in known_links:
                    continue
                title = sanitize_xml(item.get("title") or label)
                content = item.get("content_html") or item.get("content_text") or title
                date_obj = parse_date(item["date_published"]) if item.get("date_published") else None
                author = (item.get("author") or {}).get("name")
                entries.append({
                    "title": title,
                    "link": link,
                    "date": date_obj,
                    "description": sanitize_xml(content)[:2000],
                    "source": f"{label} ({author})" if author else label,
                })
                count += 1
            except Exception as e:  # one bad item never kills the run
                logger.warning(f"  [{label}] skipping malformed item: {e}")
        logger.info(f"  [{label}] parsed {count} entries")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="V2EX",
        subtitle="Combined V2EX feed: sspai.com, the Creative and Play tabs, "
                 "and the Claude / Android / Reddit node JSON feeds. "
                 "(Hot tab excluded — the upstream feed is broken.)",
        blog_url="https://www.v2ex.com/",
        author="various",
        sources=SOURCES,
        extra_scrapers=[scrape_v2ex_json_nodes],
        max_entries=300,
        language="zh",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the V2EX Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
