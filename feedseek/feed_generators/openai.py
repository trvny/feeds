"""OpenAI feed generator.

Aggregates OpenAI's product/update sources into one **Atom** feed written to
``feeds/feed_openai.xml``:

    - OpenAI News            https://openai.com/news/rss.xml                    (native RSS)
    - OpenAI Engineering     https://openai.com/news/engineering/rss.xml        (native RSS)
    - OpenAI Release notes   https://openai.com/products/release-notes/rss.xml  (native RSS)
    - OpenAI Developers      https://developers.openai.com/rss.xml              (native RSS)
    - Codex changelog        https://developers.openai.com/codex/changelog      (HTML)
    - Apps SDK changelog     https://developers.openai.com/apps-sdk/changelog   (HTML)
    - ChatGPT changelog      https://learn.chatgpt.com/docs/changelog           (HTML)
    - API changelog          https://developers.openai.com/api/docs/changelog   (HTML)

Source handling:
  * RSS feeds — openai.com 403s plain requests (Cloudflare TLS fingerprinting),
    so everything is fetched via curl_cffi Chrome impersonation with a plain
    requests fallback. The News feed is huge (~1000 items), so per-run intake
    is capped to the newest slice; history still accumulates in the cache.
    Research posts (openai.com/research/index) are republished through the
    News RSS, so they arrive via that source — no separate scraper needed.
  * Codex / Apps SDK changelogs — server-rendered Astro pages. Each entry is a
    ``<li id=...>`` with a ``<time>`` stamp, an ``<h3>`` title and an
    ``<article>`` body; the ``li`` id is a stable anchor, so links use it as a
    fragment (fragments are the only differentiator between entries — preserve
    them).
  * API changelog — entries are date-badged grid rows with no year and no
    anchors. The year is inferred by walking the (newest-first) list and
    rolling the year back whenever the month jumps upward; links get a
    synthetic ``#api-<date>-<slug>`` fragment for stable dedupe.

History accumulates across runs via the shared JSON cache
(``cache/openai_posts.json``); entries dedupe by link, then cross-source by
normalized URL/title (News and Engineering overlap).
"""

import argparse
import re
import sys

import pytz
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import (
    dedupe_entries,
    deserialize_entries,
    get_feeds_dir,
    load_cache,
    make_entry_id,
    merge_entries,
    sanitize_xml,
    save_cache,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "openai"
BLOG_URL = "https://openai.com/news/"

# (label, rss_url, per-run intake cap or None)
RSS_SOURCES = [
    ("OpenAI News", "https://openai.com/news/rss.xml", 80),
    ("OpenAI Engineering", "https://openai.com/news/engineering/rss.xml", None),
    ("OpenAI Release notes", "https://openai.com/products/release-notes/rss.xml", 80),
    ("OpenAI Developers", "https://developers.openai.com/rss.xml", None),
    ("OpenAI Codex", "https://developers.openai.com/codex/changelog/rss.xml", None),
]

# (label, page_url) — all share the li/time/h3/article layout.
LI_CHANGELOGS = [
    ("Codex changelog", "https://developers.openai.com/codex/changelog"),
    ("Apps SDK changelog", "https://developers.openai.com/apps-sdk/changelog"),
    ("ChatGPT changelog", "https://learn.chatgpt.com/docs/changelog"),
]

API_CHANGELOG_LABEL = "API changelog"
API_CHANGELOG_URL = "https://developers.openai.com/api/docs/changelog"

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
_BADGE_DATE_RE = re.compile(r"^([A-Z][a-z]{2})\s+(\d{1,2})$")

DESC_LIMIT = 500
MAX_ENTRIES = 200


def _get_html(url):
    """Fetch a URL impersonating Chrome (openai.com 403s plain clients);
    fall back to plain requests if curl_cffi is unavailable. Returns text or None."""
    try:
        from curl_cffi import requests as creq

        resp = creq.get(url, impersonate="chrome", timeout=30)
    except ImportError:
        logger.warning(f"curl_cffi unavailable; using plain requests for {url}")
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"},
                timeout=30,
            )
        except Exception as e:
            logger.warning(f"Fetch failed for {url}: {e}")
            return None
    except Exception as e:
        logger.warning(f"Fetch failed for {url}: {e}")
        return None
    if resp.status_code != 200:
        logger.warning(f"Fetch for {url} returned HTTP {resp.status_code}")
        return None
    return resp.text


def parse_date(date_str):
    """Parse a date string into a UTC datetime, or None on failure."""
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return None


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


# --------------------------------------------------------------------------- #
# Native RSS feeds
# --------------------------------------------------------------------------- #


def scrape_rss(label, rss_url, known_links, cap=None):
    entries = []
    html = _get_html(rss_url)
    if html is None:
        return entries

    try:
        soup = BeautifulSoup(html, "xml")
    except Exception as e:
        logger.warning(f"Could not parse {rss_url}: {e}")
        return entries

    items = soup.find_all("item")
    if cap:
        items = items[:cap]
    for item in items:
        try:
            link_el = item.find("link")
            link = link_el.get_text(strip=True) if link_el else ""
            if not link or link in known_links:
                continue
            title_el = item.find("title")
            title = sanitize_xml(title_el.get_text(strip=True)) if title_el else label
            pub_el = item.find("pubDate")
            date_obj = parse_date(pub_el.get_text(strip=True)) if pub_el else None
            desc_el = item.find("description")
            if desc_el:
                desc = BeautifulSoup(desc_el.get_text(), "html.parser").get_text(" ", strip=True)
                desc = sanitize_xml(desc)[:DESC_LIMIT]
            else:
                desc = title
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": desc or title,
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping malformed item: {e}")
    return entries


