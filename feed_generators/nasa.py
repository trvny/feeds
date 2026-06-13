"""NASA feed: combined Atom from NASA's native RSS feeds — the main newsroom,
the blogs firehose, NASA Science, the launch schedule, the Image of the Day,
and Astronomy Picture of the Day (APOD).

APOD has two mirrors (apod.com/feed.rss and apod.nasa.gov/apod.rss); the .com
mirror carries proper titles and dates, so it is the one used here. The launch
schedule feed is frequently empty between announcements — that's expected and
harmless (per-source isolation means it just contributes nothing until NASA
schedules the next launch).
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "nasa"

SOURCES = [
    ("NASA", "https://www.nasa.gov/feed/", 40),
    ("NASA Blogs", "https://www.nasa.gov/blogs/feed/", 40),
    ("NASA Science", "https://science.nasa.gov/feed/", 40),
    ("Launch Schedule", "https://www.nasa.gov/event-type/launch-schedule/feed/", 40),
    ("Image of the Day", "https://www.nasa.gov/feeds/iotd-feed", 40),
    ("APOD", "https://apod.com/feed.rss", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="NASA",
        subtitle="Combined NASA feed: the main newsroom, the blogs firehose, "
                 "NASA Science, the launch schedule, the Image of the Day, and "
                 "Astronomy Picture of the Day.",
        blog_url="https://www.nasa.gov/",
        author="NASA",
        sources=SOURCES,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the NASA Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
