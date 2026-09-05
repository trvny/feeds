"""Standalone Hugging Face Trending Papers feed."""

import argparse
import sys

from huggingface import TRENDING_PAPERS_URL, collect_trending_papers
from multi_rss import run
from utils import favicon_proxy

FEED_NAME = "hf_trending_papers"


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Hugging Face — Trending Papers",
        subtitle="Trending research papers from the Hugging Face community.",
        blog_url=TRENDING_PAPERS_URL,
        author="Hugging Face",
        extra_scrapers=(collect_trending_papers,),
        max_entries=200,
        dedupe_title_field=None,
        icon=favicon_proxy("huggingface.co"),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Hugging Face Trending Papers feed"
    )
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
