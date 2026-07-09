"""AI-bridge feed: one combined Atom stream of AI labs and newsletters.

Native RSS sources: Thinking Machines, Ollama, Mistral, Interconnected
(Matt Webb), and AI Clock (Substack). On top of those it reuses the existing
scrapers for Perplexity's Framer sites (Blog/Changelog/Research + API docs
changelog RSS) and The Batch / DeepLearning.AI (__NEXT_DATA__) — same parsers,
separate cache, so this feed stands alone even though the sources overlap with
feed_perplexity.xml and feed_thebatch.xml. Groq (blog/newsroom/changelog +
groq-changelog commits) is folded in the same way via groq.scrape_all.
"""

import argparse
import sys

import re

from bs4 import BeautifulSoup

from groq import scrape_all as scrape_groq
from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, stable_fallback_date
from perplexity import RSS_SOURCES as PERPLEXITY_RSS
from perplexity import scrape_framer_listings
from thebatch import scrape_blog as scrape_dlai_blog
from thebatch import scrape_thebatch

FEED_NAME = "aibridge"

SOURCES = [
    ("Thinking Machines", "https://thinkingmachines.ai/blog/index.xml", 40),
    ("Ollama", "https://ollama.com/blog/rss.xml", 40),
    ("Mistral", "https://mistral.ai/rss.xml", 40),
    ("Interconnected", "https://interconnected.org/home/feed", 40),
    ("AI Clock", "https://aiclock.substack.com/feed", 40),
    ("Glama", "https://glama.ai/blog/rss.xml", 40),
    ("Answer.AI", "https://www.answer.ai/index.xml", 40),
] + list(PERPLEXITY_RSS)


# CrewClaw blog has no native feed: a static grid of /blog/<slug> cards whose
# text is "<Category> <Title> YYYY-MM-DD \u00b7 N min read <Title again>...".
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
        entries.append({
            "title": sanitize_xml(title[:200]),
            "link": link,
            "date": parse_date(m.group(1)),
            "description": sanitize_xml(title[:200]),
            "source": "CrewClaw",
        })
    # CrewClaw lists a large SEO archive; keep only the newest so it doesn't
    # swamp the combined feed (undated cards sink to the bottom).
    entries.sort(key=lambda e: (e["date"] is not None, e["date"] or ""), reverse=True)
    return entries[:40]


# Glama's blog is covered above via its native RSS (glama.ai/blog/rss.xml). The
# separate /release-notes page has no feed: each item is an <article> with an
# <h2> title, an Improvement/Feature/Fix/Announcement badge, a "Mon D, YYYY"
# date, and a body. Items have no per-entry permalink, so a stable
# "#<date>-<title-slug>" fragment is synthesised as the dedup id.
GLAMA_RELEASE_NOTES_URL = "https://glama.ai/release-notes"
_GLAMA_RN_DATE_RE = re.compile(r"\b([A-Z][a-z]{2,9} \d{1,2}, \d{4})\b")
_GLAMA_RN_TYPE_RE = re.compile(r"^(Improvement|Feature|Fix|Announcement)\b")


def _glama_slugify(text, max_len=80):
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", text)[:max_len] or "item"


def scrape_glama_release_notes(known_links):
    html = get_html(GLAMA_RELEASE_NOTES_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    seen, entries = set(), []
    for art in soup.find_all("article"):
        try:
            heading = art.find(["h1", "h2", "h3"])
            if not heading:
                continue
            title = sanitize_xml(heading.get_text(" ", strip=True))
            if not title:
                continue
            full = art.get_text(" ", strip=True)
            date_match = _GLAMA_RN_DATE_RE.search(full)
            date = parse_date(date_match.group(1)) if date_match else None
            tail = full[len(title):].strip()
            type_match = _GLAMA_RN_TYPE_RE.search(tail)
            rtype = type_match.group(1) if type_match else None
            body = full[date_match.end():].strip(" .|") if date_match else ""
            description = (f"[{rtype}] " if rtype else "") + (body[:300] if body else title)
            date_slug = date.strftime("%Y-%m-%d") if date else "nodate"
            link = f"{GLAMA_RELEASE_NOTES_URL}#{date_slug}-{_glama_slugify(title)}"
            if link in seen or link in known_links:
                continue
            seen.add(link)
            entries.append({
                "title": title,
                "link": link,
                "date": date or stable_fallback_date(link),
                "description": sanitize_xml(description),
                "source": "Glama Release Notes",
            })
        except Exception:  # one bad item never kills the feed
            continue
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="AI-bridge",
        subtitle="Combined AI feed: Thinking Machines, Ollama, Mistral, "
                 "Interconnected, AI Clock, Perplexity (blog/changelog/research/"
                 "API changelog), The Batch / DeepLearning.AI, and Groq "
                 "(blog/newsroom/changelog).",
        blog_url="https://thinkingmachines.ai/blog/",
        author="various",
        sources=SOURCES,
        extra_scrapers=[scrape_framer_listings, scrape_thebatch, scrape_dlai_blog, scrape_groq, scrape_crewclaw, scrape_glama_release_notes],
        max_entries=400,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the AI-bridge Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
