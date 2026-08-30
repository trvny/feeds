"""Combined AWS announcements, blogs, re:Post articles, and AWS CLI releases."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

import multi_rss
from bs4 import BeautifulSoup
from utils import sanitize_xml

FEED_NAME = "aws"
FEED_TITLE = "AWS"
BLOG_URL = "https://aws.amazon.com/blogs/"
MAX_ENTRIES = 400
MAX_REPOST_PAGES = 8
REPOST_CURSOR_KEY = "repost_cursor"
REPOST_FRESH_CURSOR_KEY = "repost_fresh_cursor"
REPOST_CURSOR_FAILURE_LIMIT = 2

WHATS_NEW_FEED = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
NEWS_BLOG_URL = "https://aws.amazon.com/blogs/aws/"
NEWS_BLOG_FEED = f"{NEWS_BLOG_URL}feed/"
DEVELOPER_BLOG_URL = "https://aws.amazon.com/blogs/developer/"
DEVELOPER_BLOG_FEED = f"{DEVELOPER_BLOG_URL}feed/"
OPEN_SOURCE_BLOG_URL = "https://aws.amazon.com/blogs/opensource/"
OPEN_SOURCE_BLOG_FEED = f"{OPEN_SOURCE_BLOG_URL}feed/"
REPOST_URL = "https://repost.aws/articles"
CLI_CHANGELOG_URL = "https://raw.githubusercontent.com/aws/aws-cli/v2/CHANGELOG.rst"
CLI_RELEASES_ATOM = "https://github.com/aws/aws-cli/releases.atom"

SOURCES = (
    ("AWS What's New", WHATS_NEW_FEED, 100),
    ("AWS News Blog", NEWS_BLOG_FEED, 80),
    ("AWS Developer Tools Blog", DEVELOPER_BLOG_FEED, 80),
    ("AWS Open Source Blog", OPEN_SOURCE_BLOG_FEED, 80),
)
PER_SOURCE_CAP = {
    "AWS What's New": 100,
    "AWS News Blog": 80,
    "AWS Developer Tools Blog": 80,
    "AWS Open Source Blog": 80,
    "AWS re:Post Articles": 80,
    "AWS CLI v2 Changelog": 40,
}
_VERSION_HEADING_RE = re.compile(r"(?m)^(\d+\.\d+\.\d+)\r?\n=+\s*$")


def doc_sources():
    """Return the user-facing AWS surfaces represented by this aggregate."""
    return [
        ("AWS What's New", WHATS_NEW_FEED),
        ("AWS Blogs", BLOG_URL),
        ("AWS re:Post Articles", REPOST_URL),
        ("AWS News Blog", NEWS_BLOG_URL),
        ("AWS CLI v2 Changelog", CLI_CHANGELOG_URL),
        ("AWS Developer Tools Blog", DEVELOPER_BLOG_URL),
        ("AWS Open Source Blog", OPEN_SOURCE_BLOG_URL),
    ]


def _repost_response(html: str) -> tuple[dict, BeautifulSoup] | None:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None or not script.string:
        return None
    try:
        payload = json.loads(script.string)
        response = payload["props"]["pageProps"]["response"]
    except json.JSONDecodeError, KeyError, TypeError:
        return None
    if not isinstance(response, dict) or not isinstance(response.get("articles"), list):
        return None
    return response, soup


def _repost_links(soup: BeautifulSoup) -> dict[str, str]:
    """Map re:Post article ids to their canonical server-rendered URLs."""
    links: dict[str, str] = {}
    for anchor in soup.select("a[href^='/articles/']"):
        href = str(anchor.get("href") or "").split("?", 1)[0].split("#", 1)[0]
        parts = href.split("/")
        if len(parts) >= 4 and parts[2]:
            links.setdefault(parts[2], f"https://repost.aws{href}")
    return links


def _repost_entry(item, links: dict[str, str]) -> dict | None:
    """Normalize one English re:Post article record."""
    if not isinstance(item, dict) or item.get("language") not in (None, "en"):
        return None
    article_id = str(item.get("id") or "").strip()
    title = sanitize_xml(str(item.get("title") or "").strip()).strip()
    link = links.get(article_id)
    date = multi_rss.parse_date(item.get("createdAt"))
    if not article_id or not title or not link or date is None:
        return None
    description = sanitize_xml(str(item.get("description") or "").strip()).strip()
    return {
        "title": title[:300],
        "link": link,
        "date": date,
        "description": (description or title)[:2000],
        "source": "AWS re:Post Articles",
    }


def _repost_metadata(response: dict) -> tuple[int, int, int] | None:
    """Validate and return page number, page size, and advertised total."""
    page = response.get("page")
    page_size = response.get("pageSize")
    total = response.get("totalCount")
    if isinstance(page, bool) or not isinstance(page, int) or page < 0:
        return None
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 0:
        return None
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        return None
    return page, page_size, total


def _repost_tokens(response: dict) -> dict[int, str]:
    """Return validated pagination tokens keyed by destination page."""
    tokens: dict[int, str] = {}
    raw_tokens = response.get("pagingTokens")
    if not isinstance(raw_tokens, list):
        return tokens
    for record in raw_tokens:
        if not isinstance(record, dict):
            continue
        page = record.get("page")
        token = record.get("token")
        if (
            isinstance(page, int)
            and not isinstance(page, bool)
            and isinstance(token, str)
            and token
        ):
            tokens[page] = token
    return tokens


def parse_repost_page(html: str) -> dict | None:
    """Parse one server-rendered AWS re:Post article listing page."""
    parsed = _repost_response(html)
    if parsed is None:
        return None
    response, soup = parsed
    metadata = _repost_metadata(response)
    if metadata is None:
        return None
    page, page_size, total = metadata
    links = _repost_links(soup)
    entries = [
        entry
        for item in response["articles"]
        if (entry := _repost_entry(item, links)) is not None
    ]
    return {
        "entries": entries,
        "page": page,
        "page_size": page_size,
        "total": total,
        "tokens": _repost_tokens(response),
    }


def _repost_page_url(token: str) -> str:
    return f"{REPOST_URL}?{urlencode({'page': token, 'pageSize': 12})}"


@dataclass(frozen=True)
class _RepostContext:
    """Shared scrape state plus the immutable history boundary for one cursor."""

    known_links: set[str]
    boundary_links: set[str]
    seen: set[str]
    cache_state: dict
    cursor_key: str = REPOST_CURSOR_KEY

    def with_cursor(
        self, cursor_key: str, boundary_links: set[str] | None = None
    ) -> _RepostContext:
        """Reuse scrape state with another cursor and optional history boundary."""
        return _RepostContext(
            self.known_links,
            self.boundary_links if boundary_links is None else boundary_links,
            self.seen,
            self.cache_state,
            cursor_key,
        )


def _append_repost_entries(
    entries: list[dict], context: _RepostContext, collected: list[dict]
) -> bool:
    """Append unseen entries and report whether the original history was reached."""
    reached_boundary = False
    for entry in entries:
        link = entry["link"]
        if link in context.boundary_links:
            reached_boundary = True
        if link in context.known_links or link in context.boundary_links:
            continue
        if link not in context.seen:
            context.seen.add(link)
            collected.append(entry)
    return reached_boundary


def _repost_cursor(
    cache_state: dict, *, key: str = REPOST_CURSOR_KEY
) -> tuple[int, str, int] | None:
    """Return a validated saved re:Post continuation cursor."""
    raw = cache_state.get(key)
    if not isinstance(raw, dict):
        return None
    page = raw.get("page")
    token = raw.get("token")
    failures = raw.get("failures", 0)
    if isinstance(page, bool) or not isinstance(page, int) or page <= 1:
        return None
    if not isinstance(token, str) or not token:
        return None
    if isinstance(failures, bool) or not isinstance(failures, int) or failures < 0:
        return None
    return page, token, failures


def _repost_boundary_key(cursor_key: str) -> str:
    return f"{cursor_key}_boundary"


def _load_repost_boundary(cache_state: dict, cursor_key: str) -> set[str] | None:
    """Load the immutable history snapshot stored with a pagination cursor."""
    raw = cache_state.get(_repost_boundary_key(cursor_key))
    if raw is None:
        return None
    if not isinstance(raw, list):
        return set()
    return {link for link in raw if isinstance(link, str) and link}


def _store_repost_cursor(
    cache_state: dict,
    page: int,
    token: str,
    failures: int = 0,
    *,
    key: str = REPOST_CURSOR_KEY,
) -> None:
    cursor = {"page": page, "token": token}
    if failures:
        cursor["failures"] = failures
    cache_state[key] = cursor


def _store_repost_boundary(
    cache_state: dict, cursor_key: str, boundary_links: set[str]
) -> None:
    cache_state[_repost_boundary_key(cursor_key)] = sorted(boundary_links)


def _clear_repost_cursor(cache_state: dict, *, key: str = REPOST_CURSOR_KEY) -> None:
    cache_state.pop(key, None)
    cache_state.pop(_repost_boundary_key(key), None)


def _note_repost_cursor_failure(
    context: _RepostContext, cursor: tuple[int, str, int]
) -> None:
    """Keep one transient cursor failure, then reset a repeatedly dead token."""
    page, token, failures = cursor
    failures += 1
    if failures >= REPOST_CURSOR_FAILURE_LIMIT:
        _clear_repost_cursor(context.cache_state, key=context.cursor_key)
        multi_rss.logger.warning(
            "[AWS re:Post Articles] saved page %d cursor failed repeatedly; resetting",
            page,
        )
        return
    _store_repost_cursor(
        context.cache_state,
        page,
        token,
        failures,
        key=context.cursor_key,
    )
    _store_repost_boundary(
        context.cache_state,
        context.cursor_key,
        context.boundary_links,
    )


def _repost_finished(page_no: int, parsed: dict, reached_boundary: bool) -> bool:
    """Return whether original history or the advertised source end was reached."""
    return reached_boundary or page_no * parsed["page_size"] >= parsed["total"]


def _next_repost_cursor(parsed: dict, page_no: int) -> tuple[int, str] | None:
    """Return the validated token for the next absolute page."""
    next_page = page_no + 1
    token = parsed["tokens"].get(next_page)
    return (next_page, token) if token else None


def _fetch_repost_page(url: str, page_no: int) -> tuple[dict | None, str | None]:
    """Fetch and validate one re:Post page, returning a small failure code."""
    html = multi_rss.get_html(url)
    if not html:
        return None, "unavailable"
    parsed = parse_repost_page(html)
    if parsed is None or parsed["page"] != page_no:
        return None, "changed"
    if parsed["total"] > 0 and not parsed["entries"]:
        return None, "empty"
    return parsed, None


def _log_repost_page_failure(page_no: int, failure: str) -> None:
    messages = {
        "unavailable": "unavailable",
        "changed": "payload changed",
        "empty": "has no usable entries",
    }
    multi_rss.logger.warning(
        "[AWS re:Post Articles] page %d %s", page_no, messages[failure]
    )


def _collect_repost_head(
    context: _RepostContext,
) -> tuple[list[dict], bool, tuple[int, str] | None] | None:
    """Poll page 1 and report whether the original history was reached."""
    parsed, failure = _fetch_repost_page(REPOST_URL, 1)
    if parsed is None:
        _log_repost_page_failure(1, failure or "changed")
        return None
    collected: list[dict] = []
    reached_boundary = _append_repost_entries(parsed["entries"], context, collected)
    finished = _repost_finished(1, parsed, reached_boundary)
    next_cursor = None if finished else _next_repost_cursor(parsed, 1)
    return collected, finished, next_cursor


def _repost_window_start(cursor: tuple[int, str, int] | None) -> tuple[int, str]:
    """Return the absolute page and URL for a fresh or resumed window."""
    if cursor is None:
        return 1, REPOST_URL
    page, token, _failures = cursor
    return page, _repost_page_url(token)


def _handle_repost_window_failure(
    context: _RepostContext,
    cursor: tuple[int, str, int] | None,
    page_no: int,
    failure: str,
) -> None:
    """Apply the bounded retry/reset policy for a failed pagination window."""
    _log_repost_page_failure(page_no, failure)
    if cursor is None:
        return
    if failure == "unavailable":
        _note_repost_cursor_failure(context, cursor)
    else:
        _clear_repost_cursor(context.cache_state, key=context.cursor_key)


def _healthy_repost_cursor(
    context: _RepostContext, cursor: tuple[int, str, int] | None
) -> tuple[int, str, int] | None:
    """Reset a saved cursor's transient-failure count after a successful fetch."""
    if cursor is None:
        return None
    page, token, _failures = cursor
    healthy = (page, token, 0)
    _store_repost_cursor(context.cache_state, page, token, key=context.cursor_key)
    return healthy


