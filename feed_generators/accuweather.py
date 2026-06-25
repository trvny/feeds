"""AccuWeather combined feed generator.

One Atom feed (``feeds/feed_accuweather.xml``) from three AccuWeather surfaces,
each fetched independently so one failing source never sinks the run:

  * News      https://www.accuweather.com/en/weather-news  (and every other
              editorial category: space-news, climate, health-wellness,
              leisure-recreation, blogs-webinars, severe-weather, weather-
              forecasts, travel, sports, ...). The category landing pages are
              client-rendered, but AccuWeather publishes a Google-News sitemap
              at ``/sitemaps_v2/articles/news/`` carrying the ~40 most recent
              articles with their title and publication date; the category is
              taken from the ``/en/<category>/`` URL segment.
  * Corporate https://name.accuweather.com/corporate/feed/  (native WordPress
              RSS — press releases and corporate posts; the canonical
              corporate.accuweather.com/feed/ is currently empty, so the
              populated ``name.`` mirror is used).
  * API change log  https://apidev.accuweather.com/developers/change-log
              (one ``<h2 id=...>`` per change, titled "Month YYYY — summary";
              the month/year is parsed for the date and the id is the anchor).

The public site sits behind bot mitigation that 403s a plain requests
User-Agent, so fetches use curl_cffi Chrome impersonation. (cms.accuweather.com,
the WordPress backend, is gated behind Microsoft auth and is *not* a usable
source; the public Google-News sitemap is used instead.)

Entries carry a per-source/category ``<category>`` label and are deduplicated
by URL. A rolling JSON cache keeps history across runs.
"""

import argparse
import re
import sys
import time
from datetime import datetime, timezone

import feedparser
import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import (
    deserialize_entries,
    fetch_page,
    get_feeds_dir,
    load_cache,
    merge_entries,
    sanitize_xml,
    save_cache,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "accuweather"
BLOG_URL = "https://www.accuweather.com/en/weather-news"

NEWS_SITEMAP = "https://www.accuweather.com/sitemaps_v2/articles/news/"
CORPORATE_FEED = "https://name.accuweather.com/corporate/feed/"
CHANGELOG_URL = "https://apidev.accuweather.com/developers/change-log"

# Cap the merged feed so the committed XML stays a reasonable size.
MAX_ENTRIES = 150

# Pretty labels for the /en/<segment>/ news category in each article URL.
CATEGORY_LABELS = {
    "weather-news": "Weather News",
    "weather-forecasts": "Weather Forecasts",
    "severe-weather": "Severe Weather",
    "space-news": "Space News",
    "climate": "Climate",
    "health-wellness": "Health & Wellness",
    "leisure-recreation": "Leisure & Recreation",
    "blogs-webinars": "Blogs & Webinars",
    "travel": "Travel",
    "sports": "Sports",
    "recreation": "Recreation",
    "astronomy": "Astronomy",
    "hurricane": "Hurricane",
    "winter-weather": "Winter Weather",
    "business": "Business",
    "case-studies": "Case Studies",
}
_NEWS_SEGMENT_RE = re.compile(r"accuweather\.com/en/([a-z0-9\-]+)/")
# "May 2026 — Heat index ..." -> ("May 2026", "Heat index ...")
_CHANGELOG_SPLIT_RE = re.compile(r"\s*[\u2014\u2013-]\s*")


def fetch_text(url, retries=3, backoff=2.0, headers=None):
    """Fetch a URL's text with retries via curl_cffi Chrome impersonation.

    AccuWeather's public site 403s plain requests, so impersonate Chrome when
    curl_cffi is available and fall back to the shared fetch_page otherwise.
    Returns None on failure (never raises) so one dead source is survivable.
    """
    try:
        from curl_cffi import requests as creq
    except ImportError:
        creq = None

    for attempt in range(1, retries + 1):
        try:
            if creq is not None:
                resp = creq.get(url, impersonate="chrome", timeout=30, headers=headers)
                resp.raise_for_status()
                return resp.text
            return fetch_page(url, headers=headers)
        except Exception as e:
            logger.warning(f"Fetch failed for {url} (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(backoff * attempt)
    return None


def parse_date(value):
    """Parse a date string into a UTC datetime, or None."""
    try:
        dt = date_parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError):
        return None


def category_for(url):
    """Map an article URL's /en/<segment>/ to a pretty category label."""
    m = _NEWS_SEGMENT_RE.search(url)
    if not m:
        return "News"
    seg = m.group(1)
    return CATEGORY_LABELS.get(seg, seg.replace("-", " ").title())


def collect_news():
    """Parse the Google-News sitemap into entries (title + date + category)."""
    xml = fetch_text(NEWS_SITEMAP)
    if xml is None:
        logger.warning("[News] sitemap unavailable; continuing")
        return []

    soup = BeautifulSoup(xml, "xml")
    entries = []
    for url_el in soup.find_all("url"):
        try:
            loc_el = url_el.find("loc")
            if not loc_el:
                continue
            link = loc_el.get_text(strip=True)
            news_el = url_el.find("news")
            title_el = news_el.find("title") if news_el else None
            title = sanitize_xml((title_el.get_text(strip=True) if title_el else "").strip())
            if not link or not title:
                continue
            date = None
            pub_el = news_el.find("publication_date") if news_el else None
            if pub_el:
                date = parse_date(pub_el.get_text(strip=True))
            category = category_for(link)
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date or stable_fallback_date(link),
                    "description": title,
                    "source": "AccuWeather News",
                    "category": category,
                }
            )
        except Exception as e:  # one malformed url block never kills the source
            logger.warning(f"[News] skipping a sitemap entry: {e}")
    logger.info(f"[News] parsed {len(entries)} articles from the news sitemap")
    return entries


