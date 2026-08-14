"""DaTime feed: time, calendars, astronomy and holidays, combined.

    - timeanddate     Time Zone News    https://rss.timeanddate.com/news-time.rss
    - timeanddate     Astronomy News    https://rss.timeanddate.com/news-astronomy.rss
    - timeanddate     Calendar News     https://rss.timeanddate.com/news-calendar.rss
    - Office Holidays blog              https://blog.officeholidays.com/feed/
    - Office Holidays public-holiday news
                                        https://www.officeholidays.com/rss/external-news
    - Office Holidays upcoming holidays https://www.officeholidays.com/rss/all_holidays  (filtered to Poland)
    - Holidays and Observances          https://www.holidays-and-observances.com/holidays-and-observances.xml
    - Web-Holidays blog                 https://web-holidays.com/blog?format=rss

All native RSS except ``all_holidays``, which needs handling. It is not a news
feed but a rolling ~30-day window of *every* upcoming national public holiday
on earth — ~266 items across 155 countries per fetch, the great majority of
them single-country observances of no interest here. It is therefore fetched
through :func:`collect_poland_holidays`, which keeps only Polish entries.

That filter drops the source from ~266 items per fetch to roughly one, because
Poland has about thirteen public holidays a year. That is the intended volume:
international observances are not in this feed at all (it carries strictly
national public holidays) and are already covered elsewhere here — the
Holidays and Observances per-day pages, Web-Holidays, and timeanddate.

Filtering by holiday *name* was considered and rejected: matching World or
International against the title picks up entries like "India (Rajasthan):
World Tribal Day", a regional holiday that merely has "World" in its name,
while missing the genuine UN observances this feed never carries anyway.

Each holiday sits at a *stable* URL that repeats year after year, so a cached
entry would stay frozen at the date it was first seen and next year's
occurrence would never be added. ``cache_filter`` therefore drops this
source's cached entries on every run, and the scraper re-adds the current
window with fresh dates — a live "what's coming up" list, not a stale
archive.
"""

import argparse
import sys

from multi_rss import run, scrape_feed

FEED_NAME = "datime"

UPCOMING = "Office Holidays (upcoming)"

SOURCES = [
    ("timeanddate — Time Zones", "https://rss.timeanddate.com/news-time.rss", 30),
    ("timeanddate — Astronomy", "https://rss.timeanddate.com/news-astronomy.rss", 30),
    ("timeanddate — Calendar", "https://rss.timeanddate.com/news-calendar.rss", 30),
    ("Office Holidays Blog", "https://blog.officeholidays.com/feed/", 30),
    ("Office Holidays News", "https://www.officeholidays.com/rss/external-news", 30),
    ("Holidays and Observances", "https://www.holidays-and-observances.com/holidays-and-observances.xml", 40),
    ("Web-Holidays", "https://web-holidays.com/blog?format=rss", 30),
]

UPCOMING_URL = "https://www.officeholidays.com/rss/all_holidays"
# Only Polish national holidays are kept from the worldwide firehose.
POLAND_PATH = "/holidays/poland/"

# The holidays source gets a small slice; everyone else keeps a useful share.
PER_SOURCE_CAP = {UPCOMING: 25, "": 40}


def collect_poland_holidays(known_links):
    """Upcoming Polish public holidays, filtered out of the worldwide feed."""
    entries = scrape_feed(UPCOMING, UPCOMING_URL, known_links)
    return [e for e in entries if POLAND_PATH in e["link"]]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="DaTime",
        subtitle="Time zones, calendars, astronomy and public holidays — timeanddate, "
                 "Office Holidays, Holidays and Observances, Web-Holidays.",
        blog_url="https://www.timeanddate.com/news/",
        author="DaTime",
        sources=SOURCES,
        extra_scrapers=(collect_poland_holidays,),
        # Stable per-holiday URLs mean a cached entry never refreshes, so this
        # source's cache is dropped and rebuilt from the live window each run.
        cache_filter=lambda entry: entry.get("source") != UPCOMING,
        per_source_cap=PER_SOURCE_CAP,
        max_entries=250,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the DaTime Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
