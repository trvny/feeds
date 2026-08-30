"""Combined AWS announcements, blogs, re:Post articles, and AWS CLI releases."""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urlencode

import multi_rss
from bs4 import BeautifulSoup
from utils import sanitize_xml

FEED_NAME = "aws"
FEED_TITLE = "AWS"
BLOG_URL = "https://aws.amazon.com/blogs/"
MAX_ENTRIES = 400
MAX_REPOST_PAGES = 8

WHATS_NEW_FEED = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
NEWS_BLOG_URL = "https://aws.amazon.com/blogs/aws/"
NEWS_BLOG_FEED = f"{NEWS_BLOG_URL}feed/"
DEVELOPER_BLOG_URL = "https://aws.amazon.com/blogs/developer/"
DEVELOPER_BLOG_FEED = f"{DEVELOPER_BLOG_URL}feed/"
OPEN_SOURCE_BLOG_URL = "https://aws.amazon.com/blogs/opensource/"
OPEN_SOURCE_BLOG_FEED = f"{OPEN_SOURCE_BLOG_URL}feed/"
REPOST_URL = "https://repost.aws/articles"
CLI_CHANGELOG_URL = "https://raw.githubusercontent.com/aws/aws-cli/v2/CHANGELOG.rst"
CLI_RELEASES_ATOM = "https://github.com/aws/aws-cli/releases.atom"

SOURCES = (
    ("AWS What's New", WHATS_NEW_FEED, 100),
    ("AWS News Blog", NEWS_BLOG_FEED, 80),
    ("AWS Developer Tools Blog", DEVELOPER_BLOG_FEED, 80),
    ("AWS Open Source Blog", OPEN_SOURCE_BLOG_FEED, 80),
)
PER_SOURCE_CAP = {
    "AWS What's New": 100,
    "AWS News Blog": 80,
    "AWS Developer Tools Blog": 80,
    "AWS Open Source Blog": 80,
    "AWS re:Post Articles": 80,
    "AWS CLI v2 Changelog": 40,
}
_VERSION_HEADING_RE = re.compile(r"(?m)^(\d+\.\d+\.\d+)\r?\n=+\s*$")


def doc_sources():
    """Return the user-facing AWS surfaces represented by this aggregate."""
    return [
        ("AWS What's New", WHATS_NEW_FEED),
        ("AWS Blogs", BLOG_URL),
        ("AWS re:Post Articles", REPOST_URL),
        ("AWS News Blog", NEWS_BLOG_URL),
        ("AWS CLI v2 Changelog", CLI_CHANGELOG_URL),
        ("AWS Developer Tools Blog", DEVELOPER_BLOG_URL),
        ("AWS Open Source Blog", OPEN_SOURCE_BLOG_URL),
    ]


