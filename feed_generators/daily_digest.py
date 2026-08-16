"""Daily digest feed generator.

Combines small daily JSON APIs into a single Atom feed:

  * ViewBits ZenQuotes quote of the day  https://api.viewbits.com/v1/zenquotes?mode=today
  * ViewBits useless fact of the day     https://api.viewbits.com/v1/uselessfacts?mode=today
  * ViewBits life hack of the day        https://api.viewbits.com/v1/lifehacks?mode=today
  * ViewBits fortune cookie of the day   https://api.viewbits.com/v1/fortunecookie?mode=today
  * ViewBits Jester joke of the day      https://api.viewbits.com/v1/jester?mode=today
  * ViewBits news headlines              https://api.viewbits.com/v1/headlines?limit=10
  * ViewBits On This Day                 https://api.viewbits.com/v1/onthisday?m={month}&d={day}
  * Nager.Date Polish public holidays    https://date.nager.at/api/v3/publicholidays/{year}/PL
  * a cat or dog fact with a picture     see CRITTER_FACT_SOURCES below
  * an absurd product of the day         https://anycrap.shop/api/v1/products/random

Each source is fetched independently so one failure never sinks the run. Entries
merge into a local cache (dedup by ``guid``) so history accumulates across hourly
runs, and the result is written as an **Atom** feed to ``feeds/feed_daily_digest.xml``.

The five "today" endpoints expose only a single URL each (no per-day permalink),
so they are deduplicated by a synthetic ``{kind}:{date}`` guid while their
clickable ``link`` stays pointed at the real source. Headlines dedupe by article URL.
On This Day produces one compact daily entry for events, births, and deaths.

Holidays don't fit that per-URL shape: they're driven by a date window instead of
a single upstream URL. ``adapt_holidays`` pulls Poland's public holidays for the
years that can fall within the window, and emits at most two entries per holiday
across its lifetime -- one on the day itself, one exactly a week ahead as a
reminder -- each guid-stable so it's written once and never churns. Each entry
links to the matching Polish Wikipedia article when ``opensearch`` finds one,
else falls back to the Nager.Date source.

The critter and anycrap entries don't fit either shape: each is one entry a day,
the critter built from two independent APIs (a fact host and a picture host)
picked per day. Both are skipped outright once the day's guid is cached.
"""

import argparse
import html
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin

import pytz
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from enrich import enrich_entries
from utils import (
    add_entry_media,
    deserialize_entries,
    favicon_proxy,
    fetch_page,
    get_feeds_dir,
    load_cache,
    merge_entries,
    sanitize_xml,
    save_cache,
    setup_feed_extensions,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "daily_digest"
BLOG_URL = "https://api.viewbits.com/"
VIEWBITS_API = "https://api.viewbits.com/v1"
VIEWBITS_DOCS = "https://viewbits.com/docs/"
HEADLINE_LIMIT = 10
ON_THIS_DAY_ITEMS_PER_GROUP = 5
VIEWBITS_MIN_INTERVAL = 6.1

SOURCES = {
    "quote": f"{VIEWBITS_API}/zenquotes?mode=today",
    "fact": f"{VIEWBITS_API}/uselessfacts?mode=today",
    "lifehack": f"{VIEWBITS_API}/lifehacks?mode=today",
    "fortune": f"{VIEWBITS_API}/fortunecookie?mode=today",
    "jester": f"{VIEWBITS_API}/jester?mode=today",
    "headlines": f"{VIEWBITS_API}/headlines?limit={HEADLINE_LIMIT}",
}
ON_THIS_DAY_URL = f"{VIEWBITS_API}/onthisday?m={{month}}&d={{day}}"
ON_THIS_DAY_GROUPS = (
    ("Events", "On This Day", "on_this_day_event"),
    ("Births", "Born on This Day", "on_this_day_birth"),
    ("Deaths", "Died on This Day", "on_this_day_death"),
)

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
    "User-Agent": "trvny-feeds/1.0 (+https://github.com/trvny/feedseek) daily_digest generator",
    "Accept": "application/json",
}

