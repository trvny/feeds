"""Cache trimming: keep the newest entries, drop the oldest.

Guards the bound on cache growth. Without it every entry ever seen was kept —
4chan reached 21 109 entries to publish a 200-entry feed, and the directory hit
49.9 MB on its way to the 128 MB ceiling above which the R2 backup silently
stops refreshing.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from utils import DEFAULT_CACHE_LIMIT, trim_entries  # noqa: E402


def dated(n, day_offset=0):
    """n entries sorted ascending by date, as sort_posts_for_feed leaves them."""
    return [
        {"date": f"2026-01-01T00:{i:02d}:00+00:00", "n": i + day_offset} for i in range(n)
    ]


class TrimEntriesTests(unittest.TestCase):
    def test_keeps_newest_and_drops_oldest(self):
        entries = dated(10)
        trimmed = trim_entries(entries, limit=3)
        self.assertEqual([e["n"] for e in trimmed], [7, 8, 9])

    def test_preserves_ascending_order(self):
        trimmed = trim_entries(dated(50), limit=10)
        dates = [e["date"] for e in trimmed]
        self.assertEqual(dates, sorted(dates))

    def test_noop_below_limit(self):
        entries = dated(5)
        self.assertIs(trim_entries(entries, limit=100), entries)

    def test_noop_at_exactly_the_limit(self):
        entries = dated(7)
        self.assertIs(trim_entries(entries, limit=7), entries)

    def test_limit_none_disables_trimming(self):
        entries = dated(10_000)
        self.assertIs(trim_entries(entries, limit=None), entries)

    def test_dateless_entries_survive_without_displacing_recent_ones(self):
        # sort_posts_for_feed parks dateless entries after the dated ones, so a
        # plain entries[-limit:] would keep those in preference to fresh items.
        entries = dated(10) + [{"date": None, "n": "x"}]
        trimmed = trim_entries(entries, limit=3)
        self.assertEqual([e["n"] for e in trimmed], [7, 8, 9, "x"])

    def test_alternative_date_field(self):
        entries = [{"published": f"2026-01-0{i}", "n": i} for i in range(1, 6)]
        trimmed = trim_entries(entries, limit=2, date_field="published")
        self.assertEqual([e["n"] for e in trimmed], [4, 5])

    def test_busy_source_cannot_starve_a_quiet_one(self):
        # The real shape this guards: tvp's cache held 4345 TVP Sport and 4167
        # TVP Info entries against 39 TVP Informacje. A recency-only slice would
        # have been ~97% the two busy sources and dropped the quiet ones whole.
        busy = [
            {"date": f"2026-01-02T00:{i:02d}:00+00:00", "source": "busy", "n": i}
            for i in range(50)
        ]
        quiet = [
            {"date": f"2026-01-01T00:{i:02d}:00+00:00", "source": "quiet", "n": f"q{i}"}
            for i in range(3)
        ]
        entries = sorted(quiet + busy, key=lambda e: e["date"])  # quiet is older
        trimmed = trim_entries(entries, limit=10)
        kept_sources = {e["source"] for e in trimmed}
        self.assertIn("quiet", kept_sources, "quiet source was starved out")
        self.assertEqual(sum(e["source"] == "quiet" for e in trimmed), 3)
        self.assertEqual(len(trimmed), 10)

    def test_single_source_behaves_like_a_plain_recency_trim(self):
        entries = [
            {"date": f"2026-01-01T00:{i:02d}:00+00:00", "source": "only", "n": i}
            for i in range(20)
        ]
        self.assertEqual([e["n"] for e in trim_entries(entries, limit=5)], [15, 16, 17, 18, 19])

    def test_backfills_unused_quota_by_recency(self):
        # quiet cannot fill its share, so busy takes the remainder rather than
        # the result coming back short.
        busy = [
            {"date": f"2026-01-02T00:{i:02d}:00+00:00", "source": "busy", "n": i}
            for i in range(30)
        ]
        quiet = [{"date": "2026-01-01T00:00:00+00:00", "source": "quiet", "n": "q"}]
        trimmed = trim_entries(sorted(quiet + busy, key=lambda e: e["date"]), limit=10)
        self.assertEqual(len(trimmed), 10)
        self.assertEqual(sum(e["source"] == "quiet" for e in trimmed), 1)

    def test_default_limit_leaves_accumulator_feeds_untouched(self):
        # The largest accumulator documented in docs/feeds.md (beatport_top100)
        # holds 200 entries. Those feeds publish their whole cache, so trimming
        # one would delete published history rather than dedup state.
        largest_accumulator = 200
        entries = dated(largest_accumulator)
        self.assertIs(trim_entries(entries), entries)
        self.assertGreater(DEFAULT_CACHE_LIMIT, largest_accumulator * 5)


if __name__ == "__main__":
    unittest.main()
