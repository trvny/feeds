"""Spotify feed: the company newsroom plus the developer-platform changelog."""

import argparse
import sys

from multi_rss import run

FEED_NAME = "spotify"

SOURCES = [
    ("Spotify Newsroom", "https://newsroom.spotify.com/feed/", 20),
    ("Spotify for Developers", "https://developer.spotify.com/rss.xml", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Spotify",
        subtitle="Spotify newsroom announcements and the Spotify for Developers "
                 "platform changelog.",
        blog_url="https://newsroom.spotify.com/",
        author="Spotify",
        sources=SOURCES,
        max_entries=150,
        per_source_cap=60,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Spotify Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
