"""Visual Crossing resources feed: the vendor's own news, blog and
documentation streams.

Kept separate from the ``visualcrossing`` feed, which is a location forecast
built from the Timeline API — its entries are keyed by forecast day and are
refreshed in place as the forecast is revised, so editorial posts don't belong
in it.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "visualcrossing_blog"

SOURCES = [
    ("Visual Crossing News", "https://www.visualcrossing.com/resources/category/news/feed/", 15),
    ("Visual Crossing Blog", "https://www.visualcrossing.com/resources/category/blog/feed/", 20),
    ("Visual Crossing Documentation",
     "https://www.visualcrossing.com/resources/category/documentation/feed/", 20),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Visual Crossing Resources",
        subtitle="Visual Crossing news, blog posts and documentation updates.",
        blog_url="https://www.visualcrossing.com/resources/",
        author="Visual Crossing",
        sources=SOURCES,
        max_entries=150,
        per_source_cap=40,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Visual Crossing resources Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
