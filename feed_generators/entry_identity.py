"""Durable entry identity helpers.

Published entry IDs are reader state: changing one can make an old article look
new again. Keep the currently published URL-derived ID as the compatibility
fallback, but prefer an ID already persisted with the cache entry so a link can
later move without silently changing identity.
"""

from __future__ import annotations

from collections.abc import Callable

ENTRY_ID_FIELD = "entry_id"


def persist_entry_ids(
    feed_name: str,
    entries: list[dict],
    *,
    make_entry_id: Callable[[str, str], str] | None = None,
) -> list[dict]:
    """Seed missing persisted IDs with the exact currently published fallback."""
    if make_entry_id is None:
        import utils

        make_entry_id = utils.make_entry_id

    for entry in entries:
        if entry.get(ENTRY_ID_FIELD):
            continue
        link = entry.get("link")
        if link:
            entry[ENTRY_ID_FIELD] = make_entry_id(feed_name, str(link))
    return entries


def entry_id_for(feed_name: str, entry: dict, *, link_field: str = "link") -> str:
    """Return durable cached identity, falling back to the legacy URL-derived ID."""
    persisted = entry.get(ENTRY_ID_FIELD)
    if persisted:
        return str(persisted)

    link = entry.get(link_field)
    if not link:
        raise ValueError(f"Entry has no {link_field!r} for ID fallback")

    # Resolve through the module at call time. invoke_generator temporarily wraps
    # utils.make_entry_id while a generator runs so fresh fallback IDs are also
    # persisted without making every generator know about that migration layer.
    import utils

    return utils.make_entry_id(feed_name, str(link))
