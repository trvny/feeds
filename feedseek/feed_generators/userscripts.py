"""UserScripts feed: one combined Atom stream for the userscript ecosystem.

Native feeds only (no scraping, per repo doctrine):
  - Greasespot        the Greasemonkey blog (Blogger Atom)
  - Sleazyfork        latest updated scripts (Greasyfork-family .atom)

Tampermonkey (changelog.php) and Violentmonkey (/posts/) publish no native
feed and would each need a bespoke HTML scraper -- left out for now so this
feed stays scrape-free. Sleazyfork sits behind anti-bot filtering; multi_rss's
curl_cffi Chrome impersonation usually gets through, and per-source isolation
means a block there never sinks the run.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "userscripts"

SOURCES = [
    ("Greasespot", "https://www.greasespot.net/feeds/posts/default", 40),
    ("Sleazyfork", "https://sleazyfork.org/scripts.atom?sort=updated", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="UserScripts",
        subtitle="Combined userscript-ecosystem feed: Greasespot (Greasemonkey "
                 "blog) and Sleazyfork (latest updated scripts).",
        blog_url="https://www.greasespot.net/",
        author="various",
        sources=SOURCES,
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the UserScripts Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
