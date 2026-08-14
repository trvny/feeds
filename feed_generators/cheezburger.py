"""Cheezburger network feed: combined Atom from the network's native RSS feeds.

Sources (all native RSS; descriptions keep their HTML so the meme images stay
embedded): the main cheezburger.com feed plus FAIL Blog, CheezCake, Memebase,
I Can Has Cheezburger, and Geek Universe sub-sites.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "cheezburger"

SOURCES = [
    ("Cheezburger", "https://www.cheezburger.com/rss", 40),
    ("FAIL Blog", "https://failblog.cheezburger.com/rss", 40),
    ("CheezCake", "https://cheezcake.cheezburger.com/rss", 40),
    ("Memebase", "https://memebase.cheezburger.com/rss", 40),
    ("I Can Has Cheezburger", "https://icanhas.cheezburger.com/rss", 40),
    ("Geek Universe", "https://geek.cheezburger.com/rss", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Cheezburger Network",
        subtitle="Combined feed of the Cheezburger network: Cheezburger, FAIL Blog, "
                 "CheezCake, Memebase, I Can Has Cheezburger, and Geek Universe.",
        blog_url="https://www.cheezburger.com/",
        author="Cheezburger",
        sources=SOURCES,
        keep_html=True,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Cheezburger Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
