"""Unsplash feed: one combined Atom stream for the blog, the API changelog, and
(optionally) a stream of fresh wallpaper photos.

Sources:
  * Unsplash Blog   https://unsplash.com/blog/rss/            native RSS
  * Unsplash Status https://status.unsplash.com/history.atom  incident history (Atom)
  * API Changelog   https://unsplash.com/documentation/changelog
                    server-rendered doc page (no feed): each change is an
                    ``<h2 id=...>`` title followed by ``<p><strong>Month D,
                    YYYY</strong></p>`` and a body paragraph. Low-volume and
                    historical, but stable; the combined feed's freshness is
                    driven by the blog.
  * Wallpapers      https://api.unsplash.com/topics/wallpapers/photos
                    the "daily image / wallpapers" part. Unsplash walled off
                    every keyless path — the internal ``/napi`` endpoints now
                    return 401 and the topic/home pages are empty JS shells with
                    no preloaded data — so fresh photos require the official API
                    and a (free) access key. This source is therefore gated on
                    the ``UNSPLASH_ACCESS_KEY`` env var: set it as an Actions
                    secret and each run folds in the newest wallpapers (deduped
                    by photo page URL); leave it unset and the source is simply
                    skipped, so the blog + changelog feed still builds.
"""

import argparse
import os
import sys

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "unsplash"

SOURCES = [
    ("Unsplash Blog", "https://unsplash.com/blog/rss/", 30),
    ("Unsplash Status", "https://status.unsplash.com/history.atom", 15),
]

CHANGELOG_URL = "https://unsplash.com/documentation/changelog"


def scrape_changelog(known_links):
    """Parse the API changelog doc page into entries.

    Layout per change: ``<h2 id="slug">Title</h2>`` then ``<p><strong>date
    </strong></p>`` then one or more body ``<p>``. The ``id`` gives a stable
    per-entry permalink (``…/changelog#slug``).
    """
    html = get_html(CHANGELOG_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for h2 in soup.find_all("h2"):
        anchor = h2.get("id")
        if not anchor:
            continue
        title = sanitize_xml(h2.get_text(" ", strip=True))
        if not title:
            continue
        link = f"{CHANGELOG_URL}#{anchor}"
        if link in known_links:
            continue
        # Walk forward siblings until the next h2, collecting date + body.
        date, body = None, ""
        for sib in h2.find_next_siblings():
            if sib.name == "h2":
                break
            text = sib.get_text(" ", strip=True)
            if not text:
                continue
            if date is None and sib.find("strong"):
                date = parse_date(sib.get_text(" ", strip=True))
                continue
            if not body:
                body = text
        entries.append({
            "title": title,
            "link": link,
            "date": date or stable_fallback_date(link),
            "description": sanitize_xml(body or title)[:500],
            "source": "API Changelog",
        })
    return entries


def scrape_wallpapers(known_links):
    """Fresh wallpaper photos via the official API. No-op without a key."""
    key = (os.environ.get("UNSPLASH_ACCESS_KEY") or "").strip()
    if not key:
        logger.info("[Wallpapers] UNSPLASH_ACCESS_KEY not set — skipping photo source")
        return []
    try:
        import requests

        resp = requests.get(
            "https://api.unsplash.com/topics/wallpapers/photos",
            params={"per_page": 12, "order_by": "latest"},
            headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"},
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning(f"[Wallpapers] API returned HTTP {resp.status_code}")
            return []
        photos = resp.json()
    except Exception as e:
        logger.warning(f"[Wallpapers] fetch failed: {e}")
        return []

    entries = []
    for p in photos if isinstance(photos, list) else []:
        try:
            link = (p.get("links") or {}).get("html")
            if not link or link in known_links:
                continue
            author = (p.get("user") or {}).get("name") or "Unsplash"
            caption = p.get("description") or p.get("alt_description") or "Wallpaper"
            img = (p.get("urls") or {}).get("regular") or (p.get("urls") or {}).get("full") or ""
            date = parse_date(p.get("created_at") or p.get("updated_at") or "")
            entries.append({
                "title": sanitize_xml(f"{caption} — by {author}"[:200]),
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": sanitize_xml(f"Photo by {author}. {caption}. {img}")[:500],
                "source": "Wallpapers",
            })
        except Exception:  # one bad photo never kills the feed
            continue
    logger.info(f"[Wallpapers] collected {len(entries)} photo(s)")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Unsplash",
        subtitle="Combined Unsplash feed: blog, status, API changelog, and (with "
                 "an UNSPLASH_ACCESS_KEY) fresh wallpaper photos.",
        blog_url="https://unsplash.com/blog/",
        author="Unsplash",
        sources=SOURCES,
        extra_scrapers=[scrape_changelog, scrape_wallpapers],
        max_entries=150,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined Unsplash Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
