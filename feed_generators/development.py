"""Dormant combined development feed for Rust, Django, and related sources.

This module is intentionally not registered in ``feeds.yaml`` yet. It can be
expanded and verified before Feedseek starts publishing it.
"""

import argparse
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "development"

# Direct/original feeds come before the Django community aggregator so exact-link
# dedupe keeps the most specific source attribution.
SOURCES = [
    ("Rust Blog", "https://blog.rust-lang.org/feed.xml", 40),
    ("Inside Rust", "https://blog.rust-lang.org/inside-rust/feed.xml", 40),
    ("TestDriven.io", "https://testdriven.io/feed.xml", 30),
    ("Django Weblog", "https://www.djangoproject.com/rss/weblog/", 30),
    ("Django News", "https://django-news.com/rss", 30),
    ("Django Packages latest", "https://djangopackages.org/feeds/packages/latest/atom/", 3),
    ("Django Community", "https://www.djangoproject.com/rss/community/blogs/", 40),
]

RUST_RELEASES_URL = "https://blog.rust-lang.org/releases/"
RUST_RELEASES_MAX = 30
DJANGO_PACKAGES_CHANGELOG_URL = "https://djangopackages.org/changelog/"
DJANGO_PACKAGES_CHANGELOG_MAX = 20

_RUST_RELEASE_DATE = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")


def scrape_rust_releases(known_links):
    """Read the official Rust releases index.

    The page is a release-only subset of the main Rust blog. Keeping it as a
    source gives the aggregate deeper release history; shared link dedupe removes
    announcements already present in the main blog feed.
    """
    html = get_html(RUST_RELEASES_URL)
    if not html:
        logger.warning("  [Rust Releases] fetch failed; continuing")
        return []

    soup = BeautifulSoup(html, "html.parser")
    entries, seen = [], set()
    for anchor in soup.find_all("a", href=True):
        title = anchor.get_text(" ", strip=True)
        if not title.startswith("Announcing Rust"):
            continue
        link = urljoin(RUST_RELEASES_URL, anchor["href"])
        if link in known_links or link in seen:
            continue
        seen.add(link)

        match = _RUST_RELEASE_DATE.search(link)
        date = parse_date("-".join(match.groups())) if match else None
        entries.append(
            {
                "title": sanitize_xml(title),
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": sanitize_xml(title),
                "source": "Rust Releases",
            }
        )
        if len(entries) >= RUST_RELEASES_MAX:
            break
    return entries


def scrape_django_packages_changelog(known_links):
    """Read dated entries from the Django Packages changelog page."""
    html = get_html(DJANGO_PACKAGES_CHANGELOG_URL)
    if not html:
        logger.warning("  [Django Packages changelog] fetch failed; continuing")
        return []

    soup = BeautifulSoup(html, "html.parser")
    entries, seen = [], set()
    for heading in soup.find_all("h2"):
        anchor = heading.find("a", href=True)
        if not anchor or "/changelog/" not in anchor["href"]:
            continue
        link = urljoin(DJANGO_PACKAGES_CHANGELOG_URL, anchor["href"])
        if link.rstrip("/") == DJANGO_PACKAGES_CHANGELOG_URL.rstrip("/"):
            continue
        if link in known_links or link in seen:
            continue

        date_node = heading.parent.select_one(".text-muted-foreground")
        date_text = date_node.get_text(" ", strip=True) if date_node else ""
        date = parse_date(date_text) if date_text else None
        title = anchor.get_text(" ", strip=True)
        if not title:
            continue

        seen.add(link)
        entries.append(
            {
                "title": sanitize_xml(title),
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": sanitize_xml(title),
                "source": "Django Packages changelog",
            }
        )
        if len(entries) >= DJANGO_PACKAGES_CHANGELOG_MAX:
            break
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Development",
        subtitle="Combined Rust, Django, TestDriven.io, and development ecosystem updates.",
        blog_url="https://blog.rust-lang.org/",
        author="development communities",
        sources=SOURCES,
        extra_scrapers=[scrape_rust_releases, scrape_django_packages_changelog],
        max_entries=300,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined development feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