def _repost_page_continuation(
    parsed: dict,
    page_no: int,
    context: _RepostContext,
    collected: list[dict],
) -> tuple[bool, tuple[int, str] | None]:
    """Append one page and return whether it finished plus its continuation."""
    reached_boundary = _append_repost_entries(parsed["entries"], context, collected)
    if _repost_finished(page_no, parsed, reached_boundary):
        return True, None
    return False, _next_repost_cursor(parsed, page_no)


def _checkpoint_repost_cursor(
    context: _RepostContext, next_cursor: tuple[int, str]
) -> None:
    page, token = next_cursor
    _store_repost_cursor(context.cache_state, page, token, key=context.cursor_key)
    _store_repost_boundary(
        context.cache_state,
        context.cursor_key,
        context.boundary_links,
    )
    multi_rss.logger.info(
        "[AWS re:Post Articles] checkpointed continuation at page %d", page
    )


def _resume_repost_context(context: _RepostContext, cursor_key: str) -> _RepostContext:
    """Bind a cursor to its original immutable history boundary."""
    boundary = _load_repost_boundary(context.cache_state, cursor_key)
    if boundary is None:
        boundary = (
            set()
            if _repost_cursor(context.cache_state, key=cursor_key)
            else context.boundary_links
        )
    return context.with_cursor(cursor_key, boundary)


