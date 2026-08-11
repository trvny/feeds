"""Normalize generated feed metadata after each generator run.

Besides fixing legacy raw-GitHub self links, make Atom icon metadata deliberately
redundant: readers disagree on whether they inspect ``<icon>`` or ``<logo>``.
Mirroring the favicon into a missing logo gives both camps the same usable hint.
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

# YouTube's blog currently exposes Google's generic mark through the usual
# favicon guess, while its own page advertises this YouTube icon explicitly.
ATOM_ICON_OVERRIDES = {
    "youtube": (
        "https://blog.youtube/static/blog_youtube/images/favicon.ico"
        "?version=pr20260729-1718"
    ),
}

# Trójka already has a raster <icon>, but its separate <logo> is SVG. Some feed
# readers accept one and not the other, so use the reader-friendly icon in both
# slots for this feed.
MIRROR_ICON_TO_LOGO = {"trojka"}

_TAG_RE = {
    tag: re.compile(
        rf"^(?P<indent>\s*)<{tag}>(?P<value>[^<]*)</{tag}>\s*$",
        re.MULTILINE,
    )
    for tag in ("icon", "logo")
}


def _feed_name(path: Path) -> str:
    return path.stem.removeprefix("feed_")


def _tag_match(content: str, tag: str):
    return _TAG_RE[tag].search(content)


def _replace_tag(content: str, tag: str, value: str) -> str:
    match = _tag_match(content, tag)
    if not match:
        return content
    replacement = f"{match.group('indent')}<{tag}>{value}</{tag}>"
    return content[: match.start()] + replacement + content[match.end() :]


def _insert_after_tag(content: str, tag: str, new_tag: str, value: str) -> str:
    match = _tag_match(content, tag)
    if not match:
        return content
    indent = match.group("indent")
    insertion = f"\n{indent}<{new_tag}>{value}</{new_tag}>"
    return content[: match.end()] + insertion + content[match.end() :]


def _normalize_atom_icons(content: str, feed_name: str) -> str:
    """Expose the same favicon through the common Atom icon/logo slots."""
    if "<feed" not in content:
        return content

    override = ATOM_ICON_OVERRIDES.get(feed_name)
    if override and _tag_match(content, "icon"):
        content = _replace_tag(content, "icon", override)

    icon = _tag_match(content, "icon")
    logo = _tag_match(content, "logo")

    # Be symmetrical for the rare feed that has a logo but no icon.
    if not icon and logo:
        content = _insert_after_tag(content, "logo", "icon", logo.group("value"))
        icon = _tag_match(content, "icon")

    if not icon:
        return content

    icon_value = icon.group("value")
    if logo and feed_name in MIRROR_ICON_TO_LOGO:
        return _replace_tag(content, "logo", icon_value)
    if not logo:
        return _insert_after_tag(content, "icon", "logo", icon_value)
    return content


def normalize_feed_file(path: Path) -> bool:
    """Normalize self-link and favicon metadata in one generated feed file."""
    content = path.read_text(encoding="utf-8")
    normalized = content.replace(LEGACY_PREFIX, CURRENT_PREFIX)
    normalized = _normalize_atom_icons(normalized, _feed_name(path))
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
