"""Daily digest feed generator.

Combines six small JSON APIs into a single Atom feed:

  * ZenQuotes "quote of the day"          https://zenquotes.io/api/today
  * ViewBits useless fact of the day      https://api.viewbits.com/v1/uselessfacts?mode=today
  * ViewBits life hack of the day         https://api.viewbits.com/v1/lifehacks?mode=today
  * ViewBits fortune cookie of the day    https://api.viewbits.com/v1/fortunecookie?mode=today
  * ViewBits news headlines               https://api.viewbits.com/v1/headlines
  * Nager.Date Polish public holidays     https://date.nager.at/api/v3/publicholidays/{year}/PL

Each source is fetched independently so one failure never sinks the run. Entries
merge into a local cache (dedup by ``guid``) so history accumulates across hourly
runs, and the result is written as an **Atom** feed to ``feeds/feed_daily_digest.xml``.

The four "today" endpoints expose only a single URL each (no per-day permalink),
so they are deduplicated by a synthetic ``{kind}:{date}`` guid while their
clickable ``link`` stays pointed at the real source. Headlines dedupe by article URL.

Holidays don't fit that per-URL shape: they're driven by a date window instead of
a single upstream URL. ``adapt_holidays`` pulls Poland's public holidays for the
years that can fall within the window, and emits at most two entries per holiday
across its lifetime -- one on the day itself, one exactly a week ahead as a
reminder -- each guid-stable so it's written once and never churns. Each entry
links to the matching Polish Wikipedia article when ``opensearch`` finds one,
else falls back to the Nager.Date source.
"""

import argparse
import html
import json
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import pytz
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
    favicon_proxy,
)

logger = setup_logging()

FEED_NAME = "daily_digest"
BLOG_URL = "https://api.viewbits.com/"

SOURCES = {
    "quote": "https://zenquotes.io/api/today",
    "fact": "https://api.viewbits.com/v1/uselessfacts?mode=today",
    "lifehack": "https://api.viewbits.com/v1/lifehacks?mode=today",
    "fortune": "https://api.viewbits.com/v1/fortunecookie?mode=today",
    "headlines": "https://api.viewbits.com/v1/headlines",
}

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Nager.Date -- Polish public holidays. v3 (not v4) is used deliberately: v4's
# /api/v4/Holidays/{country}/{year} drops the localized name and only returns
# the English one, and a Polish name is what we need both to display and to
# look up on pl.wikipedia.org.
NAGER_HOLIDAYS_URL = "https://date.nager.at/api/v3/publicholidays/{year}/{country}"
HOLIDAY_COUNTRY = "PL"
REMINDER_DAYS_AHEAD = 7

WIKI_OPENSEARCH_URL = (
    "https://pl.wikipedia.org/w/api.php"
    "?action=opensearch&format=json&namespace=0&limit=1&search={query}"
)
WIKI_HEADERS = {
    "User-Agent": "trvny-feeds/1.0 (+https://github.com/trvny/feeds) daily_digest generator",
    "Accept": "application/json",
}

# Cap the merged feed so the committed XML stays a reasonable size.
MAX_ENTRIES = 100


def fetch_json(url, retries=3, backoff=2.0):
    """Fetch *url* and parse JSON, retrying transient failures. None on failure."""
    for attempt in range(1, retries + 1):
        try:
            body = fetch_page(url, headers=FETCH_HEADERS)
            return json.loads(body)
        except Exception as e:
            logger.warning(f"Fetch failed for {url} (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(backoff * attempt)
    return None


def _clean(text):
    """HTML-unescape then strip characters invalid in XML 1.0."""
    return sanitize_xml(html.unescape(text or "").strip())


def _today_utc():
    return datetime.now(pytz.UTC)


def _day_midnight(date_str=None):
    """Midnight UTC for the given YYYY-MM-DD (or today). Stable within a day so
    repeated runs produce an identical entry and the feed doesn't churn."""
    if date_str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            d = _today_utc()
    else:
        d = _today_utc()
    return d.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)


