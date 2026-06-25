"""Euronews feed: combined Atom from Euronews' native per-section Atom feeds
(News, My Europe, No Comment, Culture, Sport, Travel, Next)."""

import argparse
import sys

from multi_rss import run

FEED_NAME = "euronews"

_BASE = "https://www.euronews.com/rss?format=atom&level={level}&name={name}"

SOURCES = [
    ("News", _BASE.format(level="theme", name="news"), 40),
    ("My Europe", _BASE.format(level="vertical", name="my-europe"), 40),
    ("No Comment", _BASE.format(level="program", name="nocomment"), 40),
    ("Culture", _BASE.format(level="vertical", name="culture"), 40),
    ("Sport", _BASE.format(level="theme", name="sport"), 40),
    ("Travel", _BASE.format(level="vertical", name="travel"), 40),
    ("Next", _BASE.format(level="vertical", name="next"), 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Euronews",
        subtitle="Combined Euronews feed: News, My Europe, No Comment, Culture, "
                 "Sport, Travel, and Next.",
        blog_url="https://www.euronews.com/",
        author="Euronews",
        sources=SOURCES,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Euronews Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
