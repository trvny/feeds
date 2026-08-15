"""Oracle feed: product, developer, Java, Linux, cloud and company news.

Specific Oracle channels precede the broad Oracle Blogs feed so shared title/URL
dedupe keeps the more useful source label. Forum, podcast and low-volume niche
sources use small intake/published caps. ``https://dev.java/news/`` is not
scraped separately: its news list points back to Inside Java, whose native
``https://inside.java/feed.xml`` is the maintained source of truth here.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "oracle"
BLOG_URL = "https://blogs.oracle.com/"

SOURCES = [
    ("Oracle Developers", "https://blogs.oracle.com/developers/feed", 20),
    ("Oracle Java", "https://blogs.oracle.com/java/feed", 18),
    ("Oracle Linux", "https://blogs.oracle.com/linux/feed", 16),
    (
        "Oracle Cloud Infrastructure",
        "https://blogs.oracle.com/cloud-infrastructure/feed",
        18,
    ),
    ("Oracle Virtualization", "https://blogs.oracle.com/virtualization/feed", 12),
    ("Oracle Connect", "https://blogs.oracle.com/connect/feed", 15),
    ("Oracle Scoter", "https://blogs.oracle.com/scoter/feed", 8),
    (
        "Oracle Developer Community",
        "https://forums.oracle.com/ords/apexds/feeds/domain/dev-community/",
        10,
    ),
    ("Inside Java", "https://inside.java/feed.xml", 20),
    (
        "Inside Java Podcast",
        "https://rss.libsyn.com/shows/294923/destinations/2318780.xml",
        10,
    ),
    (
        "Oracle Press Releases",
        "https://www.oracle.com/corporate/press/rss/rss-pr.xml",
        18,
    ),
    ("Oracle Blogs", "https://blogs.oracle.com/feed", 24),
]

PER_SOURCE_QUOTA = {
    "": 24,
    "Oracle Developers": 28,
    "Oracle Java": 24,
    "Oracle Linux": 22,
    "Oracle Cloud Infrastructure": 26,
    "Oracle Virtualization": 18,
    "Oracle Connect": 20,
    "Oracle Scoter": 10,
    "Oracle Developer Community": 14,
    "Inside Java": 26,
    "Inside Java Podcast": 12,
    "Oracle Press Releases": 22,
    "Oracle Blogs": 28,
}


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Oracle",
        subtitle=(
            "Oracle company and developer news: Java, Linux, OCI, virtualization, "
            "community, press releases and Inside Java."
        ),
        blog_url=BLOG_URL,
        author="Oracle",
        sources=SOURCES,
        max_entries=200,
        per_source_cap=PER_SOURCE_QUOTA,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Oracle Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
