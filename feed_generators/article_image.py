"""Find an article's own image when the feed it came from shipped none.

Measured on 11.08.2026 across the 90 published feeds: **14 138 of 18 347
entries (77%) carried no image at all** - no media:content, no media:thumbnail,
no enclosure - so readers render them as a wall of text. 55 of the 82 worst
feeds run through :mod:`multi_rss`, and the reason is not that the pictures do
not exist: the upstream RSS simply omits them. The article page has the image
anyway, in the Open Graph tags every CMS emits so links look good on social
media. This module goes and gets it.

Cost is the whole design problem. The feeds regenerate every two hours, so a
naive "fetch every entry" pass would mean tens of thousands of requests a day
against other people's sites, for pictures that never change. Four things keep
it small:

- only entries about to be **published** are looked up, not everything cached;
- a hit is written into the entry, so the cache carries it forever after;
- a miss is remembered too (``image_checked``), so a genuinely imageless
  article is not re-fetched every run;
- each feed spends at most :data:`MAX_LOOKUPS` fetches and :data:`MAX_SECONDS`
  of wall clock per run, so the initial backfill spreads over runs instead of
  arriving as one thundering herd - and one unresponsive origin cannot push the
  scheduled job toward its timeout.

A network error is deliberately *not* recorded as a miss - it stays pending and
is retried next run, at most :data:`MAX_ATTEMPTS` times *per lookup URL*.
When a Google News wrapper URL fails transiently and later resolves to the real
article URL, the counter is bound to the wrapper, so the real URL is still
eligible for lookup. A 404 or 410 is recorded as a settled miss, because
that page is not coming back.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from utils import setup_logging

logger = setup_logging(__name__)

# Per-feed budget for one run. 40 x ~55 multi-source feeds is ~2200 fetches
# spread over a two-hourly job, and only until the backlog clears: once every
# published entry is resolved or marked, a normal run looks up only what is new.
MAX_LOOKUPS = int(os.environ.get("FEEDSEEK_IMAGE_LOOKUPS", "40"))
# Second budget, in wall clock. The scheduled job runs ~12 min against a 69 min
# timeout, and 55 feeds each waiting out a hung origin would eat that headroom;
# whatever a feed does not finish inside this stays pending for the next run.
MAX_SECONDS = float(os.environ.get("FEEDSEEK_IMAGE_SECONDS", "25"))
# Maximum number of attempts for a URL that keeps returning transient failures
# before marking it as permanently checked to avoid retrying it forever.
MAX_ATTEMPTS = int(os.environ.get("FEEDSEEK_IMAGE_ATTEMPTS", "3"))
WORKERS = 8
TIMEOUT = 10
# Open Graph tags live in <head>; reading further is paying for markup we ignore.
HEAD_BYTES = 262_144

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

# Ordered best-first. og:image is the near-universal one; the rest cover CMSes
# that emit a variant spelling, put the tag under name= instead of property=
# (technically wrong, widely done), or only ship Twitter cards.
_META_TAGS = (
    ("property", "og:image:secure_url"),
    ("property", "og:image"),
    ("name", "og:image"),
    ("property", "og:image:url"),
    ("name", "twitter:image"),
    ("property", "twitter:image"),
    ("name", "twitter:image:src"),
    ("itemprop", "image"),
)

# Sites that serve a house placeholder for every article are worse than no
# image: an identical picture on 200 entries reads as a rendering bug.
_JUNK_MARKERS = ("placeholder", "default-image", "no-image", "blank.gif", "spacer.gif")


def _absolute(url: str | None, base_url: str) -> str | None:
    """Absolutize a candidate, or reject it if it is not a usable http(s) image."""
    if not url:
        return None
    url = url.strip()
    if not url or url.startswith("data:"):
        return None
    url = urljoin(base_url, url)
    if urlsplit(url).scheme not in ("http", "https"):
        return None
    if any(marker in url.lower() for marker in _JUNK_MARKERS):
        return None
    return url


def _from_json_ld(soup: BeautifulSoup, base_url: str) -> str | None:
    """Pull an image out of schema.org JSON-LD.

    Worth the trouble because news sites that omit Open Graph almost always
    still ship NewsArticle/BlogPosting metadata for Google. The ``image`` value
    is allowed to be a string, an ImageObject, or a list of either, and the
    payload may be a @graph wrapper, so this walks rather than indexes.
    """

    def walk(node):
        if isinstance(node, str):
            return node
        if isinstance(node, dict):
            # Only an ImageObject's own url is an image; an Article's url is the
            # article, and returning that would attach the page to itself.
            if node.get("@type") == "ImageObject" and isinstance(node.get("url"), str):
                return node["url"]
            for key in ("image", "thumbnailUrl", "primaryImageOfPage"):
                if key in node:
                    found = walk(node[key])
                    if found:
                        return found
            for key in ("@graph", "mainEntity", "mainEntityOfPage"):
                if key in node:
                    found = walk(node[key])
                    if found:
                        return found
            return None
        if isinstance(node, list):
            for item in node:
                found = walk(item)
                if found:
                    return found
        return None

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue  # hand-written JSON-LD is frequently invalid; skip it
        image = _absolute(walk(data), base_url)
        if image:
            return image
    return None


def page_image(html: str, base_url: str) -> tuple[str | None, int | None, int | None]:
    """Best image URL declared by an HTML page, with dimensions when stated.

    Returns ``(url, width, height)``; width/height are ``None`` unless the page
    declares og:image:width / og:image:height. They are worth carrying: MRSS
    consumers that get them can lay out a thumbnail without downloading it
    first.
    """
    if not html:
        return None, None, None
    soup = BeautifulSoup(html, "html.parser")

    image = None
    for attribute, value in _META_TAGS:
        element = soup.find("meta", attrs={attribute: value})
        if element:
            image = _absolute(element.get("content"), base_url)
            if image:
                break

    if not image:
        link = soup.find("link", rel="image_src")
        image = _absolute(link.get("href") if link else None, base_url)

    if not image:
        image = _from_json_ld(soup, base_url)

    if not image:
        return None, None, None

    def dimension(prop: str) -> int | None:
        element = soup.find("meta", attrs={"property": prop})
        try:
            size = int((element.get("content") or "").strip()) if element else 0
        except (ValueError, TypeError):
            return None
        return size if 0 < size <= 10000 else None

    return image, dimension("og:image:width"), dimension("og:image:height")


def _read_head(response) -> str:
    """Read only as far as </head>, decoded with the response's own encoding."""
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(16_384):
        chunks.append(chunk)
        total += len(chunk)
        if total >= HEAD_BYTES or b"</head>" in chunks[-1] or b"</HEAD>" in chunks[-1]:
            break
    body = b"".join(chunks)
    encoding = response.encoding or response.apparent_encoding or "utf-8"
    return body.decode(encoding, errors="replace")


