"""Shared utilities for feed generators.

A trimmed, self-contained version: HTTP fetching, XML sanitization, a JSON
cache for incremental updates, and feedgen link helpers. No Selenium and no
external settings library — everything here depends only on requests, feedgen,
and pytz.
"""

import hashlib
import html as html_lib
import json
import logging
import os
import re
import unicodedata
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
REPO_SLUG = os.getenv("RSS_REPO_SLUG") or os.getenv("GITHUB_REPOSITORY") or "trvny/feedseek"

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
            # Cache files are committed, so they cross platforms; the default
            # encoding does not. UnicodeDecodeError means the same thing here
            # as a bad parse: refetch rather than take the run down.
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Loaded cache with {len(data.get(entries_key, []))} entries")
                return data
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning(f"Corrupted cache file {cache_file}, starting fresh")
    logger.info("No cache file found, will do full fetch")
    return {"last_updated": None, entries_key: []}


# Nothing bounded cache growth before this. Caches held every entry ever seen:
# 4chan had 21 109 of them (7.9 MB) to publish a 200-entry feed, and pap kept
# entries back to April 2021. At 82 335 entries across 91 files the directory
# was already 49.9 MB, and the R2 backup step silently keeps the previous
# snapshot once the cache passes FEEDSEEK_CACHE_MAX_BYTES (128 MB) — so
# unbounded growth was on course to disable the backup without failing anything.
#
# 2000 is deliberately generous: every accumulator feed documented in
# docs/feeds.md is far below it (the largest, beatport_top100, holds 200), so
# none of them lose history. It trims 7 of 91 caches. Pass a larger limit, or
# None, for a feed that genuinely needs a deeper dedup window.
DEFAULT_CACHE_LIMIT = 2000

# Quota for sources a per-source cap mapping does not name.
DEFAULT_SOURCE_QUOTA = 30


def source_quota(per_source_cap, source: str) -> int | None:
    """Resolve one source's ceiling from an int, a mapping, or None.

    A plain int applies to every source. A mapping gives named sources their own
    ceiling and falls back to its ``""`` key (or ``DEFAULT_SOURCE_QUOTA``) for
    the rest, which is how a content farm can be held to a handful of slots
    while editorial sources keep a useful share of the same feed.
    """
    if isinstance(per_source_cap, dict):
        return per_source_cap.get(source, per_source_cap.get("", DEFAULT_SOURCE_QUOTA))
    return per_source_cap


def allocate_fair_share(
    entries: list[dict],
    limit: int,
    per_source_cap=None,
    date_field: str = "date",
) -> list[dict]:
    """Pick ``limit`` entries by dealing slots round-robin across sources.

    The rule that matters: **every source places its newest entry before any
    source places a second one.** A source that publishes three times a year
    therefore keeps its latest post visible until it publishes again, instead of
    being evicted by whichever source happens to post hourly. Rounds continue —
    everyone's second-newest, then third — until ``limit`` is reached.

    This replaces a quota-plus-backfill scheme that leaked badly. There, entries
    over quota went to an overflow pool and leftover slots were refilled from it
    *by recency alone*, so the most prolific source ate every slot the quiet ones
    could not fill. Real numbers before the change: lemmy set a per-source cap of
    50, yet sh.itjust.works held 128 of 250 entries because two sibling instances
    were quiet. Steam published 7 of the 20 sources sitting in its cache.

    ``per_source_cap`` keeps its two shapes but changes meaning:

    - a **mapping** is a hard ceiling and stays hard through both passes, since
      naming a source explicitly is how this repo throttles a content farm;
    - an **int** is a first-pass target, not a wall. Once every source has hit it
      or run dry, a second pass refills whatever slots remain, again round-robin.
      Without that pass a feed would simply shrink whenever a source went quiet.

    ``entries`` arrives ascending (see :func:`sort_posts_for_feed`); the result is
    returned in the same order, so only membership changes, never feed ordering.
    """
    if limit is None or len(entries) <= limit:
        return list(entries)

    by_source: dict[str, list[dict]] = {}
    for entry in entries:
        by_source.setdefault(entry.get("source") or "", []).append(entry)
    for bucket in by_source.values():
        bucket.reverse()  # ascending input -> newest first within each source

    # Sorted rotation keeps the choice deterministic: the same cache must not
    # produce a different feed on a re-run just because dict order shifted.
    order = sorted(by_source)
    cursor = dict.fromkeys(order, 0)
    selected: list[dict] = []

    def deal(ceiling_for) -> None:
        progressed = True
        while len(selected) < limit and progressed:
            progressed = False
            for source in order:
                if len(selected) >= limit:
                    break
                bucket = by_source[source]
                index = cursor[source]
                ceiling = ceiling_for(source)
                if index >= len(bucket) or (ceiling is not None and index >= ceiling):
                    continue
                selected.append(bucket[index])
                cursor[source] = index + 1
                progressed = True

    deal(lambda source: source_quota(per_source_cap, source))
    if len(selected) < limit:
        hard = isinstance(per_source_cap, dict)
        deal(lambda source: source_quota(per_source_cap, source) if hard else None)

    return sort_posts_for_feed(selected, date_field=date_field)


