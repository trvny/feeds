"""Moltbook feed generator backed by the public posts API.

Moltbook is a social network for AI agents. Its public JSON endpoint exposes
post titles, bodies, authors, submolts, scores, comment counts and timestamps,
so this generator can avoid brittle HTML scraping entirely. Cursor pagination
scans the complete publishable window before the shared cache is advanced.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from urllib.parse import quote

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "moltbook"
SOURCE_NAME = "Moltbook"
SITE_URL = "https://www.moltbook.com/"
MOLTBOOK_PAGE_SIZE = 50
MOLTBOOK_API_URL = (
    f"https://www.moltbook.com/api/v1/posts?sort=new&limit={MOLTBOOK_PAGE_SIZE}"
)
MAX_ENTRIES = 250
CANDIDATE_LIMIT = 1000
PER_SUBMOLT_CAP = {"": 20}
ALLOCATION_FIELD = "submolt"


def doc_sources():
    """Expose the concrete Moltbook endpoint used by the generator."""
    return [("Moltbook Posts API", MOLTBOOK_API_URL)]


def _parse_date(value) -> datetime | None:
    """Parse a Moltbook timestamp through Feedseek's shared safe date parser."""
    return parse_date(value) if value else None


def _post_link(post: dict) -> str:
    """Return the canonical Moltbook web URL for an API post."""
    post_id = str(post.get("id") or "").strip()
    return f"{SITE_URL}post/{post_id}" if post_id else ""


def _post_submolt(post: dict) -> str:
    """Return the post's submolt as a readable description label."""
    submolt = post.get("submolt")
    if isinstance(submolt, dict):
        name = submolt.get("name") or submolt.get("display_name")
    else:
        name = submolt
    return sanitize_xml(f"m/{str(name or 'unknown').strip()}")


def _restore_submolt(entry: dict) -> dict:
    """Backfill the allocation bucket on cache entries written before caps."""
    if entry.get(ALLOCATION_FIELD):
        return entry
    migrated = entry.copy()
    match = re.search(r"\bm/[\w.-]+", str(entry.get("description") or ""))
    migrated[ALLOCATION_FIELD] = sanitize_xml(match.group(0)) if match else "m/unknown"
    return migrated


def _post_description(post: dict) -> str:
    """Build a compact description with author, submolt and engagement."""
    author = post.get("author")
    author_name = author.get("name") if isinstance(author, dict) else author
    author_name = sanitize_xml(str(author_name or "unknown agent").strip())
    score = post.get("score", post.get("upvotes", 0))
    comments = post.get("comment_count", 0)
    header = (
        f"{author_name} · {_post_submolt(post)} · score {score} · {comments} comments"
    )

    body = sanitize_xml(" ".join(str(post.get("content") or "").split()))[:1400]
    external = str(post.get("url") or "").strip()
    parts = [header]
    if body:
        parts.append(body)
    if external:
        parts.append(f"Link: {external}")
    return "\n\n".join(parts)


def _post_title(post: dict) -> str:
    """Return a feed-safe title, or an empty string when sanitization removes it."""
    return sanitize_xml(str(post.get("title") or "").strip()).strip()


def _usable_post(post) -> bool:
    """Return whether a raw API post is eligible for the published feed."""
    return bool(
        isinstance(post, dict)
        and not post.get("is_deleted")
        and not post.get("is_spam")
        and _post_link(post)
        and _post_title(post)
    )


def parse_posts(payload: dict, known_links: set[str]) -> list[dict]:
    """Normalize Moltbook API posts into Feedseek entry dictionaries."""
    if not isinstance(payload, dict):
        return []
    posts = payload.get("posts")
    if not isinstance(posts, list):
        return []

    entries: list[dict] = []
    for post in posts:
        if not _usable_post(post):
            continue
        link = _post_link(post)
        if link in known_links:
            continue
        entries.append(
            {
                "title": _post_title(post),
                "link": link,
                "date": _parse_date(post.get("created_at")),
                "description": _post_description(post),
                "source": SOURCE_NAME,
                ALLOCATION_FIELD: _post_submolt(post),
            }
        )
    return entries


def _decode_page(raw: str | None, url: str) -> dict | None:
    """Decode one posts API page, isolating malformed or failed responses."""
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("[Moltbook] invalid API JSON from %s: %s", url, exc)
        return None
    if not isinstance(payload, dict) or not payload.get("success", True):
        logger.warning("[Moltbook] API returned an unusable page for %s", url)
        return None
    return payload


def _page_url(cursor: str | None) -> str:
    """Build a cursor-safe URL for one Moltbook posts page."""
    if not cursor:
        return MOLTBOOK_API_URL
    return f"{MOLTBOOK_API_URL}&cursor={quote(cursor, safe='')}"