def _repost_response(html: str) -> tuple[dict, BeautifulSoup] | None:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None or not script.string:
        return None
    try:
        payload = json.loads(script.string)
        response = payload["props"]["pageProps"]["response"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    if not isinstance(response, dict) or not isinstance(response.get("articles"), list):
        return None
    return response, soup


def parse_repost_page(html: str) -> dict | None:
    """Parse one server-rendered AWS re:Post article listing page."""
    parsed = _repost_response(html)
    if parsed is None:
        return None
    response, soup = parsed
    links: dict[str, str] = {}
    for anchor in soup.select("a[href^='/articles/']"):
        href = str(anchor.get("href") or "").split("?", 1)[0].split("#", 1)[0]
        parts = href.split("/")
        if len(parts) >= 4 and parts[2]:
            links.setdefault(parts[2], f"https://repost.aws{href}")

    entries = []
    for item in response["articles"]:
        if not isinstance(item, dict) or item.get("language") not in (None, "en"):
            continue
        article_id = str(item.get("id") or "").strip()
        title = sanitize_xml(str(item.get("title") or "").strip()).strip()
        link = links.get(article_id)
        date = multi_rss.parse_date(item.get("createdAt"))
        if not article_id or not title or not link or date is None:
            continue
        description = sanitize_xml(str(item.get("description") or "").strip()).strip()
        entries.append(
            {
                "title": title[:300],
                "link": link,
                "date": date,
                "description": (description or title)[:2000],
                "source": "AWS re:Post Articles",
            }
        )

    page = response.get("page")
    page_size = response.get("pageSize")
    total = response.get("totalCount")
    if not all(isinstance(value, int) and value >= 0 for value in (page, page_size, total)):
        return None
    tokens = {
        record.get("page"): record.get("token")
        for record in response.get("pagingTokens", [])
        if isinstance(record, dict)
        and isinstance(record.get("page"), int)
        and isinstance(record.get("token"), str)
        and record.get("token")
    }
    return {"entries": entries, "page": page, "page_size": page_size, "total": total, "tokens": tokens}


def _repost_page_url(token: str) -> str:
    return f"{REPOST_URL}?{urlencode({'page': token, 'pageSize': 12})}"


def collect_repost(known_links: set[str]) -> list[dict]:
    """Collect re:Post pages until cached history or the initial-history cap."""
    collected: list[dict] = []
    seen: set[str] = set()
    url = REPOST_URL
    page_no = 1
    reached_known = False
    latest_meta = None

    while page_no <= MAX_REPOST_PAGES:
        html = multi_rss.get_html(url)
        if not html:
            multi_rss.logger.warning("[AWS re:Post Articles] page %d unavailable; discarding partial batch", page_no)
            return []
        parsed = parse_repost_page(html)
        if parsed is None or parsed["page"] != page_no:
            multi_rss.logger.warning("[AWS re:Post Articles] page %d payload changed; discarding partial batch", page_no)
            return []
        latest_meta = parsed
        for entry in parsed["entries"]:
            link = entry["link"]
            if link in known_links:
                reached_known = True
                continue
            if link not in seen:
                seen.add(link)
                collected.append(entry)
        if (
            reached_known
            or page_no * parsed["page_size"] >= parsed["total"]
            or page_no >= MAX_REPOST_PAGES
        ):
            break
        next_page = page_no + 1
        token = parsed["tokens"].get(next_page)
        if not token:
            multi_rss.logger.warning("[AWS re:Post Articles] missing token for page %d; discarding partial batch", next_page)
            return []
        page_no = next_page
        url = _repost_page_url(token)

    if (
        known_links
        and not reached_known
        and latest_meta is not None
        and page_no * latest_meta["page_size"] < latest_meta["total"]
    ):
        multi_rss.logger.warning("[AWS re:Post Articles] history boundary exceeded safety cap; discarding partial batch")
        return []
    multi_rss.logger.info("[AWS re:Post Articles] collected %d fresh entries across %d page(s)", len(collected), page_no)
    return collected


def parse_cli_release_dates(atom_xml: str) -> dict[str, tuple[object, str]]:
    """Map AWS CLI release versions to their GitHub release date and URL."""
    soup = BeautifulSoup(atom_xml, "xml")
    releases = {}
    for entry in soup.find_all("entry"):
        title_el = entry.find("title")
        updated_el = entry.find("updated")
        link_el = entry.find("link", href=True)
        version = title_el.get_text(strip=True) if title_el else ""
        date = multi_rss.parse_date(updated_el.get_text(strip=True)) if updated_el else None
        link = str(link_el.get("href") or "").strip() if link_el else ""
        if re.fullmatch(r"2\.\d+\.\d+", version) and date is not None and link:
            releases[version] = (date, link)
    return releases


def _clean_rst_summary(body: str, version: str) -> str:
    lines = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^\*\s*", "", line)
        line = line.replace("``", "")
        lines.append(line)
    summary = sanitize_xml(" ".join(lines)).strip()
    return (summary or f"AWS CLI {version} release")[:3000]


def parse_cli_changelog(
    changelog: str,
    release_dates: dict[str, tuple[object, str]],
    known_links: set[str] | None = None,
) -> list[dict]:
    """Join v2 changelog sections with authoritative GitHub release dates."""
    known_links = known_links or set()
    matches = list(_VERSION_HEADING_RE.finditer(changelog))
    entries = []
    for index, match in enumerate(matches):
        version = match.group(1)
        release = release_dates.get(version)
        if release is None:
            continue
        date, link = release
        if link in known_links:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
        body = changelog[match.end() : end]
        entries.append(
            {
                "title": f"AWS CLI {version}",
                "link": link,
                "date": date,
                "description": _clean_rst_summary(body, version),
                "source": "AWS CLI v2 Changelog",
            }
        )
    entries.sort(key=lambda entry: entry["date"], reverse=True)
    return entries


def collect_cli_changelog(known_links: set[str]) -> list[dict]:
    """Collect dated AWS CLI v2 changelog entries."""
    changelog = multi_rss.get_html(CLI_CHANGELOG_URL)
    releases_xml = multi_rss.get_html(CLI_RELEASES_ATOM)
    if not changelog or not releases_xml:
        return []
    releases = parse_cli_release_dates(releases_xml)
    entries = parse_cli_changelog(changelog, releases, known_links)
    multi_rss.logger.info("[AWS CLI v2 Changelog] collected %d fresh releases", len(entries))
    return entries


def main(full: bool = False) -> bool:
    return multi_rss.run(
        feed_name=FEED_NAME,
        title=FEED_TITLE,
        subtitle="AWS announcements, selected blogs, re:Post articles, and AWS CLI v2 releases.",
        blog_url=BLOG_URL,
        author="Amazon Web Services",
        sources=SOURCES,
        extra_scrapers=(collect_repost, collect_cli_changelog),
        max_entries=MAX_ENTRIES,
        per_source_cap=PER_SOURCE_CAP,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined AWS Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
