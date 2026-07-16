"""Canva combined feed generator.

Canva has no native RSS/Atom feed and both source pages sit behind Cloudflare,
which returns HTTP 403 to plain ``requests``. They're Next.js apps, but the
content ships in each page's ``__NEXT_DATA__`` blob, so one ``curl_cffi``
Chrome-impersonated fetch per section is enough — no browser/JS execution.

This builds **one combined feed** from Canva's two editorial surfaces:

* ``/newsroom/news/`` — company news and announcements. Each post carries a
  real ``publishedAt`` timestamp, so these are genuinely date-ordered.
* ``/learn/`` — the design-tips/tutorials hub. This is an editorial topic
  listing with no publish dates and no chronological order, so — like
  ``beatport_top100.py`` — those articles are dated by the moment they're first
  observed, with that timestamp preserved in the JSON cache across runs.

The two surfaces have disjoint URL spaces, but entries are still
**deduplicated by article URL** for safety. The cache
(``cache/canva_posts.json``) accumulates history and dedupes across runs.

Writes an **Atom** feed to ``feeds/feed_canva.xml``.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta

import pytz
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import (
    add_entry_media,
    deserialize_entries,
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

FEED_NAME = "canva"
BLOG_URL = "https://www.canva.com/newsroom/news/"
NEWSROOM_URL = "https://www.canva.com/newsroom/news/"
LEARN_URL = "https://www.canva.com/learn/"
NEWSROOM_ARTICLE_TMPL = "https://www.canva.com/newsroom/news/{slug}/"
LEARN_ARTICLE_TMPL = "https://www.canva.com/learn/{slug}/"
MAX_ENTRIES = 200


def fetch_html(url: str, retries: int = 3, backoff: float = 2.0) -> str | None:
    """Fetch a Canva page via curl_cffi (Cloudflare 403s plain requests)."""
    try:
        from curl_cffi import requests as creq
    except ImportError:
        logger.warning("curl_cffi not installed; falling back to plain requests (likely 403)")
        from utils import fetch_page

        try:
            return fetch_page(url)
        except Exception as e:
            logger.error(f"Fallback fetch failed for {url}: {e}")
            return None

    for attempt in range(1, retries + 1):
        try:
            resp = creq.get(url, impersonate="chrome", timeout=30)
            if resp.status_code == 200 and "__NEXT_DATA__" in resp.text:
                logger.info(f"Fetched {url} ({len(resp.text)} bytes)")
                return resp.text
            logger.warning(f"Unexpected response (status {resp.status_code}) for {url} on attempt {attempt}")
        except Exception as e:
            logger.warning(f"Fetch failed for {url} (attempt {attempt}/{retries}): {e}")
        if attempt < retries:
            time.sleep(backoff * attempt)
    return None


def _next_data(html: str) -> dict:
    """Return props.pageProps from a page's __NEXT_DATA__, or {} on failure."""
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag is None or not tag.string:
        logger.error("__NEXT_DATA__ script not found — page layout may have changed")
        return {}
    try:
        return json.loads(tag.string)["props"]["pageProps"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Could not parse __NEXT_DATA__ structure: {e}")
        return {}


def _canva_img(obj: dict) -> str | None:
    """Pull an image URL from a Canva post/article object. Both surfaces store
    it as a nested {"url": ...} dict under featuredImage (newsroom) or a couple
    of fallback keys; returns None when nothing usable is present."""
    for key in ("featuredImage", "image", "thumbnail"):
        val = obj.get(key)
        if isinstance(val, dict) and val.get("url"):
            return val["url"]
        if isinstance(val, str) and val:
            return val
    images = obj.get("images")
    if isinstance(images, dict) and images.get("url"):
        return images["url"]
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict) and first.get("url"):
            return first["url"]
    return None


def parse_newsroom(html: str) -> list[dict]:
    """Newsroom posts — real publishedAt dates."""
    props = _next_data(html)
    if not props:
        return []
    posts = list(props.get("featuredArticles") or []) + list(props.get("posts") or [])

    entries: list[dict] = []
    for post in posts:
        try:
            slug = (post.get("slug") or "").strip()
            title = (post.get("name") or "").strip()
            if not slug or not title:
                continue
            link = NEWSROOM_ARTICLE_TMPL.format(slug=slug)

            date = None
            raw_date = post.get("publishedAt")
            if raw_date:
                try:
                    dt = date_parser.parse(raw_date)
                    date = dt.astimezone(pytz.UTC) if dt.tzinfo else pytz.UTC.localize(dt)
                except (ValueError, OverflowError):
                    date = None

            summary = (post.get("summary") or "").strip()
            category = ((post.get("category") or {}).get("title") or "").strip()
            label = f"News · {category}" if category else "News"
            description = f"{summary}\n\n{label}" if summary else label

            entries.append(
                {
                    "title": sanitize_xml(title),
                    "link": link,
                    "date": date,  # may be None; build_feed dates dateless items
                    "description": sanitize_xml(description),
                    "image": _canva_img(post),
                }
            )
        except Exception as e:  # never let one bad post kill the run
            logger.warning(f"Skipping malformed newsroom post: {e}")
            continue

    logger.info(f"Parsed {len(entries)} newsroom entries")
    return entries


