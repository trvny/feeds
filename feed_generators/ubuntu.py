"""Ubuntu feed: official Canonical/Ubuntu sources plus selected community news.

The official Ubuntu and Canonical blogs intentionally overlap. Specific Ubuntu
items are listed first so shared title-based dedupe keeps the Ubuntu label.
Planet Ubuntu and high-volume community feeds use bounded intake/published caps
so they cannot crowd out quieter project sources.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "ubuntu"
BLOG_URL = "https://ubuntu.com/blog"

SOURCES = [
    ("Ubuntu Blog", "https://ubuntu.com/blog/feed", 24),
    ("Canonical Blog", "https://canonical.com/blog/feed", 20),
    ("Ubuntu Studio", "https://ubuntustudio.org/feed/", 12),
    ("Planet Ubuntu", "https://planet.ubuntu.com/feed", 24),
    ("OMG! Ubuntu", "https://www.omgubuntu.co.uk/feed", 20),
    (
        "UbuntuHandbook",
        "https://feeds.feedburner.com/UbuntuhandbookNewsTutorialsHowtosForUbuntuLinux",
        14,
    ),
]

PER_SOURCE_QUOTA = {
    "": 24,
    "Ubuntu Blog": 36,
    "Canonical Blog": 28,
    "Ubuntu Studio": 16,
    "Planet Ubuntu": 28,
    "OMG! Ubuntu": 28,
    "UbuntuHandbook": 18,
}


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Ubuntu",
        subtitle=(
            "Ubuntu and Canonical news, Planet Ubuntu, Ubuntu Studio, "
            "OMG! Ubuntu and UbuntuHandbook."
        ),
        blog_url=BLOG_URL,
        author="Ubuntu community",
        sources=SOURCES,
        max_entries=160,
        per_source_cap=PER_SOURCE_QUOTA,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Ubuntu Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
