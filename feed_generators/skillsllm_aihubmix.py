"""AIHubMix source adapters for the SkillsLLM aggregate."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from utils import sanitize_xml, stable_fallback_date

logger = logging.getLogger(__name__)

AIHUBMIX_BLOG_URL = "https://aihubmix.com/blog/pl"
AIHUBMIX_DOCS_BLOG_URL = "https://docs.aihubmix.com/en/blogs"
AIHUBMIX_CHANGELOG_URL = "https://docs.aihubmix.com/en/update/News"
AIHUBMIX_BLOG_MAX = 40
AIHUBMIX_SOURCE = {
    "label": "AIHubMix Blog (PL)",
    "title_suffixes": (" | AIHubMix Blog", " | AIHubMix"),
    "category": lambda _loc: "aihubmix",
}
AIHUBMIX_DOCS_SOURCE = {
    "label": "AIHubMix Docs Blog (EN)",
    "category": "aihubmix-docs",
}
_CHANGELOG_YEAR_RE = re.compile(r"^20\d{2}$")
_CHANGELOG_DAY_RE = re.compile(r"^(?P<month>[A-Z][a-z]+)\s+(?P<day>\d{1,2})$")
_LAST_UPDATED_RE = re.compile(r"\bLast updated:\s*(20\d{2}-\d{2}-\d{2})\b")


def _discover_links(html: str, base_url: str) -> list[str]:
    """Return unique article URLs below one listing path."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    allowed_prefix = base_url.rstrip("/") + "/"
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].split("#", 1)[0].split("?", 1)[0]
        link = urljoin(allowed_prefix, href).rstrip("/")
        if not link.startswith(allowed_prefix) or "/tag/" in link or link in seen:
            continue
        seen.add(link)
        links.append(link)
    return links[:AIHUBMIX_BLOG_MAX]


def discover_aihubmix_links(html: str) -> list[str]:
    """Return unique Polish AIHubMix article URLs from the main blog listing."""
    return _discover_links(html, AIHUBMIX_BLOG_URL)


def discover_aihubmix_docs_links(html: str) -> list[str]:
    """Return unique English AIHubMix docs-blog article URLs."""
    return _discover_links(html, AIHUBMIX_DOCS_BLOG_URL)


def _docs_detail(link: str, fetch_url) -> dict | None:
    """Fetch one Mintlify blog page, preserving its visible Last updated date."""
    html = fetch_url(link)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    title = sanitize_xml(heading.get_text(" ", strip=True)) if heading else ""
    if not title:
        title_tag = soup.find("title")
        title = sanitize_xml(title_tag.get_text(" ", strip=True)) if title_tag else ""
        title = title.removesuffix(" - AIHubMix").strip()
    if not title:
        return None

    desc = soup.find("meta", attrs={"name": "description"})
    description = (
        sanitize_xml(desc["content"].strip())
        if desc and desc.get("content")
        else title
    )
    date_match = _LAST_UPDATED_RE.search(soup.get_text(" ", strip=True))
    date = (
        datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if date_match
        else stable_fallback_date(link)
    )
    image_tag = soup.find("meta", attrs={"property": "og:image"}) or soup.find(
        "meta", attrs={"name": "twitter:image"}
    )
    image = image_tag["content"].strip() if image_tag and image_tag.get("content") else None
    return {
        "title": title,
        "link": link,
        "date": date,
        "description": description,
        "source": AIHUBMIX_DOCS_SOURCE["label"],
        "category": AIHUBMIX_DOCS_SOURCE["category"],
        "image": image,
    }


def _collect_discovered(links, known_links, ledger, label, detail_fetcher) -> list[dict]:
    """Fetch discovered links while isolating and recording per-page failures."""
    if not links:
        return []
    ledger.listed(label)
    entries = []
    for link in links:
        if link in known_links or ledger.exhausted(label, link):
            continue
        try:
            entry = detail_fetcher(link)
            if entry:
                entries.append(entry)
            else:
                ledger.failed(label, link)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            ledger.failed(label, link)
            logger.warning("[%s] skipping %s: %s", label, link, exc)
    return entries


def _changelog_entry(year: str, day_label: str, chunks: list[str], known_links) -> dict | None:
    """Build one stable changelog entry from a year, month/day label, and body."""
    try:
        date = datetime.strptime(f"{year} {day_label}", "%Y %B %d").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None

    link = f"{AIHUBMIX_CHANGELOG_URL}#{date:%Y-%m-%d}"
    if link in known_links:
        return None
    description = sanitize_xml(" ".join(chunks)[:700])
    display_date = f"{date.strftime('%B')} {date.day}, {date.year}"
    title = f"AIHubMix updates — {display_date}"
    return {
        "title": title,
        "link": link,
        "date": date,
        "description": description or title,
        "source": "AIHubMix Changelog",
        "category": "aihubmix-changelog",
    }


def parse_aihubmix_changelog(html: str, known_links=None) -> list[dict]:
    """Turn Mintlify's separate year and month/day blocks into feed entries."""
    known_links = known_links or set()
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup
    entries: list[dict] = []
    current_year: str | None = None
    current_day: str | None = None
    chunks: list[str] = []

    def flush_current() -> None:
        if current_year is None or current_day is None:
            return
        entry = _changelog_entry(current_year, current_day, chunks, known_links)
        if entry:
            entries.append(entry)

    for raw_text in root.stripped_strings:
        text = " ".join(raw_text.split())
        if _CHANGELOG_YEAR_RE.fullmatch(text):
            flush_current()
            current_year = text
            current_day = None
            chunks = []
            continue
        if _CHANGELOG_DAY_RE.fullmatch(text) and current_year is not None:
            flush_current()
            current_day = text
            chunks = []
            continue
        if current_day is not None:
            chunks.append(text)

    flush_current()
    entries.sort(key=lambda entry: entry["date"], reverse=True)
    return entries[:80]


def collect_aihubmix_blog(known_links, ledger, fetch_url, fetch_detail):
    """Collect the main blog, docs blog, and changelog as one AIHubMix source family."""
    entries: list[dict] = []

    main_html = fetch_url(AIHUBMIX_BLOG_URL)
    if main_html is not None:
        links = discover_aihubmix_links(main_html)
        entries.extend(
            _collect_discovered(
                links,
                known_links,
                ledger,
                AIHUBMIX_SOURCE["label"],
                lambda link: fetch_detail(link, None, AIHUBMIX_SOURCE),
            )
        )

    docs_html = fetch_url(AIHUBMIX_DOCS_BLOG_URL)
    if docs_html is not None:
        links = discover_aihubmix_docs_links(docs_html)
        entries.extend(
            _collect_discovered(
                links,
                known_links,
                ledger,
                AIHUBMIX_DOCS_SOURCE["label"],
                lambda link: _docs_detail(link, fetch_url),
            )
        )

    changelog_html = fetch_url(AIHUBMIX_CHANGELOG_URL)
    if changelog_html is not None:
        entries.extend(parse_aihubmix_changelog(changelog_html, known_links))

    return entries
