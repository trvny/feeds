"""Bethesda News feed: combined Atom from Bethesda.net news pages.

Sources (none have native RSS):
  * Bethesda.net News PL (bethesda.net/pl-PL/news) — the all-games hub;
    server-rendered ``<a data-element="feed-card">`` cards with a game
    label and an abbreviated Polish date ("11 cze 2026") in
    ``feed-card-sidecar-topic`` elements, the title in ``<h2>``, and the
    blurb in ``feed-card-sidecar-body``. (Some hrefs carry a stray trailing
    "}" — Bethesda's own bug — which is stripped.)
  * The Elder Scrolls News PL (elderscrolls.bethesda.net/pl-PL/news) —
    server-rendered ``<article class="news-module-feed-item">`` cards;
    title in ``news-module-feed-item-title-link``, game and full-name
    Polish date ("09 grudnia 2025") in ``news-module-feed-item-details-*``.
  * Fallout News PL (fallout.bethesda.net) — client-rendered, but backed by
    a clean JSON endpoint at
    ``/_api/v1/components/news?locale=pl`` returning the latest articles
    with ``title``, ``blurb``, ``date_raw`` (ISO), ``game``, and a relative
    ``url`` (rewritten to the canonical ``/pl/article/...`` link).

Deliberately excluded — the Creations / mod-browser pages
(creations.bethesda.net/pl/{fallout4,skyrim}/...): these are a pure SPA
backed by the ``api.bethesda.net/ugcmods/v2/`` API, which is a POST search
that 403s without an attunement auth token, so it can't be scraped from CI.
They are also mod listings rather than news.
"""

import argparse
import datetime
import json
import re
import sys
from urllib.parse import urljoin

import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from multi_rss import get_html, logger, run
from utils import sanitize_xml

FEED_NAME = "bethesda"

MAIN_URL = "https://bethesda.net/pl-PL/news"
ES_URL = "https://elderscrolls.bethesda.net/pl-PL/news"
FO_NEWS_API = "https://fallout.bethesda.net/_api/v1/components/news?locale=pl"

# Polish month names (genitive forms used on the sites) + abbreviations.
PL_MONTHS = {
    "stycznia": 1, "sty": 1, "styczeń": 1,
    "lutego": 2, "lut": 2, "luty": 2,
    "marca": 3, "mar": 3, "marzec": 3,
    "kwietnia": 4, "kwi": 4, "kwiecień": 4,
    "maja": 5, "maj": 5,
    "czerwca": 6, "cze": 6, "czerwiec": 6,
    "lipca": 7, "lip": 7, "lipiec": 7,
    "sierpnia": 8, "sie": 8, "sierpień": 8,
    "września": 9, "wrz": 9, "wrzesień": 9,
    "października": 10, "paź": 10, "październik": 10,
    "listopada": 11, "lis": 11, "listopad": 11,
    "grudnia": 12, "gru": 12, "grudzień": 12,
}

_PL_DATE_RE = re.compile(r"^(\d{1,2})\s+([^\W\d_]+)\.?\s+(\d{4})$", re.UNICODE)


def parse_bethesda_date(s):
    """Parse Bethesda's date strings: Polish "DD <month> YYYY" (full or
    abbreviated) and plain ISO dates. Returns a UTC datetime or None."""
    if not s:
        return None
    s = s.strip()
    m = _PL_DATE_RE.match(s)
    if m:
        day, month, year = m.group(1), m.group(2).lower(), m.group(3)
        if month in PL_MONTHS:
            return datetime.datetime(int(year), PL_MONTHS[month], int(day), tzinfo=pytz.UTC)
    try:
        dt = date_parser.parse(s)
        return dt.replace(tzinfo=pytz.UTC) if dt.tzinfo is None else dt.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError):
        logger.warning(f"  could not parse date {s!r}")
        return None


