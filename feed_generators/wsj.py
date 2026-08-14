"""Combined Wall Street Journal feed from public Dow Jones RSS channels."""

import argparse
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from multi_rss import get_html, parse_date, run
from utils import favicon_proxy, sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "wsj"
LATEST_URL = "https://www.wsj.com/news/latest-headlines?mod=wsjfooter"
ARTICLE_PATH_RE = re.compile(r"-[0-9a-f]{8}/?$")

SOURCES = [
    ("World", "https://feeds.content.dowjones.io/public/rss/RSSWorldNews", 50),
    ("Opinion", "https://feeds.content.dowjones.io/public/rss/RSSOpinion", 50),
    ("Style", "https://feeds.content.dowjones.io/public/rss/RSSStyle", 40),
    ("Lifestyle", "https://feeds.content.dowjones.io/public/rss/RSSLifestyle", 40),
    ("Tech", "https://feeds.content.dowjones.io/public/rss/RSSWSJD", 50),
    ("Economy", "https://feeds.content.dowjones.io/public/rss/socialeconomyfeed", 50),
    (
        "Arts & Culture",
        "https://feeds.content.dowjones.io/public/rss/RSSArtsCulture",
        40,
    ),
    ("Health", "https://feeds.content.dowjones.io/public/rss/socialhealth", 40),
    ("Sports", "https://feeds.content.dowjones.io/public/rss/rsssportsfeed", 50),
]


def _article_link(href):
    link = urljoin("https://www.wsj.com/", href or "")
    parsed = urlparse(link)
    if parsed.netloc not in {"wsj.com", "www.wsj.com"}:
        return None
    if not ARTICLE_PATH_RE.search(parsed.path):
        return None
    return f"https://www.wsj.com{parsed.path}"


def _card_date(scope):
    time_el = scope.find("time", datetime=True)
    if time_el:
        parsed = parse_date(time_el.get("datetime"))
        if parsed:
            return parsed
    return datetime.now(timezone.utc)


def scrape_latest(known_links):
    """Pick article cards from WSJ's server-rendered Latest Headlines page."""
    html = get_html(LATEST_URL)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    entries = []
    seen = set()
    for heading in soup.find_all(["h2", "h3"]):
        try:
            anchor = heading.find("a", href=True) or heading.find_parent("a", href=True)
            if not anchor:
                continue
            link = _article_link(anchor.get("href"))
            if not link or link in known_links or link in seen:
                continue

            title = heading.get_text(" ", strip=True)
            if len(title) < 8:
                continue

            scope = heading.find_parent(["article", "li", "div"]) or heading.parent
            summary = ""
            if scope:
                paragraph = scope.find("p")
                summary = paragraph.get_text(" ", strip=True) if paragraph else ""
                image_el = scope.find("img", src=True)
                image = (
                    urljoin("https://www.wsj.com/", image_el.get("src"))
                    if image_el
                    else None
                )
            else:
                image = None

            seen.add(link)
            entries.append(
                {
                    "title": sanitize_xml(title[:250]),
                    "link": link,
                    "date": _card_date(scope or heading),
                    "description": sanitize_xml((summary or title)[:500]),
                    "source": "Latest Headlines",
                    "image": image,
                }
            )
            if len(entries) >= 50:
                break
        except Exception as exc:
            logger.warning("  [Latest Headlines] skipping card: %s", exc)

    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="WSJ",
        subtitle="Combined Wall Street Journal latest headlines and public section feeds.",
        blog_url=LATEST_URL,
        icon=favicon_proxy("wsj.com"),
        author="The Wall Street Journal",
        sources=SOURCES,
        extra_scrapers=[scrape_latest],
        max_entries=300,
        per_source_cap=35,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the WSJ Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
