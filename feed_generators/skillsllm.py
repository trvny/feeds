"""SkillsLLM + MCP / Plugins ecosystem feed generator.

Combines AI-tooling sites into a single Atom feed (``feeds/feed_skillsllm.xml``)
using three discovery strategies, each source isolated so one failure never
sinks the run:

Native RSS/Atom feeds (feedparser):
  * Model Context Protocol  https://blog.modelcontextprotocol.io/index.xml
  * FastMCP (changelog)     https://gofastmcp.com/changelog/rss.xml
  * Agent Client Protocol   https://agentclientprotocol.com/updates/rss.xml
  * Pieces (updates + blog) https://pieces.app/updates/rss.xml, /blog/rss.xml
  * ClaudePluginHub         https://claudepluginhub.com/feed.xml
  * OpenRouter (blog)       https://openrouter.ai/blog/feed.xml
  * LiteLLM (blog)          https://docs.litellm.ai/blog/rss.xml
  * LiteLLM (release notes) https://github.com/BerriAI/litellm/releases.atom
                            (docs.litellm.ai/release_notes is a dateless HTML
                            mirror of these GitHub releases)
  * Glama (blog)            https://glama.ai/blog/rss.xml
  * Glama MCP Servers       https://glama.ai/mcp/servers/feeds/recent-servers.xml
                            (recently-registered MCP servers; high-churn, capped)
  * LobeHub (changelog)     https://lobehub.com/pl/changelog/feed
  * LobeHub (blog)          https://lobehub.com/pl/blog/feed
  * AI Skill Market         https://aiskill.market/rss.xml
  * Devin Desktop           https://docs.devin.ai/desktop/changelog/rss.xml
  * Hugging Face Blog       https://huggingface.co/blog/feed.xml
  * MindStudio              https://www.mindstudio.ai/rss.xml

Sitemap discovery + per-page detail fetch (no native feed; pages server-render
real ``<title>`` / ``<meta description>`` and sometimes ``article:published_time``):
  * SkillsLLM           https://skillsllm.com        (/news daily summaries + /blog guides)
  * Desktop Commander   https://desktopcommander.app (/blog posts)
  * Mem0 Blog           https://mem0.ai/blog         (/blog posts; Framer sitemap,
                        no <lastmod>, per-page article:published_time)
  * Mem0 Research       https://mem0.ai/research     (benchmark/research landing page)
  * Claude Skills Hub   https://claudeskills.info    (/blog posts via sitemap_blog.xml)

Index asset-slug discovery + detail fetch (no feed, no sitemap):
  * MCP Servers Blog    https://blog.mcpservers.org  (/posts/<slug>, slugs from
                        /assets/blog/<slug>/ paths on the index)

Dated listing / MDX scrape (no native feed):
  * Cognition             https://cognition.com/blog + /research
  * Devin Release Notes   https://docs.devin.ai/release-notes/overview

Bespoke HTML/MDX scrape (no feed, no sitemap):
  * Glama Release Notes https://glama.ai/release-notes (moved here from the
                        aibridge feed along with the rest of Glama's sources)
  * Mem0 Changelog      https://docs.mem0.ai/changelog/highlights (the raw .md
                        exposes <Update label="DATE"> milestone blocks)


Note: https://mcpservers.org itself is a server *directory* (thousands of
catalog pages, no news stream), so it is intentionally not aggregated here.
Sources evaluated and skipped: claudemarketplaces.com/digest has no feed and
is a near-static 3-issue archive page (not worth a bespoke scraper);
llmbase.ai/news/ sits behind a Cloudflare bot challenge (403 on every fetch
strategy tried) and can't be scraped at all; anysearch.com/blog has no feed,
no <link rel="alternate"> autodiscovery, and every common feed path
(/feed, /rss.xml, /atom.xml, /feed.xml, /blog/feed, /blog/rss.xml) 404s —
zero signal to build a scraper from.

Dates, per source:
  * SkillsLLM news      — from the ``/news/ai-news-YYYY-MM-DD`` slug
  * SkillsLLM blog      — from the sitemap ``<lastmod>``
  * Claude Skills Hub   — from the sitemap ``<lastmod>`` (or page ``published_time``)
  * Desktop Commander   — from the page's ``article:published_time`` meta
  * Native feeds        — from the feed entry's published/updated date
  * MCP Servers Blog    — no date exposed; stable per-link fallback

Entries merge into a local cache, dedup by ``link`` and then by normalized
URL/title, and are trimmed with a per-source quota.
"""