def _load_page(cursor: str | None, fetch) -> tuple[list, str | None, bool] | None:
    """Fetch and validate one cursor page, returning posts and continuation state."""
    url = _page_url(cursor)
    payload = _decode_page(fetch(url, retry_delay=2), url)
    if payload is None:
        return None
    posts = payload.get("posts")
    if not isinstance(posts, list):
        logger.warning("[Moltbook] API page has no posts list: %s", url)
        return None
    next_cursor = str(payload.get("next_cursor") or "").strip() or None
    has_more = bool(payload.get("has_more"))
    if has_more and not next_cursor:
        logger.warning("[Moltbook] continuation page omitted next_cursor: %s", url)
        return None
    return posts, next_cursor, has_more


def _scan_page(
    posts: list, known_links: set[str]
) -> tuple[list[dict], set[str], set[str]]:
    """Normalize one page and report moderated plus distinct usable links."""
    moderated: set[str] = set()
    usable_links: set[str] = set()
    for post in posts:
        if not isinstance(post, dict):
            continue
        link = _post_link(post)
        if link and (post.get("is_deleted") or post.get("is_spam")):
            moderated.add(link)
        if link and _usable_post(post):
            usable_links.add(link)
    return parse_posts({"posts": posts}, known_links), moderated, usable_links


def _append_unique(entries: list[dict], page_entries: list[dict], seen: set[str]) -> None:
    """Append page entries once even if an API page overlaps its neighbor."""
    for entry in page_entries:
        if entry["link"] in seen:
            continue
        seen.add(entry["link"])
        entries.append(entry)


def fetch_moltbook_pages(
    known_links: set[str], *, fetch=get_html
) -> tuple[list[dict], set[str], bool]:
    """Fetch the recent candidate window used for capped publication.

    Publication is balanced by submolt, but only inside the newest
    ``CANDIDATE_LIMIT`` usable global posts. Scanning that entire window keeps
    moderation checks aligned with every item eligible for publication while
    giving quieter submolts enough room to fill the 250-entry feed. A failed
    cursor page discards the whole batch so cache state never advances across an
    unobserved gap.
    """
    entries: list[dict] = []
    moderated_links: set[str] = set()
    seen_entry_links: set[str] = set()
    usable_links_seen: set[str] = set()
    seen_cursors: set[str] = set()
    cursor: str | None = None

    while len(usable_links_seen) < CANDIDATE_LIMIT:
        if cursor is not None:
            if cursor in seen_cursors:
                logger.warning("[Moltbook] repeated cursor detected: %s", cursor)
                return [], set(), False
            seen_cursors.add(cursor)

        loaded = _load_page(cursor, fetch)
        if loaded is None:
            return [], set(), False
        posts, next_cursor, has_more = loaded
        if not posts:
            if has_more:
                logger.warning("[Moltbook] empty page advertised a continuation")
                return [], set(), False
            break

        page_entries, page_moderated, page_usable_links = _scan_page(posts, known_links)
        _append_unique(entries, page_entries, seen_entry_links)
        moderated_links.update(page_moderated)
        usable_links_seen.update(page_usable_links)
        usable_links_seen.difference_update(moderated_links)
        if not has_more:
            break
        if next_cursor in seen_cursors:
            logger.warning("[Moltbook] cursor cycle detected: %s", next_cursor)
            return [], set(), False
        cursor = next_cursor

    logger.info(
        "[Moltbook] scanned %d distinct usable post(s), collected %d new, found %d moderated",
        len(usable_links_seen),
        len(entries),
        len(moderated_links & known_links),
    )
    return entries, moderated_links, True


def _fresh_unmoderated(
    entries: list[dict], known_links: set[str], moderated_links: set[str]
) -> list[dict]:
    """Exclude cached or newly moderated posts from a prefetched batch."""
    return [
        entry
        for entry in entries
        if entry["link"] not in known_links and entry["link"] not in moderated_links
    ]


def main(full: bool = False) -> bool:
    """Generate the Moltbook Atom feed."""
    fresh_entries, moderated_links, complete = fetch_moltbook_pages(set())
    if not complete:
        logger.warning("[Moltbook] incomplete pagination; preserving last good feed")
        return False

    def scrape_prefetched(known_links: set[str]) -> list[dict]:
        """Return prefetched entries that remain fresh and unmoderated."""
        return _fresh_unmoderated(fresh_entries, known_links, moderated_links)

    def keep_cached(entry: dict) -> bool:
        """Drop cached posts observed as deleted or spam in the publishable window."""
        return entry.get("link") not in moderated_links

    return run(
        feed_name=FEED_NAME,
        title="Moltbook",
        subtitle=(
            "Newest non-spam posts from Moltbook, balanced across submolts with "
            "at most 20 published entries from any one community."
        ),
        blog_url=SITE_URL,
        author="Moltbook agents",
        extra_scrapers=(scrape_prefetched,),
        max_entries=MAX_ENTRIES,
        per_source_cap=PER_SUBMOLT_CAP,
        allocation_field=ALLOCATION_FIELD,
        candidate_limit=CANDIDATE_LIMIT,
        image_backfill=False,
        cache_filter=keep_cached,
        cache_transform=_restore_submolt,
        dedupe_title_field=None,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Moltbook Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
