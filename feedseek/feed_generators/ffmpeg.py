"""FFmpeg feed: official project news and source-code activity."""

import argparse
import re
import sys

from multi_rss import parse_date, run, scrape_feed

FEED_NAME = "ffmpeg"
BLOG_URL = "https://ffmpeg.org/"
NEWS_URL = "https://ffmpeg.org/main.rss"
CODE_URL = "https://code.ffmpeg.org/FFmpeg.rss"

SOURCES = [("FFmpeg Code", CODE_URL, 120)]

NEWS_DATE_RE = re.compile(
    r"^([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,\s+(\d{4}),"
)


def news_title_date(title):
    """Extract the publication date embedded in an FFmpeg news title."""
    match = NEWS_DATE_RE.match(title or "")
    if not match:
        return None
    month, day, year = match.groups()
    return parse_date(f"{month} {day}, {year}")


def repair_news_date(entry):
    """Repair missing/first-seen dates for FFmpeg News cache entries."""
    repaired = entry.copy()
    if repaired.get("source") != "FFmpeg News":
        return repaired
    parsed = news_title_date(repaired.get("title", ""))
    if parsed is not None:
        repaired["date"] = parsed
    return repaired


def scrape_news(known_links):
    entries = scrape_feed("FFmpeg News", NEWS_URL, known_links, cap=80)
    return [repair_news_date(entry) for entry in entries]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="FFmpeg",
        subtitle="Official FFmpeg project news and source-code activity.",
        blog_url=BLOG_URL,
        author="FFmpeg project",
        sources=SOURCES,
        extra_scrapers=(scrape_news,),
        cache_transform=repair_news_date,
        max_entries=200,
        per_source_cap={"FFmpeg News": 80, "FFmpeg Code": 120, "": 30},
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined FFmpeg Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
