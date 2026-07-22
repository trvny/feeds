#!/usr/bin/env python3
"""Generate a combined Atom feed from selected worksafe 4chan boards.

The official read-only JSON API supplies current OP threads for substantive
worksafe boards. Explicit, warez-heavy, nationalism/flame, and low-signal boards
are deliberately excluded from this public feed. The official 4chan blog is
included through its native RSS feed.
"""

from __future__ import annotations

import argparse
import datetime
import html
import sys
import time

import pytz
import requests
from bs4 import BeautifulSoup

from multi_rss import run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "4chan"
SITE_URL = "https://www.4chan.org/"
API_BASE = "https://a.4cdn.org"
BOARDS_BASE = "https://boards.4chan.org"

# Substantive worksafe topical boards only. Do not add /b/, /trash/, /s4s/,
# /t/, /int/, or /bant/ to the public feed.
BOARDS = [
    ("news", "/news/ News"),
    ("g", "/g/ Technology"),
    ("o", "/o/ Auto"),
    ("tv", "/tv/ TV & Film"),
    ("v", "/v/ Video Games"),
    ("mu", "/mu/ Music"),
    ("vip", "/vip/ VIP"),
]

BLOG_FEED = "https://blog.4chan.org/feed/"
PER_BOARD = 12
DESC_LIMIT = 500
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; trvny-feeds/1.0; +https://github.com/trvny/feeds)"
}


def _strip(value: str) -> str:
    """Convert 4chan comment/subject HTML to sanitized plain text."""
    if not value:
        return ""
    text = BeautifulSoup(html.unescape(value), "html.parser").get_text(" ", strip=True)
    return sanitize_xml(text)


def scrape_board(board: str, label: str, known_links: set) -> list:
    """Pull newest OP threads from one board; return [] on any failure."""
    entries = []
    url = f"{API_BASE}/{board}/catalog.json"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        pages = response.json()
    except Exception as exc:
        logger.warning("  [%s] fetch/parse failed: %s", label, exc)
        return entries

    threads = []
    for page in pages:
        threads.extend(page.get("threads", []))
    threads.sort(key=lambda thread: thread.get("time", 0), reverse=True)

    for thread in threads[:PER_BOARD]:
        try:
            number = thread.get("no")
            if not number:
                continue
            link = f"{BOARDS_BASE}/{board}/thread/{number}"
            if link in known_links:
                continue
            subject = _strip(thread.get("sub") or "")
            body = _strip(thread.get("com") or "")
            headline = subject or (body[:80] + ("…" if len(body) > 80 else "")) or f"thread {number}"
            timestamp = thread.get("time")
            published = (
                datetime.datetime.fromtimestamp(int(timestamp), tz=pytz.UTC)
                if timestamp
                else None
            )
            entries.append(
                {
                    "title": sanitize_xml(f"{label}: {headline}"),
                    "link": link,
                    "date": published,
                    "description": sanitize_xml((body or subject or headline)[:DESC_LIMIT]),
                    "source": label,
                }
            )
            logger.info("  [%s] %s", label, headline)
        except Exception as exc:
            logger.warning("  [%s] skipping malformed thread: %s", label, exc)

    time.sleep(1)
    return entries


def scrape_boards(known_links: set) -> list:
    entries = []
    for board, label in BOARDS:
        logger.info("Scraping %s ...", label)
        entries += scrape_board(board, label, known_links)
    return entries


def main(full: bool = False) -> bool:
    return run(
        feed_name=FEED_NAME,
        title="4chan",
        subtitle=(
            "Newest threads from selected worksafe 4chan boards "
            "(news, g, o, tv, v, mu, vip) via the read-only JSON API, "
            "plus the official 4chan blog. Board posts are user-generated "
            "and unmoderated; each title is prefixed with its board."
        ),
        blog_url=SITE_URL,
        author="4chan",
        sources=[("4chan Blog", BLOG_FEED, 20)],
        extra_scrapers=[scrape_boards],
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the 4chan Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
