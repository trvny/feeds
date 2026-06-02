"""RSS feed generator for Windows 11 release notes.

Combines two Microsoft sources into a single feed:
  1. Windows 11, version 25H2 update history (support.microsoft.com)
     -- the KB / OS Build release entries.
  2. Windows message center (learn.microsoft.com)
     -- announcements, advisories, and "news you can use" posts.

Both sources serve their content in the static HTML, so this is a plain
requests + BeautifulSoup generator.
"""

import contextlib
import re
from datetime import datetime

import pytz
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    DEFAULT_HEADERS,
    sanitize_xml,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "windows11_release_notes"
# Public landing page for the feed's <link>; the update-history aka.ms short link.
BLOG_URL = "https://aka.ms/Windows11/25H2/UpdateHistory"

# Source 1: resolved target of the aka.ms short link.
UPDATE_HISTORY_URL = (
    "https://support.microsoft.com/en-us/topic/"
    "windows-11-version-25h2-update-history-99c7f493-df2a-4832-bd2d-6706baa0dec0"
)
SUPPORT_BASE = "https://support.microsoft.com"

# Source 2: Windows release-health message center.
MESSAGE_CENTER_URL = "https://learn.microsoft.com/en-us/windows/release-health/windows-message-center"

# Date formats seen across the two sources.
DATE_FORMATS = [
    "%B %d, %Y",  # "May 26, 2026" (update history)
    "%b %d, %Y",  # "May 26, 2026" (abbreviated, just in case)
]

# Leading "Month DD, YYYY" portion of an update-history title.
_HISTORY_DATE_RE = re.compile(
    r"^((?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s+\d{4})"
)
# "2026-06-01 16:00 PT" style timestamps in the message center.
_MC_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?")


def fetch_page_utf8(url):
    """Fetch a page forcing UTF-8 decoding.

    Microsoft pages omit a charset in some responses, so requests guesses
    latin-1 and mangles smart quotes/dashes. Forcing UTF-8 fixes that.
    """
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def parse_history_date(title):
    """Extract a datetime from the leading date in an update-history title."""
    match = _HISTORY_DATE_RE.match(title)
    if match:
        for fmt in DATE_FORMATS:
            with contextlib.suppress(ValueError):
                return datetime.strptime(match.group(1), fmt).replace(tzinfo=pytz.UTC)
    return None


def parse_message_center_date(date_text):
    """Parse a message center timestamp like '2026-06-01 16:00 PT'."""
    match = _MC_DATE_RE.search(date_text or "")
    if match:
        date_part, time_part = match.group(1), match.group(2) or "00:00"
        with contextlib.suppress(ValueError):
            return datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M").replace(tzinfo=pytz.UTC)
    return None


def parse_update_history(html):
    """Parse KB / OS Build release entries from the 25H2 update-history page."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    seen = set()

    # Release entries live as left-nav article links pointing at /<locale>/help/<kb>.
    links = soup.select("a.supLeftNavLink, .supLeftNavArticle a, a[href*='/help/']")
    for link in links:
        try:
            title = link.get_text(" ", strip=True)
            href = link.get("href", "")
            if not title or "KB" not in title or "OS Build" not in title:
                continue
            if "/help/" not in href:
                continue

            full_link = href if href.startswith("http") else SUPPORT_BASE + href
            if full_link in seen:
                continue
            seen.add(full_link)

            date_obj = parse_history_date(title) or stable_fallback_date(full_link)
            posts.append(
                {
                    "title": sanitize_xml(title),
                    "description": sanitize_xml(f"Windows 11 update: {title}"),
                    "link": full_link,
                    "date": date_obj,
                }
            )
        except Exception as e:  # noqa: BLE001 - never let one row crash the run
            logger.warning(f"Skipping an update-history entry: {e!s}")
            continue

    logger.info(f"Parsed {len(posts)} update-history entries")
    return posts


def parse_message_center(html):
    """Parse announcement rows from the Windows message center table."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    seen = set()

    table = soup.find("table")
    if not table:
        logger.warning("Message center: no table found")
        return posts

    for row in table.find_all("tr"):
        try:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue  # header row

            msg_cell, date_cell = cells[0], cells[1]
            anchor = msg_cell.find("a")

            title_el = msg_cell.find("b") or anchor
            title = title_el.get_text(" ", strip=True) if title_el else msg_cell.get_text(" ", strip=True)
            if not title:
                continue

            body_el = msg_cell.find("div")
            description = body_el.get_text(" ", strip=True) if body_el else title

            href = anchor.get("href", "") if anchor else ""
            if href and not href.startswith("http"):
                href = "https://learn.microsoft.com" + href
            if not href:
                row_id = msg_cell.get("id")
                href = f"{MESSAGE_CENTER_URL}#{row_id}" if row_id else MESSAGE_CENTER_URL

            if href in seen:
                continue
            seen.add(href)

            date_obj = parse_message_center_date(date_cell.get_text(" ", strip=True)) or stable_fallback_date(href)
            posts.append(
                {
                    "title": sanitize_xml(title),
                    "description": sanitize_xml(description),
                    "link": href,
                    "date": date_obj,
                }
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Skipping a message-center row: {e!s}")
            continue

    logger.info(f"Parsed {len(posts)} message-center entries")
    return posts


def generate_rss_feed(posts, feed_name=FEED_NAME):
    """Generate the combined RSS feed."""
    fg = FeedGenerator()
    fg.title("Windows 11 Release notes")
    fg.description(
        "Windows 11, version 25H2 update history (KB / OS Build releases) "
        "combined with the Windows release-health message center."
    )
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language("en")
    fg.author({"name": "Microsoft"})
    fg.subtitle("Windows 11 update history and message center announcements")

    for post in posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post["link"])
        fe.published(post["date"])

    logger.info("Successfully generated RSS feed")
    return fg


def main(feed_name=FEED_NAME):
    """Fetch both sources, merge them, and write the combined feed."""
    posts = []

    for label, url, parser in (
        ("update history", UPDATE_HISTORY_URL, parse_update_history),
        ("message center", MESSAGE_CENTER_URL, parse_message_center),
    ):
        try:
            posts.extend(parser(fetch_page_utf8(url)))
        except Exception as e:  # noqa: BLE001 - one source failing shouldn't kill the other
            logger.error(f"Failed to fetch/parse {label}: {e!s}")

    if not posts:
        logger.warning("No posts found -- skipping feed update to avoid overwriting with empty feed")
        return False

    # Deduplicate across sources by link, then sort (ascending -> newest first in feed).
    deduped = {}
    for post in posts:
        deduped.setdefault(post["link"], post)
    ordered = sort_posts_for_feed(list(deduped.values()))

    feed = generate_rss_feed(ordered, feed_name)
    save_rss_feed(feed, feed_name)
    return True


if __name__ == "__main__":
    main()
