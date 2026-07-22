"""They Said So quotes plus a resilient Verse of the Day feed.

The feed combines the native They Said So Quote of the Day RSS with a Bible
verse. The They Said So Bible API is preferred when a key is configured.
Bible Gateway's official Verse of the Day Atom feed is used when the primary
API is unavailable, unauthenticated, rate-limited, or returns unusable data.
Both verse sources use one canonical per-day link so repeated runs cannot add
multiple Bible entries for the same UTC day.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any

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
_TOKEN_RE = re.compile(r"\S+")
_MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â€™", "â€œ", "â€\x9d", "ï¿½", "�")
_TEXT_FIELDS = ("title", "description", "source")

# 1-based Protestant canon. Index zero is intentionally empty.
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


def _mojibake_score(value: str) -> int:
    return sum(value.count(marker) for marker in _MOJIBAKE_MARKERS)


def repair_mojibake(value: str) -> str:
    """Repair UTF-8 text accidentally decoded as Latin-1/Windows-1252.

    Only whitespace-delimited tokens containing characteristic mojibake markers
    are considered. A candidate replacement is accepted only when it reduces
    the marker score, keeping already-correct Unicode unchanged.
    """

    def repair_token(match: re.Match[str]) -> str:
        token = match.group(0)
        original_score = _mojibake_score(token)
        if original_score == 0:
            return token
        for encoding in ("latin-1", "cp1252"):
            try:
                repaired = token.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if _mojibake_score(repaired) < original_score:
                return repaired
        return token

    return _TOKEN_RE.sub(repair_token, value)


def repair_cached_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Repair textual fields in historical cache entries without mutating input."""
    repaired = dict(entry)
    for field in _TEXT_FIELDS:
        value = repaired.get(field)
        if isinstance(value, str):
            repaired[field] = repair_mojibake(value)
    return repaired


def scrape_qod(known_links: set[str]) -> list[dict[str, Any]]:
    """Collect new category quotes from the native QOD RSS feed."""
    xml = get_html(QOD_FEED)
    if not xml:
        return []

    soup = BeautifulSoup(xml, "xml")
    entries: list[dict[str, Any]] = []
    for item in soup.find_all("item"):
        try:
            guid = item.find("guid")
            category_link = item.find("link")
            link = (guid.get_text(strip=True) if guid else "") or (
                category_link.get_text(strip=True) if category_link else ""
            )
            if not link or link in known_links:
                continue

            description = item.find("description")
            quote = (
                repair_mojibake(
                    sanitize_xml(html.unescape(description.get_text(strip=True)))
                )
                if description
                else ""
            )
            if not quote:
                continue

            published = item.find("pubDate")
            date = parse_date(published.get_text(strip=True)) if published else None

            category = None
            if category_link:
                match = _CAT_RE.search(category_link.get_text(strip=True))
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
        except Exception:  # one malformed item must not stop the feed
            continue
    return entries


def _request_votd() -> requests.Response | None:
    """Fetch the primary VOD endpoint, including bounded 429 retries."""
    if not API_KEY:
        logger.info(
            "THEYSAIDSO_API_KEY not set; using the Bible Gateway VOD fallback"
        )
        return None

    for attempt in range(3):
        try:
            response = requests.get(
                VOD_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Accept": "application/json",
                },
                timeout=30,
            )
        except Exception as exc:
            logger.warning("Verse of the Day fetch failed: %s", exc)
            return None

        if response.status_code != 429:
            return response

        retry_after = response.headers.get("Retry-After", "")
        wait = int(retry_after) if retry_after.isdigit() else (2**attempt) * 3
        if attempt < 2 and wait <= 15:
            time.sleep(wait)
            continue

        logger.warning("Verse of the Day rate-limited (HTTP 429); using fallback")
        return None

    return None


def _book_reference(item: dict[str, Any]) -> str:
    book = item.get("book")
    chapter = item.get("chapter")
    verse_number = item.get("verse")
    if (
        isinstance(book, int)
        and 1 <= book < len(BOOK_NAMES)
        and chapter is not None
        and verse_number is not None
    ):
        return f"{BOOK_NAMES[book]} {chapter}:{verse_number}"
    return ""


def _utc_day(value: Any = None) -> str:
    """Return a stable UTC calendar day for a parsed or textual timestamp."""
    if isinstance(value, datetime):
        date = value
    elif value:
        date = parse_date(str(value))
    else:
        date = None

    if date is None:
        date = datetime.now(timezone.utc)
    elif date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    else:
        date = date.astimezone(timezone.utc)
    return date.date().isoformat()


def _daily_verse_link(value: Any = None) -> str:
    """Canonical identity shared by both Bible sources for one UTC day."""
    return f"https://theysaidso.com/bible#{_utc_day(value)}"


def scrape_votd(
    known_links: set[str],
) -> list[dict[str, Any]] | None:
    """Return primary VOD entries, or None when the fallback should be used.

    An empty list means the primary endpoint worked but today's canonical verse
    link is already cached. The same daily link is used by Bible Gateway, so a
    recovered primary cannot duplicate an earlier fallback entry.
    """
    response = _request_votd()
    if response is None:
        return None

    if response.status_code != 200:
        logger.warning(
            "Verse of the Day returned HTTP %s: %s",
            response.status_code,
            response.text[:200],
        )
        return None

    try:
        verse = response.json().get("contents", {}).get("verse")
    except (ValueError, AttributeError) as exc:
        logger.warning("Verse of the Day returned bad JSON: %s", exc)
        return None

    if not verse:
        logger.warning("Verse of the Day response contains no verse")
        return None

    verses = verse if isinstance(verse, list) else [verse]
    entries: list[dict[str, Any]] = []
    already_known = False

    for item in verses:
        try:
            text = sanitize_xml(html.unescape(str(item.get("text") or "").strip()))
            if not text:
                continue

            date_str = str(item.get("date") or "").strip()
            date = parse_date(date_str) if date_str else datetime.now(timezone.utc)
            link = _daily_verse_link(date)
            if link in known_links:
                already_known = True
                continue

            reference = _book_reference(item)
            description = f"{text} — {reference}" if reference else text
            title = f"{reference} — {text}" if reference else text
            entries.append(
                {
                    "title": title[:300],
                    "link": link,
                    "date": date,
                    "description": description,
                    "source": "Verse of the Day (They Said So)",
                }
            )
        except Exception:  # one malformed verse must not stop the feed
            continue

    if entries or already_known:
        return entries

    logger.warning("Verse of the Day response contained no usable verse")
    return None


def scrape_biblegateway_votd(known_links: set[str]) -> list[dict[str, Any]]:
    """Fetch one fallback verse and assign the shared per-day identity."""
    raw_entries = scrape_feed(
        "Verse of the Day (Bible Gateway)",
        BIBLEGATEWAY_VOTD_FEED,
        set(),
        cap=1,
    )
    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        date = entry.get("date") or datetime.now(timezone.utc)
        link = _daily_verse_link(date)
        if link in known_links:
            continue
        entries.append({**entry, "link": link, "date": date})
    return entries


def scrape_verse_of_day(known_links: set[str]) -> list[dict[str, Any]]:
    """Prefer They Said So VOD and use Bible Gateway only on primary failure."""
    primary_entries = scrape_votd(known_links)
    if primary_entries is not None:
        return primary_entries

    logger.info("Using Bible Gateway Verse of the Day fallback")
    return scrape_biblegateway_votd(known_links)


def main(full: bool = False) -> bool:
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
        cache_transform=repair_cached_entry,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the They Said So quotes and Verse-of-the-Day Atom feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
