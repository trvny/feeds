"""Red Hat Enterprise feed: news, RHEL, CentOS, research and security.

Native RSS is preferred wherever Red Hat exposes it. The newsroom and Security
Data Changelog do not provide useful native feeds, so they use small HTML
adapters. Legacy Customer Portal blogs remain included for archive continuity,
but their intake and published quotas are intentionally tiny.
"""

import argparse
import hashlib
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "redhat"
BLOG_URL = "https://www.redhat.com/en/"
NEWSROOM_URL = "https://www.redhat.com/en/about/newsroom"
SECURITY_CHANGELOG_URL = "https://access.redhat.com/articles/5554431"

# Specific Red Hat channels precede the general blog so cross-source duplicates
# keep the more useful source label. The four Customer Portal blogs are legacy
# archives and intentionally have tiny first-run intake caps.
SOURCES = [
    (
        "Red Hat Enterprise Linux",
        "https://www.redhat.com/en/rss/blog/channel/red-hat-enterprise-linux",
        12,
    ),
    ("Red Hat Security", "https://www.redhat.com/en/rss/blog/channel/security", 12),
    (
        "Red Hat Satellite",
        "https://www.redhat.com/en/rss/blog/channel/red-hat-satellite",
        10,
    ),
    ("Red Hat Developer", "https://developers.redhat.com/blog/feed", 15),
    ("CentOS Blog", "https://blog.centos.org/feed/", 12),
    ("Red Hat Research", "https://research.redhat.com/feed/", 12),
    ("Red Hat Blog", "https://www.redhat.com/en/rss/blog", 20),
    (
        "Red Hat Security Errata",
        "https://security.access.redhat.com/data/meta/v1/rhsa.rss",
        15,
    ),
    (
        "Red Hat Security Blog (legacy)",
        "https://access.redhat.com/blogs/766093/feed",
        4,
    ),
    (
        "Red Hat Satellite Blog (legacy)",
        "https://access.redhat.com/blogs/1169563/feed",
        3,
    ),
    (
        "Red Hat Performance Blog (legacy)",
        "https://access.redhat.com/blogs/767173/feed",
        3,
    ),
    (
        "Red Hat Insights Blog (legacy)",
        "https://access.redhat.com/blogs/2184921/feed",
        4,
    ),
]

# Hard published ceilings. multi_rss still deals entries round-robin, so quieter
# sources retain visibility while RHSA and the general blog cannot flood them.
PER_SOURCE_QUOTA = {
    "": 18,
    "Red Hat Newsroom": 20,
    "Red Hat Enterprise Linux": 20,
    "Red Hat Security": 18,
    "Red Hat Satellite": 14,
    "Red Hat Developer": 24,
    "CentOS Blog": 18,
    "Red Hat Research": 18,
    "Red Hat Blog": 24,
    "Red Hat Security Errata": 14,
    "Red Hat Security Data Changelog": 12,
    "Red Hat Security Blog (legacy)": 4,
    "Red Hat Satellite Blog (legacy)": 3,
    "Red Hat Performance Blog (legacy)": 3,
    "Red Hat Insights Blog (legacy)": 4,
}

NEWSROOM_CAP = 20
SECURITY_CHANGELOG_CAP = 20
DESC_LIMIT = 500

_DATE_RE = re.compile(
    r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4})",
    re.IGNORECASE,
)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _stable_fragment(prefix, date_obj, title, occurrence=1):
    digest = hashlib.sha256(title.encode("utf-8")).hexdigest()[:8]
    slug = _slug(title)[:56] or "update"
    fragment = f"{prefix}-{date_obj.date().isoformat()}-{slug}-{digest}"
    return f"{fragment}-{occurrence}" if occurrence > 1 else fragment


def _nearest_text(link, *, max_depth=4):
    """Return the nearest small card/container text surrounding an anchor."""
    node = link
    for _ in range(max_depth):
        node = node.parent
        if node is None:
            break
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        if _DATE_RE.search(text) and len(text) <= 1200:
            return text
    return ""


def _newsroom_card_text(link):
    """Keep each press-release date scoped to its own Red Hat card."""
    card = link.find_parent("rh-card") or link.find_parent("article")
    if card is not None:
        text = re.sub(r"\s+", " ", card.get_text(" ", strip=True)).strip()
        if _DATE_RE.search(text):
            return text
    return _nearest_text(link)


