"""Validate all RSS feeds for empty content and stale items.

STALE detection is adaptive per feed. Instead of one flat age threshold for
every feed, each feed's own publishing cadence -- the p90 gap between its
entries -- sets how long it may go quiet before it's flagged. A rare-by-design
source (monthly or slower) no longer false-positives; a normally-frequent feed
that suddenly goes silent -- the usual signature of a silently broken parser
that fell back to the last-good XML -- still trips.

Exit status is non-zero only for EMPTY feeds or XML parse errors (the CI gate).
STALE is advisory and never fails the run, since a quiet source is not a bug.
"""

import os
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

# STALE when: days_since_newest > max(STALE_FLOOR_DAYS, GAP_MULTIPLIER * p90_gap)
# The floor is the minimum patience for fast feeds, so a one-day quiet spell on
# an hourly feed doesn't flag. The gap term stretches the window for slow feeds.
STALE_FLOOR_DAYS = 30
STALE_GAP_MULTIPLIER = 3.0
# Minimum dated entries needed to trust a cadence estimate. Below this there is
# too little history, so fall back to the flat floor instead of guessing.
MIN_HISTORY = 5

FEEDS_DIR = Path(__file__).parent.parent / "feeds"


def _local(tag):
    """Return an element tag without its XML namespace prefix."""
    return tag.split("}")[-1] if "}" in tag else tag


def _find_entries(root):
    """Return feed entries for both RSS (<item>) and Atom (<entry>)."""
    return [el for el in root.iter() if _local(el.tag) in ("item", "entry")]


def _entry_date(entry):
    """Parse an entry's date from RSS pubDate or Atom updated/published."""
    for child in entry:
        tag = _local(child.tag)
        text = (child.text or "").strip()
        if not text:
            continue
        if tag == "pubDate":
            try:
                return parsedate_to_datetime(text)
            except (ValueError, TypeError):
                return None
        if tag in ("updated", "published"):
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
    return None


def _percentile(values, pct):
    """Linear-interpolated percentile of a list (pct in [0, 1]); stdlib only."""
    s = sorted(values)
    if not s:
        return None
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _stale_threshold_days(dates):
    """Adaptive staleness window (days) for a feed, from its own cadence.

    Returns (threshold_days, p90_gap_days_or_None). With fewer than MIN_HISTORY
    dated entries there is not enough history to estimate cadence, so the flat
    floor is used and p90 is returned as None.
    """
    if len(dates) < MIN_HISTORY:
        return float(STALE_FLOOR_DAYS), None
    ordered = sorted(dates)
    gaps = [(ordered[i] - ordered[i - 1]).total_seconds() / 86400.0 for i in range(1, len(ordered))]
    p90 = _percentile(gaps, 0.9)
    return max(float(STALE_FLOOR_DAYS), STALE_GAP_MULTIPLIER * p90), p90


def validate_feed(feed_path):
    """Validate a single feed file.

    Returns:
        dict with keys: name, item_count, newest_date, status, message
    """
    name = feed_path.name
    try:
        tree = ET.parse(feed_path)
    except ET.ParseError as e:
        return {
            "name": name,
            "item_count": 0,
            "newest_date": None,
            "status": "ERROR",
            "message": f"XML parse error: {e}",
        }

    root = tree.getroot()
    items = _find_entries(root)
    item_count = len(items)

    if item_count == 0:
        return {
            "name": name,
            "item_count": 0,
            "newest_date": None,
            "status": "EMPTY",
            "message": "0 items",
        }

    # Collect every parseable entry date (RSS pubDate or Atom updated/published);
    # the full set drives the adaptive cadence estimate, not just the newest.
    dates = []
    for item in items:
        dt = _entry_date(item)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            dates.append(dt)

    if not dates:
        return {
            "name": name,
            "item_count": item_count,
            "newest_date": None,
            "status": "OK",
            "message": f"{item_count} items, no parseable dates",
        }

    newest = max(dates)
    days_ago = (datetime.now(UTC) - newest).days
    threshold, p90 = _stale_threshold_days(dates)

    if days_ago > threshold:
        cadence = f"p90 gap {p90:.0f}d" if p90 is not None else f"floor {STALE_FLOOR_DAYS}d"
        return {
            "name": name,
            "item_count": item_count,
            "newest_date": newest,
            "status": "STALE",
            "message": (
                f"{item_count} items, newest {newest.strftime('%Y-%m-%d')} "
                f"({days_ago}d ago), threshold {threshold:.0f}d ({cadence})"
            ),
        }

    return {
        "name": name,
        "item_count": item_count,
        "newest_date": newest,
        "status": "OK",
        "message": f"{item_count} items, newest {newest.strftime('%Y-%m-%d')}",
    }


def _write_step_summary(results):
    """Append a non-OK feed table to $GITHUB_STEP_SUMMARY when running in CI.

    Best-effort: surfacing the health table must never fail the workflow.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        rows = [f"| {r['name']} | {r['status']} | {r['message']} |" for r in results if r["status"] != "OK"]
        lines = ["## Feed health", "", "| Feed | Status | Detail |", "|---|---|---|"]
        lines += rows or ["| _all feeds_ | OK | nothing empty, stale, or broken |"]
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def main():
    feeds = sorted(FEEDS_DIR.glob("feed_*.xml"))

    if not feeds:
        print("No feed files found in feeds/ yet (nothing to validate).")
        return

    results = [validate_feed(f) for f in feeds]

    # Print summary
    print(f"\nFeed Validation Summary ({len(results)} feeds):")
    print(f"{'=' * 70}")

    for r in results:
        print(f"  {r['name']:50s} {r['status']:5s}  {r['message']}")

    empty = [r for r in results if r["status"] == "EMPTY"]
    stale = [r for r in results if r["status"] == "STALE"]
    errors = [r for r in results if r["status"] == "ERROR"]

    print(f"{'=' * 70}")

    if errors:
        print(f"\nERRORS: {len(errors)} feed(s) with XML parse errors")
        for r in errors:
            print(f"  {r['name']}: {r['message']}")

    if empty:
        print(f"\nERRORS: {len(empty)} empty feed(s)")
        for r in empty:
            print(f"  {r['name']}")

    if stale:
        print(f"\nWARNINGS: {len(stale)} stale feed(s) (adaptive per-feed cadence)")
        for r in stale:
            print(f"  {r['name']}: {r['message']}")

    if not empty and not errors:
        print("\nAll feeds have content.")

    _write_step_summary(results)

    # Exit 1 only for empty or parse-error feeds; STALE is advisory.
    if empty or errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