import argparse
import re
import sys
import time
from datetime import datetime

import feedparser
import pytz
from bs4 import BeautifulSoup
from cognition import (
    COGNITION_BLOG_URL,
    COGNITION_RESEARCH_URL,
    DEVIN_DESKTOP_RSS_URL,
    DEVIN_RELEASE_NOTES_URL,
    collect_cognition,
    collect_devin_release_notes,
)
from dateutil import parser as date_parser
from enrich import enrich_entries
from feedgen.feed import FeedGenerator
from multi_rss import apply_per_source_cap, get_html
from utils import (
    add_entry_media,
    dedupe_entries,
    deserialize_entries,
    feedparser_entry_image,
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
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "skillsllm"
BLOG_URL = "https://skillsllm.com/"
MEM0_SITEMAP_URL = "https://mem0.ai/sitemap.xml"

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
        "label": "Mem0 Blog",
        "sitemap": MEM0_SITEMAP_URL,
        "include": lambda loc: "/blog/" in loc
        and not loc.rstrip("/").endswith("/blog"),
        "slug_date_re": None,
        "use_lastmod": False,  # Framer sitemap carries no <lastmod>; page has article:published_time
        "title_suffixes": (" | Mem0", " - Mem0"),
        "category": lambda loc: "mem0-blog",
        "max_candidates": 40,
    },
    {
        "label": "Mem0 Research",
        "sitemap": MEM0_SITEMAP_URL,
        "include": lambda loc: loc.rstrip("/") == "https://mem0.ai/research",
        "slug_date_re": None,
        "use_lastmod": False,
        "title_suffixes": (" | Mem0", " - Mem0"),
        "category": lambda loc: "mem0-research",
        "max_candidates": 1,
    },
    {
        "label": "Claude Skills Hub",
        "sitemap": "https://claudeskills.info/sitemap_blog.xml",
        "include": lambda loc: "/blog/" in loc
        and not loc.rstrip("/").endswith("/blog"),
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
    ("Devin Desktop", DEVIN_DESKTOP_RSS_URL, "devin-desktop", 40),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "huggingface", 40),
    ("MindStudio", "https://www.mindstudio.ai/rss.xml", "mindstudio", 40),
    ("Model Context Protocol", "https://blog.modelcontextprotocol.io/index.xml", "mcp"),
    ("FastMCP", "https://gofastmcp.com/changelog/rss.xml", "fastmcp"),
    (
        "Agent Client Protocol",
        "https://agentclientprotocol.com/updates/rss.xml",
        "acp",
        30,
    ),
    ("Pieces Updates", "https://pieces.app/updates/rss.xml", "pieces-updates", 30),
    ("Pieces Blog", "https://pieces.app/blog/rss.xml", "pieces-blog", 30),
    # ClaudePluginHub is a high-churn directory feed (300+ entries, all stamped
    # at the crawl time), so it floods the MAX_ENTRIES budget and evicts every
    # editorial source. Cap it hard, like Glama MCP Servers.
    ("ClaudePluginHub", "https://claudepluginhub.com/feed.xml", "plugins", 30),
    # LLM gateways / routers. OpenRouter's blog feed is large, so cap it; the
    # LiteLLM docs release_notes pages are a dateless HTML mirror of the GitHub
    # releases, so the dated releases.atom is used for those instead. Optional
    # 4th tuple element caps how many of the newest entries are taken.
    ("OpenRouter", "https://openrouter.ai/blog/feed.xml", "openrouter", 30),
    ("LiteLLM Blog", "https://docs.litellm.ai/blog/rss.xml", "litellm", 20),
    (
        "LiteLLM Releases",
        "https://github.com/BerriAI/litellm/releases.atom",
        "litellm-releases",
        15,
    ),
    # Glama sources (moved here from the aibridge feed, where they flooded
    # the AI-labs stream). MCP Servers is a high-churn directory feed: capped
    # low per run, but it still accumulates across runs, so keep an eye on it
    # crowding the editorial sources here too.
    ("Glama Blog", "https://glama.ai/blog/rss.xml", "glama-blog", 40),
    (
        "Glama MCP Servers",
        "https://glama.ai/mcp/servers/feeds/recent-servers.xml",
        "glama-mcp",
        20,
    ),
    # LobeHub's changelog/blog feeds (URL is the /pl/ locale variant that was
    # requested; content isn't Polish-exclusive).
    (
        "LobeHub Changelog",
        "https://lobehub.com/pl/changelog/feed",
        "lobehub-changelog",
        30,
    ),
    ("LobeHub Blog", "https://lobehub.com/pl/blog/feed", "lobehub-blog", 30),
    ("AI Skill Market", "https://aiskill.market/rss.xml", "aiskill-market", 40),
]


