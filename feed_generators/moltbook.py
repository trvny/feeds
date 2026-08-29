"""Moltbook feed generator backed by the public posts API.

Moltbook is a social network for AI agents. Its public JSON endpoint exposes
post titles, bodies, authors, submolts, scores, comment counts and timestamps,
so this generator can avoid brittle HTML scraping entirely. Cursor pagination
scans the complete publishable window before the shared cache is advanced.
"""

from __future__ import annotations

import argparse
import json
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


def _usable_post(post) -> bool:
    """Return whether a raw API post is eligible for the published feed."""
    return bool(
        isinstance(post, dict)
        and not post.get("is_deleted")
        and not post.get("is_spam")
        and _post_link(post)
        and str(post.get("title") or "").strip()
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
                "title": sanitize_xml(str(post["title"]).strip()),
                "link": link,
                "date": _parse_date(post.get("created_at")),
                "description": _post_description(post),
                "source": SOURCE_NAME,
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
    """Fetch every page needed to cover the 250-item publication window.

    Moltbook is deliberately one Feedseek source: submolts remain visible in
    descriptions but do not participate in the shared round-robin allocator.
    Therefore the publishable set is exactly the newest ``MAX_ENTRIES`` distinct
    usable global posts. Scanning that whole window both captures bursts larger
    than a page and observes moderation for every cached item that can remain
    visible. A failed cursor page discards the whole batch so cache state never
    advances across an unobserved gap.
    """
    entries: list[dict] = []
    moderated_links: set[str] = set()
    seen_entry_links: set[str] = set()
    usable_links_seen: set[str] = set()
    cursor: str | None = None

    while len(usable_links_seen) < MAX_ENTRIES:
        loaded = _load_page(cursor, fetch)
        if loaded is None:
            return [], set(), False
        posts, cursor, has_more = loaded
        if not posts:
            if has_more:
                logger.warning("[Moltbook] empty page advertised a continuation")
                return [], set(), False
            break

        page_entries, page_moderated, page_usable_links = _scan_page(posts, known_links)
        _append_unique(entries, page_entries, seen_entry_links)
        moderated_links.update(page_moderated)
        usable_links_seen.update(page_usable_links)
        if not has_more:
            break

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
            "Newest non-spam posts from Moltbook, the social network for AI agents, "
            "with submolt labels preserved in each entry."
        ),
        blog_url=SITE_URL,
        author="Moltbook agents",
        extra_scrapers=(scrape_prefetched,),
        max_entries=MAX_ENTRIES,
        image_backfill=False,
        cache_filter=keep_cached,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Moltbook Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
