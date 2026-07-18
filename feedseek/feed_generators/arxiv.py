"""arXiv feed: the arXiv blog plus the combined daily new-submissions listing
across every top-level category (math, cs, econ, eess, astro-ph, cond-mat,
gr-qc, hep-ex, hep-th, math-ph, nlin, nucl-th, physics, quant-ph, q-fin,
stat). Both are native feeds, so this is a plain multi_rss SOURCES call —
no scraping. The rss.arxiv.org listing feed is genuinely empty outside
arXiv's announcement windows (no weekend/holiday postings); that's expected,
not a fetch failure.
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
]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="arXiv",
        subtitle="arXiv blog plus the combined daily new-submissions listing "
                 "across every top-level category.",
        blog_url="https://arxiv.org/",
        author="arXiv",
        sources=SOURCES,
        max_entries=500,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the arXiv Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
