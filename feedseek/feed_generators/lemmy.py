"""Combined Lemmy feed with cross-instance duplicate removal.

Federated posts can appear in several instance feeds under different local
URLs. The shared ``multi_rss`` pipeline deduplicates them by normalized target
URL and, for local/self posts, normalized title.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "lemmy"

SOURCES = [
    ("Lemmy.world", "https://lemmy.world/feeds/all.xml?sort=TopWeek", 50),
    ("Szmer", "https://szmer.info/feeds/local.xml?sort=Scaled", 50),
    ("Lemmy.org", "https://lemmy.org/feeds/all.xml?sort=Hot", 50),
    ("Lemmy.ml", "https://lemmy.ml/feeds/all.xml?sort=Active", 50),
    ("sh.itjust.works", "https://sh.itjust.works/feeds/all.xml", 50),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Lemmy",
        subtitle=(
            "Combined Lemmy feed from Lemmy.world, Szmer, Lemmy.org, Lemmy.ml "
            "and sh.itjust.works, deduplicated across federated instances."
        ),
        blog_url="https://join-lemmy.org/",
        author="Various Lemmy communities",
        sources=SOURCES,
        max_entries=250,
        per_source_cap=50,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Lemmy Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
