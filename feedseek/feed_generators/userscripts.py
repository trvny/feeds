"""UserScripts feed: one combined Atom stream for the userscript ecosystem.

Native feeds:
  - Greasespot    the Greasemonkey blog (Blogger Atom)
  - Sleazyfork    latest updated scripts (Greasyfork-family .atom)

Scraped (no native feed):
  - Violentmonkey  the /posts/ blog (static Astro: <h2> title + <time>)
  - Tampermonkey   changelog.php (a flat "VERSION / date / changes" text blob)

Sleazyfork sits behind anti-bot filtering; multi_rss's curl_cffi Chrome
impersonation usually gets through, and per-source isolation means a block
there never sinks the run.
"""

import argparse
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml

FEED_NAME = "userscripts"

SOURCES = [
    ("Greasespot", "https://www.greasespot.net/feeds/posts/default", 40),
    ("Sleazyfork", "https://sleazyfork.org/scripts.atom?sort=updated", 40),
]

# Violentmonkey blog: static Astro list of <h2> titles, each with a sibling
# <time> and a /posts/<slug> link.
VM_URL = "https://violentmonkey.github.io/posts/"


def scrape_violentmonkey(known_links):
    html = get_html(VM_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for h2 in soup.find_all("h2"):
        a = h2.find("a", href=True) or h2.find_parent("a", href=True) or h2.find_next("a", href=re.compile(r"/posts/"))
        if not a or "/posts/" not in a.get("href", ""):
            continue
        link = urljoin(VM_URL, a["href"].split("?")[0].split("#")[0])
        if link.rstrip("/") == VM_URL.rstrip("/") or link in known_links:
            continue
        title = h2.get_text(" ", strip=True)
        if not title:
            continue
        time_el = h2.find_next("time")
        date_obj = parse_date(time_el.get_text(strip=True)) if time_el else None
        entries.append({
            "title": sanitize_xml(title[:200]),
            "link": link,
            "date": date_obj,
            "description": sanitize_xml(title[:200]),
            "source": "Violentmonkey",
        })
    return entries


# Tampermonkey changelog.php: no feed and no per-version markup -- a flat text
# blob of "VERSION\nYYYY-MM-DD\n<changes...>" separated by version lines.
TM_URL = "https://www.tampermonkey.net/changelog.php"
_TM_VER_RE = re.compile(r"^\d+\.\d+\.\d+(?:\s*BETA)?$")
_TM_DATE_RE = re.compile(r"^20\d\d-\d\d-\d\d$")


def scrape_tampermonkey(known_links):
    html = get_html(TM_URL)
    if not html:
        return []
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    blocks, cur = [], None
    for line in text.split("\n"):
        line = line.strip()
        if _TM_VER_RE.match(line):
            if cur:
                blocks.append(cur)
            cur = {"ver": line, "date": None, "body": []}
        elif cur is not None:
            if cur["date"] is None and _TM_DATE_RE.match(line):
                cur["date"] = line
            elif line:
                cur["body"].append(line)
    if cur:
        blocks.append(cur)

    entries = []
    for b in blocks:
        link = f"{TM_URL}#v{b['ver'].split()[0]}"
        if link in known_links:
            continue
        body = " ".join(b["body"][:25])
        entries.append({
            "title": sanitize_xml(f"Tampermonkey {b['ver']}"),
            "link": link,
            "date": parse_date(b["date"]) if b["date"] else None,
            "description": sanitize_xml(body[:500]) or f"Tampermonkey {b['ver']}",
            "source": "Tampermonkey",
        })
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="UserScripts",
        subtitle="Combined userscript-ecosystem feed: Greasespot (Greasemonkey "
                 "blog), Sleazyfork (latest updated scripts), the Violentmonkey "
                 "blog, and the Tampermonkey changelog.",
        blog_url="https://www.greasespot.net/",
        author="various",
        sources=SOURCES,
        extra_scrapers=[scrape_violentmonkey, scrape_tampermonkey],
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the UserScripts Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
