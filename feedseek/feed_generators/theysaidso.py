"""They Said So quotes plus a resilient Verse of the Day feed.

Standalone quotes feed (kept separate from ``daily_quote``, which is a curated
one-a-day pick from a local gist). Two source families are merged into one feed:

* **Quote of the Day** — the native QOD RSS at ``https://theysaidso.com/qod/feed``,
  which carries ~8 category quotes per day (inspire, life, love, art,
  management, sports, funny, nature, …). No key required.
* **Verse of the Day** — primarily the They Said So Bible API
  (``https://quotes.rest/bible/vod.json``). Public access is rate-limited and
  now requires auth, so this source only contributes when an API key is present.
  Provide it via the ``THEYSAIDSO_API_KEY`` environment variable (a GitHub
  Actions secret in CI). Authenticated with an ``Authorization: Bearer <key>``
  header. A per-key 429 throttle is retried briefly, then skipped for the run.
* **Bible Gateway fallback** — when the They Said So Bible API is unavailable,
  unauthenticated, or rate-limited, the official Bible Gateway Verse of the Day
  Atom feed is used. This keeps the Bible half publishing without a secret while
  preserving They Said So as the preferred source whenever it works.

Parsing notes:
* QOD — each ``<item>``'s ``<link>`` is a *stable* category URL
  (``…/quote-of-the-day/love``) that would collapse every day's quote onto one
  dedup key, so the per-quote ``<guid>`` (``…/quote/<slug>``) is used as the
  link instead — it's unique per quote, so new daily quotes accumulate.
* VOD — the API returns a single ``contents.verse`` object (``text`` holds the
  passage; ``verse`` is the verse *number*; ``book`` is a 1-based book number,
  mapped to a name via ``BOOK_NAMES``). There's no per-verse web URL, so the
  dedup link is a synthetic ``…/verse/<id>`` (unique per verse) with the date
  as a fallback. Identical verse *text* on different days collapses via the
  title-level cross-source dedup, which is fine.

Not included: theysaidso.com/blog has no feed (404 on the usual paths), and
api.quotable.io is dead (the domain no longer resolves), so neither is wired in.
"""

import argparse
import html
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run, scrape_feed
from utils import sanitize_xml, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "theysaidso"
QOD_FEED = "https://theysaidso.com/qod/feed"
VOD_URL = "https://quotes.rest/bible/vod.json"
BIBLEGATEWAY_VOTD_FEED = "https://www.biblegateway.com/votd/get/?format=atom"
API_KEY = os.getenv("THEYSAIDSO_API_KEY", "").strip()
_CAT_RE = re.compile(r"/quote-of-the-day/([a-z0-9-]+)", re.I)

# 1-based Protestant canon (book 3 == Leviticus, per the API docs). Index 0 is a
# placeholder so BOOK_NAMES[n] gives the name for the API's 1-based book number.
BOOK_NAMES = (
    "",
    "Genesis",
    "Exodus",
    "Leviticus",
    "Numbers",
    "Deuteronomy",
    "Joshua",
    "Judges",
    "Ruth",
    "1 Samuel",
    "2 Samuel",
    "1 Kings",
    "2 Kings",
    "1 Chronicles",
    "2 Chronicles",
    "Ezra",
    "Nehemiah",
    "Esther",
    "Job",
    "Psalms",
    "Proverbs",
    "Ecclesiastes",
    "Song of Solomon",
    "Isaiah",
    "Jeremiah",
    "Lamentations",
    "Ezekiel",
    "Daniel",
    "Hosea",
    "Joel",
    "Amos",
    "Obadiah",
    "Jonah",
    "Micah",
    "Nahum",
    "Habakkuk",
    "Zephaniah",
    "Haggai",
    "Zechariah",
    "Malachi",
    "Matthew",
    "Mark",
    "Luke",
    "John",
    "Acts",
    "Romans",
    "1 Corinthians",
    "2 Corinthians",
    "Galatians",
    "Ephesians",
    "Philippians",
    "Colossians",
    "1 Thessalonians",
    "2 Thessalonians",
    "1 Timothy",
    "2 Timothy",
    "Titus",
    "Philemon",
    "Hebrews",
    "James",
    "1 Peter",
    "2 Peter",
    "1 John",
    "2 John",
    "3 John",
    "Jude",
    "Revelation",
)


