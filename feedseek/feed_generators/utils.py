"""Shared utilities for feed generators.

A trimmed, self-contained version: HTTP fetching, XML sanitization, a JSON
cache for incremental updates, and feedgen link helpers. No Selenium and no
external settings library — everything here depends only on requests, feedgen,
and pytz.
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytz
import requests
from feedgen.feed import FeedGenerator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {"User-Agent": DEFAULT_USER_AGENT}

# Used to build the rel="self" link in each feed. In GitHub Actions,
# GITHUB_REPOSITORY ("owner/repo") is set automatically, so the self link is
# correct out of the box. Override locally with RSS_REPO_SLUG if needed.
REPO_SLUG = os.getenv("RSS_REPO_SLUG") or os.getenv("GITHUB_REPOSITORY") or "trvny/feeds"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def setup_logging(name: str | None = None) -> logging.Logger:
    """Configure logging and return a logger. Call once: ``logger = setup_logging()``."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    if name is None:
        import inspect

        frame_info = inspect.stack()[1]
        frame = getattr(frame_info, "frame", frame_info[0])
        name = frame.f_globals.get("__name__", __name__)
    return logging.getLogger(name)


logger = setup_logging()

# ---------------------------------------------------------------------------
# Text sanitization
# ---------------------------------------------------------------------------

