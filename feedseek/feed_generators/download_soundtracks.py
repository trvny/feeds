"""Reliable Atom feed for Download Soundtracks with a homepage fallback."""

import argparse
import re
import sys
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run, scrape_feed
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "download-soundtracks"
BLOG_URL = "https://download-soundtracks.com/"
ATOM_URL = urljoin(BLOG_URL, "feed/atom/")
MAX_DISCOVERED = 60


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


def parse_homepage(html, known_links=()):
    """Extract current soundtrack posts from WordPress-style article cards."""
    soup = BeautifulSoup(html or "", "html.parser")
    entries = []
    seen = set(known_links)

    for article in soup.select("article"):
        try:
            heading = article.select_one("h1, h2, h3")
            anchor = heading.find("a", href=True) if heading else None
            if not anchor:
                continue

            link = urljoin(BLOG_URL, anchor["href"]).split("#", 1)[0]
            parsed = urlparse(link)
            if parsed.hostname not in {
                "download-soundtracks.com",
                "www.download-soundtracks.com",
            }:
                continue
            if link in seen or re.search(r"/(?:feed|category|tag|author|page)/", parsed.path):
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
            if len(entries) >= MAX_DISCOVERED:
                break
        except Exception as exc:
            logger.warning("Skipping malformed Download Soundtracks card: %s", exc)

    return entries


def scrape_download_soundtracks(known_links):
    """Prefer the native Atom feed and use the homepage when it yields nothing new."""
    entries = scrape_feed(
        "Download Soundtracks",
        ATOM_URL,
        known_links,
        cap=100,
        keep_html=True,
    )
    if entries:
        return entries

    homepage = get_html(BLOG_URL)
    fallback = parse_homepage(homepage, known_links) if homepage else []
    logger.info("Download Soundtracks homepage fallback: %d entries", len(fallback))
    return fallback


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Download Soundtracks",
        subtitle="New movie, game, television, anime, musical, and trailer soundtrack posts.",
        blog_url=BLOG_URL,
        author="Download Soundtracks",
        extra_scrapers=(scrape_download_soundtracks,),
        max_entries=250,
        per_source_cap=250,
        language="en",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Download Soundtracks Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