def _impersonated_html(url: str) -> str | None:
    """Retry through curl_cffi for origins that reject a plain requests TLS
    fingerprint. Medium and other Cloudflare-fronted sites answer 403 to the
    stdlib client no matter the User-Agent, and serve the page fine to this."""
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        return None
    try:
        response = curl_requests.get(url, impersonate="chrome", timeout=TIMEOUT)
    except Exception as exc:  # curl_cffi raises its own error hierarchy
        logger.debug("Impersonated image lookup failed for %s: %s", url, exc)
        return None
    if response.status_code != 200:
        return None
    return response.text


def article_image(url: str, session=None) -> tuple[str | None, int | None, int | None, bool]:
    """Fetch ``url`` and return ``(image, width, height, settled)``.

    ``settled`` is the important half: True means the answer is final and the
    caller should stop asking - either an image was found, or the page loaded
    and genuinely has none, or the page is gone for good. False means something
    transient went wrong (timeout, 5xx, rate limit) and the entry should be
    left pending for the next run.
    """
    getter = session or requests
    try:
        response = getter.get(
            url, headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=True
        )
    except requests.RequestException as exc:
        logger.debug("Image lookup failed for %s: %s", url, exc)
        return None, None, None, False

    try:
        status = response.status_code
        if status in (401, 403):
            html = _impersonated_html(url)
            if html:
                image, width, height = page_image(html, url)
                return image, width, height, True
            return None, None, None, False
        if status != 200:
            # 404/410 will never become an image; 429/5xx might, next run.
            return None, None, None, status in (404, 410)
        content_type = (response.headers.get("content-type") or "").lower()
        if "html" not in content_type and content_type:
            return None, None, None, True  # a PDF or JSON endpoint has no og:image
        html = _read_head(response)
    except requests.RequestException as exc:
        logger.debug("Image lookup aborted for %s: %s", url, exc)
        return None, None, None, False
    finally:
        response.close()

    image, width, height = page_image(html, url)
    return image, width, height, True


