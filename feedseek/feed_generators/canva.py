"""Canva combined feed generator.

Canva has no native RSS/Atom feed. Both source pages used to be reachable via
a ``curl_cffi`` Chrome-impersonated fetch of their ``__NEXT_DATA__`` blob, but
canva.com now serves an active Cloudflare interactive challenge
(``cf-mitigated: challenge``) to that fetch too — a JS challenge, not just a
TLS-fingerprint check, so no static HTTP client can pass it. Both surfaces are
well indexed by Google News, so this generator uses the same proxy workaround
as ``reuters.py``/``govpl.py`` instead.

This builds **one combined feed** from Canva's two editorial surfaces:

* ``/newsroom/`` — company news and announcements.
* ``/learn/`` — the design-tips/tutorials hub.

Tradeoff of the proxy approach: links point at Google News' redirect URLs
rather than canva.com directly, and per-article images/categories are gone
(Google News RSS rarely carries them). Entries are deduplicated by URL across
both surfaces. The cache (``cache/canva_posts.json``) accumulates history and
dedupes across runs.

Writes an **Atom** feed to ``feeds/feed_canva.xml``.
"""

import argparse
import sys
import time

import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import (
    add_entry_media,
    deserialize_entries,
    fetch_page,
    get_feeds_dir,
    load_cache,
    make_entry_id,
    merge_entries,
    sanitize_xml,
    save_cache,
    set_entry_source,
    setup_feed_extensions,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "canva"
BLOG_URL = "https://www.canva.com/newsroom/news/"
MAX_ENTRIES = 200

# Google News RSS proxies, scoped per surface via `site:`. A few query variants
# per surface, tried in order, so a transient block or empty window on one
# doesn't sink that surface's half of the run.
NEWSROOM_SOURCE_URLS = [
    "https://news.google.com/rss/search?q=when:14d+site:canva.com/newsroom&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=site:canva.com/newsroom&hl=en-US&gl=US&ceid=US:en",
]
LEARN_SOURCE_URLS = [
    "https://news.google.com/rss/search?q=when:14d+site:canva.com/learn&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=site:canva.com/learn&hl=en-US&gl=US&ceid=US:en",
]

# Browser-like headers — Google News is more permissive with these than a bare
# request, which matters on shared/datacenter IPs such as CI runners.
FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_source(source_urls, retries: int = 3, backoff: float = 2.0):
    """Fetch the first URL in *source_urls* that returns parseable items."""
    for url in source_urls:
        for attempt in range(1, retries + 1):
            try:
                xml = fetch_page(url, headers=FETCH_HEADERS)
                if "<item>" in xml:
                    logger.info(f"Fetched source: {url}")
                    return xml
                logger.warning(f"No <item> elements from {url} (attempt {attempt})")
            except Exception as e:
                logger.warning(f"Fetch failed for {url} (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(backoff * attempt)
    return None


def parse_date(date_str):
    """Parse a Google News RFC-822 pubDate into a UTC datetime."""
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return None


def parse_proxy_feed(xml_content, label: str):
    """Parse a Google News RSS proxy response into a list of entry dicts.

    *label* ("News" or "Learn") tags which Canva surface these came from,
    since the proxy itself doesn't carry that distinction.
    """
    soup = BeautifulSoup(xml_content, "xml")
    entries = []
    seen_links = set()

    for item in soup.find_all("item"):
        try:
            title_el = item.find("title")
            link_el = item.find("link")
            if not title_el or not link_el:
                continue

            title = sanitize_xml(title_el.get_text(strip=True))
            link = link_el.get_text(strip=True)
            if not title or not link or link in seen_links:
                continue
            seen_links.add(link)

            # Google News appends " - Canva" (or the odd co-published outlet)
            # to titles; strip the trailing source suffix for a clean headline.
            source_el = item.find("source")
            source_name = source_el.get_text(strip=True) if source_el else "Canva"
            if source_name and title.endswith(f" - {source_name}"):
                title = title[: -len(f" - {source_name}")].strip()

            pub_el = item.find("pubDate")
            date_obj = parse_date(pub_el.get_text(strip=True)) if pub_el else None

            desc_el = item.find("description")
            description = sanitize_xml(desc_el.get_text(strip=True)) if desc_el else title
            description = f"{description}\n\n{label}" if description else label

            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date_obj,
                    "description": description,
                    "source": source_name or "Canva",
                    "image": None,  # Google News RSS rarely carries one
                }
            )
        except Exception as e:  # never let one bad item kill the run
            logger.warning(f"Skipping malformed {label} item: {e}")
            continue

    logger.info(f"Parsed {len(entries)} {label} entries")
    return entries


def collect_entries():
    """Fetch and parse both surfaces via the Google News proxy, deduped by link."""
    raw = []

    newsroom_xml = fetch_source(NEWSROOM_SOURCE_URLS)
    if newsroom_xml:
        raw.extend(parse_proxy_feed(newsroom_xml, "News"))
    else:
        logger.warning("Newsroom source unavailable — continuing with Learn only")

    learn_xml = fetch_source(LEARN_SOURCE_URLS)
    if learn_xml:
        raw.extend(parse_proxy_feed(learn_xml, "Learn"))
    else:
        logger.warning("Learn source unavailable — continuing with Newsroom only")

    entries = []
    seen = set()
    for e in raw:
        if e["link"] in seen:
            continue
        seen.add(e["link"])
        entries.append(e)

    logger.info(f"Collected {len(entries)} combined entries")
    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    fg = FeedGenerator()
    fg.id(f"https://www.canva.com/#{feed_name}")
    fg.title("Canva")
    fg.subtitle("Canva newsroom announcements and Learn design guides, aggregated via Google News")
    setup_feed_links(fg, BLOG_URL, feed_name)
    setup_feed_extensions(fg)
    fg.language("en")
    fg.author({"name": "Canva"})

    for e in entries:
        fe = fg.add_entry()
        fe.id(make_entry_id(feed_name, e["link"]))
        fe.title(e["title"])
        fe.link(href=e["link"])
        add_entry_media(fe, e.get("image"))
        fe.description(e["description"])
        set_entry_source(fe, e.get("source"))
        if e.get("date"):
            fe.published(e["date"])
            fe.updated(e["date"])

    logger.info("Generated Atom feed")
    return fg


def save_atom_feed(fg, feed_name=FEED_NAME):
    out = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(out), pretty=True)
    logger.info(f"Saved Atom feed to {out}")
    return out


def main(full=False) -> bool:
    new_entries = collect_entries()
    if not new_entries:
        logger.warning("No entries collected — skipping write to avoid an empty feed")
        return False

    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cached = deserialize_entries(load_cache(FEED_NAME).get("entries", []), date_field="date")

    merged = merge_entries(new_entries, cached, id_field="link", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]

    save_cache(FEED_NAME, merged)
    save_atom_feed(generate_atom_feed(merged))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined Canva Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
