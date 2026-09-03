"""Tencent Newsroom + Cloud Blogs + Tencent Music combined Atom feed.

Tencent's corporate newsroom and Tencent Music expose reliable native RSS feeds,
while Tencent Cloud server-renders its blog listing with a ``__ASYNC_DATA__``
JSON payload. Keep the native feeds native and reuse the existing structured
Cloud collector instead of scraping card CSS.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import multi_rss
from bs4 import BeautifulSoup
from utils import sanitize_xml, stable_fallback_date

FEED_NAME = "tencent"
FEED_TITLE = "Tencent"
NEWSROOM_URL = "https://www.tencent.com/newsroom/"
_NEWSROOM_RSS_URL = "https://www.tencent.com/newsroom/all-news/feed/"
BLOGS_URL = "https://www.tencentcloud.com/dynamic/blogs/800"
_BLOGS_FETCH_URL = (
    "https://www.tencentcloud.com/dynamic/blogs/800?lang=en&pg=&from_qcintl=topnav"
)
MUSIC_RSS_URL = "https://ir.tencentmusic.com/Press-Releases?pagetemplate=rss"
BLOG_URL = NEWSROOM_URL
MAX_ENTRIES = 300
PER_SOURCE_CAP = 120
PAGE_SIZE = 12
MAX_PAGES = 60
CLOUD_LABEL = "Tencent Cloud Blogs"
CURRENT_SOURCE_LABELS = {
    "Tencent Newsroom",
    CLOUD_LABEL,
    "Tencent Music Press Releases",
}
_NATIVE_SOURCES = (
    ("Tencent Newsroom", _NEWSROOM_RSS_URL, 100),
    ("Tencent Music Press Releases", MUSIC_RSS_URL, 100),
)

_ASYNC_DATA_RE = re.compile(
    r"window\['__ASYNC_DATA__'\]\s*=\s*(\[.*?\])\s*;?\s*</script>", re.DOTALL
)


def doc_sources():
    """Return the three Tencent surfaces requested for the combined feed."""
    return [
        ("Tencent Newsroom", NEWSROOM_URL),
        (CLOUD_LABEL, BLOGS_URL),
        ("Tencent Music Press Releases", MUSIC_RSS_URL),
    ]


def _page_url(url: str, page: int) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["pg"] = str(page)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _express_data(payload) -> dict | None:
    if not isinstance(payload, list):
        return None
    for root in payload:
        if not isinstance(root, dict):
            continue
        for bucket in root.values():
            if not isinstance(bucket, list):
                continue
            for item in bucket:
                if not isinstance(item, dict):
                    continue
                express = item.get("expressList")
                if not isinstance(express, dict):
                    continue
                data = express.get("data")
                if isinstance(data, dict) and isinstance(data.get("item"), list):
                    return data
    return None


def _listing_total(data: dict) -> int | None:
    raw_total = data.get("num")
    if isinstance(raw_total, bool):
        return None
    if isinstance(raw_total, int):
        total = raw_total
    elif isinstance(raw_total, str) and re.fullmatch(r"[+-]?\d+", raw_total.strip()):
        total = int(raw_total.strip())
    else:
        return None
    return total if total >= 0 else None


def _listing_entry(item, *, label: str) -> dict | None:
    if not isinstance(item, dict) or str(item.get("cateId")) != "800":
        return None
    news_id = str(item.get("newsId") or "").strip()
    title = sanitize_xml(str(item.get("title") or "").strip()).strip()
    if not news_id or not title:
        return None
    link = f"https://www.tencentcloud.com/dynamic/blogs/sample-article/{news_id}"
    description_html = str(item.get("description") or "")
    description = sanitize_xml(
        BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True)
    ).strip()
    return {
        "title": title[:300],
        "link": link,
        "date": multi_rss.parse_date(item.get("newsTime"))
        or stable_fallback_date(link),
        "description": (description or title)[:2000],
        "source": label,
        "image": str(item.get("thumbnail") or "").strip() or None,
    }


def parse_listing(
    html: str, *, label: str = CLOUD_LABEL
) -> tuple[list[dict], int] | None:
    match = _ASYNC_DATA_RE.search(html)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    data = _express_data(payload)
    if data is None or (total := _listing_total(data)) is None:
        return None
    entries = [
        entry for item in data["item"] if (entry := _listing_entry(item, label=label))
    ]
    if total < len(entries):
        return None
    return entries, total


def _append_fresh_entries(page_entries, *, known_links, seen, collected) -> bool:
    reached_known = False
    for entry in page_entries:
        link = entry["link"]
        if link in known_links:
            reached_known = True
            continue
        if link in seen:
            continue
        seen.add(link)
        collected.append(entry)
    return reached_known


def _collect_cloud(known_links: set[str]) -> list[dict]:
    collected: list[dict] = []
    seen: set[str] = set()
    page = 1
    advertised_total: int | None = None
    total_pages: int | None = None
    reached_known = False

    while page <= MAX_PAGES:
        html = multi_rss.get_html(_page_url(_BLOGS_FETCH_URL, page))
        if not html:
            multi_rss.logger.warning(
                "[%s] page %d unavailable; discarding partial batch", CLOUD_LABEL, page
            )
            return []
        parsed = parse_listing(html)
        if parsed is None:
            multi_rss.logger.warning(
                "[%s] page %d payload changed; discarding partial batch",
                CLOUD_LABEL,
                page,
            )
            return []
        page_entries, total = parsed
        if total_pages is None:
            advertised_total = total
            total_pages = max(1, math.ceil(total / PAGE_SIZE)) if total else 1
        reached_known = _append_fresh_entries(
            page_entries, known_links=known_links, seen=seen, collected=collected
        )
        if not page_entries:
            if advertised_total and advertised_total > 0:
                multi_rss.logger.warning(
                    "[%s] empty page %d before advertised end", CLOUD_LABEL, page
                )
                return []
            break
        if reached_known or page >= total_pages:
            break
        page += 1

    if total_pages is not None and page < total_pages and not reached_known:
        multi_rss.logger.warning("[%s] pagination exceeded safety cap", CLOUD_LABEL)
        return []
    multi_rss.logger.info(
        "[%s] collected %d fresh entries across %d page(s)",
        CLOUD_LABEL,
        len(collected),
        page,
    )
    return collected


def _keep_current_source(entry: dict) -> bool:
    """Drop cached items from the retired Tencent Cloud Press Center source."""
    return entry.get("source") in CURRENT_SOURCE_LABELS


def main(full: bool = False) -> bool:
    return multi_rss.run(
        feed_name=FEED_NAME,
        title=FEED_TITLE,
        subtitle="Tencent Newsroom, Tencent Cloud Blogs, and Tencent Music press releases in one feed.",
        blog_url=BLOG_URL,
        author="Tencent",
        sources=_NATIVE_SOURCES,
        extra_scrapers=(_collect_cloud,),
        max_entries=MAX_ENTRIES,
        per_source_cap=PER_SOURCE_CAP,
        cache_filter=_keep_current_source,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the combined Tencent Atom feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