# XML 1.0 forbids NULL bytes and most C0/C1 control characters.
_INVALID_XML_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def sanitize_xml(text: str) -> str:
    """Strip characters that are invalid in XML 1.0 from *text*."""
    return _INVALID_XML_RE.sub("", text)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def get_cache_dir() -> Path:
    cache_dir = get_project_root() / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_feeds_dir() -> Path:
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def get_cache_file(feed_name: str) -> Path:
    return get_cache_dir() / f"{feed_name}_posts.json"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def fetch_page(url: str, timeout: int = 30, headers: dict | None = None) -> str:
    """Fetch a URL and return its text body, raising on HTTP errors."""
    response = requests.get(url, headers=headers or DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def stable_fallback_date(identifier: str) -> datetime:
    """Generate a stable date from a URL/title hash for dateless posts.

    Uses hashlib rather than the builtin hash(), which is salted per process
    (PYTHONHASHSEED) and would otherwise assign a different fallback date on
    every run — defeating the whole point of a *stable* fallback.
    """
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    hash_val = int(digest, 16) % 730
    epoch = datetime(2023, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
    return epoch + timedelta(days=hash_val)


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


def load_cache(feed_name: str, entries_key: str = "entries") -> dict:
    """Load existing cache or return an empty structure."""
    cache_file = get_cache_file(feed_name)
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                data = json.load(f)
                logger.info(f"Loaded cache with {len(data.get(entries_key, []))} entries")
                return data
        except json.JSONDecodeError:
            logger.warning(f"Corrupted cache file {cache_file}, starting fresh")
    logger.info("No cache file found, will do full fetch")
    return {"last_updated": None, entries_key: []}


def save_cache(feed_name: str, entries: list[dict], entries_key: str = "entries") -> None:
    """Save entries to the cache file, serializing datetimes to ISO strings."""
    cache_file = get_cache_file(feed_name)
    serializable = []
    for entry in entries:
        entry_copy = entry.copy()
        for key, value in entry_copy.items():
            if isinstance(value, datetime):
                entry_copy[key] = value.isoformat()
        serializable.append(entry_copy)

    data = {"last_updated": datetime.now(pytz.UTC).isoformat(), entries_key: serializable}
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved cache with {len(entries)} entries to {cache_file}")


def deserialize_entries(entries: list[dict], date_field: str = "date") -> list[dict]:
    """Convert cached ISO date strings back to datetime objects."""
    result = []
    for entry in entries:
        entry_copy = entry.copy()
        if isinstance(entry_copy.get(date_field), str):
            try:
                entry_copy[date_field] = datetime.fromisoformat(entry_copy[date_field])
            except ValueError:
                entry_copy[date_field] = stable_fallback_date(entry_copy.get("link", ""))
        result.append(entry_copy)
    return result


def merge_entries(
    new_entries: list[dict],
    cached_entries: list[dict],
    id_field: str = "link",
    date_field: str = "date",
) -> list[dict]:
    """Merge new entries into the cache, deduplicate by id_field, and sort."""
    existing_ids = {e[id_field] for e in cached_entries}
    merged = list(cached_entries)

    added = 0
    for entry in new_entries:
        if entry[id_field] not in existing_ids:
            merged.append(entry)
            existing_ids.add(entry[id_field])
            added += 1

    logger.info(f"Added {added} new entries to cache")
    return sort_posts_for_feed(merged, date_field=date_field)


# ---------------------------------------------------------------------------
# Feed generation
# ---------------------------------------------------------------------------


def setup_feed_links(fg: FeedGenerator, blog_url: str, feed_name: str) -> None:
    """Set feed links so <link rel="self"> points to the raw feed and the main
    link points to the source site.

    feedgen requires rel="self" be set first and rel="alternate" last.
    """
    fg.link(
        href=f"https://raw.githubusercontent.com/{REPO_SLUG}/main/feedseek/feeds/feed_{feed_name}.xml",
        rel="self",
    )
    fg.link(href=blog_url, rel="alternate")


# ---------------------------------------------------------------------------
# Media (MRSS) + per-item source attribution + stable entry IDs
# ---------------------------------------------------------------------------

# Tag-URI authority: this project has controlled the trvny.github.io /
# trvny/feeds namespace since before this date. Per RFC 4151, a tag URI's
# date only needs to predate first use, not be exact.
_TAG_AUTHORITY = "trvny.github.io"
_TAG_DATE = "2024"

_EXT_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".avif": "image/avif",
}


def guess_mime_type(url: str, default: str = "image/jpeg") -> str:
    """Guess an image MIME type from a URL's extension. Falls back to
    image/jpeg (the most common case) rather than failing, since a slightly
    wrong MIME type on an enclosure is harmless."""
    path = urlsplit(url).path.lower() if url else ""
    for ext, mime in _EXT_MIME.items():
        if path.endswith(ext):
            return mime
    return default


def make_entry_id(feed_name: str, link: str) -> str:
    """Build a stable tag-URI entry ID (RFC 4151) from a feed name + link.

    Atom/RSS entry IDs are supposed to be permanent - they're how readers
    dedupe and track read/unread state. Using the raw article link as the ID
    (the previous convention here) ties identity to something that can
    legitimately change (a site migrates URLs, adds/drops a trailing slash,
    a link gets re-canonicalized). A tag URI decouples the two: the link can
    move without the entry losing its read/subscribed identity in readers
    that treat id changes as a new item.
    """
    digest = hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]
    return f"tag:{_TAG_AUTHORITY},{_TAG_DATE}:feedseek/{feed_name}/{digest}"


def setup_feed_extensions(fg: FeedGenerator) -> None:
    """Load the extensions shared image/attribution handling depends on:

    - ``media`` (feedgen built-in): media:content / media:thumbnail / media:group.
    - ``dc`` (feedgen built-in): per-item dc:creator for source attribution
      in combined/aggregated feeds.
    - ``media_full`` (this repo's media_ext.py): media:community / license /
      embed - the rest of MRSS 1.5.1 that feedgen's built-in module skips.

    Call once per FeedGenerator, before adding entries.
    """
    fg.load_extension("media")
    fg.load_extension("dc")
    from media_ext import MediaFullEntryExtension, MediaFullExtension

    fg.register_extension("media_full", MediaFullExtension, MediaFullEntryExtension)


