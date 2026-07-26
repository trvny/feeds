"""Daily one-liners: quotes, sayings and jokes, plus a resilient Verse of the Day.

The feed combines the native They Said So Quote of the Day RSS with a Bible
verse, and folds in five more one-liner feeds (The Quotations Page, Quote for
the Day, Quotes4all, Sayings.net, Jokes4all) through ``scrape_one_liners``,
which rebuilds each entry so the line itself becomes the title — see the
comment above ``ONE_LINER_FEEDS`` for why none of them are usable as-is.

For the Bible verse, the They Said So Bible API is preferred when a key is
configured. Bible Gateway's official Verse of the Day Atom feed is used when
the primary API is unavailable, unauthenticated, rate-limited, or returns
unusable data. Both verse sources use one canonical per-day link so repeated
runs cannot add multiple Bible entries for the same UTC day.
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
# These feeds rebuild once a day and serve ~10 rotating items, so a per-run cap
# keeps a single source from dominating the day's intake.
ONE_LINER_CAP = 25
QOD_FEED = "https://theysaidso.com/qod/feed"
VOD_URL = "https://quotes.rest/bible/vod.json"
BIBLEGATEWAY_VOTD_FEED = "https://www.biblegateway.com/votd/get/?format=atom"
API_KEY = os.getenv("THEYSAIDSO_API_KEY", "").strip()
_CAT_RE = re.compile(r"/quote-of-the-day/([a-z0-9-]+)", re.I)
_SEGMENT_RE = re.compile(r"[^\t\n\r\f\v ]+")
_MOJIBAKE_MARKERS = ("Ã", "Â", "â", "ï¿½", "\ufffd")
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


def _reconstruct_mojibake_bytes(segment: str) -> bytes | None:
    """Map Latin-1 controls and Windows-1252 glyphs back to source bytes."""
    raw = bytearray()
    for character in segment:
        codepoint = ord(character)
        if codepoint <= 0xFF:
            raw.append(codepoint)
            continue
        try:
            raw.extend(character.encode("cp1252"))
        except UnicodeEncodeError:
            return None
    return bytes(raw)


def repair_mojibake(value: str) -> str:
    """Repair UTF-8 text accidentally decoded as Latin-1/Windows-1252.

    Only segments containing characteristic mojibake markers are considered.
    Segments are split on ASCII whitespace only, keeping non-breaking spaces and
    C1 byte characters attached to their UTF-8 lead bytes. Source bytes are
    reconstructed from both Latin-1 controls and Windows-1252 display glyphs. A
    candidate is accepted only when it decodes as UTF-8 and reduces the marker
    score, keeping correct Unicode unchanged.
    """

    def repair_segment(match: re.Match[str]) -> str:
        segment = match.group(0)
        original_score = _mojibake_score(segment)
        if original_score == 0:
            return segment

        raw = _reconstruct_mojibake_bytes(segment)
        if raw is None:
            return segment
        try:
            repaired = raw.decode("utf-8")
        except UnicodeDecodeError:
            return segment
        if _mojibake_score(repaired) < original_score:
            return repaired
        return segment

    return _SEGMENT_RE.sub(repair_segment, value)


def repair_cached_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Repair textual fields in historical cache entries without mutating input."""
    repaired = dict(entry)
    for field in _TEXT_FIELDS:
        value = repaired.get(field)
        if isinstance(value, str):
            repaired[field] = repair_mojibake(value)
    return repaired


# Extra one-liner feeds. Every one of these publishes a usable line but hides
# it somewhere a reader won't show: the *4all.net family puts a breadcrumb
# ("Sayings.net > Common Sense > Saying #2455") in <title> and the line in the
# description, Quote for the Day (Blogger) ships an empty <title>, and The
# Quotations Page puts the author in <title> and the quote in the description.
# All three shapes are repaired the same way below, which is why they share one
# scraper instead of going through multi_rss SOURCES.
ONE_LINER_FEEDS = [
    ("The Quotations Page", "https://feeds.feedburner.com/quotationspage/qotd"),
    ("Quote for the Day", "https://q4td.blogspot.com/feeds/posts/default"),
    ("Quotes4all", "https://quotes4all.net/quotes.rss"),
    ("Sayings.net", "https://sayings.net/sayings.rss"),
    ("Jokes4all", "https://jokes4all.net/jokes.rss"),
]

# "Site.net > Category > Saying #2455" — a breadcrumb, not a title.
_BREADCRUMB_RE = re.compile(r">\s*[A-Za-z ]+#\s*(\d+)\s*$")
# Attribution lines arrive variously as "— Name", "-- Name" or just "Name".
_LEADING_DASH_RE = re.compile(r"^[\s\u2012-\u2015\u2212-]+")
_NAMED_ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]+);")
_XML_ENTITIES = frozenset({"amp", "lt", "gt", "quot", "apos"})


def resolve_html_entities(xml: str) -> str:
    """Expand HTML-only named entities before the XML parser sees them.

    The Quotations Page emits ``&mdash;`` inside an ``application/xml``
    document. lxml only knows the five XML entities and drops the rest
    silently, which swallows the punctuation and glues two words together.
    Expanding them first keeps the character; the five XML entities are left
    alone so escaped markup in descriptions still round-trips.
    """

    def expand(match: re.Match[str]) -> str:
        if match.group(1) in _XML_ENTITIES:
            return match.group(0)
        return html.unescape(match.group(0))

    return _NAMED_ENTITY_RE.sub(expand, xml)


