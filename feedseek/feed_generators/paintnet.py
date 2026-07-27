"""Paint.NET feed: the official blog plus the busiest forum boards.

The forum boards expose per-board RSS, but the items come back in board order
rather than by date (pinned and long-running topics sit at the top), so entry
dates span 2006 to today in a single fetch. multi_rss sorts and caps by date,
and the per-source quota keeps the fast-moving plugin board from crowding out
the quieter ones.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "paintnet"

FORUM = "https://forums.paint.net/forum"

SOURCES = [
    ("Paint.NET Blog", "https://blog.paint.net/feed/", 20),
    ("Plugins (publishing only)", f"{FORUM}/7-plugins-publishing-only.xml/", 25),
    ("Preview Center", f"{FORUM}/45-preview-center.xml/", 25),
    ("The Pictorium", f"{FORUM}/16-the-pictorium.xml/", 25),
    ("Beginner Tutorials", f"{FORUM}/20-beginner-tutorials.xml/", 25),
    ("Miscellaneous", f"{FORUM}/24-miscellaneous.xml/", 25),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Paint.NET",
        subtitle="Paint.NET blog releases plus the plugins, preview center, "
                 "pictorium, beginner tutorials and miscellaneous forum boards.",
        blog_url="https://blog.paint.net/",
        author="Paint.NET",
        sources=SOURCES,
        max_entries=200,
        per_source_cap=30,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Paint.NET Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
