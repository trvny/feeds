"""Combined Wykop feed built from the three native RSS views.

Wykop exposes the front page, most-commented links, and the upcoming queue as
separate RSS feeds. The same finding can appear in all three with slightly
different metadata, so this generator canonicalizes every Wykop permalink to
its numeric finding ID and keeps the richest representation.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from multi_rss import get_html, parse_date
from utils import (
    add_entry_media,
    deserialize_entries,
    favicon_proxy,
    feed_item_image,
    load_cache,
    make_entry_id,
    normalize_link,
    sanitize_xml,
    save_atom_feed,
    save_cache,
    set_entry_source,
    setup_feed_extensions,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "wykop"
BLOG_URL = "https://wykop.pl/"
SUBTITLE = "Znaleziska z Wykopaliska"
MAX_ENTRIES = 200
SOURCE_ORDER = ("Wykopane", "Komentowane", "Wykopalisko")
FEED_SOURCES = [
    ("Wykopane", "https://wykop.pl/rss", 60),
    ("Komentowane", "https://wykop.pl/rss/comments", 60),
    ("Wykopalisko", "https://wykop.pl/rss/upcoming", 60),
]

_WYKOP_ID_RE = re.compile(
    r"(?:https?://(?:www\.)?wykop\.pl)?/(?:link|znalezisko)/(\d+)(?:[/?#]|$)",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def _tag_text(item, *local_names):
    wanted = {name.lower() for name in local_names}
    for tag in item.find_all(True):
        local = tag.name.rsplit(":", 1)[-1].lower()
        if local in wanted and tag.get_text(strip=True):
            return tag.get_text(" ", strip=True)
    return ""


def _description_html(item):
    for local_name in ("encoded", "description", "summary", "content"):
        for tag in item.find_all(True):
            local = tag.name.rsplit(":", 1)[-1].lower()
            if local != local_name or tag.get("url"):
                continue
            raw = tag.decode_contents() or tag.get_text()
            if raw and raw.strip():
                return raw
    return ""


def clean_html(raw):
    """Collapse feed HTML to readable, XML-safe plain text."""
    if not raw:
        return ""
    soup = BeautifulSoup(html.unescape(raw), "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = _WHITESPACE_RE.sub(" ", soup.get_text(" ", strip=True)).strip()
    return sanitize_xml(text)[:1500]


def _normalize_url(url):
    if not url:
        return ""
    url = html.unescape(url.strip())
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = urljoin(BLOG_URL, url)
    return normalize_link(url)


def _url_candidates(item):
    candidates = []
    for tag in item.find_all(True):
        local = tag.name.rsplit(":", 1)[-1].lower()
        if local not in {"link", "guid", "comments"}:
            continue
        for attr in ("href", "url"):
            if tag.get(attr):
                candidates.append(tag[attr].strip())
        text = tag.get_text(strip=True)
        if text:
            candidates.append(text)
    return candidates


def finding_id(item):
    """Return Wykop's numeric finding ID from any native RSS permalink."""
    candidates = _url_candidates(item)
    candidates.append(str(item))
    for candidate in candidates:
        match = _WYKOP_ID_RE.search(candidate)
        if match:
            return match.group(1)

    guid = _tag_text(item, "guid")
    if guid.isdigit():
        return guid
    return ""


def canonical_item_link(item):
    item_id = finding_id(item)
    if item_id:
        return f"https://wykop.pl/link/{item_id}"
    for candidate in _url_candidates(item):
        normalized = _normalize_url(candidate)
        if normalized:
            return normalized
    return ""


def _external_link(item):
    for candidate in _url_candidates(item):
        normalized = _normalize_url(candidate)
        if not normalized:
            continue
        host = (urlsplit(normalized).hostname or "").lower()
        if host not in {"wykop.pl", "www.wykop.pl"}:
            return normalized
    return ""


def _image_from_html(raw):
    if not raw:
        return ""
    soup = BeautifulSoup(html.unescape(raw), "html.parser")
    image = soup.find("img")
    if not image:
        return ""
    candidate = image.get("src") or image.get("data-src") or ""
    normalized = _normalize_url(candidate)
    return "" if normalized.startswith("data:") else normalized


def _item_categories(item):
    categories = []
    for tag in item.find_all(True):
        if tag.name.rsplit(":", 1)[-1].lower() != "category":
            continue
        value = sanitize_xml(tag.get_text(" ", strip=True))
        if value and value not in categories:
            categories.append(value)
    return categories


def _publisher(item, external_link):
    source = sanitize_xml(_tag_text(item, "source", "creator", "author"))
    if source:
        return source
    host = (urlsplit(external_link).hostname or "").lower()
    return re.sub(r"^www\.", "", host) or "Wykop"


