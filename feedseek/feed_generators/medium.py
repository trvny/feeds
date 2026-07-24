"""Medium feed: combined Atom from Medium's native per-publication and
per-author RSS feeds — the Medium Blog, Medium Engineering, engineering and
design publications (Flutter, Android Developers, ProAndroidDev, Samsung
Internet, Bootcamp, UX Planet), science and geopolitics publications, and a
handful of individual authors.

Medium serves only the 10 newest items per feed, so history comes from the
JSON cache. Because ~23 sources publish at wildly different rates, the write
uses ``per_source_cap`` so the fast publications cannot evict the slow ones.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "medium"

# Medium caps every RSS endpoint at 10 items, so the fetch cap is just 10.
SOURCES = [
    ("The Medium Blog", "https://medium.com/feed/blog", 10),
    ("Medium Engineering", "https://medium.engineering/feed", 10),
    ("Medium Staff", "https://medium.com/feed/@MediumStaff", 10),
    ("Flutter", "https://blog.flutter.dev/feed", 10),
    ("Android Developers", "https://medium.com/feed/androiddevelopers", 10),
    ("ProAndroidDev", "https://proandroiddev.com/feed", 10),
    ("Samsung Internet Developers", "https://medium.com/feed/samsung-internet-dev", 10),
    ("Yandex", "https://medium.com/feed/yandex", 10),
    ("Toyota Research Institute", "https://medium.com/feed/toyotaresearch", 10),
    ("Bootcamp", "https://medium.com/feed/design-bootcamp", 10),
    ("UX Planet", "https://uxplanet.org/feed", 10),
    ("The Useful Life", "https://medium.com/feed/the-useful-life", 10),
    ("The Riff", "https://medium.com/feed/the-riff", 10),
    ("Starts With A Bang!", "https://medium.com/feed/starts-with-a-bang", 10),
    ("Science Spectrum", "https://sciencespectrumu.com/feed", 10),
    ("Science Fiction", "https://medium.com/feed/science-fiction", 10),
    ("404: Geek Not Found", "https://medium.com/feed/404-geek-not-found", 10),
    ("The Ugly Monster", "https://medium.com/feed/theuglymonster", 10),
    ("The Geopolitics Report", "https://medium.com/feed/the-geopolitics-report", 10),
    ("The Geopolitical Economist", "https://medium.com/feed/the-geopolitical-economist", 10),
    ("Defence Affairs & Analysis", "https://medium.com/feed/@Defenceaffairs", 10),
    ("Russian Bear", "https://medium.com/feed/@russianbearussr", 10),
    ("Damien Walter", "https://damiengwalter.medium.com/feed", 10),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Medium",
        subtitle="Combined Medium feed: the Medium Blog and Engineering, "
                 "Flutter, Android Developers, ProAndroidDev, Samsung "
                 "Internet, Yandex, Toyota Research, Bootcamp, UX Planet, "
                 "The Useful Life, The Riff, Starts With A Bang!, Science "
                 "Spectrum, Science Fiction, 404: Geek Not Found, The Ugly "
                 "Monster, geopolitics publications, and selected authors.",
        blog_url="https://medium.com/",
        author="Medium",
        sources=SOURCES,
        max_entries=200,
        per_source_cap=8,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Medium Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
