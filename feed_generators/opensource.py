"""Open Source / open-standards feed: combined Atom from Creative Commons,
the Open Source Initiative, the Linux Foundation, SPDX, the Open Geospatial
Consortium, the RFC Editor, and IETF status. Renamed from creativecommons.py — this feed now
covers open-licensing and open-standards bodies generally, not just CC.

All sources are native RSS/Atom feeds (multi_rss SOURCES) — no scraping:

  * Creative Commons  https://creativecommons.org/feed/ (the ``/blog/feed/``
                      path is a stale comments feed — don't use it)
  * OSI               https://opensource.org/feed
  * Linux Foundation  https://www.linuxfoundation.org/blog/rss.xml and
                      .../press/rss.xml — blog and press wire are separate
                      feeds on the same site, both native RSS
  * SPDX              https://spdx.dev/feed/
  * OGC                https://www.ogc.org/feed/ — the only feed the site
                      exposes; /blog/ and /news/ were both requested
                      separately but share this one WordPress feed (no
                      per-section split upstream)
  * RFC Editor        https://www.rfc-editor.org/rfcatom.xml
  * IETF Status       https://status.ietf.org/history.atom (incident log,
                      capped low like the other status feeds elsewhere)

Note: renaming from creativecommons.py changes the cache key (feed_name
"creativecommons" -> "opensource"), so the first run starts from an empty
cache and re-ingests each source's current feed window as "new" — a one-time
bump in feed_opensource.xml, not a bug.

Usage:
    python opensource.py          # incremental (merge into cache)
    python opensource.py --full   # ignore cache, rebuild from sources only
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "opensource"

# (label, url, cap)
SOURCES = [
    ("Creative Commons", "https://creativecommons.org/feed/", 30),
    ("Open Source Initiative", "https://opensource.org/feed", 20),
    ("Linux Foundation", "https://www.linuxfoundation.org/blog/rss.xml", 30),
    ("Linux Foundation Press", "https://www.linuxfoundation.org/press/rss.xml", 20),
    ("SPDX", "https://spdx.dev/feed/", 20),
    ("OGC", "https://www.ogc.org/feed/", 20),
    ("RFC Editor", "https://www.rfc-editor.org/rfcatom.xml", 30),
    ("IETF Status", "https://status.ietf.org/history.atom", 10),
    # ogp.me itself has no feed (the .rdf is the frozen OGP vocabulary, not a
    # changelog); the spec's hosting repo commit feed is the real change stream.
    ("Open Graph protocol", "https://github.com/facebook/open-graph-protocol/commits/master.atom", 15),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Open Source",
        subtitle="Open-licensing and open-standards bodies: Creative Commons, "
                 "the Open Source Initiative, the Linux Foundation, SPDX, the "
                 "Open Geospatial Consortium, the RFC Editor, IETF status, and "
                 "the Open Graph protocol.",
        blog_url="https://creativecommons.org/blog/",
        author="various",
        sources=SOURCES,
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Open Source Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