def parse_item(item, source_label):
    link = canonical_item_link(item)
    if not link:
        return None

    raw_description = _description_html(item)
    title = sanitize_xml(_tag_text(item, "title"))[:300]
    description = clean_html(raw_description)
    title = title or description[:200] or link
    description = description or title

    external_link = _external_link(item)
    image = _normalize_url(feed_item_image(item) or "") or _image_from_html(
        raw_description
    )
    date = parse_date(
        _tag_text(item, "pubdate", "published", "updated", "date")
    ) or stable_fallback_date(link)

    return {
        "title": title,
        "link": link,
        "date": date,
        "description": description,
        "source": _publisher(item, external_link),
        "image": image or None,
        "external_link": external_link or None,
        "feed_sources": [source_label],
        "categories": _item_categories(item),
    }


def scrape_source(label, url, cap):
    """Fetch and parse one native Wykop RSS view without aborting the others."""
    xml = get_html(url)
    if not xml:
        return []
    try:
        soup = BeautifulSoup(xml, "xml")
    except Exception as exc:
        logger.warning("  [%s] invalid XML: %s", label, exc)
        return []

    entries = []
    items = soup.find_all("item") or soup.find_all("entry")
    for item in items[:cap]:
        try:
            entry = parse_item(item, label)
            if entry:
                entries.append(entry)
        except Exception as exc:
            logger.warning("  [%s] skipping item: %s", label, exc)
    return entries


def richness_score(entry):
    description = entry.get("description") or ""
    title = entry.get("title") or ""
    return (
        bool(description and description != title),
        len(description),
        bool(entry.get("image")),
        bool(entry.get("external_link")),
        len(entry.get("categories") or []),
        len(title),
    )


def _ordered_union(*groups):
    values = []
    for group in groups:
        for value in group or []:
            if value and value not in values:
                values.append(value)
    return values


def merge_richest(left, right):
    """Merge duplicate findings while keeping the most informative variant."""
    richer, other = (
        (left, right)
        if richness_score(left) >= richness_score(right)
        else (right, left)
    )
    merged = dict(richer)
    for field in ("title", "description", "source", "image", "external_link"):
        if not merged.get(field) and other.get(field):
            merged[field] = other[field]

    dates = [value for value in (left.get("date"), right.get("date")) if value]
    if dates:
        merged["date"] = min(dates)
    merged["feed_sources"] = _ordered_union(
        *(entry.get("feed_sources") for entry in (left, right))
    )
    merged["feed_sources"].sort(
        key=lambda value: SOURCE_ORDER.index(value)
        if value in SOURCE_ORDER
        else len(SOURCE_ORDER)
    )
    merged["categories"] = _ordered_union(
        left.get("categories"), right.get("categories")
    )
    merged["link"] = left.get("link") or right.get("link")
    return merged


def finding_id_from_url(url):
    match = _WYKOP_ID_RE.search(url or "")
    return match.group(1) if match else ""


def dedupe_richest(entries):
    by_identity = {}
    order = []
    for entry in entries:
        identity = finding_id_from_url(entry.get("link", "")) or normalize_link(
            entry.get("link", "")
        )
        if not identity:
            continue
        if identity not in by_identity:
            by_identity[identity] = entry
            order.append(identity)
        else:
            by_identity[identity] = merge_richest(by_identity[identity], entry)
    return [by_identity[identity] for identity in order]


def scrape_all():
    entries = []
    for label, url, cap in FEED_SOURCES:
        logger.info("Scraping %s ...", label)
        entries.extend(scrape_source(label, url, cap))
    return dedupe_richest(entries)


def merge_with_cache(fresh, cached):
    return dedupe_richest([*cached, *fresh])


def generate_atom_feed(entries):
    fg = FeedGenerator()
    fg.id(f"{BLOG_URL}#wykop")
    fg.title("Wykop")
    fg.subtitle(SUBTITLE)
    setup_feed_links(fg, BLOG_URL, FEED_NAME, icon=favicon_proxy("wykop.pl"))
    fg.language("pl")
    fg.author({"name": "Wykop"})
    setup_feed_extensions(fg)

    for entry in entries:
        fe = fg.add_entry()
        fe.id(make_entry_id(FEED_NAME, entry["link"]))
        fe.title(entry["title"])
        fe.link(href=entry["link"])
        fe.description(entry.get("description") or entry["title"])
        for category in _ordered_union(
            entry.get("feed_sources"), entry.get("categories")
        ):
            fe.category(term=category, label=category)
        set_entry_source(fe, entry.get("source"))
        add_entry_media(fe, entry.get("image"))
        if entry.get("date"):
            fe.published(entry["date"])
            fe.updated(entry["date"])
    return fg


def main(full=False):
    fresh = scrape_all()
    cached = []
    if not full:
        cached = deserialize_entries(
            load_cache(FEED_NAME).get("entries", []), date_field="date"
        )
    if not fresh and not cached:
        logger.warning("No Wykop entries collected; preserving the last good feed")
        return False

    merged = merge_with_cache(fresh, cached)
    merged = sort_posts_for_feed(merged, date_field="date")
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]
    save_cache(FEED_NAME, merged)
    save_atom_feed(generate_atom_feed(merged), FEED_NAME)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined Wykop feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
