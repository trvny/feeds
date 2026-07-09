#!/usr/bin/env python3
"""HackerOne blog + newsroom feed generator.

HackerOne (a Drupal site) has no native RSS/Atom feed. Both the blog and the
newsroom are fully server-rendered — the article cards are present in the
initial HTML as ``div.views-row`` tiles — so a plain browser-UA request is
enough (no JS/browser automation, no Cloudflare fingerprinting to defeat).

Two sources are combined into one feed:

* Blog       https://www.hackerone.com/blog            (all /blog/ posts)
* Newsroom   https://www.hackerone.com/company/newsroom (HackerOne's own
             /press-release/ items only)

The newsroom page mixes first-party press releases with "in the news" links to
external outlets (WSJ, Forbes, ...). Those external links are intentionally
dropped — only on-domain HackerOne content goes into the feed. Entries are
deduped by canonical URL and accumulated across runs via the JSON cache.

Usage:
    python hackerone.py          # incremental (merge into cache)
    python hackerone.py --full   # ignore cache, rebuild from the live pages
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    deserialize_entries,
    fetch_page,
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

FEED_NAME = "hackerone"
BLOG_URL = "https://www.hackerone.com/blog"
BASE_URL = "https://www.hackerone.com"
FEED_TITLE = "HackerOne Blog & Newsroom"
FEED_DESC = "Posts from the HackerOne blog and first-party press releases"
FEED_LANG = "en"
MAX_ENTRIES = 100

# (source label, listing URL, keep-predicate on the resolved absolute link)
SOURCES = [
    ("Blog", "https://www.hackerone.com/blog", lambda href: "/blog/" in href),
    (
        "Newsroom",
        "https://www.hackerone.com/company/newsroom",
        lambda href: "/press-release/" in href,
    ),
]

# Non-article /blog/ links to reject (topic/category/author pages, the index).
_BLOG_JUNK = ("/blog/topic/", "/blog/author/", "/blog/tag/", "/blog/category/")


def fetch_listing(url: str, retries: int = 3, backoff: float = 2.0) -> str | None:
    """Fetch one listing page with a browser UA; return HTML or None."""
    for attempt in range(1, retries + 1):
        try:
            html = fetch_page(url)
            if html and "views-row" in html:
                logger.info("Fetched %s (%d bytes)", url, len(html))
                return html
            logger.warning("Unexpected response for %s (attempt %d/%d)", url, attempt, retries)
        except Exception as exc:
            logger.warning("Fetch failed for %s (attempt %d/%d): %s", url, attempt, retries, exc)
        if attempt < retries:
            time.sleep(backoff * attempt)
    return None


def _title_from_row(row):
    """Pick the substantive title anchor from a card (skip 'Image'/CTA links)."""
    best = None
    for a in row.find_all("a", href=True):
        txt = a.get_text(strip=True)
        low = txt.lower()
        if not txt or low in ("image", "read now", "learn more", "read more"):
            continue
        if txt.startswith("/"):
            continue
        if best is None or len(txt) > len(best[0]):
            best = (txt, a["href"])
    return best


def _row_date(row) -> datetime | None:
    tm = row.find("time")
    if tm and tm.get("datetime"):
        try:
            return datetime.fromisoformat(tm["datetime"].replace("Z", "+00:00")).astimezone(pytz.UTC)
        except ValueError:
            pass
    return None


def parse_listing(html: str, keep) -> list[dict]:
    """Parse ``div.views-row`` cards; keep only links passing ``keep``."""
    soup = BeautifulSoup(html, "html.parser")
    entries: list[dict] = []
    for row in soup.select("div.views-row"):
        try:
            picked = _title_from_row(row)
            if not picked:
                continue
            title, href = picked
            abs_link = href if href.startswith("http") else BASE_URL + href
            if not keep(abs_link):
                continue
            if any(j in abs_link for j in _BLOG_JUNK):
                continue
            link = normalize_link(abs_link)
            title = sanitize_xml(title.strip())
            if not link or not title:
                continue
            summary = ""
            p = row.find("p")
            if p:
                summary = sanitize_xml(p.get_text(strip=True))
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": _row_date(row) or stable_fallback_date(link),
                    "description": summary,
                }
            )
        except Exception as exc:  # one malformed card is skipped, not fatal
            logger.warning("Skipping a card due to error: %s", exc)
    return entries


def fetch_source() -> list[dict] | None:
    """Fetch and parse every source; return combined entries or None if all fail."""
    all_entries: list[dict] = []
    any_ok = False
    for label, url, keep in SOURCES:
        html = fetch_listing(url)
        if html is None:
            logger.warning("[%s] fetch failed; skipping this source", label)
            continue
        any_ok = True
        rows = parse_listing(html, keep)
        logger.info("[%s] parsed %d entries", label, len(rows))
        all_entries.extend(rows)
    if not any_ok:
        return None
    return all_entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    fg = FeedGenerator()
    fg.id(f"{BLOG_URL}#{feed_name}")
    fg.title(FEED_TITLE)
    fg.subtitle(FEED_DESC)
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language(FEED_LANG)
    fg.author({"name": "HackerOne"})
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
    new_entries = fetch_source()
    if new_entries is None:
        logger.error("All sources failed — skipping write to preserve the last good feed")
        return False
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
    parser = argparse.ArgumentParser(description="Generate the HackerOne Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
