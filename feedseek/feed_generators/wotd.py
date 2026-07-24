"""Word of the Day feed: one combined Atom stream of daily-word sources.

Native feeds: Merriam-Webster's Word of the Day, Wordsmith's A.Word.A.Day,
The Free Dictionary's Word of the Day, and Wiktionary's word of the day via
the MediaWiki `featuredfeed` API. Only Dictionary.com needs scraping — it
dropped its old wotd.rss and serves no feed, but /e/word-of-the-day/ is
server-rendered with `.wotd-entry-wrapper` cards carrying headword, date,
part of speech, and definition.

Every source is routed through extra_scrapers rather than the plain SOURCES
list for one reason: `dedupe_entries` collapses entries that share a
normalized *title*, and these titles are bare words. Two dictionaries
featuring "maverick" on different days would silently lose one of them, so
each title is suffixed with its source before the merge. Within a source the
usual link-based dedupe still applies.

Merriam-Webster is taken from its text RSS rather than the art19 podcast
feed: the podcast items carry no <link> (only an art19 GUID) and the feed
ships its entire ~7000-episode archive, 30 MB on every fetch. The text feed
is ten items, links straight to the word page, and includes the definition.
"""

import argparse
import re
import sys

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run, scrape_feed
from utils import favicon_proxy, sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "wotd"

RSS_SOURCES = [
    ("Merriam-Webster", "https://www.merriam-webster.com/wotd/feed/rss2", 10),
    ("A.Word.A.Day", "https://wordsmith.org/awad/rss1.xml", 10),
    ("The Free Dictionary", "https://www.thefreedictionary.com/_/WoD/rss.aspx", 10),
    (
        "Wiktionary",
        "https://en.wiktionary.org/w/api.php?action=featuredfeed&feed=wotd&feedformat=atom",
        10,
    ),
]

DICTIONARY_URL = "https://www.dictionary.com/e/word-of-the-day/"

# "Word of the day for July 24 union n (countable) The act of ..." -> "union"
_WIKTIONARY_WORD_RE = re.compile(
    r"Word of the day for [A-Z][a-z]+ \d{1,2}\s+(\S+)"
)
_WIKTIONARY_CHROME_RE = re.compile(
    r"^\s*edit\s*·\s*refresh\s*·\s*view\s*(?:Word of the day for [A-Z][a-z]+ \d{1,2}\s*)?"
)


def _qualify(entry, label):
    """Suffix the title with its source so cross-source dedupe can't collide."""
    entry["title"] = sanitize_xml(f"{entry['title']} \u2014 {label}")[:250]
    return entry


def scrape_rss_sources(known_links):
    entries = []
    for label, url, cap in RSS_SOURCES:
        for entry in scrape_feed(label, url, known_links, cap=cap):
            try:
                if label == "Wiktionary":
                    entry = _clean_wiktionary(entry)
                    if entry is None:
                        continue
                entries.append(_qualify(entry, label))
            except Exception as exc:
                logger.warning("  [%s] skipping item: %s", label, exc)
    return entries


def _clean_wiktionary(entry):
    """Wiktionary titles are 'Word of the day for July 24' — pull out the word."""
    description = _WIKTIONARY_CHROME_RE.sub("", entry.get("description", "")).strip()
    match = _WIKTIONARY_WORD_RE.search(entry.get("description", ""))
    if match:
        entry["title"] = match.group(1)
    entry["description"] = sanitize_xml(description)[:500] or entry["title"]
    return entry


def scrape_dictionary_com(known_links):
    """Dictionary.com /e/word-of-the-day/ cards."""
    html = get_html(DICTIONARY_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries, seen = [], set()
    for card in soup.select(".wotd-entry-wrapper"):
        try:
            headword_el = card.select_one(".wotd-entry-headword")
            if not headword_el:
                continue
            word = headword_el.get_text(" ", strip=True)
            if not word:
                continue
            anchor = card.select_one("a[href]")
            href = anchor["href"] if anchor else f"/browse/{word}"
            link = href if href.startswith("http") else "https://www.dictionary.com" + href
            if link in seen or link in known_links:
                continue
            date_el = card.select_one(".wotd-entry-date")
            pos_el = card.select_one(".wotd-entry-pos")
            definition_el = card.select_one(".wotd-entry-definition")
            parts = [
                pos_el.get_text(" ", strip=True) if pos_el else "",
                definition_el.get_text(" ", strip=True) if definition_el else "",
            ]
            description = " \u2014 ".join(part for part in parts if part)
            seen.add(link)
            entries.append(_qualify({
                "title": word,
                "link": link,
                "date": parse_date(date_el.get_text(" ", strip=True)) if date_el else None,
                "description": sanitize_xml(description or word)[:500],
                "source": "Dictionary.com",
            }, "Dictionary.com"))
        except Exception as exc:
            logger.warning("  [Dictionary.com] skipping card: %s", exc)
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Word of the Day",
        subtitle="Combined daily-word feed: Merriam-Webster, Dictionary.com, "
                 "A.Word.A.Day, The Free Dictionary, and Wiktionary.",
        blog_url="https://www.dictionary.com/e/word-of-the-day/",
        icon=favicon_proxy("dictionary.com"),
        author="various",
        extra_scrapers=[scrape_rss_sources, scrape_dictionary_com],
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Word of the Day Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