def _body_parts(item) -> tuple[str, str]:
    """Split an item body into its lead line and whatever trails it.

    The lead line is the first paragraph (the quote, saying or joke); the rest
    is usually the attribution block. Feeds without any markup collapse to a
    single lead line and an empty tail.
    """
    for tag in ("description", "content", "summary", "content:encoded"):
        el = item.find(tag)
        if el is None:
            continue
        raw = html.unescape(el.get_text())
        if not raw.strip():
            continue
        body = BeautifulSoup(repair_mojibake(raw), "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in body.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        if paragraphs:
            tail = _LEADING_DASH_RE.sub("", " ".join(paragraphs[1:])).strip()
            return paragraphs[0], tail
        text = body.get_text(" ", strip=True)
        if text:
            return text, ""
    return "", ""


def _item_permalink(item) -> str:
    """Prefer the per-item guid over <link>.

    These feeds point <link> at a category or author page shared by many items,
    so the guid is what actually identifies the quote. Where the guid is not a
    URL (the *4all.net family stamps every item of a day with the same
    ``tag:site,DATE:rss-item``), the item number from the breadcrumb title is
    appended to the link instead.
    """
    guid = item.find("guid")
    guid_text = guid.get_text(strip=True) if guid else ""
    if guid_text.startswith("http"):
        return guid_text

    link = ""
    for link_el in item.find_all("link"):
        href = (link_el.get("href") or "").strip()
        if href and link_el.get("rel") in (None, "alternate"):
            link = href
            break
        text = link_el.get_text(strip=True)
        if text:
            link = text
            break
    if not link:
        return ""

    title_el = item.find("title")
    match = _BREADCRUMB_RE.search(title_el.get_text(strip=True) if title_el else "")
    return f"{link}#{match.group(1)}" if match else link


def scrape_one_liners(known_links: set[str]) -> list[dict[str, Any]]:
    """Fetch ONE_LINER_FEEDS and rebuild each entry around its actual line."""
    entries: list[dict[str, Any]] = []
    for label, url in ONE_LINER_FEEDS:
        xml = get_html(url)
        if not xml:
            logger.warning("[%s] feed unavailable; continuing", label)
            continue
        try:
            soup = BeautifulSoup(resolve_html_entities(repair_mojibake(xml)), "xml")
        except Exception as exc:
            logger.warning("[%s] could not parse feed: %s", label, exc)
            continue

        items = soup.find_all("item") or soup.find_all("entry")
        if not items:
            logger.warning("[%s] feed has no items; format may have changed", label)
            continue

        before = len(entries)
        for item in items[:ONE_LINER_CAP]:
            try:
                link = _item_permalink(item)
                if not link or link in known_links:
                    continue
                lead, tail = _body_parts(item)
                if not lead:
                    continue

                title_el = item.find("title")
                raw_title = title_el.get_text(strip=True) if title_el else ""
                # An author-only title (The Quotations Page) is the byline; a
                # breadcrumb title is noise and gets dropped entirely.
                if not tail and raw_title and not _BREADCRUMB_RE.search(raw_title):
                    tail = _LEADING_DASH_RE.sub("", raw_title).strip()

                published = item.find("pubDate") or item.find("published")
                date = parse_date(published.get_text(strip=True)) if published else None

                entries.append(
                    {
                        "title": sanitize_xml(lead)[:300],
                        "link": link,
                        "date": date or stable_fallback_date(link),
                        "description": sanitize_xml(
                            f"{lead} — {tail}" if tail else lead
                        )[:500],
                        "source": label,
                    }
                )
            except Exception as exc:
                logger.warning("[%s] skipping malformed item: %s", label, exc)
        logger.info("[%s] collected %d new item(s)", label, len(entries) - before)
    return entries


def scrape_qod(known_links: set[str]) -> list[dict[str, Any]]:
    """Collect new category quotes from the native QOD RSS feed."""
    xml = get_html(QOD_FEED)
    if not xml:
        return []

    # Repair the raw document before the XML parser or sanitizer can discard C1
    # byte characters that belong to a mis-decoded UTF-8 sequence.
    soup = BeautifulSoup(repair_mojibake(xml), "xml")
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
                sanitize_xml(
                    repair_mojibake(html.unescape(description.get_text(strip=True)))
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
        logger.info("THEYSAIDSO_API_KEY not set; using the Bible Gateway VOD fallback")
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
        title="Quotes, Sayings and Jokes of the Day",
        subtitle=(
            "Daily one-liners: quotes across categories from They Said So, The "
            "Quotations Page, Quote for the Day and Quotes4all, sayings from "
            "Sayings.net, jokes from Jokes4all, plus a daily Bible verse from "
            "They Said So with an official Bible Gateway Atom fallback."
        ),
        blog_url="https://theysaidso.com/",
        author="various",
        sources=(),
        extra_scrapers=[scrape_qod, scrape_one_liners, scrape_verse_of_day],
        max_entries=300,
        per_source_cap=40,
        full=full,
        cache_transform=repair_cached_entry,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the quotes, sayings, jokes and Verse-of-the-Day Atom feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
