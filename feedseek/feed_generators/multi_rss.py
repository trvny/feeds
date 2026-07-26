"""Shared pipeline for combined multi-source Atom feeds.

Several generators in this repo do the same thing: pull a handful of native
RSS/Atom feeds (and sometimes a custom scraper), merge them into one Atom feed
with per-source category labels, dedupe across sources, and accumulate history
in a JSON cache. This module is that pipeline; per-feed scripts just declare
their sources and call :func:`run`.
"""

from __future__ import annotations

import time

import pytz
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import (
    add_entry_media,
    dedupe_entries,
    deserialize_entries,
    feed_item_image,
    load_cache,
    make_entry_id,
    merge_entries,
    sanitize_xml,
    save_atom_feed,
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
# Fallback quota for sources a per-source cap mapping does not name.
DEFAULT_SOURCE_QUOTA = 30


PLAIN_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}


def _fetch_plain(url):
    """Plain requests GET with a browser User-Agent."""
    try:
        return requests.get(url, headers=PLAIN_HEADERS, timeout=30)
    except Exception as exc:
        logger.warning("Fetch failed for %s: %s", url, exc)
        return None


def _fetch_impersonated(url):
    """curl_cffi Chrome-impersonated GET, or None if unavailable/failed."""
    try:
        from curl_cffi import requests as creq
    except ImportError:
        logger.warning("curl_cffi unavailable; using plain requests for %s", url)
        return None
    try:
        return creq.get(url, impersonate="chrome", timeout=30)
    except Exception as exc:
        logger.warning("Impersonated fetch failed for %s: %s", url, exc)
        return None


def get_html(url, *, retry_delay=4):
    """Fetch a URL, trying both HTTP clients before giving up.

    Some origins only answer one of the two: Cloudflare-style TLS
    fingerprinting rejects plain requests, while a few WAFs (notably
    news.samsung.com/global) reject the curl_cffi Chrome fingerprint and serve
    an ordinary browser-UA request fine. So a non-200 from the impersonated
    request is retried plainly.

    Those same WAFs also rate-limit bursts per IP, which shows up as a 403 on a
    URL that answered a moment earlier, so one full round is retried after a
    short pause before the fetch is called a failure.
    """
    last_status = None
    for attempt in (0, 1):
        if attempt:
            time.sleep(retry_delay)
        resp = _fetch_impersonated(url)
        if resp is not None:
            if resp.status_code == 200:
                return resp.text
            last_status = resp.status_code
            logger.info("Retrying %s with plain requests (HTTP %s)", url, resp.status_code)
        fallback = _fetch_plain(url)
        if fallback is not None:
            if fallback.status_code == 200:
                return fallback.text
            last_status = fallback.status_code

    logger.warning("Fetch for %s failed (last HTTP %s)", url, last_status)
    return None


def parse_date(date_str):
    """Parse a date string into a UTC datetime, or None on failure."""
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError) as exc:
        logger.warning("Could not parse date %r: %s", date_str, exc)
        return None


def _item_link(item):
    """Link from an RSS item (text) or Atom entry (link href)."""
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
    """Parse one native RSS or Atom feed into entry dictionaries."""
    entries = []
    xml = get_html(feed_url)
    if xml is None:
        return entries
    try:
        soup = BeautifulSoup(xml, "xml")
    except Exception as exc:
        logger.warning("Could not parse %s: %s", feed_url, exc)
        return entries

    items = soup.find_all("item") or soup.find_all("entry")
    if not items:
        logger.warning("  [%s] feed has no items; format may have changed", label)
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
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": _item_date(item),
                    "description": _item_description(item, keep_html=keep_html) or title,
                    "source": label,
                    "image": _item_image(item),
                }
            )
            logger.info("  [%s] %s", label, title)
        except Exception as exc:
            logger.warning("  [%s] skipping malformed item: %s", label, exc)
    return entries


