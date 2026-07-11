"""They Said So — Quote of the Day feed.

Standalone quotes feed (kept separate from ``daily_quote``, which is a curated
one-a-day pick from a local gist). Source: the native QOD RSS at
``https://theysaidso.com/qod/feed``, which carries ~8 category quotes per day
(inspire, life, love, art, management, sports, funny, nature, …).

Parsing note: each ``<item>``'s ``<link>`` is a *stable* category URL
(``…/quote-of-the-day/love``) that would collapse every day's quote onto one
dedup key, so the per-quote ``<guid>`` (``…/quote/<slug>``) is used as the link
instead — it's unique per quote, so new daily quotes accumulate correctly. The
quote text lives in ``<description>`` and becomes the entry title; the category
is taken from the ``<link>`` path.

Not included: theysaidso.com/blog has no feed (404 on the usual paths), and
api.quotable.io is dead (the domain no longer resolves), so neither is wired in.
"""

import argparse
import html
import re
import sys

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, stable_fallback_date

FEED_NAME = "theysaidso"
QOD_FEED = "https://theysaidso.com/qod/feed"
_CAT_RE = re.compile(r"/quote-of-the-day/([a-z0-9-]+)", re.I)


def scrape_qod(known_links):
    xml = get_html(QOD_FEED)
    if not xml:
        return []
    soup = BeautifulSoup(xml, "xml")
    entries = []
    for item in soup.find_all("item"):
        try:
            guid = item.find("guid")
            cat_link = item.find("link")
            link = (guid.get_text(strip=True) if guid else "") or (
                cat_link.get_text(strip=True) if cat_link else "")
            if not link or link in known_links:
                continue
            desc_el = item.find("description")
            quote = sanitize_xml(html.unescape(desc_el.get_text(strip=True))) if desc_el else ""
            if not quote:
                continue
            pub = item.find("pubDate")
            date = parse_date(pub.get_text(strip=True)) if pub else None
            category = None
            if cat_link:
                m = _CAT_RE.search(cat_link.get_text(strip=True))
                if m:
                    category = m.group(1).replace("-", " ").title()
            entries.append({
                "title": quote[:300],
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": quote,
                "source": category or "Quote of the Day",
            })
        except Exception:  # one bad item never kills the feed
            continue
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="They Said So — Quote of the Day",
        subtitle="Daily quotes across categories (inspire, life, love, art, "
                 "management, sports, funny, nature) from theysaidso.com.",
        blog_url="https://theysaidso.com/",
        author="They Said So",
        sources=(),
        extra_scrapers=[scrape_qod],
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the They Said So Quote-of-the-Day Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
