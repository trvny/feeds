"""European institutions feed.

The European Parliament's own RSS endpoints (``europarl.europa.eu/rss/...``)
cannot be fetched from a datacenter IP: CloudFront answers every request with
``HTTP 202`` and ``x-amzn-waf-action: challenge``, an AWS WAF interstitial that
needs a real browser to solve. Both HTTP clients, a warmed-up session and the
feeds proxy all get the same 202, so the Parliament is covered here through the
Google News RSS proxy instead — the same workaround this repo already uses for
Cloudflare-challenged sites. That yields Polish-language EP coverage restricted
to ``europarl.europa.eu/news`` rather than the raw per-committee feeds.

Everything else is native RSS:

  * European Commission press corner, Polish and English. The API endpoint
    (``/presscorner/api/rss?language=..``) is the only one that answers; the
    HTML press corner is a client-rendered SPA.
  * European Central Bank press releases. Note this one needs the curl_cffi
    Chrome impersonation — a plain request gets a stub with a single item,
    which ``multi_rss.get_html`` handles by trying the impersonated client
    first.

Evaluated and unusable from CI: the Council (consilium.europa.eu) 403s both
clients, and the EEA and Court of Justice feed paths 404.
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
]

PER_SOURCE_QUOTA = {
    "": 40,
    "Parlament Europejski (PL)": 80,
}


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Europa",
        subtitle="Instytucje europejskie: Parlament Europejski (przez proxy "
        "Google News, bo własne kanały RSS są za AWS WAF), press corner "
        "Komisji Europejskiej po polsku i angielsku, oraz komunikaty "
        "prasowe Europejskiego Banku Centralnego.",
        blog_url="https://european-union.europa.eu/",
        author="various",
        sources=SOURCES,
        max_entries=250,
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