def collect_corporate():
    """Parse the corporate WordPress RSS into entries."""
    raw = fetch_text(CORPORATE_FEED)
    if raw is None:
        logger.warning("[Corporate] feed unavailable; continuing")
        return []
    parsed = feedparser.parse(raw)
    entries = []
    for e in parsed.entries:
        try:
            link = (e.get("link") or "").strip()
            title = sanitize_xml((e.get("title") or "").strip())
            if not link or not title:
                continue
            date = None
            for key in ("published_parsed", "updated_parsed"):
                struct = e.get(key)
                if struct:
                    date = datetime(*struct[:6], tzinfo=timezone.utc)
                    break
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date or stable_fallback_date(link),
                    "description": sanitize_xml(e.get("summary") or "") or title,
                    "source": "AccuWeather Corporate",
                    "category": "Corporate",
                }
            )
        except Exception as exc:
            logger.warning(f"[Corporate] skipping an entry: {exc}")
    logger.info(f"[Corporate] parsed {len(entries)} entries")
    return entries


def collect_changelog():
    """Scrape the API change log: one <h2 id=...> per change, 'Month YYYY — x'."""
    html = fetch_text(CHANGELOG_URL)
    if html is None:
        logger.warning("[API Change Log] page unavailable; continuing")
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for h2 in soup.find_all("h2"):
        try:
            heading = h2.get_text(" ", strip=True)
            if not heading:
                continue
            parts = _CHANGELOG_SPLIT_RE.split(heading, maxsplit=1)
            date_part = parts[0].strip()
            title = sanitize_xml(parts[1].strip() if len(parts) > 1 else heading)
            date = parse_date(date_part)  # "May 2026" -> first of month
            if date is None:
                continue  # not a dated change entry (skip stray headings)
            anchor = h2.get("id") or ""
            link = f"{CHANGELOG_URL}#{anchor}" if anchor else CHANGELOG_URL
            sib = h2.find_next_sibling()
            body = sanitize_xml(sib.get_text(" ", strip=True)[:500]) if sib else title
            entries.append(
                {
                    "title": f"API Change Log — {title}",
                    "link": link,
                    "date": date,
                    "description": body or title,
                    "content_type": "text",
                    "source": "AccuWeather API",
                    "category": "API Change Log",
                }
            )
        except Exception as e:
            logger.warning(f"[API Change Log] skipping a heading: {e}")
    logger.info(f"[API Change Log] parsed {len(entries)} changes")
    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    """Build an Atom FeedGenerator from the normalized entry list."""
    fg = FeedGenerator()
    fg.id("https://www.accuweather.com/")
    fg.title("AccuWeather")
    fg.subtitle("AccuWeather news across every category, corporate press releases, and API change log")
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language("en")
    fg.author({"name": "AccuWeather"})

    for entry in entries:
        fe = fg.add_entry()
        fe.id(entry["link"])
        fe.title(entry["title"])
        fe.link(href=entry["link"])
        if entry.get("description"):
            fe.content(entry["description"], type=entry.get("content_type", "html"))
        if entry.get("category"):
            fe.category(term=entry["category"])
        if entry.get("source"):
            fe.author({"name": entry["source"]})
        if entry.get("date"):
            fe.published(entry["date"])
            fe.updated(entry["date"])

    logger.info("Generated Atom feed")
    return fg


def save_atom_feed(fg, feed_name=FEED_NAME):
    """Write the feed to feeds/feed_<name>.xml in Atom format."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return output_file


def main(full=False):
    """Collect from every source, merge with cache, write the feed."""
    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")

    news = collect_news()
    corporate = collect_corporate()
    changelog = collect_changelog()

    if not news and not corporate and not changelog:
        logger.error("All sources failed — skipping write to preserve the last good feed")
        return False

    new_entries = news + corporate + changelog
    merged = merge_entries(new_entries, cached, id_field="link", date_field="date")
    if not merged:
        logger.warning("No entries — skipping write to avoid an empty feed")
        return False

    merged = sort_posts_for_feed(merged, date_field="date")

    # sort_posts_for_feed returns ascending (feedgen reverses on write), so the
    # tail is newest — keep it when capping.
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]

    save_cache(FEED_NAME, merged)
    save_atom_feed(generate_atom_feed(merged))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the AccuWeather Atom feed (news + corporate + API change log)")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
