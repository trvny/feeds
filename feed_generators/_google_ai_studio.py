"""Internal Google AI Studio adapter for the combined Google feed."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from utils import DEFAULT_HEADERS, sanitize_xml, setup_logging

logger = setup_logging()

AI_STUDIO_CHANGELOG_URL = "https://aistudio.google.com/docs/changelog"
AI_STUDIO_CHANGELOG_LABEL = "Google AI Studio"
AI_STUDIO_CHANGELOG_EXCERPT = 600

_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December"
)
_DATE_RE = re.compile(rf"\b({_MONTHS})\s+(\d{{1,2}}),\s+(\d{{4}})\b")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _parse_date(text: str) -> datetime | None:
    """Parse a date from a release-notes heading or standalone text node."""
    text = re.sub(r"\s+", " ", text).strip()
    match = _DATE_RE.search(text)
    if match:
        try:
            return datetime.strptime(match.group(0), "%B %d, %Y").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None

    match = _ISO_DATE_RE.search(text)
    if match:
        try:
            return datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None
    return None


def _entry(date: datetime, description: str, fragment: str) -> dict:
    description = re.sub(r"\s+", " ", description).strip()
    if len(description) > AI_STUDIO_CHANGELOG_EXCERPT:
        description = description[: AI_STUDIO_CHANGELOG_EXCERPT - 1].rstrip() + "…"
    date_slug = date.strftime("%Y-%m-%d")
    return {
        "title": f"Google AI Studio — {date_slug}",
        "link": f"{AI_STUDIO_CHANGELOG_URL}#{fragment or date_slug}",
        "date": date,
        "description": sanitize_xml(description) or f"Google AI Studio update — {date_slug}",
        "content_type": "text",
        "source": AI_STUDIO_CHANGELOG_LABEL,
    }


def _parse_ai_studio_changelog(html: str) -> list[dict]:
    """Parse dated release-note sections from AI Studio's public docs page."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("main") or soup.find("article") or soup.body or soup
    entries: list[dict] = []
    seen_dates: set[str] = set()

    # Preferred path: semantic date headings with their following section body.
    for heading in body.find_all(["h2", "h3", "h4"]):
        date = _parse_date(heading.get_text(" ", strip=True))
        if not date:
            continue
        date_slug = date.strftime("%Y-%m-%d")
        if date_slug in seen_dates:
            continue

        parts: list[str] = []
        for node in heading.find_all_next(["h2", "h3", "h4", "p", "li"]):
            if node is heading:
                continue
            node_text = node.get_text(" ", strip=True)
            if node.name in ("h2", "h3", "h4") and _parse_date(node_text):
                break
            if node.name in ("h3", "h4", "p", "li") and node_text:
                if not parts or parts[-1] != node_text:
                    parts.append(node_text)

        entries.append(
            _entry(date, " ".join(parts), (heading.get("id") or "").strip())
        )
        seen_dates.add(date_slug)

    if entries:
        return entries

    # Fallback for a client-rendered layout that still ships visible text in
    # non-semantic containers: split the flattened text at standalone dates.
    strings = [re.sub(r"\s+", " ", text).strip() for text in body.stripped_strings]
    starts: list[tuple[int, datetime]] = []
    for index, text in enumerate(strings):
        date = _parse_date(text)
        if date and (_DATE_RE.fullmatch(text) or _ISO_DATE_RE.fullmatch(text)):
            starts.append((index, date))

    for position, (index, date) in enumerate(starts):
        date_slug = date.strftime("%Y-%m-%d")
        if date_slug in seen_dates:
            continue
        end = starts[position + 1][0] if position + 1 < len(starts) else len(strings)
        parts = [text for text in strings[index + 1 : end] if text]
        entries.append(_entry(date, " ".join(parts), date_slug))
        seen_dates.add(date_slug)

    return entries


def collect_ai_studio_changelog(
    url: str = AI_STUDIO_CHANGELOG_URL,
) -> list[dict]:
    """Fetch Google AI Studio release notes; one dead source never kills Google."""
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
        entries = _parse_ai_studio_changelog(response.text)
    except Exception as exc:
        logger.warning("[google-ai-studio] fetch failed (%s); skipping source", exc)
        return []

    if not entries:
        logger.warning("[google-ai-studio] no dated release notes found; skipping source")
    else:
        logger.info("[google-ai-studio] parsed %d entries", len(entries))
    return entries
