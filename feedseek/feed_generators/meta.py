"""Meta Newsroom feed generator.

Aggregates Meta's public blog streams into one **Atom** feed written to
``feeds/feed_meta_newsroom.xml``:

    - The Meta.com Blog   https://www.meta.com/blog/rss/      (native RSS)
    - Meta Newsroom       https://about.fb.com/feed/          (native RSS)
    - Engineering at Meta https://engineering.fb.com/feed/    (native RSS)
    - AI at Meta Blog     https://ai.meta.com/blog/           (no native feed;
          mirrored by Olshansk/rss-feeds, consumed from its raw GitHub XML)

Plus native RSS developer changelogs (Messenger / WhatsApp / WhatsApp Flows)
and HTML scrapers for the sources with no feed at all: the Pages API and
Instagram Platform doc changelogs, and the Meta-for-Developers, Meta
Developers, and Instagram blogs (all server-rendered, so no browser needed).
The Facebook graph-api changelog is intentionally left out -- it's a
version-diff table, not a datable entry list.

Each source is fetched independently and wrapped so one failing source is
skipped, never fatal -- the feed is still built from whatever succeeded.
History accumulates across hourly runs via the shared JSON cache
(``cache/meta_newsroom_posts.json``).
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
)

logger = setup_logging()

FEED_NAME = "meta_newsroom"
BLOG_URL = "https://about.fb.com/news/"

# Native RSS / Atom feeds (and one mirror) -- parsed directly, no scraping.
NATIVE_FEEDS = [
    ("The Meta.com Blog", "https://www.meta.com/blog/rss/"),
    ("Meta Newsroom", "https://about.fb.com/feed/"),
    ("Engineering at Meta", "https://engineering.fb.com/feed/"),
    # ai.meta.com/blog/ has no native feed; consume the Olshansk mirror.
    ("AI at Meta", "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_meta_ai.xml"),
    # Developer docs changelogs (native RSS under /changelog/rss/).
    ("Messenger Platform Changelog", "https://developers.facebook.com/documentation/business-messaging/messenger-platform/changelog/rss/"),
    ("WhatsApp Changelog", "https://developers.facebook.com/documentation/business-messaging/whatsapp/changelog/rss/"),
    ("WhatsApp Flows Changelog", "https://developers.facebook.com/documentation/business-messaging/whatsapp/flows/changelog/rss/"),
]

# Cap the merged feed so the committed XML stays a reasonable size.
MAX_ENTRIES = 100


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
    """Fetch a URL's text body with retries; return None on failure (never raise).

    meta.com sits behind TLS-fingerprint filtering and 400s a plain requests
    User-Agent, so try curl_cffi Chrome impersonation first when available and
    fall back to the shared fetch_page otherwise.
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


def clean_description(html, fallback=""):
    """Strip HTML to a plain-text summary, sanitized and length-capped."""
    if not html:
        return sanitize_xml(fallback)
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 500:
        text = text[:497].rstrip() + "..."
    return sanitize_xml(text or fallback)


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
        logger.warning(f"[{label}] fetch failed -- skipping this source")
        return []
    return parse_native_feed(xml, label)


# --------------------------------------------------------------------------- #
# HTML scrapers (sources with no native feed). Each is server-rendered; a
# browser is not needed. All are wrapped so one failure is skipped, not fatal.
# --------------------------------------------------------------------------- #
from urllib.parse import urljoin  # noqa: E402

# Developer doc changelogs: a flat list of dated <h2> headings, each followed by
# <h3>/<li>/<p> change notes until the next <h2>. One entry per dated heading.
FB_DOC_CHANGELOGS = [
    ("Pages API Changelog", "https://developers.facebook.com/documentation/pages-api/changelog"),
    ("Instagram Platform Changelog", "https://developers.facebook.com/documentation/instagram-platform/changelog"),
]
# "June 22, 2026" and "November, 15 2025" both occur -- comma may sit after the
# month or the day. dateutil parses either; the regex just gates date-only h2s.
_FB_DATE_RE = re.compile(r"^[A-Za-z]+,?\s+\d{1,2},?\s+\d{4}$")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def scrape_fb_doc_changelog(label, url, known_links):
    html = fetch_text(url)
    if not html:
        logger.warning(f"[{label}] fetch failed -- skipping this source")
        return []
    soup = BeautifulSoup(html, "html.parser")
    short = label.replace(" Changelog", "")
    entries = []
    for h2 in soup.find_all("h2"):
        head = h2.get_text(" ", strip=True)
        if not _FB_DATE_RE.match(head):
            continue
        date_obj = parse_date(head)
        if not date_obj:
            continue
        link = f"{url}#{_slug(head)}"
        if link in known_links:
            continue
        parts = []
        for el in h2.find_all_next():
            if el.name == "h2":
                break
            if el.name in ("h3", "li", "p"):
                t = el.get_text(" ", strip=True)
                if t and t not in parts:
                    parts.append(t)
            if len(parts) >= 30:
                break
        entries.append({
            "title": sanitize_xml(f"{short} \u2014 {head}"),
            "link": link,
            "date": date_obj,
            "description": clean_description(" ".join(parts), fallback=head),
            "source": label,
        })
    logger.info(f"[{label}] scraped {len(entries)} entries")
    return entries


# Blog listings: anchors whose text leads with a date. developers.facebook.com
# encodes the date in the URL (/blog/post/YYYY/MM/DD/slug); the others carry a
# leading "MONTH DD, YYYY" in the link text.
_TEXT_DATE_RE = re.compile(
    r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4})", re.IGNORECASE)
