"""SkillsLLM + MCP / Claude Skills ecosystem feed generator.

Combines AI-tooling sites into a single Atom feed (``feeds/feed_skillsllm.xml``)
using three discovery strategies, each source isolated so one failure never
sinks the run:

Native RSS/Atom feeds (feedparser):
  * Model Context Protocol  https://blog.modelcontextprotocol.io/index.xml
  * FastMCP (changelog)     https://gofastmcp.com/changelog/rss.xml
  * ClaudePluginHub         https://claudepluginhub.com/feed.xml
  * OpenRouter (blog)       https://openrouter.ai/blog/feed.xml
  * LiteLLM (blog)          https://docs.litellm.ai/blog/rss.xml
  * LiteLLM (release notes) https://github.com/BerriAI/litellm/releases.atom
                            (docs.litellm.ai/release_notes is a dateless HTML
                            mirror of these GitHub releases)

Sitemap discovery + per-page detail fetch (no native feed; pages server-render
real ``<title>`` / ``<meta description>`` and sometimes ``article:published_time``):
  * SkillsLLM           https://skillsllm.com        (/news daily summaries + /blog guides)
  * Desktop Commander   https://desktopcommander.app (/blog posts)
  * Claude Skills Hub   https://claudeskills.info    (/blog posts via sitemap_blog.xml)

Index asset-slug discovery + detail fetch (no feed, no sitemap):
  * MCP Servers Blog    https://blog.mcpservers.org  (/posts/<slug>, slugs from
                        /assets/blog/<slug>/ paths on the index)


Note: https://mcpservers.org itself is a server *directory* (thousands of
catalog pages, no news stream), so it is intentionally not aggregated here.

Dates, per source:
  * SkillsLLM news      — from the ``/news/ai-news-YYYY-MM-DD`` slug
  * SkillsLLM blog      — from the sitemap ``<lastmod>``
  * Claude Skills Hub   — from the sitemap ``<lastmod>`` (or page ``published_time``)
  * Desktop Commander   — from the page's ``article:published_time`` meta
  * Native feeds        — from the feed entry's published/updated date
  * MCP Servers Blog    — no date exposed; stable per-link fallback

Entries merge into a local cache (dedup by ``link``).
"""

import argparse
import re
import sys
import time
from datetime import datetime

