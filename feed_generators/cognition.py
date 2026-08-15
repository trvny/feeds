"""Cognition / Devin source adapters for the SkillsLLM aggregate."""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import multi_rss
import pytz
from bs4 import BeautifulSoup
from utils import sanitize_xml, stable_fallback_date

COGNITION_BLOG_URL = "https://cognition.com/blog"
COGNITION_RESEARCH_URL = "https://cognition.com/research"
DEVIN_DESKTOP_RSS_URL = "https://docs.devin.ai/desktop/changelog/rss.xml"
DEVIN_RELEASE_NOTES_URL = "https://docs.devin.ai/release-notes/overview"
_DEVIN_RELEASE_NOTES_MD = DEVIN_RELEASE_NOTES_URL + ".md"

_COGNITION_DATE_RE = re.compile(r"\b(\d{2}\.\d{2}\.\d{2})\b")
_DEVIN_DATE_HEADING_RE = re.compile(
    r"^#{1,6}\s+([A-Z][a-z]+ \d{1,2}, 20\d{2})\s*$", re.MULTILINE
)
_DEVIN_UPDATE_RE = re.compile(
    r'<Update\s+label="([A-Z][a-z]+ \d{1,2}, 20\d{2})"[^>]*>(.*?)</Update>',
    re.DOTALL,
)
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_MARKUP_RE = re.compile(r"[`*_>#~-]+")


def _fetch(url: str) -> str | None:
    return multi_rss.get_html(url)


def _cognition_date(value: str):
    try:
        return datetime.strptime(value, "%m.%d.%y").replace(tzinfo=pytz.UTC)
    except ValueError:
        return None


def collect_cognition(known_links: set[str]) -> list[dict]:
    """Collect dated Cognition research first, then remaining blog posts."""
    entries: list[dict] = []
    seen = set(known_links)
    sources = (
        ("Cognition Research", COGNITION_RESEARCH_URL, "cognition-research"),
        ("Cognition Blog", COGNITION_BLOG_URL, "cognition-blog"),
    )
    for label, url, category in sources:
        html = _fetch(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        source_entries = []
        for anchor in soup.find_all("a", href=True):
            text = " ".join(anchor.stripped_strings)
            match = _COGNITION_DATE_RE.search(text)
            if not match:
                continue
            title = sanitize_xml(text[: match.start()].strip(" -|"))
            if not title:
                continue
            link = urljoin(url, anchor["href"]).split("#", 1)[0]
            if not link.startswith("https://cognition.com/") or link in seen:
                continue
            description = sanitize_xml(text[match.end() :].strip(" -|")) or title
            date = _cognition_date(match.group(1))
            source_entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date or stable_fallback_date(link),
                    "description": description,
                    "source": label,
                    "category": category,
                }
            )
            seen.add(link)
        entries.extend(source_entries[:80])
    return entries


def _plain_markdown(text: str) -> str:
    text = _MD_LINK_RE.sub(lambda match: match.group(1), text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _MD_MARKUP_RE.sub(" ", text)
    return sanitize_xml(re.sub(r"\s+", " ", text).strip())


def _release_sections(md: str) -> list[tuple[str, str]]:
    matches = list(_DEVIN_DATE_HEADING_RE.finditer(md))
    if matches:
        return [
            (
                match.group(1),
                md[
                    match.end() : (
                        matches[i + 1].start() if i + 1 < len(matches) else len(md)
                    )
                ],
            )
            for i, match in enumerate(matches)
        ]
    return _DEVIN_UPDATE_RE.findall(md)


def collect_devin_release_notes(known_links: set[str]) -> list[dict]:
    """Turn each dated Devin application release batch into one feed entry."""
    md = _fetch(_DEVIN_RELEASE_NOTES_MD)
    if not md:
        return []
    entries: list[dict] = []
    for label, body in _release_sections(md):
        try:
            date = datetime.strptime(label, "%B %d, %Y").replace(tzinfo=pytz.UTC)
        except ValueError:
            continue
        anchor = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        link = f"{DEVIN_RELEASE_NOTES_URL}#{anchor}"
        if link in known_links:
            continue
        plain = _plain_markdown(body)
        title = f"Devin updates — {label}"
        entries.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "description": plain[:700] or title,
                "source": "Devin Release Notes",
                "category": "devin-release-notes",
            }
        )
    return entries[:80]
