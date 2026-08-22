"""The attempt ledger that stops skillsllm refetching dead URLs forever.

A discovered URL that fails to fetch, or yields no <title>, caches nothing, so
the next run rediscovers it from the same sitemap and pays for the same three
retries again — every two hours, indefinitely. The ledger counts those failures
across runs and gives up at the cap, while still not growing without bound.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import utils  # noqa: E402
from skillsllm import MAX_FETCH_ATTEMPTS, AttemptLedger  # noqa: E402


class AttemptLedgerTests(unittest.TestCase):
    def test_counts_up_to_the_cap_then_gives_up(self):
        previous = {}
        for expected in range(1, MAX_FETCH_ATTEMPTS + 1):
            ledger = AttemptLedger(previous)
            self.assertFalse(ledger.exhausted("https://x.test/a"))
            ledger.failed("https://x.test/a")
            self.assertEqual(ledger.current["https://x.test/a"], expected)
            previous = ledger.current

        ledger = AttemptLedger(previous)
        self.assertTrue(ledger.exhausted("https://x.test/a"))
        self.assertEqual(ledger.skipped, 1)

    def test_exhausted_url_keeps_its_count_while_still_discovered(self):
        ledger = AttemptLedger({"https://x.test/a": MAX_FETCH_ATTEMPTS})
        ledger.exhausted("https://x.test/a")
        self.assertEqual(ledger.current, {"https://x.test/a": MAX_FETCH_ATTEMPTS})

    def test_url_that_stops_being_discovered_drops_out(self):
        """The bound on growth: the ledger is rebuilt from what this run saw."""
        ledger = AttemptLedger({"https://x.test/gone": 2, "https://x.test/here": 1})
        ledger.failed("https://x.test/here")
        self.assertEqual(ledger.current, {"https://x.test/here": 2})

    def test_success_leaves_no_trace(self):
        ledger = AttemptLedger({"https://x.test/a": 2})
        self.assertFalse(ledger.exhausted("https://x.test/a"))
        self.assertEqual(ledger.current, {})

    def test_garbage_counts_are_ignored(self):
        """A hand-edited or half-written cache must not crash the run."""
        ledger = AttemptLedger({"https://x.test/a": "lots", "https://x.test/b": None})
        self.assertFalse(ledger.exhausted("https://x.test/a"))
        ledger.failed("https://x.test/a")
        self.assertEqual(ledger.current, {"https://x.test/a": 1})

    def test_empty_and_missing_previous_are_both_fine(self):
        self.assertEqual(AttemptLedger().current, {})
        self.assertEqual(AttemptLedger(None).current, {})


class SaveCacheExtraTests(unittest.TestCase):
    def write(self, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feed.json"
            with mock.patch.object(utils, "get_cache_file", return_value=path):
                utils.save_cache("feed", [{"link": "a", "date": "2026-01-01"}], **kwargs)
            return json.loads(path.read_text(encoding="utf-8"))

    def test_extra_keys_land_next_to_the_entries(self):
        data = self.write(extra={"unresolvable": {"https://x.test/a": 3}})
        self.assertEqual(data["unresolvable"], {"https://x.test/a": 3})
        self.assertEqual(len(data["entries"]), 1)

    def test_reserved_keys_are_refused(self):
        for key in ("entries", "last_updated"):
            with self.assertRaises(ValueError):
                self.write(extra={key: "clobbered"})

    def test_no_extra_leaves_the_cache_shape_unchanged(self):
        self.assertEqual(set(self.write()), {"last_updated", "entries"})


if __name__ == "__main__":
    unittest.main()
