"""Combined native YouTube long-form and live-stream feed."""

import argparse
import sys

import requests
from bs4 import BeautifulSoup

from multi_rss import parse_date, run
from utils import DEFAULT_HEADERS, normalize_link, sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "youtubs"
BLOG_URL = "https://www.youtube.com/"
MAX_PER_CHANNEL = 24
PLAYLIST_PREFIXES = ("UULF", "UULV")

CHANNEL_IDS = (
    "UCwAiG5lj7w24SbgPy6eiYvg",
    "UCpTO7UgWBeiuXtA5ksSkjYg",
    "UCxI9R2o15s4vnGP_Arh575Q",
    "UC1Myj674wRVXB9I4c6Hm5zA",
    "UC_5niPa-d35gg88HaS7RrIw",
    "UCq0OueAsdxH6b8nyAspwViw",
    "UCJmMwjGoRDZSZY5EXEUUu4Q",
    "UC8ga0qpj4m2YPMj2gryDO6A",
    "UCGkX_HCD_T5XOwxi_KR6YoQ",
    "UCk96JambgW5zsOBquR63iEQ",
    "UCQvUwfWSuzKcGflbw5WUFCg",
    "UCzybXLxv08IApdjdN0mJhEg",
    "UC8X4WT5_lUXqMjeN8bGFk9w",
    "UC-716wgP94vhil91RVJwaIQ",
    "UC6VcWc1rAoWdBCM0JxrRQ3A",
    "UCaTXcCfYQd_G5VZeNwsYzPg",
    "UClhEl4bMD8_escGCCTmRAYg",
    "UCMmGbcxT0UbVC9VbxoOyP7A",
)


def channel_feed_urls(channel_id):
    """Derive YouTube's long-form and live playlist feeds from a channel ID."""
    suffix = channel_id[2:] if channel_id.startswith("UC") else channel_id
    return tuple(
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={prefix}{suffix}"
        for prefix in PLAYLIST_PREFIXES
    )


def _find_local(node, name):
    return node.find(
        lambda tag: bool(tag.name) and tag.name.split(":")[-1] == name
    )


def _text_local(node, name):
    element = _find_local(node, name)
    return element.get_text(" ", strip=True) if element else ""


def _entry_link(entry):
    for link in entry.find_all("link"):
        href = (link.get("href") or "").strip()
        if href and link.get("rel") in (None, "alternate"):
            return href
    return ""


def _channel_title(feed):
    author = feed.find("author", recursive=False)
    name = author.find("name") if author else None
    if name and name.get_text(strip=True):
        return sanitize_xml(name.get_text(" ", strip=True))
    title = feed.find("title", recursive=False)
    return (
        sanitize_xml(title.get_text(" ", strip=True))
        if title and title.get_text(strip=True)
        else "YouTube"
    )


def parse_channel_feed(xml, known_links=()):
    """Parse one native YouTube playlist Atom feed."""
    soup = BeautifulSoup(xml or "", "xml")
    feed = soup.find("feed")
    if not feed:
        return []

    source = _channel_title(feed)
    known = {normalize_link(link) for link in known_links}
    entries = []

    for entry in feed.find_all("entry", recursive=False):
        try:
            link = _entry_link(entry)
            normalized = normalize_link(link)
            if not link or normalized in known:
                continue

            title_el = entry.find("title")
            title = (
                sanitize_xml(title_el.get_text(" ", strip=True))
                if title_el
                else ""
            )
            if not title:
                continue

            video_id = _text_local(entry, "videoId")
            published = _text_local(entry, "published")
            updated = _text_local(entry, "updated")
            description = sanitize_xml(_text_local(entry, "description"))
            thumbnail = _find_local(entry, "thumbnail")
            image = (thumbnail.get("url") or "").strip() if thumbnail else ""
            if not image and video_id:
                image = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": parse_date(published or updated),
                    "description": description or title,
                    "source": source,
                    "image": image or None,
                }
            )
            known.add(normalized)
            if len(entries) >= MAX_PER_CHANNEL:
                break
        except Exception as exc:
            logger.warning("Skipping malformed YouTube entry from %s: %s", source, exc)

    return entries


def fetch_youtube_feed(url):
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        response.raise_for_status()
        return response.text
    except Exception as exc:
        logger.warning("YouTube feed %s failed: %s", url, exc)
        return None


def collect_youtubs(known_links):
    entries = []
    seen = set(known_links)
    for channel_id in CHANNEL_IDS:
        for url in channel_feed_urls(channel_id):
            xml = fetch_youtube_feed(url)
            if not xml:
                continue
            channel_entries = parse_channel_feed(xml, seen)
            entries.extend(channel_entries)
            seen.update(entry["link"] for entry in channel_entries)
    logger.info(
        "YouTubs: collected %d videos and live streams from %d channels",
        len(entries),
        len(CHANNEL_IDS),
    )
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="YouTubs",
        subtitle=(
            "Long-form videos and live streams from selected YouTube channels, "
            "directly from native feeds, without Shorts."
        ),
        blog_url=BLOG_URL,
        author="YouTube channels",
        extra_scrapers=(collect_youtubs,),
        max_entries=360,
        per_source_cap=MAX_PER_CHANNEL,
        language="en",
        icon="https://www.youtube.com/favicon.ico",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined YouTubs Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