def trim_entries(
    entries: list[dict],
    limit: int | None = DEFAULT_CACHE_LIMIT,
    date_field: str = "date",
) -> list[dict]:
    """Keep the newest ``limit`` entries, without letting one source starve others.

    Recency alone is not safe here. Six of the seven caches this trims belong to
    combined feeds, and their sources are wildly unequal: tvp holds 4345 TVP
    Sport and 4167 TVP Info entries against 131 Moto, 65 Rozrywka, 53 Kultura
    and 39 Informacje. A plain newest-N slice would be ~97% Sport and Info, and
    the quiet sources would vanish from the dedup state entirely — the very
    outcome the published-feed allocator exists to prevent. So the cache uses
    that same allocator: :func:`allocate_fair_share`, round-robin, no ceiling.
    A single-source cache has nothing to round-robin against and so degrades to
    a plain recency trim, which is the right behaviour for it.

    Entries arrive sorted ascending by date (see sort_posts_for_feed), which
    also parks dateless entries after the dated ones. Those are split out and
    always kept: without a date they cannot be ranked, and dropping them risks
    re-emitting the item on the next run. The result can therefore exceed
    ``limit`` by the number of dateless entries, which is normally zero because
    invoke_generator.freeze_missing_dates fills them in first.
    """
    if limit is None or len(entries) <= limit:
        return entries

    dated = [e for e in entries if e.get(date_field) is not None]
    dateless = [e for e in entries if e.get(date_field) is None]
    if len(dated) <= limit:
        return dated + dateless

    return allocate_fair_share(dated, limit, date_field=date_field) + dateless


def save_cache(
    feed_name: str,
    entries: list[dict],
    entries_key: str = "entries",
    limit: int | None = DEFAULT_CACHE_LIMIT,
    date_field: str = "date",
    extra: dict | None = None,
) -> None:
    """Save entries to the cache file, serializing datetimes to ISO strings.

    *extra* adds top-level keys alongside the entries — for bookkeeping that
    belongs with the cache but is not an entry, such as a per-URL count of
    failed fetches. It cannot overwrite ``last_updated`` or *entries_key*.
    Identical state is not rewritten: ``last_updated`` tracks the last semantic
    cache change, which keeps repository diffs quiet and R2 freshness meaningful.
    """
    cache_file = get_cache_file(feed_name)
    original_count = len(entries)
    entries = trim_entries(entries, limit=limit, date_field=date_field)
    if len(entries) < original_count:
        logger.info(
            f"Trimmed cache from {original_count} to {len(entries)} entries "
            f"(limit {limit}); oldest dropped first"
        )
    serializable = []
    for entry in entries:
        entry_copy = entry.copy()
        for key, value in entry_copy.items():
            if isinstance(value, datetime):
                entry_copy[key] = value.isoformat()
        serializable.append(entry_copy)

    payload = {entries_key: serializable}
    for key, value in (extra or {}).items():
        if key in {"last_updated", entries_key}:
            raise ValueError(f"extra key {key!r} would overwrite a reserved cache field")
        payload[key] = value

    previous = None
    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                previous = json.load(f)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            pass

    if isinstance(previous, dict) and isinstance(previous.get("last_updated"), str):
        try:
            datetime.fromisoformat(previous["last_updated"])
        except (ValueError, TypeError, OverflowError):
            pass
        else:
            previous_payload = {
                key: value for key, value in previous.items() if key != "last_updated"
            }
            def canonical(value):
                return json.dumps(
                    value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                )

            if canonical(previous_payload) == canonical(payload):
                logger.info(f"Cache unchanged; keeping {cache_file}")
                return

    data = {"last_updated": datetime.now(pytz.UTC).isoformat(), **payload}

    def _write(target):
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    write_atomically(cache_file, _write)
    logger.info(f"Saved cache with {len(entries)} entries to {cache_file}")


