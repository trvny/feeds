"""Perplexity feed: combined Atom from Perplexity's Framer-built sites.

Sources (none expose a usable native feed except the API docs changelog,
which is covered by its own RSS):

    - Hub Blog    https://www.perplexity.ai/hub/blog        (Framer listing)
    - Changelog   https://www.perplexity.ai/changelog       (Framer listing)
    - Research    https://research.perplexity.ai/           (Framer listing)
    - API changelog  https://docs.perplexity.ai/docs/resources/changelog/rss.xml (native RSS)

The Framer listings render article cards server-side with relative links
(``./blog/<slug>``, ``./changelog/<slug>``, ``./articles/<slug>``) but the
per-card dates are unreliable to associate, so each *new* article is fetched
once for its ``og:title`` / ``og:description`` meta and the first
human-readable date on the page (Framer renders the publish date first).
The cache gate keeps steady-state runs at zero per-article fetches.
"""

import argparse
import re
import sys
import time

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "perplexity"

# (label, listing URL, relative href regex, absolute base, title_from_description)
# Changelog article pages all share og:title="Perplexity Changelog"; their real
# title (and date) lives in og:description, so that listing flips the flag.
LISTINGS = [
    ("Perplexity Blog", "https://www.perplexity.ai/hub/blog",
     re.compile(r'href="\./(blog/[A-Za-z0-9_-]+)"'), "https://www.perplexity.ai/hub/", False),
    ("Perplexity Changelog", "https://www.perplexity.ai/changelog",
     re.compile(r'href="\./(changelog/[A-Za-z0-9_-]+)"'), "https://www.perplexity.ai/", True),
    ("Perplexity Research", "https://research.perplexity.ai/",
     re.compile(r'href="\./(articles/[A-Za-z0-9_-]+)"'), "https://research.perplexity.ai/", False),
]

RSS_SOURCES = [
    ("Perplexity API changelog",
     "https://docs.perplexity.ai/docs/resources/changelog/rss.xml", 40),
]

DATE_RE = re.compile(
    r"((?:January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4})"
)

SLEEP_BETWEEN = 0.3


def _meta(html, prop):
    m = re.search(rf'<meta[^>]+property="{prop}"[^>]+content="([^"]*)"', html)
    if not m:
        m = re.search(rf'<meta[^>]+content="([^"]*)"[^>]+property="{prop}"', html)
    return m.group(1).strip() if m else None


def _scrape_listing(label, listing_url, href_re, base, known_links, title_from_description=False):
    entries = []
    html = get_html(listing_url)
    if html is None:
        return entries

    slugs = []
    for m in href_re.finditer(html):
        if m.group(1) not in slugs:
            slugs.append(m.group(1))
    if not slugs:
        logger.warning(f"  [{label}] no article links matched — layout may have changed")
        return entries

    for slug in slugs:
        link = base + slug
        if link in known_links:
            continue
        try:
            page = get_html(link)
            time.sleep(SLEEP_BETWEEN)
            if page is None:
                continue
            title = _meta(page, "og:title") or slug.split("/")[-1].replace("-", " ").capitalize()
            desc = _meta(page, "og:description") or title
            if title_from_description and _meta(page, "og:description"):
                title = _meta(page, "og:description").strip()
            dm = DATE_RE.search(desc) if title_from_description else None
            dm = dm or DATE_RE.search(page)
            date_obj = parse_date(dm.group(1)) if dm else stable_fallback_date(link)
            entries.append({
                "title": sanitize_xml(title.strip()),
                "link": link,
                "date": date_obj,
                "description": sanitize_xml(desc)[:500],
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping {slug}: {e}")
    return entries


def scrape_framer_listings(known_links):
    entries = []
    for label, url, href_re, base, tfd in LISTINGS:
        logger.info(f"Scraping {label} ...")
        entries += _scrape_listing(label, url, href_re, base, known_links,
                                   title_from_description=tfd)
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Perplexity",
        subtitle="Combined Perplexity feed: Hub Blog, product Changelog, Research, "
                 "and the API docs changelog.",
        blog_url="https://www.perplexity.ai/hub",
        author="Perplexity",
        sources=RSS_SOURCES,
        extra_scrapers=[scrape_framer_listings],
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Perplexity Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