import pytz
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import (
    add_entry_media,
    setup_feed_extensions,
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

FEED_NAME = "skillsllm"
BLOG_URL = "https://skillsllm.com/"

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_SKILLSLLM_NEWS_DATE_RE = re.compile(r"/news/ai-news-(\d{4}-\d{2}-\d{2})")

# Desktop Commander's sitemap also lists taxonomy/index pages under /blog/;
# only real posts should become entries.
_DC_SKIP_RE = re.compile(r"/blog/(about|author|category|tag|page)(/|$)|/blog/?$")

# Per-source configuration. ``include`` decides which sitemap URLs are article
# candidates; ``sitemap_date`` extracts a date from the sitemap entry (return
# None to rely on the article page / fallback); ``use_lastmod`` gates whether
# <lastmod> is trustworthy for dating; ``title_suffixes`` are stripped from
# page titles; ``category`` maps a link to its feed category.
SOURCES = [
    {
        "label": "SkillsLLM",
        "sitemap": "https://skillsllm.com/sitemap.xml",
        "include": lambda loc: "/news/" in loc or "/blog/" in loc,
        "slug_date_re": _SKILLSLLM_NEWS_DATE_RE,
        "use_lastmod": True,
        "title_suffixes": (" | SkillsLLM Blog", " | SkillsLLM"),
        "category": lambda loc: "news" if "/news/" in loc else "blog",
        "max_candidates": 60,
    },
    {
        "label": "Desktop Commander",
        "sitemap": "https://desktopcommander.app/sitemap.xml",
        "include": lambda loc: "/blog/" in loc and not _DC_SKIP_RE.search(loc),
        "slug_date_re": None,
        "use_lastmod": False,  # sitemap stamps every URL with the build date
        "title_suffixes": (" | Desktop Commander Blog", " | Desktop Commander"),
        "category": lambda loc: "desktop-commander",
        "max_candidates": 40,
    },
    {
        "label": "Claude Skills Hub",
        "sitemap": "https://claudeskills.info/sitemap_blog.xml",
        "include": lambda loc: "/blog/" in loc and not loc.rstrip("/").endswith("/blog"),
        "slug_date_re": None,
        "use_lastmod": True,  # sitemap_blog stamps each post with its real date
        "title_suffixes": (" - Claude Skills Hub",),
        "category": lambda loc: "claude-skills",
        "max_candidates": 40,
    },
]

# Native RSS/Atom feeds from the MCP / Claude-skills ecosystem. These already
# expose a feed endpoint, so they take the feedparser path rather than sitemap
# discovery. (label, url, category)
NATIVE_FEEDS = [
    ("Model Context Protocol", "https://blog.modelcontextprotocol.io/index.xml", "mcp"),
    ("FastMCP", "https://gofastmcp.com/changelog/rss.xml", "fastmcp"),
    ("ClaudePluginHub", "https://claudepluginhub.com/feed.xml", "plugins"),
    # LLM gateways / routers. OpenRouter's blog feed is large, so cap it; the
    # LiteLLM docs release_notes pages are a dateless HTML mirror of the GitHub
    # releases, so the dated releases.atom is used for those instead. Optional
    # 4th tuple element caps how many of the newest entries are taken.
    ("OpenRouter", "https://openrouter.ai/blog/feed.xml", "openrouter", 30),
    ("LiteLLM Blog", "https://docs.litellm.ai/blog/rss.xml", "litellm", 20),
    ("LiteLLM Releases", "https://github.com/BerriAI/litellm/releases.atom", "litellm-releases", 15),
]

# blog.mcpservers.org is a small Next.js blog with no feed and no sitemap, but
# its post slugs leak through /assets/blog/<slug>/ asset paths on the index and
# each post server-renders a real <title> at /posts/<slug>. We discover slugs
# from those asset paths, then reuse fetch_detail to pull the title. Posts carry
# no published_time meta, so they fall back to a stable per-link date.
MCPSERVERS_BLOG_BASE = "https://blog.mcpservers.org"
MCPSERVERS_BLOG_SOURCE = {
    "label": "MCP Servers Blog",
    "title_suffixes": (" | MCP Servers",),
    "category": lambda loc: "mcp-servers",
}
_MCPSERVERS_SLUG_RE = re.compile(r"/assets/blog/([a-z0-9][a-z0-9-]*)/")


# Cap the merged feed so the committed XML stays a reasonable size.
MAX_ENTRIES = 400


def fetch_url(url, retries=3, backoff=2.0):
    """Fetch *url* text, retrying transient failures. None on failure."""
    for attempt in range(1, retries + 1):
        try:
            return fetch_page(url, headers=FETCH_HEADERS)
        except Exception as e:
            logger.warning(f"Fetch failed for {url} (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(backoff * attempt)
    return None


def parse_date(value):
    """Parse a date string into a UTC datetime, or None."""
    try:
        dt = date_parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt.astimezone(pytz.UTC)
    except (ValueError, TypeError, OverflowError):
        return None


def discover_urls(source):
    """Return [(link, sitemap_date)] for one source's articles, newest first.

    None on a sitemap fetch failure (so the caller can skip the source without
    treating it as \"zero articles\").
    """
    sitemap_xml = fetch_url(source["sitemap"])
    if sitemap_xml is None:
        return None

    soup = BeautifulSoup(sitemap_xml, "xml")
    found = []
    for url_el in soup.find_all("url"):
        loc_el = url_el.find("loc")
        if not loc_el:
            continue
        loc = loc_el.get_text(strip=True)
        if not source["include"](loc):
            continue

        date_obj = None
        slug_re = source.get("slug_date_re")
        if slug_re:
            slug_match = slug_re.search(loc)
            if slug_match:
                date_obj = parse_date(slug_match.group(1))
        if date_obj is None and source["use_lastmod"]:
            lastmod_el = url_el.find("lastmod")
            if lastmod_el:
                date_obj = parse_date(lastmod_el.get_text(strip=True))

        found.append((loc, date_obj))

    found.sort(key=lambda t: (t[1] or datetime.min.replace(tzinfo=pytz.UTC)), reverse=True)
    logger.info(f"[{source['label']}] discovered {len(found)} article URLs in sitemap")
    return found[: source["max_candidates"]]


def _clean_title(raw, suffixes):
    title = sanitize_xml(raw.strip())
    for suffix in suffixes:
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
            break
    return title


def fetch_detail(link, sitemap_date, source):
    """Fetch one article page and return a normalized entry dict, or None."""
    html = fetch_url(link)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find("title")
    title = _clean_title(title_el.get_text(), source["title_suffixes"]) if title_el else None
    if not title:
        return None

    desc_el = soup.find("meta", attrs={"name": "description"})
    description = sanitize_xml(desc_el["content"].strip()) if desc_el and desc_el.get("content") else title

    img_el = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "twitter:image"})
    image = img_el["content"].strip() if img_el and img_el.get("content") else None

    # Prefer the page's own publish date when the site exposes one.
    page_date = None
    pub_el = soup.find("meta", attrs={"property": "article:published_time"})
    if pub_el and pub_el.get("content"):
        page_date = parse_date(pub_el["content"])

    return {
        "title": title,
        "link": link,
        "date": page_date or sitemap_date or stable_fallback_date(link),
        "description": description or title,
        "source": source["label"],
        "category": source["category"](link),
        "image": image,
    }


