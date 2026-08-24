"""Safe cache refresh for entries rediscovered by a native feed."""

from __future__ import annotations

from utils import normalize_link, sort_posts_for_feed

SYNTHETIC_TITLE_FIELD = "_feedseek_synthetic_title"
_IMAGE_DIMENSIONS = ("image_width", "image_height")


def _meaningful(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _identity(value) -> str:
    """Canonical comparison key without changing the cached/public link."""
    raw = str(value or "")
    return normalize_link(raw) or raw


def _same_source(cached: dict, fresh: dict) -> bool:
    """Do not let a cross-source duplicate rewrite the kept source's metadata."""
    cached_source = cached.get("source")
    fresh_source = fresh.get("source")
    return not (cached_source and fresh_source and cached_source != fresh_source)


def refresh_cached_entry(cached: dict, fresh: dict, *, date_field: str = "date") -> dict:
    """Overlay mutable upstream metadata while preserving cache-local state."""
    updated = dict(cached)

    synthetic_title = bool(fresh.get(SYNTHETIC_TITLE_FIELD))
    title = fresh.get("title")
    if _meaningful(title) and not synthetic_title:
        updated["title"] = title

    for field in ("source", date_field):
        value = fresh.get(field)
        if _meaningful(value):
            updated[field] = value

    description = fresh.get("description")
    if _meaningful(description):
        # multi_rss falls back to the title when a native feed omits a body.
        # A synthesized title/description pair is not upstream metadata and
        # must not degrade whatever the cache already knows.
        fallback = description == fresh.get("title")
        cached_description = cached.get("description")
        cached_title = cached.get("title")
        if not (
            (synthetic_title and fallback)
            or (
                fallback
                and _meaningful(cached_description)
                and cached_description != cached_title
            )
        ):
            updated["description"] = description

    image = fresh.get("image")
    if _meaningful(image):
        image_changed = image != updated.get("image")
        updated["image"] = image
        for field in _IMAGE_DIMENSIONS:
            value = fresh.get(field)
            if _meaningful(value):
                updated[field] = value
            elif image_changed:
                updated.pop(field, None)

    return updated


def merge_refreshed_entries(
    fresh_entries: list[dict],
    cached_entries: list[dict],
    *,
    id_field: str = "link",
    date_field: str = "date",
) -> list[dict]:
    """Merge fresh entries, refreshing only items that existed in the cache.

    Existing entries keep arbitrary persisted fields such as ``entry_id``,
    resolved article URLs, and image lookup state. Identity comparison uses the
    same canonical URL rules as feed dedupe, while the original cached link is
    preserved. Refreshes stay within the cached source, and fresh duplicates
    keep first-occurrence-wins semantics.
    """
    merged = list(cached_entries)
    cached_index: dict[str, int] = {}
    for index, entry in enumerate(cached_entries):
        raw_identity = entry.get(id_field)
        if raw_identity is None:
            continue
        cached_index.setdefault(_identity(raw_identity), index)

    existing_ids = set(cached_index)
    seen_fresh: set[str] = set()

    for entry in fresh_entries:
        identity = _identity(entry[id_field])
        if identity in seen_fresh:
            continue
        seen_fresh.add(identity)

        if identity in cached_index:
            index = cached_index[identity]
            if _same_source(merged[index], entry):
                merged[index] = refresh_cached_entry(
                    merged[index], entry, date_field=date_field
                )
        elif identity not in existing_ids:
            clean = dict(entry)
            clean.pop(SYNTHETIC_TITLE_FIELD, None)
            merged.append(clean)
            existing_ids.add(identity)

    return sort_posts_for_feed(merged, date_field=date_field)
