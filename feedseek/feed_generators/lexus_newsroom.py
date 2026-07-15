"""Lexus Newsroom feed generator.

Aggregates Lexus' public article streams into one **Atom** feed written to
``feeds/feed_lexus_newsroom.xml``:

    - Lexus USA Newsroom     https://pressroom.lexus.com/   (native Atom feed)
    - Newsroom Lexus Europe  https://newsroom.lexus.eu/     (native presspage RSS feed)
    - Discover Lexus         https://discoverlexus.com/     (Nuxt SPA; stories from sitemap.xml)
    - Lexus Polska           https://www.lexus-polska.pl/   (server-rendered HTML news listing)

Two of the four sources publish usable native feeds, so those are consumed
directly (no scraping). The other two have no feed: Discover Lexus is a
JavaScript-rendered site whose story URLs and modified dates are exposed in its
sitemap, and Lexus Polska is server-rendered HTML whose article dates live in a
JSON-LD block. Each source is fetched independently and wrapped so one failing
source is skipped, never fatal — the feed is still built from whatever
succeeded. History accumulates across hourly runs via the shared JSON cache
(``cache/lexus_newsroom_posts.json``); only links not already cached trigger a
per-article metadata fetch, so steady-state runs are cheap.
"""

import argparse
import re
import sys
import time

import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import (
    add_entry_media,
    setup_feed_extensions,
    DEFAULT_HEADERS,
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

FEED_NAME = "lexus_newsroom"
BLOG_URL = "https://pressroom.lexus.com/"

# Native RSS / Atom feeds — parsed directly, no scraping needed.
NATIVE_FEEDS = [
    ("Lexus USA Newsroom", "https://pressroom.lexus.com/feed/atom/"),
    ("Newsroom Lexus Europe", "https://newsroom.lexus.eu/feed/"),
]

# Discover Lexus: a JS-rendered site with no feed. Its sitemap lists every
# story URL plus a <lastmod>, which is enough to build entries without a browser.
DISCOVER_SITEMAP = "https://discoverlexus.com/sitemap.xml"
DISCOVER_BASE = "https://discoverlexus.com"

# Lexus Polska: server-rendered news listing. Article URLs embed the year and
# each article page carries a JSON-LD datePublished.
LEXUS_PL_LISTING = "https://www.lexus-polska.pl/discover-lexus/news"
LEXUS_PL_BASE = "https://www.lexus-polska.pl"
LEXUS_PL_LINK_RE = re.compile(r"^/discover-lexus/news/\d{4}/[\w-]+/?$")

# Polite delay between per-article metadata fetches.
SLEEP_BETWEEN = 0.4

# Cap the merged feed so the committed XML stays a reasonable size.
MAX_ENTRIES = 100


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def parse_date(date_str):
    """Parse a date string into a UTC datetime, or None on failure."""
    if not date_str:
        return None
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return None


def fetch_text(url, retries=3, backoff=2.0, headers=None):
    """Fetch a URL's text body with retries; return None on failure (never raise)."""
    for attempt in range(1, retries + 1):
        try:
            return fetch_page(url, headers=headers)
        except Exception as e:
            logger.warning(f"Fetch failed for {url} (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(backoff * attempt)
    return None


def clean_description(html, fallback=""):
    """Strip HTML to a plain-text summary, sanitized and length-capped."""
    if not html:
        return sanitize_xml(fallback)
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 500:
        text = text[:497].rstrip() + "..."
    return sanitize_xml(text or fallback)


def og_meta(soup, *keys):
    """Return the first matching og:/meta content value on a parsed page."""
    for key in keys:
        tag = soup.find("meta", property=key) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def title_from_slug(href):
    """Last-resort title derived from a URL slug."""
    slug = href.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").replace("_", " ").strip().capitalize()


# ---------------------------------------------------------------------------
# Source: native RSS / Atom feeds
# ---------------------------------------------------------------------------


def parse_native_feed(xml, label):
    """Parse an RSS 2.0 or Atom feed into entry dicts. Handles both shapes."""
    entries = []
    soup = BeautifulSoup(xml, "xml")
    items = soup.find_all("item") or soup.find_all("entry")
    for item in items:
        try:
            title_el = item.find("title")
            title = sanitize_xml(title_el.get_text(strip=True)) if title_el else None

            # RSS <link> carries the URL as text; Atom <link> carries it in href.
            link = None
            link_el = item.find("link")
            if link_el is not None:
                link = (link_el.get_text(strip=True) or link_el.get("href") or "").strip()
            if not link:
                for la in item.find_all("link"):
                    if la.get("rel") in (None, "alternate") and la.get("href"):
                        link = la["href"].strip()
                        break
            if not title or not link:
                continue

            date_el = (
                item.find("pubDate")
                or item.find("published")
                or item.find("updated")
                or item.find("date")
            )
            date_obj = parse_date(date_el.get_text(strip=True)) if date_el else None

            desc_el = (
                item.find("description")
                or item.find("summary")
                or item.find("encoded")
                or item.find("content")
            )
            description = clean_description(desc_el.get_text() if desc_el else "", fallback=title)

            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": description,
                "source": label,
            })
        except Exception as e:
            logger.warning(f"[{label}] skipped a malformed item: {e}")
    logger.info(f"[{label}] parsed {len(entries)} entries")
    return entries


