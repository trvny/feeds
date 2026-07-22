#!/usr/bin/env python3
"""Generate an Atom feed for Program Trzeci Polskiego Radia."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime

import pytz
from feedgen.feed import FeedGenerator

from utils import (
    add_entry_media,
    deserialize_entries,
    fetch_page,
    load_cache,
    make_entry_id,
    merge_entries,
    sanitize_xml,
    save_atom_feed,
    save_cache,
    setup_feed_extensions,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()
FEED_NAME = "trojka"
BLOG_URL = "https://trojka.polskieradio.pl/czytaj-wiecej"
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


def _extract_next_data(html: str) -> dict:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        raise ValueError("__NEXT_DATA__ blob not found; page structure changed")
    return json.loads(match.group(1))


def _parse_date(value: str | None, fallback_id: str) -> datetime:
    if not value:
        return stable_fallback_date(fallback_id)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = pytz.timezone("Europe/Warsaw").localize(parsed)
        return parsed
    except (ValueError, TypeError):
        logger.warning("Unable to parse date %r; using fallback", value)
        return stable_fallback_date(fallback_id)


def parse_posts(html: str) -> list[dict]:
    data = _extract_next_data(html)
    articles = data.get("props", {}).get("pageProps", {}).get("data", [])
    posts: list[dict] = []
    for article in articles:
        try:
            link = article.get("url")
            title = article.get("title")
            if not link or not title:
                continue
            if link.startswith("/"):
                link = f"https://trojka.polskieradio.pl{link}"
            clean_title = sanitize_xml(title.strip())
            lead = sanitize_xml((article.get("lead") or "").strip())
            posts.append(
                {
                    "link": link,
                    "title": clean_title,
                    "description": lead or clean_title,
                    "date": _parse_date(article.get("datePublic"), link),
                    "category": (article.get("categoryName") or "").strip() or None,
                    "image": article.get("photo"),
                }
            )
        except Exception as exc:
            logger.warning("Skipping malformed article (%s): %s", article.get("id"), exc)
    logger.info("Parsed %d articles from listing", len(posts))
    return posts


def generate_atom_feed(posts: list[dict]) -> FeedGenerator:
    feed = FeedGenerator()
    feed.id("https://trojka.polskieradio.pl")
    feed.title("PR3 Trójka")
    feed.description(
        "Najnowsze artykuły radiowej Trójki: muzyka, kultura, koncerty, "
        "Lista Przebojów Trójki i Trójkowe podcasty."
    )
    feed.language("pl")
    feed.author({"name": "Polskie Radio – Trójka"})
    feed.logo("https://trojka.polskieradio.pl/logo_100_black.svg")
    feed.subtitle("Program Trzeci Polskiego Radia")
    setup_feed_links(
        feed,
        blog_url="https://trojka.polskieradio.pl",
        feed_name=FEED_NAME,
        icon="https://trojka.polskieradio.pl/assets/favicon-32x32.png",
    )
    setup_feed_extensions(feed)

    for post in posts:
        entry = feed.add_entry()
        entry.title(post["title"])
        entry.description(post["description"])
        entry.link(href=post["link"])
        entry.id(make_entry_id(FEED_NAME, post["link"]))
        add_entry_media(entry, post.get("image"))
        if post.get("category"):
            entry.category(term=post["category"])
        if post.get("date"):
            entry.published(post["date"])
    return feed


def main(full_reset: bool = False) -> bool:
    try:
        cached = deserialize_entries(load_cache(FEED_NAME).get("entries", []))
        new_posts = parse_posts(fetch_page(BLOG_URL))
    except Exception as exc:
        logger.error("Trójka fetch/parse failed: %s", exc)
        return False

    if full_reset or not cached:
        posts = sort_posts_for_feed(new_posts, date_field="date")
    else:
        posts = merge_entries(new_posts, cached)

    if not posts:
        logger.warning("No posts fetched; keeping the last good feed")
        return False

    save_cache(FEED_NAME, posts)
    save_atom_feed(generate_atom_feed(posts), FEED_NAME)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Trójka Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild")
    sys.exit(0 if main(full_reset=parser.parse_args().full) else 1)
