"""Atom feed scraped from Download Soundtracks HTML.

The origin blocks GitHub-hosted runner IPs with HTTP 403 even while normal
residential requests succeed. Since 03.09.2026 scheduled generation therefore
uses Feedseek's host-locked ``feeds-proxy`` route on GitHub Actions. Outside
Actions the scraper keeps the origin as the preferred path and only falls back
to the proxy if the direct request fails. The proxy route is restricted to
``download-soundtracks.com`` and was verified live before re-enabling the feed.
"""

import argparse
import os
import re
import sys
from urllib.parse import urlencode, urljoin, urlparse

from bs4 import BeautifulSoup
from multi_rss import get_html, parse_date, run
from utils import normalize_link, sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "download-soundtracks"
BLOG_URL = "https://download-soundtracks.com/"
PROXY_URL = "https://feeds.trfny.com/download-soundtracks"
MAX_ENTRIES = 250
MAX_PAGES = 25
MAX_STALE_PAGES = 2
TITLE_LINK_SELECTOR = ".entry-title a[href], h1 a[href], h2 a[href], h3 a[href]"
LISTING_PATH_RE = re.compile(r"/(?:feed|category|tag|author|page)(?:/|$)")


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


def _title_anchor(article):
    return article.select_one(TITLE_LINK_SELECTOR)


def _article_link(article):
    anchor = _title_anchor(article)
    if not anchor:
        return None

    link = normalize_link(urljoin(BLOG_URL, anchor["href"]).split("#", 1)[0])
    parsed = urlparse(link)
    if parsed.hostname not in {
        "download-soundtracks.com",
        "www.download-soundtracks.com",
    }:
        return None
    if LISTING_PATH_RE.search(parsed.path):
        return None
    return link


def _listing_signature(articles):
    return frozenset(filter(None, (_article_link(article) for article in articles)))


def parse_homepage(document, known_links=()):
    """Extract soundtrack posts from HTML text or an already parsed listing page."""
    soup = (
        document
        if isinstance(document, BeautifulSoup)
        else BeautifulSoup(document or "", "html.parser")
    )
    entries = []
    seen = {normalize_link(link) for link in known_links}

    for article in soup.select("article"):
        try:
            anchor = _title_anchor(article)
            link = _article_link(article)
            if not anchor or not link or link in seen:
                continue

            title = sanitize_xml(anchor.get_text(" ", strip=True))
            if not title:
                continue

            summary = article.select_one(
                ".entry-summary, .post-excerpt, .entry-content, .post-content"
            )
            description = (
                sanitize_xml(summary.get_text(" ", strip=True))[:1000]
                if summary
                else title
            )
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": _article_date(article),
                    "description": description or title,
                    "source": _source_from_article(article),
                    "image": _article_image(article),
                }
            )
            seen.add(link)
        except Exception as exc:
            logger.warning("Skipping malformed Download Soundtracks card: %s", exc)

    return entries


def _page_url(page):
    return BLOG_URL if page == 1 else urljoin(BLOG_URL, f"page/{page}/")


def _proxy_url(page):
    path = "/" if page == 1 else f"/page/{page}/"
    return f"{PROXY_URL}?{urlencode({'path': path})}"


def _fetch_listing_html(page):
    direct = _page_url(page)
    proxy = _proxy_url(page)
    urls = (proxy, direct) if os.getenv("GITHUB_ACTIONS") == "true" else (direct, proxy)
    for url in urls:
        html = get_html(url)
        if html:
            return html
    return None


def scrape_download_soundtracks(known_links):
    """Crawl listing pages and return entries oldest-first for Feedseek merging."""
    entries = []
    seen = {normalize_link(link) for link in known_links}
    page_signatures = set()
    stale_pages = 0

    for page in range(1, MAX_PAGES + 1):
        html = _fetch_listing_html(page)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("article")
        signature = _listing_signature(articles)
        if not signature:
            if articles:
                logger.warning("Download Soundtracks listing has no recognizable post links")
            break
        if signature in page_signatures:
            break
        page_signatures.add(signature)

        page_entries = parse_homepage(soup, seen)
        if page_entries:
            stale_pages = 0
        else:
            stale_pages += 1

        entries.extend(page_entries)
        seen.update(entry["link"] for entry in page_entries)
        if len(entries) >= MAX_ENTRIES or stale_pages >= MAX_STALE_PAGES:
            break

    entries = entries[:MAX_ENTRIES]
    entries.reverse()
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
