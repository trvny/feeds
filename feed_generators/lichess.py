"""Lichess feed: the official Lichess update blog plus the community blogs.

Three native Atom feeds, merged into one:

    - Lichess updates          https://lichess.org/feed.atom
    - Community blogs (PL)     https://lichess.org/blog/community.atom?lang=pl
    - Community blogs (EN)     https://lichess.org/blog/community.atom?lang=en

The two community feeds are the same endpoint filtered by post language, so
they carry disjoint sets in practice; ``dedupe_entries`` in multi_rss covers
the rest if a post ever appears in both.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "lichess"

SOURCES = [
    ("Lichess Updates", "https://lichess.org/feed.atom", 60),
    ("Community (PL)", "https://lichess.org/blog/community.atom?lang=pl", 30),
    ("Community (EN)", "https://lichess.org/blog/community.atom?lang=en", 30),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Lichess",
        subtitle="Official Lichess update blog plus the Polish and English community blogs.",
        blog_url="https://lichess.org/blog",
        author="Lichess",
        sources=SOURCES,
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Lichess Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