def write_atomically(path, write) -> None:
    """Write via a temporary sibling and rename into place.

    Every published artifact is written straight to its final path, and the
    scheduled job commits feeds/ and cache/ whether or not generation
    succeeded. So a generator killed mid-write - by the per-generator timeout,
    by the job timeout, by anything - would commit a truncated file over a good
    one. os.replace is atomic on both POSIX and Windows as long as source and
    destination share a filesystem, which a sibling always does: readers either
    see the previous file or the complete new one, never half of either.
    """
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        write(tmp)
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:  # a leftover temp file is not worth masking the real error
            pass
        raise


def _make_feedgen_writes_atomic() -> None:
    """Route every feedgen file write through :func:`write_atomically`.

    Patched on the class rather than only at shared helper call sites so direct
    feedgen writes remain atomic as a fallback safety net. Current generators
    use the shared writers, and this wrapper also protects future or legacy
    direct ``atom_file`` / ``rss_file`` calls from committing partial output.
    """
    for name in ("atom_file", "rss_file"):
        original = getattr(FeedGenerator, name)
        if getattr(original, "_feedseek_atomic", False):
            continue  # re-importing must not wrap the wrapper

        def make(original):
            def write_file(self, filename, *args, **kwargs):
                return write_atomically(
                    filename, lambda target: original(self, str(target), *args, **kwargs)
                )

            write_file._feedseek_atomic = True
            write_file.__name__ = original.__name__
            write_file.__doc__ = original.__doc__
            return write_file

        setattr(FeedGenerator, name, make(original))


_make_feedgen_writes_atomic()


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


def favicon_url(blog_url: str) -> str:
    """Best-guess favicon URL for a site: scheme + host + /favicon.ico.

    Not guaranteed (some sites serve their icon elsewhere), but it's the same
    convention every hand-set <icon> in this repo already uses, and most feed
    readers show it in place of a fallback letter-avatar when present.
    Returns blog_url unchanged if it can't be parsed.
    """
    try:
        parts = urlsplit(blog_url)
        if not parts.scheme or not parts.netloc:
            return blog_url
        return f"{parts.scheme}://{parts.netloc}/favicon.ico"
    except Exception:
        return blog_url


def favicon_proxy(domain: str, *, sz: int = 64, provider: str = "google") -> str:
    """Favicon URL via a third-party resolver, for sites whose own
    ``/favicon.ico`` 404s or serves HTML. The resolver finds the real icon
    server-side and self-heals when the site moves it, so it never rots the way
    a hard-coded asset path does.

    ``provider="google"`` -> Google S2 (honours ``sz``); ``"duckduckgo"`` ->
    DDG ip3 (fixed size). Pick whichever actually resolves the domain.
    """
    if provider == "duckduckgo":
        return f"https://icons.duckduckgo.com/ip3/{domain}.ico"
    return f"https://www.google.com/s2/favicons?domain={domain}&sz={sz}"


