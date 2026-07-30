"""FFmpeg feed: official project news and source-code activity."""

import argparse
import sys

from multi_rss import run

FEED_NAME = "ffmpeg"
BLOG_URL = "https://ffmpeg.org/"

SOURCES = [
    ("FFmpeg News", "https://ffmpeg.org/main.rss", 80),
    ("FFmpeg Code", "https://code.ffmpeg.org/FFmpeg.rss", 120),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="FFmpeg",
        subtitle="Official FFmpeg project news and source-code activity.",
        blog_url=BLOG_URL,
        author="FFmpeg project",
        sources=SOURCES,
        max_entries=200,
        per_source_cap={"FFmpeg News": 80, "FFmpeg Code": 120, "": 30},
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined FFmpeg Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
