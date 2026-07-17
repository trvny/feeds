"""Resident Advisor (RA) magazine feed generator.

RA (https://ra.co) has no native RSS/Atom feed and is a Next.js + Apollo
GraphQL app behind DataDome bot protection. The article listings are *not* in
``pageProps`` (those load client-side), but the server still ships the Apollo
cache in the page's ``__NEXT_DATA__`` blob under ``props.apolloState`` — so a
single ``curl_cffi`` Chrome-impersonated fetch per section is enough; no
browser/JS execution and no GraphQL calls needed.

This builds **one combined feed** from RA's editorial sections:

* ``/magazine`` — the magazine landing (news + featured pieces)
* ``/features`` — long-form feature articles
* ``/music``    — reviews, podcasts and music news

These sections overlap (the magazine landing re-lists features and news), so
entries are **deduplicated by their canonical content URL** across all three.

Each Apollo object exposes ``contentUrl`` (the dedupe key, e.g. ``/news/85326``,
``/features/4503``, ``/reviews/36353``, ``/podcast/1060``), a ``title`` and a
``blurb``. ``News`` and ``Feature`` objects carry a real ISO ``date``; ``Review``
and ``Podcast`` listings don't, so — like ``beatport_top100.py`` — those are
dated by the moment they're first observed and that timestamp is preserved in
the JSON cache (``cache/ra_posts.json``) across hourly runs. Within a single run
dateless items are offset by their listing position so the section order is kept.

Writes an **Atom** feed to ``feeds/feed_ra.xml``.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta

import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import (
    add_entry_media,
    deserialize_entries,
    get_feeds_dir,
    load_cache,
    merge_entries,
    sanitize_xml,
    save_cache,
    setup_feed_extensions,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "ra"
BLOG_URL = "https://ra.co/magazine"
BASE_URL = "https://ra.co"

# Sections that feed the combined output. Order matters only for the listing
# offset applied to dateless (Review/Podcast) items within a single run.
SECTIONS = [
    "https://ra.co/magazine",
    "https://ra.co/features",
    "https://ra.co/music",
]

# Apollo __typename values we treat as feed-worthy content.
CONTENT_TYPES = {"News", "Feature", "Review", "Podcast"}

# Human-readable category per content type.
CATEGORY = {
    "News": "News",
    "Feature": "Feature",
    "Review": "Review",
    "Podcast": "Podcast",
}

MAX_ENTRIES = 200


def fetch_section(url, retries=3, backoff=2.0):
    """Fetch one section's HTML, returning the body or None.

    RA sits behind DataDome, which fingerprints the TLS handshake and returns a
    challenge/403 to plain ``requests``. ``curl_cffi`` impersonating a real
    Chrome TLS fingerprint clears it; we fall back to the shared ``fetch_page``
    only if curl_cffi isn't installed (which will likely fail, but keeps the
    import non-fatal).
    """
    try:
        from curl_cffi import requests as creq
    except ImportError:
        logger.warning("curl_cffi not installed; falling back to plain requests (likely blocked)")
        from utils import fetch_page

        try:
            return fetch_page(url)
        except Exception as e:
            logger.error(f"Fallback fetch failed for {url}: {e}")
            return None

    for attempt in range(1, retries + 1):
        try:
            resp = creq.get(url, impersonate="chrome", timeout=30)
            if resp.status_code == 200 and "__NEXT_DATA__" in resp.text:
                logger.info(f"Fetched {url} ({len(resp.text)} bytes)")
                return resp.text
            logger.warning(f"Unexpected response (status {resp.status_code}) for {url} on attempt {attempt}")
        except Exception as e:
            logger.warning(f"Fetch failed for {url} (attempt {attempt}/{retries}): {e}")
        if attempt < retries:
            time.sleep(backoff * attempt)
    return None


def extract_apollo_state(html):
    """Pull props.apolloState out of the page's __NEXT_DATA__ blob."""
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag is None or not tag.string:
        logger.error("__NEXT_DATA__ script not found — page layout may have changed")
        return {}
    try:
        data = json.loads(tag.string)
        return data["props"]["apolloState"] or {}
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Could not parse __NEXT_DATA__ / apolloState: {e}")
        return {}


def _deref(value, state):
    """Resolve an Apollo ``{"__ref": "Type:id"}`` reference against the state."""
    if isinstance(value, dict) and "__ref" in value:
        return state.get(value["__ref"], {})
    return value if isinstance(value, dict) else {}


def _blurb(obj, state):
    """Best-effort description: direct blurb, else a (possibly ref'd) translation blurb."""
    if obj.get("blurb"):
        return obj["blurb"]
    translation = _deref(obj.get("translation"), state)
    return translation.get("blurb") or ""


def parse_date(raw):
    """Parse an ISO date string to a tz-aware UTC datetime, or None."""
    if not raw:
        return None
    try:
        dt = date_parser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, OverflowError, TypeError):
        return None


