"""Shared pipeline for combined multi-source Atom feeds.

Several generators in this repo do the same thing: pull a handful of native
RSS/Atom feeds (and sometimes a custom scraper), merge them into one Atom feed
with per-source ``<category>`` labels, dedupe across sources, and accumulate
history in a JSON cache. This module is that pipeline; per-feed scripts (e.g.
``cheezburger.py``, ``euronews.py``, ``pap.py``, ``microsoft.py``) just declare
their sources and call :func:`run`.

Conventions preserved from the standalone generators:
  * curl_cffi Chrome impersonation with a plain-requests fallback,
  * per-source error isolation (one failing source never sinks the run),
  * empty-feed guard (skip writing when nothing was collected),
  * link-level dedupe via the cache, then cross-source dedupe by normalized
    URL/title (query and fragment are PRESERVED in the URL key, since some
    sources distinguish entries only by fragment),
  * full history kept in ``cache/<n>_posts.json``; only the rendered feed
    is capped.
"""

import pytz
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import (
    add_entry_media,
    feed_item_image,
    dedupe_entries,
    deserialize_entries,
    get_feeds_dir,
    guess_mime_type,
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

DESC_LIMIT = 500
DEFAULT_MAX_ENTRIES = 200


def get_html(url):
    """Fetch a URL impersonating Chrome, falling back to plain requests if
    curl_cffi is unavailable. Returns text or None."""
    try:
        from curl_cffi import requests as creq

        resp = creq.get(url, impersonate="chrome", timeout=30)
    except ImportError:
        logger.warning(f"curl_cffi unavailable; using plain requests for {url}")
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"},
                timeout=30,
            )
        except Exception as e:
            logger.warning(f"Fetch failed for {url}: {e}")
            return None
    except Exception as e:
        logger.warning(f"Fetch failed for {url}: {e}")
        return None
    if resp.status_code != 200:
        logger.warning(f"Fetch for {url} returned HTTP {resp.status_code}")
        return None
    return resp.text


def parse_date(date_str):
    """Parse a date string into a UTC datetime, or None on failure."""
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return None


def _item_link(item):
    """Link from an RSS <item> (text) or Atom <entry> (<link href>)."""
    for link_el in item.find_all("link"):
        href = (link_el.get("href") or "").strip()
        if href and link_el.get("rel") in (None, "alternate"):
            return href
        text = link_el.get_text(strip=True)
        if text:
            return text
    return ""


def _item_date(item):
    for tag in ("pubDate", "published", "updated", "dc:date"):
        el = item.find(tag)
        if el and el.get_text(strip=True):
            return parse_date(el.get_text(strip=True))
    return None


def _item_image(item):
    """Delegates to utils.feed_item_image (single source of truth); kept as a
    thin local wrapper so existing call sites stay unchanged."""
    return feed_item_image(item)


def _item_description(item, keep_html=False):
    for tag in ("description", "summary", "content", "content:encoded"):
        el = item.find(tag)
        if el is None:
            continue
        raw = el.get_text()
        if not raw.strip():
            continue
        if keep_html:
            return sanitize_xml(raw.strip())[:4000]
        text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
        if text:
            return sanitize_xml(text)[:DESC_LIMIT]
    return ""


def scrape_feed(label, feed_url, known_links, cap=None, keep_html=False):
    """Parse one native RSS or Atom feed into entry dicts."""
    entries = []
    xml = get_html(feed_url)
    if xml is None:
        return entries
    try:
        soup = BeautifulSoup(xml, "xml")
    except Exception as e:
        logger.warning(f"Could not parse {feed_url}: {e}")
        return entries

    items = soup.find_all("item") or soup.find_all("entry")
    if not items:
        logger.warning(f"  [{label}] feed has no items — format may have changed")
        return entries
    if cap:
        items = items[:cap]

    for item in items:
        try:
            link = _item_link(item)
            if not link or link in known_links:
                continue
            title_el = item.find("title")
            title = sanitize_xml(title_el.get_text(strip=True)) if title_el else label
            entries.append({
                "title": title,
                "link": link,
                "date": _item_date(item),
                "description": _item_description(item, keep_html=keep_html) or title,
                "source": label,
                "image": _item_image(item),
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping malformed item: {e}")
    return entries


def generate_atom_feed(articles, *, feed_name, feed_id, title, subtitle, blog_url, author, icon=None):
    fg = FeedGenerator()
    fg.id(feed_id)
    fg.title(title)
    fg.subtitle(subtitle)
    setup_feed_links(fg, blog_url, feed_name, icon=icon)
    fg.language("en")
    fg.author({"name": author})
    setup_feed_extensions(fg)

    for article in articles:
        fe = fg.add_entry()
        fe.id(make_entry_id(feed_name, article["link"]))
        fe.title(article["title"])
        fe.link(href=article["link"])
        source = article.get("source")
        if source:
            fe.category(term=source, label=source)
            set_entry_source(fe, source)
        fe.description(article.get("description") or article["title"])
        add_entry_media(fe, article.get("image"))
        if article.get("date"):
            fe.published(article["date"])
            fe.updated(article["date"])

    logger.info("Generated Atom feed")
    return fg


def run(*, feed_name, title, subtitle, blog_url, author, sources=(),
        extra_scrapers=(), keep_html=False, max_entries=DEFAULT_MAX_ENTRIES,
        language="en", full=False, cache_filter=None, cache_transform=None,
        icon=None):
    """Full pipeline: scrape ``sources`` (label, url, cap) and any
    ``extra_scrapers`` (callables taking ``known_links``), merge with the
    cache, dedupe, and write ``feeds/feed_<feed_name>.xml``. Returns bool.

    ``cache_filter`` is an optional ``entry -> bool`` predicate applied to
    cached entries on load; entries returning False are dropped (and re-added
    fresh if still live). Use it to evict stale/malformed cached entries.

    ``cache_transform`` is an optional ``entry -> entry`` map applied to each
    cached entry on load, for repairing fields derived post-fetch (e.g. a date
    parsed from the title) that would otherwise stay frozen at whatever value
    was first cached."""
    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cache = load_cache(feed_name)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")
        if cache_filter is not None:
            before = len(cached)
            cached = [e for e in cached if cache_filter(e)]
            if len(cached) != before:
                logger.info(f"cache_filter dropped {before - len(cached)} stale cached entries")
        if cache_transform is not None:
            cached = [cache_transform(e) for e in cached]

    known_links = {e["link"] for e in cached}
    new_articles = []
    for label, url, cap in sources:
        logger.info(f"Scraping {label} ...")
        new_articles += scrape_feed(label, url, known_links, cap=cap, keep_html=keep_html)
    for scraper in extra_scrapers:
        try:
            new_articles += scraper(known_links)
        except Exception as e:
            logger.warning(f"Scraper {getattr(scraper, '__name__', scraper)} failed: {e}")

    if not new_articles and not cached:
        logger.warning("No articles collected — skipping write to avoid an empty feed")
        return False

    merged = merge_entries(new_articles, cached, id_field="link", date_field="date")
    merged = dedupe_entries(merged)
    merged = sort_posts_for_feed(merged, date_field="date")

    # Keep full (deduplicated) history in the cache; cap only the rendered feed.
    save_cache(feed_name, merged)

    feed_items = merged[-max_entries:] if len(merged) > max_entries else merged
    fg = generate_atom_feed(
        feed_items, feed_name=feed_name, feed_id=blog_url, title=title,
        subtitle=subtitle, blog_url=blog_url, author=author, icon=icon,
    )
    fg.language(language)
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return True
