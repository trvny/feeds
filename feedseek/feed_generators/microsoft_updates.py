"""Microsoft Updates feed (successor to windows11_release_notes).

One combined Atom feed of Microsoft's update/release-note streams:

    - Windows 11 update history (all versions) (support.microsoft.com KB list)
    - Windows 10 update history               (support.microsoft.com KB list)
    - Windows message center                  (learn.microsoft.com table)
    - Office Current Channel release notes    (via RSS-Bridge Atom)
    - Outlook for Windows (new) release notes (learn.microsoft.com)
    - Outlook Mobile release notes            (learn.microsoft.com)
    - Office Deployment Tool release history  (learn.microsoft.com)
    - Microsoft 365 Copilot release notes     (learn.microsoft.com)

Parsing notes:
  * Support update-history pages render every KB as a left-nav link whose
    title starts with the release date and contains "KB"/"OS Build"; intake is
    capped per page (Windows 10 alone lists hundreds) — the cache accumulates.
  * Learn release-note pages use ``<h2 id="june-5-2026">`` headings; the id is
    an English date, so dates are parsed from the id and the id doubles as a
    stable anchor. The pages are fetched from their ``en-us`` URLs so heading
    and body text stay English (Learn otherwise geolocates to Polish).
  * The message center is a table of (message, date) rows, kept from the old
    generator.
  * Office Current Channel comes from RSS-Bridge, which ships its version rows
    with NO per-entry date; the release date is recovered from each title
    ("Version 2606: June 25") so the rows sort correctly instead of clumping
    at the run time.
"""

import argparse
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run, scrape_feed
from utils import sanitize_xml, setup_logging, stable_fallback_date

logger = setup_logging()

FEED_NAME = "microsoft_updates"
BLOG_URL = "https://support.microsoft.com/en-us/windows"

SUPPORT_BASE = "https://support.microsoft.com"

# (label, resolved support.microsoft.com update-history URL)
# The Windows 11 left-nav lists every Win 11 KB regardless of which version
# topic is open (the 25H2 and 26H1 pages serve identical KB link sets), so one
# source covers all current Windows 11 versions.
UPDATE_HISTORY_SOURCES = [
    ("Windows 11 updates",
     "https://support.microsoft.com/en-us/topic/"
     "windows-11-version-26h1-update-history-253c73cd-cab1-4bfd-94dc-76c452273fc9"),
    ("Windows 10 updates",
     "https://support.microsoft.com/en-us/topic/"
     "windows-10-update-history-8127c2c6-6edf-4fdf-8b9f-0f7be1ef3562"),
]
HISTORY_INTAKE_CAP = 60   # newest KB entries per page per run; cache keeps the rest

MESSAGE_CENTER_URL = "https://learn.microsoft.com/en-us/windows/release-health/windows-message-center"

# (label, learn.microsoft.com page with <h2 id="<english-date>"> sections)
# en-us so headings and body render in English -- learn.microsoft.com otherwise
# geolocates to Polish, which left Copilot entries (title + description) in
# Polish even though the date is read from the always-English anchor id.
LEARN_DATED_SOURCES = [
    ("Outlook (new) release notes",
     "https://learn.microsoft.com/en-us/officeupdates/release-notes-outlook-new"),
    ("Outlook Mobile release notes",
     "https://learn.microsoft.com/en-us/officeupdates/release-notes-outlook-mobile"),
    ("Office Deployment Tool releases",
     "https://learn.microsoft.com/en-us/officeupdates/odt-release-history"),
    ("Microsoft 365 Copilot release notes",
     "https://learn.microsoft.com/en-us/microsoft-365/copilot/release-notes?tabs=all"),
]

# The RSS-Bridge Office feed emits its version rows with NO per-entry dates, so
# feedgen would stamp every one with the run time and clump 100+ build rows at
# the top of the feed. The release date is in the title ("Version 2606: June
# 25"), so we scrape it ourselves and parse the date out instead.
OFFICE_CC_URL = (
    "https://rss-bridge.org/bridge01/?action=display"
    "&bridge=MicrosoftOfficeUpdatesBridge&channel=current-channel&format=Atom"
)
OFFICE_CC_CAP = 50

