"""Xiaomi feed: combined Atom from Xiaomi's native RSS feeds.

Sources:
  * xiaomi.eu community forum (index.rss) — native RSS
  * xiaomiadvices.com — native RSS
  * xiaomitoday.com — native RSS
  * Xiaomi Corporation investor news releases (xiaomi.gcs-web.com) — native RSS

mi.com/global/discover/newsroom and mi.com/in/discover/news have no native
feed; miuipolska.pl's forum RSS is Cloudflare-challenge blocked (403 "Just a
moment..."). Google News site: proxies were tried for all three but only
surface forum threads and support posts, not actual news — too noisy to be
worth publishing, so they're deliberately left out.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "xiaomi"

SOURCES = [
    ("xiaomi.eu community", "https://xiaomi.eu/community/forums/-/index.rss", 40),
    ("Xiaomi Advices", "https://xiaomiadvices.com/feed/", 40),
    ("Xiaomi Today", "https://xiaomitoday.com/feed/", 40),
    ("Xiaomi Corp Investor News", "https://xiaomi.gcs-web.com/rss/news-releases.xml", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Xiaomi Newsroom",
        subtitle="Combined Xiaomi feed: xiaomi.eu community, Xiaomi Advices, "
                 "Xiaomi Today, and Xiaomi Corp investor news.",
        blog_url="https://www.mi.com/global/discover/newsroom",
        author="Xiaomi",
        sources=SOURCES,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Xiaomi Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
