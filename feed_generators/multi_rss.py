"""Shared pipeline for combined multi-source Atom feeds.

Several generators in this repo do the same thing: pull a handful of native
RSS/Atom feeds (and sometimes a custom scraper), merge them into one Atom feed
with per-source category labels, dedupe across sources, and accumulate history
in a JSON cache. This module is that pipeline; per-feed scripts just declare
their sources and call :func:`run`.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytz
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from enrich import enrich_entries
from entry_identity import entry_id_for
from entry_refresh import SYNTHETIC_TITLE_FIELD, merge_refreshed_entries
from feedgen.feed import FeedGenerator
from google_news import entry_url
from utils import (
    add_entry_media,
    allocate_fair_share,
    dedupe_entries,
    deserialize_entries,
    feed_item_image,
    load_cache,
    merge_entries,
    normalize_link,
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
            logger.info(
                "Retrying %s with plain requests (HTTP %s)", url, resp.status_code
            )
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


def _item_date(item, cached_date=None):
    # A real publication timestamp may legitimately be corrected upstream.
    for tag in ("pubDate", "published", "dc:date"):
        el = item.find(tag)
        if el and el.get_text(strip=True):
            return parse_date(el.get_text(strip=True))

    # Atom's <updated> often changes when metadata is edited. Once an item is
    # cached, don't let that revision timestamp reorder it as if it were new.
    if cached_date is not None:
        return cached_date
    el = item.find("updated")
    if el and el.get_text(strip=True):
        return parse_date(el.get_text(strip=True))
    return None


def _item_image(item):
    return feed_item_image(item)


def _title_from_slug(link):
    """Readable last-resort title derived from a URL slug."""
    slug = (link or "").rstrip("/").split("/")[-1].split("?")[0]
    return slug.replace("-", " ").replace("_", " ").strip().capitalize()


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


def scrape_feed(
    label,
    feed_url,
    known_links,
    cap=None,
    keep_html=False,
    cached_dates=None,
):
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

    cached_dates = cached_dates or {}
    for item in items:
        try:
            link = _item_link(item)
            if not link or link in known_links:
                continue
            # Some feeds (Europol, GitHub Trending) carry no per-item date. New
            # items are stamped on first sight; rediscovered cached items keep
            # that first-seen value instead of moving to "now" every refresh.
            cached_date = cached_dates.get(normalize_link(link))
            date = (
                _item_date(item, cached_date)
                or cached_date
                or datetime.now(timezone.utc)
            )
            title_el = item.find("title")
            title = sanitize_xml(title_el.get_text(strip=True)) if title_el else ""
            # Some feeds ship an empty <title/> (timeanddate's calendar RSS
            # does). feedgen refuses to write a titleless entry, and falling
            # back to the source label would give every such item the same
            # title, which dedupe_entries then collapses into one. Mark the
            # synthesized title so refresh never overwrites a richer cached one.
            synthetic_title = not bool(title)
            title = title or _title_from_slug(link) or label
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date,
                    "description": _item_description(item, keep_html=keep_html)
                    or title,
                    "source": label,
                    "image": _item_image(item),
                    SYNTHETIC_TITLE_FIELD: synthetic_title,
                }
            )
            logger.info("  [%s] %s", label, title)
        except Exception as exc:
            logger.warning("  [%s] skipping malformed item: %s", label, exc)
    return entries


def apply_per_source_cap(entries, per_source_cap, limit):
    """Trim to ``limit`` entries while guaranteeing each source a fair share.

    Kept as the public name because generators import it directly (skillsllm.py);
    the algorithm itself is :func:`utils.allocate_fair_share`, shared with the
    cache trimmer so the published feed and the dedup state stay consistent.
    """
    return allocate_fair_share(entries, limit, per_source_cap=per_source_cap)


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
    source_tags=None,
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
        fe.id(entry_id_for(feed_name, article))
        fe.title(article["title"])
        fe.link(href=entry_url(article))
        source = article.get("source")
        if source:
            fe.category(term=source, label=source)
            set_entry_source(fe, source)
            tag = (source_tags or {}).get(source)
            if tag:
                fe.category(term=tag, label=tag)
        fe.description(article.get("description") or article["title"])
        add_entry_media(
            fe,
            article.get("image"),
            width=article.get("image_width"),
            height=article.get("image_height"),
        )
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
    refresh_sources=None,
    extra_scrapers=(),
    keep_html=False,
    max_entries=DEFAULT_MAX_ENTRIES,
    per_source_cap=None,
    language="en",
    full=False,
    cache_filter=None,
    cache_transform=None,
    cache_state=None,
    dedupe_title_field="title",
    icon=None,
    source_tags=None,
    image_backfill=True,
):
    """Scrape, merge, dedupe, cache, and write XML plus JSON Feed sidecar.

    Native RSS/Atom sources refresh cached metadata by default because their
    listing feed is already fetched on every run. Pass ``refresh_sources=()``
    to retain add-only behavior, or a label collection to refresh only those
    native sources. Extra/custom scrapers remain cache-gated and add-only. Pass
    a mutable ``cache_state`` dict to round-trip non-entry top-level bookkeeping,
    such as resumable pagination cursors. Set ``dedupe_title_field=None`` for
    sources whose stable URL is the only identity.
    """
    cache = {}
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
                logger.info(
                    "cache_filter dropped %d cached entries", before - len(cached)
                )
        if cache_transform is not None:
            cached = [cache_transform(entry) for entry in cached]

    if cache_state is not None:
        cache_state.clear()
        if not full:
            cache_state.update(
                {
                    key: value
                    for key, value in cache.items()
                    if key not in {"entries", "last_updated"}
                }
            )

    sources = tuple(sources)
    if refresh_sources is None:
        refresh_sources = {label for label, _, _ in sources}
    else:
        refresh_sources = set(refresh_sources)

    known_links = {entry["link"] for entry in cached}
    cached_dates = {
        normalize_link(entry["link"]): entry.get("date")
        for entry in cached
        if entry.get("link") and entry.get("date") is not None
    }
    refresh_articles = []
    add_only_articles = []
    for label, url, cap in sources:
        logger.info("Scraping %s ...", label)
        source_known_links = known_links
        refreshing = label in refresh_sources
        if refreshing:
            source_known_links = known_links - {
                entry["link"] for entry in cached if entry.get("source") == label
            }
        scraped = scrape_feed(
            label,
            url,
            source_known_links,
            cap=cap,
            keep_html=keep_html,
            cached_dates=cached_dates,
        )
        if refreshing:
            refresh_articles += scraped
        else:
            add_only_articles += scraped

    for scraper in extra_scrapers:
        try:
            add_only_articles += scraper(known_links)
        except Exception as exc:
            logger.warning(
                "Scraper %s failed: %s", getattr(scraper, "__name__", scraper), exc
            )

    if not refresh_articles and not add_only_articles and not cached:
        logger.warning("No articles collected; skipping write to avoid an empty feed")
        return False

    merged = merge_refreshed_entries(
        refresh_articles, cached, id_field="link", date_field="date"
    )
    merged = merge_entries(
        add_only_articles, merged, id_field="link", date_field="date"
    )
    for entry in merged:
        entry.pop(SYNTHETIC_TITLE_FIELD, None)
    merged = dedupe_entries(merged, title_field=dedupe_title_field)
    merged = sort_posts_for_feed(merged, date_field="date")

    # Unconditional: a feed without an explicit per_source_cap used to fall back
    # to a plain recency slice, which is precisely where the starvation was worst
    # (steam published 7 of the 20 sources in its cache; cheezburger 4 of 6, with
    # two sources at zero). Round-robin needs no tuning to be fair, so there is
    # no reason to make it opt-in — per_source_cap now only adds a ceiling.
    feed_items = apply_per_source_cap(merged, per_source_cap, max_entries)

    # Resolves wrapper links and fills in missing pictures. feed_items holds the
    # same dicts as merged, so what is learned here is kept by the cache below
    # and no URL is ever looked up twice.
    enrich_entries(feed_items, images=image_backfill)
    save_cache(feed_name, merged, extra=cache_state)

    fg = generate_atom_feed(
        feed_items,
        feed_name=feed_name,
        feed_id=blog_url,
        title=title,
        subtitle=subtitle,
        blog_url=blog_url,
        author=author,
        icon=icon,
        source_tags=source_tags,
    )
    fg.language(language)
    save_atom_feed(fg, feed_name)
    return True
