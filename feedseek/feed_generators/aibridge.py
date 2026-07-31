"""AI-bridge feed: one combined Atom stream of AI labs and newsletters.

Native RSS sources: Thinking Machines, Ollama, Mistral, Interconnected
(Matt Webb), AI Clock (Substack), the Polish AI blogs Promptowy and Maistry,
and Stability AI (news-updates, via the
Squarespace ?format=rss trick — see note below). On top of those it reuses
the existing scrapers for Perplexity's Framer sites (Blog/Changelog/Research
+ API docs changelog RSS) and The Batch / DeepLearning.AI (__NEXT_DATA__) —
same parsers, separate cache, so this feed stands alone even though the
sources overlap with feed_perplexity.xml and feed_thebatch.xml. Groq
(blog/newsroom/changelog + groq-changelog commits) is folded in the same way
via groq.scrape_all.

Stability AI: plain /news?format=rss and /news/rss.xml both 301-redirect to
the client-rendered /news-updates page, dropping the query string — but
appending the same ?format=rss straight onto /news-updates works (Squarespace
serves the collection's native RSS from there instead). /blog/rss.xml still
404s and isn't used.
"""

import argparse
import re
import sys

from bs4 import BeautifulSoup
from groq import scrape_all as scrape_groq
from multi_rss import get_html, parse_date, run, scrape_feed
from perplexity import RSS_SOURCES as PERPLEXITY_RSS
from perplexity import scrape_framer_listings
from thebatch import scrape_blog as scrape_dlai_blog
from thebatch import scrape_thebatch
from utils import favicon_proxy, sanitize_xml

FEED_NAME = "aibridge"

# Slots in the written feed, per source. The "" key is the default.
PER_SOURCE_QUOTA = {
    "": 40,
    "CrewClaw": 12,
    "Perplexity Blog": 30,
    "Promptowy": 30,
}

ANSWER_AI_FEED = "https://www.answer.ai/index.xml"
ANSWER_AI_TOOLCALLING = "https://www.answer.ai/posts/2026-01-20-toolcalling.html"
ANSWER_AI_TOOLCALLING_DESCRIPTION = (
    "A security analysis of language models calling tools that were not explicitly "
    "provided, with demonstrations across several major AI providers."
)

SOURCES = [
    ("Thinking Machines", "https://thinkingmachines.ai/blog/index.xml", 40),
    ("Ollama", "https://ollama.com/blog/rss.xml", 40),
    ("Mistral", "https://mistral.ai/rss.xml", 40),
    ("Interconnected", "https://interconnected.org/home/feed", 40),
    ("AI Clock", "https://aiclock.substack.com/feed", 40),
    ("Stability AI", "https://stability.ai/news-updates?format=rss", 30),
    ("Promptowy", "https://promptowy.com/feed/", 40),
    ("Maistry", "https://maistry.pl/rss/", 40),
    ("Karpathy", "https://karpathy.bearblog.dev/feed/", 40),
    ("Karpathy (blog)", "https://karpathy.github.io/feed.xml", 40),
    ("Transformer", "https://www.transformernews.ai/feed", 40),
] + list(PERPLEXITY_RSS)


# Answer.AI shipped this item without a usable per-entry date and with build
# output as its summary. Without a fixed date feedgen assigns the generation
# time on every run, so readers repeatedly surface the same stable entry.
def repair_answer_ai_entry(entry):
    repaired = dict(entry)
    if repaired.get("link") == ANSWER_AI_TOOLCALLING:
        repaired["date"] = parse_date("2026-02-18")
        repaired["description"] = ANSWER_AI_TOOLCALLING_DESCRIPTION
    return repaired


def scrape_answer_ai(known_links):
    entries = scrape_feed("Answer.AI", ANSWER_AI_FEED, known_links, cap=40)
    return [repair_answer_ai_entry(entry) for entry in entries]


# CrewClaw blog has no native feed: a static grid of /blog/<slug> cards whose
# text is "<Category> <Title> YYYY-MM-DD · N min read <Title again>...".
CREWCLAW_URL = "https://crewclaw.com/blog"
_CC_DATE_RE = re.compile(r"(20\d\d-\d\d-\d\d)")


def scrape_crewclaw(known_links):
    html = get_html(CREWCLAW_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen, entries = set(), []
    for a in soup.select("a[href*='/blog/']"):
        href = a.get("href", "").split("?")[0].split("#")[0]
        # real posts are /blog/<slug>; /blog and /blog/<category> hubs are skipped
        if len([p for p in href.split("/blog/")[-1].split("/") if p]) != 1:
            continue
        text = a.get_text(" ", strip=True)
        m = _CC_DATE_RE.search(text)
        if not m:
            continue
        link = href if href.startswith("http") else "https://crewclaw.com" + href
        if link in seen or link in known_links:
            continue
        # Title is the prose after "min read"; fall back to the card's heading.
        title = ""
        if "min read" in text:
            title = text.split("min read", 1)[1].strip()
        if len(title) < 12:
            h = a.find(["h2", "h3"])
            title = h.get_text(" ", strip=True) if h else title
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 12:
            continue
        seen.add(link)
        entries.append(
            {
                "title": sanitize_xml(title[:200]),
                "link": link,
                "date": parse_date(m.group(1)),
                "description": sanitize_xml(title[:200]),
                "source": "CrewClaw",
            }
        )
    # CrewClaw lists a large SEO archive; keep only the newest so it doesn't
    # swamp the combined feed (undated cards sink to the bottom).
    entries.sort(key=lambda e: (e["date"] is not None, e["date"] or ""), reverse=True)
    return entries[:40]


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="AI-bridge",
        subtitle="Combined AI feed: Thinking Machines, Ollama, Mistral, "
        "Interconnected, AI Clock, Stability AI, Promptowy, Maistry, "
        "Karpathy (bearblog + old blog), Transformer, "
        "Perplexity (blog/changelog/research/API changelog), "
        "The Batch / DeepLearning.AI, and Groq (blog/newsroom/changelog).",
        blog_url="https://thinkingmachines.ai/blog/",
        icon=favicon_proxy("thinkingmachines.ai"),
        author="various",
        sources=SOURCES,
        extra_scrapers=[
            scrape_answer_ai,
            scrape_framer_listings,
            scrape_thebatch,
            scrape_dlai_blog,
            scrape_groq,
            scrape_crewclaw,
        ],
        max_entries=400,
        # Volume here is wildly uneven: CrewClaw is an SEO archive that landed
        # 108 posts in a single month and had taken 214 of the feed's slots,
        # while Interconnected publishes a handful. Quotas keep the content
        # farms from burying the labs.
        per_source_cap=PER_SOURCE_QUOTA,
        # Glama (blog, MCP Servers, release notes) all moved to the skillsllm
        # feed; evict any leftover Glama-sourced cache entries so they don't
        # linger here until they age past the cap.
        cache_filter=lambda e: not str(e.get("source", "")).startswith("Glama"),
        cache_transform=repair_answer_ai_entry,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the AI-bridge Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
