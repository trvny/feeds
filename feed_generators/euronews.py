"""Euronews feed: combined feed from Euronews' native per-section MRSS feeds
(News, My Europe, No Comment, Culture, Sport, Travel, Next), EN + PL editions.

Both editions are fetched in MRSS (format=mrss: RSS 2.0 + media: namespace)
rather than Atom -- same section coverage, but items carry media:content
thumbnails that the Atom variant drops. multi_rss.scrape_feed parses <item>
generically, so no format-specific handling is needed.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "euronews"

_EN_BASE = "https://www.euronews.com/rss?format=mrss&level={level}&name={name}"
_PL_BASE = "https://pl.euronews.com/rss?format=mrss&level={level}&name={name}"

# (level, name, label suffix) -- same section set on both editions.
_SECTIONS = [
    ("theme", "news", "News"),
    ("vertical", "my-europe", "My Europe"),
    ("program", "nocomment", "No Comment"),
    ("vertical", "culture", "Culture"),
    ("theme", "sport", "Sport"),
    ("vertical", "travel", "Travel"),
    ("vertical", "next", "Next"),
]

SOURCES = (
    [(label, _EN_BASE.format(level=level, name=name), 40) for level, name, label in _SECTIONS]
    + [(f"{label} (PL)", _PL_BASE.format(level=level, name=name), 40) for level, name, label in _SECTIONS]
)


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Euronews",
        subtitle="Combined Euronews feed (MRSS): News, My Europe, No Comment, "
                 "Culture, Sport, Travel, and Next -- English and Polish editions.",
        blog_url="https://www.euronews.com/",
        author="Euronews",
        sources=SOURCES,
        max_entries=400,  # 14 sources now (EN + PL editions); default 200 was starving whole sections
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Euronews Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
