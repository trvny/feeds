"""PAP (Polska Agencja Prasowa) feed: combined Atom from PAP's native RSS
services. pap.pl itself exposes no feed (Incapsula returns "Not found." for
/rss.xml), so the combined feed covers the network's sub-services instead:
Mediaroom, Nauka w Polsce, Zdrowie, Serwis Samorzadowy, Biznes, EuroPAP News,
and Dzieje.pl. Note: samorzad.pap.pl serves valid RSS with a text/html
content-type — harmless, the parser ignores it."""

import argparse
import sys

from multi_rss import run

FEED_NAME = "pap"

SOURCES = [
    ("PAP Mediaroom", "https://pap-mediaroom.pl/rss.xml", 40),
    ("Nauka w Polsce", "https://naukawpolsce.pl/all/rss.xml", 40),
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
        author="Polska Agencja Prasowa",
        sources=SOURCES,
        language="pl",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the PAP Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
