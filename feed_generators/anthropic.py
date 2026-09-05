"""Anthropic aggregate with Alignment Science and Interpretability included."""

import argparse
import json
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import _anthropic_base as anthropic_base
import feedparser
from bs4 import BeautifulSoup
from enrich import enrich_entries
from entry_identity import persist_entry_ids
from utils import (
    dedupe_entries,
    deserialize_entries,
    feedparser_entry_image,
    fetch_page,
    load_cache,
    merge_entries,
    sanitize_xml,
    save_atom_feed,
    save_cache,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = anthropic_base.logger

FEED_NAME = "anthropic"
SOURCES = anthropic_base.SOURCES
BLOG_URL = anthropic_base.BLOG_URL
ALIGNMENT_URL = "https://alignment.anthropic.com/"
ALIGNMENT_LABEL = "Anthropic Alignment Science"
TRANSFORMER_CIRCUITS_FEED_URL = "https://transformer-circuits.pub/feed.xml"
TRANSFORMER_CIRCUITS_LABEL = "Anthropic Interpretability"
PRESERVE_MISSING_DATE = "_feedseek_preserve_missing_date"
ALIGNMENT_PATH_RE = re.compile(r"^/20\d{2}/[^/?#]+/?$")
ALIGNMENT_YEAR_RE = re.compile(r"^/(20\d{2})/")
MONTH_YEAR_RE = re.compile(r"^([A-Z][a-z]+)\s+(20\d{2})$")
BIBTEX_DATE_RE = re.compile(
    r"year\s*=\s*\{(20\d{2})\}.*?month\s*=\s*\{([A-Za-z]+)\}.*?day\s*=\s*\{(\d{1,2})\}",
    re.DOTALL | re.IGNORECASE,
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


def _month_start(text):
    match = MONTH_YEAR_RE.fullmatch(re.sub(r"\s+", " ", text or "").strip())
    if not match:
        return None
    return anthropic_base.parse_date(f"{match.group(1)} 1, {match.group(2)}")


def _alignment_index(soup):
    """Yield article links with the month heading that precedes each card.

    Month labels are plain text in the current site markup rather than stable
    heading elements. Walking text nodes keeps document order without depending
    on whether the label is rendered as an h2, div, paragraph, or span.
    """
    fallback_date = None
    seen = set()
    for node in soup.find_all(string=True):
        text = re.sub(r"\s+", " ", str(node)).strip()
        month_date = _month_start(text)
        if month_date:
            fallback_date = month_date
            continue

        anchor = node.find_parent("a", href=True)
        if anchor is None:
            continue
        href = (anchor.get("href") or "").strip()
        link = urljoin(ALIGNMENT_URL, href)
        parsed = urlparse(link)
        if parsed.netloc != "alignment.anthropic.com" or not ALIGNMENT_PATH_RE.match(
            parsed.path
        ):
            continue
        link = f"https://alignment.anthropic.com{parsed.path}"
        if link in seen:
            continue
        seen.add(link)
        yield link, fallback_date


def _year_fallback(link):
    path = urlparse(link or "").path
    match = ALIGNMENT_YEAR_RE.match(path)
    return anthropic_base.parse_date(f"January 1, {match.group(1)}") if match else None


def _new_alignment_entry(link, meta, fallback_date):
    parsed = urlparse(link)
    title = sanitize_xml(meta["title"] or anthropic_base.title_from_slug(parsed.path))
    return {
        "title": title,
        "link": link,
        "date": meta["date"] or fallback_date or _year_fallback(link),
        "description": sanitize_xml(meta["summary"] or title),
        "source": ALIGNMENT_LABEL,
        "image": meta["image"],
    }


def _refresh_alignment_entry(cached, meta, fallback_date):
    """Merge a recovered date without discarding richer cached metadata."""
    refreshed = dict(cached)
    refreshed["date"] = meta["date"] or fallback_date or _year_fallback(
        refreshed.get("link")
    )
    refreshed.pop(PRESERVE_MISSING_DATE, None)
    if meta["title"]:
        refreshed["title"] = sanitize_xml(meta["title"])
    if meta["summary"]:
        refreshed["description"] = sanitize_xml(meta["summary"])
    if meta["image"]:
        refreshed["image"] = meta["image"]
    refreshed["source"] = ALIGNMENT_LABEL
    return refreshed


def scrape_alignment(known_links, refresh_entries=None):
    """Scrape new posts and refresh cached entries that still lack dates."""
    try:
        soup = BeautifulSoup(fetch_page(ALIGNMENT_URL), "html.parser")
    except Exception as exc:
        logger.warning("Could not fetch %s: %s", ALIGNMENT_URL, exc)
        return []

    refresh_entries = refresh_entries or {}
    entries = []
    for link, fallback_date in _alignment_index(soup):
        cached = refresh_entries.get(link)
        if link in known_links and cached is None:
            continue

        meta = _alignment_meta(
            link,
            fallback_date=fallback_date or _year_fallback(link),
        )
        entry = (
            _refresh_alignment_entry(cached, meta, fallback_date)
            if cached is not None
            else _new_alignment_entry(link, meta, fallback_date)
        )
        entries.append(entry)
        logger.info("  [%s] %s", ALIGNMENT_LABEL, entry["title"])

    return entries


def scrape_transformer_circuits(known_links):
    """Collect Anthropic Interpretability posts from its native Atom feed."""
    try:
        raw = fetch_page(TRANSFORMER_CIRCUITS_FEED_URL)
    except Exception as exc:
        logger.warning("Could not fetch %s: %s", TRANSFORMER_CIRCUITS_FEED_URL, exc)
        return []

    parsed = feedparser.parse(raw)
    entries = []
    for item in parsed.entries:
        try:
            link = (item.get("link") or "").strip()
            title = sanitize_xml((item.get("title") or "").strip())
            if not link or not title or link in known_links:
                continue
            date = anthropic_base.parse_date(item.get("published") or item.get("updated"))
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date or stable_fallback_date(link),
                    "description": sanitize_xml(item.get("summary") or "") or title,
                    "source": TRANSFORMER_CIRCUITS_LABEL,
                    "image": feedparser_entry_image(item),
                }
            )
        except Exception as exc:
            logger.warning("[%s] skipping an entry: %s", TRANSFORMER_CIRCUITS_LABEL, exc)
    logger.info("[%s] parsed %d entries", TRANSFORMER_CIRCUITS_LABEL, len(entries))
    return entries