def _collect_repost_window(
    context: _RepostContext,
    *,
    budget: int,
    cursor: tuple[int, str, int] | None = None,
) -> tuple[list[dict] | None, int]:
    """Collect one bounded sequential window and checkpoint its continuation."""
    if budget <= 0:
        return [], 0
    collected: list[dict] = []
    page_no, url = _repost_window_start(cursor)
    requests_used = 0
    active_cursor = cursor
    result: list[dict] | None = None
    while requests_used < budget:
        requests_used += 1
        parsed, failure = _fetch_repost_page(url, page_no)
        if parsed is None:
            _handle_repost_window_failure(
                context,
                active_cursor,
                page_no,
                failure or "changed",
            )
            if failure == "unavailable" and collected:
                result = collected
            break
        if requests_used == 1:
            active_cursor = _healthy_repost_cursor(context, active_cursor)
        finished, next_cursor = _repost_page_continuation(
            parsed, page_no, context, collected
        )
        if finished:
            _clear_repost_cursor(context.cache_state, key=context.cursor_key)
            result = collected
            break
        if next_cursor is None:
            multi_rss.logger.warning(
                "[AWS re:Post Articles] missing token for page %d", page_no + 1
            )
            _clear_repost_cursor(context.cache_state, key=context.cursor_key)
            break
        if requests_used >= budget:
            _checkpoint_repost_cursor(context, next_cursor)
            result = collected
            break
        page_no, token = next_cursor
        active_cursor = (page_no, token, 0)
        url = _repost_page_url(token)
    return result, requests_used


