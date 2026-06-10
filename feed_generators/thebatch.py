"""The Batch / DeepLearning.AI feed.

Neither deeplearning.ai listing exposes a working feed (the Ghost-style RSS
routes 404/500), but both are Next.js pages that ship their post lists in
``__NEXT_DATA__``:

    - The Batch  https://www.deeplearning.ai/the-batch/  -> pageProps.posts
      (Ghost posts: title, slug, published_at, excerpt)
    - Blog       https://www.deeplearning.ai/blog/       -> pageProps.posts.nodes
      (WordPress nodes: title, slug, date, excerpt)

One fetch per listing per run; history accumulates in the cache.
"""

import argparse
import json
import re
import sys

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "thebatch"


def _next_data(url):
    html = get_html(url)
    if html is None:
        return None
    try:
        nd = BeautifulSoup(html, "html.parser").find("script", id="__NEXT_DATA__")
        return json.loads(nd.string)["props"]["pageProps"]
    except Exception as e:
        logger.warning(f"Could not extract __NEXT_DATA__ from {url}: {e}")
        return None


def _clean(text, limit=500):
    text = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    return sanitize_xml(re.sub(r"\s+", " ", text))[:limit]


def scrape_thebatch(known_links):
    label = "The Batch"
    entries = []
    pp = _next_data("https://www.deeplearning.ai/the-batch/")
    if pp is None:
        return entries
    posts = pp.get("posts") or []
    if not posts:
        logger.warning(f"  [{label}] no posts in __NEXT_DATA__ — page structure may have changed")
        return entries
    for post in posts:
        try:
            slug = post.get("slug")
            if not slug:
                continue
            link = f"https://www.deeplearning.ai/the-batch/{slug}/"
            if link in known_links:
                continue
            title = sanitize_xml(post.get("title") or slug)
            date_obj = parse_date(post.get("published_at")) if post.get("published_at") else None
            desc = _clean(post.get("custom_excerpt") or post.get("excerpt") or title)
            entries.append({
                "title": title, "link": link, "date": date_obj,
                "description": desc or title, "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping malformed post: {e}")
    return entries


def scrape_blog(known_links):
    label = "DeepLearning.AI Blog"
    entries = []
    pp = _next_data("https://www.deeplearning.ai/blog/")
    if pp is None:
        return entries
    nodes = (pp.get("posts") or {}).get("nodes") or []
    if not nodes:
        logger.warning(f"  [{label}] no nodes in __NEXT_DATA__ — page structure may have changed")
        return entries
    for post in nodes:
        try:
            slug = post.get("slug") or post.get("desiredSlug")
            if not slug:
                continue
            link = f"https://www.deeplearning.ai/blog/{slug}/"
            if link in known_links:
                continue
            title = _clean(post.get("title") or slug, 200)
            date_obj = parse_date(post.get("date")) if post.get("date") else None
            desc = _clean(post.get("excerpt") or title)
            entries.append({
                "title": title, "link": link, "date": date_obj,
                "description": desc or title, "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping malformed post: {e}")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="The Batch / DeepLearning.AI",
        subtitle="The Batch newsletter issues and the DeepLearning.AI blog (parsed "
                 "from each page's __NEXT_DATA__; the native RSS routes are broken).",
        blog_url="https://www.deeplearning.ai/the-batch",
        author="DeepLearning.AI",
        extra_scrapers=[scrape_thebatch, scrape_blog],
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate The Batch Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
