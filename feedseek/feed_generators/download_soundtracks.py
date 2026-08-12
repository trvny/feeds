"""Atom feed scraped directly from Download Soundtracks HTML."""

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import normalize_link, sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "download-soundtracks"
BLOG_URL = "https://download-soundtracks.com/"
MAX_ENTRIES = 250
MAX_PAGES = 25


def _source_from_article(article):
    category = article.select_one('a[rel~="category"], .cat-links a, .entry-category a')
    if not category:
        return "Download Soundtracks"
    label = sanitize_xml(category.get_text(" ", strip=True))
    return f"Download Soundtracks / {label}" if label else "Download Soundtracks"


def _article_date(article):
    time_el = article.find("time")
    if not time_el:
        return None
    raw = time_el.get("datetime") or time_el.get_text(" ", strip=True)
    return parse_date(raw)


def _article_image(article):
    image = article.find("img")
    if not image:
        return None
    value = image.get("src") or image.get("data-src")
    if not value and image.get("srcset"):
        value = image["srcset"].split(",", 1)[0].strip().split(" ", 1)[0]
    return urljoin(BLOG_URL, value) if value else None


def _listing_signature(articles):
    links = []
    for article in articles:
        anchor = article.select_one("h1 a[href], h2 a[href], h3 a[href]")
        if anchor:
            links.append(normalize_link(urljoin(BLOG_URL, anchor["href"])))
    return frozenset(links)


def parse_homepage(html, known_links=(), fallback_time=None, fallback_offset=0):
    """Extract soundtrack posts from one WordPress-style listing page."""
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html or "", "html.parser")
    entries = []
    seen = {normalize_link(link) for link in known_links}
    fallback_time = fallback_time or datetime.now(timezone.utc)

    for position, article in enumerate(soup.select("article")):
        try:
            heading = article.select_one("h1, h2, h3")
            anchor = heading.find("a", href=True) if heading else None
            if not anchor:
                continue

            link = urljoin(BLOG_URL, anchor["href"]).split("#", 1)[0]
            parsed = urlparse(link)
            normalized = normalize_link(link)
            if parsed.hostname not in {
                "download-soundtracks.com",
                "www.download-soundtracks.com",
            }:
                continue
            if normalized in seen or re.search(
                r"/(?:feed|category|tag|author|page)/", parsed.path
            ):
                continue

            title = sanitize_xml(heading.get_text(" ", strip=True))
            if not title:
                continue

            summary = article.select_one(".entry-summary, .post-excerpt, p")
            description = (
                sanitize_xml(summary.get_text(" ", strip=True))[:1000]
                if summary
                else title
            )
            published = _article_date(article) or fallback_time - timedelta(
                microseconds=fallback_offset + position
            )
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": published,
                    "description": description or title,
                    "source": _source_from_article(article),
                    "image": _article_image(article),
                }
            )
            seen.add(normalized)
        except Exception as exc:
            logger.warning("Skipping malformed Download Soundtracks card: %s", exc)

    return entries


def _page_url(page):
    return BLOG_URL if page == 1 else urljoin(BLOG_URL, f"page/{page}/")


def scrape_download_soundtracks(known_links):
    """Crawl website listing pages; intentionally ignore the broken native feed."""
    entries = []
    seen = {normalize_link(link) for link in known_links}
    page_signatures = set()
    crawl_time = datetime.now(timezone.utc)
    listing_offset = 0

    for page in range(1, MAX_PAGES + 1):
        html = get_html(_page_url(page))
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("article")
        signature = _listing_signature(articles)
        if not signature or signature in page_signatures:
            break
        page_signatures.add(signature)

        page_entries = parse_homepage(
            soup,
            seen,
            fallback_time=crawl_time,
            fallback_offset=listing_offset,
        )
        listing_offset += len(articles)
        entries.extend(page_entries)
        seen.update(normalize_link(entry["link"]) for entry in page_entries)
        if len(entries) >= MAX_ENTRIES:
            break

    entries = entries[:MAX_ENTRIES]
    logger.info("Download Soundtracks website scrape: %d entries", len(entries))
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Download Soundtracks",
        subtitle="New movie, game, television, anime, musical, and trailer soundtrack posts.",
        blog_url=BLOG_URL,
        author="Download Soundtracks",
        extra_scrapers=(scrape_download_soundtracks,),
        max_entries=MAX_ENTRIES,
        per_source_cap=MAX_ENTRIES,
        language="en",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Download Soundtracks Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
