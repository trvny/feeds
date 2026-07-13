#!/usr/bin/env python3
"""Discover RSS/Atom/JSON feed candidates for a site.

Manual scouting tool, not part of the hourly generator pipeline. Use this
when adding a new source to feeds.yaml, to find native feed URLs before
reaching for a scraper.

Usage:
    uv run feed_generators/discover.py <url>

Tries the local feedsearch-crawler library first (a full async crawl, no
external service dependency). Falls back to the hosted feedsearch.dev API
(https://feedsearch.dev) if the local crawl errors or finds nothing.
"""

import sys


def discover_local(url: str):
    from feedsearch_crawler import search_with_info

    result = search_with_info(url, include_stats=False)
    if result.root_error:
        print(f"local crawl error: {result.root_error.message}", file=sys.stderr)
        return None
    return list(result.feeds)


def discover_hosted(url: str):
    import requests

    resp = requests.get(
        "https://feedsearch.dev/api/v1/search",
        params={"url": url, "info": "true"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    if len(sys.argv) != 2:
        print("usage: discover.py <url>", file=sys.stderr)
        sys.exit(1)
    url = sys.argv[1]

    feeds = discover_local(url)
    source = "local"
    if not feeds:
        print("local crawl found nothing, falling back to feedsearch.dev", file=sys.stderr)
        feeds = discover_hosted(url)
        source = "hosted"

    if not feeds:
        print("no feeds found", file=sys.stderr)
        sys.exit(1)

    print(f"# source: {source}", file=sys.stderr)
    for f in feeds:
        if source == "local":
            print(f"{f.url}\t{f.version}\tscore={f.score}\t{f.title}")
        else:
            print(f"{f['url']}\t{f['version']}\tscore={f['score']}\t{f['title']}")


if __name__ == "__main__":
    main()