def add_entry_media(
    fe,
    image_url: str | None,
    *,
    mime_type: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Attach an image to an entry via MRSS + a plain enclosure.

    Emits both media:content (medium="image") and a plain RSS <enclosure> -
    per-reader support for MRSS varies (Miniflux/FreshRSS render it,
    NetNewsWire's RSS parser currently only reads <enclosure>), so shipping
    both maximizes how many readers actually show the image. Requires
    setup_feed_extensions(fg) to have been called on the parent feed.
    No-ops silently if image_url is falsy - callers don't need to guard.
    """
    if not image_url:
        return
    mime = mime_type or guess_mime_type(image_url)

    # fe.enclosure() is intentionally NOT used here -- feedgen 1.0.0 has a
    # variable-shadowing bug in FeedEntry.atom_entry() that silently drops
    # rel/type/length from entry-level <link> elements, so an Atom enclosure
    # added that way renders as an unlabeled link a reader would mistake for
    # a second alternate page. media_full.enclosure() (this repo's
    # media_ext.py) renders the correct rel="enclosure" link (Atom) /
    # <enclosure> element (RSS) directly, sidestepping the bug.
    if hasattr(fe, "media_full"):
        fe.media_full.enclosure(image_url, mime_type=mime)

    if hasattr(fe, "media"):
        content = {"url": image_url, "type": mime, "medium": "image"}
        if width:
            content["width"] = str(width)
        if height:
            content["height"] = str(height)
        fe.media.content(content)
        thumb = {"url": image_url}
        if width:
            thumb["width"] = str(width)
        if height:
            thumb["height"] = str(height)
        fe.media.thumbnail(thumb)


def feed_item_image(item) -> str | None:
    """Pull an image URL from a BeautifulSoup-parsed RSS/Atom <item>/<entry>.

    Handles MRSS media:content / media:thumbnail (namespace-stripped by the xml
    parser to "content" / "thumbnail"), a plain <enclosure type="image/...">,
    and a bare <image><url> / Atom <link rel="image" href>. Returns None when
    nothing usable is found (add_entry_media already no-ops on None).
    """
    media_content = item.find("content", medium="image") or item.find("content")
    if media_content and media_content.get("url") and media_content.get("medium") in (None, "image"):
        return media_content["url"]

    thumbnail = item.find("thumbnail")
    if thumbnail and thumbnail.get("url"):
        return thumbnail["url"]

    enclosure = item.find("enclosure")
    if enclosure and enclosure.get("url") and "image" in (enclosure.get("type") or ""):
        return enclosure["url"]

    image_el = item.find("image")
    if image_el:
        url_el = image_el.find("url")
        if url_el and url_el.get_text(strip=True):
            return url_el.get_text(strip=True)
        if image_el.get("href"):  # Atom <link rel="image" href="..."> style
            return image_el["href"]

    return None


def feedparser_entry_image(entry) -> str | None:
    """Pull an image URL from a feedparser entry.

    feedparser normalizes MRSS into entry.media_content / entry.media_thumbnail
    (lists of dicts), RSS enclosures into entry.enclosures, and Atom enclosure
    links into entry.links (rel="enclosure"). Returns None when nothing usable
    is found (add_entry_media already no-ops on None).
    """
    for mc in entry.get("media_content", []) or []:
        url = mc.get("url")
        if not url:
            continue
        medium = mc.get("medium")
        mtype = mc.get("type") or ""
        if medium == "image" or (medium is None and (not mtype or "image" in mtype)):
            return url

    for mt in entry.get("media_thumbnail", []) or []:
        if mt.get("url"):
            return mt["url"]

    for enc in entry.get("enclosures", []) or []:
        if enc.get("href") and "image" in (enc.get("type") or ""):
            return enc["href"]

    for link in entry.get("links", []) or []:
        if (
            link.get("rel") == "enclosure"
            and link.get("href")
            and "image" in (link.get("type") or "")
        ):
            return link["href"]

    return None


def set_entry_source(fe, source: str | None) -> None:
    """Set dc:creator on an entry to the original source/publisher name.

    For combined/aggregated feeds this preserves per-item provenance
    independent of <category> (which some readers hide or don't render),
    and is the field readers commonly show as a byline. Requires
    setup_feed_extensions(fg) to have been called. No-op if source is falsy.
    """
    if not source or not hasattr(fe, "dc"):
        return
    fe.dc.dc_creator(source)


def sort_posts_for_feed(posts: list[dict[str, Any]], date_field: str = "date") -> list[dict[str, Any]]:
    """Sort newest-last (ascending). feedgen reverses on write, so the final
    feed is newest-first. Dateless posts are placed at the end."""
    with_date = [p for p in posts if p.get(date_field) is not None]
    without_date = [p for p in posts if p.get(date_field) is None]
    with_date.sort(key=lambda x: x[date_field])
    return with_date + without_date


def save_atom_feed(fg: FeedGenerator, feed_name: str) -> Path:
    """Write an Atom feed to feeds/feed_<name>.xml (project default format)."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return output_file


def save_rss_feed(fg: FeedGenerator, feed_name: str) -> Path:
    """Write an RSS 2.0 feed to feeds/feed_<name>.xml (for future RSS feeds)."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.rss_file(str(output_file), pretty=True)
    logger.info(f"Saved RSS feed to {output_file}")
    return output_file


# ---------------------------------------------------------------------------
# URL / title normalization + cross-source dedupe
# ---------------------------------------------------------------------------

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode  # noqa: E402

# Tracking/click-id query params dropped during canonicalization. utm_* is
# matched by prefix separately.
_TRACKING_PARAMS = {
    "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src",
    "igshid", "yclid", "_hsenc", "_hsmi", "vero_id",
}


def normalize_link(url: str) -> str:
    """Canonicalize a URL into a still-valid form usable as both a stored link
    and a dedup key: force https, lowercase the host, drop a leading ``www.``,
    fold ``index.html`` and a trailing slash, and strip tracking query params
    (``utm_*``, ``gclid``, ``fbclid``, ...). Non-tracking query params AND the
    fragment are PRESERVED — some feeds distinguish entries only by ``?query`` or
    ``#fragment``. Returns the trimmed input on parse failure."""
    if not url:
        return url
    try:
        p = urlsplit(url.strip())
        host = re.sub(r"^www\.", "", (p.hostname or "").lower())
        if p.port:
            host = f"{host}:{p.port}"
        path = re.sub(r"/index\.html?$", "/", p.path or "")
        if len(path) > 1:
            path = path.rstrip("/")
        kept = [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
        ]
        scheme = "https" if p.scheme in ("http", "https", "") else p.scheme
        return urlunsplit((scheme, host, path, urlencode(kept), p.fragment))
    except Exception:
        return url.strip()


def normalize_title(title: str) -> str:
    """Collapse a title to a comparison key: lowercase, runs of non-alphanumerics
    folded to a single space, trimmed."""
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def dedupe_entries(entries, id_field="link", title_field="title", date_field="date"):
    """Remove cross-source duplicates by normalized URL or normalized title.
    First occurrence wins and order is preserved; a later duplicate that carries a
    date replaces a kept one that lacks it."""
    seen_url, seen_title, result, removed = {}, {}, [], 0
    for entry in entries:
        ukey = normalize_link(entry.get(id_field, ""))
        tkey = normalize_title(entry.get(title_field, ""))
        idx = seen_url.get(ukey) if ukey else None
        if idx is None and tkey:
            idx = seen_title.get(tkey)
        if idx is None:
            pos = len(result)
            if ukey:
                seen_url[ukey] = pos
            if tkey:
                seen_title[tkey] = pos
            result.append(entry)
        else:
            removed += 1
            if result[idx].get(date_field) is None and entry.get(date_field) is not None:
                result[idx] = entry
    if removed:
        logger.info(f"Deduplicated {removed} entries")
    return result
