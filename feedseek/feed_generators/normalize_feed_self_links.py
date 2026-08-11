"""Normalize generated feed metadata after each generator run.

Besides fixing legacy raw-GitHub self links, make Atom icon metadata deliberately
redundant: readers disagree on whether they inspect ``<icon>`` or ``<logo>``.
Mirroring a lone value into the missing slot gives both camps the same hint.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
FEEDS_DIR = ROOT_DIR / "feeds"
LEGACY_PREFIX = "https://raw.githubusercontent.com/trvny/feeds/main/feeds/"
CURRENT_PREFIX = "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/"

_TAG_RE = {
    tag: re.compile(rf"<{tag}>(?P<value>[^<]+)</{tag}>")
    for tag in ("icon", "logo")
}


def _tag_match(content: str, tag: str):
    return _TAG_RE[tag].search(content)


def _tag_indent(content: str, position: int) -> str:
    line_start = content.rfind("\n", 0, position) + 1
    prefix = content[line_start:position]
    return prefix if prefix.strip() == "" else ""


def _insert_after_tag(content: str, tag: str, new_tag: str, value: str) -> str:
    match = _tag_match(content, tag)
    if not match:
        return content
    indent = _tag_indent(content, match.start())
    insertion = f"\n{indent}<{new_tag}>{value}</{new_tag}>"
    return content[: match.end()] + insertion + content[match.end() :]


def _normalize_atom_icons(content: str) -> str:
    """Expose a lone Atom icon/logo through both metadata slots."""
    if "<feed" not in content:
        return content

    icon = _tag_match(content, "icon")
    logo = _tag_match(content, "logo")

    if not icon and logo:
        return _insert_after_tag(content, "logo", "icon", logo.group("value"))
    if icon and not logo:
        return _insert_after_tag(content, "icon", "logo", icon.group("value"))
    return content


def normalize_feed_file(path: Path) -> bool:
    """Normalize self-link and favicon metadata in one generated feed file."""
    content = path.read_text(encoding="utf-8")
    normalized = content.replace(LEGACY_PREFIX, CURRENT_PREFIX)
    normalized = _normalize_atom_icons(normalized)
    if normalized == content:
        return False
    path.write_text(normalized, encoding="utf-8")
    logger.info("Normalized feed metadata in %s", path.name)
    return True


def normalize_feed_self_links(feeds_dir: Path = FEEDS_DIR) -> list[Path]:
    """Normalize all generated XML feeds and return the files changed."""
    changed: list[Path] = []
    for path in sorted(feeds_dir.glob("feed_*.xml")):
        if normalize_feed_file(path):
            changed.append(path)
    return changed


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    try:
        changed = normalize_feed_self_links()
    except OSError as exc:
        logger.error("Could not normalize generated feed metadata: %s", exc)
        return 1
    logger.info("Normalized metadata in %d feed(s)", len(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
