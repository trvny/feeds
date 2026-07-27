"""DaTime feed: time, calendars, astronomy and holidays, combined.

    - timeanddate     Time Zone News    https://rss.timeanddate.com/news-time.rss
    - timeanddate     Astronomy News    https://rss.timeanddate.com/news-astronomy.rss
    - timeanddate     Calendar News     https://rss.timeanddate.com/news-calendar.rss
    - Office Holidays blog              https://blog.officeholidays.com/feed/
    - Office Holidays public-holiday news
                                        https://www.officeholidays.com/rss/external-news
    - Office Holidays upcoming holidays https://www.officeholidays.com/rss/all_holidays
    - Holidays and Observances          https://www.holidays-and-observances.com/holidays-and-observances.xml
    - Web-Holidays blog                 https://web-holidays.com/blog?format=rss

All native RSS. ``all_holidays`` is the odd one out: it is not a news feed but
a rolling ~30-day window of every upcoming public holiday worldwide (~260 items
per fetch), each under a *stable* per-holiday URL that repeats year after year.
Left alone it would both flood the combined feed and freeze each holiday at the
date it was first seen. So it is capped to the nearest few dozen entries and
listed in ``refresh_sources``, which drops its cached entries before each
re-scrape — the source stays a live "what's coming up" window instead of
accumulating into a stale archive. ``per_source_cap`` then keeps it from
crowding out the editorial sources in the published feed.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "datime"

UPCOMING = "Office Holidays (upcoming)"

SOURCES = [
    ("timeanddate — Time Zones", "https://rss.timeanddate.com/news-time.rss", 30),
    ("timeanddate — Astronomy", "https://rss.timeanddate.com/news-astronomy.rss", 30),
    ("timeanddate — Calendar", "https://rss.timeanddate.com/news-calendar.rss", 30),
    ("Office Holidays Blog", "https://blog.officeholidays.com/feed/", 30),
    ("Office Holidays News", "https://www.officeholidays.com/rss/external-news", 30),
    (UPCOMING, "https://www.officeholidays.com/rss/all_holidays", 40),
    ("Holidays and Observances", "https://www.holidays-and-observances.com/holidays-and-observances.xml", 40),
    ("Web-Holidays", "https://web-holidays.com/blog?format=rss", 30),
]

# The upcoming-holidays firehose gets a small slice; everyone else keeps a
# useful share of the feed.
PER_SOURCE_CAP = {UPCOMING: 25, "": 40}


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="DaTime",
        subtitle="Time zones, calendars, astronomy and public holidays — timeanddate, "
                 "Office Holidays, Holidays and Observances, Web-Holidays.",
        blog_url="https://www.timeanddate.com/news/",
        author="DaTime",
        sources=SOURCES,
        refresh_sources=(UPCOMING,),
        per_source_cap=PER_SOURCE_CAP,
        max_entries=250,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the DaTime Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
