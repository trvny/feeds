"""HP feed: combined Atom from HP's native feeds plus Google News proxies for
sources with no native feed.

Sources:
  * HP Support RSS (support.hp.com) — native RSS, security/driver/support bulletins
  * HPE Newsroom (hpe.com) — native RSS, enterprise press releases
  * HP Newsroom (hp.com/us-en/newsroom.html) — no native feed found; Google
    News site: proxy
  * hppartner.pl news — Polish partner portal, no native feed; Google News
    site: proxy (PL)
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "hp"

SOURCES = [
    ("HP Support", "https://support.hp.com/wcc-widget-services/us-en/rss-feed?category=all", 40),
    ("HPE Newsroom", "https://www.hpe.com/us/en/newsroom/rss.xml", 40),
    ("HP Newsroom (Google News proxy)",
     "https://news.google.com/rss/search?q=site:hp.com/us-en/newsroom&hl=en-US&gl=US&ceid=US:en", 40),
    ("hppartner.pl (Google News proxy)",
     "https://news.google.com/rss/search?q=site:hppartner.pl&hl=pl&gl=PL&ceid=PL:pl", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="HP Newsroom",
        subtitle="Combined HP feed: HP Support bulletins, HPE Newsroom, HP "
                 "Newsroom (via Google News proxy), and hppartner.pl (via "
                 "Google News proxy).",
        blog_url="https://www.hp.com/us-en/newsroom.html",
        author="HP",
        sources=SOURCES,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the HP Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
