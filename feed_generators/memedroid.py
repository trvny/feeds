"""Memedroid feed: scraped Atom feed of trending memes from memedroid.com.

Memedroid has no native feed. The homepage is server-rendered: each meme is an
``article.gallery-item`` carrying a ``time[datetime]`` stamp, a permalink of
the form ``/memes/detail/<id>/<slug>`` (tracking query stripped), the title as
the detail-link text, and the meme image hosted on memes.memedroid.com. The
image is embedded in the entry description, jbzd-style.
"""

import argparse
import re
import sys

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "memedroid"
HOME_URL = "https://www.memedroid.com/"
BASE = "https://www.memedroid.com"

_DETAIL_RE = re.compile(r"^(/memes/detail/\d+/[A-Za-z0-9_-]+)")


def scrape_home(known_links):
    label = "Memedroid"
    entries = []
    html = get_html(HOME_URL)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")

    articles = soup.find_all("article", class_="gallery-item")
    if not articles:
        logger.warning(f"  [{label}] no gallery items matched — layout may have changed")
        return entries

    for art in articles:
        try:
            detail = None
            for a in art.find_all("a", href=True):
                m = _DETAIL_RE.match(a["href"])
                if m:
                    detail = m.group(1)
                    break
            if not detail:
                continue
            link = BASE + detail
            if link in known_links:
                continue
            title = detail.rstrip("/").split("/")[-1].replace("-", " ").capitalize()
            for a in art.find_all("a", href=True):
                if _DETAIL_RE.match(a["href"]) and a.get_text(strip=True):
                    title = a.get_text(" ", strip=True)
                    break
            time_el = art.find("time")
            date_obj = parse_date(time_el.get("datetime")) if time_el and time_el.get("datetime") else None

            img_src = None
            for img in art.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if "memes.memedroid.com" in src:
                    img_src = src
                    break
            title = sanitize_xml(title)
            if img_src:
                desc = sanitize_xml(
                    f'<p><a href="{link}"><img src="{img_src}" alt="{title}" /></a></p>'
                )
            else:
                desc = title
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": desc,
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping malformed item: {e}")
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Memedroid",
        subtitle="Trending memes from memedroid.com (no native feed; scraped from "
                 "the server-rendered homepage).",
        blog_url=HOME_URL,
        author="Memedroid",
        extra_scrapers=[scrape_home],
        max_entries=150,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Memedroid Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
