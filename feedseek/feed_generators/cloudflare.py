"""Cloudflare feed: combined Atom from Cloudflare's native RSS feeds — the
Cloudflare Blog, the developer Changelog, and the Community top topics — plus a
scraper for Cloudflare Research publications, which have no native feed.

The native feed sources are handled by the shared :mod:`multi_rss` pipeline. The
Research site lists publications as top-level ``/<author><year>`` slugs (e.g.
``/nikulin2026``) with no feed and no per-post date beyond the year encoded in
the slug, so :func:`scrape_research` collects those, derives the date from the
slug year, and reads the clean title from each publication's ``<h1>``. History
accumulates across hourly runs via the shared JSON cache
(``cache/cloudflare_posts.json``); only new links trigger a page fetch.
"""

import argparse
import re
import sys
from datetime import datetime

import pytz
from bs4 import BeautifulSoup

from multi_rss import get_html, run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "cloudflare"

# (source label, native feed URL, cap)
SOURCES = [
    ("Cloudflare Blog", "https://blog.cloudflare.com/rss", 40),
    ("Cloudflare Changelog", "https://developers.cloudflare.com/changelog/rss/index.xml", 40),
    ("Cloudflare Community", "https://community.cloudflare.com/top.rss", 40),
    ("Cloudflare Status", "https://new.cloudflarestatus.com/api/v3/incidents.atom", 30),
    ("Cloudflare Maintenance", "https://new.cloudflarestatus.com/api/v3/maintenance.atom", 15),
]

# Cloudflare Research publications: top-level author+year slugs, e.g.
# /nikulin2026, /turner2026, /antunes2025. No native feed exists.
RESEARCH_BASE = "https://research.cloudflare.com"
RESEARCH_LABEL = "Cloudflare Research"
RESEARCH_SLUG = re.compile(r"^/([a-z]+)(20\d\d)/?$")


def scrape_research(known_links):
    """Scrape the Cloudflare Research home page for publication links. Date is
    the slug year (the only date the site exposes); title is the page <h1>."""
    entries = []
    html = get_html(RESEARCH_BASE + "/")
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")

    seen = set()
    for a in soup.find_all("a", href=True):
        m = RESEARCH_SLUG.match(a["href"])
        if not m:
            continue
        link = RESEARCH_BASE + "/" + a["href"].lstrip("/").rstrip("/")
        if link in seen or link in known_links:
            continue
        seen.add(link)

        year = int(m.group(2))
        date_obj = pytz.UTC.localize(datetime(year, 1, 1))

        title = None
        page = get_html(link)
        if page:
            h1 = BeautifulSoup(page, "html.parser").find("h1")
            if h1:
                title = h1.get_text(" ", strip=True)
        if not title:  # fall back to link text with the leading year stripped
            title = re.sub(r"^\s*20\d\d\s+", "", a.get_text(" ", strip=True))
        title = sanitize_xml(title) or link

        entries.append({
            "title": title,
            "link": link,
            "date": date_obj,
            "description": title,
            "source": RESEARCH_LABEL,
        })
        logger.info(f"  [{RESEARCH_LABEL}] {title}")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Cloudflare",
        subtitle="Combined Cloudflare feed: the Cloudflare Blog, the developer "
                 "Changelog, Community top topics, Status incidents and "
                 "maintenance, and Cloudflare Research publications.",
        blog_url="https://blog.cloudflare.com/",
        author="Cloudflare",
        sources=SOURCES,
        extra_scrapers=(scrape_research,),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Cloudflare Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