def collect_entries(known_links):
    """Discover and fetch new articles from every source.

    *known_links* is the set of links already in the cache; those are skipped
    (their cached entry is reused by the merge step). Returns None only if
    every source's sitemap failed, so a total outage preserves the last good
    feed while a single dead source doesn't.
    """
    entries = []
    any_sitemap_ok = False

    for source in SOURCES:
        discovered = discover_urls(source)
        if discovered is None:
            logger.warning(f"[{source['label']}] sitemap unavailable; continuing")
            continue
        any_sitemap_ok = True

        fetched = 0
        for link, sitemap_date in discovered:
            if link in known_links:
                continue
            try:
                entry = fetch_detail(link, sitemap_date, source)
                if entry:
                    entries.append(entry)
                    fetched += 1
                else:
                    logger.warning(f"[{source['label']}] no usable title for {link}; skipping")
            except Exception as e:  # never let one bad page kill the run
                logger.warning(f"[{source['label']}] skipping {link}: {e}")
        logger.info(f"[{source['label']}] fetched details for {fetched} new article(s)")

    if not any_sitemap_ok:
        return None
    return entries


def collect_native_feeds():
    """Fetch the native RSS/Atom feeds with feedparser. Per-feed isolated."""
    entries = []
    for feed in NATIVE_FEEDS:
        label, url, category = feed[0], feed[1], feed[2]
        cap = feed[3] if len(feed) > 3 else None
        raw = fetch_url(url)
        if raw is None:
            logger.warning(f"[{label}] feed unavailable; continuing")
            continue
        parsed = feedparser.parse(raw)
        count = 0
        items = parsed.entries[:cap] if cap else parsed.entries
        for e in items:
            try:
                link = (e.get("link") or "").strip()
                title = sanitize_xml((e.get("title") or "").strip())
                if not link or not title:
                    continue
                date = None
                for key in ("published_parsed", "updated_parsed"):
                    struct = e.get(key)
                    if struct:
                        date = datetime(*struct[:6], tzinfo=pytz.UTC)
                        break
                entries.append(
                    {
                        "title": title,
                        "link": link,
                        "date": date or stable_fallback_date(link),
                        "description": sanitize_xml(e.get("summary") or "") or title,
                        "source": label,
                        "category": category,
                    }
                )
                count += 1
            except Exception as exc:  # one bad item never kills the feed
                logger.warning(f"[{label}] skipping an entry: {exc}")
        logger.info(f"[{label}] parsed {count} entries")
    return entries


