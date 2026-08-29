"""Tencent Cloud Blogs + Press Center combined Atom feed.

Tencent Cloud server-renders each listing page with a ``__ASYNC_DATA__`` JSON
payload. Using that structured payload is more stable than scraping card CSS,
and the normal ``pg`` query parameter lets the collector paginate until it
reaches already cached history.
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
BLOGS_URL = "https://www.tencentcloud.com/dynamic/blogs/800?lang=en&pg=&from_qcintl=topnav"
PRESS_URL = "https://www.tencentcloud.com/dynamic/400?lang=en&pg=&from_qcintl=topnav"
BLOG_URL = BLOGS_URL
MAX_ENTRIES = 300
PER_SOURCE_CAP = 180
PAGE_SIZE = 12
MAX_PAGES = 60

SOURCES = (
    ("Tencent Cloud Blogs", BLOGS_URL, "800"),
    ("Tencent Cloud Press Center", PRESS_URL, "400"),
)

_ASYNC_DATA_RE = re.compile(
    r"window\['__ASYNC_DATA__'\]\s*=\s*(\[.*?\])\s*;?\s*</script>", re.DOTALL
)


def doc_sources():
    """Return the two Tencent Cloud surfaces combined by this feed."""
    return [(label, url) for label, url, _category in SOURCES]


def _page_url(url: str, page: int) -> str:
    """Return *url* with Tencent's ``pg`` query parameter set to *page*."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["pg"] = str(page)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _express_data(payload) -> dict | None:
    """Locate the hashed ``expressList.data`` object in Tencent's async payload."""
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


def _detail_url(category: str, news_id: str) -> str:
    """Build the canonical Tencent Cloud detail URL for one listing record."""
    if category == "800":
        path = f"/dynamic/blogs/sample-article/{news_id}"
    else:
        path = f"/dynamic/news-details/{news_id}"
    return f"https://www.tencentcloud.com{path}"


def parse_listing(html: str, *, label: str, category: str) -> tuple[list[dict], int] | None:
    """Parse one Tencent listing page into entries and the total result count."""
    match = _ASYNC_DATA_RE.search(html)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    data = _express_data(payload)
    if data is None:
        return None

    raw_total = data.get("num")
    if raw_total is None:
        return None
    try:
        total = int(raw_total)
    except (TypeError, ValueError):
        return None

    entries: list[dict] = []
    for item in data["item"]:
        if not isinstance(item, dict) or str(item.get("cateId")) != category:
            continue
        news_id = str(item.get("newsId") or "").strip()
        title = sanitize_xml(str(item.get("title") or "").strip()).strip()
        if not news_id or not title:
            continue
        link = _detail_url(category, news_id)
        description_html = str(item.get("description") or "")
        description = sanitize_xml(
            BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True)
        ).strip()
        date = multi_rss.parse_date(item.get("newsTime")) or stable_fallback_date(link)
        image = str(item.get("thumbnail") or "").strip() or None
        entries.append(
            {
                "title": title[:300],
                "link": link,
                "date": date,
                "description": (description or title)[:2000],
                "source": label,
                "image": image,
            }
        )
    return entries, total


def _collect_source(
    *, label: str, url: str, category: str, known_links: set[str]
) -> list[dict]:
    """Collect one Tencent source until cached history or API exhaustion."""
    collected: list[dict] = []
    seen: set[str] = set()
    page = 1
    total_pages: int | None = None

    while page <= MAX_PAGES:
        html = multi_rss.get_html(_page_url(url, page))
        if not html:
            multi_rss.logger.warning("[%s] page %d unavailable; discarding partial batch", label, page)
            return []
        parsed = parse_listing(html, label=label, category=category)
        if parsed is None:
            multi_rss.logger.warning("[%s] page %d payload changed; discarding partial batch", label, page)
            return []
        page_entries, total = parsed
        if total_pages is None:
            total_pages = max(1, math.ceil(total / PAGE_SIZE)) if total else 1

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

        if not page_entries:
            if total > 0:
                multi_rss.logger.warning(
                    "[%s] empty page %d while source still advertises entries; discarding partial batch",
                    label,
                    page,
                )
                return []
            break
        if reached_known or page >= total_pages:
            break
        page += 1

    if total_pages is not None and page < total_pages and not reached_known:
        multi_rss.logger.warning(
            "[%s] pagination exceeded safety cap before history boundary; discarding partial batch",
            label,
        )
        return []

    multi_rss.logger.info("[%s] collected %d fresh entries across %d page(s)", label, len(collected), page)
    return collected


def collect_tencent(known_links: set[str]) -> list[dict]:
    """Collect fresh Tencent Cloud blog and Press Center entries."""
    out: list[dict] = []
    seen = set(known_links)
    for label, url, category in SOURCES:
        entries = _collect_source(
            label=label,
            url=url,
            category=category,
            known_links=seen,
        )
        out.extend(entries)
        seen.update(entry["link"] for entry in entries)
    return out


def main(full: bool = False) -> bool:
    """Generate the combined Tencent Atom feed."""
    return multi_rss.run(
        feed_name=FEED_NAME,
        title=FEED_TITLE,
        subtitle="Tencent Cloud Blogs and Press Center in one feed.",
        blog_url=BLOG_URL,
        author="Tencent Cloud",
        extra_scrapers=(collect_tencent,),
        max_entries=MAX_ENTRIES,
        per_source_cap=PER_SOURCE_CAP,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Tencent Cloud Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
