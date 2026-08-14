"""GOG feed: combined Atom from GOG's own newsroom surfaces.

All sources are native WordPress-style RSS feeds:

  * GOG Blog (``/blog/feed/``) — editorial posts, sales, curated lists
  * GOG Pressroom (``/pressroom/feed/``) — press releases
  * GOG News PL / EN (``/{lang}/news/feed``) — the storefront news column;
    the two locales carry the same stories translated, so they are kept at a
    small cap each and the cross-source dedupe in ``multi_rss`` only catches
    the ones that share a link.

``/news/rss`` (no locale prefix) returns a 200 with an empty channel and is
deliberately not used.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "gog"

SOURCES = [
    ("GOG Blog", "https://www.gog.com/blog/feed/", 40),
    ("GOG Pressroom", "https://www.gog.com/pressroom/feed/", 40),
    ("GOG News (PL)", "https://www.gog.com/pl/news/feed", 20),
    ("GOG News (EN)", "https://www.gog.com/en/news/feed", 20),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="GOG",
        subtitle="Combined GOG feed: the GOG Blog, the Pressroom, and the "
                 "storefront news column in Polish and English.",
        blog_url="https://www.gog.com/blog",
        author="GOG",
        sources=SOURCES,
        max_entries=200,
        per_source_cap=60,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the GOG Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