def collect_mcpservers_blog(known_links):
    """Discover blog.mcpservers.org posts from index asset paths, fetch titles."""
    index_html = fetch_url(MCPSERVERS_BLOG_BASE + "/")
    if index_html is None:
        logger.warning("[MCP Servers Blog] index unavailable; continuing")
        return []
    slugs = sorted(set(_MCPSERVERS_SLUG_RE.findall(index_html)))
    if not slugs:
        logger.warning("[MCP Servers Blog] no post slugs found on index; continuing")
        return []

    entries = []
    for slug in slugs:
        link = f"{MCPSERVERS_BLOG_BASE}/posts/{slug}"
        if link in known_links:
            continue
        try:
            entry = fetch_detail(link, None, MCPSERVERS_BLOG_SOURCE)
            if entry:
                entries.append(entry)
            else:
                logger.warning(f"[MCP Servers Blog] no usable title for {link}; skipping")
        except Exception as exc:
            logger.warning(f"[MCP Servers Blog] skipping {link}: {exc}")
    logger.info(f"[MCP Servers Blog] fetched details for {len(entries)} new post(s)")
    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    """Build an Atom FeedGenerator from the normalized entry list."""
    fg = FeedGenerator()
    fg.id(f"https://skillsllm.com/{feed_name}")
    fg.title("SkillsLLM")
    fg.subtitle(
        "AI tooling news and guides: SkillsLLM, Desktop Commander, Model Context "
        "Protocol, FastMCP, ClaudePluginHub, MCP Servers blog, Claude Skills Hub, "
        "OpenRouter, and LiteLLM (blog + releases)"
    )
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language("en")
    fg.author({"name": "SkillsLLM & the MCP / Claude Skills ecosystem"})
    setup_feed_extensions(fg)

    for entry in entries:
        fe = fg.add_entry()
        fe.id(entry["link"])
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
        add_entry_media(fe, entry.get("image"))

    logger.info("Generated Atom feed")
    return fg


def save_atom_feed(fg, feed_name=FEED_NAME):
    """Write the feed to feeds/feed_<n>.xml in Atom format."""
    output_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    fg.atom_file(str(output_file), pretty=True)
    logger.info(f"Saved Atom feed to {output_file}")
    return output_file


def main(full=False):
    """Discover articles, fetch new ones, merge with cache, write the feed."""
    if full:
        logger.info("Full reset requested — ignoring existing cache")
        cached = []
    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")

    known_links = {e["link"] for e in cached}
    sitemap_entries = collect_entries(known_links)
    native_entries = collect_native_feeds()
    mcpblog_entries = collect_mcpservers_blog(known_links)

    # Treat as a total outage (preserve the last good feed) only if every path
    # produced nothing: sitemaps all failed AND no native feed AND no scraped post.
    if (
        sitemap_entries is None
        and not native_entries
        and not mcpblog_entries
    ):
        logger.error("All sources failed — skipping write to preserve the last good feed")
        return False

    new_entries = (
        (sitemap_entries or [])
        + native_entries
        + mcpblog_entries
    )

    merged = merge_entries(new_entries, cached, id_field="link", date_field="date")
    if not merged:
        logger.warning("No entries — skipping write to avoid an empty feed")
        return False

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
    parser = argparse.ArgumentParser(description="Generate the SkillsLLM + MCP / Claude Skills ecosystem Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
