"""X (Twitter) API changelog feed generator.

Turns the developer changelog at ``https://docs.x.com/changelog`` into an
**Atom** feed at ``feeds/feed_x_changelog.xml``.

Why only the changelog, and not the blogs or user timelines that were also
requested:

    - blog.x.com and blog.x.com/engineering are frozen archives -- the newest
      posts are from 2023 (Twitter era). A self-updating feed for a dead blog
      would just trip validate_feeds.py's staleness guard, so they're omitted.
    - x.com/<user> timelines (x, api, elonmusk, AnthropicAI, prezydentpl,
      POTUS, realDonaldTrump) are a JS-rendered, login-walled SPA. The served
      HTML carries no tweet data; reading it needs the paid X API or auth
      tokens, neither viable from CI/datacenter IPs. Out of scope here.

The changelog itself is a live, well-dated Mintlify page (server-rendered HTML,
behind Cloudflare -> curl_cffi). Each entry is an ``<h3 id=...>`` heading with a
"Mon DD, YYYY" date sitting just before it in the DOM and an anchor link of the
form ``.../changelog#<id>``. ~190 entries back to 2016; we cap to MAX_ENTRIES.
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
    deserialize_entries,
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

FEED_NAME = "x_changelog"
BLOG_URL = "https://docs.x.com/changelog"
MAX_ENTRIES = 100

DATE_RE = re.compile(r"\b([A-Z][a-z]{2}\s+\d{1,2},\s+20\d\d)\b")


def fetch_text(url, retries=3, backoff=2.0):
    """Fetch via curl_cffi Chrome impersonation; None on failure (never raise)."""
    try:
        from curl_cffi import requests as creq
    except ImportError:
        creq = None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
        ),
    }
    for attempt in range(1, retries + 1):
        try:
            if creq is not None:
                resp = creq.get(url, headers=headers, impersonate="chrome", timeout=30)
                resp.raise_for_status()
                return resp.text
            from utils import fetch_page
            return fetch_page(url, headers=headers)
        except Exception as e:
            logger.warning(f"Fetch failed for {url} (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(backoff * attempt)
    return None


def parse_date(date_str):
    """'Mon DD, YYYY' -> UTC datetime (midnight), or None."""
    try:
        dt = date_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError):
        return None


def clean_description(text, fallback=""):
    if not text:
        return sanitize_xml(fallback)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 500:
        text = text[:497].rstrip() + "..."
    return sanitize_xml(text or fallback)


def parse_items(html):
    """Return entry dicts (title, link, date, description) for each changelog h3."""
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for h in soup.find_all("h3"):
        try:
            hid = h.get("id")
            if not hid:
                continue
            title = sanitize_xml(h.get_text(" ", strip=True).lstrip("\u200b").strip())
            if not title:
                continue
            link = f"{BLOG_URL}#{hid}"

            # The "Mon DD, YYYY" label renders just before the heading in the DOM.
            date_obj = None
            ds = h.find_previous(string=DATE_RE)
            if ds:
                m = DATE_RE.search(str(ds))
                if m:
                    date_obj = parse_date(m.group(1))

            # First real sentence after the heading makes the lead. Skip the
            # zero-width spacer and the repeated-title node; stop before the
            # next entry's date label so we don't bleed across entries.
            description = title
            for n in h.find_all_next(["p", "span", "div", "li"], limit=30):
                txt = n.get_text(" ", strip=True).replace("\u200b", "").strip()
                if DATE_RE.search(txt):
                    break  # reached the next changelog entry
                if len(txt) >= 25 and txt != title and not title.startswith(txt):
                    description = txt
                    break
            description = clean_description(description, fallback=title)

            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": description,
            })
        except Exception as e:
            logger.warning(f"Skipped a malformed changelog entry: {e}")
    logger.info(f"Parsed {len(entries)} changelog entries")
    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    fg = FeedGenerator()
    fg.id(f"{BLOG_URL}#{feed_name}")
    fg.title("X API Changelog")
    fg.subtitle("Release notes and changes to the X (Twitter) developer API, from docs.x.com/changelog.")
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language("en")
    fg.author({"name": "X"})

    for e in entries:
        fe = fg.add_entry()
        fe.id(e["link"])
        fe.title(e["title"])
        fe.link(href=e["link"])
        fe.description(e.get("description") or e["title"])
        if e.get("date"):
            fe.published(e["date"])
            fe.updated(e["date"])
    logger.info("Generated Atom feed")
    return fg


def save_atom_feed(fg, feed_name=FEED_NAME):
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return output_file


def main(full=False):
    html = fetch_text(BLOG_URL)
    if html is None:
        logger.error("Fetch failed -- skipping write to preserve the last good feed")
        return False
    new_entries = parse_items(html)
    if not new_entries:
        logger.warning("No entries parsed -- skipping write to avoid an empty feed")
        return False

    cached = [] if full else deserialize_entries(
        load_cache(FEED_NAME).get("entries", []), date_field="date"
    )
    merged = merge_entries(new_entries, cached, id_field="link", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]

    save_cache(FEED_NAME, merged)
    save_atom_feed(generate_atom_feed(merged))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the X API Changelog Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
