"""Combined Palantir feed for company news, blog posts, and Foundry updates."""

import argparse
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from multi_rss import get_html, parse_date, run
from utils import favicon_proxy, sanitize_xml, setup_logging

logger = setup_logging()

FEED_NAME = "palantir"
BASE_URL = "https://www.palantir.com"
NEWSROOM_URL = f"{BASE_URL}/newsroom/"
BLOG_URL = f"{BASE_URL}/blog/"
MEDIA_URL = f"{BASE_URL}/newsroom/media/"
PRESS_URL = f"{BASE_URL}/newsroom/press-releases/"
ANNOUNCEMENTS_URL = f"{BASE_URL}/docs/foundry/announcements"
RELEASE_NOTES_URL = f"{BASE_URL}/docs/foundry/release-notes"

DATE_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},\s+20\d{2}\b",
    re.I,
)
ISO_DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
INDEX_PATHS = {
    "/blog/",
    "/newsroom/",
    "/newsroom/letters/",
    "/newsroom/media/",
    "/newsroom/press-releases/",
    "/newsroom/thought-leadership/",
}
LISTING_CAP = 40


def _meta(soup, *keys):
    for key in keys:
        tag = soup.find("meta", property=key) or soup.find(
            "meta", attrs={"name": key}
        )
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _clean_title(value):
    title = sanitize_xml((value or "").strip())
    return re.sub(
        r"\s+[|–—-]\s+Palantir(?: Technologies)?\s*$",
        "",
        title,
    ).strip()


def _slug(value):
    text = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return text[:80] or "update"


def _date_from_text(text):
    match = ISO_DATE_RE.search(text or "") or DATE_RE.search(text or "")
    return parse_date(match.group(0)) if match else None


def _scope_date(scope):
    if scope is None:
        return None
    time_el = scope.find("time", datetime=True)
    if time_el:
        parsed = parse_date(time_el.get("datetime"))
        if parsed:
            return parsed
    return _date_from_text(scope.get_text(" ", strip=True))


def _article_meta(url, fallback_title="", fallback_date=None):
    html = get_html(url)
    if not html:
        return {
            "title": fallback_title,
            "description": fallback_title,
            "date": fallback_date,
            "image": None,
        }

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = _clean_title(
        _meta(soup, "og:title", "twitter:title")
        or (h1.get_text(" ", strip=True) if h1 else fallback_title)
    )
    description = sanitize_xml(
        _meta(soup, "og:description", "description") or title
    )[:500]
    date_value = _meta(
        soup,
        "article:published_time",
        "datePublished",
        "date",
    )
    date = parse_date(date_value) if date_value else None
    return {
        "title": title or fallback_title,
        "description": description or title or fallback_title,
        "date": date or _scope_date(soup) or fallback_date,
        "image": _meta(soup, "og:image", "twitter:image"),
    }


def _listing_link(href, *, internal_prefix=None, allow_external=False):
    link = urljoin(BASE_URL, (href or "").strip())
    parsed = urlparse(link)
    if parsed.scheme not in {"http", "https"}:
        return None

    is_palantir = parsed.netloc in {"palantir.com", "www.palantir.com"}
    if allow_external and not is_palantir:
        return link.split("#", 1)[0]
    if not is_palantir:
        return None

    path = parsed.path.rstrip("/") + "/"
    if path in INDEX_PATHS:
        return None
    if internal_prefix and not path.startswith(internal_prefix):
        return None
    return f"{BASE_URL}{path}"


def scrape_listing(
    label,
    url,
    known_links,
    seen,
    *,
    internal_prefix=None,
    allow_external=False,
    fetch_article=True,
):
    """Parse cards from one Palantir listing page."""
    html = get_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    entries = []
    for heading in soup.find_all(["h2", "h3", "h4"]):
        try:
            anchor = heading.find("a", href=True) or heading.find_parent(
                "a", href=True
            )
            if not anchor:
                continue
            link = _listing_link(
                anchor.get("href"),
                internal_prefix=internal_prefix,
                allow_external=allow_external,
            )
            if not link or link in known_links or link in seen:
                continue

            title = _clean_title(heading.get_text(" ", strip=True))
            if len(title) < 8:
                continue

            scope = heading.find_parent(["article", "li", "section", "div"])
            date = _scope_date(scope or heading)
            description = ""
            image = None
            if scope:
                paragraph = scope.find("p")
                if paragraph:
                    description = sanitize_xml(
                        paragraph.get_text(" ", strip=True)
                    )[:500]
                image_el = scope.find("img")
                if image_el:
                    image_src = (
                        image_el.get("src")
                        or image_el.get("data-src")
                        or image_el.get("data-image")
                    )
                    if image_src:
                        image = urljoin(BASE_URL, image_src)

            if fetch_article and urlparse(link).netloc.endswith("palantir.com"):
                meta = _article_meta(
                    link,
                    fallback_title=title,
                    fallback_date=date,
                )
                title = meta["title"] or title
                description = meta["description"] or description or title
                date = meta["date"] or date
                image = meta["image"] or image
            else:
                date = date or datetime.now(timezone.utc)
                description = description or title

            seen.add(link)
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date,
                    "description": description,
                    "source": label,
                    "image": image,
                }
            )
            if len(entries) >= LISTING_CAP:
                break
        except Exception as exc:
            logger.warning("  [%s] skipping card: %s", label, exc)
    return entries


