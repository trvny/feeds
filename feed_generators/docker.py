"""Docker feed: combined Atom from Docker's native blog RSS plus scrapers for
the Docker docs release-notes pages, which have no native feed.

The blog (``https://www.docker.com/feed/``) is a real WordPress RSS feed and is
handled by the shared :mod:`multi_rss` pipeline. The release-notes pages on
``docs.docker.com`` are static Hugo pages with one ``<h2 id=...>`` section per
release; :func:`scrape_docs` turns each section into an entry, linking to the
in-page anchor. Dates come from the heading where it is itself a date
(Docker Hub, Docker Platform), from the first ISO date in the section body where
the heading is a version (Docker Desktop, Docker Engine), or from the quarter
for the quarterly Hardened Images notes. History accumulates across hourly runs
via the shared JSON cache (``cache/docker_posts.json``); only links not already
cached trigger work.
"""

import argparse
import re
import sys
from datetime import datetime

import pytz
from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "docker"

# (source label, native feed URL, cap)
SOURCES = [
    ("Docker Blog", "https://www.docker.com/feed/", 40),
]

# Docs release-notes pages: one <h2 id=...> per release, newest first.
# date_mode: "heading_date" (heading is YYYY-MM-DD), "body_date" (heading is a
# version; date is the first ISO date in the section body), "quarter"
# (heading is "Qn YYYY"). cap bounds how many recent sections we take per page,
# so legacy entries don't flood the feed and the cache stays current-focused.
# (label, url, date_mode, cap)
DOCS_PAGES = [
    ("Docker Desktop", "https://docs.docker.com/desktop/release-notes/", "body_date", 25),
    ("Docker Engine", "https://docs.docker.com/engine/release-notes/", "body_date", 25),
    ("Docker Hub", "https://docs.docker.com/docker-hub/release-notes/", "heading_date", 20),
    ("Docker Platform", "https://docs.docker.com/platform-release-notes/", "heading_date", 15),
    ("Docker Hardened Images", "https://docs.docker.com/dhi/release-notes/platform/", "quarter", 8),
]

DESC_LIMIT = 500
_ISO_DATE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
_QUARTER = re.compile(r"\bQ([1-4])\s*(20\d\d)\b", re.I)
_QUARTER_START = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}


def _section_date(date_mode, heading, body):
    """Resolve a tz-aware UTC date for one release section, or None."""
    if date_mode == "heading_date":
        m = _ISO_DATE.search(heading)
        return parse_date(m.group(1)) if m else None
    if date_mode == "body_date":
        m = _ISO_DATE.search(heading) or _ISO_DATE.search(body[:300])
        return parse_date(m.group(1)) if m else None
    if date_mode == "quarter":
        m = _QUARTER.search(heading)
        if m:
            month, day = _QUARTER_START[int(m.group(1))]
            return pytz.UTC.localize(datetime(int(m.group(2)), month, day))
    return None


def _section_description(heading, body):
    """Trim the leading ISO date and collapse whitespace for a clean summary."""
    text = _ISO_DATE.sub("", body, count=1).strip()
    text = re.sub(r"\s+", " ", text)
    return sanitize_xml(text)[:DESC_LIMIT] or heading


def _scrape_page(label, url, date_mode, cap, known_links):
    entries = []
    html = get_html(url)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup

    sections = [h2 for h2 in article.find_all("h2") if h2.get("id")]
    for h2 in sections[:cap]:
        try:
            hid = h2.get("id")
            link = f"{url}#{hid}"
            if link in known_links:
                continue
            heading = h2.get_text(" ", strip=True)
            if not heading:
                continue

            parts, sib = [], h2.find_next_sibling()
            while sib is not None and getattr(sib, "name", None) != "h2":
                parts.append(sib.get_text(" ", strip=True))
                sib = sib.find_next_sibling()
            body = " ".join(p for p in parts if p)

            # Fall back to a stable, deterministic date so a section whose date
            # we can't parse doesn't float to the top with a fresh timestamp.
            date = _section_date(date_mode, heading, body) or stable_fallback_date(link)
            entries.append({
                "title": sanitize_xml(f"{label} {heading}"),
                "link": link,
                "date": date,
                "description": _section_description(heading, body),
                "source": label,
            })
            logger.info(f"  [{label}] {heading}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping malformed section: {e}")
    return entries


def scrape_docs(known_links):
    """Scrape every configured docs release-notes page into entry dicts."""
    entries = []
    for label, url, date_mode, cap in DOCS_PAGES:
        logger.info(f"Scraping {label} ...")
        entries += _scrape_page(label, url, date_mode, cap, known_links)
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Docker",
        subtitle="Combined Docker feed: the Docker Blog plus release notes for "
                 "Docker Desktop, Engine, Hub, Platform, and Hardened Images.",
        blog_url="https://www.docker.com/blog/",
        author="Docker",
        sources=SOURCES,
        extra_scrapers=(scrape_docs,),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Docker Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
