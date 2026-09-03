"""Mirror the native Kościelec weather Atom feed into Feedseek publication."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from lxml import etree as ET
from urllib3.util import Timeout

import multi_rss
from jsonfeed import write_json_feed
from utils import feedparser_entry_image, get_feeds_dir, write_atomically

FEED_NAME = "weather"
SOURCE_URL = "https://weather.trfny.com/feed.atom"
_PUBLISHED_URL = (
    "https://raw.githubusercontent.com/trvny/feedseek/main/feeds/feed_weather.xml"
)
ATOM = "{http://www.w3.org/2005/Atom}"
MAX_SOURCE_BYTES = 2 * 1024 * 1024
SOURCE_TOTAL_SECONDS = 30.0


def doc_sources():
    return [("Pogoda — Kościelec (Atom)", SOURCE_URL)]


def _redirect_target(current_url: str, location: str) -> str | None:
    target = urljoin(current_url, location)
    source = urlsplit(SOURCE_URL)
    parsed = urlsplit(target)
    if parsed.scheme != "https" or parsed.hostname != source.hostname:
        return None
    return target


def _fetch_source() -> bytes | None:
    """Fetch upstream Atom with bounded I/O and same-host redirects."""
    started = time.monotonic()
    current_url = SOURCE_URL
    timeout: Any = Timeout(total=SOURCE_TOTAL_SECONDS, connect=5, read=5)
    for _ in range(4):
        try:
            with requests.get(
                current_url,
                headers=multi_rss.PLAIN_HEADERS,
                timeout=timeout,
                stream=True,
                allow_redirects=False,
            ) as response:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("Location")
                    target = _redirect_target(current_url, location or "")
                    if not target:
                        multi_rss.logger.warning("Weather Atom unsafe redirect rejected")
                        return None
                    current_url = target
                    continue
                if response.status_code != 200:
                    multi_rss.logger.warning(
                        "Weather Atom fetch failed (HTTP %s)", response.status_code
                    )
                    return None
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_SOURCE_BYTES:
                    multi_rss.logger.warning("Weather Atom response exceeds size limit")
                    return None
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if time.monotonic() - started > SOURCE_TOTAL_SECONDS:
                        multi_rss.logger.warning(
                            "Weather Atom fetch exceeded total deadline"
                        )
                        return None
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_SOURCE_BYTES:
                        multi_rss.logger.warning("Weather Atom response exceeds size limit")
                        return None
                    chunks.append(chunk)
                return b"".join(chunks)
        except (requests.RequestException, ValueError) as exc:
            multi_rss.logger.warning("Weather Atom fetch failed: %s", exc)
            return None
    multi_rss.logger.warning("Weather Atom fetch exceeded redirect limit")
    return None


def _has_required_atom_text(element: ET._Element, name: str) -> bool:
    child = element.find(f"{ATOM}{name}")
    return bool(child is not None and "".join(child.itertext()).strip())


def build_xml(xml: str | bytes) -> bytes | None:
    """Validate upstream Atom and repoint only its feed-level self URL."""
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    xml_parser = ET.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        root = ET.fromstring(xml, parser=xml_parser)
    except ET.XMLSyntaxError:
        return None
    if root.getroottree().docinfo.doctype:
        return None
    entries = root.findall(f"{ATOM}entry")
    if root.tag != f"{ATOM}feed" or not entries:
        return None
    required = ("id", "title", "updated")
    if any(not _has_required_atom_text(root, field) for field in required):
        return None
    if any(
        not _has_required_atom_text(entry, field)
        for entry in entries
        for field in required
    ):
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
    if full:
        multi_rss.logger.debug("Weather generator received compatibility --full flag")
    xml = _fetch_source()
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
    cli_parser = argparse.ArgumentParser(
        description="Publish the Kościelec weather Atom feed"
    )
    cli_parser.add_argument(
        "--full", action="store_true", help="Accepted for generator compatibility"
    )
    sys.exit(0 if main(full=cli_parser.parse_args().full) else 1)
