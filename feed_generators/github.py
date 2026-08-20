"""GitHub ecosystem feed: GitHub's own blogs plus the app store built on top
of GitHub Releases.

All regular sources are native RSS:

  * The GitHub Blog and its per-topic channels (changelog, engineering,
    security, open source, AI/ML, enterprise). The channels are subsets of the
    main feed, so the cross-source URL/title dedupe in ``multi_rss`` collapses
    the overlap and the per-topic label survives on whichever copy is kept.
  * GitHub Status incident history.
  * Komi Store, an open-source app store that distributes GitHub Releases.
    Its feed is served from komistore.app but every link points at
    github-store.org, which is the same site under its older domain.
  * The wider Git/GitHub tooling ecosystem: Mergify, Devin, GitGuardian,
    GitKraken, Tower, Shields.io, git-annex, Jekyll, Travis CI and HelloGitHub.
  * The GitHubTrendingRSS streams. Daily, weekly and monthly list the same
    repositories over different windows, so they share one source label: the
    URL dedupe collapses the overlap and the per-source quota treats trending
    as a single bucket instead of giving it three shares of the feed. Those
    items carry no per-item date; ``multi_rss`` stamps them on first sight.
  * Track Awesome List's full and weekly feeds. They share one source label so
    overlapping list updates are deduplicated and use one combined quota.

Devin's general release notes and BeeWare News have no native feeds used here,
so the generator folds them in with small HTML/MDX adapters.

The changelog is the highest-volume channel by far, so it gets the largest
quota. The global cap keeps the combined feed bounded while per-source quotas
preserve space for lower-volume ecosystem sources.
"""

import argparse
import re
import sys
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from cognition import (
    DEVIN_DESKTOP_RSS_URL,
    DEVIN_RELEASE_NOTES_URL,
    collect_devin_release_notes,
)
from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, stable_fallback_date

FEED_NAME = "github"

TRENDING = "GitHub Trending"
AWESOME_LISTS = "Track Awesome List"
MERGIFY_CHANGELOG_RSS_URL = "https://docs.mergify.com/changelog/rss.xml"
BEEWARE_NEWS_URL = "https://beeware.org/news/"
BEEWARE_LABEL = "BeeWare News"
BEEWARE_MAX = 20
_BEEWARE_ARTICLE_RE = re.compile(r"^/news/[^/]+/20\d{2}/[^/]+/?$")

SOURCES = [
    ("GitHub Changelog", "https://github.blog/changelog/feed/", 40),
    ("GitHub Engineering", "https://github.blog/engineering/feed/", 30),
    ("GitHub Security", "https://github.blog/security/feed/", 30),
    ("GitHub Open Source", "https://github.blog/open-source/feed/", 30),
    ("GitHub AI & ML", "https://github.blog/ai-and-ml/feed/", 30),
    ("GitHub Enterprise", "https://github.blog/enterprise-software/feed/", 20),
    ("GitHub Status", "https://www.githubstatus.com/history.atom", 25),
    ("Komi Store", "https://komistore.app/blog/feed.xml", 20),
    ("The GitHub Blog", "https://github.blog/feed/", 40),
    ("Mergify Changelog", MERGIFY_CHANGELOG_RSS_URL, 30),
    ("Devin Desktop", DEVIN_DESKTOP_RSS_URL, 30),
    ("GitGuardian", "https://blog.gitguardian.com/rss/", 20),
    ("GitKraken", "https://www.gitkraken.com/feed", 15),
    ("Tower", "https://feeds.git-tower.com/tower-blog", 20),
    ("Shields.io", "https://shields.io/blog/atom.xml", 15),
    ("git-annex", "https://git-annex.branchable.com/news/index.atom", 15),
    ("Jekyll", "https://jekyllrb.com/feed.xml", 10),
    ("Travis CI", "https://www.travis-ci.com/feed/", 10),
    ("HelloGitHub", "https://hellogithub.com/rss", 20),
    (TRENDING, "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml", 15),
    (TRENDING, "https://mshibanami.github.io/GitHubTrendingRSS/weekly/all.xml", 15),
    (TRENDING, "https://mshibanami.github.io/GitHubTrendingRSS/monthly/all.xml", 15),
    (AWESOME_LISTS, "https://www.trackawesomelist.com/rss.xml", 20),
    (AWESOME_LISTS, "https://www.trackawesomelist.com/week/rss.xml", 20),
]

PER_SOURCE_QUOTA = {
    "": 30,
    "GitHub Changelog": 60,
    "GitHub Status": 20,
    TRENDING: 20,
    AWESOME_LISTS: 30,
}


def _meta(page, attr, value):
    element = page.find("meta", attrs={attr: value})
    return element["content"].strip() if element and element.get("content") else None


def scrape_beeware_news(known_links):
    """Scrape BeeWare's news index and normalize new article pages."""
    index = get_html(BEEWARE_NEWS_URL)
    if not index:
        return []

    soup = BeautifulSoup(index, "html.parser")
    links = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        link = urljoin(BEEWARE_NEWS_URL, anchor["href"].split("#")[0].split("?")[0])
        parsed = urlparse(link)
        if parsed.hostname not in {"beeware.org", "www.beeware.org"}:
            continue
        if not _BEEWARE_ARTICLE_RE.match(parsed.path):
            continue
        canonical = f"https://beeware.org{parsed.path}"
        if canonical in seen or canonical in known_links:
            continue
        seen.add(canonical)
        links.append(canonical)

    entries = []
    for link in links:
        try:
            html = get_html(link)
            if not html:
                continue
            page = BeautifulSoup(html, "html.parser")
            title = _meta(page, "property", "og:title")
            if not title:
                heading = page.find("h1")
                title = heading.get_text(" ", strip=True) if heading else None
            if not title:
                continue

            description = (
                _meta(page, "property", "og:description")
                or _meta(page, "name", "description")
                or title
            )
            published = _meta(page, "property", "article:published_time")
            if not published:
                time_el = page.find("time", datetime=True)
                published = time_el.get("datetime") if time_el else None
            image = _meta(page, "property", "og:image")

            entries.append(
                {
                    "title": sanitize_xml(title),
                    "link": link,
                    "date": parse_date(published) if published else stable_fallback_date(link),
                    "description": sanitize_xml(description),
                    "source": BEEWARE_LABEL,
                    "image": image,
                }
            )
        except Exception:
            continue
        if len(entries) >= BEEWARE_MAX:
            break
    return entries


EXTRA_SCRAPERS = (collect_devin_release_notes, scrape_beeware_news)


def doc_sources():
    """Expose non-RSS sources to generated docs."""
    return [
        ("Devin Release Notes", DEVIN_RELEASE_NOTES_URL),
        (BEEWARE_LABEL, BEEWARE_NEWS_URL),
    ]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="GitHub",
        subtitle="Combined GitHub feed: GitHub blogs and changelogs, GitHub "
        "Status, Mergify and Devin updates, BeeWare News, Komi Store, the Git "
        "tooling ecosystem, Track Awesome List and deduplicated GitHub trending "
        "streams.",
        blog_url="https://github.blog/",
        author="GitHub",
        sources=SOURCES,
        refresh_sources=("GitHub Status",),
        extra_scrapers=EXTRA_SCRAPERS,
        max_entries=400,
        per_source_cap=PER_SOURCE_QUOTA,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the GitHub Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
