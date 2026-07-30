"""Dwutygodnik culture magazine feed with direct and indexed fallbacks."""

import argparse
import re
import sys
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "dwutygodnik"
BASE_URL = "https://www.dwutygodnik.com/"
SITEMAP_URL = urljoin(BASE_URL, "sitemap.xml")
GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?"
    "q=when:30d+site:dwutygodnik.com+-site:stypendiawarszawy.dwutygodnik.com"
    "&hl=pl&gl=PL&ceid=PL:pl"
)
MAX_DISCOVERED = 60

ARTICLE_PATH_RE = re.compile(r"^/(artykul|wiersz)/(\d+)-[^/?#]+[.]html$")
NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](20\d{2})\b")
POLISH_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+"
    r"(stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|"
    r"września|października|listopada|grudnia)\s+(20\d{2})\b",
    re.I,
)
POLISH_MONTHS = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "października": 10,
    "listopada": 11,
    "grudnia": 12,
}
SECTIONS = {
    "film",
    "literatura",
    "media",
    "muzyka",
    "obyczaje",
    "poezja",
    "sztuka",
    "teatr",
}
GENERIC_TITLES = {"czytaj", "czytaj więcej", "więcej", "dwutygodnik"}


def _article_link(href):
    link = urljoin(BASE_URL, (href or "").strip()).split("#", 1)[0]
    parsed = urlparse(link)
    if parsed.hostname not in {"dwutygodnik.com", "www.dwutygodnik.com"}:
        return None
    if not ARTICLE_PATH_RE.fullmatch(parsed.path):
        return None
    return f"https://www.dwutygodnik.com{parsed.path}"


def _date_from_text(text):
    value = text or ""
    numeric = NUMERIC_DATE_RE.search(value)
    if numeric:
        return parse_date(f"{numeric.group(3)}-{int(numeric.group(2)):02d}-{int(numeric.group(1)):02d}")
    polish = POLISH_DATE_RE.search(value)
    if polish:
        month = POLISH_MONTHS[polish.group(2).lower()]
        return parse_date(f"{polish.group(3)}-{month:02d}-{int(polish.group(1)):02d}")
    return None


def _scope_date(scope):
    if scope is None:
        return None
    time_el = scope.find("time")
    if time_el:
        raw = time_el.get("datetime") or time_el.get_text(" ", strip=True)
        parsed = parse_date(raw) or _date_from_text(raw)
        if parsed:
            return parsed
    date_el = scope.find(attrs={"itemprop": re.compile(r"datePublished", re.I)})
    if date_el:
        raw = date_el.get("content") or date_el.get_text(" ", strip=True)
        parsed = parse_date(raw) or _date_from_text(raw)
        if parsed:
            return parsed
    return _date_from_text(scope.get_text(" ", strip=True))


def _title(anchor, scope):
    candidates = [
        anchor.find(["h1", "h2", "h3", "h4"]),
        anchor.find_parent(["h1", "h2", "h3", "h4"]),
        scope.find(["h1", "h2", "h3", "h4"]) if scope else None,
    ]
    values = [
        candidate.get_text(" ", strip=True) for candidate in candidates if candidate
    ]
    values += [anchor.get("title", ""), anchor.get_text(" ", strip=True)]
    for value in values:
        cleaned = sanitize_xml(re.sub(r"\s+", " ", value or "").strip())
        if len(cleaned) >= 6 and cleaned.lower() not in GENERIC_TITLES:
            return cleaned[:240]
    return ""


def _source(link, scope):
    if urlparse(link).path.startswith("/wiersz/"):
        return "Dwutygodnik / Poezja"
    if scope:
        for anchor in scope.select("a[href]"):
            label = anchor.get_text(" ", strip=True).lower()
            if label in SECTIONS:
                return f"Dwutygodnik / {label.capitalize()}"
    return "Dwutygodnik"


def _image(scope):
    image = scope.find("img") if scope else None
    if not image:
        return None
    value = image.get("src") or image.get("data-src")
    if not value and image.get("srcset"):
        value = image["srcset"].split(",", 1)[0].strip().split(" ", 1)[0]
    return urljoin(BASE_URL, value) if value else None