def backfill_images(
    entries: list[dict],
    *,
    limit: int = MAX_LOOKUPS,
    workers: int = WORKERS,
    max_seconds: float = MAX_SECONDS,
    lookup=article_image,
) -> int:
    """Fill in ``image`` for entries that have none. Returns how many were found.

    Mutates the entry dicts in place, which is the point: callers hand in the
    very dicts they are about to cache, so a resolved image is written once and
    read from the cache from then on. Newest entries are served first - they are
    what a reader actually sees when the budget runs out mid-backlog.
    """
    # article_url is set by google_news when the entry's link is a Google News
    # wrapper; asking the wrapper for a picture would always come back empty.
    def target(entry) -> str:
        return str(entry.get("article_url") or entry.get("link") or "")

    pending = [
        entry
        for entry in entries
        if not entry.get("image")
        and not entry.get("image_checked")
        and target(entry).startswith(("http://", "https://"))
        and not (
            entry.get("image_attempts", 0) >= MAX_ATTEMPTS
            and entry.get("image_attempt_url") == target(entry)
        )
    ]
    # Entries sharing one link have no per-article page to ask, so a lookup
    # would stamp the same picture on all of them - foobar2000 publishes 326
    # changelog entries across four URLs, and a reader seeing one image repeated
    # 326 times reads it as a rendering bug, not as illustration.
    #
    # Counted over every entry, not just the pending ones: whether a URL is
    # shared is a property of the feed, not of who still needs a picture.
    # Counting the filtered list instead would let the last unresolved sibling
    # look unique - the others having been resolved, marked or capped - and
    # collect the shared page's image after all.
    seen = Counter(
        target(entry)
        for entry in entries
        if target(entry).startswith(("http://", "https://"))
    )
    pending = [entry for entry in pending if seen[target(entry)] == 1]
    if not pending:
        return 0

    # entries arrive sorted ascending by date, so the tail is the newest.
    if limit is not None and limit <= 0:
        return 0  # a budget of zero means "not this run", not "no ceiling"
    batch = pending[-limit:] if limit and len(pending) > limit else pending
    logger.info(
        "Looking up images for %d of %d entries missing one", len(batch), len(pending)
    )

    session = requests.Session()
    pool = ThreadPoolExecutor(max_workers=workers)
    pending_futures = {pool.submit(lookup, target(entry), session): entry for entry in batch}

    def note_transient(entry) -> None:
        """Record one inconclusive attempt against the URL it was made on.

        Every way a lookup can end without an answer funnels through here -
        a transient status, a raised exception, or a future abandoned when the
        wall-clock budget expires. Missing any of them would exempt that whole
        class from the cap and leave it retried forever, which is the bug the
        cap exists to prevent.
        """
        url = target(entry)
        if entry.get("image_attempt_url") != url:
            entry["image_attempts"] = 0
        entry["image_attempts"] = entry.get("image_attempts", 0) + 1
        entry["image_attempt_url"] = url

    found = 0
    answered = 0
    handled: set[int] = set()
    try:
        for future in as_completed(pending_futures, timeout=max_seconds):
            entry = pending_futures[future]
            answered += 1
            handled.add(id(entry))
            try:
                image, width, height, settled = future.result()
            except Exception as exc:  # a lookup must never sink the feed
                logger.debug("Image lookup raised for %s: %s", target(entry), exc)
                note_transient(entry)
                continue
            if image:
                entry["image"] = image
                if width:
                    entry["image_width"] = width
                if height:
                    entry["image_height"] = height
                found += 1
                # Clean up attempt tracking from prior failures
                entry.pop("image_attempts", None)
                entry.pop("image_attempt_url", None)
            elif settled:
                # A settled miss is final; mark it so it is not retried.
                entry["image_checked"] = True
            else:
                # Transient failure: retried at most MAX_ATTEMPTS times per URL.
                note_transient(entry)
    except FuturesTimeout:
        # An abandoned lookup is still an attempt, but only if it ever ran.
        # With 40 lookups over 8 workers most futures are still queued when the
        # budget expires; charging those an attempt would retire entries that
        # were never fetched at all. running() or done() is the difference
        # between an origin that hung and one we simply never got to.
        for future, entry in pending_futures.items():
            if id(entry) not in handled and (future.running() or future.done()):
                note_transient(entry)
        logger.info(
            "Image budget of %.0fs spent after %d of %d lookups; the rest waits for the next run",
            max_seconds,
            answered,
            len(batch),
        )
    finally:
        # Not waiting: whatever is still in flight has already had its answer
        # abandoned, and its own socket timeout ends it shortly after.
        pool.shutdown(wait=False, cancel_futures=True)
        session.close()

    logger.info("Resolved %d image(s); %d page(s) had none", found, answered - found)
    return found
