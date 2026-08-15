#!/usr/bin/env python3

import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "feed_generators"))

from multi_rss import get_html, scrape_feed  # noqa: E402

FEEDS = [
    ("Rust Blog", "https://blog.rust-lang.org/feed.xml", 20),
    ("Inside Rust", "https://blog.rust-lang.org/inside-rust/feed.xml", 20),
    ("TestDriven.io", "https://testdriven.io/feed.xml", 20),
    ("Django Weblog", "https://www.djangoproject.com/rss/weblog/", 20),
    ("Django News", "https://django-news.com/rss", 20),
    ("Django Community", "https://www.djangoproject.com/rss/community/blogs/", 20),
    ("Django Packages latest", "https://djangopackages.org/feeds/packages/latest/atom/", 3),
]

PAGES = [
    ("Rust releases", "https://blog.rust-lang.org/releases/"),
    ("Django Packages changelog", "https://djangopackages.org/changelog/"),
]


def main():
    failed = False
    print("== native feeds ==")
    for label, url, cap in FEEDS:
        entries = scrape_feed(label, url, set(), cap=cap)
        print(f"{label}: {len(entries)} entries")
        for entry in entries[:3]:
            print("  ", entry["date"], entry["title"], entry["link"])
        if not entries:
            failed = True

    print("\n== html pages ==")
    for label, url in PAGES:
        html = get_html(url)
        print(f"{label}: {'OK' if html else 'FAILED'} len={len(html or '')}")
        if not html:
            failed = True
            continue
        soup = BeautifulSoup(html, "html.parser")
        if label == "Rust releases":
            matches = [
                a
                for a in soup.find_all("a", href=True)
                if a.get_text(" ", strip=True).startswith("Announcing Rust")
            ]
        else:
            matches = [
                h.find("a", href=True)
                for h in soup.find_all("h2")
                if h.find("a", href=True)
            ]
        print(f"  candidate links: {len(matches)}")
        for node in matches[:3]:
            print("  LINK", node.get_text(" ", strip=True), node.get("href"))
            container = node.parent.parent if label == "Django Packages changelog" else node.parent
            print(container.prettify()[:3000].replace("\n", " "))

    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