def scrape_newsroom(known_links):
    label = "Red Hat Newsroom"
    html = get_html(NEWSROOM_URL)
    if html is None:
        return []
    soup = BeautifulSoup(html, "html.parser")

    candidates = []
    seen = set()
    for link_el in soup.select('a[href*="/en/about/press-releases/"]'):
        href = (link_el.get("href") or "").strip()
        if not href:
            continue
        link = urljoin(NEWSROOM_URL, href)
        if link in seen:
            continue
        seen.add(link)
        title = sanitize_xml(
            re.sub(r"\s+", " ", link_el.get_text(" ", strip=True))
        )
        card_text = _newsroom_card_text(link_el)
        match = _DATE_RE.search(card_text)
        date_obj = parse_date(match.group(1)) if match else None
        if not title or date_obj is None:
            continue
        description = card_text.replace(title, "", 1)
        description = _DATE_RE.sub("", description, count=1).strip(" -–—|")
        candidates.append(
            {
                "title": title,
                "link": link,
                "date": date_obj,
                "description": sanitize_xml(description)[:DESC_LIMIT] or title,
                "source": label,
            }
        )

    if not candidates:
        logger.warning(
            "  [%s] no press-release cards matched; layout may have changed", label
        )
        return []

    candidates.sort(key=lambda entry: entry["date"], reverse=True)
    entries = [
        entry
        for entry in candidates[:NEWSROOM_CAP]
        if entry["link"] not in known_links
    ]
    for entry in entries:
        logger.info("  [%s] %s", label, entry["title"])
    return entries


def _changelog_description(heading):
    parts = []
    for node in heading.next_elements:
        if node is heading:
            continue
        if isinstance(node, Tag) and node.name in {"h2", "h3"}:
            break
        if isinstance(node, Tag) and node.name in {"p", "li"}:
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            if text and text not in parts:
                parts.append(text)
        if sum(len(part) for part in parts) >= DESC_LIMIT:
            break
    return sanitize_xml(" ".join(parts))[:DESC_LIMIT]


def scrape_security_data_changelog(known_links):
    label = "Red Hat Security Data Changelog"
    html = get_html(SECURITY_CHANGELOG_URL)
    if html is None:
        return []
    soup = BeautifulSoup(html, "html.parser")

    current_date = None
    occurrence_by_key = {}
    candidates = []
    for heading in soup.find_all(["h2", "h3"]):
        text = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip()
        if heading.name == "h2":
            match = _DATE_RE.search(text)
            current_date = parse_date(match.group(1)) if match else None
            continue
        if current_date is None or not text:
            continue
        title = sanitize_xml(text)
        key = (current_date.date(), title)
        occurrence_by_key[key] = occurrence_by_key.get(key, 0) + 1
        fragment = _stable_fragment(
            "security-data", current_date, title, occurrence_by_key[key]
        )
        candidates.append(
            {
                "title": title,
                "link": f"{SECURITY_CHANGELOG_URL}#{fragment}",
                "date": current_date,
                "description": _changelog_description(heading) or title,
                "source": label,
            }
        )

    if not candidates:
        logger.warning(
            "  [%s] no dated changelog entries matched; layout may have changed", label
        )
        return []

    # Make the newest-slice cap independent of whatever order the page renders.
    candidates.sort(key=lambda entry: entry["date"], reverse=True)
    # Cap before filtering known links so later runs do not slowly backfill years
    # of historical changes after the current slice has already been cached.
    entries = [
        entry
        for entry in candidates[:SECURITY_CHANGELOG_CAP]
        if entry["link"] not in known_links
    ]
    for entry in entries:
        logger.info("  [%s] %s", label, entry["title"])
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Red Hat Enterprise",
        subtitle=(
            "Red Hat enterprise news, RHEL, Developer, CentOS, Research, Security, "
            "Satellite, Insights, RHSA advisories and security-data changes."
        ),
        blog_url=BLOG_URL,
        author="Red Hat",
        sources=SOURCES,
        extra_scrapers=(scrape_newsroom, scrape_security_data_changelog),
        max_entries=200,
        per_source_cap=PER_SOURCE_QUOTA,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Red Hat Enterprise Atom feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
