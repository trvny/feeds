"""Keep feedgen's build timestamp from masquerading as an article update.

When an Atom entry has ``published`` but no explicit ``updated``, feedgen inserts
an ``updated`` value at serialization time. Every regeneration then makes an old
article look freshly modified. Replace only timestamps that match the feed-level
build time; genuine article update timestamps remain untouched.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from utils import get_feeds_dir

_FEED_UPDATED_RE = re.compile(
    r"<feed\b[^>]*>.*?<updated>([^<]+)</updated>", re.DOTALL
)
_ENTRY_RE = re.compile(r"(<entry\b[^>]*>)(.*?)(</entry>)", re.DOTALL)
_UPDATED_RE = re.compile(r"(<updated>)([^<]+)(</updated>)")
_PUBLISHED_RE = re.compile(r"<published>([^<]+)</published>")
_GENERATED_WINDOW_SECONDS = 5


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_atom_xml(xml: str) -> tuple[str, int]:
    """Return XML with generated entry updates replaced by publication dates."""
    feed_match = _FEED_UPDATED_RE.search(xml)
    if not feed_match:
        return xml, 0

    feed_updated = _parse_timestamp(feed_match.group(1))
    if feed_updated is None:
        return xml, 0

    replacements = 0

    def normalize_entry(match: re.Match[str]) -> str:
        nonlocal replacements
        body = match.group(2)
        updated_match = _UPDATED_RE.search(body)
        published_match = _PUBLISHED_RE.search(body)
        if not updated_match or not published_match:
            return match.group(0)

        entry_updated = _parse_timestamp(updated_match.group(2))
        if entry_updated is None:
            return match.group(0)
        if abs((entry_updated - feed_updated).total_seconds()) > _GENERATED_WINDOW_SECONDS:
            return match.group(0)

        published = published_match.group(1)
        body = _UPDATED_RE.sub(
            lambda updated: f"{updated.group(1)}{published}{updated.group(3)}",
            body,
            count=1,
        )
        replacements += 1
        return f"{match.group(1)}{body}{match.group(3)}"

    return _ENTRY_RE.sub(normalize_entry, xml), replacements


def normalize_feed_entry_dates(feeds_dir: Path | None = None) -> list[Path]:
    """Normalize every generated Atom feed and return changed paths."""
    root = feeds_dir or get_feeds_dir()
    changed: list[Path] = []
    for path in sorted(root.glob("feed_*.xml")):
        xml = path.read_text(encoding="utf-8")
        if "<feed" not in xml or "<entry" not in xml:
            continue
        normalized, replacements = normalize_atom_xml(xml)
        if not replacements:
            continue
        path.write_text(normalized, encoding="utf-8")
        changed.append(path)
    return changed