# --------------------------------------------------------------------------- #
# Codex / Apps SDK changelogs (li id + time + h3 + article)
# --------------------------------------------------------------------------- #


def scrape_li_changelog(label, page_url, known_links):
    entries = []
    html = _get_html(page_url)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")

    items = soup.select("section[data-changelog-month-section] li[id]")
    if not items:
        logger.warning(f"  [{label}] no changelog entries matched — layout may have changed")
        return entries

    for li in items:
        try:
            anchor = li.get("id")
            link = f"{page_url}#{anchor}"
            if link in known_links:
                continue
            time_el = li.find("time")
            date_obj = parse_date(time_el.get_text(strip=True)) if time_el else None
            h3 = li.find("h3")
            # The h3 wraps the title span plus a copy-link button; take the span.
            span = h3.find("span") if h3 else None
            title_text = (span or h3).get_text(" ", strip=True) if h3 else anchor
            title = sanitize_xml(re.sub(r"\s+", " ", title_text))
            body_el = li.find("article")
            desc = body_el.get_text(" ", strip=True)[:DESC_LIMIT] if body_el else title
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": sanitize_xml(desc) or title,
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping malformed item: {e}")
    return entries


# --------------------------------------------------------------------------- #
# API changelog (date-badged grid rows; no year, no anchors)
# --------------------------------------------------------------------------- #


def scrape_api_changelog(known_links, today=None):
    import datetime as _dt

    label = API_CHANGELOG_LABEL
    entries = []
    html = _get_html(API_CHANGELOG_URL)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")

    rows = []
    for badge in soup.find_all("div", attrs={"data-variant": "outline"}):
        m = _BADGE_DATE_RE.match(badge.get_text(strip=True))
        if not m:
            continue
        row = badge.find_parent("div", class_=re.compile(r"grid"))
        if row is not None:
            rows.append((m.group(1), int(m.group(2)), row))
    if not rows:
        logger.warning(f"  [{label}] no changelog entries matched — layout may have changed")
        return entries

    # Rows are newest-first with no year on the badge. Anchor the first row to
    # the current year (stepping back one year if that lands in the future),
    # then roll the year back whenever the month jumps upward as we descend.
    today = today or _dt.datetime.now(pytz.UTC)
    year = today.year
    prev_month = None
    for mon_name, day, row in rows:
        try:
            month = MONTHS[mon_name]
            if prev_month is None:
                if (month, day) > (today.month, today.day + 7):
                    year -= 1
            elif month > prev_month:
                year -= 1
            prev_month = month
            date_obj = _dt.datetime(year, month, day, tzinfo=pytz.UTC)

            content = row.find("div", class_=re.compile(r"MarkdownContent"))
            text = content.get_text(" ", strip=True) if content else ""
            if not text:
                continue
            first_sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
            tags = [
                b.get_text(strip=True)
                for b in row.find_all("div", attrs={"data-variant": "soft"})
            ]
            kind = tags[0] if tags else "Update"
            title = first_sentence if len(first_sentence) <= 110 else first_sentence[:107] + "..."
            title = sanitize_xml(f"{kind}: {title}")

            frag = f"api-{date_obj.date().isoformat()}-{slugify(' '.join(text.split()[:6]))[:48]}"
            link = f"{API_CHANGELOG_URL}#{frag}"
            if link in known_links:
                continue
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": sanitize_xml(text)[:DESC_LIMIT] or title,
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping malformed item: {e}")
    return entries


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def scrape_all(known_links):
    new_entries = []
    for label, url, cap in RSS_SOURCES:
        logger.info(f"Scraping {label} ...")
        new_entries += scrape_rss(label, url, known_links, cap=cap)
    for label, url in LI_CHANGELOGS:
        logger.info(f"Scraping {label} ...")
        new_entries += scrape_li_changelog(label, url, known_links)
    logger.info(f"Scraping {API_CHANGELOG_LABEL} ...")
    new_entries += scrape_api_changelog(known_links)
    return new_entries


def generate_atom_feed(articles, feed_name=FEED_NAME):
    fg = FeedGenerator()
    fg.id(f"https://openai.com/{feed_name}")
    fg.title("OpenAI")
    fg.subtitle(
        "OpenAI product updates: News (incl. Research), Engineering, Release "
        "notes, Developers, and the Codex / Apps SDK / API changelogs."
    )
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language("en")
    fg.author({"name": "OpenAI"})

    for article in articles:
        fe = fg.add_entry()
        fe.id(make_entry_id(FEED_NAME, article["link"]))
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
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return output_file


def main(full=False):
    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")

    known_links = {e["link"] for e in cached}
    new_articles = scrape_all(known_links)

    if not new_articles and not cached:
        logger.warning("No articles collected — skipping write to avoid an empty feed")
        return False

    merged = merge_entries(new_articles, cached, id_field="link", date_field="date")
    merged = dedupe_entries(merged, id_field="link", title_field="title", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")

    # Keep full (deduplicated) history in the cache so already-seen links are
    # never re-evaluated on later runs; only the rendered feed is capped.
    save_cache(FEED_NAME, merged)

    feed_items = merged[-MAX_ENTRIES:] if len(merged) > MAX_ENTRIES else merged

    fg = generate_atom_feed(feed_items)
    save_atom_feed(fg)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the OpenAI Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