# --- Critter of the day ----------------------------------------------------
#
# Nine animal APIs were on the table for this; five answer, and those are the
# ones wired up. Probed 16.08.2026 from a residential IP:
#
#   works  https://catfact.ninja/fact
#   works  https://meowfacts.herokuapp.com/
#   works  https://api.thecatapi.com/v1/images/search  keyless; a key only raises the rate limit
#   works  https://cataas.com/cat?json=true
#   works  https://random.dog/woof.json                ?filter= keeps the video files out
#   empty  https://dog-api.kinduff.com/api/facts       HTTP 200 with {"facts": [], "success": false}
#   gone   https://dog-facts-api.herokuapp.com/...     "No such app" — a casualty of Heroku's free tier
#   gone   https://cat-fact.herokuapp.com/...          HTTP 503 — the same
#   key    https://anycrap.shop/api/v1/products/random 401 without a free API key
#
# Neither dog-fact host on that list still returns a fact, so dogapi.dog stands
# in for both. Each source is a (name, url, home, extract) tuple; ``extract``
# may assume its documented shape because _pick_from_sources catches the
# exception a moved field raises and moves on to the next source.
CRITTER_KINDS = ("cat", "dog")

CRITTER_FACT_SOURCES = {
    "cat": (
        ("Cat Fact Ninja", "https://catfact.ninja/fact", "https://catfact.ninja/",
         lambda data: data["fact"]),
        ("meowfacts", "https://meowfacts.herokuapp.com/",
         "https://github.com/wh-iterabb-it/meowfacts",
         lambda data: data["data"][0]),
    ),
    "dog": (
        ("Dog API", "https://dogapi.dog/api/v2/facts", "https://dogapi.dog/",
         lambda data: data["data"][0]["attributes"]["body"]),
    ),
}

CRITTER_PICTURE_SOURCES = {
    "cat": (
        ("TheCatAPI", "https://api.thecatapi.com/v1/images/search", "https://thecatapi.com/",
         lambda data: data[0]["url"]),
        ("Cataas", "https://cataas.com/cat?json=true", "https://cataas.com/",
         lambda data: data["url"]),
    ),
    "dog": (
        ("random.dog", "https://random.dog/woof.json?filter=mp4,webm,mov", "https://random.dog/",
         lambda data: data["url"]),
    ),
}

# anycrap.shop -- 35k absurdist product concepts, one a day. The only source
# here behind a key (free, from https://anycrap.shop/developers); without
# ANYCRAP_API_KEY the endpoint answers 401 and the source sits out. The product
# page path comes from the site's own sitemap, not from the API payload, which
# carries only the slug.
ANYCRAP_RANDOM_URL = "https://anycrap.shop/api/v1/products/random"
ANYCRAP_PRODUCT_URL = "https://anycrap.shop/product/{slug}"

# Cap the merged feed so the committed XML stays a reasonable size.
MAX_ENTRIES = 100
_last_viewbits_request = None


def _viewbits_request_url(url):
    key = os.environ.get("VIEWBITS_API_KEY")
    if not key or not url.startswith(VIEWBITS_API):
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}key={quote(key, safe='')}"


def _throttle_viewbits(url):
    """Respect ViewBits' keyless limit of five calls per 30 seconds."""
    global _last_viewbits_request

    if os.environ.get("VIEWBITS_API_KEY") or not url.startswith(VIEWBITS_API):
        return
    now = time.monotonic()
    if _last_viewbits_request is not None:
        delay = VIEWBITS_MIN_INTERVAL - (now - _last_viewbits_request)
        if delay > 0:
            time.sleep(delay)
    _last_viewbits_request = time.monotonic()