def _fresh_cursor_from_head(
    head_next: tuple[int, str] | None,
) -> tuple[int, str, int] | None:
    if head_next is None:
        multi_rss.logger.warning(
            "[AWS re:Post Articles] missing token for fresh page 2"
        )
        return None
    page, token = head_next
    return page, token, 0


def _collect_repost_prefix_to_known(
    context: _RepostContext, *, budget: int
) -> tuple[list[dict] | None, bool, bool, int]:
    """Rescan from the head until cached overlap safely reconnects a saved cursor."""
    if budget <= 0:
        return [], False, False, 0
    collected: list[dict] = []
    page_no = 1
    url = REPOST_URL
    requests_used = 0
    reconnected = False
    reached_boundary = False
    result: list[dict] | None = collected
    while requests_used < budget:
        requests_used += 1
        parsed, failure = _fetch_repost_page(url, page_no)
        if parsed is None:
            _log_repost_page_failure(page_no, failure or "changed")
            if failure != "unavailable" or not collected:
                result = None
            break
        links = {entry["link"] for entry in parsed["entries"]}
        reached_boundary = bool(links & context.boundary_links)
        reached_known = bool(links & context.known_links)
        _append_repost_entries(parsed["entries"], context, collected)
        if reached_boundary or page_no * parsed["page_size"] >= parsed["total"]:
            reconnected = True
            reached_boundary = True
            break
        if reached_known:
            reconnected = True
            break
        next_cursor = _next_repost_cursor(parsed, page_no)
        if next_cursor is None:
            multi_rss.logger.warning(
                "[AWS re:Post Articles] missing token for page %d", page_no + 1
            )
            result = None
            break
        page_no, token = next_cursor
        url = _repost_page_url(token)
    return result, reconnected, reached_boundary, requests_used


