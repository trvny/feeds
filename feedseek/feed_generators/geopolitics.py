"""Geopolitics feed: combined Atom stream of defence and foreign-policy think
tanks — ISW, RUSI, CSIS, and the Carnegie Endowment.

Only RUSI publishes usable native feeds (latest-commentary + latest-publications;
whats-new.xml is skipped because it mixes in years-old conference pages). The
other three need scraping:

- ISW (understandingwar.org) is WordPress but every feed route (/feed,
  ?feed=rss2) 302s to the homepage, and robots.txt disallows /wp-json/. The
  Research Library at /research/ is server-rendered, so the cards there
  (div.research-card-loop-item-3colgrid) are the source: title, link, and a
  "Mon D, YYYY" date, no per-article fetch needed.
- CSIS still serves /rss.xml but it froze in 2016; the /analysis listing is
  server-rendered Drupal (article.article-search-listing) with title, teaser,
  thumbnail, and a trailing "— July 23, 2026" byline date.
- Carnegie runs a Payload CMS behind Next.js: the listing pages are
  client-rendered, and /api/posts + /api/research return paths and timestamps
  but strip `title` via field-level access control. So the API supplies the
  URL list and each *new* article page is fetched once for its og: tags.
  Cached links are skipped, so a normal run costs a handful of requests.
"""

import argparse
import json
import re
import sys

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import favicon_proxy, sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "geopolitics"

SOURCES = [
    ("RUSI Commentary", "https://www.rusi.org/rss/latest-commentary.xml", 40),
    ("RUSI Publications", "https://www.rusi.org/rss/latest-publications.xml", 40),
]

ISW_URL = "https://understandingwar.org/research/"
CSIS_URL = "https://www.csis.org/analysis"
CARNEGIE_API = "https://carnegieendowment.org/api/{collection}?limit=20&sort=-createdAt&depth=0"
CARNEGIE_COLLECTIONS = ("posts", "research")
CARNEGIE_MAX_FETCHES = 25  # per run; only unseen links cost a request

_DATE_RE = re.compile(
    r"\b([A-Z][a-z]{2,8}\.?\s+\d{1,2},\s+20\d\d)\b"
)
_META_RE = re.compile(
    r'<meta[^>]+(?:property|name)="(og:title|og:description|article:published_time)"'
    r'[^>]+content="([^"]*)"',
    re.I,
)


def _abs(base, href):
    if href.startswith("http"):
        return href
    return base.rstrip("/") + "/" + href.lstrip("/")


def scrape_isw(known_links):
    """ISW Research Library cards."""
    html = get_html(ISW_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries, seen = [], set()
    for card in soup.select("div.research-card-loop-item-3colgrid"):
        try:
            anchor = card.select_one("h3.research-card-title a")
            if not anchor or not anchor.get("href"):
                continue
            link = _abs("https://understandingwar.org", anchor["href"].split("?")[0])
            if link in seen or link in known_links:
                continue
            title = anchor.get_text(" ", strip=True)
            if len(title) < 8:
                continue
            text = card.get_text(" ", strip=True)
            match = _DATE_RE.search(text)
            seen.add(link)
            entries.append({
                "title": sanitize_xml(title[:250]),
                "link": link,
                "date": parse_date(match.group(1)) if match else None,
                "description": sanitize_xml(title[:250]),
                "source": "ISW",
            })
        except Exception as exc:  # one bad card never kills the run
            logger.warning("  [ISW] skipping card: %s", exc)
    return entries


def scrape_csis(known_links):
    """CSIS /analysis listing cards."""
    html = get_html(CSIS_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries, seen = [], set()
    for card in soup.select("article.article-search-listing"):
        try:
            anchor = card.select_one("h3 a[href]")
            if not anchor:
                continue
            link = _abs("https://www.csis.org", anchor["href"].split("?")[0])
            if link in seen or link in known_links:
                continue
            title = anchor.get_text(" ", strip=True)
            if len(title) < 8:
                continue
            summary_el = card.select_one(".search-listing--summary")
            summary = summary_el.get_text(" ", strip=True) if summary_el else ""
            match = _DATE_RE.search(card.get_text(" ", strip=True))
            image_el = card.select_one("img[src]")
            image = _abs("https://www.csis.org", image_el["src"]) if image_el else None
            seen.add(link)
            entries.append({
                "title": sanitize_xml(title[:250]),
                "link": link,
                "date": parse_date(match.group(1)) if match else None,
                "description": sanitize_xml(summary[:500] or title[:250]),
                "source": "CSIS",
                "image": image,
            })
        except Exception as exc:
            logger.warning("  [CSIS] skipping card: %s", exc)
    return entries


def _carnegie_paths(collection):
    raw = get_html(CARNEGIE_API.format(collection=collection))
    if not raw:
        return []
    try:
        docs = json.loads(raw).get("docs", [])
    except ValueError as exc:
        logger.warning("  [Carnegie] skipping item: %s", exc)
        return []
    paths = []
    for doc in docs:
        path = (doc.get("path") or {}).get("canonicalPath") or (doc.get("path") or {}).get("path")
        if path:
            paths.append("https://carnegieendowment.org" + path)
    return paths


def scrape_carnegie(known_links):
    """Carnegie: Payload API for the URL list, og: tags for the metadata."""
    links = []
    for collection in CARNEGIE_COLLECTIONS:
        for link in _carnegie_paths(collection):
            if link not in known_links and link not in links:
                links.append(link)
    entries = []
    for link in links[:CARNEGIE_MAX_FETCHES]:
        try:
            html = get_html(link)
            if not html:
                continue
            meta = {key.lower(): value for key, value in _META_RE.findall(html)}
            title = meta.get("og:title", "").strip()
            if len(title) < 8:
                continue
            entries.append({
                "title": sanitize_xml(title[:250]),
                "link": link,
                "date": parse_date(meta.get("article:published_time", "")) or None,
                "description": sanitize_xml(
                    (meta.get("og:description") or title)[:500]
                ),
                "source": "Carnegie Endowment",
            })
        except Exception as exc:
            logger.warning("  [Carnegie] skipping item: %s", exc)
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Geopolitics",
        subtitle="Combined think-tank feed: ISW, RUSI, CSIS, and the Carnegie "
                 "Endowment for International Peace.",
        blog_url="https://understandingwar.org/research/",
        icon=favicon_proxy("understandingwar.org"),
        author="various",
        sources=SOURCES,
        extra_scrapers=[scrape_isw, scrape_csis, scrape_carnegie],
        max_entries=300,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the geopolitics Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
