"""Radios feed: internet-radio stations and platforms, combined.

    - TuneIn                   https://cms.tunein.com/feed/
    - Radio Maxi Italo         https://radiomaxitalo.com/feed/
    - Electro Swing Radio      https://electroswing-radio.com/feed/
    - Electro Swing Thing      https://electroswingthing.com/feed/

All four are WordPress RSS. TuneIn and Electro Swing Radio currently publish a
well-formed but *empty* channel (no <item> at all) — they're kept registered so
the feed picks them up the moment they start posting; ``scrape_feed`` just logs
a warning and returns nothing for an empty source, which never fails the run.
Electro Swing Thing has been dormant since 2020 and is included for its
archive; the combined feed's freshness comes from Radio Maxi Italo.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "radios"

SOURCES = [
    ("TuneIn", "https://cms.tunein.com/feed/", 40),
    ("Radio Maxi Italo", "https://radiomaxitalo.com/feed/", 40),
    ("Electro Swing Radio", "https://electroswing-radio.com/feed/", 40),
    ("Electro Swing Thing", "https://electroswingthing.com/feed/", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Radios",
        subtitle="Internet radio: TuneIn, Radio Maxi Italo, Electro Swing Radio, Electro Swing Thing.",
        blog_url="https://tunein.com/",
        author="Radios",
        sources=SOURCES,
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Radios Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