def _resume_repost_freshness(
    context: _RepostContext,
    saved_cursor: tuple[int, str, int],
    *,
    budget: int,
) -> tuple[list[dict] | None, bool, int]:
    """Reconnect the current head to a persisted freshness continuation."""
    prefix, reconnected, reached_boundary, used = _collect_repost_prefix_to_known(
        context, budget=budget
    )
    if prefix is None:
        return None, False, used
    if reached_boundary:
        _clear_repost_cursor(context.cache_state, key=REPOST_FRESH_CURSOR_KEY)
        return prefix, True, used
    if not reconnected or used >= budget:
        return prefix, False, used
    more, resumed_used = _collect_repost_window(
        context,
        budget=budget - used,
        cursor=saved_cursor,
    )
    if more is not None:
        prefix.extend(more)
    complete = (
        more is not None
        and _repost_cursor(context.cache_state, key=REPOST_FRESH_CURSOR_KEY) is None
    )
    return prefix, complete, used + resumed_used


def _start_repost_freshness(
    context: _RepostContext, *, budget: int
) -> tuple[list[dict] | None, bool, int]:
    """Start a new bounded freshness scan from the listing head."""
    head = _collect_repost_head(context)
    if head is None:
        return None, False, 1
    collected, finished, head_next = head
    if finished:
        _clear_repost_cursor(context.cache_state, key=REPOST_FRESH_CURSOR_KEY)
        return collected, True, 1
    fresh_cursor = _fresh_cursor_from_head(head_next)
    if fresh_cursor is None:
        return collected, False, 1
    remaining = budget - 1
    if remaining <= 0:
        _checkpoint_repost_cursor(context, (fresh_cursor[0], fresh_cursor[1]))
        return collected, False, 1
    more, used = _collect_repost_window(
        context,
        budget=remaining,
        cursor=fresh_cursor,
    )
    if more is not None:
        collected.extend(more)
    complete = (
        more is not None
        and _repost_cursor(context.cache_state, key=REPOST_FRESH_CURSOR_KEY) is None
    )
    return collected, complete, 1 + used


def _collect_repost_freshness(
    context: _RepostContext,
    *,
    budget: int,
) -> tuple[list[dict] | None, bool, int]:
    """Scan fresh pages from the head before any archive continuation."""
    fresh_context = _resume_repost_context(context, REPOST_FRESH_CURSOR_KEY)
    saved_cursor = _repost_cursor(context.cache_state, key=REPOST_FRESH_CURSOR_KEY)
    if saved_cursor is not None:
        return _resume_repost_freshness(fresh_context, saved_cursor, budget=budget)
    return _start_repost_freshness(fresh_context, budget=budget)


def _collect_repost_initial(context: _RepostContext) -> list[dict]:
    cursor_key = REPOST_FRESH_CURSOR_KEY if context.known_links else REPOST_CURSOR_KEY
    entries, _used = _collect_repost_window(
        context.with_cursor(cursor_key),
        budget=MAX_REPOST_PAGES,
    )
    return entries or []


def _collect_repost_bootstrap_resume(
    context: _RepostContext, archive_cursor: tuple[int, str, int]
) -> list[dict]:
    head_context = context.with_cursor(REPOST_FRESH_CURSOR_KEY, set())
    head = _collect_repost_head(head_context)
    if head is None:
        return []
    head_entries, _finished, _next_cursor = head
    archive_context = _resume_repost_context(context, REPOST_CURSOR_KEY)
    archive, _used = _collect_repost_window(
        archive_context,
        budget=max(0, MAX_REPOST_PAGES - 1),
        cursor=archive_cursor,
    )
    return head_entries + (archive or [])


def _collect_repost_incremental(context: _RepostContext) -> list[dict]:
    fresh, fresh_complete, used = _collect_repost_freshness(
        context,
        budget=MAX_REPOST_PAGES,
    )
    if fresh is None:
        return []
    if not fresh_complete:
        return fresh
    archive_cursor = _repost_cursor(context.cache_state)
    remaining = max(0, MAX_REPOST_PAGES - used)
    if archive_cursor is None or remaining <= 0:
        return fresh
    archive_context = _resume_repost_context(context, REPOST_CURSOR_KEY)
    archive, _used = _collect_repost_window(
        archive_context,
        budget=remaining,
        cursor=archive_cursor,
    )
    return fresh + (archive or [])


