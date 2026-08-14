#!/usr/bin/env python3
"""Mirror feeds embedded in released pre-split Kanarek clients."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "feeds"
TARGET = ROOT / "feedseek" / "feeds"

# Historical compatibility contract. Do not automatically track future defaults
# from the standalone Kanarek repository: these names are the Feedseek URLs
# already embedded in released pre-split APKs.
RELEASED_DEFAULT_FEEDS = (
    "pap",
    "reuters",
    "wikipedia_pl",
    "daily_digest",
    "daily_quote",
    "jbzd",
    "beatport_top100",
    "cloudflare",
)


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    expected: set[str] = set()
    for name in RELEASED_DEFAULT_FEEDS:
        for suffix in ("xml", "json"):
            source = SOURCE / f"feed_{name}.{suffix}"
            if source.exists():
                target = TARGET / source.name
                shutil.copyfile(source, target)
                if source.read_bytes() != target.read_bytes():
                    raise OSError(f"Legacy mirror verification failed for {source.name}")
                expected.add(target.name)
    for path in TARGET.glob("feed_*.*"):
        if path.name not in expected:
            path.unlink()


if __name__ == "__main__":
    main()
