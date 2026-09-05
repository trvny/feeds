"""European institutions feed.

The European Parliament's own RSS endpoints (``europarl.europa.eu/rss/...``)
cannot be fetched from a datacenter IP: CloudFront answers every request with
``HTTP 202`` and ``x-amzn-waf-action: challenge``, an AWS WAF interstitial that
needs a real browser to solve. Both HTTP clients, a warmed-up session and the
feeds proxy all get the same 202, so the Parliament is covered here through the
Google News RSS proxy instead — the same workaround this repo already uses for
Cloudflare-challenged sites. That yields Polish-language EP coverage restricted
to ``europarl.europa.eu/news`` rather than the raw per-committee feeds.

Most other sources are native RSS:

  * European Commission press corner, Polish and English. The API endpoint
    (``/presscorner/api/rss?language=..``) is the only one that answers; the
    HTML press corner is a client-rendered SPA.
  * European Central Bank press releases. Note this one needs the curl_cffi
    Chrome impersonation — a plain request gets a stub with a single item,
    which ``multi_rss.get_html`` handles by trying the impersonated client
    first.
  * The Union's own news and priorities channels, the European Commission's
    Research & Innovation topic feed, EU agencies (Europol, EUSPA,
    Interoperable Europe) and independent EU-affairs commentary (ECFR, UNIO,
    EUbusiness). European Law Blog's published ``/rss.xml`` now 404s, so that
    source is covered through a site-scoped Google News RSS query too.
    Institutional sources additionally carry an ``official`` category term, so
    a reader can separate institutional communication from third-party analysis.

The Council (consilium.europa.eu) 403s both clients from a datacenter IP, so it
too arrives through the Google News proxy. The EEA and Court of Justice feed
paths 404.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "europa"

# Google News indexes the whole domain, so the query is scoped to /news to keep
# out document boilerplate and MEP profile pages.
EP_GOOGLE_NEWS = (
    "https://news.google.com/rss/search"
    "?q=site:europarl.europa.eu/news&hl=pl&gl=PL&ceid=PL:pl"
)

SOURCES = [
    ("Parlament Europejski (PL)", EP_GOOGLE_NEWS, 60),
    (
        "Komisja Europejska (PL)",
        "https://ec.europa.eu/commission/presscorner/api/rss?language=pl",
        40,
    ),
    (
        "European Commission (EN)",
        "https://ec.europa.eu/commission/presscorner/api/rss?language=en",
        40,
    ),
    ("European Central Bank", "https://www.ecb.europa.eu/rss/press.html", 30),
    ("ECB — blog", "https://www.ecb.europa.eu/rss/blog.html", 15),
    ("European Union — news", "https://european-union.europa.eu/node/309/rss_en", 30),
    (
        "European Union — priorities",
        "https://european-union.europa.eu/node/279/rss_en",
        30,
    ),
    (
        "European Commission — Research & Innovation",
        "https://research-and-innovation.ec.europa.eu/node/2/rss_en?f%5B0%5D=topic_topic%3A150",
        25,
    ),
    (
        "Council of the EU — press releases",
        "https://news.google.com/rss/search"
        "?q=site:consilium.europa.eu&hl=en-GB&gl=GB&ceid=GB:en",
        25,
    ),
    ("Europol — news", "https://www.europol.europa.eu/cms/api/rss/news", 20),
    ("EUSPA — news", "https://www.euspa.europa.eu/rss.xml", 15),
    (
        "Interoperable Europe — EUPL",
        "https://interoperable-europe.ec.europa.eu/collection/eupl/feed.xml",
        15,
    ),
    ("ECFR", "https://ecfr.eu/feed/", 25),
    (
        "European Law Blog",
        (
            "https://news.google.com/rss/search"
            "?q=site:europeanlawblog.eu&hl=en&gl=US&ceid=US:en"
        ),
        25,
    ),
    ("Official Blog of UNIO", "https://officialblogofunio.com/feed/", 15),
    ("EUbusiness", "https://www.eubusiness.com/feed/", 20),
]

OFFICIAL = "official"

SOURCE_TAGS = {
    "Parlament Europejski (PL)": OFFICIAL,
    "Komisja Europejska (PL)": OFFICIAL,
    "European Commission (EN)": OFFICIAL,
    "European Central Bank": OFFICIAL,
    "ECB — blog": OFFICIAL,
    "European Union — news": OFFICIAL,
    "European Union — priorities": OFFICIAL,
    "European Commission — Research & Innovation": OFFICIAL,
    "Council of the EU — press releases": OFFICIAL,
    "Europol — news": OFFICIAL,
    "EUSPA — news": OFFICIAL,
    "Interoperable Europe — EUPL": OFFICIAL,
}

PER_SOURCE_QUOTA = {
    "": 20,
    "Parlament Europejski (PL)": 60,
    "Komisja Europejska (PL)": 30,
    "European Commission (EN)": 30,
    "European Commission — Research & Innovation": 20,
}


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Europa",
        subtitle="Instytucje europejskie: Parlament Europejski (przez proxy "
        "Google News, bo własne kanały RSS są za AWS WAF), press corner "
        "Komisji Europejskiej po polsku i angielsku, oraz komunikaty "
        "prasowe Europejskiego Banku Centralnego. Dodatkowo kanały news i "
        "priorities Unii, Research & Innovation Komisji Europejskiej, "
        "komunikaty Rady UE, agencje (Europol, EUSPA, "
        "Interoperable Europe) oraz niezależny komentarz o sprawach unijnych "
        "(ECFR, European Law Blog, UNIO, EUbusiness). Źródła instytucjonalne "
        "mają dodatkowy tag 'official'.",
        blog_url="https://european-union.europa.eu/",
        author="various",
        sources=SOURCES,
        source_tags=SOURCE_TAGS,
        max_entries=350,
        per_source_cap=PER_SOURCE_QUOTA,
        language="pl",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Europa Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
