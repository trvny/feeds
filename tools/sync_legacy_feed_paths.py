#!/usr/bin/env python3
"""Mirror feeds embedded in released pre-split Kanarek clients."""

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "feeds"
TARGET = ROOT / "feedseek" / "feeds"

sys.path.insert(0, str(ROOT / "feed_generators"))
from validate_feeds import validate_feed, validate_json_sidecar

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


def validated_pair(name: str) -> tuple[Path, Path]:
    xml_path = SOURCE / f"feed_{name}.xml"
    json_path = SOURCE / f"feed_{name}.json"
    for path in (xml_path, json_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Required Feedseek artifact missing; preserving legacy mirror: {path}"
            )

    xml_result = validate_feed(xml_path)
    if xml_result["status"] not in {"OK", "STALE"}:
        raise ValueError(
            f"Invalid compatibility XML; preserving legacy mirror: "
            f"{xml_path.name}: {xml_result['status']} {xml_result['message']}"
        )

    json_result = validate_json_sidecar(json_path)
    if json_result["status"] != "OK":
        raise ValueError(
            f"Invalid compatibility JSON; preserving legacy mirror: "
            f"{json_path.name}: {json_result['status']} {json_result['message']}"
        )
    return xml_path, json_path


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    expected: set[str] = set()
    for name in RELEASED_DEFAULT_FEEDS:
        sources = validated_pair(name)
        for source in sources:
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
