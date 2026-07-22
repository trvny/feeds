"""Normalize legacy raw-GitHub Atom self-link paths in generated feeds."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
FEEDS_DIR = ROOT_DIR / "feeds"
LEGACY_PREFIX = "https://raw.githubusercontent.com/trvny/feeds/main/feeds/"
CURRENT_PREFIX = "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/"


def normalize_feed_file(path: Path) -> bool:
    """Rewrite the legacy self-link prefix in one generated feed file."""
    content = path.read_text(encoding="utf-8")
    normalized = content.replace(LEGACY_PREFIX, CURRENT_PREFIX)
    if normalized == content:
        return False
    path.write_text(normalized, encoding="utf-8")
    logger.info("Normalized Atom self link in %s", path.name)
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
        logger.error("Could not normalize generated feed self links: %s", exc)
        return 1
    logger.info("Normalized self links in %d feed(s)", len(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
