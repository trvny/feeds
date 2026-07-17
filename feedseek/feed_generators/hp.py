"""HP feed: combined Atom from HP's native RSS feeds.

Sources:
  * HP Support RSS (support.hp.com) — native RSS, security/driver/support bulletins
  * HPE Newsroom (hpe.com) — native RSS, enterprise press releases

hp.com/us-en/newsroom.html and hppartner.pl have no native feed. A Google
News site: proxy was tried for both but only returns shop product listings
(hppartner.pl) or unrelated pages (hp.com), not press releases — too noisy
to be worth publishing, so they're deliberately left out.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "hp"

SOURCES = [
    ("HP Support", "https://support.hp.com/wcc-widget-services/us-en/rss-feed?category=all", 40),
    ("HPE Newsroom", "https://www.hpe.com/us/en/newsroom/rss.xml", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="HP Newsroom",
        subtitle="Combined HP feed: HP Support bulletins and HPE Newsroom.",
        blog_url="https://www.hp.com/us-en/newsroom.html",
        author="HP",
        sources=SOURCES,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the HP Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
