"""Microsoft feed: combined Atom from Microsoft's native RSS feeds — the
Official Microsoft Blog, On the Issues, Research, Source (global + EMEA PL),
Signal, Unlocked (PL), the Microsoft 365 Blog, DevBlogs, the Microsoft 365
Developer changelog, and the Tech Community blogs firehose."""

import argparse
import sys

from multi_rss import run

FEED_NAME = "microsoft"

SOURCES = [
    ("Official Microsoft Blog", "https://blogs.microsoft.com/feed/", 40),
    ("Microsoft On the Issues", "https://blogs.microsoft.com/on-the-issues/feed/", 40),
    ("Microsoft Research", "https://www.microsoft.com/en-us/research/feed/", 40),
    ("Microsoft Source", "https://news.microsoft.com/source/feed/", 40),
    ("Microsoft Source EMEA (PL)", "https://news.microsoft.com/source/emea/feed/?lang=pl", 40),
    ("Microsoft Signal", "https://news.microsoft.com/signal/feed", 40),
    ("Microsoft Unlocked (PL)", "https://unlocked.microsoft.com/pl/feed/", 40),
    ("Microsoft 365 Blog", "https://www.microsoft.com/en-us/microsoft-365/blog/feed/", 40),
    ("Microsoft DevBlogs", "https://devblogs.microsoft.com/feed", 40),
    ("Microsoft 365 Developer Changelog", "https://developer.microsoft.com/api/changelog/rss", 40),
    ("Tech Community",
     "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/Community"
     "?interaction.style=blog&feeds.replies=false", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Microsoft",
        subtitle="Combined Microsoft feed: Official Microsoft Blog, On the "
                 "Issues, Research, Source (global + EMEA PL), Signal, "
                 "Unlocked (PL), the Microsoft 365 Blog, DevBlogs, the "
                 "Microsoft 365 Developer changelog, and the Tech Community "
                 "blogs.",
        blog_url="https://blogs.microsoft.com/",
        author="Microsoft",
        sources=SOURCES,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Microsoft Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