def source_quota(per_source_cap, source):
    """Resolve one source's quota from an int or a per-source mapping.

    A plain int applies to every source. A mapping gives named sources their
    own quota and falls back to its ``""`` key (or ``DEFAULT_SOURCE_QUOTA``) for
    the rest, which is how a content farm can be held to a handful of slots
    while editorial sources keep a useful share of the same feed.
    """
    if isinstance(per_source_cap, dict):
        return per_source_cap.get(source, per_source_cap.get("", DEFAULT_SOURCE_QUOTA))
    return per_source_cap


def apply_per_source_cap(entries, per_source_cap, limit):
    """Trim to ``limit`` entries while guaranteeing each source a fair share.

    ``entries`` is ascending (oldest first). Newest-first, keep at most
    ``per_source_cap`` entries per source; anything over quota goes to an
    overflow pool that backfills the remaining slots by recency. Without this,
    a few high-churn sources can evict every slow-publishing source from a
    combined feed.

    ``per_source_cap`` is either an int (same quota for everyone) or a
    ``{source: quota}`` mapping with a ``""`` default — see :func:`source_quota`.
    """
    kept, overflow, counts = [], [], {}
    for entry in reversed(entries):
        source = entry.get("source") or ""
        counts[source] = counts.get(source, 0) + 1
        quota = source_quota(per_source_cap, source)
        (kept if counts[source] <= quota else overflow).append(entry)

    selected = kept[:limit]
    if len(selected) < limit:
        selected += overflow[: limit - len(selected)]
    return sort_posts_for_feed(selected, date_field="date")


def generate_atom_feed(
    articles,
    *,
    feed_name,
    feed_id,
    title,
    subtitle,
    blog_url,
    author,
    icon=None,
):
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


def run(
    *,
    feed_name,
    title,
    subtitle,
    blog_url,
    author,
    sources=(),
    extra_scrapers=(),
    keep_html=False,
    max_entries=DEFAULT_MAX_ENTRIES,
    per_source_cap=None,
    language="en",
    full=False,
    cache_filter=None,
    cache_transform=None,
    icon=None,
):
    """Scrape, merge, dedupe, cache, and write XML plus JSON Feed sidecar."""
    if full:
        logger.info("Full reset requested; ignoring existing cache")
        cached = []
    else:
        cache = load_cache(feed_name)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")
        if cache_filter is not None:
            before = len(cached)
            cached = [entry for entry in cached if cache_filter(entry)]
            if len(cached) != before:
                logger.info("cache_filter dropped %d cached entries", before - len(cached))
        if cache_transform is not None:
            cached = [cache_transform(entry) for entry in cached]

    known_links = {entry["link"] for entry in cached}
    new_articles = []
    for label, url, cap in sources:
        logger.info("Scraping %s ...", label)
        new_articles += scrape_feed(label, url, known_links, cap=cap, keep_html=keep_html)
    for scraper in extra_scrapers:
        try:
            new_articles += scraper(known_links)
        except Exception as exc:
            logger.warning("Scraper %s failed: %s", getattr(scraper, "__name__", scraper), exc)

    if not new_articles and not cached:
        logger.warning("No articles collected; skipping write to avoid an empty feed")
        return False

    merged = merge_entries(new_articles, cached, id_field="link", date_field="date")
    merged = dedupe_entries(merged)
    merged = sort_posts_for_feed(merged, date_field="date")
    save_cache(feed_name, merged)

    if per_source_cap:
        feed_items = apply_per_source_cap(merged, per_source_cap, max_entries)
    else:
        feed_items = merged[-max_entries:] if len(merged) > max_entries else merged
    fg = generate_atom_feed(
        feed_items,
        feed_name=feed_name,
        feed_id=blog_url,
        title=title,
        subtitle=subtitle,
        blog_url=blog_url,
        author=author,
        icon=icon,
    )
    fg.language(language)
    save_atom_feed(fg, feed_name)
    return True