# Feeds whose site does not serve a usable /favicon.ico, so the guess made by
# favicon_url() produces a dead <icon> and the reader falls back to a letter
# avatar. Measured 11.08.2026 by fetching every published feed's <icon>: 17 of
# 90 were dead — 404 (europa, lemmy, mit, ra, saas, sony, spotify, usgov,
# wykop), 403 (nexusmods_news, openai) or a 200 with an empty body (jbzd,
# lexus_newsroom, microsoft, mozilla, theysaidso, toyota_global).
#
# Every entry resolves through Google S2 rather than the site's own asset path.
# That is deliberate: the sites here mostly *do* serve an icon, just from a
# versioned theme path like /wp-content/themes/foxtail/... which rots at the
# next redesign — exactly how these 17 broke. S2 re-resolves server-side, so it
# self-heals. Checked 11.08.2026: all 17 return a distinct real image (269 B to
# 3877 B, no two alike), not S2's generic globe placeholder.
#
# An explicit icon= argument still wins over this map; use it when a feed wants
# a specific mark rather than whatever the domain resolves to. Re-check the map
# with tools/check_feed_icons.py.
VERIFIED_ICONS = {
    "europa": "european-union.europa.eu",
    "jbzd": "jbzd.com.pl",
    "lemmy": "join-lemmy.org",
    "lexus_newsroom": "pressroom.lexus.com",
    "microsoft": "blogs.microsoft.com",
    "mit": "news.mit.edu",
    "mozilla": "blog.mozilla.org",
    "nexusmods_news": "nexusmods.com",
    "openai": "openai.com",
    "ra": "ra.co",
    "saas": "hashicorp.com",
    "sony": "sony.com",
    "spotify": "newsroom.spotify.com",
    "theysaidso": "theysaidso.com",
    "toyota_global": "pressroom.toyota.com",
    # usgov and wykop were dead too, but they already set icon= explicitly, so
    # they are fixed at their call site rather than duplicated here.
}


def verified_icon(feed_name: str) -> str | None:
    """Icon URL for a feed whose own /favicon.ico is known not to work."""
    domain = VERIFIED_ICONS.get(feed_name)
    return favicon_proxy(domain) if domain else None


def large_icon(icon_url: str, size: int = 256) -> str:
    """A bigger version of an icon URL, when the source can serve one.

    Atom's <logo> and JSON Feed's "icon" are both meant to be the large,
    display-sized image, next to the small <icon>/"favicon" pair - and a
    64px square stretched into a card header looks like exactly what it is.
    Google's S2 resolver takes the size as a query parameter, so for the icons
    this project routes through it the bigger one is free. Anything else is
    returned unchanged rather than guessed at.
    """
    if "google.com/s2/favicons" not in (icon_url or ""):
        return icon_url
    return re.sub(r"([?&]sz=)\d+", rf"\g<1>{size}", icon_url)


def setup_feed_links(
    fg: FeedGenerator, blog_url: str, feed_name: str, icon: str | None = None
) -> None:
    """Set feed links so <link rel="self"> points to the raw feed and the main
    link points to the source site. Also sets <icon> to a best-guess favicon
    so readers show a real icon instead of a letter-avatar fallback; pass
    ``icon`` to override the guess when a site serves its icon elsewhere.

    feedgen requires rel="self" be set first and rel="alternate" last.
    """
    fg.link(
        href=f"https://raw.githubusercontent.com/{REPO_SLUG}/main/feeds/feed_{feed_name}.xml",
        rel="self",
    )
    fg.link(href=blog_url, rel="alternate")
    resolved = icon or verified_icon(feed_name) or favicon_url(blog_url)
    fg.icon(resolved)
    # Readers disagree on which of the two they read, so set both rather than
    # leave either to chance. normalize_feed_self_links still mirrors one into
    # the other for generators that write their feed without this helper.
    fg.logo(large_icon(resolved))


# ---------------------------------------------------------------------------
# Media (MRSS) + per-item source attribution + entry-ID compatibility seed
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
    """Build the legacy-compatible initial tag-URI ID seed from a link.

    Published entry IDs are reader state and must stay permanent. New entries
    keep this URL-derived value only as the compatibility seed used before an
    ID has been persisted in cache. Renderers must use
    :func:`entry_identity.entry_id_for`, which prefers the persisted ID so a
    later URL change does not make the same article look new again.
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


# Images that are not the article's picture: tracking beacons, author avatars,
# share buttons and layout spacers, all of which are commonly the first <img>
# in a feed's description HTML.
_JUNK_IMAGE_MARKERS = (
    "pixel",
    "spacer",
    "blank.",
    "1x1",
    "/avatar",
    "gravatar.com",
    "feedburner",
    "doubleclick",
    "/emoji/",
    "/badge",
    "/button",
    "share-",
    "icon-",
)
_IMG_SRC_RE = re.compile(
    r"""<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["'][^>]*>""", re.IGNORECASE
)
_IMG_DIMENSION_RE = re.compile(
    r"""\b(?:width|height)\s*=\s*["']?\s*(\d+)""", re.IGNORECASE
)