def doc_sources():
    """Sources built outside the regular source declarations."""
    return [
        ("Cognition Blog", COGNITION_BLOG_URL),
        ("Cognition Research", COGNITION_RESEARCH_URL),
        ("Devin Release Notes", DEVIN_RELEASE_NOTES_URL),
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
# Directory feeds (ClaudePluginHub, Glama MCP Servers, AI Skill Market) publish
# hundreds of machine-generated listings at a time and had grown to fill the
# entire cache, evicting every editorial source. Each source gets a quota; the
# directories get a much smaller one than the editorial feeds, since a listing
# is worth far less to a reader than a post. The "" key is the default.
PER_SOURCE_CAP = {
    "": 30,
    "ClaudePluginHub": 10,
    "Glama MCP Servers": 10,
    "AI Skill Market": 10,
}


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
    treating it as "zero articles").
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

    found.sort(
        key=lambda t: (t[1] or datetime.min.replace(tzinfo=pytz.UTC)), reverse=True
    )
    logger.info(f"[{source['label']}] discovered {len(found)} article URLs in sitemap")
    return found[: source["max_candidates"]]


def _clean_title(raw, suffixes):
    title = sanitize_xml(raw.strip())
    for suffix in suffixes:
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
            break
    return title


# A discovered URL that fails to fetch, or yields no <title>, caches nothing —
# so the next run rediscovers it from the same sitemap and pays for the same
# three retries again, every two hours, indefinitely. Bounded per run by
# max_candidates, unbounded across runs. Same defect class as the google_news
# resolver, and fixed the same way: count the attempts, give up at the cap.
MAX_FETCH_ATTEMPTS = 3


class AttemptLedger:
    """Counts failed detail fetches per URL and gives up at MAX_FETCH_ATTEMPTS.

    Forgetting is what keeps the ledger from growing without bound: a URL that
    drops out of its source's listing drops out of the ledger. But it may only
    be forgotten on the strength of a listing that actually happened — a
    sitemap that was merely unreachable this run says nothing about its URLs,
    and dropping them there would reset dead links to zero on every outage,
    defeating the cap entirely.

    So the counts are filed under the source label, not the URL's host: two
    SOURCES entries can share a hostname (Mem0 Blog and Mem0 Research both read
    mem0.ai) while being fetched, and failing, independently. Only the sources
    :meth:`listed` saw this run are rebuilt; the rest are carried over as they
    were. A URL that succeeds is simply never re-added.
    """

    def __init__(self, previous=None):
        outer = previous if isinstance(previous, dict) else {}
        self._previous = {}
        for source, counts in outer.items():
            if not isinstance(counts, dict):
                continue
            clean = {
                link: count
                for link, count in counts.items()
                # bool is a subclass of int, and `true` is not an attempt count.
                if isinstance(count, int) and not isinstance(count, bool)
            }
            if clean:
                self._previous[source] = clean
        self._attempts = {}
        self.skipped = 0

    def listed(self, source):
        """Record that *source* produced a listing, so its counts may be pruned."""
        self._attempts.setdefault(source, {})

    def exhausted(self, source, link):
        """True if *link* has already failed its budget. Keeps remembering it."""
        count = self._previous.get(source, {}).get(link, 0)
        if count >= MAX_FETCH_ATTEMPTS:
            self._attempts.setdefault(source, {})[link] = count
            self.skipped += 1
            return True
        return False

    def failed(self, source, link):
        previous = self._previous.get(source, {}).get(link, 0)
        self._attempts.setdefault(source, {})[link] = previous + 1

    @property
    def current(self):
        """What to store: rebuilt sources, plus every source we could not list."""
        merged = {
            source: dict(counts)
            for source, counts in self._previous.items()
            if source not in self._attempts
        }
        for source, counts in self._attempts.items():
            if counts:
                merged[source] = counts
        return merged


