#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "feed_generators"))

import development  # noqa: E402
from multi_rss import scrape_feed  # noqa: E402
from utils import dedupe_entries, merge_entries  # noqa: E402


def main():
    collected = []
    print("== native feeds ==")
    for label, url, cap in development.SOURCES:
        entries = scrape_feed(label, url, set(), cap=cap)
        print(f"{label}: {len(entries)} entries")
        if not entries:
            raise SystemExit(f"no entries from {label}")
        if label == "Django Packages latest" and len(entries) > 3:
            raise SystemExit("Django Packages latest exceeded cap=3")
        collected.extend(entries)

    print("\n== HTML adapters ==")
    rust = development.scrape_rust_releases(set())
    changelog = development.scrape_django_packages_changelog(set())
    print(f"Rust Releases: {len(rust)} entries")
    print(f"Django Packages changelog: {len(changelog)} entries")
    if not rust or not changelog:
        raise SystemExit("an HTML adapter returned no entries")
    collected.extend(rust)
    collected.extend(changelog)

    merged = merge_entries(collected, [], id_field="link", date_field="date")
    deduped = dedupe_entries(merged)
    print(f"\ncombined: {len(collected)} fetched, {len(deduped)} after dedupe")
    if not deduped:
        raise SystemExit("combined source set is empty after dedupe")


if __name__ == "__main__":
    main()
