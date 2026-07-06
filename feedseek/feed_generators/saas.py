"""Combined Atom feed for assorted SaaS / web-product vendors.

Merges three low-volume vendor feeds that previously lived on their own into a
single Atom stream written to ``feeds/feed_saas.xml``:

    - HashiCorp / HCP   blog (native Atom) + HCP changelog (scraped)
    - Bitly             blog + press room + MCP changelog
    - Common Ninja      blog
    - Svelte            blog (native RSS)
    - Vercel            blog (native Atom)
    - Apify             blog (native RSS)
    - Zapier            blog (native RSS)

Each source's parser is reused verbatim from its original module
(``hcp_combined``, ``bitly``, ``commoninja_blog``), so there is exactly one
place that knows how to scrape each site. This generator only normalizes the
entries to a common shape, tags every entry with a per-vendor ``<category>``,
and keeps one rolling JSON cache (``cache/saas_posts.json``) so history
survives even when a source truncates its listing.

HCP entries carry rich HTML bodies (``content_html``) which are emitted as
``<content type="html">``; the other sources only have plain summaries.

Usage:
    python saas.py          # incremental: merge new entries into cache
    python saas.py --full   # ignore cache, rebuild from sources only
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

import bitly
import commoninja_blog as commoninja
import hcp_combined as hcp
import multi_rss
from utils import (
    deserialize_entries,
    get_feeds_dir,
    load_cache,
    merge_entries,
    sanitize_xml,
    save_cache,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "saas"
FEED_TITLE = "SaaS vendors"
FEED_SUBTITLE = (
    "Combined updates from HashiCorp / HCP (blog + changelog), "
    "Bitly (blog + press + MCP changelog), Common Ninja, "
    "Svelte, Vercel, Apify, Zapier, and Postman (blog + press)."
)
BLOG_URL = "https://www.hashicorp.com/blog"
MAX_ENTRIES = 300  # all vendors share one archive

_TAG_PREFIX_RE = re.compile(r"^\[[^\]]+\]\s*")


def _text(html: str) -> str:
    """Plain-text rendering of an HTML fragment, collapsed and trimmed."""
    if not html:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" ", strip=True)).strip()


# --------------------------------------------------------------------------- #
# Per-vendor adapters: reuse the original scrapers, normalize to one shape
#   {id, title, link, date, description, content_html?, source}
# --------------------------------------------------------------------------- #
def collect_hcp() -> list[dict]:
    """HashiCorp blog (native Atom) + HCP changelog (scraped). Both already
    return rich HTML in ``summary``; relabel the source and drop the redundant
    ``[Blog]`` / ``[Changelog]`` title prefix (we tag via <category>)."""
    out: list[dict] = []
    label = {"Blog": "HashiCorp Blog", "Changelog": "HCP Changelog"}
    try:
        raw = hcp.fetch_blog() + hcp.fetch_changelog()
    except Exception as exc:
        logger.warning("HCP sources failed: %s", exc)
        return out
    for e in raw:
        body = e.get("summary") or ""
        out.append({
            "id": e["id"],
            "title": sanitize_xml(_TAG_PREFIX_RE.sub("", e["title"])),
            "link": e["link"],
            "date": e.get("date"),
            "description": sanitize_xml(_text(body))[:500] or sanitize_xml(_TAG_PREFIX_RE.sub("", e["title"])),
            "content_html": body or None,
            "source": label.get(e.get("source"), e.get("source") or "HashiCorp"),
        })
    logger.info("HCP: %d entries", len(out))
    return out


def collect_bitly(known_links: set[str]) -> list[dict]:
    """Bitly blog + press + MCP changelog via bitly.scrape_all (already in the
    common {title, link, date, description, source} shape)."""
    out: list[dict] = []
    try:
        for e in bitly.scrape_all(known_links):
            out.append({
                "id": e["link"],
                "title": e["title"],
                "link": e["link"],
                "date": e.get("date"),
                "description": e.get("description") or e["title"],
                "content_html": None,
                "source": e.get("source") or "Bitly",
            })
    except Exception as exc:
        logger.warning("Bitly sources failed: %s", exc)
    logger.info("Bitly: %d entries", len(out))
    return out


# --------------------------------------------------------------------------- #
# Native RSS/Atom vendor feeds — parsed via the shared multi_rss helper.
# (label, url, cap): cap trims high-volume archives to the most recent items.
# --------------------------------------------------------------------------- #
NATIVE_FEEDS = [
    ("Svelte", "https://svelte.dev/blog/rss.xml", 40),
    ("Vercel", "https://vercel.com/atom", 40),
    ("Apify", "https://blog.apify.com/rss/", None),
    ("Zapier", "https://zapier.com/blog/feeds/latest/", None),
    ("Postman", "https://blog.postman.com/feed/", 40),
]


def collect_native_feeds(known_links: set[str]) -> list[dict]:
    """Pull each native RSS/Atom vendor feed via multi_rss.scrape_feed and
    normalize to the saas entry shape. Per-source failures are isolated."""
    out: list[dict] = []
    for label, url, cap in NATIVE_FEEDS:
        try:
            for e in multi_rss.scrape_feed(label, url, known_links, cap=cap):
                out.append({
                    "id": e["link"],
                    "title": e["title"],
                    "link": e["link"],
                    "date": e.get("date"),
                    "description": e.get("description") or e["title"],
                    "content_html": None,
                    "source": label,
                })
        except Exception as exc:
            logger.warning("%s feed failed: %s", label, exc)
    logger.info("Native feeds: %d entries", len(out))
    return out


import datetime as _dt  # noqa: E402

# Postman press page: no feed. Each release is an <h3> title linking to a
# BusinessWire URL whose /home/<YYYYMMDD...> segment carries the date.
POSTMAN_PRESS_URL = "https://www.postman.com/company/press-media/"

_BW_DATE_RE = re.compile(r"/home/(20\d{2})(\d{2})(\d{2})")


def collect_postman_press(known_links: set[str]) -> list[dict]:
    out: list[dict] = []
    try:
        html = multi_rss.get_html(POSTMAN_PRESS_URL)
    except Exception as exc:
        logger.warning("Postman press fetch failed: %s", exc)
        return out
    if not html:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    for h3 in soup.find_all("h3"):
        title = h3.get_text(" ", strip=True)
        if not title:
            continue
        a = h3.find("a", href=True) or h3.find_parent("a", href=True) or h3.find_next("a", href=True)
        if not a:
            continue
        link = a["href"].split("?")[0]
        if link in seen or link in known_links:
            continue
        m = _BW_DATE_RE.search(link)
        date = None
        if m:
            try:
                date = _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_dt.timezone.utc)
            except ValueError:
                date = None
        seen.add(link)
        out.append({
            "id": link,
            "title": sanitize_xml(title[:200]),
            "link": link,
            "date": date,
            "description": sanitize_xml(title[:200]),
            "content_html": None,
            "source": "Postman Press",
        })
    logger.info("Postman Press: %d entries", len(out))
    return out


def collect_commoninja() -> list[dict]:
    """Common Ninja blog: fetch the listing and reuse its card parser."""
    out: list[dict] = []
    try:
        html = commoninja.fetch_listing()
        if html:
            for e in commoninja.parse_items(html):
                out.append({
                    "id": e["link"],
                    "title": e["title"],
                    "link": e["link"],
                    "date": e.get("date") or stable_fallback_date(e["link"]),
                    "description": e.get("description") or e["title"],
                    "content_html": None,
                    "source": "Common Ninja",
                })
    except Exception as exc:
        logger.warning("Common Ninja source failed: %s", exc)
    logger.info("Common Ninja: %d entries", len(out))
    return out


# --------------------------------------------------------------------------- #
# Feed
# --------------------------------------------------------------------------- #
def generate_atom_feed(entries: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.id(f"{BLOG_URL}#{FEED_NAME}")
    fg.title(FEED_TITLE)
    fg.subtitle(FEED_SUBTITLE)
    setup_feed_links(fg, BLOG_URL, FEED_NAME)
    fg.language("en")
    fg.author({"name": "various"})
    fg.updated(datetime.now(timezone.utc))
    fg.generator("trvny-feeds saas.py")

    # entries are ascending (oldest first); feedgen reverses on write.
    for e in entries:
        fe = fg.add_entry()
        fe.id(e["id"])
        fe.title(e["title"])
        fe.link(href=e["link"], rel="alternate")
        if e.get("content_html"):
            fe.content(e["content_html"], type="html")
        else:
            fe.description(e.get("description") or e["title"])
        if e.get("source"):
            fe.category(term=e["source"], label=e["source"])
        if e.get("date"):
            fe.published(e["date"])
            fe.updated(e["date"])
    logger.info("Generated Atom feed with %d entries", len(entries))
    return fg


def main(full: bool = False) -> bool:
    cached = (
        []
        if full
        else deserialize_entries(load_cache(FEED_NAME).get("entries", []), date_field="date")
    )
    known_links = {e.get("link") for e in cached}

    new_entries = (
        collect_hcp()
        + collect_bitly(known_links)
        + collect_commoninja()
        + collect_native_feeds(known_links)
        + collect_postman_press(known_links)
    )
    if not new_entries and not cached:
        logger.error("No entries from any source; preserving the last good feed")
        return False

    merged = merge_entries(new_entries, cached, id_field="id", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]  # ascending, so the tail is newest

    save_cache(FEED_NAME, merged)
    out = get_feeds_dir() / f"feed_{FEED_NAME}.xml"
    generate_atom_feed(merged).atom_file(str(out), pretty=True)
    logger.info("Wrote %s", out)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined SaaS-vendors Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