def collect_repost(known_links: set[str], cache_state: dict) -> list[dict]:
    """Collect fresh pages first, then advance bounded archive catch-up."""
    repost_links = {link for link in known_links if link.startswith(f"{REPOST_URL}/")}
    context = _RepostContext(repost_links, repost_links, set(), cache_state)
    archive_cursor = _repost_cursor(cache_state)
    fresh_cursor = _repost_cursor(cache_state, key=REPOST_FRESH_CURSOR_KEY)
    if archive_cursor is None and fresh_cursor is None:
        return _collect_repost_initial(context)
    if archive_cursor is not None and not repost_links and fresh_cursor is None:
        return _collect_repost_bootstrap_resume(context, archive_cursor)
    return _collect_repost_incremental(context)


def parse_cli_release_dates(atom_xml: str) -> dict[str, tuple[datetime, str]]:
    """Map AWS CLI release versions to their GitHub release date and URL."""
    soup = BeautifulSoup(atom_xml, "xml")
    releases = {}
    for entry in soup.find_all("entry"):
        title_el = entry.find("title")
        updated_el = entry.find("updated")
        link_el = entry.find("link", href=True)
        version = title_el.get_text(strip=True) if title_el else ""
        date = (
            multi_rss.parse_date(updated_el.get_text(strip=True))
            if updated_el
            else None
        )
        link = str(link_el.get("href") or "").strip() if link_el else ""
        if re.fullmatch(r"2\.\d+\.\d+", version) and date is not None and link:
            releases[version] = (date, link)
    return releases


def _clean_rst_summary(body: str, version: str) -> str:
    lines = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^\*\s*", "", line)
        line = line.replace("``", "")
        lines.append(line)
    summary = sanitize_xml(" ".join(lines)).strip()
    return (summary or f"AWS CLI {version} release")[:3000]


def parse_cli_changelog(
    changelog: str,
    release_dates: dict[str, tuple[datetime, str]],
    known_links: set[str] | None = None,
) -> list[dict]:
    """Join v2 changelog sections with authoritative GitHub release dates."""
    known_links = known_links or set()
    matches = list(_VERSION_HEADING_RE.finditer(changelog))
    entries = []
    for index, match in enumerate(matches):
        version = match.group(1)
        release = release_dates.get(version)
        if release is None:
            continue
        date, link = release
        if link in known_links:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
        body = changelog[match.end() : end]
        entries.append(
            {
                "title": f"AWS CLI {version}",
                "link": link,
                "date": date,
                "description": _clean_rst_summary(body, version),
                "source": "AWS CLI v2 Changelog",
            }
        )
    return entries


def collect_cli_changelog(known_links: set[str]) -> list[dict]:
    """Collect dated AWS CLI v2 changelog entries."""
    changelog = multi_rss.get_html(CLI_CHANGELOG_URL)
    releases_xml = multi_rss.get_html(CLI_RELEASES_ATOM)
    if not changelog or not releases_xml:
        return []
    releases = parse_cli_release_dates(releases_xml)
    entries = parse_cli_changelog(changelog, releases, known_links)
    multi_rss.logger.info(
        "[AWS CLI v2 Changelog] collected %d fresh releases", len(entries)
    )
    return entries


def main(full: bool = False) -> bool:
    """Generate the combined AWS feed with persisted scraper state."""
    cache_state: dict = {}

    def collect_repost_with_state(known_links: set[str]) -> list[dict]:
        """Bind the shared cache state to the re:Post scraper callback."""
        return collect_repost(known_links, cache_state)

    return multi_rss.run(
        feed_name=FEED_NAME,
        title=FEED_TITLE,
        subtitle="AWS announcements, selected blogs, re:Post articles, and AWS CLI v2 releases.",
        blog_url=BLOG_URL,
        author="Amazon Web Services",
        sources=SOURCES,
        extra_scrapers=(collect_repost_with_state, collect_cli_changelog),
        max_entries=MAX_ENTRIES,
        per_source_cap=PER_SOURCE_CAP,
        cache_state=cache_state,
        full=full,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the combined AWS Atom feed")
    parser.add_argument(
        "--full", action="store_true", help="Ignore cache and rebuild from scratch"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