def _entry(title, link, date, game, desc, fallback_label):
    title = sanitize_xml((title or "").strip())
    desc = sanitize_xml((desc or "").strip())
    return {
        "title": title,
        "link": link.strip(),
        "date": date,
        "description": desc or title,
        "source": sanitize_xml((game or "").strip()) or fallback_label,
    }


def scrape_main(known_links):
    """Article cards from the all-games Bethesda.net news hub."""
    entries, count = [], 0
    html = get_html(MAIN_URL)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.find_all("a", attrs={"data-element": "feed-card"}):
        try:
            href = (card.get("href") or "").strip().rstrip("}")
            h2 = card.find("h2")
            if not href or not h2:
                continue
            href = urljoin(MAIN_URL, href)
            if href in known_links:
                continue
            topics = card.find_all("feed-card-sidecar-topic")
            game = topics[0].get_text(strip=True) if topics else None
            date = parse_bethesda_date(topics[1].get_text(strip=True)) if len(topics) > 1 else None
            body = card.find("feed-card-sidecar-body")
            entries.append(_entry(
                h2.get_text(strip=True), href, date, game,
                body.get_text(" ", strip=True) if body else "", "Bethesda.net",
            ))
            count += 1
        except Exception as e:
            logger.warning(f"  [Bethesda.net] skipping malformed card: {e}")
    logger.info(f"  [Bethesda.net News] {count} new entries")
    return entries


def scrape_elderscrolls(known_links):
    """Cards from the server-rendered Elder Scrolls news module."""
    entries, count = [], 0
    html = get_html(ES_URL)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")
    for art in soup.find_all("article", class_="news-module-feed-item"):
        try:
            a = art.find("a", class_="news-module-feed-item-title-link")
            if not a or not a.get("href"):
                continue
            link = urljoin(ES_URL, a["href"].strip())
            if link in known_links:
                continue
            game_el = art.find("span", class_="news-module-feed-item-details-game")
            date_el = art.find("span", class_="news-module-feed-item-details-date")
            body_el = art.find(class_=re.compile(
                r"news-module-feed-item-(body|excerpt|description|summary)"))
            entries.append(_entry(
                a.get_text(" ", strip=True), link,
                parse_bethesda_date(date_el.get_text(strip=True)) if date_el else None,
                game_el.get_text(strip=True) if game_el else None,
                body_el.get_text(" ", strip=True) if body_el else "",
                "The Elder Scrolls",
            ))
            count += 1
        except Exception as e:
            logger.warning(f"  [The Elder Scrolls] skipping malformed card: {e}")
    logger.info(f"  [The Elder Scrolls News] {count} new entries")
    return entries


def scrape_fallout(known_links):
    """Latest Fallout articles from the JSON news endpoint."""
    entries, count = [], 0
    raw = get_html(FO_NEWS_API)
    if raw is None:
        return entries
    try:
        articles = json.loads(raw).get("articles", [])
    except (ValueError, TypeError) as e:
        logger.warning(f"  [Fallout] news API JSON changed: {e}")
        return entries
    for a in articles:
        try:
            url = (a.get("url") or "").strip()
            title = (a.get("title") or "").strip()
            if not url or not title:
                continue
            link = urljoin("https://fallout.bethesda.net/pl/", url.lstrip("/"))
            if link in known_links:
                continue
            entries.append(_entry(
                title, link, parse_bethesda_date(a.get("date_raw")),
                a.get("game"), a.get("blurb"), "Fallout",
            ))
            count += 1
        except Exception as e:
            logger.warning(f"  [Fallout] skipping malformed item: {e}")
    logger.info(f"  [Fallout News] {count} new entries")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Bethesda News",
        subtitle="Combined Bethesda feed: Bethesda.net News (PL), "
                 "The Elder Scrolls News (PL), and Fallout News (PL).",
        blog_url=MAIN_URL,
        author="Bethesda Softworks",
        extra_scrapers=(scrape_main, scrape_elderscrolls, scrape_fallout),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Bethesda News Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
