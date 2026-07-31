"""GitHub ecosystem feed: GitHub's own blogs plus the app store built on top
of GitHub Releases.

All sources are native RSS:

  * The GitHub Blog and its per-topic channels (changelog, engineering,
    security, open source, AI/ML, enterprise). The channels are subsets of the
    main feed, so the cross-source URL/title dedupe in ``multi_rss`` collapses
    the overlap and the per-topic label survives on whichever copy is kept.
  * GitHub Status incident history.
  * Komi Store, an open-source app store that distributes GitHub Releases.
    Its feed is served from komistore.app but every link points at
    github-store.org, which is the same site under its older domain.
  * The wider Git/GitHub tooling ecosystem: GitGuardian, GitKraken, Tower,
    Shields.io, git-annex, Jekyll, Travis CI and HelloGitHub.
  * The GitHubTrendingRSS streams. Daily, weekly and monthly list the same
    repositories over different windows, so they share one source label: the
    URL dedupe collapses the overlap and the per-source quota treats trending
    as a single bucket instead of giving it three shares of the feed. Those
    items carry no per-item date; ``multi_rss`` stamps them on first sight.
  * Track Awesome List's full and weekly feeds. They share one source label so
    overlapping list updates are deduplicated and use one combined quota.

The changelog is the highest-volume channel by far, so it gets the largest
quota. The global cap keeps the combined feed bounded while per-source quotas
preserve space for lower-volume ecosystem sources.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "github"

TRENDING = "GitHub Trending"
AWESOME_LISTS = "Track Awesome List"

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


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="GitHub",
        subtitle="Combined GitHub feed: The GitHub Blog and its changelog, "
        "engineering, security, open source, AI/ML and enterprise "
        "channels, GitHub Status incidents, and Komi Store — the "
        "open-source app store for GitHub Releases, the Git tooling "
        "ecosystem (GitGuardian, GitKraken, Tower, Shields.io, git-annex, "
        "Jekyll, Travis CI, HelloGitHub), Track Awesome List and the "
        "deduplicated GitHub trending streams.",
        blog_url="https://github.blog/",
        author="GitHub",
        sources=SOURCES,
        refresh_sources=("GitHub Status",),
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
