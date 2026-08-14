#!/usr/bin/env python3
"""Mirror released Kanarek default feeds at their historical raw paths."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "feeds"
TARGET = ROOT / "feedseek" / "feeds"
NAMES = (
    "pap", "reuters", "wikipedia_pl", "daily_digest", "daily_quote",
    "jbzd", "beatport_top100", "cloudflare",
)


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    expected: set[str] = set()
    for name in NAMES:
        for suffix in ("xml", "json"):
            source = SOURCE / f"feed_{name}.{suffix}"
            if source.exists():
                target = TARGET / source.name
                shutil.copyfile(source, target)
                expected.add(target.name)
    for path in TARGET.glob("feed_*.*"):
        if path.name not in expected:
            path.unlink()


if __name__ == "__main__":
    main()
