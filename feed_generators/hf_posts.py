"""Standalone Hugging Face community Posts feed."""

import argparse
import sys

from huggingface import POSTS_URL, collect_posts
from multi_rss import run
from utils import favicon_proxy

FEED_NAME = "hf_posts"


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Hugging Face — Posts",
        subtitle="Community posts published on the Hugging Face Hub.",
        blog_url=POSTS_URL,
        author="Hugging Face",
        extra_scrapers=(collect_posts,),
        max_entries=200,
        dedupe_title_field=None,
        icon=favicon_proxy("huggingface.co"),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Hugging Face Posts feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