def parse_learn(html: str) -> list[dict]:
    """Learn hub articles — dateless, so left undated here (first-seen later)."""
    props = _next_data(html)
    if not props:
        return []
    buckets = list(props.get("featuredPosts") or [])
    for section in props.get("sections") or []:
        buckets.extend(section.get("posts") or [])

    entries: list[dict] = []
    seen_slugs: set[str] = set()
    for art in buckets:
        try:
            slug = (art.get("slug") or "").strip()
            title = (art.get("title") or "").strip()
            if not slug or not title or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            link = LEARN_ARTICLE_TMPL.format(slug=slug)

            excerpt = (art.get("excerpt") or "").strip()
            group = (art.get("primaryGroupTitle") or "").strip()
            label = f"Learn · {group}" if group else "Learn"
            description = f"{excerpt}\n\n{label}" if excerpt else label

            entries.append(
                {
                    "title": sanitize_xml(title),
                    "link": link,
                    "date": None,  # no dates on the hub; first-seen applied later
                    "description": sanitize_xml(description),
                    "image": _canva_img(art),
                }
            )
        except Exception as e:  # never let one bad article kill the run
            logger.warning(f"Skipping malformed learn article: {e}")
            continue

    logger.info(f"Parsed {len(entries)} learn entries")
    return entries


def collect_entries() -> list[dict]:
    """Fetch and parse both surfaces, dating dateless items at first observation.

    Dateless items (all of Learn) are stamped with the run time, offset by their
    listing position so section order is preserved on the first run; the cache
    keeps their original first-seen date afterwards, so only genuinely new items
    surface. Deduped by URL across both surfaces.
    """
    raw: list[dict] = []

    news_html = fetch_html(NEWSROOM_URL)
    if news_html:
        raw.extend(parse_newsroom(news_html))
    else:
        logger.warning("Newsroom fetch failed — continuing with Learn only")

    learn_html = fetch_html(LEARN_URL)
    if learn_html:
        raw.extend(parse_learn(learn_html))
    else:
        logger.warning("Learn fetch failed — continuing with Newsroom only")

    now = datetime.now(pytz.UTC)
    entries: list[dict] = []
    seen: set[str] = set()
    for pos, e in enumerate(raw, start=1):
        link = e["link"]
        if link in seen:
            continue
        seen.add(link)
        if e.get("date") is None:
            e["date"] = now - timedelta(seconds=pos)
        entries.append(e)

    logger.info(f"Collected {len(entries)} combined entries")
    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    fg = FeedGenerator()
    fg.id(f"https://www.canva.com/#{feed_name}")
    fg.title("Canva")
    fg.subtitle("Canva newsroom announcements and Learn design guides")
    setup_feed_links(fg, BLOG_URL, feed_name)
    setup_feed_extensions(fg)
    fg.language("en")
    fg.author({"name": "Canva"})

    for e in entries:
        fe = fg.add_entry()
        fe.id(e["link"])
        fe.title(e["title"])
        fe.link(href=e["link"])
        add_entry_media(fe, e.get("image"))
        fe.description(e["description"])
        if e.get("date"):
            fe.published(e["date"])
            fe.updated(e["date"])

    logger.info("Generated Atom feed")
    return fg


def save_atom_feed(fg, feed_name=FEED_NAME):
    out = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(out), pretty=True)
    logger.info(f"Saved Atom feed to {out}")
    return out


def main(full=False) -> bool:
    new_entries = collect_entries()
    if not new_entries:
        logger.warning("No entries collected — skipping write to avoid an empty feed")
        return False

    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cached = deserialize_entries(load_cache(FEED_NAME).get("entries", []), date_field="date")

    merged = merge_entries(new_entries, cached, id_field="link", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]

    save_cache(FEED_NAME, merged)
    save_atom_feed(generate_atom_feed(merged))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined Canva Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
