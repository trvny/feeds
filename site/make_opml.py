#!/usr/bin/env python3
"""Generate subscriptions.opml from the published feed set.

Reuses build_site's feed discovery (published_feeds.txt selection + live
titles parsed from each feed_*.xml) so the OPML always lists exactly what the
site publishes — no dead xmlUrls, custom title overrides carried through.

Writes site/subscriptions.opml (committed convenience copy for the local
reader) and, when public/ exists, public/subscriptions.opml (the deployed
copy). Pure stdlib, but run as ``uv run --locked site/make_opml.py`` so it
gets the pinned interpreter rather than whatever ``python3`` resolves to.
"""
from __future__ import annotations

import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SITE_DIR))
from build_site import build_opml, collect_feeds, site_base_url  # noqa: E402

OUT_DIR = SITE_DIR.parent / "public"


def main() -> None:
    feeds = collect_feeds()
    if not feeds:
        raise SystemExit("No feeds found — nothing to write into subscriptions.opml.")
    opml = build_opml(feeds, site_base_url())
    (SITE_DIR / "subscriptions.opml").write_text(opml, encoding="utf-8")
    if OUT_DIR.exists():
        (OUT_DIR / "subscriptions.opml").write_text(opml, encoding="utf-8")
    print(f"Wrote subscriptions.opml ({len(feeds)} feeds)")


if __name__ == "__main__":
    main()
