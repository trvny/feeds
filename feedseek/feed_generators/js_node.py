"""JS | Node feed: combined Atom from the JS/Node.js runtime & tooling
ecosystem — native RSS/Atom feeds plus two bespoke scrapers for sites with
no feed at all.

Native feeds (multi_rss SOURCES): Node.js blog, pnpm blog, jsDelivr blog,
Bun, Deno, NodeSource blog, Total.js blog, Vite blog, Next.js blog, the Vue
Point (Vue.js blog), Svelte blog. Two status feeds get their own low cap
(they're incident logs, not editorial content): npm status and jsDelivr
status.

Bespoke scrapers (extra_scrapers, no feed on either site):
  * npmx.dev/blog     — small Next.js blog, release notes for the npmx
                        browser. Cards on the listing page carry a
                        <time datetime>, an <h2> title, and a <p> summary —
                        parsed directly, no per-page detail fetch needed.
  * openjsf.org/blog  — OpenJS Foundation blog (Next.js, no feed either).
                        Same shape: <time datetime>, <h3> title, a summary
                        div. First listing page (~30 posts) is enough given
                        the 2h cron cadence.

vite.dev/blog, nextjs.org/blog, and svelte.dev/blog all *do* expose a feed
via <link rel="alternate"> autodiscovery (not at an obvious /rss.xml guess),
so they're native sources, not scrapers.
"""

import argparse
import sys

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "js_node"

# (label, url, cap)
SOURCES = [
    ("Node.js Blog", "https://nodejs.org/en/feed/blog.xml", 40),
    ("pnpm Blog", "https://pnpm.io/blog/atom.xml", 40),
    ("jsDelivr Blog", "https://www.jsdelivr.com/blog/rss", 40),
    ("Bun", "https://bun.com/rss.xml", 40),
    ("Deno", "https://deno.com/feed", 40),
    ("NodeSource Blog", "https://nodesource.com/blog/rss", 40),
    ("Total.js Blog", "https://blog.totaljs.com/rss", 40),
    ("Vite Blog", "https://vite.dev/blog.rss", 40),
    ("Next.js Blog", "https://nextjs.org/feed.xml", 40),
    ("Vue Point", "https://blog.vuejs.org/feed.rss", 40),
    ("Svelte Blog", "https://svelte.dev/blog/rss.xml", 40),
    # Status/incident feeds — low churn but noisy relative to editorial
    # content, so capped hard.
    ("npm Status", "https://status.npmjs.org/history.atom", 10),
    ("jsDelivr Status", "https://status.jsdelivr.com/statuspage/jsdelivr/subscribe/rss", 8),
]

NPMX_BLOG_URL = "https://npmx.dev/blog"
NPMX_BASE = "https://npmx.dev"

OPENJSF_BLOG_URL = "https://openjsf.org/blog"
OPENJSF_BASE = "https://openjsf.org"


def scrape_npmx(known_links):
    label = "npmx"
    entries = []
    html = get_html(NPMX_BLOG_URL)
    if html is None:
        logger.warning(f"  [{label}] fetch failed; continuing")
        return entries
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.select('a[href^="/blog/"]'):
        href = a.get("href", "")
        if "_payload" in href:
            continue
        try:
            link = NPMX_BASE + href
            if link in known_links:
                continue
            title_el = a.find("h2")
            if not title_el:
                continue
            title = sanitize_xml(title_el.get_text(" ", strip=True))
            if not title:
                continue
            desc_el = a.find("p")
            description = sanitize_xml(desc_el.get_text(" ", strip=True)) if desc_el else title
            time_el = a.find("time")
            date_obj = parse_date(time_el.get("datetime")) if time_el and time_el.get("datetime") else None
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": description,
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:  # one bad card never kills the run
            logger.warning(f"  [{label}] skipping malformed item: {e}")
    return entries


def scrape_openjsf(known_links):
    label = "OpenJS Foundation"
    entries = []
    html = get_html(OPENJSF_BLOG_URL)
    if html is None:
        logger.warning(f"  [{label}] fetch failed; continuing")
        return entries
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.select('a[href^="/blog/"]'):
        href = a.get("href", "")
        if "/category/" in href or "/page/" in href:
            continue
        try:
            link = OPENJSF_BASE + href
            if link in known_links:
                continue
            title_el = a.find("h3")
            if not title_el:
                continue
            title = sanitize_xml(title_el.get_text(" ", strip=True))
            if not title:
                continue
            desc_el = title_el.find_next_sibling("div")
            description = sanitize_xml(desc_el.get_text(" ", strip=True)) if desc_el else title
            time_el = a.find("time")
            date_obj = parse_date(time_el.get("datetime")) if time_el and time_el.get("datetime") else None
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": description,
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:  # one bad card never kills the run
            logger.warning(f"  [{label}] skipping malformed item: {e}")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="JS | Node",
        subtitle="Combined JS/Node.js runtime & tooling feed: Node.js, pnpm, "
                 "jsDelivr (blog + status), Bun, Deno, NodeSource, Total.js, "
                 "Vite, Next.js, Vue, Svelte, npm status, npmx, and the "
                 "OpenJS Foundation blog.",
        blog_url="https://nodejs.org/",
        author="various",
        sources=SOURCES,
        extra_scrapers=[scrape_npmx, scrape_openjsf],
        max_entries=300,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the JS | Node Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    args = parser.parse_args()
    sys.exit(0 if main(full=args.full) else 1)
