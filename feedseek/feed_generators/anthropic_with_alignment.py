"""Anthropic aggregate with the Alignment Science Blog included."""

import argparse
import json
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import anthropic as anthropic_base
from bs4 import BeautifulSoup

from utils import (
    dedupe_entries,
    deserialize_entries,
    fetch_page,
    load_cache,
    merge_entries,
    sanitize_xml,
    save_cache,
    sort_posts_for_feed,
)

logger = anthropic_base.logger

FEED_NAME = anthropic_base.FEED_NAME
ALIGNMENT_URL = "https://alignment.anthropic.com/"
ALIGNMENT_LABEL = "Anthropic Alignment Science"
ALIGNMENT_PATH_RE = re.compile(r"^/20\d{2}/[^/?#]+/?$")
MONTH_YEAR_RE = re.compile(r"^([A-Z][a-z]+)\s+(20\d{2})$")
BIBTEX_DATE_RE = re.compile(
    r"year\s*=\s*\{(20\d{2})\}.*?month\s*=\s*\{([A-Za-z]+)\}.*?day\s*=\s*\{(\d{1,2})\}",
    re.S | re.I,
)


def _json_date(value):
    """Find datePublished/dateCreated recursively in JSON-LD."""
    if isinstance(value, dict):
        for key in ("datePublished", "dateCreated", "uploadDate"):
            if value.get(key):
                return value[key]
        for child in value.values():
            found = _json_date(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _json_date(child)
            if found:
                return found
    return None


def _alignment_date(soup, fallback=None):
    for key in ("article:published_time", "datePublished", "date"):
        value = anthropic_base._meta(soup, key)
        parsed = anthropic_base.parse_date(value) if value else None
        if parsed:
            return parsed

    time_el = soup.find("time", datetime=True)
    if time_el:
        parsed = anthropic_base.parse_date(time_el.get("datetime"))
        if parsed:
            return parsed

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            value = _json_date(json.loads(script.string or script.get_text()))
        except (TypeError, ValueError):
            continue
        parsed = anthropic_base.parse_date(value) if value else None
        if parsed:
            return parsed

    text = soup.get_text(" ", strip=True)
    match = anthropic_base.DATE_RE.search(text)
    if match:
        parsed = anthropic_base.parse_date(match.group(1))
        if parsed:
            return parsed

    match = BIBTEX_DATE_RE.search(text)
    if match:
        parsed = anthropic_base.parse_date(
            f"{match.group(2)} {match.group(3)}, {match.group(1)}"
        )
        if parsed:
            return parsed

    return fallback


def _alignment_meta(url, fallback_date=None):
    try:
        soup = BeautifulSoup(fetch_page(url), "html.parser")
        title_el = soup.find("h1")
        title = anthropic_base._meta(soup, "og:title", "twitter:title")
        title = title or (title_el.get_text(" ", strip=True) if title_el else None)
        if title:
            title = re.split(r"\s[|]\s", title)[0].strip()
        summary = anthropic_base._meta(soup, "og:description", "description")
        image = anthropic_base._meta(soup, "og:image", "twitter:image")
        date = _alignment_date(soup, fallback=fallback_date)
        return {"title": title, "summary": summary, "image": image, "date": date}
    except Exception as exc:
        logger.warning("Could not fetch alignment article %s: %s", url, exc)
        return {"title": None, "summary": None, "image": None, "date": fallback_date}
    finally:
        time.sleep(anthropic_base.SLEEP_BETWEEN)


def scrape_alignment(known_links):
    """Scrape new posts from alignment.anthropic.com."""
    try:
        soup = BeautifulSoup(fetch_page(ALIGNMENT_URL), "html.parser")
    except Exception as exc:
        logger.warning("Could not fetch %s: %s", ALIGNMENT_URL, exc)
        return []

    entries = []
    seen = set()
    fallback_date = None

    for element in soup.find_all(["h2", "a"]):
        if element.name == "h2":
            match = MONTH_YEAR_RE.match(element.get_text(" ", strip=True))
            fallback_date = (
                anthropic_base.parse_date(f"{match.group(1)} 1, {match.group(2)}")
                if match
                else fallback_date
            )
            continue

        href = (element.get("href") or "").strip()
        link = urljoin(ALIGNMENT_URL, href)
        parsed = urlparse(link)
        if parsed.netloc != "alignment.anthropic.com" or not ALIGNMENT_PATH_RE.match(parsed.path):
            continue
        link = f"https://alignment.anthropic.com{parsed.path}"
        if link in known_links or link in seen:
            continue
        seen.add(link)

        meta = _alignment_meta(link, fallback_date=fallback_date)
        title = sanitize_xml(meta["title"] or anthropic_base.title_from_slug(parsed.path))
        summary = sanitize_xml(meta["summary"] or title)
        entries.append(
            {
                "title": title,
                "link": link,
                "date": meta["date"],
                "description": summary,
                "source": ALIGNMENT_LABEL,
                "image": meta["image"],
            }
        )
        logger.info("  [%s] %s", ALIGNMENT_LABEL, title)

    return entries


def main(full=False):
    if full:
        logger.info("Full reset requested; ignoring existing cache")
        cached = []
    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")

    known_links = {entry["link"] for entry in cached}
    new_articles = anthropic_base.scrape_all(known_links)
    new_articles += scrape_alignment(known_links)

    if not new_articles and not cached:
        logger.warning("No articles collected; skipping write to avoid an empty feed")
        return False

    merged = merge_entries(new_articles, cached, id_field="link", date_field="date")
    merged = dedupe_entries(merged, id_field="link", title_field="title", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")
    save_cache(FEED_NAME, merged)

    limit = anthropic_base.MAX_ENTRIES
    feed_items = merged[-limit:] if len(merged) > limit else merged
    fg = anthropic_base.generate_atom_feed(feed_items)
    fg.subtitle(
        "Anthropic Newsroom, Research, Engineering, Red, and Alignment Science posts in one feed."
    )
    anthropic_base.save_atom_feed(fg)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Anthropic Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