def _feed_entry(entry):
    """Render retryable cache rows with a stable year fallback, without persisting it."""
    if entry.get("date") is not None or not entry.get(PRESERVE_MISSING_DATE):
        return entry
    rendered = dict(entry)
    rendered["date"] = _year_fallback(rendered.get("link"))
    return rendered


def doc_sources():
    """Expose the public aggregate's sources with their canonical labels."""
    core = [(label, url) for label, url, *_ in anthropic_base.SOURCES]
    return [
        *core,
        (anthropic_base.RED_LABEL, anthropic_base.RED_BASE),
        (ALIGNMENT_LABEL, ALIGNMENT_URL),
        (TRANSFORMER_CIRCUITS_LABEL, TRANSFORMER_CIRCUITS_FEED_URL),
    ]


def main(full=False):
    if full:
        logger.info("Full reset requested; ignoring existing cache")
        cached = []
        undated_alignment_entries = {}
    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")
        undated_alignment_entries = {
            entry["link"]: entry
            for entry in cached
            if entry.get("source") == ALIGNMENT_LABEL and not entry.get("date")
        }
        for entry in undated_alignment_entries.values():
            entry[PRESERVE_MISSING_DATE] = True

    known_links = {entry["link"] for entry in cached}
    new_articles = anthropic_base.scrape_all(known_links)
    alignment_articles = scrape_alignment(
        known_links,
        refresh_entries=undated_alignment_entries,
    )
    transformer_circuits_articles = scrape_transformer_circuits(known_links)
    refreshed_links = {entry["link"] for entry in alignment_articles}
    if refreshed_links:
        cached = [
            entry
            for entry in cached
            if not (
                entry.get("source") == ALIGNMENT_LABEL
                and entry.get("link") in refreshed_links
            )
        ]
    new_articles += alignment_articles + transformer_circuits_articles

    if not new_articles and not cached:
        logger.warning("No articles collected; skipping write to avoid an empty feed")
        return False

    merged = merge_entries(new_articles, cached, id_field="link", date_field="date")
    merged = dedupe_entries(
        merged, id_field="link", title_field="title", date_field="date"
    )
    merged = sort_posts_for_feed(merged, date_field="date")

    # This registered wrapper historically published raw links as entry IDs.
    persist_entry_ids(FEED_NAME, merged, make_entry_id=lambda _feed, link: link)

    feed_items = merged[-anthropic_base.MAX_ENTRIES :]

    enrich_entries(feed_items)
    save_cache(FEED_NAME, merged)
    fg = anthropic_base.generate_atom_feed([_feed_entry(entry) for entry in feed_items])
    fg.subtitle(
        "Anthropic Newsroom, Research, Engineering, Red, Alignment Science, and Interpretability posts in one feed."
    )
    save_atom_feed(fg, FEED_NAME)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Anthropic Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