def scrape_corporate(known_links):
    """Collect all corporate listing pages while sharing one dedupe set."""
    entries = []
    seen = set()
    listings = (
        ("Newsroom", NEWSROOM_URL, "/newsroom/", False, True),
        ("Blog", BLOG_URL, "/blog/", False, True),
        ("Media Coverage", MEDIA_URL, None, True, False),
        (
            "Press Releases",
            PRESS_URL,
            "/newsroom/press-releases/",
            False,
            True,
        ),
    )
    for label, url, prefix, allow_external, fetch_article in listings:
        entries += scrape_listing(
            label,
            url,
            known_links,
            seen,
            internal_prefix=prefix,
            allow_external=allow_external,
            fetch_article=fetch_article,
        )
    return entries


def _section_text(heading, limit=500):
    parts = []
    for node in heading.find_all_next():
        if node is heading:
            continue
        if node.name == "h2":
            break
        if node.name not in {"p", "li", "h3", "h4"}:
            continue
        text = node.get_text(" ", strip=True)
        if text:
            parts.append(text)
        if len(" ".join(parts)) >= limit:
            break
    return " ".join(parts)[:limit]


def scrape_announcements(known_links):
    """Split the current Foundry announcements page into dated entries."""
    html = get_html(ANNOUNCEMENTS_URL)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    entries = []
    seen = set()
    for heading in soup.find_all("h2"):
        try:
            title = _clean_title(heading.get_text(" ", strip=True))
            if not title or title.lower() in {"announcements", "contents"}:
                continue

            section = _section_text(heading, limit=700)
            date = _date_from_text(section)
            if date is None:
                continue
            link = (
                f"{ANNOUNCEMENTS_URL}#"
                f"{date.date().isoformat()}-{_slug(title)}"
            )
            if link in known_links or link in seen:
                continue

            description = re.sub(
                r"^Date published:\s*(?:20\d{2}-\d{2}-\d{2}|"
                + DATE_RE.pattern
                + r")\s*",
                "",
                section,
                flags=re.I,
            )
            seen.add(link)
            entries.append(
                {
                    "title": title,
                    "link": link,
                    "date": date,
                    "description": sanitize_xml(description[:500] or title),
                    "source": "Foundry Announcements",
                }
            )
        except Exception as exc:
            logger.warning("  [Foundry Announcements] skipping entry: %s", exc)
    return entries


def scrape_release_notes(known_links):
    """Create one entry per dated release-note section."""
    html = get_html(RELEASE_NOTES_URL)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    entries = []
    seen = set()
    for heading in soup.find_all("h2"):
        try:
            heading_text = heading.get_text(" ", strip=True)
            date = _date_from_text(heading_text)
            if date is None or not (
                ISO_DATE_RE.fullmatch(heading_text)
                or DATE_RE.fullmatch(heading_text)
            ):
                continue
            link = f"{RELEASE_NOTES_URL}#{date.date().isoformat()}"
            if link in known_links or link in seen:
                continue

            seen.add(link)
            description = sanitize_xml(_section_text(heading))
            entries.append(
                {
                    "title": f"Foundry release notes — {heading_text}",
                    "link": link,
                    "date": date,
                    "description": description or heading_text,
                    "source": "Foundry Release Notes",
                }
            )
        except Exception as exc:
            logger.warning("  [Foundry Release Notes] skipping entry: %s", exc)
    return entries


def main(full=False):
    return run(
        feed_name=FEED_NAME,
        title="Palantir",
        subtitle=(
            "Palantir newsroom, blog, media coverage, press releases, "
            "Foundry announcements, and release notes."
        ),
        blog_url=NEWSROOM_URL,
        icon=favicon_proxy("palantir.com"),
        author="Palantir",
        extra_scrapers=(
            scrape_corporate,
            scrape_announcements,
            scrape_release_notes,
        ),
        max_entries=300,
        per_source_cap=50,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Palantir Atom feed")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Ignore cache and rebuild from scratch",
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
