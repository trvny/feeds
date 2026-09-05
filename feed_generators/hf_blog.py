"""Standalone Hugging Face Blog feed using the native upstream RSS."""

import argparse
import sys

from multi_rss import run
from utils import favicon_proxy

FEED_NAME = "hf_blog"
BLOG_URL = "https://huggingface.co/blog"
SOURCES = [("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", 80)]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Hugging Face — Blog",
        subtitle="Hugging Face Blog articles from the native upstream feed.",
        blog_url=BLOG_URL,
        author="Hugging Face",
        sources=SOURCES,
        max_entries=200,
        icon=favicon_proxy("huggingface.co"),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Hugging Face Blog feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
