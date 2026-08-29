"""AIHubMix source adapters for the SkillsLLM aggregate."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from utils import sanitize_xml, stable_fallback_date

logger = logging.getLogger(__name__)

AIHUBMIX_BLOG_URL = "https://aihubmix.com/blog/pl"
AIHUBMIX_BLOG_MAX = 40
AIHUBMIX_SOURCE = {
    "label": "AIHubMix Blog (PL)",
    "url": AIHUBMIX_BLOG_URL,
    "title_suffixes": (" | AIHubMix Blog", " | AIHubMix"),
    "category": lambda _loc: "aihubmix",
}
AIHUBMIX_DOCS_SOURCE = {
    "label": "AIHubMix Docs Blog (EN)",
    "url": "https://docs.aihubmix.com/en/blogs",
    "category": "aihubmix-docs",
}
AIHUBMIX_CHANGELOG_SOURCE = {
    "label": "AIHubMix Changelog",
    "url": "https://docs.aihubmix.com/en/update/News",
    "category": "aihubmix-changelog",
}
AIHUBMIX_CHANGELOG_LABEL = AIHUBMIX_CHANGELOG_SOURCE["label"]
AIHUBMIX_DOC_SOURCES = tuple(
    (source["label"], source["url"])
    for source in (AIHUBMIX_SOURCE, AIHUBMIX_DOCS_SOURCE, AIHUBMIX_CHANGELOG_SOURCE)
)
_POLISH_MONTHS = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "października": 10,
    "listopada": 11,
    "grudnia": 12,
}
_POLISH_DATE_RE = re.compile(
    r"\b(?P<day>\d{1,2})\s+"
    r"(?P<month>stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|"
    r"września|października|listopada|grudnia)\s+"
    r"(?P<year>20\d{2})\b",
    re.IGNORECASE,
)
_CHANGELOG_YEAR_RE = re.compile(r"^20\d{2}$")
_CHANGELOG_DAY_RE = re.compile(r"^[A-Z][a-z]+\s+\d{1,2}$")
_LAST_UPDATED_RE = re.compile(r"\bLast updated:\s*(20\d{2}-\d{2}-\d{2})\b")


def _normalized_link(anchor, base_url: str) -> str | None:
    """Normalize one article anchor and reject links outside the listing path."""
    href = anchor["href"].split("#", 1)[0].split("?", 1)[0]
    allowed_prefix = base_url.rstrip("/") + "/"
    link = urljoin(allowed_prefix, href).rstrip("/")
    if not link.startswith(allowed_prefix) or "/tag/" in link:
        return None
    return link


def _discover_posts(
    html: str, base_url: str, date_finder=None
) -> list[tuple[str, datetime | None]]:
    """Return unique article URLs and optional dates below one listing path."""
    soup = BeautifulSoup(html, "html.parser")
    posts: dict[str, datetime | None] = {}
    for anchor in soup.find_all("a", href=True):
        link = _normalized_link(anchor, base_url)
        if not link:
            continue
        date = date_finder(anchor) if date_finder else None
        if link not in posts or posts[link] is None:
            posts[link] = date
    return list(posts.items())[:AIHUBMIX_BLOG_MAX]


def _polish_listing_date(anchor) -> datetime | None:
    """Find the publication date in the nearest AIHubMix blog-card ancestor."""
    node = anchor
    for _ in range(6):
        node = getattr(node, "parent", None)
        if node is None or getattr(node, "name", None) in {"main", "body", "html"}:
            break
        match = _POLISH_DATE_RE.search(" ".join(node.stripped_strings))
        if not match:
            continue
        month = _POLISH_MONTHS[match.group("month").lower()]
        try:
            return datetime(
                int(match.group("year")), month, int(match.group("day")), tzinfo=UTC
            )
        except ValueError:
            logger.warning(
                "[AIHubMix Blog (PL)] ignoring invalid listing date: %s",
                match.group(0),
            )
            return None
    return None


def discover_aihubmix_posts(html: str) -> list[tuple[str, datetime | None]]:
    """Return Polish blog links with listing publication dates when available."""
    return _discover_posts(html, AIHUBMIX_BLOG_URL, _polish_listing_date)


def discover_aihubmix_links(html: str) -> list[str]:
    """Return unique Polish AIHubMix article URLs from the main blog listing."""
    return [link for link, _date in discover_aihubmix_posts(html)]


def discover_aihubmix_docs_links(html: str) -> list[str]:
    """Return unique English AIHubMix docs-blog article URLs."""
    return [link for link, _date in _discover_posts(html, AIHUBMIX_DOCS_SOURCE["url"])]


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
        sanitize_xml(desc["content"].strip()) if desc and desc.get("content") else title
    )
    date_match = _LAST_UPDATED_RE.search(soup.get_text(" ", strip=True))
    date = (
        datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
        if date_match
        else stable_fallback_date(link)
    )
    image_tag = soup.find("meta", attrs={"property": "og:image"}) or soup.find(
        "meta", attrs={"name": "twitter:image"}
    )
    image = (
        image_tag["content"].strip() if image_tag and image_tag.get("content") else None
    )
    return {
        "title": title,
        "link": link,
        "date": date,
        "description": description,
        "source": AIHUBMIX_DOCS_SOURCE["label"],
        "category": AIHUBMIX_DOCS_SOURCE["category"],
        "image": image,
    }


def _collect_discovered(
    links, known_links, ledger, label, detail_fetcher
) -> list[dict]:
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
        except Exception as exc:  # noqa: BLE001  # skipcq: PYL-W0703 - isolate one broken article
            ledger.failed(label, link)
            logger.warning("[%s] skipping %s: %s", label, link, exc)
    return entries


def _changelog_entry(
    year: str, day_label: str, chunks: list[str], known_links
) -> dict | None:
    """Build one stable changelog entry from a year, month/day label, and body."""
    try:
        date = datetime.strptime(f"{year} {day_label}", "%Y %B %d").replace(tzinfo=UTC)
    except ValueError:
        return None

    changelog_url = AIHUBMIX_CHANGELOG_SOURCE["url"]
    link = f"{changelog_url}#{date:%Y-%m-%d}"
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
        "source": AIHUBMIX_CHANGELOG_LABEL,
        "category": AIHUBMIX_CHANGELOG_SOURCE["category"],
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
        posts = discover_aihubmix_posts(main_html)
        listing_dates = dict(posts)
        entries.extend(
            _collect_discovered(
                [link for link, _date in posts],
                known_links,
                ledger,
                AIHUBMIX_SOURCE["label"],
                lambda link: fetch_detail(link, listing_dates[link], AIHUBMIX_SOURCE),
            )
        )

    docs_url = AIHUBMIX_DOCS_SOURCE["url"]
    docs_html = fetch_url(docs_url)
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

    changelog_url = AIHUBMIX_CHANGELOG_SOURCE["url"]
    changelog_html = fetch_url(changelog_url)
    if changelog_html is not None:
        entries.extend(parse_aihubmix_changelog(changelog_html, known_links))

    return entries