def parse_listing(html, known_links=()):
    """Extract current article cards without relying on CSS class names."""
    soup = BeautifulSoup(html or "", "html.parser")
    entries = []
    seen = set(known_links)
    for anchor in soup.select("a[href]"):
        try:
            link = _article_link(anchor.get("href"))
            if not link or link in seen:
                continue
            scope = anchor.find_parent(["article", "li"]) or anchor.find_parent("div")
            title = _title(anchor, scope)
            if not title:
                continue
            paragraph = scope.find("p") if scope else None
            description = (
                sanitize_xml(paragraph.get_text(" ", strip=True))[:500]
                if paragraph
                else title
            )
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": _scope_date(scope or anchor),
                    "description": description or title,
                    "source": _source(link, scope),
                    "image": _image(scope),
                }
            )
            seen.add(link)
            if len(entries) >= MAX_DISCOVERED:
                break
        except Exception as exc:
            logger.warning("Skipping malformed Dwutygodnik card: %s", exc)
    return entries


def _slug_title(link):
    slug = urlparse(link).path.rsplit("/", 1)[-1].removesuffix(".html")
    slug = re.sub(r"^\d+-", "", unquote(slug))
    return sanitize_xml(slug.replace("-", " ").strip().capitalize())


def parse_sitemap(xml, known_links=()):
    """Use sitemap last-modified dates when the homepage is rate-limited."""
    soup = BeautifulSoup(xml or "", "xml")
    entries = []
    seen = set(known_links)
    for row in soup.find_all("url"):
        loc = row.find("loc")
        link = _article_link(loc.get_text(strip=True) if loc else "")
        if not link or link in seen:
            continue
        lastmod = row.find("lastmod")
        date = parse_date(lastmod.get_text(strip=True)) if lastmod else None
        title = _slug_title(link)
        entries.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "description": title,
                "source": _source(link, None),
                "image": None,
            }
        )
        seen.add(link)
    entries.sort(key=lambda item: item["date"] or parse_date("1970-01-01"), reverse=True)
    return entries[:MAX_DISCOVERED]


def parse_google_news(xml, known_links=()):
    """Last-resort recent index for periods when the origin returns HTTP 429."""
    soup = BeautifulSoup(xml or "", "xml")
    entries = []
    seen = set(known_links)
    for item in soup.find_all("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        if not title_el or not link_el:
            continue
        title = sanitize_xml(title_el.get_text(" ", strip=True))
        title = re.sub(r"\s+-\s+Dwutygodnik(?:[.]com)?$", "", title, flags=re.I)
        link = link_el.get_text(strip=True)
        description_el = item.find("description")
        description_html = description_el.decode_contents() if description_el else ""
        description_soup = BeautifulSoup(description_html, "html.parser")
        for anchor in description_soup.select("a[href]"):
            direct = _article_link(anchor.get("href"))
            if direct:
                link = direct
                break
        if not title or not link or link in seen:
            continue
        pub_date = item.find("pubDate")
        description = sanitize_xml(description_soup.get_text(" ", strip=True))[:500]
        entries.append(
            {
                "title": title,
                "link": link,
                "date": parse_date(pub_date.get_text(strip=True)) if pub_date else None,
                "description": description or title,
                "source": _source(link, None) if _article_link(link) else "Dwutygodnik",
                "image": None,
            }
        )
        seen.add(link)
    return entries[:MAX_DISCOVERED]


def scrape_dwutygodnik(known_links):
    homepage = get_html(BASE_URL)
    entries = parse_listing(homepage, known_links) if homepage else []

    if len(entries) < 20:
        sitemap = get_html(SITEMAP_URL)
        if sitemap:
            entries += parse_sitemap(
                sitemap,
                set(known_links) | {entry["link"] for entry in entries},
            )

    if not entries:
        indexed = get_html(GOOGLE_NEWS_URL)
        if indexed:
            entries = parse_google_news(indexed, known_links)

    logger.info("Dwutygodnik: collected %d entries", len(entries))
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Dwutygodnik",
        subtitle="Teksty magazynu kulturalnego Dwutygodnik.",
        blog_url=BASE_URL,
        author="Dwutygodnik",
        extra_scrapers=(scrape_dwutygodnik,),
        max_entries=200,
        per_source_cap=80,
        language="pl",
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Dwutygodnik Atom feed")
    parser.add_argument("--full", action="store_true", help="Ignore cache and rebuild from scratch")
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