# --- Per-source adapters. Each returns a list of normalized entry dicts:
#     {guid, link, title, description, date, source, category} -------------


def adapt_quote(data):
    item = data[0]
    text = _clean(item.get("q"))
    author = _clean(item.get("a"))
    date_str = item.get("date") or f"{_today_utc():%Y-%m-%d}"
    body = f"\u201c{text}\u201d \u2014 {author}" if author else f"\u201c{text}\u201d"
    return [{
        "guid": f"quote:{date_str}",
        "link": "https://zenquotes.io/",
        "title": _clean(f"Quote of the Day \u2014 {author}") if author else "Quote of the Day",
        "description": body,
        "date": _day_midnight(date_str),
        "source": author or "ZenQuotes",
        "category": "quote",
    }]


def adapt_simple(data, *, kind, title, source_name):
    """Single-object ViewBits endpoints (fact / lifehack / fortune)."""
    text = _clean(data.get("text"))
    body = text
    if data.get("numbers"):
        body = f"{text}\n\nLucky Numbers: {_clean(data['numbers'])}"
    day = f"{_today_utc():%Y-%m-%d}"
    return [{
        "guid": f"{kind}:{day}",
        "link": data.get("url") or BLOG_URL,
        "title": title,
        "description": body or title,
        "date": _day_midnight(),
        "source": source_name,
        "category": kind,
    }]


def adapt_headlines(data):
    entries = []
    seen = set()
    for item in data:
        try:
            link = item.get("link")
            title = _clean(item.get("title"))
            if not link or not title or link in seen:
                continue
            seen.add(link)
            desc = _clean(item.get("description")) or title
            pub = item.get("pubDate")
            try:
                date_obj = date_parser.parse(pub) if pub else None
                if date_obj and date_obj.tzinfo is None:
                    date_obj = date_obj.replace(tzinfo=pytz.UTC)
                if date_obj:
                    date_obj = date_obj.astimezone(pytz.UTC)
            except (ValueError, TypeError, OverflowError):
                date_obj = None
            entries.append({
                "guid": link,
                "link": link,
                "title": title,
                "description": desc,
                "date": date_obj,
                "source": item.get("source") or "headlines",
                "category": item.get("category") or "news",
            })
        except Exception as e:  # never let one bad item kill the run
            logger.warning(f"Skipping malformed headline: {e}")
    return entries


def fetch_wikipedia_link(title):
    """Look up a Polish-Wikipedia article for *title* via ``action=opensearch``
    (handles redirects/near-matches better than a direct page-summary GET).
    Returns the canonical article URL, or None if nothing matches -- the
    holiday entry is still built, just without a Wikipedia link."""
    url = WIKI_OPENSEARCH_URL.format(query=quote(title))
    try:
        body = fetch_page(url, headers=WIKI_HEADERS)
        _, _, _, urls = json.loads(body)
        return urls[0] if urls else None
    except Exception as e:
        logger.warning(f"Wikipedia lookup failed for {title!r}: {e}")
        return None


def fetch_polish_holidays(years):
    """Fetch PL public holidays for each year in *years* from Nager.Date."""
    holidays = []
    for year in years:
        data = fetch_json(NAGER_HOLIDAYS_URL.format(year=year, country=HOLIDAY_COUNTRY))
        if data:
            holidays.extend(data)
        else:
            logger.warning(f"Nager.Date unavailable for {year}; continuing")
    return holidays


