"""US.gov feed: combined Atom from a spread of U.S. federal government sources.

Native RSS/Atom (consumed directly):
  * NSA News (DotNetNuke ArticleCS RSS)
  * Department of War — Featured Stories, News, Advisories, News Releases
    (war.gov, the renamed DoD; four DNN ArticleCS feeds)
  * FBI — Press Releases and Stories (native RSS; fbi.gov/news/atom.xml is a
    nav sitemap, not news, so the per-section RSS feeds are used instead)
  * NOAA News (noaa.gov/rss.xml — the "News Around NOAA" stream; weather.gov/news
    itself is JS-rendered and has no native feed, so the NOAA RSS is used)

Scraped (no native feed available):
  * USAGov Blog (usa.gov/blog — Drupal Views listing; dates come from the
    /blog/YYYY/MM/ URL path. Publishes infrequently, so entries skew old; in a
    combined feed that's fine — the fresher sources keep the feed current.)
  * GSA Blog (gsa.gov/blog — dated /blog/YYYY/MM/DD/ links)
  * GSA News Releases (gsa.gov/about-gsa/newsroom/news-releases — the newsroom
    landing page is just a nav hub, so the news-releases listing is scraped;
    dates are the trailing MMDDYYYY in each release slug)

Proxied:
  * U.S. Army (army.mil/newsroom) — army.mil sits behind Akamai and returns 403
    to every automated client regardless of impersonation, so Army news is
    pulled via the Google News RSS proxy (links are Google News redirects).
"""

import argparse
import re
import sys
from datetime import datetime
from urllib.parse import urljoin

import pytz
from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, favicon_proxy

FEED_NAME = "usgov"

# --- Native RSS / Atom -----------------------------------------------------

_WAR = "https://www.war.gov/DesktopModules/ArticleCS/RSS.ashx"
SOURCES = [
    ("NSA", "https://www.nsa.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=1282&max=20", 20),
    ("War: Featured Stories", f"{_WAR}?ContentType=800&Site=945&max=10", 10),
    ("War: News", f"{_WAR}?ContentType=1&Site=945&max=10", 10),
    ("War: Advisories", f"{_WAR}?ContentType=2&Site=945&max=10", 10),
    ("War: News Releases", f"{_WAR}?ContentType=9&Site=945&max=10", 10),
    ("NOAA", "https://www.noaa.gov/rss.xml", 20),
]

# --- Scrapers --------------------------------------------------------------

USAGOV_BLOG = "https://www.usa.gov/blog"
GSA_BLOG = "https://www.gsa.gov/blog"
GSA_NEWS = "https://www.gsa.gov/about-gsa/newsroom/news-releases"
FBI_FEEDS = [
    ("FBI: Press Releases", "https://www.fbi.gov/news/press-releases/rss.xml", 20),
    ("FBI: Stories", "https://www.fbi.gov/news/stories/rss.xml", 15),
]

logger = __import__("multi_rss").logger


def scrape_fbi(known_links):
    """FBI RSS items carry their URL in <guid> with no <link> element, so the
    shared multi_rss link extractor skips them — parse them here directly."""
    entries = []
    for label, url, cap in FBI_FEEDS:
        xml = get_html(url)
        if not xml:
            continue
        for item in BeautifulSoup(xml, "xml").find_all("item")[:cap]:
            try:
                guid = item.find("guid")
                link = guid.get_text(strip=True) if guid else ""
                if not link or link in known_links:
                    continue
                title_el = item.find("title")
                title = sanitize_xml(title_el.get_text(strip=True)) if title_el else label
                desc_el = item.find("description")
                desc = sanitize_xml(desc_el.get_text(strip=True))[:500] if desc_el else title
                pub = item.find("pubDate")
                entries.append({
                    "title": title, "link": link,
                    "date": parse_date(pub.get_text(strip=True)) if pub else None,
                    "description": desc or title, "source": label,
                })
            except Exception as e:
                logger.warning(f"  [{label}] skipping item: {e}")
    return entries


def _date_from_path(href, *, with_day):
    """Pull a date out of a /blog/YYYY/MM[/DD]/ URL path."""
    m = re.search(r"/blog/(\d{4})/(\d{2})(?:/(\d{2}))?/", href)
    if not m:
        return None
    day = int(m.group(3)) if (with_day and m.group(3)) else 1
    try:
        return datetime(int(m.group(1)), int(m.group(2)), day, tzinfo=pytz.UTC)
    except ValueError:
        return None


