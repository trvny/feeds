"""X API changelog source adapter used by the grouped xAI feed."""

import re
import time

import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from utils import sanitize_xml, setup_logging

logger = setup_logging()

BLOG_URL = "https://docs.x.com/changelog"
DATE_RE = re.compile(r"\b([A-Z][a-z]{2}\s+\d{1,2},\s+20\d\d)\b")


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
        except Exception as exc:  # noqa: BLE001
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
    text = re.sub(r"\s+", " ", text).strip()
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
                heading.get_text(" ", strip=True).lstrip("\u200b").strip()
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
                    node.get_text(" ", strip=True).replace("\u200b", "").strip()
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
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipped a malformed changelog entry: %s", exc)
    logger.info("Parsed %d changelog entries", len(entries))
    return entries
