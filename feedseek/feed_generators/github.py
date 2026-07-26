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

The changelog is the highest-volume channel by far, so it gets the largest
quota. ``max_entries`` is deliberately above the sum of the quotas (260), so a
low-volume source like Komi Store, which posts a few times a year, keeps its
slot instead of being squeezed out by the newest-first trim.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "github"

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
]

PER_SOURCE_QUOTA = {
    "": 30,
    "GitHub Changelog": 60,
    "GitHub Status": 20,
}


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="GitHub",
        subtitle="Combined GitHub feed: The GitHub Blog and its changelog, "
        "engineering, security, open source, AI/ML and enterprise "
        "channels, GitHub Status incidents, and Komi Store — the "
        "open-source app store for GitHub Releases.",
        blog_url="https://github.blog/",
        author="GitHub",
        sources=SOURCES,
        refresh_sources=("GitHub Status",),
        max_entries=300,
        per_source_cap=PER_SOURCE_QUOTA,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the GitHub Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
