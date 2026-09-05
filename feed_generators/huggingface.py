"""Shared Hugging Face HTML adapters for standalone Feedseek feeds."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

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

_POST_LINK_RE = re.compile(r"^/posts/[^/]+/\d+$")
_PAPER_LINK_RE = re.compile(r"^/papers/[^/?#]+$")
_PAPER_DATE_RE = re.compile(r"\b([A-Z][a-z]{2} \d{1,2}, \d{4})\b")


def _clean(text: str, limit: int = DESC_LIMIT) -> str:
    return sanitize_xml(" ".join((text or "").split()))[:limit]


def parse_posts(html: str, known_links=()) -> list[dict]:
    """Parse the server-rendered Hugging Face community posts listing."""
    soup = BeautifulSoup(html or "", "html.parser")
    known = set(known_links)
    entries = []
    seen = set()
    first_seen = datetime.now(timezone.utc)

    for article in soup.find_all("article", id=True):
        link_el = article.find("a", href=_POST_LINK_RE)
        if link_el is None:
            continue
        link = urljoin(BASE_URL, link_el["href"])
        if link in known or link in seen:
            continue

        content = article.select_one("div.break-words")
        parts = [
            _clean(part)
            for part in (content.stripped_strings if content else ())
            if _clean(part)
        ]
        path_parts = link_el["href"].strip("/").split("/")
        author = path_parts[1] if len(path_parts) > 1 else "Hugging Face user"
        title = parts[0] if parts else f"Post by {author}"
        description = _clean(" ".join(parts)) or title

        image_el = article.find(
            "img", src=re.compile(r"^https://cdn-uploads\.huggingface\.co/")
        )
        entries.append(
            {
                "title": title,
                "link": link,
                "date": first_seen,
                "description": description,
                "source": POSTS_SOURCE,
                "image": image_el.get("src") if image_el else None,
            }
        )
        seen.add(link)

    return entries


def parse_trending_papers(html: str, known_links=()) -> list[dict]:
    """Parse paper cards from the public Trending Papers page."""
    soup = BeautifulSoup(html or "", "html.parser")
    known = set(known_links)
    entries = []
    seen = set()

    for article in soup.find_all("article"):
        link_el = article.find("a", href=_PAPER_LINK_RE)
        if link_el is None:
            continue
        link = urljoin(BASE_URL, link_el["href"])
        if link in known or link in seen:
            continue

        heading = article.find("h3")
        if heading is None:
            continue
        title = _clean(heading.get_text(" ", strip=True))
        if not title:
            continue

        summary = article.find("p")
        description = _clean(summary.get_text(" ", strip=True)) if summary else title
        text = article.get_text(" ", strip=True)
        date_match = _PAPER_DATE_RE.search(text)
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
                "image": image_el.get("src") if image_el else None,
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
