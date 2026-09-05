"""Shared Hugging Face HTML adapters for standalone Feedseek feeds."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date
from utils import sanitize_xml, setup_logging

logger = setup_logging()

BASE_URL = "https://huggingface.co"
POSTS_URL = f"{BASE_URL}/posts"
TRENDING_PAPERS_URL = f"{BASE_URL}/papers/trending"
POSTS_SOURCE = "Hugging Face Posts"
TRENDING_SOURCE = "Hugging Face Trending Papers"
DESC_LIMIT = 700

_POST_LINK_RE = re.compile(r"^/posts/[^/]+/\d+(?:[/?#]|$)")
_PAPER_LINK_RE = re.compile(r"^/papers/[^/?#]+(?:[/?#]|$)")
_PAPER_DATE_RE = re.compile(r"\b([A-Z][a-z]{2} \d{1,2}, \d{4})\b")


def _clean(text: str, limit: int = DESC_LIMIT) -> str:
    return sanitize_xml(" ".join((text or "").split()))[:limit]


def _canonical_link(href: object) -> str:
    """Return an absolute Hugging Face URL without query, fragment, or trailing slash."""
    raw = str(href or "").strip()
    if not raw:
        return ""
    parts = urlsplit(urljoin(BASE_URL, raw))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _structured_date(article) -> object | None:
    """Prefer machine-readable dates exposed by the source card."""
    time_el = article.find("time")
    if time_el is not None:
        raw = str(time_el.get("datetime") or time_el.get_text(" ", strip=True) or "")
        parsed = parse_date(raw)
        if parsed is not None:
            return parsed
    return None


def parse_posts(html: str, known_links=()) -> list[dict]:
    """Parse the server-rendered Hugging Face community posts listing."""
    soup = BeautifulSoup(html or "", "html.parser")
    known = {_canonical_link(link) for link in known_links}
    entries = []
    seen = set()

    for article in soup.find_all("article", id=True):
        link_el = article.find("a", href=_POST_LINK_RE)
        if link_el is None:
            continue
        raw_href = str(link_el.get("href") or "")
        link = _canonical_link(raw_href)
        if not link or link in known or link in seen:
            continue

        content = article.select_one("div.break-words")
        parts = [_clean(part) for part in (content.stripped_strings if content else ())]
        parts = [part for part in parts if part]
        path_parts = urlsplit(raw_href).path.strip("/").split("/")
        author = path_parts[1] if len(path_parts) > 1 else "Hugging Face user"
        title = parts[0] if parts else f"Post by {author}"
        description = _clean(" ".join(parts)) or title
        published = _structured_date(article)

        image_el = article.find(
            "img", src=re.compile(r"^https://cdn-uploads\.huggingface\.co/")
        )
        entries.append(
            {
                "title": title,
                "link": link,
                "date": published,
                "description": description,
                "source": POSTS_SOURCE,
                "image": str(image_el.get("src")) if image_el and image_el.get("src") else None,
            }
        )
        seen.add(link)

    return entries


def parse_trending_papers(html: str, known_links=()) -> list[dict]:
    """Parse paper cards from the public Trending Papers page."""
    soup = BeautifulSoup(html or "", "html.parser")
    known = {_canonical_link(link) for link in known_links}
    entries = []
    seen = set()

    for article in soup.find_all("article"):
        link_el = article.find("a", href=_PAPER_LINK_RE)
        if link_el is None:
            continue
        link = _canonical_link(link_el.get("href"))
        if not link or link in known or link in seen:
            continue

        heading = article.find("h3")
        if heading is None:
            continue
        title = _clean(heading.get_text(" ", strip=True))
        if not title:
            continue

        summary = article.find("p")
        description = _clean(summary.get_text(" ", strip=True)) if summary else title
        published = _structured_date(article)
        if published is None:
            date_match = _PAPER_DATE_RE.search(article.get_text(" ", strip=True))
            published = parse_date(date_match.group(1)) if date_match else None
        image_el = article.find(
            "img", src=re.compile(r"cdn-thumbnails\.huggingface\.co/.*/papers/")
        )
        entries.append(
            {
                "title": title,
                "link": link,
                "date": published,
                "description": description or title,
                "source": TRENDING_SOURCE,
                "image": str(image_el.get("src")) if image_el and image_el.get("src") else None,
            }
        )
        seen.add(link)

    return entries


def collect_posts(known_links) -> list[dict]:
    html = get_html(POSTS_URL)
    if not html:
        return []
    entries = parse_posts(html, known_links)
    if not entries:
        logger.warning("[%s] no new post cards matched", POSTS_SOURCE)
    return entries


def collect_trending_papers(known_links) -> list[dict]:
    html = get_html(TRENDING_PAPERS_URL)
    if not html:
        return []
    entries = parse_trending_papers(html, known_links)
    if not entries:
        logger.warning("[%s] no new paper cards matched", TRENDING_SOURCE)
    return entries
