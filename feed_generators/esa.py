"""ESA feed: combined Atom from the European Space Agency's native RSS feeds —
the Newsroom and Corporate News, the per-activity feeds (Space News, Space
Science, Operations, Observing the Earth, Launchers, Navigation,
Telecommunications), the Week in Images, the Webb/Hubble imagery feeds, and the
still-active blogs.esa.int mission blogs.

Notes on the source set (probed against esa.int):
  * The www.esa.int portal pages (Newsroom, Science_Exploration, Enabling_Support,
    …) are JS-rendered Magnolia CMS and expose no dates on article pages, but ESA
    publishes a matching ``/rssfeed/<Section_path>`` for most of them — those
    native feeds are used instead of scraping.
  * ``/rssfeed/Our_Activities`` is identical to ``Our_Activities/Space_News`` and
    ``/rssfeed/EOB`` is identical to ``Observing_the_Earth``, so only one of each
    pair is listed (cross-source dedupe would drop the rest anyway).
  * Science_Exploration / Enabling_Support / Applications have no top-level RSS;
    their content flows through the per-activity feeds above.
  * Press Releases (and the /pl language variant) have no RSS feed; the English
    Newsroom feed covers that ground.
  * esahubble.org/images shares no entries with the Webb or Hubble News feeds, so
    it is kept rather than skipped.
  * blogs.esa.int is a WordPress multisite; every sub-blog exposes ``/feed/``.
    Only the blogs still publishing are listed below -- the dormant ones
    (gaia, cryosat-ice-blog, thomas-pesquet, alexander-gerst, luca-parmitano,
    spaceport, ariane6, mex, eolaunches, ...) either 404 on /feed/ or stopped
    years ago, and the root https://blogs.esa.int/feed/ only carries the legacy
    root blog (last post 2020), not the sub-blogs. ``/atv/`` redirects to
    ``/orion/``, so only the latter is listed.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "esa"
ICON_URL = "https://raw.githubusercontent.com/trvny/feeds/main/assets/icons/esa.png"

_ACT = "https://www.esa.int/rssfeed/Our_Activities"
_BLOGS = "https://blogs.esa.int"
SOURCES = [
    ("Newsroom", "https://www.esa.int/rssfeed/Newsroom", 30),
    ("Corporate News", "https://www.esa.int/rssfeed/About_Us/Corporate_news", 30),
    ("Space News", f"{_ACT}/Space_News", 30),
    ("Space Science", f"{_ACT}/Space_Science", 30),
    ("Operations", f"{_ACT}/Operations", 30),
    ("Observing the Earth", f"{_ACT}/Observing_the_Earth", 30),
    ("Launchers", f"{_ACT}/Launchers", 30),
    ("Navigation", f"{_ACT}/Navigation", 30),
    ("Telecommunications", f"{_ACT}/Telecommunications_Integrated_Applications", 30),
    ("Week in Images", "https://www.esa.int/rssfeed/About_Us/Week_in_images", 10),
    ("Webb News", "https://feeds.feedburner.com/esawebb/news/", 20),
    ("Webb Images", "https://feeds.feedburner.com/esawebb/images/", 30),
    ("Hubble News", "https://feeds.feedburner.com/hubble_news/", 20),
    ("Hubble Images", "https://esahubble.org/images/feed/", 30),
    # blogs.esa.int -- only the sub-blogs still publishing
    ("Campaign Earth", f"{_BLOGS}/campaignearth/feed/", 10),
    ("To Mars and Back", f"{_BLOGS}/to-mars-and-back/feed/", 10),
    ("Exploration Blog", f"{_BLOGS}/exploration/feed/", 10),
    ("CAVES & Pangaea", f"{_BLOGS}/caves/feed/", 10),
    ("Proba-3 Blog", f"{_BLOGS}/proba-3/feed/", 10),
    ("Space Safety", f"{_BLOGS}/spacesafety-community/feed/", 10),
    ("Concordia", f"{_BLOGS}/concordia/feed/", 10),
    ("Orion Blog", f"{_BLOGS}/orion/feed/", 10),
    ("Clean Space", f"{_BLOGS}/cleanspace/feed/", 10),
    ("Rocket Science", f"{_BLOGS}/rocketscience/feed/", 10),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="ESA",
        subtitle="Combined European Space Agency feed: Newsroom, Corporate News, "
                 "the per-activity feeds (Space News, Space Science, Operations, "
                 "Observing the Earth, Launchers, Navigation, Telecommunications), "
                 "the Week in Images, the Webb and Hubble imagery feeds, and the "
                 "active blogs.esa.int mission blogs.",
        blog_url="https://www.esa.int/",
        author="ESA",
        sources=SOURCES,
        max_entries=250,
        icon=ICON_URL,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the ESA Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
