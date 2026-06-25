"""Wikipedia (PL) feed: combined Atom from Polish Wikimedia native feeds —
the Wikimedia Polska chapter blog, the Polish Diff blog, and the pl.wikipedia
featured-content feeds (featured article, On this day, Did you know), plus the
Polish-localized Wikimedia Commons Picture and Media of the day.

All sources are native Atom/RSS, so this is a pure aggregation. The
pl.wikipedia ``potd`` (picture of the day) featured feed is intentionally
excluded: it returns no items — the Polish POTD is served by Commons
(``commons ... feed=potd&language=pl``), which is included instead.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "wikipedia_pl"

_PLWIKI = "https://pl.wikipedia.org/w/api.php?action=featuredfeed&feedformat=atom&feed={f}"
_COMMONS = ("https://commons.wikimedia.org/w/api.php?action=featuredfeed"
            "&feedformat=atom&language=pl&feed={f}")

SOURCES = [
    ("Wikimedia Polska", "https://wikimedia.pl/feed/", 30),
    ("Diff (PL)", "https://diff.wikimedia.org/pl/feed/", 30),
    ("Artykuł na medal", _PLWIKI.format(f="featured"), 30),
    ("Czy wiesz...?", _PLWIKI.format(f="dyk"), 30),
    ("Tego dnia", _PLWIKI.format(f="onthisday"), 30),
    ("Commons — zdjęcie dnia", _COMMONS.format(f="potd"), 30),
    ("Commons — multimedia dnia", _COMMONS.format(f="motd"), 30),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Wikipedia (PL)",
        subtitle="Combined Polish Wikimedia feed: the Wikimedia Polska chapter "
                 "blog, the Diff (PL) blog, pl.wikipedia featured content "
                 "(featured article, Did you know, On this day), and the "
                 "Polish Wikimedia Commons picture and media of the day.",
        blog_url="https://pl.wikipedia.org/",
        author="Wikimedia",
        sources=SOURCES,
        language="pl",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Wikipedia (PL) Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
