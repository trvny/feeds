"""Sony feed: combined Atom from Sony Group press, electronics, music,
and PlayStation sources.

Sources:
  * Sony Group press releases (sony.co.jp) — the news-release page is
    JS-rendered, but its data source is a hidden RSS at
    ``assets_revamp2025/xml/en/rss_new.xml`` (~80 items, relative links,
    titles prefixed with ``[Company]`` which is lifted into the entry)
  * Sony Electronics US (sony.mediaroom.com) — native RSS
  * SIE press releases (sonyinteractive.com) — WordPress with feeds and the
    REST API disabled, so the server-rendered listing cards are scraped
  * PlayStation Blog (feeds.feedburner.com/psblog) — native RSS
  * Sony Music PL (sonymusic.pl) — native WordPress RSS
  * Sony Music PL newsroom (newsroom.sonymusic.pl) — native Prowly RSS
  * Sony PL community wallpapers (community.sony.pl) — native board RSS

Deliberately not sources (Akamai 403 to non-residential clients, including
curl_cffi Chrome impersonation and GitHub Actions IPs): www.sony.com (press
XML and Corporate Blog), www.sony.pl/presscentre, www.sonymusic.com, and
www.sonypictures.com. The sony.co.jp hidden RSS covers the same Sony Group
press content as the blocked www.sony.com XML.
"""

import argparse
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml

FEED_NAME = "sony"

GROUP_RSS_URL = "https://www.sony.co.jp/en/assets_revamp2025/xml/en/rss_new.xml"
SIE_PRESS_URL = "https://sonyinteractive.com/en/news/press-releases/"

SOURCES = [
    ("Sony Electronics", "https://sony.mediaroom.com/index.php?s=2429&pagetemplate=rss", 40),
    ("PlayStation Blog", "https://feeds.feedburner.com/psblog", 40),
    ("Sony Music PL", "https://www.sonymusic.pl/feed/", 40),
    ("Sony Music PL Newsroom", "https://newsroom.sonymusic.pl/rss", 40),
    ("Sony PL Wallpapers", "https://community.sony.pl/sonyeu1/rss/board?board.id=wallpaper_world", 30),
]


def scrape_sony_group(known_links):
    """Sony Group press releases from the hidden rss_new.xml.

    Items carry relative links (``../../../news-release/...``) that must be
    resolved against the XML's own URL, and titles prefixed with one or more
    ``[Company]`` tags, which are stripped from the title and kept in the
    description.
    """
    entries = []
    xml = get_html(GROUP_RSS_URL)
    if xml is None:
        return entries
    try:
        soup = BeautifulSoup(xml, "xml")
    except Exception:
        return entries

    for item in soup.find_all("item")[:60]:
        try:
            link_el = item.find("link")
            link = urljoin(GROUP_RSS_URL, link_el.get_text(strip=True)) if link_el else ""
            if not link or link in known_links:
                continue
            raw_title = item.find("title").get_text(strip=True) if item.find("title") else ""
            companies = []
            title = raw_title
            while title.startswith("["):
                end = title.find("]")
                if end == -1:
                    break
                companies.append(title[1:end])
                title = title[end + 1:].strip()
            if not title:
                title = raw_title
            desc_el = item.find("description")
            desc = desc_el.get_text(strip=True) if desc_el else ""
            if companies:
                desc = f"{' / '.join(companies)}. {desc}".strip(". ") or title
            entries.append({
                "title": sanitize_xml(title),
                "link": link,
                "date": parse_date(item.find("pubDate").get_text(strip=True)) if item.find("pubDate") else None,
                "description": sanitize_xml(desc or title)[:500],
                "source": "Sony Group Press",
            })
        except Exception:
            continue
    return entries


def scrape_sie_press(known_links):
    """SIE press releases from the server-rendered listing cards
    (``article.sie-post-archive-list__post``); feeds and the WP REST API
    are disabled on this site."""
    entries = []
    html = get_html(SIE_PRESS_URL)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select("article.sie-post-archive-list__post"):
        try:
            a = card.select_one("a.sie-post-archive-list__post-link")
            if not a or not a.get("href"):
                continue
            link = urljoin(SIE_PRESS_URL, a["href"])
            if link in known_links:
                continue
            title = sanitize_xml(a.get_text(" ", strip=True))
            date_el = card.select_one(".sie-post-archive-list__post-date")
            date = parse_date(date_el.get_text(strip=True)) if date_el else None
            byline = card.select_one(".sie-post-archive-list__post-byline-name")
            desc = byline.get_text(strip=True) if byline else title
            entries.append({
                "title": title,
                "link": link,
                "date": date,
                "description": sanitize_xml(desc),
                "source": "SIE Press",
            })
        except Exception:
            continue
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Sony",
        subtitle="Combined Sony feed: Sony Group press, Sony Electronics, "
                 "SIE press releases, PlayStation Blog, Sony Music PL "
                 "(+ newsroom), and Sony PL community wallpapers.",
        blog_url="https://www.sony.com/en/SonyInfo/News/Press/",
        author="Sony",
        sources=SOURCES,
        extra_scrapers=(scrape_sony_group, scrape_sie_press),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Sony Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
