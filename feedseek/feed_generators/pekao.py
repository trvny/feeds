"""Pekao feed: combined Atom from Bank Pekao SA's news and media pages.

Google News RSS (``site:pekao.com.pl`` and ``site:media.pekao.com.pl``) provides
the primary reliable content; four direct HTML scrapers supplement with articles
from the specific pages the user wants to track:

  - media.pekao.com.pl/informacje-prasowe  (press releases)
  - media.pekao.com.pl/peoview             (Peoview magazine/newsletter)
  - pekao.com.pl/o-banku/aktualnosci.html  (bank news/updates)
  - pekao.com.pl/private-banking/          (private banking section)

Each scraper uses curl_cffi Chrome impersonation and degrades gracefully:
if the page structure changes or the site returns an error, the scraper
returns an empty list and the Google News sources carry the feed.
"""

import argparse
import sys
from urllib.parse import urljoin

import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from multi_rss import get_html, run
from utils import sanitize_xml, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "pekao"
BLOG_URL = "https://www.pekao.com.pl/"

# Google News with Polish locale, scoped to pekao.com.pl and its media subdomain.
SOURCES = [
    (
        "Pekao (Google News)",
        "https://news.google.com/rss/search?q=when:14d+site:pekao.com.pl"
        "&hl=pl-PL&gl=PL&ceid=PL:pl",
        30,
    ),
    (
        "Pekao Media (Google News)",
        "https://news.google.com/rss/search?q=when:14d+site:media.pekao.com.pl"
        "&hl=pl-PL&gl=PL&ceid=PL:pl",
        20,
    ),
]


def _parse_date(text):
    if not text:
        return None
    try:
        dt = date_parser.parse(text, dayfirst=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError):
        return None


def _scrape_page(url, label, known_links):
    """Generic article scraper for pekao.com.pl and media.pekao.com.pl pages.

    Tries article elements and common news-card class patterns, then narrows
    to the main content area to avoid nav/footer noise.
    """
    html = get_html(url)
    if html is None:
        logger.warning(f"  [{label}] fetch failed for {url}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    entries = []

    # Try explicit article elements first, then common news-card class patterns.
    items = soup.find_all("article")
    if not items:
        items = soup.find_all(
            attrs={"class": lambda c: c and any(
                k in " ".join(c).lower()
                for k in ("news", "article", "post", "card", "item", "press", "tile", "entry")
            )}
        )
    # If we matched too many elements (likely nav/footer noise), re-scope to main.
    if len(items) > 50:
        main = soup.find(["main", "section"]) or soup.find(
            id=lambda i: i and "content" in i.lower()
        )
        if main:
            items = main.find_all("article") or main.find_all(
                attrs={"class": lambda c: c and any(
                    k in " ".join(c).lower()
                    for k in ("news", "article", "post", "card", "item", "press", "tile", "entry")
                )}
            )

    for item in items:
        try:
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            link = urljoin(url, href)
            if link in known_links or link in seen or link == url:
                continue
            seen.add(link)

            heading = item.find(["h1", "h2", "h3", "h4"])
            title = sanitize_xml(
                heading.get_text(" ", strip=True) if heading
                else a.get_text(" ", strip=True)
            )
            if not title or len(title) < 5:
                continue

            # Date: prefer <time datetime="...">, then short date-like text nodes.
            time_el = item.find("time")
            date_obj = None
            if time_el:
                date_obj = _parse_date(
                    time_el.get("datetime") or time_el.get_text(strip=True)
                )
            if date_obj is None:
                for el in item.find_all(["span", "p", "div", "small"], limit=8):
                    text = el.get_text(strip=True)
                    if 5 < len(text) < 30 and any(ch.isdigit() for ch in text):
                        date_obj = _parse_date(text)
                        if date_obj:
                            break
            if date_obj is None:
                date_obj = stable_fallback_date(link)

            desc_el = item.find("p")
            description = (
                sanitize_xml(desc_el.get_text(" ", strip=True)[:400])
                if desc_el else title
            )

            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": description or title,
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping item: {e}")

    logger.info(f"  [{label}] {len(entries)} entries")
    return entries


def scrape_informacje_prasowe(known_links):
    return _scrape_page(
        "https://media.pekao.com.pl/informacje-prasowe",
        "Pekao Informacje Prasowe",
        known_links,
    )


def scrape_peoview(known_links):
    return _scrape_page(
        "https://media.pekao.com.pl/peoview",
        "Pekao Peoview",
        known_links,
    )


def scrape_aktualnosci(known_links):
    return _scrape_page(
        "https://www.pekao.com.pl/o-banku/aktualnosci.html",
        "Pekao Aktualnosci",
        known_links,
    )


def scrape_private_banking(known_links):
    return _scrape_page(
        "https://www.pekao.com.pl/private-banking/",
        "Pekao Private Banking",
        known_links,
    )


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Bank Pekao SA",
        subtitle=(
            "Aktualnosci, informacje prasowe i Peoview Banku Pekao SA. "
            "Zrodla: pekao.com.pl i media.pekao.com.pl."
        ),
        blog_url=BLOG_URL,
        author="Bank Pekao SA",
        sources=SOURCES,
        extra_scrapers=(
            scrape_informacje_prasowe,
            scrape_peoview,
            scrape_aktualnosci,
            scrape_private_banking,
        ),
        language="pl",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Pekao Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
