#!/usr/bin/env python3
"""Creative Commons blog feed generator.

Creative Commons runs on WordPress and *does* publish a native RSS feed at
``https://creativecommons.org/feed/`` (the ``/blog/feed/`` path is a stale
comments feed — don't use it). This generator republishes the main feed as a
clean Atom feed inside the feedseek repo so it shows up on the landing page and
in the reader alongside the other feeds, deduplicated and accumulated across
runs via the JSON cache (the native WP feed only carries the newest ~10 posts,
so the rolling cache is what keeps history).

The press page (creativecommons.org/mission/contact/press/) is a static contact
page with no feed of its own, so the blog feed is the only source here.

Usage:
    python creativecommons.py          # incremental (merge into cache)
    python creativecommons.py --full   # ignore cache, rebuild from the live feed
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import feedparser
import requests
from feedgen.feed import FeedGenerator

from utils import (
    DEFAULT_HEADERS,
    deserialize_entries,
    load_cache,
    merge_entries,
    normalize_link,
    sanitize_xml,
    save_atom_feed,
    save_cache,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "creativecommons"
BLOG_URL = "https://creativecommons.org/blog/"
FEED_TITLE = "Creative Commons Blog"
FEED_DESC = "News and updates from Creative Commons"
FEED_LANG = "en"
SOURCE_FEED = "https://creativecommons.org/feed/"
MAX_ENTRIES = 100


def entry_date(entry) -> datetime | None:
    """Best-effort tz-aware UTC datetime from a feedparser entry."""
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            return datetime(*struct[:6], tzinfo=timezone.utc)
    return None


def fetch_source(retries: int = 3, backoff: float = 2.0):
    """Fetch and parse the native WP feed; return a feedparser result or None."""
    import time

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(SOURCE_FEED, headers=DEFAULT_HEADERS, timeout=30)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            if parsed.entries:
                logger.info("Fetched %d entries from %s", len(parsed.entries), SOURCE_FEED)
                return parsed
            logger.warning("Feed parsed but had no entries (attempt %d/%d)", attempt, retries)
        except Exception as exc:
            logger.warning("Fetch failed (attempt %d/%d): %s", attempt, retries, exc)
        if attempt < retries:
            time.sleep(backoff * attempt)
    return None


def parse_items(parsed) -> list[dict]:
    """Normalize the parsed feed into the project's entry dicts."""
    entries: list[dict] = []
    for e in parsed.entries:
        try:
            link = normalize_link(e.get("link") or "")
            title = sanitize_xml((e.get("title") or "").strip())
            if not link or not title:
                continue
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": entry_date(e) or stable_fallback_date(link),
                    "description": sanitize_xml(e.get("summary") or ""),
                }
            )
        except Exception as exc:  # one malformed item is skipped, not fatal
            logger.warning("Skipping an entry due to error: %s", exc)
    logger.info("Parsed %d entries", len(entries))
    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    fg = FeedGenerator()
    fg.id(f"{BLOG_URL}#{feed_name}")
    fg.title(FEED_TITLE)
    fg.subtitle(FEED_DESC)
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language(FEED_LANG)
    fg.author({"name": "Creative Commons"})
    for e in entries:
        fe = fg.add_entry()
        fe.id(e["link"])
        fe.title(e["title"])
        fe.link(href=e["link"])
        fe.description(e["description"])
        if e.get("date"):
            fe.published(e["date"])
            fe.updated(e["date"])
    return fg


def main(full: bool = False) -> bool:
    parsed = fetch_source()
    if parsed is None:
        logger.error("Fetch failed — skipping write to preserve the last good feed")
        return False
    new_entries = parse_items(parsed)
    if not new_entries:
        logger.warning("No entries parsed — skipping write to avoid an empty feed")
        return False

    cached = [] if full else deserialize_entries(load_cache(FEED_NAME).get("entries", []), date_field="date")
    merged = merge_entries(new_entries, cached, id_field="link", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]

    save_cache(FEED_NAME, merged)
    save_atom_feed(generate_atom_feed(merged), FEED_NAME)
    logger.info("Wrote %d entries to feed_%s.xml", len(merged), FEED_NAME)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Creative Commons Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
