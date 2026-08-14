"""One call that upgrades entries just before they are published.

Two things were being lost on the way out: entries whose link is a Google News
wrapper rather than the article, and entries with no picture because the
upstream feed shipped none. Both are fixed by asking the web, both are budgeted
per feed, and both write what they learn into the entry dicts - so a generator
that caches those dicts pays for each lookup exactly once, ever.

Order is not arbitrary: a wrapper page has no picture of its own, so links are
resolved first and only then is the real article asked for its image.

Generators call this with the entries they are about to write::

    feed_items = merged[-MAX_ENTRIES:]
    enrich_entries(feed_items)
    save_cache(FEED_NAME, merged)   # keeps what was learned

Nothing here is allowed to fail a feed. A missing picture is a blemish; a
generator that exits non-zero over one is an outage.
"""

from __future__ import annotations

from article_image import backfill_images
from google_news import resolve_entries
from utils import setup_logging

logger = setup_logging(__name__)


def enrich_entries(entries: list[dict], *, images: bool = True, links: bool = True) -> None:
    """Resolve wrapper links, then fill in missing images. Never raises."""
    if links:
        try:
            resolve_entries(entries)
        except Exception as exc:  # a wrapper link still works, just badly
            logger.warning("Google News resolution failed: %s", exc)
    if images:
        try:
            backfill_images(entries)
        except Exception as exc:  # a picture is never worth failing a feed over
            logger.warning("Image backfill failed: %s", exc)
