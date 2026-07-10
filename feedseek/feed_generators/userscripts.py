"""UserScripts feed: one combined Atom stream for the userscript ecosystem.

Native feeds:
  - Greasespot    the Greasemonkey blog (Blogger Atom)
  - Sleazyfork    latest updated scripts (Greasyfork-family .atom)

Scraped (no native feed):
  - Violentmonkey  the /posts/ blog (static Astro: <h2> title + <time>)
  - Tampermonkey   changelog.php (a flat "VERSION / date / changes" text blob)
  - ScriptCat      newest scripts via the JSON API (sort=createtime) + the
                   VitePress docs changelog (docs.scriptcat.org)

Sleazyfork sits behind anti-bot filtering; multi_rss's curl_cffi Chrome
impersonation usually gets through, and per-source isolation means a block
there never sinks the run.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
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


# ScriptCat (scriptcat.org): no native feed. Two sources:
#  - newest scripts via the JSON API (sort=createtime), one entry per script
#  - the docs changelog: a VitePress page of "<version> (YYYY-MM-DD)" <h2>s
SCRIPTCAT_API = "https://scriptcat.org/api/v2/scripts?sort=createtime"
SCRIPTCAT_CHANGELOG = "https://docs.scriptcat.org/en/docs/change/"
_SC_VER_RE = re.compile(r"(\d+\.\d+\.\d+)\s*\((\d{4}-\d{2}-\d{2})\)")


def scrape_scriptcat_scripts(known_links):
    """Newest ScriptCat scripts via the public JSON API."""
    raw = get_html(SCRIPTCAT_API)
    if not raw:
        return []
    try:
        items = (json.loads(raw).get("data") or {}).get("list") or []
    except (ValueError, AttributeError):
        return []
    entries = []
    for it in items:
        sid = it.get("id")
        name = (it.get("name") or "").strip()
        if not sid or not name:
            continue
        link = f"https://scriptcat.org/script-show-page/{sid}"
        if link in known_links:
            continue
        ct = it.get("createtime") or (it.get("script") or {}).get("createtime")
        date = None
        if ct:
            try:
                date = datetime.fromtimestamp(int(ct), tz=timezone.utc)
            except (ValueError, OSError, OverflowError):
                date = None
        author = (it.get("username") or "").strip()
        title = f"{name} \u2014 {author}" if author else name
        desc = (it.get("description") or name).strip()
        entries.append({
            "title": sanitize_xml(title[:200]),
            "link": link,
            "date": date,
            "description": sanitize_xml(desc[:500]) or name,
            "source": "ScriptCat",
        })
    return entries


def scrape_scriptcat_changelog(known_links):
    """ScriptCat app changelog: VitePress <h2> per version, id like
    ``140-2026-06-26``; sibling h3/li text becomes the summary."""
    html = get_html(SCRIPTCAT_CHANGELOG)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup
    entries = []
    for h2 in root.find_all("h2"):
        text = h2.get_text(" ", strip=True).replace("\u200b", "").strip()
        m = _SC_VER_RE.search(text)
        if not m:
            continue
        ver, dstr = m.group(1), m.group(2)
        anchor = h2.get("id") or f"{ver.replace('.', '')}-{dstr}"
        link = f"{SCRIPTCAT_CHANGELOG}#{anchor}"
        if link in known_links:
            continue
        parts = []
        for sib in h2.find_all_next():
            if sib.name == "h2":
                break
            if sib.name in ("h3", "li"):
                t = sib.get_text(" ", strip=True).replace("\u200b", "").strip()
                if t:
                    parts.append(t)
            if sum(len(p) for p in parts) > 400:
                break
        desc = "; ".join(parts)[:500] or f"ScriptCat {ver}"
        entries.append({
            "title": sanitize_xml(f"ScriptCat {ver} ({dstr})"),
            "link": link,
            "date": parse_date(dstr),
            "description": sanitize_xml(desc),
            "source": "ScriptCat Changelog",
        })
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="UserScripts",
        subtitle="Combined userscript-ecosystem feed: Greasespot (Greasemonkey "
                 "blog), Sleazyfork (latest updated scripts), ScriptCat (newest "
                 "scripts + app changelog), the Violentmonkey blog, and the "
                 "Tampermonkey changelog.",
        blog_url="https://www.greasespot.net/",
        author="various",
        sources=SOURCES,
        extra_scrapers=[
            scrape_violentmonkey,
            scrape_tampermonkey,
            scrape_scriptcat_scripts,
            scrape_scriptcat_changelog,
        ],
        max_entries=200,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the UserScripts Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
