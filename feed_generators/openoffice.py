"""ONLYOFFICE blog and API changelog combined as the OPENOFFICE feed."""

from __future__ import annotations

import argparse
import json
import sys

import multi_rss
import requests
from bs4 import BeautifulSoup
from utils import sanitize_xml

FEED_NAME = "openoffice"
FEED_TITLE = "OPENOFFICE"
BLOG_URL = "https://www.onlyoffice.com/blog"
BLOG_API_URL = "https://www.onlyoffice.com/blog/api/load-more-posts"
CHANGELOG_URL = "https://api.onlyoffice.com/changelog/"
CHANGELOG_RSS = "https://api.onlyoffice.com/changelog/rss.xml"
MAX_ENTRIES = 220
MAX_BLOG_PAGES = 20
BLOG_ENTRY_CAP = 120

SOURCES = (("ONLYOFFICE API Changelog", CHANGELOG_RSS, 100),)
PER_SOURCE_CAP = {
    "ONLYOFFICE Blog": BLOG_ENTRY_CAP,
    "ONLYOFFICE API Changelog": 100,
}

_POST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Content-Type": "text/plain;charset=UTF-8",
    "Origin": "https://www.onlyoffice.com",
    "Referer": BLOG_URL,
}


def doc_sources():
    """Return the user-facing ONLYOFFICE surfaces represented by this feed."""
    return [
        ("ONLYOFFICE Blog", BLOG_URL),
        ("ONLYOFFICE API Changelog", CHANGELOG_URL),
    ]


def _blog_link(uri: object) -> str | None:
    if not isinstance(uri, str) or not uri.startswith("/"):
        return None
    path = uri.rstrip("/")
    return f"{BLOG_URL}{path}" if path else None


def _blog_image(node: dict) -> str | None:
    featured = node.get("featuredImage")
    if isinstance(featured, dict):
        image_node = featured.get("node")
        if isinstance(image_node, dict):
            source = image_node.get("sourceUrl")
            if isinstance(source, str) and source.strip():
                return source.strip()
    fallback = node.get("firstImgPost")
    return fallback.strip() if isinstance(fallback, str) and fallback.strip() else None


def _blog_entry(node: object) -> dict | None:
    if not isinstance(node, dict):
        return None
    title = sanitize_xml(str(node.get("title") or "").strip()).strip()
    link = _blog_link(node.get("uri"))
    date = multi_rss.parse_date(node.get("date"))
    if not title or link is None or date is None:
        return None
    author = node.get("author")
    author_name = ""
    if isinstance(author, dict) and isinstance(author.get("node"), dict):
        raw_name = author["node"].get("name")
        if isinstance(raw_name, str):
            author_name = sanitize_xml(raw_name.strip()).strip()
    description = f"{title} — by {author_name}" if author_name else title
    return {
        "title": title[:300],
        "link": link,
        "date": date,
        "description": description[:2000],
        "source": "ONLYOFFICE Blog",
        "image": _blog_image(node),
    }


def _posts_payload(value: object) -> tuple[list[dict], bool, str | None] | None:
    if not isinstance(value, dict) or not isinstance(value.get("edges"), list):
        return None
    page_info = value.get("pageInfo")
    if not isinstance(page_info, dict):
        return None
    has_next = page_info.get("hasNextPage")
    if not isinstance(has_next, bool):
        return None
    cursor = page_info.get("endCursor")
    if has_next and (not isinstance(cursor, str) or not cursor):
        return None
    entries = [
        entry
        for edge in value["edges"]
        if isinstance(edge, dict)
        and (entry := _blog_entry(edge.get("node"))) is not None
    ]
    return entries, has_next, cursor if isinstance(cursor, str) and cursor else None


def parse_blog_page(html: str) -> tuple[list[dict], bool, str | None] | None:
    """Parse the blog's server-rendered Next.js payload."""
    script = BeautifulSoup(html, "html.parser").find("script", id="__NEXT_DATA__")
    if script is None or not script.string:
        return None
    try:
        payload = json.loads(script.string)
        posts = payload["props"]["pageProps"]["allPosts"]
    except json.JSONDecodeError, KeyError, TypeError:
        return None
    return _posts_payload(posts)


def _fetch_more_posts(cursor: str) -> tuple[list[dict], bool, str | None] | None:
    body = {
        "isInThePressPage": False,
        "isSearchPage": False,
        "isAuthorPage": False,
        "isTagPage": False,
        "isCategoryPage": False,
        "locale": "en",
        "endCursor": cursor,
    }
    try:
        response = requests.post(
            BLOG_API_URL,
            data=json.dumps(body, separators=(",", ":")),
            headers=_POST_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException, ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return _posts_payload(payload.get("data"))


def _append_fresh(
    entries: list[dict], known_links: set[str], seen: set[str], collected: list[dict]
) -> bool:
    for entry in entries:
        link = entry["link"]
        if link in known_links:
            return True
        if link not in seen:
            seen.add(link)
            collected.append(entry)
    return False


def collect_onlyoffice_blog(known_links: set[str]) -> list[dict]:
    """Collect current blog posts, paging only when cached history is deeper."""
    html = multi_rss.get_html(BLOG_URL)
    parsed = parse_blog_page(html) if html else None
    if parsed is None:
        multi_rss.logger.warning("[ONLYOFFICE Blog] structured payload unavailable")
        return []

    entries, has_next, cursor = parsed
    collected: list[dict] = []
    seen: set[str] = set()
    reached_known = _append_fresh(entries, known_links, seen, collected)
    pages = 1

    while (
        has_next
        and cursor
        and not reached_known
        and pages < MAX_BLOG_PAGES
        and len(collected) < BLOG_ENTRY_CAP
    ):
        parsed = _fetch_more_posts(cursor)
        if parsed is None:
            multi_rss.logger.warning(
                "[ONLYOFFICE Blog] load-more page unavailable; discarding partial batch"
            )
            return []
        entries, has_next, cursor = parsed
        pages += 1
        reached_known = _append_fresh(entries, known_links, seen, collected)

    if len(collected) > BLOG_ENTRY_CAP:
        collected = collected[:BLOG_ENTRY_CAP]
    if has_next and not reached_known and pages >= MAX_BLOG_PAGES:
        multi_rss.logger.warning(
            "[ONLYOFFICE Blog] pagination reached the %d-page safety cap",
            MAX_BLOG_PAGES,
        )
    multi_rss.logger.info(
        "[ONLYOFFICE Blog] collected %d fresh entries across %d page(s)",
        len(collected),
        pages,
    )
    return collected


def main(full: bool = False) -> bool:
    """Generate the combined OPENOFFICE Atom feed."""
    return multi_rss.run(
        feed_name=FEED_NAME,
        title=FEED_TITLE,
        subtitle="ONLYOFFICE Blog and API changelog in one feed.",
        blog_url=BLOG_URL,
        author="ONLYOFFICE",
        sources=SOURCES,
        extra_scrapers=(collect_onlyoffice_blog,),
        max_entries=MAX_ENTRIES,
        per_source_cap=PER_SOURCE_CAP,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the OPENOFFICE Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
