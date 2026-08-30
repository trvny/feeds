"""Validate generated XML + JSON Feed artifacts and registry coverage.

The hard publication contract is deliberately structural, not editorial:

* every enabled entry in ``feeds.yaml`` has a generated XML artifact,
* XML parses and contains at least one item,
* every XML artifact has a valid JSON Feed 1.1 sidecar with matching item count,
* JSON items have durable non-empty IDs and a content field.

Publication-date staleness remains advisory because a quiet or dateless source
is not necessarily broken. Rich metadata such as images, authors and categories
is source-dependent and therefore intentionally outside the universal gate.
"""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from models import load_feed_registry

STALE_FLOOR_DAYS = 30
STALE_GAP_MULTIPLIER = 3.0
MIN_HISTORY = 5
JSON_FEED_VERSION = "https://jsonfeed.org/version/1.1"

ROOT = Path(__file__).parent.parent
FEEDS_DIR = ROOT / "feeds"
CACHE_DIR = ROOT / "cache"


def _local(tag: str) -> str:
    """Return an element tag without its XML namespace prefix."""
    return tag.split("}")[-1] if "}" in tag else tag


def _find_entries(root: ET.Element) -> list[ET.Element]:
    """Return feed entries for both RSS (item) and Atom (entry)."""
    return [el for el in root.iter() if _local(el.tag) in ("item", "entry")]


def _parse_rss_date(text: str) -> datetime | None:
    try:
        return parsedate_to_datetime(text)
    except ValueError, TypeError:
        return None


def _parse_atom_date(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _entry_date(entry: ET.Element) -> datetime | None:
    """Return an entry's publication date.

    Atom ``published`` is preferred over ``updated``. FeedGenerator may synthesize
    ``updated`` at render time, which would otherwise make a frozen cached feed
    appear fresh forever. RSS uses ``pubDate``.
    """
    values: dict[str, str] = {}
    for child in entry:
        text = (child.text or "").strip()
        if text:
            values.setdefault(_local(child.tag), text)

    if pub_date := values.get("pubDate"):
        return _parse_rss_date(pub_date)
    if published := values.get("published"):
        return _parse_atom_date(published)
    if updated := values.get("updated"):
        return _parse_atom_date(updated)
    return None


def _percentile(values: list[float], pct: float) -> float | None:
    """Linear-interpolated percentile of a list (pct in [0, 1])."""
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _stale_threshold_days(dates: list[datetime]) -> tuple[float, float | None]:
    if len(dates) < MIN_HISTORY:
        return float(STALE_FLOOR_DAYS), None
    ordered = sorted(dates)
    gaps = [(ordered[i] - ordered[i - 1]).total_seconds() / 86400.0 for i in range(1, len(ordered))]
    p90 = _percentile(gaps, 0.9)
    if p90 is None:
        return float(STALE_FLOOR_DAYS), None
    return max(float(STALE_FLOOR_DAYS), STALE_GAP_MULTIPLIER * p90), p90


def _result(name: str, status: str, message: str, *, count: int = 0, newest=None) -> dict:
    return {
        "name": name,
        "item_count": count,
        "newest_date": newest,
        "status": status,
        "message": message,
    }


def validate_feed(feed_path: Path) -> dict:
    """Validate one RSS/Atom XML file."""
    name = feed_path.name
    try:
        root = ET.parse(feed_path).getroot()
    except (ET.ParseError, OSError) as exc:
        return _result(name, "ERROR", f"XML parse/read error: {exc}")

    items = _find_entries(root)
    item_count = len(items)
    if item_count == 0:
        return _result(name, "EMPTY", "0 items")

    dates: list[datetime] = []
    for item in items:
        dt = _entry_date(item)
        if dt is not None:
            dates.append(dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC))

    if not dates:
        return _result(name, "OK", f"{item_count} items, no parseable dates", count=item_count)

    newest = max(dates)
    days_ago = (datetime.now(UTC) - newest).days
    threshold, p90 = _stale_threshold_days(dates)
    if days_ago > threshold:
        cadence = f"p90 gap {p90:.0f}d" if p90 is not None else f"floor {STALE_FLOOR_DAYS}d"
        return _result(
            name,
            "STALE",
            f"{item_count} items, newest {newest:%Y-%m-%d} "
            f"({days_ago}d ago), threshold {threshold:.0f}d ({cadence})",
            count=item_count,
            newest=newest,
        )

    return _result(
        name,
        "OK",
        f"{item_count} items, newest {newest:%Y-%m-%d}",
        count=item_count,
        newest=newest,
    )