def scrape_usagov_blog(known_links):
    html = get_html(USAGOV_BLOG)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for row in soup.select(".views-row"):
        try:
            h = row.find(["h2", "h3"])
            a = row.find("a", href=True)
            if not h or not a:
                continue
            link = urljoin(USAGOV_BLOG, a["href"])
            if link in known_links:
                continue
            title = sanitize_xml(h.get_text(strip=True))
            text = row.get_text(" ", strip=True)
            desc = sanitize_xml(text.replace(title, "", 1).replace("Image", "", 1).strip())[:500]
            entries.append({
                "title": title, "link": link,
                "date": _date_from_path(a["href"], with_day=False),
                "description": desc or title, "source": "USAGov Blog",
            })
        except Exception as e:
            logger.warning(f"  [USAGov Blog] skipping item: {e}")
    return entries


def scrape_gsa_blog(known_links):
    html = get_html(GSA_BLOG)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries, seen = [], set()
    for a in soup.find_all("a", href=True):
        try:
            if not re.search(r"/blog/\d{4}/\d{2}/\d{2}/", a["href"]):
                continue
            title = sanitize_xml(a.get_text(strip=True))
            if not title or title.lower() == "read more":
                continue
            link = urljoin(GSA_BLOG, a["href"])
            if link in known_links or link in seen:
                continue
            seen.add(link)
            entries.append({
                "title": title, "link": link,
                "date": _date_from_path(a["href"], with_day=True),
                "description": title, "source": "GSA Blog",
            })
        except Exception as e:
            logger.warning(f"  [GSA Blog] skipping item: {e}")
    return entries


def scrape_gsa_news(known_links):
    html = get_html(GSA_NEWS)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries, seen = [], set()
    for a in soup.find_all("a", href=True):
        try:
            if "/newsroom/news-releases/" not in a["href"]:
                continue
            title = sanitize_xml(a.get_text(strip=True))
            if not title:
                continue
            link = urljoin(GSA_NEWS, a["href"])
            if link in known_links or link in seen:
                continue
            seen.add(link)
            m = re.search(r"-(\d{2})(\d{2})(\d{4})(?:[/?#]|$)", a["href"])
            date = None
            if m:
                try:
                    date = datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)), tzinfo=pytz.UTC)
                except ValueError:
                    pass
            entries.append({
                "title": title, "link": link, "date": date,
                "description": title, "source": "GSA News Releases",
            })
        except Exception as e:
            logger.warning(f"  [GSA News] skipping item: {e}")
    return entries


_ARMY_PROXY = "https://news.google.com/rss/search?q=site:army.mil/news+when:30d&hl=en-US&gl=US&ceid=US:en"
_ARMY_CAP = 20


def scrape_army(known_links):
    """army.mil 403s every automated client (Akamai); pull via Google News."""
    xml = get_html(_ARMY_PROXY)
    if not xml:
        return []
    soup = BeautifulSoup(xml, "xml")
    entries = []
    for item in soup.find_all("item"):
        if len(entries) >= _ARMY_CAP:
            break
        try:
            title_el, link_el = item.find("title"), item.find("link")
            if not title_el or not link_el:
                continue
            link = link_el.get_text(strip=True)
            if not link or link in known_links:
                continue
            title = sanitize_xml(title_el.get_text(strip=True))
            src_el = item.find("source")
            src = src_el.get_text(strip=True) if src_el else ""
            if src and title.endswith(f" - {src}"):
                title = title[: -len(f" - {src}")].strip()
            pub = item.find("pubDate")
            entries.append({
                "title": title, "link": link,
                "date": parse_date(pub.get_text(strip=True)) if pub else None,
                "description": title, "source": "U.S. Army",
            })
        except Exception as e:
            logger.warning(f"  [U.S. Army] skipping item: {e}")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="US.gov",
        subtitle="Combined U.S. federal government feed: NSA, Department of War "
                 "(Featured Stories, News, Advisories, News Releases), FBI, "
                 "NOAA, the USAGov and GSA blogs, GSA news releases, and U.S. "
                 "Army news.",
        blog_url="https://www.usa.gov/",
        icon=favicon_proxy("usa.gov"),
        author="U.S. Government",
        sources=SOURCES,
        extra_scrapers=(scrape_fbi, scrape_usagov_blog, scrape_gsa_blog, scrape_gsa_news, scrape_army),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the US.gov Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
