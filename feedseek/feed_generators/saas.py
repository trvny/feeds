"""Combined Atom feed for assorted SaaS / web-product vendors.

Merges three low-volume vendor feeds that previously lived on their own into a
single Atom stream written to ``feeds/feed_saas.xml``:

    - HashiCorp / HCP   blog (native Atom) + HCP changelog (scraped)
    - Bitly             blog + press room + MCP changelog
    - Common Ninja      blog
    - Svelte            blog (native RSS)
    - Vercel            blog (native Atom) + changelog (native RSS)
                        + Chat SDK / Flags SDK / Workflow SDK / AI Elements
                        docs feeds (native RSS)
    - Apify             blog (native RSS)
    - Zapier            blog (native RSS)
    - Exa               changelog (native RSS) + blog (sitemap + per-post fetch)
    - Home Assistant    blog (native Atom)
    - Xweather          blog (scraped index) + weather-api changelog (scraped)
                        + mcp-server changelog (scraped)

Note: exa.ai/research is a client-rendered listing with no sitemap entries and
no server-rendered post list, so it isn't aggregated here (would need a
browser to enumerate posts).

Each source's parser is reused verbatim from its original module
(``hcp_combined``, ``bitly``, ``commoninja_blog``), so there is exactly one
place that knows how to scrape each site. This generator only normalizes the
entries to a common shape, tags every entry with a per-vendor ``<category>``,
and keeps one rolling JSON cache (``cache/saas_posts.json``) so history
survives even when a source truncates its listing.

HCP entries carry rich HTML bodies (``content_html``) which are emitted as
``<content type="html">``; the other sources only have plain summaries.

Usage:
    python saas.py          # incremental: merge new entries into cache
    python saas.py --full   # ignore cache, rebuild from sources only
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

import bitly
import commoninja_blog as commoninja
import hcp_combined as hcp
import multi_rss
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
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "saas"
FEED_TITLE = "SaaS vendors"
FEED_SUBTITLE = (
    "Combined updates from HashiCorp / HCP (blog + changelog), "
    "Bitly (blog + press + MCP changelog), Common Ninja, "
    "Svelte, Vercel (blog + changelog + SDK docs), Apify, Zapier, Postman (blog + press), "
    "Exa (blog + changelog), Home Assistant, "
    "and Xweather (blog + API + MCP changelogs)."
)
BLOG_URL = "https://www.hashicorp.com/blog"
MAX_ENTRIES = 300  # all vendors share one archive

_TAG_PREFIX_RE = re.compile(r"^\[[^\]]+\]\s*")


def _text(html: str) -> str:
    """Plain-text rendering of an HTML fragment, collapsed and trimmed."""
    if not html:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" ", strip=True)).strip()


# --------------------------------------------------------------------------- #
# Per-vendor adapters: reuse the original scrapers, normalize to one shape
#   {id, title, link, date, description, content_html?, source}
# --------------------------------------------------------------------------- #
def collect_hcp() -> list[dict]:
    """HashiCorp blog (native Atom) + HCP changelog (scraped). Both already
    return rich HTML in ``summary``; relabel the source and drop the redundant
    ``[Blog]`` / ``[Changelog]`` title prefix (we tag via <category>)."""
    out: list[dict] = []
    label = {"Blog": "HashiCorp Blog", "Changelog": "HCP Changelog"}
    try:
        raw = hcp.fetch_blog() + hcp.fetch_changelog()
    except Exception as exc:
        logger.warning("HCP sources failed: %s", exc)
        return out
    for e in raw:
        body = e.get("summary") or ""
        out.append({
            "id": e["id"],
            "title": sanitize_xml(_TAG_PREFIX_RE.sub("", e["title"])),
            "link": e["link"],
            "date": e.get("date"),
            "description": sanitize_xml(_text(body))[:500] or sanitize_xml(_TAG_PREFIX_RE.sub("", e["title"])),
            "content_html": body or None,
            "source": label.get(e.get("source"), e.get("source") or "HashiCorp"),
        })
    logger.info("HCP: %d entries", len(out))
    return out


def collect_bitly(known_links: set[str]) -> list[dict]:
    """Bitly blog + press + MCP changelog via bitly.scrape_all (already in the
    common {title, link, date, description, source} shape)."""
    out: list[dict] = []
    try:
        for e in bitly.scrape_all(known_links):
            out.append({
                "id": e["link"],
                "title": e["title"],
                "link": e["link"],
                "date": e.get("date"),
                "description": e.get("description") or e["title"],
                "content_html": None,
                "source": e.get("source") or "Bitly",
            })
    except Exception as exc:
        logger.warning("Bitly sources failed: %s", exc)
    logger.info("Bitly: %d entries", len(out))
    return out


# --------------------------------------------------------------------------- #
# Native RSS/Atom vendor feeds — parsed via the shared multi_rss helper.
# (label, url, cap): cap trims high-volume archives to the most recent items.
# --------------------------------------------------------------------------- #
NATIVE_FEEDS = [
    ("Svelte", "https://svelte.dev/blog/rss.xml", 40),
    ("Vercel", "https://vercel.com/atom", 40),
    ("Vercel Changelog", "https://vercel.com/changelog/rss.xml", 40),
    ("Chat SDK", "https://chat-sdk.dev/rss.xml", 40),
    ("Flags SDK", "https://flags-sdk.dev/rss.xml", 40),
    ("Workflow SDK", "https://workflow-sdk.dev/rss.xml", 40),
    ("AI Elements", "https://elements.ai-sdk.dev/rss.xml", 40),
    ("Apify", "https://blog.apify.com/rss/", None),
    ("Zapier", "https://zapier.com/blog/feeds/latest/", None),
    ("Postman", "https://blog.postman.com/feed/", 40),
    ("Exa Changelog", "https://exa.ai/docs/changelog/rss.xml", 40),
    ("Home Assistant", "https://www.home-assistant.io/atom.xml", 40),
]


def collect_native_feeds(known_links: set[str]) -> list[dict]:
    """Pull each native RSS/Atom vendor feed via multi_rss.scrape_feed and
    normalize to the saas entry shape. Per-source failures are isolated."""
    out: list[dict] = []
    for label, url, cap in NATIVE_FEEDS:
        try:
            for e in multi_rss.scrape_feed(label, url, known_links, cap=cap):
                out.append({
                    "id": e["link"],
                    "title": e["title"],
                    "link": e["link"],
                    "date": e.get("date"),
                    "description": e.get("description") or e["title"],
                    "content_html": None,
                    "source": label,
                })
        except Exception as exc:
            logger.warning("%s feed failed: %s", label, exc)
    logger.info("Native feeds: %d entries", len(out))
    return out


import datetime as _dt  # noqa: E402

# Postman press page: no feed. Each release is an <h3> title linking to a
# BusinessWire URL whose /home/<YYYYMMDD...> segment carries the date.
POSTMAN_PRESS_URL = "https://www.postman.com/company/press-media/"

_BW_DATE_RE = re.compile(r"/home/(20\d{2})(\d{2})(\d{2})")


def collect_postman_press(known_links: set[str]) -> list[dict]:
    out: list[dict] = []
    try:
        html = multi_rss.get_html(POSTMAN_PRESS_URL)
    except Exception as exc:
        logger.warning("Postman press fetch failed: %s", exc)
        return out
    if not html:
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    for h3 in soup.find_all("h3"):
        title = h3.get_text(" ", strip=True)
        if not title:
            continue
        a = h3.find("a", href=True) or h3.find_parent("a", href=True) or h3.find_next("a", href=True)
        if not a:
            continue
        link = a["href"].split("?")[0]
        if link in seen or link in known_links:
            continue
        m = _BW_DATE_RE.search(link)
        date = None
        if m:
            try:
                date = _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_dt.timezone.utc)
            except ValueError:
                date = None
        seen.add(link)
        out.append({
            "id": link,
            "title": sanitize_xml(title[:200]),
            "link": link,
            "date": date,
            "description": sanitize_xml(title[:200]),
            "content_html": None,
            "source": "Postman Press",
        })
    logger.info("Postman Press: %d entries", len(out))
    return out


def collect_commoninja() -> list[dict]:
    """Common Ninja blog: fetch the listing and reuse its card parser."""
    out: list[dict] = []
    try:
        html = commoninja.fetch_listing()
        if html:
            for e in commoninja.parse_items(html):
                out.append({
                    "id": e["link"],
                    "title": e["title"],
                    "link": e["link"],
                    "date": e.get("date") or stable_fallback_date(e["link"]),
                    "description": e.get("description") or e["title"],
                    "content_html": None,
                    "source": "Common Ninja",
                })
    except Exception as exc:
        logger.warning("Common Ninja source failed: %s", exc)
    logger.info("Common Ninja: %d entries", len(out))
    return out


# --------------------------------------------------------------------------- #
# Exa: changelog is native RSS (see NATIVE_FEEDS); the blog has no feed and
# its listing page is client-rendered, but the sitemap stamps every
# /blog/<slug> with a real <lastmod> and each post page is server-rendered
# with a proper <title>/<meta description> — same discover+fetch shape as
# skillsllm.py's sitemap sources.
# --------------------------------------------------------------------------- #
EXA_SITEMAP_URL = "https://exa.ai/sitemap.xml"
EXA_BLOG_MAX = 30
_EXA_TITLE_SUFFIX_RE = re.compile(r"\s*\|\s*Exa Blog\s*$")


def collect_exa_blog(known_links: set[str]) -> list[dict]:
    out: list[dict] = []
    try:
        xml = multi_rss.get_html(EXA_SITEMAP_URL)
    except Exception as exc:
        logger.warning("Exa sitemap fetch failed: %s", exc)
        return out
    if not xml:
        logger.warning("Exa sitemap unavailable; continuing")
        return out
    soup = BeautifulSoup(xml, "xml")
    candidates = []
    for url_el in soup.find_all("url"):
        loc_el = url_el.find("loc")
        if not loc_el:
            continue
        loc = loc_el.get_text(strip=True)
        if "/blog/" not in loc or loc.rstrip("/").endswith("/blog"):
            continue
        lastmod_el = url_el.find("lastmod")
        date = multi_rss.parse_date(lastmod_el.get_text(strip=True)) if lastmod_el else None
        candidates.append((loc, date))
    candidates.sort(key=lambda t: (t[1] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

    for link, date in candidates[:EXA_BLOG_MAX]:
        if link in known_links:
            continue
        try:
            html = multi_rss.get_html(link)
            if not html:
                continue
            page = BeautifulSoup(html, "html.parser")
            title_el = page.find("title")
            title = sanitize_xml(title_el.get_text(strip=True)) if title_el else ""
            title = _EXA_TITLE_SUFFIX_RE.sub("", title).strip()
            if not title:
                logger.warning("Exa Blog: no usable title for %s; skipping", link)
                continue
            desc_el = page.find("meta", attrs={"name": "description"})
            description = sanitize_xml(desc_el["content"].strip()) if desc_el and desc_el.get("content") else title
            out.append({
                "id": link,
                "title": title,
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": description or title,
                "content_html": None,
                "source": "Exa Blog",
            })
        except Exception as exc:
            logger.warning("Exa Blog: skipping %s: %s", link, exc)
    logger.info("Exa Blog: %d entries", len(out))
    return out


# --------------------------------------------------------------------------- #
# Xweather blog: no feed, but the index is server-rendered — every post is an
# <article> with a cover-link, an h2/h3 title, and either a <time datetime>
# (list cards) or a plain date span (the hero card). Scraped directly, no
# per-post fetch needed.
# --------------------------------------------------------------------------- #
XWEATHER_BLOG_URL = "https://www.xweather.com/blog"
_XWEATHER_DATE_RE = re.compile(r"[A-Z][a-z]{2,8} \d{1,2}, 20\d{2}")


def collect_xweather_blog() -> list[dict]:
    out: list[dict] = []
    try:
        html = multi_rss.get_html(XWEATHER_BLOG_URL)
    except Exception as exc:
        logger.warning("Xweather Blog fetch failed: %s", exc)
        return out
    if not html:
        logger.warning("Xweather Blog unavailable; continuing")
        return out
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    for art in soup.find_all("article"):
        a = art.find("a", class_="cover-link", href=True)
        if not a:
            continue
        heading = a.find(["h2", "h3"])
        if not heading:
            continue
        title = sanitize_xml(heading.get_text(" ", strip=True))
        if not title:
            continue
        href = a["href"]
        link = href if href.startswith("http") else "https://www.xweather.com" + href
        if link in seen:
            continue
        seen.add(link)

        date = None
        time_el = art.find("time")
        if time_el and time_el.get("datetime"):
            date = multi_rss.parse_date(time_el["datetime"])
        if date is None:
            date_el = art.find("span", string=_XWEATHER_DATE_RE)
            if date_el:
                date = multi_rss.parse_date(date_el.get_text(strip=True))

        desc_el = art.find("div", class_=re.compile("simpleRichText"))
        description = _text(str(desc_el)) if desc_el else title

        out.append({
            "id": link,
            "title": title,
            "link": link,
            "date": date or stable_fallback_date(link),
            "description": sanitize_xml(description)[:500] or title,
            "content_html": None,
            "source": "Xweather Blog",
        })
    logger.info("Xweather Blog: %d entries", len(out))
    return out


# --------------------------------------------------------------------------- #
# Xweather docs changelogs (weather-api, mcp-server): Nextra-style single
# page, ``<h2 id="..">version</h2>`` followed by a sibling ``<p>`` date
# (sometimes wrapped in ``<em>``, sometimes not) and a sibling ``<ul>`` of
# bullet points, newest first. No per-entry permalink, so the h2's own id
# becomes a stable ``#fragment``.
# --------------------------------------------------------------------------- #
XWEATHER_CHANGELOGS = [
    ("Xweather Weather API Changelog", "https://www.xweather.com/docs/weather-api/changelog"),
    ("Xweather MCP Server Changelog", "https://www.xweather.com/docs/mcp-server/changelog"),
]
CHANGELOG_MAX_ENTRIES = 30


def _parse_docs_changelog(html: str, base_url: str, label: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for h2 in soup.find_all("h2", id=True):
        version = h2.get_text(strip=True)
        if not version:
            continue
        date = None
        p = h2.find_next_sibling("p")
        if p:
            em = p.find("em")
            date_text = em.get_text(strip=True) if em else p.get_text(strip=True)
            date = multi_rss.parse_date(date_text)
        bullets = []
        ul = h2.find_next_sibling("ul")
        if ul:
            bullets = [li.get_text(" ", strip=True) for li in ul.find_all("li")]
        description = "; ".join(bullets)[:500] or version
        link = f"{base_url}#{h2['id']}"
        out.append({
            "id": link,
            "title": sanitize_xml(f"{label} {version}"),
            "link": link,
            "date": date or stable_fallback_date(link),
            "description": sanitize_xml(description),
            "content_html": None,
            "source": label,
        })
    out.sort(key=lambda e: e["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return out[:CHANGELOG_MAX_ENTRIES]


def collect_xweather_changelogs() -> list[dict]:
    out: list[dict] = []
    for label, url in XWEATHER_CHANGELOGS:
        try:
            html = multi_rss.get_html(url)
            if not html:
                logger.warning("%s fetch failed", label)
                continue
            out += _parse_docs_changelog(html, url, label)
        except Exception as exc:
            logger.warning("%s failed: %s", label, exc)
    logger.info("Xweather changelogs: %d entries", len(out))
    return out


# --------------------------------------------------------------------------- #
# Feed
# --------------------------------------------------------------------------- #
def generate_atom_feed(entries: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.id(f"{BLOG_URL}#{FEED_NAME}")
    fg.title(FEED_TITLE)
    fg.subtitle(FEED_SUBTITLE)
    setup_feed_links(fg, BLOG_URL, FEED_NAME)
    fg.language("en")
    fg.author({"name": "various"})
    fg.updated(datetime.now(timezone.utc))
    fg.generator("trvny-feeds saas.py")

    # entries are ascending (oldest first); feedgen reverses on write.
    for e in entries:
        fe = fg.add_entry()
        fe.id(e["id"])
        fe.title(e["title"])
        fe.link(href=e["link"], rel="alternate")
        if e.get("content_html"):
            fe.content(e["content_html"], type="html")
        else:
            fe.description(e.get("description") or e["title"])
        if e.get("source"):
            fe.category(term=e["source"], label=e["source"])
        if e.get("date"):
            fe.published(e["date"])
            fe.updated(e["date"])
    logger.info("Generated Atom feed with %d entries", len(entries))
    return fg


def main(full: bool = False) -> bool:
    cached = (
        []
        if full
        else deserialize_entries(load_cache(FEED_NAME).get("entries", []), date_field="date")
    )
    known_links = {e.get("link") for e in cached}

    new_entries = (
        collect_hcp()
        + collect_bitly(known_links)
        + collect_commoninja()
        + collect_native_feeds(known_links)
        + collect_postman_press(known_links)
        + collect_exa_blog(known_links)
        + collect_xweather_blog()
        + collect_xweather_changelogs()
    )
    if not new_entries and not cached:
        logger.error("No entries from any source; preserving the last good feed")
        return False

    merged = merge_entries(new_entries, cached, id_field="id", date_field="date")
    merged = sort_posts_for_feed(merged, date_field="date")
    if len(merged) > MAX_ENTRIES:
        merged = merged[-MAX_ENTRIES:]  # ascending, so the tail is newest

    save_cache(FEED_NAME, merged)
    out = get_feeds_dir() / f"feed_{FEED_NAME}.xml"
    generate_atom_feed(merged).atom_file(str(out), pretty=True)
    logger.info("Wrote %s", out)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined SaaS-vendors Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
