"""JSON Feed 1.1 sidecar writer.

Every feed this project publishes as ``feeds/feed_<name>.xml`` also gets a
``feeds/feed_<name>.json`` sibling in JSON Feed 1.1 format
(https://jsonfeed.org/version/1.1). It is written from the just-produced XML
so the published Atom/RSS file stays the single source of truth — whatever the
generator emitted (MRSS media, dc:creator, tag-URI ids) is mirrored, not
re-derived. Strictly additive: readers that consume XML ignore the .json.

Called from ``utils.save_atom_feed`` / ``utils.save_rss_feed``; a JSON sidecar
is only written when an XML file is, so the keep-last-good invariant holds (a
failed run that skips the XML leaves the previous .json in place).
"""

import calendar
import json
from datetime import datetime, timezone
from pathlib import Path

JSON_FEED_VERSION = "https://jsonfeed.org/version/1.1"

# Same rel=self base the Atom writer uses (utils.setup_feed_links), pointing at
# the JSON sibling instead of the .xml.
_FEED_URL_TMPL = "https://raw.githubusercontent.com/trvny/feeds/main/feedseek/feeds/feed_{name}.json"


def _rfc3339(struct_time) -> str | None:
    """Convert a feedparser UTC struct_time to an RFC 3339 / ISO 8601 string."""
    if not struct_time:
        return None
    try:
        dt = datetime.fromtimestamp(calendar.timegm(struct_time), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None
    return dt.isoformat().replace("+00:00", "Z")


def _entry_content(entry) -> tuple[str, str]:
    """Return (json_feed_key, value): content_html when markup, else content_text.

    JSON Feed requires at least one of content_html / content_text per item.
    """
    for c in entry.get("content") or []:
        val = (c.get("value") or "").strip()
        if val:
            if (c.get("type") or "").endswith(("html", "xhtml")):
                return "content_html", val
            return "content_text", val
    summary = (entry.get("summary") or "").strip()
    if summary:
        stype = (entry.get("summary_detail") or {}).get("type", "")
        if stype.endswith(("html", "xhtml")):
            return "content_html", summary
        return "content_text", summary
    return "content_text", ""


def build_json_feed(xml_path: Path, feed_name: str, entry_image=None) -> dict:
    """Parse the written feed_<name>.xml and return a JSON Feed 1.1 dict.

    ``entry_image`` is an optional callable (utils.feedparser_entry_image) used
    to lift a per-item image from MRSS/enclosure data.
    """
    import feedparser  # local import: keeps utils import-time light

    parsed = feedparser.parse(str(xml_path))
    f = parsed.feed

    doc: dict = {
        "version": JSON_FEED_VERSION,
        "title": f.get("title") or feed_name,
        "feed_url": _FEED_URL_TMPL.format(name=feed_name),
    }
    if f.get("link"):
        doc["home_page_url"] = f["link"]
    if f.get("subtitle"):
        doc["description"] = f["subtitle"]
    if f.get("icon"):
        doc["favicon"] = f["icon"]

    items = []
    for e in parsed.entries:
        item: dict = {"id": e.get("id") or e.get("link") or ""}
        if e.get("link"):
            item["url"] = e["link"]
        if e.get("title"):
            item["title"] = e["title"]

        ckey, cval = _entry_content(e)
        item[ckey] = cval

        if dp := _rfc3339(e.get("published_parsed")):
            item["date_published"] = dp
        if dm := _rfc3339(e.get("updated_parsed")):
            item["date_modified"] = dm

        if e.get("author"):
            item["authors"] = [{"name": e["author"]}]

        if entry_image and (img := entry_image(e)):
            item["image"] = img

        if tags := [t.get("term") for t in (e.get("tags") or []) if t.get("term")]:
            item["tags"] = tags

        attachments = []
        for enc in e.get("enclosures") or []:
            href = enc.get("href")
            if not href:
                continue
            att = {"url": href, "mime_type": enc.get("type") or "application/octet-stream"}
            length = enc.get("length")
            if length and str(length).isdigit() and int(length) > 0:
                att["size_in_bytes"] = int(length)
            attachments.append(att)
        if attachments:
            item["attachments"] = attachments

        items.append(item)

    doc["items"] = items
    return doc


def write_json_feed(xml_path: Path, feed_name: str, entry_image=None) -> Path:
    """Write feeds/feed_<name>.json next to the given XML path. Returns the path."""
    doc = build_json_feed(xml_path, feed_name, entry_image=entry_image)
    out = xml_path.with_suffix(".json")
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