def fetch_json(url, retries=3, backoff=2.0, headers=None):
    """Fetch *url* and parse JSON, retrying transient failures. None on failure.

    ``headers`` replaces FETCH_HEADERS for the hosts that need something extra
    (an Authorization bearer, so far). Only the URL is ever logged, so a header
    carrying a key cannot reach the run log.
    """
    for attempt in range(1, retries + 1):
        try:
            _throttle_viewbits(url)
            body = fetch_page(_viewbits_request_url(url), headers=headers or FETCH_HEADERS)
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
    body = f"“{text}” — {author}" if author else f"“{text}”"
    return [{
        "guid": f"quote:{date_str}",
        "link": f"{VIEWBITS_DOCS}zenquotes-api-documentation",
        "title": _clean(f"Quote of the Day — {author}") if author else "Quote of the Day",
        "description": body,
        "date": _day_midnight(date_str),
        "source": author or "ViewBits ZenQuotes",
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


def adapt_jester(data):
    text = _clean(data.get("text"))
    day = f"{_today_utc():%Y-%m-%d}"
    return [{
        "guid": f"jester:{day}",
        "link": data.get("url") or f"{VIEWBITS_DOCS}jester-api-documentation",
        "title": "Joke of the Day",
        "description": text or "Joke of the Day",
        "date": _day_midnight(),
        "source": _clean(data.get("source")) or "ViewBits Jester",
        "category": "joke",
    }]


def adapt_headlines(data):
    entries = []
    seen = set()
    for item in data[:HEADLINE_LIMIT]:
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


def _on_this_day_link(item):
    if not isinstance(item, dict):
        return None
    for link in item.get("links") or []:
        if isinstance(link, dict):
            candidate = link.get("link") or link.get("url") or link.get("href")
        else:
            candidate = link if isinstance(link, str) else None
        if candidate:
            return candidate
    return None


def adapt_on_this_day(data):
    """Create compact daily summaries for events, births, and deaths."""
    payload = data.get("data") if isinstance(data, dict) else None
    if not isinstance(payload, dict):
        return []

    today = _today_utc()
    date_str = f"{today:%Y-%m-%d}"
    display_date = f"{today:%B} {today.day}"
    fallback_link = f"{VIEWBITS_DOCS}on-this-day-api-documentation"
    entries = []

    for api_group, title, category in ON_THIS_DAY_GROUPS:
        items = payload.get(api_group) or []
        lines = []
        link = None
        for item in items:
            text = _clean(item.get("text")) if isinstance(item, dict) else _clean(str(item))
            if not text:
                continue
            lines.append(f"• {text}")
            link = link or _on_this_day_link(item)
            if len(lines) >= ON_THIS_DAY_ITEMS_PER_GROUP:
                break
        if not lines:
            continue
        entries.append({
            "guid": f"onthisday:{category}:{date_str}",
            "link": link or fallback_link,
            "title": f"{title} — {display_date}",
            "description": "\n".join(lines),
            "date": _day_midnight(date_str),
            "source": "ViewBits On This Day",
            "category": category,
        })
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
            kind, label = "holiday_today", "Dziś"
        elif delta == REMINDER_DAYS_AHEAD:
            kind, label = "holiday_reminder", "Za tydzień"
        else:
            continue

        local_name = _clean(h.get("localName") or h.get("name"))
        wiki_url = fetch_wikipedia_link(local_name)
        fallback_link = NAGER_HOLIDAYS_URL.format(year=h_date.year, country=HOLIDAY_COUNTRY)
        body = f"{label}: {local_name} ({h_date:%d.%m.%Y}), dzień wolny od pracy w Polsce."
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


def doc_sources():
    """The critter hosts, for docs/sources.md.

    docs_sources.py collects module-level URL constants; these live inside dict
    literals instead, so without this hook the digest would be documented as
    ViewBits, Nager.Date and Wikipedia only. Read by docs_sources.py; must not
    touch the network.
    """
    return [
        (f"{name} ({kind} {what})", home)
        for what, registry in (("facts", CRITTER_FACT_SOURCES), ("pictures", CRITTER_PICTURE_SOURCES))
        for kind, sources in registry.items()
        for name, _, home, _ in sources
    ] + [("Anycrap", ANYCRAP_RANDOM_URL)]


def _pick_from_sources(sources, rng, *, what):
    """Try *sources* in ``rng``'s order, returning the first usable
    ``(value, name, home, url)`` -- or four Nones when every one of them
    declines. Nothing here raises: an unreachable host and a payload whose shape
    has moved are both logged and stepped over, which is what lets a single
    working source keep the entry alive.

    The value is stripped *before* it is judged usable, so an answer that is
    blank rather than absent -- a lone newline from a host having a bad day --
    hands over to the backup instead of counting as the day's fact.
    """
    ordered = list(sources)
    rng.shuffle(ordered)

    for name, url, home, extract in ordered:
        data = fetch_json(url, retries=2)
        if data is None:
            logger.warning(f"Critter {what} source '{name}' unavailable; trying the next one")
            continue
        try:
            value = extract(data)
        except (AttributeError, IndexError, KeyError, TypeError) as e:
            logger.warning(f"Critter {what} source '{name}' changed shape ({e}); trying the next one")
            continue
        text = "" if value is None else str(value).strip()
        if text:
            return text, name, home, url
        logger.warning(f"Critter {what} source '{name}' answered blank; trying the next one")

    return None, None, None, None


def adapt_critter():
    """Build the day's single cat-or-dog entry: a fact, a picture, and credit
    for both hosts.

    The species and the order the APIs are tried in come from a generator seeded
    with the UTC date -- the same trick daily_quote uses. So a rerun on the same
    day reaches for the same sources instead of rolling a second animal, while
    the feed still turns over from one day to the next. The fact text itself is
    whatever the upstream returns; only the day's *first* successful run is kept
    (merge_entries never replaces a guid it already holds), so the entry stops
    moving once it exists.
    """
    day = f"{_today_utc():%Y-%m-%d}"
    rng = random.Random(f"critter:{day}")
    kind = rng.choice(CRITTER_KINDS)

    fact, fact_source, fact_home, _ = _pick_from_sources(
        CRITTER_FACT_SOURCES[kind], rng, what="fact"
    )
    if not fact:
        logger.warning(f"No {kind} fact available today; skipping the critter entry")
        return []

    picture, picture_source, picture_home, picture_api = _pick_from_sources(
        CRITTER_PICTURE_SOURCES[kind], rng, what="picture"
    )
    if picture:
        # Cataas answers /cat?json=true with an absolute url today, but has
        # historically returned a site-relative "/cat/<id>". A relative href in
        # MRSS renders as a broken image in every reader, and nothing
        # downstream absolutizes it, so resolve it here -- against the endpoint
        # that answered, not the human-facing home page. They differ: TheCatAPI
        # serves from api.thecatapi.com while its home is thecatapi.com, so
        # resolving against the home would move the image to the wrong host.
        picture = urljoin(picture_api, picture)

    body = _clean(fact)
    if picture_source:
        body += f"\n\nPicture: {picture_source} ({picture_home})"

    return [{
        "guid": f"critter:{day}",
        "link": fact_home,
        "title": f"{kind.capitalize()} Fact of the Day",
        "description": body,
        "date": _day_midnight(),
        "source": fact_source,
        "category": "critter",
        "image": picture,
        # The picture lookup above is the lookup. Without this flag, an entry
        # that came back picture-less would send backfill_images off to ask a
        # fact API's landing page for an og:image it was never going to have.
        "image_checked": True,
    }]


def adapt_anycrap():
    """One absurd product a day from anycrap.shop -- name, blurb, and its picture.

    Needs ``ANYCRAP_API_KEY``: the endpoint answers 401 to an unauthenticated
    request, so without the key there is nothing to try and the source is
    skipped rather than failed. The key travels in an Authorization header,
    never in the URL, so it cannot end up in a log line.
    """
    key = os.environ.get("ANYCRAP_API_KEY")
    if not key:
        logger.info("anycrap: no ANYCRAP_API_KEY set; skipping")
        return []

    data = fetch_json(
        ANYCRAP_RANDOM_URL,
        retries=2,
        headers={**FETCH_HEADERS, "Authorization": f"Bearer {key}"},
    )
    if not data:
        return []

    try:
        product = data["data"][0]
        name = _clean(product["name"])
        slug = product["slug"]
    except (IndexError, KeyError, TypeError) as e:
        logger.warning(f"anycrap returned an unusable payload ({e}); continuing")
        return []
    if not name or not slug:
        return []

    # str() before _clean here too: the blurb is read outside the shape guard
    # above, and _clean unescapes HTML, which raises on a non-string.
    description = product.get("description")
    body = _clean(str(description)) if description else ""
    body = body or name
    # A categories field that turned into objects, or stopped being a list at
    # all, should cost the categories line and nothing more -- hence the type
    # check, and str() before _clean, which unescapes HTML and would raise on a
    # non-string.
    raw_categories = product.get("categories")
    if not isinstance(raw_categories, (list, tuple)):
        raw_categories = []
    categories = ", ".join(filter(None, (_clean(str(c)) for c in raw_categories)))
    if categories:
        body += f"\n\nCategories: {categories}"

    image = product.get("image") or None
    if image:
        # Same reasoning as the critter picture: a site-relative href renders as
        # a broken image everywhere, and nothing downstream absolutizes it.
        image = urljoin(ANYCRAP_RANDOM_URL, str(image))

    return [{
        "guid": f"anycrap:{_today_utc():%Y-%m-%d}",
        # The slug is API-supplied and lands in the entry's clickable link, so
        # it is escaped rather than trusted to be URL-safe.
        "link": ANYCRAP_PRODUCT_URL.format(slug=quote(str(slug), safe="")),
        "title": f"Product of the Day — {name}",
        "description": body,
        "date": _day_midnight(),
        "source": "Anycrap",
        "category": "anycrap",
        "image": image,
        # Only claim the lookup is done when the API actually handed a picture
        # over. Unlike the critter's fact hosts, the link here is a real product
        # page, so a missing image is worth letting the backfill chase.
        "image_checked": bool(image),
    }]


def _cached_guids():
    """Every guid currently in the cache, read once per run.

    Lets the once-a-day sources stay off the wire during the day's other eleven
    runs: merge_entries keeps the cached copy of a guid it already has, so a
    second fetch buys nothing but load on somebody else's free API. An
    unreadable cache reads as empty, which costs a fetch rather than an entry.
    """
    try:
        cached = load_cache(FEED_NAME).get("entries", [])
    except Exception as e:
        logger.warning(f"Cache unreadable ({e}); treating it as empty")
        return set()
    return {entry.get("guid") for entry in cached}


ADAPTERS = {
    "quote": adapt_quote,
    "fact": lambda d: adapt_simple(
        d, kind="fact", title="Useless Fact of the Day", source_name="ViewBits"
    ),
    "lifehack": lambda d: adapt_simple(
        d, kind="lifehack", title="Life Hack of the Day", source_name="ViewBits"
    ),
    "fortune": lambda d: adapt_simple(
        d, kind="fortune", title="Fortune Cookie of the Day", source_name="ViewBits"
    ),
    "jester": adapt_jester,
    "headlines": adapt_headlines,
}


def collect_entries(full=False):
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

    # On This Day needs today's month/day in its query, so it is fetched outside
    # the static SOURCES loop but retains the same failure isolation.
    try:
        today = _today_utc()
        url = ON_THIS_DAY_URL.format(month=today.month, day=today.day)
        data = fetch_json(url)
        if data is None:
            logger.warning("Source 'on_this_day' unavailable; continuing")
        else:
            new = adapt_on_this_day(data)
            logger.info(f"on_this_day: {len(new)} entry(ies)")
            entries.extend(new)
    except Exception as e:
        logger.warning(f"Source 'on_this_day' parse failed ({e}); continuing")

    # Holidays are driven by a date window, not a single upstream URL, so they
    # don't fit the SOURCES/ADAPTERS loop above -- handled separately but with
    # the same per-source isolation (a failure here never sinks the run).
    try:
        holiday_entries = adapt_holidays()
        logger.info(f"holidays: {len(holiday_entries)} entry(ies)")
        entries.extend(holiday_entries)
    except Exception as e:
        logger.warning(f"Source 'holidays' failed ({e}); continuing")

    # These two are one entry a day, so on the day's remaining runs the entry is
    # already cached and fetching it again would spend calls on somebody's free
    # API for a result merge_entries throws away. A full rebuild ignores the
    # cache like every other source.
    day = f"{_today_utc():%Y-%m-%d}"
    known = set() if full else _cached_guids()
    for label, adapter in (("critter", adapt_critter), ("anycrap", adapt_anycrap)):
        try:
            if f"{label}:{day}" in known:
                logger.info(f"{label}: today's entry is already cached; not fetching")
                continue
            new = adapter()
            logger.info(f"{label}: {len(new)} entry(ies)")
            entries.extend(new)
        except Exception as e:
            logger.warning(f"Source '{label}' failed ({e}); continuing")

    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    """Build an Atom FeedGenerator from the normalized entry list."""
    fg = FeedGenerator()
    fg.id(f"https://api.viewbits.com/{feed_name}")
    fg.title("Daily Digest")
    fg.subtitle(
        "Quote, fact, life hack, fortune cookie, joke, headlines, and history "
        "of the day, a cat or dog with a fact and a picture, an absurd product, "
        "plus Polish public-holiday reminders"
    )
    # Entries have carried an `image` since backfill_images started running over
    # them, but nothing here ever rendered it, so it lived in the cache and
    # nowhere else. MRSS is also how the JSON sidecar finds a picture at all.
    setup_feed_extensions(fg)
    setup_feed_links(
        fg,
        BLOG_URL,
        feed_name,
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
        add_entry_media(fe, entry.get("image"))
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
    new_entries = collect_entries(full=full)
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

    enrich_entries(merged)
    save_cache(FEED_NAME, merged)

    fg = generate_atom_feed(merged)
    save_atom_feed(fg)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Daily Digest Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
