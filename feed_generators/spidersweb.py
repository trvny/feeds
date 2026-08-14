"""Spider's Web feed: combined Atom from the Spider's Web group's native
"feed-gn" RSS feeds — the main tech site, Rozrywka (entertainment), Autoblog
(automotive), Bizblog (business), and the sibling Bezprawnik (law/consumer).

All sources are native RSS, so this is a pure aggregation with per-source
``<category>`` labels and cross-source dedupe.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "spidersweb"

SOURCES = [
    ("Spider's Web", "https://spidersweb.pl/api/post/feed/feed-gn", 50),
    ("Rozrywka", "https://rozrywka.spidersweb.pl/api/feed/feed-gn", 50),
    ("Autoblog", "https://autoblog.spidersweb.pl/api/feed/feed-gn", 50),
    ("Bizblog", "https://bizblog.spidersweb.pl/api/feed/feed-gn", 50),
    ("Bezprawnik", "https://bezprawnik.pl/api/feed-gn/", 50),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Spider's Web",
        subtitle="Combined Spider's Web feed: the main site, Rozrywka, "
                 "Autoblog, Bizblog, and Bezprawnik.",
        blog_url="https://spidersweb.pl/",
        author="Spider's Web",
        sources=SOURCES,
        language="pl",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Spider's Web Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