def fetch_detail(link, sitemap_date, source):
    """Fetch one article page and return a normalized entry dict, or None."""
    html = fetch_url(link)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find("title")
    title = (
        _clean_title(title_el.get_text(), source["title_suffixes"])
        if title_el
        else None
    )
    if not title:
        return None

    desc_el = soup.find("meta", attrs={"name": "description"})
    description = (
        sanitize_xml(desc_el["content"].strip())
        if desc_el and desc_el.get("content")
        else title
    )

    img_el = soup.find("meta", attrs={"property": "og:image"}) or soup.find(
        "meta", attrs={"name": "twitter:image"}
    )
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


def collect_entries(known_links, ledger):
    """Discover and fetch new articles from every source.

    *known_links* is the set of links already in the cache; those are skipped
    (their cached entry is reused by the merge step). *ledger* is the
    :class:`AttemptLedger` that stops a permanently unfetchable URL from being
    retried on every run. Returns None only if every source's sitemap failed,
    so a total outage preserves the last good feed while a single dead source
    doesn't.
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
        ledger.listed(source["label"])
        for link, sitemap_date in discovered:
            if link in known_links or ledger.exhausted(source["label"], link):
                continue
            try:
                entry = fetch_detail(link, sitemap_date, source)
                if entry:
                    entries.append(entry)
                    fetched += 1
                else:
                    ledger.failed(source["label"], link)
                    logger.warning(
                        f"[{source['label']}] no usable title for {link}; skipping"
                    )
            except Exception as e:  # never let one bad page kill the run
                ledger.failed(source["label"], link)
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
                        "image": feedparser_entry_image(e),
                    }
                )
                count += 1
            except Exception as exc:  # one bad item never kills the feed
                logger.warning(f"[{label}] skipping an entry: {exc}")
        logger.info(f"[{label}] parsed {count} entries")
    return entries


# Glama's /release-notes page has no feed: each item is an <article> with an
# <h2> title, an Improvement/Feature/Fix/Announcement badge, a "Mon D, YYYY"
# date, and a body. Items have no per-entry permalink, so a stable
# "#<date>-<title-slug>" fragment is synthesised as the dedup id. Moved here
# from the aibridge feed along with the rest of Glama's sources.
GLAMA_RELEASE_NOTES_URL = "https://glama.ai/release-notes"
_GLAMA_RN_DATE_RE = re.compile(r"\b([A-Z][a-z]{2,9} \d{1,2}, \d{4})\b")
_GLAMA_RN_TYPE_RE = re.compile(r"^(Improvement|Feature|Fix|Announcement)\b")


def _glama_slugify(text, max_len=80):
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", text)[:max_len] or "item"


def collect_glama_release_notes(known_links):
    html = get_html(GLAMA_RELEASE_NOTES_URL)
    if not html:
        logger.warning("[Glama Release Notes] fetch failed; continuing")
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen, entries = set(), []
    for art in soup.find_all("article"):
        try:
            heading = art.find(["h1", "h2", "h3"])
            if not heading:
                continue
            title = sanitize_xml(heading.get_text(" ", strip=True))
            if not title:
                continue
            full = art.get_text(" ", strip=True)
            date_match = _GLAMA_RN_DATE_RE.search(full)
            date = parse_date(date_match.group(1)) if date_match else None
            tail = full[len(title) :].strip()
            type_match = _GLAMA_RN_TYPE_RE.search(tail)
            rtype = type_match.group(1) if type_match else None
            body = full[date_match.end() :].strip(" .|") if date_match else ""
            description = (f"[{rtype}] " if rtype else "") + (
                body[:300] if body else title
            )
            date_slug = date.strftime("%Y-%m-%d") if date else "nodate"
            link = f"{GLAMA_RELEASE_NOTES_URL}#{date_slug}-{_glama_slugify(title)}"
            if link in seen or link in known_links:
                continue
            seen.add(link)
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date or stable_fallback_date(link),
                    "description": sanitize_xml(description),
                    "source": "Glama Release Notes",
                    "category": "glama-release-notes",
                }
            )
        except Exception:  # one bad item never kills the feed
            continue
    logger.info(
        f"[Glama Release Notes] fetched {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
    )
    return entries


def collect_mcpservers_blog(known_links, ledger):
    """Discover blog.mcpservers.org posts from index asset paths, fetch titles."""
    index_html = fetch_url(MCPSERVERS_BLOG_BASE + "/")
    if index_html is None:
        logger.warning("[MCP Servers Blog] index unavailable; continuing")
        return []
    slugs = sorted(set(_MCPSERVERS_SLUG_RE.findall(index_html)))
    if not slugs:
        logger.warning("[MCP Servers Blog] no post slugs found on index; continuing")
        return []

    mcp_label = MCPSERVERS_BLOG_SOURCE["label"]
    ledger.listed(mcp_label)
    entries = []
    for slug in slugs:
        link = f"{MCPSERVERS_BLOG_BASE}/posts/{slug}"
        if link in known_links or ledger.exhausted(mcp_label, link):
            continue
        try:
            entry = fetch_detail(link, None, MCPSERVERS_BLOG_SOURCE)
            if entry:
                entries.append(entry)
            else:
                ledger.failed(mcp_label, link)
                logger.warning(
                    f"[MCP Servers Blog] no usable title for {link}; skipping"
                )
        except Exception as exc:
            ledger.failed(mcp_label, link)
            logger.warning(f"[MCP Servers Blog] skipping {link}: {exc}")
    logger.info(f"[MCP Servers Blog] fetched details for {len(entries)} new post(s)")
    return entries


# docs.mem0.ai/changelog/highlights is a Mintlify page with no feed, but the
# raw ``.md`` exposes the source MDX: each milestone is an <Update label="DATE"
# description="..."> block whose body opens with a **bold headline**. The label
# is the publish date; a stable "#<date>" fragment on the highlights URL is the
# dedup id since the blocks carry no permalink.
MEM0_CHANGELOG_URL = "https://docs.mem0.ai/changelog/highlights"
MEM0_CHANGELOG_MD = "https://docs.mem0.ai/changelog/highlights.md"
_MEM0_UPDATE_RE = re.compile(
    r'<Update\s+label="([^"]+)"(?:\s+description="([^"]*)")?\s*>(.*?)</Update>',
    re.S,
)
_MEM0_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)


def collect_mem0_changelog(known_links):
    """Parse the mem0 highlights .md into one entry per <Update> block."""
    md = fetch_url(MEM0_CHANGELOG_MD)
    if md is None:
        logger.warning("[Mem0 Changelog] fetch failed; continuing")
        return []
    entries = []
    for label, description, body in _MEM0_UPDATE_RE.findall(md):
        try:
            date = parse_date(label)
            bold = _MEM0_BOLD_RE.search(body)
            headline = bold.group(1).strip() if bold else (description or label)
            title = sanitize_xml(" ".join(headline.split()))
            if not title:
                continue
            date_slug = date.strftime("%Y-%m-%d") if date else label
            link = f"{MEM0_CHANGELOG_URL}#{date_slug}"
            if link in known_links:
                continue
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date or stable_fallback_date(link),
                    "description": sanitize_xml(description.strip()) or title,
                    "source": "Mem0 Changelog",
                    "category": "mem0-changelog",
                }
            )
        except Exception:  # one bad block never kills the feed
            continue
    logger.info(
        f"[Mem0 Changelog] fetched {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}"
    )
    return entries


def generate_atom_feed(entries, feed_name=FEED_NAME):
    """Build an Atom FeedGenerator from the normalized entry list."""
    fg = FeedGenerator()
    fg.id(f"https://skillsllm.com/{feed_name}")
    fg.title("SkillsLLM")
    fg.subtitle(
        "AI tooling news and guides: SkillsLLM, Desktop Commander, Model Context "
        "Protocol, FastMCP, Agent Client Protocol, Pieces, ClaudePluginHub, MCP "
        "Servers blog, Claude Skills Hub, Hugging Face, MindStudio, OpenRouter, "
        "LiteLLM (blog + releases), Glama (blog, MCP servers, release notes), "
        "LobeHub (changelog + blog), AI Skill Market, Mem0 (blog + research + changelog), "
        "Cognition (research + blog), and Devin (Desktop changelog + release notes)"
    )
    setup_feed_links(fg, BLOG_URL, feed_name)
    fg.language("en")
    fg.author({"name": "SkillsLLM & MCP / Plugins ecosystem"})
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
        ledger = AttemptLedger()
    else:
        cache = load_cache(FEED_NAME)
        cached = deserialize_entries(cache.get("entries", []), date_field="date")
        ledger = AttemptLedger(cache.get("unresolvable"))

    known_links = {e["link"] for e in cached}
    sitemap_entries = collect_entries(known_links, ledger)
    native_entries = collect_native_feeds()
    mcpblog_entries = collect_mcpservers_blog(known_links, ledger)
    glama_rn_entries = collect_glama_release_notes(known_links)
    mem0_changelog_entries = collect_mem0_changelog(known_links)
    cognition_entries = collect_cognition(known_links)
    devin_release_entries = collect_devin_release_notes(known_links)

    # Treat as a total outage (preserve the last good feed) only if every path
    # produced nothing: sitemaps all failed AND no native feed AND no scraped post.
    if (
        sitemap_entries is None
        and not native_entries
        and not mcpblog_entries
        and not glama_rn_entries
        and not mem0_changelog_entries
        and not cognition_entries
        and not devin_release_entries
    ):
        logger.error(
            "All sources failed — skipping write to preserve the last good feed"
        )
        return False

    new_entries = (
        (sitemap_entries or [])
        + native_entries
        + mcpblog_entries
        + glama_rn_entries
        + mem0_changelog_entries
        + cognition_entries
        + devin_release_entries
    )

    merged = merge_entries(new_entries, cached, id_field="link", date_field="date")
    # The directories republish the same project under different URLs and the
    # blogs occasionally reissue a post, so collapse by normalized URL/title
    # rather than trusting the exact link merge_entries keys on.
    merged = dedupe_entries(merged)
    if not merged:
        logger.warning("No entries — skipping write to avoid an empty feed")
        return False

    merged = sort_posts_for_feed(merged, date_field="date")

    # Trim to MAX_ENTRIES with a per-source floor rather than a plain newest-N
    # slice: the directory feeds publish in bursts and a plain slice let them
    # fill the whole cache, evicting every editorial source.
    if len(merged) > MAX_ENTRIES:
        merged = apply_per_source_cap(merged, PER_SOURCE_CAP, MAX_ENTRIES)

    enrich_entries(merged)

    if ledger.skipped:
        logger.info(
            f"Skipped {ledger.skipped} URL(s) that failed "
            f"{MAX_FETCH_ATTEMPTS} times already"
        )
    save_cache(FEED_NAME, merged, extra={"unresolvable": ledger.current})

    fg = generate_atom_feed(merged)
    save_atom_feed(fg)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the SkillsLLM + MCP / Claude Skills ecosystem Atom feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
