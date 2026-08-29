"""Uber Blog + Newsroom combined Atom feed.

The public Uber editorial listings are server-rendered and expose article links,
titles and publication dates without requiring a browser. This generator reads
three surfaces requested for the feed: the Polish blog, US blog and US Newsroom.
The shared Feedseek cache accumulates history while each run only needs the
latest listing page from every surface.

Writes ``feeds/feed_uber.xml`` and the matching JSON sidecar.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import multi_rss
from utils import sanitize_xml, stable_fallback_date

FEED_NAME = "uber"
FEED_TITLE = "Uber Newsroom"
BLOG_URL = "https://www.uber.com/us/en/newsroom/"
MAX_ENTRIES = 300
PER_SOURCE_CAP = 120

SOURCES = (
    ("Uber Blog PL", "https://www.uber.com/pl/pl/blog/", "/pl/pl/blog/", "pl"),
    ("Uber Blog US", "https://www.uber.com/us/en/blog/", "/us/en/blog/", "en"),
    ("Uber Newsroom US", BLOG_URL, "/us/en/newsroom/", "en"),
)

_EN_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}\b"
)
_PL_MONTHS = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "wrzesnia": 9,
    "października": 10,
    "pazdziernika": 10,
    "listopada": 11,
    "grudnia": 12,
}
_PL_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(map(re.escape, _PL_MONTHS)) + r")\s+(20\d{2})\b",
    re.IGNORECASE,
)


def doc_sources():
    """Return the three public Uber editorial listings used by this feed."""
    return [(label, url) for label, url, _prefix, _locale in SOURCES]


def _parse_polish_date(text: str) -> datetime | None:
    match = _PL_DATE_RE.search(text)
    if not match:
        return None
    try:
        return datetime(
            int(match.group(3)),
            _PL_MONTHS[match.group(2).lower()],
            int(match.group(1)),
            tzinfo=timezone.utc,
        )
    except (KeyError, ValueError):
        return None


def _date_from_card(card, locale: str) -> datetime | None:
    time_el = card.find("time", attrs={"datetime": True})
    if time_el:
        parsed = multi_rss.parse_date(time_el.get("datetime"))
        if parsed is not None:
            return parsed
    text = card.get_text(" ", strip=True)
    if locale == "pl":
        return _parse_polish_date(text)
    match = _EN_DATE_RE.search(text)
    return multi_rss.parse_date(match.group(0)) if match else None


def _card_for(anchor, locale: str):
    """Return the nearest ancestor that contains this article's date."""
    node = anchor
    for _ in range(6):
        if node is None:
            break
        if _date_from_card(node, locale) is not None:
            return node
        node = node.parent
    return anchor


def _image_from_card(card, base_url: str) -> str | None:
    image = card.find("img")
    if image is None:
        return None
    src = image.get("src") or image.get("data-src")
    if not src:
        srcset = image.get("srcset") or ""
        src = srcset.split(",", 1)[0].strip().split(" ", 1)[0]
    return urljoin(base_url, src) if src else None


def parse_listing(
    html: str,
    *,
    label: str,
    base_url: str,
    path_prefix: str,
    locale: str,
    known_links: set[str] | None = None,
) -> list[dict]:
    """Parse one Uber listing page into Feedseek entry dictionaries."""
    soup = BeautifulSoup(html, "html.parser")
    known_links = known_links or set()
    entries: list[dict] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").split("#", 1)[0].split("?", 1)[0]
        link = urljoin(base_url, href).rstrip("/") + "/"
        path = urlparse(link).path
        if (
            path == path_prefix
            or not path.startswith(path_prefix)
            or "/page/" in path
        ):
            continue
        if link in seen or link in known_links:
            continue

        card = _card_for(anchor, locale)
        heading = anchor.find(["h1", "h2", "h3", "h4", "h5", "h6"]) or card.find(
            ["h1", "h2", "h3", "h4", "h5", "h6"]
        )
        title_text = (
            heading.get_text(" ", strip=True)
            if heading is not None
            else anchor.get_text(" ", strip=True)
        )
        title = sanitize_xml(title_text)
        date = _date_from_card(card, locale)
        if not title or date is None:
            continue

        seen.add(link)
        entries.append(
            {
                "title": title[:200],
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": title[:500],
                "source": label,
                "image": _image_from_card(card, base_url),
            }
        )

    entries.sort(
        key=lambda entry: entry["date"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return entries


def collect_uber(known_links: set[str]) -> list[dict]:
    """Collect fresh entries from all requested Uber surfaces."""
    out: list[dict] = []
    seen = set(known_links)
    for label, url, prefix, locale in SOURCES:
        html = multi_rss.get_html(url)
        if not html:
            continue
        entries = parse_listing(
            html,
            label=label,
            base_url=url,
            path_prefix=prefix,
            locale=locale,
            known_links=seen,
        )
        out.extend(entries)
        seen.update(entry["link"] for entry in entries)
        multi_rss.logger.info("[%s] collected %d entries", label, len(entries))
    return out


def main(full: bool = False) -> bool:
    """Generate the combined Uber Atom feed."""
    return multi_rss.run(
        feed_name=FEED_NAME,
        title=FEED_TITLE,
        subtitle="Uber Blog (Poland + US) and Uber US Newsroom in one feed.",
        blog_url=BLOG_URL,
        author="Uber",
        extra_scrapers=(collect_uber,),
        max_entries=MAX_ENTRIES,
        per_source_cap=PER_SOURCE_CAP,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Uber Newsroom Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
