"""They Said So — Quote of the Day + Verse of the Day feed.

Standalone quotes feed (kept separate from ``daily_quote``, which is a curated
one-a-day pick from a local gist). Two sources are merged into one feed:

* **Quote of the Day** — the native QOD RSS at ``https://theysaidso.com/qod/feed``,
  which carries ~8 category quotes per day (inspire, life, love, art,
  management, sports, funny, nature, …). No key required.
* **Verse of the Day** — the They Said So Bible API
  (``https://quotes.rest/bible/vod.json``). Public access is rate-limited to
  10 calls/hour and now requires auth, so this source only contributes when an
  API key is present. Provide it via the ``THEYSAIDSO_API_KEY`` environment
  variable (a GitHub Actions secret in CI); with a key the limit is 5000/hour.
  Sent as the ``X-TheySaidSo-Api-Secret`` request header. When the key is
  absent the scraper logs and returns nothing, so the QOD half still publishes.

Parsing notes:
* QOD — each ``<item>``'s ``<link>`` is a *stable* category URL
  (``…/quote-of-the-day/love``) that would collapse every day's quote onto one
  dedup key, so the per-quote ``<guid>`` (``…/quote/<slug>``) is used as the
  link instead — it's unique per quote, so new daily quotes accumulate.
* VOD — the verse ``permalink`` can repeat when a verse recurs, so the dedup
  link is suffixed with the verse's date (``permalink#YYYY-MM-DD``) to keep one
  entry per day. Identical verse *text* on different days still collapses via
  the title-level cross-source dedup, which is fine.

Not included: theysaidso.com/blog has no feed (404 on the usual paths), and
api.quotable.io is dead (the domain no longer resolves), so neither is wired in.
"""

import argparse
import html
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "theysaidso"
QOD_FEED = "https://theysaidso.com/qod/feed"
VOD_URL = "https://quotes.rest/bible/vod.json"
API_KEY = os.getenv("THEYSAIDSO_API_KEY", "").strip()
_CAT_RE = re.compile(r"/quote-of-the-day/([a-z0-9-]+)", re.I)


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
                cat_link.get_text(strip=True) if cat_link else "")
            if not link or link in known_links:
                continue
            desc_el = item.find("description")
            quote = sanitize_xml(html.unescape(desc_el.get_text(strip=True))) if desc_el else ""
            if not quote:
                continue
            pub = item.find("pubDate")
            date = parse_date(pub.get_text(strip=True)) if pub else None
            category = None
            if cat_link:
                m = _CAT_RE.search(cat_link.get_text(strip=True))
                if m:
                    category = m.group(1).replace("-", " ").title()
            entries.append({
                "title": quote[:300],
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": quote,
                "source": category or "Quote of the Day",
            })
        except Exception:  # one bad item never kills the feed
            continue
    return entries


def scrape_votd(known_links):
    """Verse of the Day from the They Said So Bible API. No-ops without a key."""
    if not API_KEY:
        logger.info(
            "THEYSAIDSO_API_KEY not set — skipping Verse of the Day "
            "(quotes still publish). Add it as an Actions secret to enable."
        )
        return []
    try:
        resp = requests.get(
            VOD_URL,
            headers={"X-TheySaidSo-Api-Secret": API_KEY, "Accept": "application/json"},
            timeout=30,
        )
    except Exception as e:
        logger.warning(f"Verse of the Day fetch failed: {e}")
        return []
    if resp.status_code != 200:
        logger.warning(f"Verse of the Day returned HTTP {resp.status_code}: {resp.text[:200]}")
        return []
    try:
        verses = resp.json().get("contents", {}).get("verses", [])
    except (ValueError, AttributeError) as e:
        logger.warning(f"Verse of the Day: bad JSON: {e}")
        return []

    entries = []
    for v in verses:
        try:
            text = sanitize_xml(html.unescape((v.get("verse") or "").strip()))
            if not text:
                continue
            reference = (v.get("reference") or "").strip()
            permalink = (v.get("permalink") or "https://theysaidso.com/").strip()
            date_str = (v.get("date") or "").strip()
            date = parse_date(date_str) if date_str else None
            # Suffix the permalink with the date so each day is a distinct dedup
            # key even when the same verse recurs.
            link = f"{permalink}#{date_str}" if date_str else permalink
            if link in known_links:
                continue
            desc = f"{text} — {reference}" if reference else text
            entries.append({
                "title": text[:300],
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": desc,
                "source": "Verse of the Day",
            })
        except Exception:  # one bad verse never kills the feed
            continue
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="They Said So — Quote & Verse of the Day",
        subtitle="Daily quotes across categories (inspire, life, love, art, "
                 "management, sports, funny, nature) plus a daily Bible verse "
                 "from theysaidso.com.",
        blog_url="https://theysaidso.com/",
        author="They Said So",
        sources=(),
        extra_scrapers=[scrape_qod, scrape_votd],
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the They Said So Quote & Verse-of-the-Day Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