def scrape_qod(known_links):
    xml = get_html(QOD_FEED)
    if not xml:
        return []
    soup = BeautifulSoup(xml, "xml")
    entries = []
    for item in soup.find_all("item"):
        try:
            guid = item.find("guid")
            cat_link = item.find("link")
            link = (guid.get_text(strip=True) if guid else "") or (
                cat_link.get_text(strip=True) if cat_link else ""
            )
            if not link or link in known_links:
                continue
            desc_el = item.find("description")
            quote = (
                sanitize_xml(html.unescape(desc_el.get_text(strip=True)))
                if desc_el
                else ""
            )
            if not quote:
                continue
            pub = item.find("pubDate")
            date = parse_date(pub.get_text(strip=True)) if pub else None
            category = None
            if cat_link:
                match = _CAT_RE.search(cat_link.get_text(strip=True))
                if match:
                    category = match.group(1).replace("-", " ").title()
            entries.append(
                {
                    "title": quote[:300],
                    "link": link,
                    "date": date or stable_fallback_date(link),
                    "description": quote,
                    "source": category or "Quote of the Day",
                }
            )
        except Exception:  # one bad item never kills the feed
            continue
    return entries


def scrape_votd(known_links):
    """Verse of the Day from the They Said So Bible API. No-ops without a key."""
    if not API_KEY:
        logger.info(
            "THEYSAIDSO_API_KEY not set — skipping They Said So Verse of the Day"
        )
        return []
    resp = None
    for attempt in range(3):
        try:
            resp = requests.get(
                VOD_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Accept": "application/json",
                },
                timeout=30,
            )
        except Exception as exc:
            logger.warning("Verse of the Day fetch failed: %s", exc)
            return []
        if resp.status_code != 429:
            break
        # Per-key throttle. Honour Retry-After when short; otherwise back off a
        # little. Never stall the whole feed run for an hourly-bucket reset.
        retry_after = resp.headers.get("Retry-After", "")
        wait = int(retry_after) if retry_after.isdigit() else (2**attempt) * 3
        if attempt < 2 and wait <= 15:
            time.sleep(wait)
            continue
        logger.warning("Verse of the Day rate-limited (HTTP 429); using fallback")
        return []
    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp is not None else "no-response"
        body = resp.text[:200] if resp is not None else ""
        logger.warning("Verse of the Day returned HTTP %s: %s", code, body)
        return []
    try:
        verse = resp.json().get("contents", {}).get("verse")
    except (ValueError, AttributeError) as exc:
        logger.warning("Verse of the Day: bad JSON: %s", exc)
        return []
    if not verse:
        logger.warning("Verse of the Day: no verse in response")
        return []
    # contents.verse is normally a single object; tolerate a list defensively.
    verses = verse if isinstance(verse, list) else [verse]

    entries = []
    for item in verses:
        try:
            text = sanitize_xml(html.unescape(str(item.get("text") or "").strip()))
            if not text:
                continue
            book = item.get("book")
            chapter = item.get("chapter")
            verse_number = item.get("verse")
            book_name = (
                BOOK_NAMES[book]
                if isinstance(book, int) and 1 <= book < len(BOOK_NAMES)
                else None
            )
            if book_name and chapter is not None and verse_number is not None:
                reference = f"{book_name} {chapter}:{verse_number}"
            else:
                reference = ""
            date_str = str(item.get("date") or "").strip()
            date = parse_date(date_str) if date_str else None
            # No per-verse web URL is provided; synthesize a stable, unique key.
            verse_id = str(item.get("id") or "").strip()
            if verse_id:
                link = f"https://theysaidso.com/verse/{verse_id}"
            elif date_str:
                link = f"https://theysaidso.com/bible#{date_str}"
            else:
                continue
            if link in known_links:
                continue
            description = f"{text} — {reference}" if reference else text
            entries.append(
                {
                    "title": (
                        f"{reference} — {text}" if reference else text
                    )[:300],
                    "link": link,
                    "date": date or stable_fallback_date(link),
                    "description": description,
                    "source": "Verse of the Day (They Said So)",
                }
            )
        except Exception:  # one bad verse never kills the feed
            continue
    return entries


def scrape_verse_of_day(known_links):
    """Prefer They Said So VOD, then fall back to Bible Gateway's Atom feed."""
    entries = scrape_votd(known_links)
    if entries:
        return entries

    logger.info("Using Bible Gateway Verse of the Day fallback")
    return scrape_feed(
        "Verse of the Day (Bible Gateway)",
        BIBLEGATEWAY_VOTD_FEED,
        known_links,
        cap=1,
    )


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="They Said So Quotes + Verse of the Day",
        subtitle=(
            "Daily quotes across categories from They Said So, plus a daily Bible "
            "verse from They Said So with an official Bible Gateway Atom fallback."
        ),
        blog_url="https://theysaidso.com/",
        author="They Said So / Bible Gateway",
        sources=(),
        extra_scrapers=[scrape_qod, scrape_verse_of_day],
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the They Said So quotes and Verse-of-the-Day Atom feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
