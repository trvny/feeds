"""Daily quote feed generator.

Emits one quote per day as an Atom entry, drawn from a curated ``quotes.json``
list (a GitHub gist of ``{quote, author}`` objects). The pick is deterministic
per calendar day — seeded by the UTC date — so every reader sees the same quote
on a given day and the feed gains exactly one new entry each day. A JSON cache
(``cache/daily_quote_posts.json``) accumulates the history and dedupes by the
synthetic per-day id, so re-runs within a day never add a duplicate.

When the quote's author has an English Wikiquote page, the entry links there;
otherwise it falls back to the gist. Wikiquote existence is resolved via the
MediaWiki API (``action=query``) and the resolved URL is cached on the day's
entry, so it's looked up at most once per day.
"""

import argparse
import random
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests

from utils import (
    deserialize_entries,
    fetch_page,
    load_cache,
    merge_entries,
    sanitize_xml,
    save_atom_feed,
    save_cache,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)
from feedgen.feed import FeedGenerator

logger = setup_logging()

FEED_NAME = "daily_quote"
# The gist that holds the curated quote list; also the feed's "home" link and
# the per-entry fallback when an author has no Wikiquote page.
GIST_URL = "https://gist.github.com/travino/167d2271e3cf7d21e118aa7d906a7d2c"
QUOTES_JSON_URL = (
    "https://gist.githubusercontent.com/travino/"
    "167d2271e3cf7d21e118aa7d906a7d2c/raw/quotes.json"
)
WIKIQUOTE_API = "https://en.wikiquote.org/w/api.php"
WIKIQUOTE_WIKI = "https://en.wikiquote.org/wiki/"

# Keep roughly the last half-year of daily quotes in the committed feed.
MAX_ENTRIES = 200

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


def fetch_quotes():
    """Return the curated list of {quote, author} dicts, or None on failure."""
    import json

    for attempt in range(1, 4):
        try:
            raw = fetch_page(QUOTES_JSON_URL, headers=FETCH_HEADERS)
            data = json.loads(raw)
            quotes = data.get("quotes", []) if isinstance(data, dict) else data
            # Drop blank/placeholder entries (the source list has an empty first item).
            cleaned = [
                {"quote": q.get("quote", "").strip(), "author": (q.get("author") or "").strip()}
                for q in quotes
                if isinstance(q, dict) and (q.get("quote") or "").strip()
            ]
            if cleaned:
                logger.info(f"Loaded {len(cleaned)} usable quotes")
                return cleaned
            logger.warning("Quotes list parsed but empty after cleaning")
            return None
        except Exception as e:
            logger.warning(f"Quote fetch failed (attempt {attempt}/3): {e}")
            if attempt < 3:
                time.sleep(2.0 * attempt)
    return None


def pick_for_day(quotes, day):
    """Deterministically pick one quote for *day* (a date). Stable per calendar day."""
    seed = int(day.strftime("%Y%m%d"))
    return quotes[random.Random(seed).randrange(len(quotes))]


def resolve_wikiquote(author):
    """Return the author's English Wikiquote URL if a page exists, else None."""
    if not author:
        return None
    try:
        params = {
            "action": "query",
            "format": "json",
            "redirects": 1,
            "titles": author,
        }
        resp = requests.get(
            WIKIQUOTE_API, params=params, headers=FETCH_HEADERS, timeout=15
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            # Missing pages carry a "missing" key and a negative pageid.
            if "missing" not in page and page.get("pageid", 0) > 0:
                title = page.get("title", author)
                return WIKIQUOTE_WIKI + urllib.parse.quote(title.replace(" ", "_"))
    except Exception as e:
        logger.warning(f"Wikiquote lookup failed for {author!r}: {e}")
    return None


def build_today_entry(quotes, day):
    """Build the entry dict for *day* from the quote list."""
    chosen = pick_for_day(quotes, day)
    quote = sanitize_xml(chosen["quote"])
    author = sanitize_xml(chosen["author"])
    date = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)

    link = resolve_wikiquote(author) or GIST_URL
    title = f"“{quote}” — {author}" if author else f"“{quote}”"
    description = f"{quote} — {author}" if author else quote

    return {
        "id": f"{GIST_URL}#{day.isoformat()}",
        "link": link,
        "title": sanitize_xml(title),
        "description": sanitize_xml(description),
        "author": author,
        "date": date,
        "category": "quote",
    }


def generate_atom_feed(entries, feed_name=FEED_NAME):
    """Build an Atom FeedGenerator from the daily-quote entries."""
    fg = FeedGenerator()
    fg.id(f"{GIST_URL}#{feed_name}")
    fg.title("Daily Quote")
    fg.subtitle("One quote a day, with a Wikiquote link to the author when one exists")
    setup_feed_links(fg, GIST_URL, feed_name)
    fg.language("en")
    fg.author({"name": "Daily Quote"})

    for entry in entries:
        fe = fg.add_entry()
        fe.id(entry["id"])
        fe.title(entry["title"])
        fe.link(href=entry["link"])
        fe.description(entry["description"])
        fe.category(term=entry.get("category", "quote"))
        if entry.get("author"):
            fe.author({"name": entry["author"]})
        if entry.get("date"):
            fe.published(entry["date"])
            fe.updated(entry["date"])

    logger.info("Generated Atom feed")
    return fg


def main(full=False) -> bool:
    """Add today's quote (once per day), merge with cache, write the feed."""
    today = datetime.now(timezone.utc).date()
    today_id = f"{GIST_URL}#{today.isoformat()}"

    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cached = deserialize_entries(load_cache(FEED_NAME).get("entries", []), date_field="date")

    # If today's quote is already cached, just rebuild the feed from the cache —
    # no need to fetch the (large) quote list or hit Wikiquote again.
    if not full and any(e.get("id") == today_id for e in cached):
        logger.info("Today's quote already cached; rebuilding feed without refetch")
        merged = sort_posts_for_feed(cached, date_field="date")
        if len(merged) > MAX_ENTRIES:
            merged = merged[-MAX_ENTRIES:]
        save_atom_feed(generate_atom_feed(merged), FEED_NAME)
        return True

    quotes = fetch_quotes()
    if not quotes:
        logger.error("No quotes available — skipping write to preserve the last good feed")
        return False

    today_entry = build_today_entry(quotes, today)
    merged = merge_entries([today_entry], cached, id_field="id", date_field="date")
    if not merged:
        logger.warning("No entries — skipping write to avoid an empty feed")
        return False

    merged = sort_posts_for_feed(merged, date_field="date")
    # Ascending order (feedgen reverses on write), so keep the newest tail.
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]

    save_cache(FEED_NAME, merged)
    save_atom_feed(generate_atom_feed(merged), FEED_NAME)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Daily Quote Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
