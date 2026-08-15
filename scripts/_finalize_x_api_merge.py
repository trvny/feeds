from pathlib import Path

xai = Path("feed_generators/xai.py")
text = xai.read_text(encoding="utf-8")
if "X_API_MAX_ENTRIES = 50" not in text:
    text = text.replace(
        "MAX_ENTRIES = 200\n",
        "MAX_ENTRIES = 200\nX_API_MAX_ENTRIES = 50\n",
    )
text = text.replace(
    '    entries = []\n    for item in parse_x_api_items(html):\n',
    '    entries = []\n'
    '    items = sort_posts_for_feed(parse_x_api_items(html), date_field="date")\n'
    '    for item in items[-X_API_MAX_ENTRIES:]:\n',
)
anchor = (
    "# --------------------------------------------------------------------------- #\n"
    "# Orchestration\n"
    "# --------------------------------------------------------------------------- #\n"
)
helper = '''def _cap_x_api_history(entries):
    """Keep only the newest X API changelog slice in the aggregate cache."""
    x_api = [entry for entry in entries if entry.get("source") == "X API changelog"]
    if len(x_api) <= X_API_MAX_ENTRIES:
        return entries
    x_api = sort_posts_for_feed(x_api, date_field="date")[-X_API_MAX_ENTRIES:]
    keep = {entry["link"] for entry in x_api}
    return [
        entry
        for entry in entries
        if entry.get("source") != "X API changelog" or entry["link"] in keep
    ]


'''
if "def _cap_x_api_history(" not in text:
    text = text.replace(anchor, helper + anchor)
text = text.replace(
    '    merged = dedupe_entries(merged, id_field="link", title_field="title", date_field="date")\n'
    '    merged = sort_posts_for_feed(merged, date_field="date")\n',
    '    merged = dedupe_entries(merged, id_field="link", title_field="title", date_field="date")\n'
    '    merged = _cap_x_api_history(merged)\n'
    '    merged = sort_posts_for_feed(merged, date_field="date")\n',
)
xai.write_text(text, encoding="utf-8")

adapter = '''"""X API changelog source adapter used by the grouped xAI feed."""

import re
import time

import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from utils import sanitize_xml, setup_logging

logger = setup_logging()

BLOG_URL = "https://docs.x.com/changelog"
DATE_RE = re.compile(r"\\b([A-Z][a-z]{2}\\s+\\d{1,2},\\s+20\\d\\d)\\b")


def fetch_text(url, retries=3, backoff=2.0):
    """Fetch via curl_cffi Chrome impersonation; return None on failure."""
    try:
        from curl_cffi import requests as creq
    except ImportError:
        creq = None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
        ),
    }
    for attempt in range(1, retries + 1):
        try:
            if creq is not None:
                response = creq.get(
                    url, headers=headers, impersonate="chrome", timeout=30
                )
                response.raise_for_status()
                return response.text
            from utils import fetch_page

            return fetch_page(url, headers=headers)
        except Exception as exc:
            logger.warning(
                "Fetch failed for %s (attempt %s/%s): %s",
                url,
                attempt,
                retries,
                exc,
            )
            if attempt < retries:
                time.sleep(backoff * attempt)
    return None


def parse_date(date_str):
    """Convert an X changelog date to UTC, or None if it cannot be parsed."""
    try:
        value = date_parser.parse(date_str)
        if value.tzinfo is None:
            value = value.replace(tzinfo=pytz.UTC)
        return value.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError):
        return None


def clean_description(text, fallback=""):
    if not text:
        return sanitize_xml(fallback)
    text = re.sub(r"\\s+", " ", text).strip()
    if len(text) > 500:
        text = text[:497].rstrip() + "..."
    return sanitize_xml(text or fallback)


def parse_items(html):
    """Return X changelog entries as title/link/date/description dictionaries."""
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for heading in soup.find_all("h3"):
        try:
            heading_id = heading.get("id")
            if not heading_id:
                continue
            title = sanitize_xml(
                heading.get_text(" ", strip=True).lstrip("\\u200b").strip()
            )
            if not title:
                continue
            link = f"{BLOG_URL}#{heading_id}"

            date_obj = None
            date_node = heading.find_previous(string=DATE_RE)
            if date_node:
                match = DATE_RE.search(str(date_node))
                if match:
                    date_obj = parse_date(match.group(1))

            description = title
            for node in heading.find_all_next(["p", "span", "div", "li"], limit=30):
                candidate = (
                    node.get_text(" ", strip=True).replace("\\u200b", "").strip()
                )
                if DATE_RE.search(candidate):
                    break
                if (
                    len(candidate) >= 25
                    and candidate != title
                    and not title.startswith(candidate)
                ):
                    description = candidate
                    break

            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date_obj,
                    "description": clean_description(description, fallback=title),
                }
            )
        except Exception as exc:
            logger.warning("Skipped a malformed changelog entry: %s", exc)
    logger.info("Parsed %d changelog entries", len(entries))
    return entries
'''
Path("feed_generators/x_changelog.py").write_text(adapter, encoding="utf-8")

docs = Path("feed_generators/docs_sources.py")
docs_text = docs.read_text(encoding="utf-8")
docs_text = docs_text.replace('    "x_changelog": "X API Changelog",\n', "")
docs_text = docs_text.replace('    "x_changelog",\n', "")
docs.write_text(docs_text, encoding="utf-8")
