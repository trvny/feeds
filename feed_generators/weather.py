"""Mirror the native Kościelec weather Atom feed into Feedseek publication."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

import multi_rss
from jsonfeed import write_json_feed
from utils import feedparser_entry_image, get_feeds_dir, write_atomically

FEED_NAME = "weather"
SOURCE_URL = "https://weather.trfny.com/feed.atom"
_PUBLISHED_URL = (
    "https://raw.githubusercontent.com/trvny/feedseek/main/feeds/feed_weather.xml"
)
ATOM = "{http://www.w3.org/2005/Atom}"
ET.register_namespace("", "http://www.w3.org/2005/Atom")


def doc_sources():
    return [("Pogoda — Kościelec (Atom)", SOURCE_URL)]


def build_xml(xml: str) -> bytes | None:
    """Validate upstream Atom and repoint only its feed-level self URL."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    if root.tag != f"{ATOM}feed" or not root.findall(f"{ATOM}entry"):
        return None
    self_links = [
        link for link in root.findall(f"{ATOM}link") if link.get("rel") == "self"
    ]
    if not self_links:
        return None
    self_links[0].set("href", _PUBLISHED_URL)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def clean_json_feed(doc: dict) -> dict:
    """Remove feedparser's synthetic non-web URLs from id-only Atom entries."""
    for item in doc.get("items", []):
        url = str(item.get("url") or "").strip()
        if url and urlsplit(url).scheme not in {"http", "https"}:
            item.pop("url", None)
    return doc


def save_mirrored_atom(payload: bytes) -> None:
    """Publish XML + JSON as one last-known-good pair with full rollback."""
    output = get_feeds_dir() / f"feed_{FEED_NAME}.xml"
    json_output = output.with_suffix(".json")
    previous_xml = output.read_bytes() if output.exists() else None
    previous_json = json_output.read_bytes() if json_output.exists() else None
    write_atomically(output, lambda target: target.write_bytes(payload))
    try:
        write_json_feed(output, FEED_NAME, entry_image=feedparser_entry_image)
        doc = clean_json_feed(json.loads(json_output.read_text(encoding="utf-8")))
        rendered = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        write_atomically(
            json_output, lambda target: target.write_text(rendered, encoding="utf-8")
        )
    except Exception:
        if previous_xml is None:
            output.unlink(missing_ok=True)
        else:
            write_atomically(output, lambda target: target.write_bytes(previous_xml))
        if previous_json is None:
            json_output.unlink(missing_ok=True)
        else:
            write_atomically(
                json_output, lambda target: target.write_bytes(previous_json)
            )
        raise


def main(full: bool = False) -> bool:
    del full
    xml = multi_rss.get_html(SOURCE_URL)
    if not xml:
        return False
    payload = build_xml(xml)
    if payload is None:
        multi_rss.logger.warning(
            "Weather Atom feed had no usable entries/self link; preserving last good output"
        )
        return False
    save_mirrored_atom(payload)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Publish the Kościelec weather Atom feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Accepted for generator compatibility"
    )
    sys.exit(0 if main(full=parser.parse_args().full) else 1)