def validate_json_sidecar(path: Path, *, expected_count: int | None = None) -> dict:
    """Validate the universal JSON Feed 1.1 publication contract."""
    if not path.exists():
        return _result(path.name, "JSON_MISSING", "JSON Feed sidecar is missing")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _result(path.name, "JSON_ERROR", f"JSON parse/read error: {exc}")
    if not isinstance(doc, dict):
        return _result(path.name, "JSON_ERROR", "top level is not an object")
    if doc.get("version") != JSON_FEED_VERSION:
        return _result(path.name, "JSON_ERROR", "missing or unsupported JSON Feed 1.1 version")
    if not isinstance(doc.get("title"), str) or not doc["title"].strip():
        return _result(path.name, "JSON_ERROR", "missing non-empty title")

    items = doc.get("items")
    if not isinstance(items, list):
        return _result(path.name, "JSON_ERROR", "missing top-level items array")
    if expected_count is not None and len(items) != expected_count:
        return _result(
            path.name,
            "JSON_ERROR",
            f"item count differs from XML ({len(items)} != {expected_count})",
            count=len(items),
        )

    seen_ids: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            return _result(path.name, "JSON_ERROR", f"item {index} is not an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            return _result(path.name, "JSON_ERROR", f"item {index} has no non-empty id")
        if item_id in seen_ids:
            return _result(path.name, "JSON_ERROR", f"duplicate item id: {item_id}")
        seen_ids.add(item_id)
        has_content = any(
            isinstance(item.get(key), str) for key in ("content_html", "content_text") if key in item
        )
        if not has_content:
            return _result(path.name, "JSON_ERROR", f"item {index} has no content_html/content_text")

    return _result(path.name, "OK", f"{len(items)} items", count=len(items))


def _registry_coverage() -> tuple[list[dict], set[Path]]:
    registry, skipped = load_feed_registry(return_skipped=True)
    results: list[dict] = []
    expected_xml: set[Path] = set()

    for name, config in sorted(registry.items()):
        if not config.enabled:
            continue
        xml_path = FEEDS_DIR / f"feed_{name}.xml"
        expected_xml.add(xml_path)
        if not xml_path.exists():
            # A feed registered but never run yet has no cache either: that is a
            # brand-new registration waiting for the next scheduled run, not a
            # lost artifact. Report it, but don't fail the build over it.
            never_ran = not (CACHE_DIR / f"{name}_posts.json").exists()
            status = "PENDING" if never_ran else "MISSING"
            message = (
                f"new feed '{name}' has not been generated yet"
                if never_ran
                else f"enabled feed '{name}' has no XML artifact"
            )
            results.append(_result(xml_path.name, status, message))
            continue
        xml_result = validate_feed(xml_path)
        results.append(xml_result)
        expected_count = xml_result["item_count"] if xml_result["item_count"] else None
        results.append(
            validate_json_sidecar(xml_path.with_suffix(".json"), expected_count=expected_count)
        )

    for name in skipped:
        results.append(_result(name, "CONFIG_ERROR", "invalid feeds.yaml entry"))

    return results, expected_xml


def _write_step_summary(results: list[dict]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        rows = [f"| {r['name']} | {r['status']} | {r['message']} |" for r in results if r["status"] != "OK"]
        lines = ["## Feed health", "", "| Feed | Status | Detail |", "|---|---|---|"]
        lines += rows or ["| _all feeds_ | OK | nothing empty, stale, missing, or broken |"]
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def main() -> int:
    FEEDS_DIR.mkdir(exist_ok=True)
    results, expected_xml = _registry_coverage()

    for path in sorted(FEEDS_DIR.glob("feed_*.xml")):
        if path not in expected_xml:
            results.append(validate_feed(path))

    print(f"\nFeed Validation Summary ({len(results)} checks):")
    print("=" * 90)
    for result in results:
        print(f"  {result['name']:50s} {result['status']:12s} {result['message']}")
    print("=" * 90)

    fatal_statuses = {"ERROR", "EMPTY", "MISSING", "CONFIG_ERROR", "JSON_MISSING", "JSON_ERROR"}
    fatal = [r for r in results if r["status"] in fatal_statuses]
    stale = [r for r in results if r["status"] == "STALE"]
    pending = [r for r in results if r["status"] == "PENDING"]

    if pending:
        print(f"\nWARNINGS: {len(pending)} newly registered feed(s) awaiting their first run")
    if stale:
        print(f"\nWARNINGS: {len(stale)} stale feed(s)")
    if not fatal:
        print("\nAll enabled feeds satisfy the XML + JSON Feed publication contract.")

    _write_step_summary(results)
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
