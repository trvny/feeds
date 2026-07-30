"""MIT News feed: combined official latest, research, and campus RSS channels."""

import argparse
import sys

from multi_rss import run

FEED_NAME = "mit"
BLOG_URL = "https://news.mit.edu/"

# Put the narrower feeds first so duplicate articles retain the most useful
# category label; the broad Latest feed then fills in everything else.
SOURCES = [
    ("MIT Research", "https://news.mit.edu/rss/research", 100),
    ("MIT Campus", "https://news.mit.edu/rss/campus", 60),
    ("MIT Latest", "https://news.mit.edu/rss/feed", 100),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="MIT News",
        subtitle="Official MIT News: research, campus, and latest articles.",
        blog_url=BLOG_URL,
        author="MIT News Office",
        sources=SOURCES,
        max_entries=200,
        per_source_cap={
            "MIT Research": 100,
            "MIT Campus": 60,
            "MIT Latest": 80,
            "": 40,
        },
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined MIT News Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
