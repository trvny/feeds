"""Python ecosystem feed: one combined Atom stream for the language, the PSF,
packaging, and the wider community.

All sources are native RSS/Atom feeds parsed through ``multi_rss`` (per-source
``<category>`` label, cross-source URL/title dedupe, JSON-cached history):

  * PyPI Blog           https://blog.pypi.org/              packaging index news
  * Python Status       https://status.python.org/         infra incidents
  * Planet Python       https://planetpython.org/          community firehose
  * Python.org Downloads https://www.python.org/downloads/  every release artifact
  * Python Central      https://www.pythoncentral.io/      tutorials
  * PEPs                https://peps.python.org/           enhancement proposals
  * PyPI Updates        https://pypi.org/                  newly released packages (capped 5/day)
  * PyDevTools          https://pydevtools.com/handbook/   dev-tool handbook
  * pip / build / cibuildwheel  GitHub releases.atom       pypa tooling releases

Planet Python already aggregates Python Insider (blog.python.org), the PSF Blog
(pyfound.blogspot.com) and Real Python, so those are not fetched standalone; they
arrive via Planet and ``multi_rss``'s normalized URL/title dedupe keeps each
story single.

The pypa tools (pip, build, cibuildwheel) publish their changelogs as Sphinx /
MkDocs doc pages, but each also ships a native, dated GitHub Releases Atom feed
carrying the same version notes, which is far more robust than scraping three
different doc-site layouts.

pydantic.dev/articles has no native feed (Next.js, server-rendered cards with
clean ``og:title`` / ``article:published_time`` meta), so it is folded in via a
small custom scraper.

Deliberately excluded:
  * planetpython.org/opml.xml   — an OPML feed *list*, not a feed.
  * feeds.feedburner.com/PythonSoftwareFoundationNews — the FeedBurner feed has
    been hijacked and now serves unrelated e-commerce spam.
"""

import argparse
import sys
from collections import defaultdict

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, stable_fallback_date

FEED_NAME = "python"

# (label, feed URL, per-source cap) — native RSS/Atom feeds.
SOURCES = [
    ("PyPI Blog", "https://blog.pypi.org/feed_rss_created.xml", 40),
    ("Python Status", "https://status.python.org/history.atom", 30),
    ("Planet Python", "https://planetpython.org/rss20.xml", 60),
    ("Python.org Downloads", "https://www.python.org/downloads/feed.rss", 30),
    ("Python Central", "https://feeds.feedburner.com/PythonCentral", 20),
    ("PEPs", "https://peps.python.org/peps.rss", 40),
    ("PyPI Updates", "https://pypi.org/rss/updates.xml", 5),
    ("PyDevTools", "https://pydevtools.com/handbook/reference/index.xml", 30),
    ("pip", "https://github.com/pypa/pip/releases.atom", 15),
    ("build (pypa)", "https://github.com/pypa/build/releases.atom", 15),
    ("cibuildwheel", "https://github.com/pypa/cibuildwheel/releases.atom", 15),
]


# pydantic.dev/articles: a static grid of <a href="/articles/<slug>"> cards with
# no native feed. Each post page server-renders og:title + og:description +
# article:published_time, so we discover slugs from the index and fetch detail.
PYDANTIC_INDEX = "https://pydantic.dev/articles"
PYDANTIC_MAX = 15


def scrape_pydantic(known_links):
    index = get_html(PYDANTIC_INDEX)
    if not index:
        return []
    soup = BeautifulSoup(index, "html.parser")
    slugs = []
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0].split("#")[0]
        # real posts are /articles/<slug>; the /articles hub itself is skipped
        if href.startswith("/articles/") and href.rstrip("/") != "/articles":
            slugs.append(href.rstrip("/"))
    entries, seen = [], set()
    for href in slugs:
        link = "https://pydantic.dev" + href
        if link in seen or link in known_links:
            continue
        seen.add(link)
        try:
            html = get_html(link)
            if not html:
                continue
            page = BeautifulSoup(html, "html.parser")

            def meta(attr, val):
                el = page.find("meta", attrs={attr: val})
                return el["content"].strip() if el and el.get("content") else None

            title = meta("property", "og:title")
            if not title:
                t = page.find("title")
                title = t.get_text(strip=True) if t else None
            if not title:
                continue
            description = meta("property", "og:description") or meta("name", "description") or title
            published = meta("property", "article:published_time")
            date = parse_date(published) if published else None
            entries.append({
                "title": sanitize_xml(title),
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": sanitize_xml(description),
                "source": "Pydantic",
            })
        except Exception:  # one bad post never kills the feed
            continue
        if len(entries) >= PYDANTIC_MAX:
            break
    return entries


def _pypi_daily_cap(limit=5):
    """cache_filter keeping at most *limit* PyPI Updates entries per UTC day.

    PyPI's ``updates`` feed is a firehose (every package release), so without a
    bound its entries accumulate across the 2-hourly runs and swamp the feed.
    Non-PyPI sources are always kept; PyPI entries are counted per calendar day
    and dropped past the limit. Newly fetched entries this run bypass the filter
    (it only sees the cache), so a given day can briefly hold a few more than
    *limit* until the next load prunes it back.
    """
    seen = defaultdict(int)

    def keep(entry):
        if entry.get("source") != "PyPI Updates":
            return True
        date = entry.get("date")
        day = date.strftime("%Y-%m-%d") if date else "undated"
        seen[day] += 1
        return seen[day] <= limit

    return keep


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Python",
        subtitle="Combined Python ecosystem feed: PyPI (blog + updates), "
                 "Python Status, Planet Python, python.org downloads, "
                 "Python Central, PEPs, PyDevTools, pip/build/cibuildwheel "
                 "releases, and Pydantic.",
        blog_url="https://www.python.org/",
        author="the Python community",
        sources=SOURCES,
        extra_scrapers=[scrape_pydantic],
        max_entries=300,
        cache_filter=_pypi_daily_cap(5),
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined Python ecosystem Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
