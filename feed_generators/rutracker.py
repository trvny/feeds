"""Combined RuTracker Atom feed."""

import argparse
import sys

from multi_rss import run

FEED_NAME = "rutracker"
BLOG_URL = "https://rutracker.org/"

# Specific forums first so duplicate links keep the more useful source label;
# f/0 is the broad catch-all feed and intentionally comes last.
SOURCES = [
    ("RuTracker f/1960", "https://feed.rutracker.cc/atom/f/1960.atom", 60),
    ("RuTracker f/1880", "https://feed.rutracker.cc/atom/f/1880.atom", 60),
    ("RuTracker f/1893", "https://feed.rutracker.cc/atom/f/1893.atom", 60),
    ("RuTracker f/1397", "https://feed.rutracker.cc/atom/f/1397.atom", 60),
    ("RuTracker f/1857", "https://feed.rutracker.cc/atom/f/1857.atom", 60),
    ("RuTracker f/784", "https://feed.rutracker.cc/atom/f/784.atom", 60),
    ("RuTracker f/786", "https://feed.rutracker.cc/atom/f/786.atom", 60),
    ("RuTracker f/1631", "https://feed.rutracker.cc/atom/f/1631.atom", 60),
    ("RuTracker f/2331", "https://feed.rutracker.cc/atom/f/2331.atom", 60),
    ("RuTracker f/0", "https://feed.rutracker.cc/atom/f/0.atom", 100),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="RuTracker",
        subtitle="Combined RuTracker Atom feeds.",
        blog_url=BLOG_URL,
        author="RuTracker",
        sources=SOURCES,
        max_entries=400,
        language="ru",
        full=full,
        image_backfill=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the RuTracker Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