def collect_native_feed(label, url):
    xml = fetch_text(url, headers={**DEFAULT_HEADERS, "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"})
    if not xml:
        logger.warning(f"[{label}] fetch failed — skipping this source")
        return []
    return parse_native_feed(xml, label)


# ---------------------------------------------------------------------------
# Source: Discover Lexus (sitemap-driven)
# ---------------------------------------------------------------------------


def collect_discover_lexus(known_links):
    """Read story URLs + lastmod from the Discover Lexus sitemap; fetch a title
    only for stories we haven't cached yet."""
    label = "Discover Lexus"
    xml = fetch_text(DISCOVER_SITEMAP)
    if not xml:
        logger.warning(f"[{label}] sitemap fetch failed — skipping this source")
        return []

    entries = []
    soup = BeautifulSoup(xml, "xml")
    for url_el in soup.find_all("url"):
        try:
            loc_el = url_el.find("loc")
            if not loc_el:
                continue
            link = loc_el.get_text(strip=True)
            if "/stories/" not in link:
                continue

            lastmod_el = url_el.find("lastmod")
            date_obj = parse_date(lastmod_el.get_text(strip=True)) if lastmod_el else None
            if date_obj is None:
                date_obj = stable_fallback_date(link)

            if link in known_links:
                continue  # already cached; no metadata fetch needed

            title = summary = image = None
            page = fetch_text(link)
            if page:
                psoup = BeautifulSoup(page, "html.parser")
                title = og_meta(psoup, "og:title", "twitter:title")
                if title:
                    title = re.split(r"\s+\|\s+", title)[0].strip()
                summary = og_meta(psoup, "og:description", "description")
                image = og_meta(psoup, "og:image", "twitter:image")
            time.sleep(SLEEP_BETWEEN)

            title = sanitize_xml(title or title_from_slug(link))
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": clean_description(summary, fallback=title),
                "source": label,
                "image": image,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"[{label}] skipped a sitemap entry: {e}")
    logger.info(f"[{label}] collected {len(entries)} new entries")
    return entries


# ---------------------------------------------------------------------------
# Source: Lexus Polska (HTML listing)
# ---------------------------------------------------------------------------


