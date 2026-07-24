"""arXiv feed: the arXiv blog plus the combined daily new-submissions listing
across every top-level category (math, cs, econ, eess, astro-ph, cond-mat,
gr-qc, hep-ex, hep-th, math-ph, nlin, nucl-th, physics, quant-ph, q-fin,
stat), alongside two adjacent research-commentary sources: LessWrong and
80,000 Hours. Every source is a native feed, so this is a plain multi_rss
SOURCES call — no scraping. The rss.arxiv.org listing feed is genuinely
empty outside arXiv's announcement windows (no weekend/holiday postings);
that's expected, not a fetch failure.

LessWrong is pulled twice: the default feed.xml carries the newest posts,
while ?view=allPosts is the /allPosts listing and lags it by a few hours but
picks up items the default view omits. The two overlap heavily; dedupe_entries
collapses the duplicates by normalized link.
"""

import argparse
import sys

from multi_rss import run

FEED_NAME = "arxiv"

SOURCES = [
    ("arXiv Blog", "https://blog.arxiv.org/feed/", 20),
    (
        "arXiv New Submissions",
        "https://rss.arxiv.org/atom/math+cs+econ+eess+astro-ph+cond-mat+gr-qc+"
        "hep-ex+hep-th+math-ph+nlin+nucl-th+physics+quant-ph+q-fin+stat",
        200,
    ),
    ("LessWrong", "https://www.lesswrong.com/feed.xml", 30),
    ("LessWrong (all posts)", "https://www.lesswrong.com/feed.xml?view=allPosts", 30),
    ("80,000 Hours", "https://80000hours.org/latest/feed/", 30),
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="arXiv",
        subtitle="arXiv blog plus the combined daily new-submissions listing "
                 "across every top-level category, with LessWrong and "
                 "80,000 Hours.",
        blog_url="https://arxiv.org/",
        author="various",
        sources=SOURCES,
        max_entries=500,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the arXiv Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