def parse_section(html, state_accum):
    """Parse one section's HTML into entry dicts (date may be None).

    *state_accum* accumulates the Apollo state across sections so references
    (e.g. a Podcast's translation blurb) can be resolved. Dateless items are
    left with ``date=None`` here; ``collect_entries`` assigns a first-seen
    timestamp after cross-section dedupe so a dated copy always wins.
    """
    state = extract_apollo_state(html)
    state_accum.update(state)

    entries = []
    for key, obj in state.items():
        if not isinstance(obj, dict) or obj.get("__typename") not in CONTENT_TYPES:
            continue
        try:
            content_url = obj.get("contentUrl")
            title = (obj.get("title") or "").strip()
            if not content_url or not title:
                continue

            link = content_url if content_url.startswith("http") else BASE_URL + content_url
            category = CATEGORY.get(obj.get("__typename"), "Magazine")
            description = sanitize_xml(_blurb(obj, state_accum).strip() or title)

            entries.append(
                {
                    "title": sanitize_xml(title),
                    "link": link,
                    "date": parse_date(obj.get("date")),  # may be None
                    "description": description,
                    "category": sanitize_xml(category),
                    "image": obj.get("imageUrl"),
                }
            )
        except Exception as e:  # never let one bad object kill the run
            logger.warning(f"Skipping malformed {obj.get('__typename')} ({key}): {e}")
            continue

    return entries


def collect_entries():
    """Fetch every section and return combined, deduped (by link) entries.

    Some sections expose a slimmer projection of the same item without a
    published ``date`` (e.g. ``/music`` lists News dateless while ``/magazine``
    dates them). Dedupe therefore *prefers the copy that carries a real date*,
    independent of section fetch order. Items that have no date in any section
    (most Reviews/Podcasts and music-only News) are then dated by first-seen,
    offset by collection order so listing order is preserved within a run; the
    cache preserves that timestamp across subsequent hourly runs.

    Returns None if *no* section could be fetched, so ``main`` can preserve the
    last good feed rather than emitting an empty one.
    """
    state_accum = {}
    by_link = {}          # link -> entry, insertion-ordered
    fetched_any = False

    for url in SECTIONS:
        html = fetch_section(url)
        if html is None:
            logger.warning(f"Could not fetch {url}; continuing with other sections")
            continue
        fetched_any = True
        for entry in parse_section(html, state_accum):
            existing = by_link.get(entry["link"])
            if existing is None:
                by_link[entry["link"]] = entry
            elif existing.get("date") is None and entry.get("date") is not None:
                # Upgrade to the dated copy but keep the original insertion slot.
                existing["date"] = entry["date"]

    if not fetched_any:
        return None

    # Assign first-seen timestamps to anything still undated, preserving the
    # order in which items were collected (newest sections/positions first).
    now = datetime.now(pytz.UTC)
    for offset, entry in enumerate(by_link.values()):
        if entry.get("date") is None:
            entry["date"] = now - timedelta(seconds=offset)

    entries = list(by_link.values())
    logger.info(f"Collected {len(entries)} unique entries across {len(SECTIONS)} sections")
    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    """Build an Atom FeedGenerator from the entry list."""
    fg = FeedGenerator()
    fg.id(f"{BASE_URL}/{feed_name}")
    fg.title("RA: Resident Advisor Magazine")
    fg.subtitle("News, features, reviews and podcasts from RA")
    setup_feed_links(fg, BLOG_URL, feed_name)
    setup_feed_extensions(fg)
    fg.language("en")
    fg.author({"name": "Resident Advisor"})

    for entry in entries:
        fe = fg.add_entry()
        fe.id(entry["link"])
        fe.title(entry["title"])
        fe.link(href=entry["link"])
        add_entry_media(fe, entry.get("image"))
        fe.description(entry["description"])
        if entry.get("category"):
            fe.category(term=entry["category"])
        if entry.get("date"):
            fe.published(entry["date"])
            fe.updated(entry["date"])

    logger.info(f"Generated Atom feed with {len(entries)} entries")
    return fg


def save_atom_feed(fg, feed_name=FEED_NAME):
    """Write the feed to feeds/feed_<n>.xml in Atom format."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return output_file


def main(full=False):
    """Fetch all sections, merge with cache, and write the combined Atom feed."""
    new_entries = collect_entries()
    if new_entries is None:
        logger.error("No section could be fetched — skipping write to preserve the last good feed")
        return False
    if not new_entries:
        logger.warning("No entries parsed — skipping write to avoid an empty feed")
        return False

    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cached = deserialize_entries(load_cache(FEED_NAME).get("entries", []), date_field="date")

    # Dedupe by content URL across runs; cached items keep their original
    # first-seen date so only genuinely new pieces surface as fresh entries.
    merged = merge_entries(new_entries, cached, id_field="link", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")

    # sort_posts_for_feed is ascending (feedgen reverses on write), so keep the
    # tail to retain the most recent pieces.
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]

    save_cache(FEED_NAME, merged)
    save_atom_feed(generate_atom_feed(merged))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the RA (Resident Advisor) magazine Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
