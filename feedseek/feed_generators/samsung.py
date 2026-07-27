"""Samsung Newsroom feed: combined Atom from Samsung's public newsrooms,
developer and product blogs, and the Polish community board.

All sources are native RSS:

  * Samsung Newsroom global + PL (``news.samsung.com``); the US newsroom
    403s both clients from datacenter IPs and is left out
  * Samsung Mobile Press (``samsungmobilepress.com``) — device press releases
  * Samsung Developers (``developer.samsung.com``)
  * Samsung NEXT (Squarespace ``?format=rss``) — low volume, kept anyway
  * SmartThings blog
  * Samsung Community PL — Khoros board RSS

Fetch note: ``news.samsung.com/pl`` 403s a plain request and needs the
curl_cffi Chrome impersonation, while ``news.samsung.com/global`` 403s the
*impersonated* request and only answers a plain one. ``multi_rss.get_html``
tries the impersonated request first and retries plainly on a non-200, so both
work without per-source fetch code here.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "samsung"

SOURCES = [
    ("Samsung Newsroom", "https://news.samsung.com/global/feed", 50),
    ("Samsung Newsroom PL", "https://news.samsung.com/pl/feed", 30),
    ("Samsung Mobile Press", "https://www.samsungmobilepress.com/feed", 30),
    ("Samsung Developers", "https://developer.samsung.com/feed", 30),
    ("Samsung NEXT", "https://www.samsungnext.com/blog?format=rss", 20),
    ("SmartThings", "https://blog.smartthings.com/feed/", 30),
    (
        "Samsung Community PL",
        "https://eu.community.samsung.com/bgros26334/rss/Category?category.id=pl&interaction.style=blog",
        30,
    ),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Samsung Newsroom",
        subtitle="Combined Samsung feed: Newsroom global and PL, Mobile "
        "Press, Samsung Developers, Samsung NEXT, SmartThings, and "
        "the Polish Samsung Community board.",
        blog_url="https://news.samsung.com/global/",
        author="Samsung",
        sources=SOURCES,
        max_entries=200,
        per_source_cap=30,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Samsung Newsroom Atom feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
