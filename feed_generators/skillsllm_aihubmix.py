"""AIHubMix blog adapter for the SkillsLLM aggregate."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

AIHUBMIX_BLOG_URL = "https://aihubmix.com/blog/pl"
AIHUBMIX_BLOG_MAX = 40
AIHUBMIX_SOURCE = {
    "label": "AIHubMix Blog (PL)",
    "title_suffixes": (" | AIHubMix Blog", " | AIHubMix"),
    "category": lambda _loc: "aihubmix",
}


def discover_aihubmix_links(html: str) -> list[str]:
    """Return unique Polish AIHubMix article URLs from the blog listing."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].split("#", 1)[0].split("?", 1)[0]
        link = urljoin(AIHUBMIX_BLOG_URL + "/", href).rstrip("/")
        if not link.startswith(AIHUBMIX_BLOG_URL + "/"):
            continue
        if "/tag/" in link or link in seen:
            continue
        seen.add(link)
        links.append(link)
    return links[:AIHUBMIX_BLOG_MAX]


def collect_aihubmix_blog(known_links, ledger, fetch_url, fetch_detail):
    """Discover AIHubMix PL posts and reuse SkillsLLM's detail normalizer."""
    html = fetch_url(AIHUBMIX_BLOG_URL)
    if html is None:
        return []
    links = discover_aihubmix_links(html)
    if not links:
        return []

    label = AIHUBMIX_SOURCE["label"]
    ledger.listed(label)
    entries = []
    for link in links:
        if link in known_links or ledger.exhausted(label, link):
            continue
        try:
            entry = fetch_detail(link, None, AIHUBMIX_SOURCE)
            if entry:
                entries.append(entry)
            else:
                ledger.failed(label, link)
        except Exception:
            ledger.failed(label, link)
    return entries