_URL_DATE_RE = re.compile(r"/(20\d\d)/(\d{1,2})/(\d{1,2})/")


def _scrape_blog_anchors(label, url, known_links, href_substr, base=None, min_title=12):
    html = fetch_text(url)
    if not html:
        logger.warning(f"[{label}] fetch failed -- skipping this source")
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen, entries = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0].split("#")[0]
        if href_substr not in href:
            continue
        link = urljoin(base or url, href)
        if link in seen or link in known_links:
            continue
        text = a.get_text(" ", strip=True)
        if not text or text.lower() in ("read now", "read the story", "view all blogs", "blog"):
            continue
        date_obj = None
        m = _TEXT_DATE_RE.search(text)
        if m:
            date_obj = parse_date(m.group(1))
            text = _TEXT_DATE_RE.sub("", text).strip(" \u2014-|\u00b7")
        if date_obj is None:
            mu = _URL_DATE_RE.search(href)
            if mu:
                date_obj = parse_date(f"{mu.group(1)}-{mu.group(2)}-{mu.group(3)}")
        title = re.sub(r"\s+", " ", text).strip()
        if len(title) < min_title:
            continue
        seen.add(link)
        entries.append({
            "title": sanitize_xml(title[:200]),
            "link": link,
            "date": date_obj,
            "description": sanitize_xml(title[:200]),
            "source": label,
        })
    logger.info(f"[{label}] scraped {len(entries)} entries")
    return entries


def scrape_devfb_blog(known_links):
    return _scrape_blog_anchors(
        "Meta for Developers Blog", "https://developers.facebook.com/blog",
        known_links, "/blog/post/", base="https://developers.facebook.com")


def scrape_devmeta_blog(known_links):
    # Cards here link via an untitled image anchor + a "View all blogs" link, so
    # the title lives in the <h2>; pair each heading with its nearest /blog/ link.
    url = "https://developers.meta.com/resources/blog/"
    html = fetch_text(url)
    if not html:
        logger.warning("[Meta Developers] fetch failed -- skipping this source")
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen, entries = set(), []
    for h2 in soup.find_all("h2"):
        title = h2.get_text(" ", strip=True)
        if not title or title.lower() in ("view all blogs", "blog"):
            continue
        a = h2.find("a", href=True) or h2.find_parent("a", href=True) or h2.find_next("a", href=True)
        if not a or "/blog/" not in a.get("href", ""):
            continue
        link = urljoin(url, a["href"].split("?")[0].split("#")[0])
        if link in seen or link in known_links:
            continue
        seen.add(link)
        entries.append({
            "title": sanitize_xml(title[:200]),
            "link": link,
            "date": None,
            "description": sanitize_xml(title[:200]),
            "source": "Meta Developers",
        })
    logger.info(f"[Meta Developers] scraped {len(entries)} entries")
    return entries


def scrape_instagram_blog(known_links):
    # Real posts live at /blog/<category>/<slug> (>=2 path parts); bare
    # /blog/<category> hubs are filtered out by the segment count.
    raw = _scrape_blog_anchors(
        "Instagram Blog", "https://about.instagram.com/blog",
        known_links, "/blog/", base="https://about.instagram.com")
    return [e for e in raw if len([p for p in e["link"].split("/blog/")[-1].split("/") if p]) >= 2]


def collect_all():
    """Collect entries from every source. A failure in one source is logged and
    skipped so the others still contribute."""
    entries = []
    for label, url in NATIVE_FEEDS:
        logger.info(f"Fetching native feed: {label}")
        try:
            entries += collect_native_feed(label, url)
        except Exception as e:
            logger.warning(f"[{label}] unexpected error: {e}")

    known = {e["link"] for e in entries}
    for label, url in FB_DOC_CHANGELOGS:
        try:
            entries += scrape_fb_doc_changelog(label, url, known)
        except Exception as e:
            logger.warning(f"[{label}] unexpected error: {e}")
    for scraper in (scrape_devfb_blog, scrape_devmeta_blog, scrape_instagram_blog):
        try:
            entries += scraper(known)
        except Exception as e:
            logger.warning(f"[{scraper.__name__}] unexpected error: {e}")
    return entries


def generate_atom_feed(articles, feed_name=FEED_NAME):
    """Build an Atom FeedGenerator from the merged article list."""
    fg = FeedGenerator()
    fg.id(f"{BLOG_URL}#{feed_name}")
    fg.title("Meta Newsroom")
    fg.subtitle("Meta news, engineering, and AI blogs plus Meta developer changelogs and blogs -- in one feed.")
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language("en")
    fg.author({"name": "Meta"})

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

    logger.info("Generated Atom feed")
    return fg


def save_atom_feed(fg, feed_name=FEED_NAME):
    """Write the feed to feeds/feed_<n>.xml in Atom format."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return output_file


def main(full=False):
    """Collect every source, merge with cache, and write the Atom feed."""
    if full:
        logger.info("Full reset requested -- ignoring existing cache")
        cached = []
    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")

    new_articles = collect_all()

    if not new_articles and not cached:
        logger.warning("No articles collected -- skipping write to avoid an empty feed")
        return False

    merged = merge_entries(new_articles, cached, id_field="link", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")

    save_cache(FEED_NAME, merged)

    feed_items = merged[-MAX_ENTRIES:] if len(merged) > MAX_ENTRIES else merged

    fg = generate_atom_feed(feed_items)
    save_atom_feed(fg)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Meta Newsroom Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
