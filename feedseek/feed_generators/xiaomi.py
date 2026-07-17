"""Xiaomi feed: combined Atom from Xiaomi's native feeds plus Google News
proxies for sources with no usable native feed.

Sources:
  * xiaomi.eu community forum (index.rss) — native RSS
  * xiaomiadvices.com — native RSS
  * xiaomitoday.com — native RSS
  * Xiaomi Corporation investor news releases (xiaomi.gcs-web.com) — native RSS
  * Xiaomi global newsroom (mi.com/global/discover/newsroom) — no native
    feed; Google News site: proxy
  * Xiaomi India news (mi.com/in/discover/news) — no native feed; Google
    News site: proxy
  * miuipolska.pl forum RSS — Cloudflare-challenge blocked (403 "Just a
    moment..."), no working alternative found; Google News site: proxy (PL)
    substituted instead
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "xiaomi"

SOURCES = [
    ("xiaomi.eu community", "https://xiaomi.eu/community/forums/-/index.rss", 40),
    ("Xiaomi Advices", "https://xiaomiadvices.com/feed/", 40),
    ("Xiaomi Today", "https://xiaomitoday.com/feed/", 40),
    ("Xiaomi Corp Investor News", "https://xiaomi.gcs-web.com/rss/news-releases.xml", 40),
    ("Xiaomi Global Newsroom (Google News proxy)",
     "https://news.google.com/rss/search?q=site:mi.com/global/discover/newsroom&hl=en-US&gl=US&ceid=US:en", 40),
    ("Xiaomi India News (Google News proxy)",
     "https://news.google.com/rss/search?q=site:mi.com/in/discover/news&hl=en-IN&gl=IN&ceid=IN:en", 40),
    ("MIUIPolska (Google News proxy)",
     "https://news.google.com/rss/search?q=site:miuipolska.pl&hl=pl&gl=PL&ceid=PL:pl", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Xiaomi Newsroom",
        subtitle="Combined Xiaomi feed: xiaomi.eu community, Xiaomi Advices, "
                 "Xiaomi Today, Xiaomi Corp investor news, Xiaomi global and "
                 "India newsrooms (via Google News proxy), and MIUIPolska "
                 "(via Google News proxy).",
        blog_url="https://www.mi.com/global/discover/newsroom",
        author="Xiaomi",
        sources=SOURCES,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Xiaomi Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
