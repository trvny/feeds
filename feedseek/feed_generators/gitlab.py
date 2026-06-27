"""GitLab feed: combined Atom from GitLab's blog, release notes, press, and what's new.

Three native feeds are the primary content:
  - about.gitlab.com/atom.xml                        (GitLab Blog)
  - docs.gitlab.com/releases/releases.xml            (GitLab Release Notes)
  - docs.gitlab.com/releases/patch-releases.xml      (GitLab Patch Releases)

Two HTML scrapers supplement for pages with no native feed:
  - about.gitlab.com/press/     (press releases listing)
  - about.gitlab.com/whats-new/ (feature highlights per release)

The about.gitlab.com site is statically generated so plain fetch works fine;
curl_cffi impersonation is not required but get_html() provides it as a fallback.
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

FEED_NAME = "gitlab"
BLOG_URL = "https://about.gitlab.com/"
PRESS_URL = "https://about.gitlab.com/press/"
WHATS_NEW_URL = "https://about.gitlab.com/whats-new/"

SOURCES = [
    ("GitLab Blog", "https://about.gitlab.com/atom.xml", 50),
    ("GitLab Releases", "https://docs.gitlab.com/releases/releases.xml", 40),
    ("GitLab Patch Releases", "https://docs.gitlab.com/releases/patch-releases.xml", 40),
]


def _parse_date(text):
    if not text:
        return None
    try:
        dt = date_parser.parse(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError):
        return None


def _extract_entries(soup, base_url, label, known_links):
    """Extract article-like entries from a BeautifulSoup page."""
    seen = set()
    entries = []

    # Try explicit article elements, then common GitLab static-site card patterns.
    items = soup.find_all("article")
    if not items:
        items = soup.find_all(
            attrs={"class": lambda c: c and any(
                k in " ".join(c).lower()
                for k in ("article", "card", "release", "press", "post", "item", "feature", "tile")
            )}
        )
    # Re-scope to main content area if we matched too many.
    if len(items) > 50:
        main = soup.find(["main", "section"])
        if main:
            items = main.find_all("article") or main.find_all(
                attrs={"class": lambda c: c and any(
                    k in " ".join(c).lower()
                    for k in ("article", "card", "release", "press", "post", "item", "feature")
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
            link = urljoin(base_url, href)
            if link in known_links or link in seen or link == base_url:
                continue
            seen.add(link)

            heading = item.find(["h1", "h2", "h3", "h4"])
            title = sanitize_xml(
                heading.get_text(" ", strip=True) if heading
                else a.get_text(" ", strip=True)
            )
            if not title or len(title) < 5:
                continue

            time_el = item.find("time")
            date_obj = None
            if time_el:
                date_obj = _parse_date(
                    time_el.get("datetime") or time_el.get_text(strip=True)
                )
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

    return entries


def scrape_press(known_links):
    """Scrape about.gitlab.com/press/ for press release entries."""
    html = get_html(PRESS_URL)
    if html is None:
        logger.warning("  [GitLab Press] fetch failed")
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries = _extract_entries(soup, PRESS_URL, "GitLab Press", known_links)
    logger.info(f"  [GitLab Press] {len(entries)} entries")
    return entries


def scrape_whats_new(known_links):
    """Scrape about.gitlab.com/whats-new/ for feature highlight entries."""
    html = get_html(WHATS_NEW_URL)
    if html is None:
        logger.warning("  [GitLab What's New] fetch failed")
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries = _extract_entries(soup, WHATS_NEW_URL, "GitLab What's New", known_links)
    logger.info(f"  [GitLab What's New] {len(entries)} entries")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="GitLab",
        subtitle=(
            "Combined GitLab feed: blog, release notes, patch releases, "
            "press releases, and what's new."
        ),
        blog_url=BLOG_URL,
        author="GitLab",
        sources=SOURCES,
        extra_scrapers=(scrape_press, scrape_whats_new),
        language="en",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the GitLab Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