_OFFICE_VER_RE = re.compile(
    r"Version\s+(\d{2})(\d{2}):\s*"
    r"(January|February|March|April|May|June|July|August|September|October"
    r"|November|December)\s+(\d{1,2})",
    re.IGNORECASE,
)
_MONTHS = {
    m.lower(): i for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], 1)
}

_HISTORY_DATE_RE = re.compile(
    r"^((?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s+\d{4})"
)
_MC_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?")
_H2_DATE_ID_RE = re.compile(
    r"^(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"-(\d{1,2})-(\d{4})$"
)


# --------------------------------------------------------------------------- #
# support.microsoft.com update histories (KB / OS Build left-nav links)
# --------------------------------------------------------------------------- #


def _scrape_update_history(label, url, known_links):
    entries = []
    html = get_html(url)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")

    links = soup.select("a.supLeftNavLink, .supLeftNavArticle a, a[href*='/help/']")
    count, seen = 0, set()
    for link in links:
        if count >= HISTORY_INTAKE_CAP:
            break
        try:
            title = link.get_text(" ", strip=True)
            href = link.get("href", "")
            if not title or "KB" not in title or "OS Build" not in title or "/help/" not in href:
                continue
            full_link = href if href.startswith("http") else SUPPORT_BASE + href
            if full_link in seen:
                continue
            seen.add(full_link)
            count += 1
            if full_link in known_links:
                continue
            m = _HISTORY_DATE_RE.match(title)
            date_obj = parse_date(m.group(1)) if m else stable_fallback_date(full_link)
            entries.append({
                "title": sanitize_xml(title),
                "link": full_link,
                "date": date_obj,
                "description": sanitize_xml(f"{label.rsplit(' ', 1)[0]} update: {title}"),
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping entry: {e}")
    if not count:
        logger.warning(f"  [{label}] no KB entries matched — layout may have changed")
    return entries


def scrape_update_histories(known_links):
    entries = []
    for label, url in UPDATE_HISTORY_SOURCES:
        logger.info(f"Scraping {label} ...")
        entries += _scrape_update_history(label, url, known_links)
    return entries


# --------------------------------------------------------------------------- #
# Windows message center (learn.microsoft.com table)
# --------------------------------------------------------------------------- #


def scrape_message_center(known_links):
    label = "Windows message center"
    entries = []
    html = get_html(MESSAGE_CENTER_URL)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")
    if not table:
        logger.warning(f"  [{label}] no table found — layout may have changed")
        return entries

    seen = set()
    for row in table.find_all("tr"):
        try:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            msg_cell, date_cell = cells[0], cells[1]
            anchor = msg_cell.find("a")
            title_el = msg_cell.find("b") or anchor
            title = (title_el or msg_cell).get_text(" ", strip=True)
            if not title:
                continue
            body_el = msg_cell.find("div")
            description = body_el.get_text(" ", strip=True) if body_el else title

            href = anchor.get("href", "") if anchor else ""
            if href and not href.startswith("http"):
                href = "https://learn.microsoft.com" + href
            if not href:
                row_id = msg_cell.get("id")
                href = f"{MESSAGE_CENTER_URL}#{row_id}" if row_id else MESSAGE_CENTER_URL
            if href in seen:
                continue
            seen.add(href)
            if href in known_links:
                continue

            m = _MC_DATE_RE.search(date_cell.get_text(" ", strip=True))
            date_obj = (
                parse_date(f"{m.group(1)} {m.group(2) or '00:00'}") if m
                else stable_fallback_date(href)
            )
            entries.append({
                "title": sanitize_xml(title),
                "link": href,
                "date": date_obj,
                "description": sanitize_xml(description)[:500],
                "source": label,
            })
            logger.info(f"  [{label}] {title}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping row: {e}")
    return entries


# --------------------------------------------------------------------------- #
# learn.microsoft.com dated-h2 release notes (Outlook/ODT/Copilot)
# --------------------------------------------------------------------------- #


def _scrape_learn_dated(label, url, known_links):
    entries = []
    html = get_html(url)
    if html is None:
        return entries
    soup = BeautifulSoup(html, "html.parser")
    page_base = url.split("?")[0]

    headings = [h for h in soup.find_all("h2", id=True) if _H2_DATE_ID_RE.match(h["id"])]
    if not headings:
        logger.warning(f"  [{label}] no dated headings matched — layout may have changed")
        return entries

    for h in headings:
        try:
            anchor = h["id"]
            link = f"{page_base}#{anchor}"
            if link in known_links:
                continue
            date_obj = parse_date(anchor.replace("-", " "))
            heading_text = h.get_text(" ", strip=True)
            title = sanitize_xml(f"{label}: {heading_text}")
            parts = []
            for el in h.next_elements:
                if getattr(el, "name", None) == "h2" and el is not h:
                    break
                if getattr(el, "name", None) in ("h3", "p", "li"):
                    parts.append(el.get_text(" ", strip=True))
            desc = re.sub(r"\s+", " ", " ".join(parts)).strip()[:500]
            entries.append({
                "title": title,
                "link": link,
                "date": date_obj,
                "description": sanitize_xml(desc) or title,
                "source": label,
            })
            logger.info(f"  [{label}] {heading_text}")
        except Exception as e:
            logger.warning(f"  [{label}] skipping section: {e}")
    return entries


def scrape_learn_pages(known_links):
    entries = []
    for label, url in LEARN_DATED_SOURCES:
        logger.info(f"Scraping {label} ...")
        entries += _scrape_learn_dated(label, url, known_links)
    return entries


# --------------------------------------------------------------------------- #
# Office Current Channel (RSS-Bridge; date recovered from the title)
# --------------------------------------------------------------------------- #


def _office_version_date(title):
    """Parse the release date out of an Office build title.

    "Version 2606: June 25" -> 2026-06-25. The ``YYMM`` prefix gives the year;
    a Nov/Dec version line serviced in Jan/Feb belongs to the following year.
    """
    m = _OFFICE_VER_RE.search(title or "")
    if not m:
        return None
    yy, vmm, month_name, day = m.groups()
    year = 2000 + int(yy)
    month = _MONTHS[month_name.lower()]
    if int(vmm) >= 11 and month <= 2:
        year += 1
    try:
        return datetime(year, month, int(day), tzinfo=timezone.utc)
    except ValueError:
        return None


def scrape_office_current_channel(known_links):
    """Office Current Channel release notes via RSS-Bridge, with the per-entry
    date recovered from each title (the bridge ships none)."""
    label = "Office Current Channel"
    logger.info(f"Scraping {label} ...")
    entries = scrape_feed(label, OFFICE_CC_URL, known_links, cap=OFFICE_CC_CAP)
    for e in entries:
        e["date"] = _office_version_date(e["title"]) or stable_fallback_date(e["link"])
    return entries


# One-time self-heal: the Learn pages were briefly fetched from pl-pl URLs, so
# some cached entries (notably Copilot) kept Polish titles/descriptions. Drop
# any Polish-dated cached entry on load; the en-us scrape re-adds it in English.
_PL_MONTHS = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
              "lipca", "sierpnia", "wrze\u015bnia", "pa\u017adziernika",
              "listopada", "grudnia")


def _not_polish(entry):
    return not any(m in entry.get("title", "") for m in _PL_MONTHS)


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Microsoft Updates",
        subtitle="Windows 11/10 update histories, the Windows message center, "
                 "Office Current Channel, Outlook (new/Mobile), Office Deployment "
                 "Tool, and Microsoft 365 Copilot release notes.",
        blog_url=BLOG_URL,
        author="Microsoft",
        extra_scrapers=[
            scrape_update_histories,
            scrape_message_center,
            scrape_learn_pages,
            scrape_office_current_channel,
        ],
        max_entries=300,
        full=full,
        cache_filter=_not_polish,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Microsoft Updates Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
