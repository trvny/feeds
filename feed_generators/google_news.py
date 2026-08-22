"""Turn a Google News RSS link into the article it actually points at.

Eight generators reach sites that block scrapers (reuters.com answers 403 to
anything automated) through Google News RSS. That works for discovery, but the
links it hands back are wrappers - ``news.google.com/rss/articles/CBMi...`` -
and 2257 published entries carried one on 12.08.2026. A wrapper is bad three
ways: the reader lands on a Google interstitial instead of the article, the
entry can never get a picture (the wrapper page has no og:image), and the
destination is invisible before clicking.

The wrapper cannot be decoded offline. The token used to be a base64 of the
target URL; since 2024 it is an opaque id, and the article page resolves it in
JavaScript. What still works is the endpoint that page calls: fetch the wrapper
once for its per-article signature, then ask ``batchexecute`` to translate it.
Two requests per article, so the same budgeting the image lookup uses applies.

The resolved URL is published, but it deliberately does **not** become the
entry's identity - see :func:`resolve_entries`.
"""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout

import requests
from utils import setup_logging

logger = setup_logging(__name__)

BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
MAX_RESOLUTIONS = int(os.environ.get("FEEDSEEK_GNEWS_LOOKUPS", "40"))
MAX_SECONDS = float(os.environ.get("FEEDSEEK_GNEWS_SECONDS", "25"))
# Gentler than the image lookup: this is all one host, and one that throttles.
WORKERS = 4
# A wrapper that keeps refusing is not a transient blip forever. Without a cap the
# same links rebuild the pending list on every two-hourly run and are re-fetched
# indefinitely; this mirrors article_image.MAX_ATTEMPTS, which exists for exactly
# the same reason.
MAX_ATTEMPTS = int(os.environ.get("FEEDSEEK_GNEWS_ATTEMPTS", "3"))
TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    )
}
# Google redirects EU visitors to a consent wall before serving anything, which
# is invisible from a US CI runner and fatal when running from Poland. This is
# the "already answered" marker, not a way to skip a choice a user should make -
# nothing here is personalised and no account is involved.
CONSENT_COOKIES = {"SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg"}

_SIGNATURE_RE = re.compile(r'data-n-a-sg="([^"]+)"')
_TIMESTAMP_RE = re.compile(r'data-n-a-ts="(\d+)"')
_RESULT_RE = re.compile(r'\[\\"garturlres\\",\\"(.*?)\\"')

# Fixed request envelope the article page sends; only the id, timestamp and
# signature vary. The "X" placeholders are what Google's own client sends.
_REQUEST_SHELL = [
    ["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
    "X",
    "X",
    1,
    [1, 1, 1],
    1,
    1,
    None,
    0,
    0,
    None,
    0,
]


def is_wrapper(url: str) -> bool:
    """True for a Google News link that hides the real article behind it."""
    return "news.google.com/rss/articles/" in (url or "")


def _article_id(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?")[0]


def resolve(url: str, session=None) -> str | None:
    """The article a wrapper points at, or None if it cannot be resolved now."""
    if not is_wrapper(url):
        return url
    http = session or requests.Session()
    try:
        page = http.get(url, headers=HEADERS, timeout=TIMEOUT, cookies=CONSENT_COOKIES)
        signature = _SIGNATURE_RE.search(page.text)
        timestamp = _TIMESTAMP_RE.search(page.text)
        if not signature or not timestamp:
            # Either the consent wall won, or the page layout moved.
            logger.debug("No resolution signature on %s", url)
            return None

        payload = json.dumps(
            ["garturlreq", _REQUEST_SHELL, _article_id(url), int(timestamp.group(1)), signature.group(1)]
        )
        response = http.post(
            BATCH_URL,
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data={"f.req": json.dumps([[["Fbv4je", payload, None, "generic"]]])},
            timeout=TIMEOUT,
            cookies=CONSENT_COOKIES,
        )
        found = _RESULT_RE.search(response.text)
        return found.group(1) if found else None
    except requests.RequestException as exc:
        logger.debug("Could not resolve %s: %s", url, exc)
        return None
    finally:
        if session is None:
            http.close()


def resolve_entries(
    entries: list[dict],
    *,
    limit: int = MAX_RESOLUTIONS,
    max_seconds: float = MAX_SECONDS,
    resolver=resolve,
) -> int:
    """Fill in ``article_url`` for entries still pointing at a wrapper.

    The wrapper stays in ``link``, which is what the cache dedupes on and what
    :func:`utils.make_entry_id` hashes. Overwriting it would give 2257 already
    published entries a new id, and every reader would show them as unread
    again - a one-off flood to fix a link. So identity stays put and only the
    published href changes.

    Budgeted exactly like the image lookup: newest first, capped in both count
    and wall clock. A failure is not recorded as an answer - Google throttling is
    not the same as "this article does not exist" - but it is counted, and after
    MAX_ATTEMPTS against the same wrapper the entry stops being asked. Without
    that, a link Google never resolves is re-fetched on every run forever.
    """
    def note_transient(entry) -> None:
        """Count one inconclusive attempt against the wrapper it was made on.

        Bound to the URL so a wrapper that later changes starts from zero, and
        so every way of failing - a raised resolver, a future abandoned by the
        wall clock - lands here rather than slipping past uncounted.
        """
        link = str(entry.get("link", ""))
        if entry.get("resolve_attempt_url") != link:
            entry["resolve_attempts"] = 0
        entry["resolve_attempts"] = entry.get("resolve_attempts", 0) + 1
        entry["resolve_attempt_url"] = link

    pending = [
        entry
        for entry in entries
        if is_wrapper(str(entry.get("link", "")))
        and not entry.get("article_url")
        and not (
            entry.get("resolve_attempts", 0) >= MAX_ATTEMPTS
            and entry.get("resolve_attempt_url") == str(entry.get("link", ""))
        )
    ]
    if not pending:
        return 0

    if limit is not None and limit <= 0:
        return 0  # a budget of zero means "not this run", not "no ceiling"
    batch = pending[-limit:] if limit and len(pending) > limit else pending
    logger.info("Resolving %d of %d Google News links", len(batch), len(pending))

    session = requests.Session()
    pool = ThreadPoolExecutor(max_workers=WORKERS)
    futures = {pool.submit(resolver, entry["link"], session): entry for entry in batch}

    resolved = 0
    handled: set[int] = set()
    try:
        for future in as_completed(futures, timeout=max_seconds):
            entry = futures[future]
            handled.add(id(entry))
            try:
                target = future.result()
            except Exception as exc:  # never worth failing a feed over
                logger.debug("Resolution raised: %s", exc)
                note_transient(entry)
                continue
            if target and not is_wrapper(target):
                entry["article_url"] = target
                entry.pop("resolve_attempts", None)
                entry.pop("resolve_attempt_url", None)
                resolved += 1
            else:
                note_transient(entry)
    except FuturesTimeout:
        # Only a lookup that actually ran is charged. Most futures are still
        # queued when the clock runs out, and retiring those would drop links
        # that were never fetched at all.
        for future, entry in futures.items():
            if id(entry) not in handled and (future.running() or future.done()):
                note_transient(entry)
        logger.info("Google News budget of %.0fs spent; the rest waits for the next run", max_seconds)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        session.close()

    logger.info("Resolved %d Google News link(s)", resolved)
    return resolved


def entry_url(entry: dict) -> str:
    """The href to publish: the real article when known, the wrapper until then."""
    return entry.get("article_url") or entry.get("link") or ""
