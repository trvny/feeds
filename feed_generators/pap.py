"""PAP (Polska Agencja Prasowa) network aggregate.

Most sub-services expose native RSS. ``pap.pl`` itself has no usable feed, and
Nauka w Polsce's advertised ``/all/rss.xml`` currently rejects both supported
HTTP clients with host validation, so Nauka is covered through a site-scoped
Google News RSS query. The remaining sources are Mediaroom, Zdrowie, Serwis
Samorzadowy, Biznes, EuroPAP News and Dzieje.pl. ``samorzad.pap.pl`` serves
valid RSS with a ``text/html`` content type, which the parser accepts."""

import argparse
import sys

from multi_rss import run
from utils import favicon_proxy

FEED_NAME = "pap"

SOURCES = [
    ("PAP Mediaroom", "https://pap-mediaroom.pl/rss.xml", 40),
    (
        "Nauka w Polsce",
        (
            "https://news.google.com/rss/search"
            "?q=site:naukawpolsce.pl&hl=pl&gl=PL&ceid=PL:pl"
        ),
        40,
    ),
    ("PAP Zdrowie", "https://zdrowie.pap.pl/rss.xml", 40),
    ("Serwis Samorzadowy", "https://samorzad.pap.pl/rss.xml", 40),
    ("PAP Biznes", "https://biznes.pap.pl/rss", 40),
    ("EuroPAP News", "https://europapnews.pap.pl/rss.xml", 40),
    ("Dzieje.pl", "https://dzieje.pl/rss.xml", 40),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="PAP",
        subtitle="Combined PAP network feed: Mediaroom, Nauka w Polsce, Zdrowie, "
                 "Serwis Samorzadowy, Biznes, EuroPAP News, and Dzieje.pl.",
        blog_url="https://www.pap.pl/",
        icon=favicon_proxy("pap.pl"),
        author="Polska Agencja Prasowa",
        sources=SOURCES,
        language="pl",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the PAP Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
