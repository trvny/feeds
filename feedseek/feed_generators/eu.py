"""EU feed: combined Atom from European Union institutions, agencies and
independent EU-affairs commentary.

Official sources (europa.eu institutions and agencies) additionally carry an
``official`` category term, so a reader can separate institutional
communication from third-party analysis.

The Council of the EU (consilium.europa.eu) blocks datacenter IPs outright, so
its press releases arrive through the Google News proxy instead.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "eu"

OFFICIAL = "official"

SOURCES = [
    # --- EU institutions -------------------------------------------------
    ("European Union — news", "https://european-union.europa.eu/node/309/rss_en", 30),
    ("European Union — priorities", "https://european-union.europa.eu/node/279/rss_en", 30),
    ("European Commission — press corner",
     "https://ec.europa.eu/commission/presscorner/api/rss?language=en", 20),
    ("Council of the EU — press releases",
     "https://news.google.com/rss/search?q=site:consilium.europa.eu&hl=en-GB&gl=GB&ceid=GB:en", 25),
    ("ECB — press releases", "https://www.ecb.europa.eu/rss/press.html", 20),
    ("ECB — blog", "https://www.ecb.europa.eu/rss/blog.html", 15),
    # --- EU agencies -----------------------------------------------------
    ("Europol — news", "https://www.europol.europa.eu/cms/api/rss/news", 20),
    ("EUSPA — news", "https://www.euspa.europa.eu/rss.xml", 15),
    ("Interoperable Europe — EUPL",
     "https://interoperable-europe.ec.europa.eu/collection/eupl/feed.xml", 15),
    # --- Independent EU-affairs commentary -------------------------------
    ("ECFR", "https://ecfr.eu/feed/", 25),
    ("European Law Blog", "https://www.europeanlawblog.eu/rss.xml", 25),
    ("Official Blog of UNIO", "https://officialblogofunio.com/feed/", 15),
    ("EUbusiness", "https://www.eubusiness.com/feed/", 20),
]

SOURCE_TAGS = {
    "European Union — news": OFFICIAL,
    "European Union — priorities": OFFICIAL,
    "European Commission — press corner": OFFICIAL,
    "Council of the EU — press releases": OFFICIAL,
    "ECB — press releases": OFFICIAL,
    "ECB — blog": OFFICIAL,
    "Europol — news": OFFICIAL,
    "EUSPA — news": OFFICIAL,
    "Interoperable Europe — EUPL": OFFICIAL,
}


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="EU",
        subtitle="Combined EU feed: European Union news and priorities, the "
                 "Commission press corner, Council press releases, the ECB "
                 "(press + blog), Europol, EUSPA, Interoperable Europe, and "
                 "independent EU-affairs commentary (ECFR, European Law Blog, "
                 "UNIO, EUbusiness). Institutional sources are tagged "
                 "'official'.",
        blog_url="https://european-union.europa.eu/",
        author="European Union",
        sources=SOURCES,
        source_tags=SOURCE_TAGS,
        max_entries=200,
        per_source_cap=14,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the EU Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