def adapt_holidays():
    """Build entries for Polish public holidays: one when a holiday falls on
    today, one as a reminder exactly a week ahead. Each links to a Polish
    Wikipedia article when one can be found, else falls back to Nager.Date."""
    today = _today_utc().date()
    years = sorted({today.year, (today + timedelta(days=REMINDER_DAYS_AHEAD)).year})
    holidays = fetch_polish_holidays(years)

    entries = []
    for h in holidays:
        try:
            h_date = date_parser.parse(h["date"]).date()
        except (ValueError, TypeError, KeyError):
            continue

        delta = (h_date - today).days
        if delta == 0:
            kind, label = "holiday_today", "Dzi\u015b"
        elif delta == REMINDER_DAYS_AHEAD:
            kind, label = "holiday_reminder", "Za tydzie\u0144"
        else:
            continue

        local_name = _clean(h.get("localName") or h.get("name"))
        wiki_url = fetch_wikipedia_link(local_name)
        fallback_link = NAGER_HOLIDAYS_URL.format(year=h_date.year, country=HOLIDAY_COUNTRY)
        body = f"{label}: {local_name} ({h_date:%d.%m.%Y}), dzie\u0144 wolny od pracy w Polsce."
        if wiki_url:
            body += f"\n\nWikipedia: {wiki_url}"

        entries.append({
            "guid": f"holiday:{h_date}:{kind}",
            "link": wiki_url or fallback_link,
            "title": f"{label}: {local_name}",
            "description": body,
            "date": _day_midnight(),
            "source": "Nager.Date",
            "category": kind,
        })
    return entries


ADAPTERS = {
    "quote": adapt_quote,
    "fact": lambda d: adapt_simple(d, kind="fact", title="Useless Fact of the Day", source_name="ViewBits"),
    "lifehack": lambda d: adapt_simple(d, kind="lifehack", title="Life Hack of the Day", source_name="ViewBits"),
    "fortune": lambda d: adapt_simple(d, kind="fortune", title="Fortune Cookie of the Day", source_name="ViewBits"),
    "headlines": adapt_headlines,
}


def collect_entries():
    """Fetch and normalize all sources. Per-source failures are logged and skipped."""
    entries = []
    for key, url in SOURCES.items():
        data = fetch_json(url)
        if data is None:
            logger.warning(f"Source '{key}' unavailable; continuing")
            continue
        try:
            new = ADAPTERS[key](data)
            logger.info(f"{key}: {len(new)} entry(ies)")
            entries.extend(new)
        except Exception as e:
            logger.warning(f"Source '{key}' parse failed ({e}); continuing")

    # Holidays are driven by a date window, not a single upstream URL, so they
    # don't fit the SOURCES/ADAPTERS loop above -- handled separately but with
    # the same per-source isolation (a failure here never sinks the run).
    try:
        holiday_entries = adapt_holidays()
        logger.info(f"holidays: {len(holiday_entries)} entry(ies)")
        entries.extend(holiday_entries)
    except Exception as e:
        logger.warning(f"Source 'holidays' failed ({e}); continuing")

    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    """Build an Atom FeedGenerator from the normalized entry list."""
    fg = FeedGenerator()
    fg.id(f"https://api.viewbits.com/{feed_name}")
    fg.title("Daily Digest")
    fg.subtitle("Quote, fact, life hack, fortune cookie, and headlines of the day, plus Polish public-holiday reminders")
    setup_feed_links(
        fg, BLOG_URL, feed_name,
        icon=favicon_proxy("viewbits.com", provider="duckduckgo"),
    )
    fg.language("en")
    fg.author({"name": "Daily Digest"})

    for entry in entries:
        fe = fg.add_entry()
        fe.id(entry["guid"])
        fe.title(entry["title"])
        fe.link(href=entry["link"])
        fe.description(entry["description"])
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
    """Write the feed to feeds/feed_<n>.xml in Atom format."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return output_file


def main(full=False):
    """Fetch all sources, merge with cache, and write the Atom feed."""
    new_entries = collect_entries()
    if not new_entries:
        logger.warning("No entries from any source — skipping write to preserve last good feed")
        return False

    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")

    merged = merge_entries(new_entries, cached, id_field="guid", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")

    # Keep the newest MAX_ENTRIES. sort_posts_for_feed returns ascending
    # (oldest first; feedgen reverses on write), so keep the tail.
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]

    save_cache(FEED_NAME, merged)

    fg = generate_atom_feed(merged)
    save_atom_feed(fg)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Daily Digest Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
