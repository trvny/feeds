#!/usr/bin/env python3
"""Generate subscriptions.opml from the published feed set.

Reuses build_site's feed discovery (published_feeds.txt selection + live
titles parsed from each feed_*.xml) so the OPML always lists exactly what the
site publishes — no dead xmlUrls, custom title overrides carried through.

Writes site/subscriptions.opml (committed convenience copy for the local
reader) and, when public/ exists, public/subscriptions.opml (the deployed
copy). Pure stdlib; run with plain python3.
"""
from __future__ import annotations

import html
import sys
from datetime import datetime, timezone
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SITE_DIR))
from build_site import collect_feeds, site_base_url  # noqa: E402

OUT_DIR = SITE_DIR.parent / "public"


def build_opml(feeds: list[dict], base: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<opml version="2.0">',
        "  <head>",
        "    <title>trvny subscriptions</title>",
        f"    <dateModified>{stamp}</dateModified>",
        "  </head>",
        "  <body>",
    ]
    for f in feeds:
        text = html.escape(f["title"], quote=True)
        attrs = (
            f'type="rss" text="{text}" title="{text}" '
            f'xmlUrl="{html.escape(base + f["filename"], quote=True)}"'
        )
        if f["source"]:
            attrs += f' htmlUrl="{html.escape(f["source"], quote=True)}"'
        lines.append(f"    <outline {attrs} />")
    lines += ["  </body>", "</opml>"]
    return "\n".join(lines) + "\n"


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