def collect_lexus_polska(known_links):
    """Scrape the Lexus Polska news listing; fetch JSON-LD date + og:title for
    links we haven't cached yet."""
    label = "Lexus Polska"
    html = fetch_text(LEXUS_PL_LISTING)
    if not html:
        logger.warning(f"[{label}] fetch failed — skipping this source")
        return []

    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0].split("#")[0]
        if LEXUS_PL_LINK_RE.match(href) and href not in seen:
            seen.add(href)
            links.append(LEXUS_PL_BASE + href)

    entries = []
    for link in links:
        try:
            if link in known_links:
                continue
            page = fetch_text(link)
            if not page:
                continue
            psoup = BeautifulSoup(page, "html.parser")

            title = og_meta(psoup, "og:title", "twitter:title")
            if title:
                title = re.split(r"\s+\|\s+", title)[0].strip()

            date_obj = None
            for sc in psoup.find_all("script", type="application/ld+json"):
                m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', sc.string or "")
                if m:
                    date_obj = parse_date(m.group(1))
                    break
            if date_obj is None:
                # Fall back to the year embedded in the URL path.
                ym = re.search(r"/news/(\d{4})/", link)
                date_obj = parse_date(f"{ym.group(1)}-01-01") if ym else stable_fallback_date(link)

            summary = og_meta(psoup, "og:description", "description")
            image = og_meta(psoup, "og:image", "twitter:image")
            time.sleep(SLEEP_BETWEEN)

            title = sanitize_xml(title or title_from_slug(link))
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": clean_description(summary, fallback=title),
                "source": label,
                "image": image,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"[{label}] skipped {link}: {e}")
    logger.info(f"[{label}] collected {len(entries)} new entries")
    return entries


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def collect_all(known_links):
    """Collect entries from every source. A failure in one source is logged and
    skipped so the others still contribute."""
    entries = []
    for label, url in NATIVE_FEEDS:
        logger.info(f"Fetching native feed: {label}")
        try:
            entries += collect_native_feed(label, url)
        except Exception as e:
            logger.warning(f"[{label}] unexpected error: {e}")

    logger.info("Scraping Discover Lexus (sitemap) ...")
    try:
        entries += collect_discover_lexus(known_links)
    except Exception as e:
        logger.warning(f"[Discover Lexus] unexpected error: {e}")

    logger.info("Scraping Lexus Polska ...")
    try:
        entries += collect_lexus_polska(known_links)
    except Exception as e:
        logger.warning(f"[Lexus Polska] unexpected error: {e}")

    return entries


def generate_atom_feed(articles, feed_name=FEED_NAME):
    """Build an Atom FeedGenerator from the merged article list."""
    fg = FeedGenerator()
    fg.id(f"{BLOG_URL}#{feed_name}")
    fg.title("Lexus Newsroom")
    fg.subtitle("Lexus news from the USA, Europe, Poland, and the global Discover Lexus stories, in one feed.")
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language("en")
    fg.author({"name": "Lexus"})
    setup_feed_extensions(fg)

    for article in articles:
        fe = fg.add_entry()
        fe.id(article["link"])
        fe.title(article["title"])
        fe.link(href=article["link"])
        source = article.get("source")
        if source:
            fe.category(term=source, label=source)
        fe.description(article.get("description") or article["title"])
        if article.get("date"):
            fe.published(article["date"])
            fe.updated(article["date"])
        add_entry_media(fe, article.get("image"))

    logger.info("Generated Atom feed")
    return fg


def save_atom_feed(fg, feed_name=FEED_NAME):
    """Write the feed to feeds/feed_<name>.xml in Atom format."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return output_file


def main(full=False):
    """Collect every source, merge with cache, and write the Atom feed."""
    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")

    known_links = {e["link"] for e in cached}
    new_articles = collect_all(known_links)

    if not new_articles and not cached:
        logger.warning("No articles collected — skipping write to avoid an empty feed")
        return False

    merged = merge_entries(new_articles, cached, id_field="link", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")

    # Keep full history in the cache so already-seen links are never re-evaluated
    # on later runs; only the rendered feed is capped to the newest MAX_ENTRIES.
    save_cache(FEED_NAME, merged)

    feed_items = merged[-MAX_ENTRIES:] if len(merged) > MAX_ENTRIES else merged

    fg = generate_atom_feed(feed_items)
    save_atom_feed(fg)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Lexus Newsroom Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