def html_image(html: str, base_url: str | None = None) -> str | None:
    """First real image inside a chunk of entry HTML.

    Measured 12.08.2026: of 150 items sampled across six upstream feeds, none
    carried MRSS or an enclosure, but 103 carried an ``<img>`` in their
    description. Reading only the structured fields threw all of them away and
    left the entry looking imageless, which is how 77% of published entries
    ended up with no picture at all.

    Skips the usual impostors - tracking beacons, avatars, share buttons - and
    anything declaring a dimension under 64px, which no article illustration
    does but every spacer gif does.
    """
    if not html or "<img" not in html.lower():
        return None
    for match in _IMG_SRC_RE.finditer(html):
        src = html_lib.unescape((match.group(1) or "").strip())
        if not src or src.startswith("data:"):
            continue
        if any(marker in src.lower() for marker in _JUNK_IMAGE_MARKERS):
            continue
        sizes = [int(value) for value in _IMG_DIMENSION_RE.findall(match.group(0))]
        if sizes and min(sizes) < 64:
            continue
        url = urljoin(base_url, src) if base_url else src
        if urlsplit(url).scheme in ("http", "https"):
            return url
    return None


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

    # Last and by far the most productive: the picture sitting in the entry's
    # own HTML. WordPress, Ghost and most CMS feeds ship it there and nowhere
    # else, so the structured fields above find nothing on the majority of
    # feeds this project reads.
    for tag in ("encoded", "description", "content", "summary"):
        for element in item.find_all(tag):
            found = html_image(element.get_text(), _entry_base_url(item))
            if found:
                return found

    return None


def _entry_base_url(item) -> str | None:
    """The entry's own link, for resolving relative <img src> paths."""
    for link_el in item.find_all("link"):
        href = (link_el.get("href") or "").strip() or link_el.get_text(strip=True)
        if href.startswith("http"):
            return href
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

    # Same last resort as feed_item_image: most feeds put the picture only in
    # the entry body.
    bodies = [part.get("value") for part in entry.get("content", []) or []]
    bodies += [entry.get("summary"), entry.get("description")]
    for body in bodies:
        found = html_image(body or "", entry.get("link"))
        if found:
            return found

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
    """Write an Atom feed to feeds/feed_<n>.xml (project default format)."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    _write_json_sidecar(output_file, feed_name)
    return output_file


def save_rss_feed(fg: FeedGenerator, feed_name: str) -> Path:
    """Write an RSS 2.0 feed to feeds/feed_<n>.xml (for future RSS feeds)."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.rss_file(str(output_file), pretty=True)
    logger.info(f"Saved RSS feed to {output_file}")
    _write_json_sidecar(output_file, feed_name)
    return output_file


def _write_json_sidecar(xml_path: Path, feed_name: str) -> None:
    """Write a JSON Feed 1.1 sibling next to the XML. Never fails the run:
    the XML is the published artifact; a JSON hiccup must not blank a feed."""
    try:
        from jsonfeed import write_json_feed

        write_json_feed(xml_path, feed_name, entry_image=feedparser_entry_image)
        logger.info(f"Saved JSON feed to {xml_path.with_suffix('.json')}")
    except Exception as exc:  # per-item isolation philosophy: log, don't abort
        logger.warning(f"JSON Feed sidecar failed for {feed_name}: {exc}")


# ---------------------------------------------------------------------------
# URL / title normalization + cross-source dedupe
# ---------------------------------------------------------------------------

from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qsl, urlencode  # noqa: E402

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
    """Collapse a Unicode title to a canonical, case-folded comparison key."""
    folded = unicodedata.normalize(
        "NFC", unicodedata.normalize("NFD", title or "").casefold()
    )
    chars: list[str] = []
    for char in folded:
        is_mark = unicodedata.category(char).startswith("M")
        if char.isalnum() or (is_mark and chars and chars[-1] != " "):
            chars.append(char)
        else:
            chars.append(" ")
    return " ".join("".join(chars).split())


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
