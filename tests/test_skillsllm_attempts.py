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


A = "https://x.test/a"
B = "https://x.test/b"
BLOG = "Mem0 Blog"
RESEARCH = "Mem0 Research"


class AttemptLedgerTests(unittest.TestCase):
    def test_counts_up_to_the_cap_then_gives_up(self):
        previous = {}
        for expected in range(1, MAX_FETCH_ATTEMPTS + 1):
            ledger = AttemptLedger(previous)
            ledger.listed(BLOG)
            self.assertFalse(ledger.exhausted(BLOG, A))
            ledger.failed(BLOG, A)
            self.assertEqual(ledger.current[BLOG][A], expected)
            previous = ledger.current

        ledger = AttemptLedger(previous)
        ledger.listed(BLOG)
        self.assertTrue(ledger.exhausted(BLOG, A))
        self.assertEqual(ledger.skipped, 1)

    def test_exhausted_url_keeps_its_count_while_still_listed(self):
        ledger = AttemptLedger({BLOG: {A: MAX_FETCH_ATTEMPTS}})
        ledger.listed(BLOG)
        ledger.exhausted(BLOG, A)
        self.assertEqual(ledger.current, {BLOG: {A: MAX_FETCH_ATTEMPTS}})

    def test_url_that_stops_being_listed_drops_out(self):
        """The bound on growth: a link gone from a listing we did read is dropped."""
        ledger = AttemptLedger({BLOG: {A: 2, B: 1}})
        ledger.listed(BLOG)
        ledger.failed(BLOG, B)
        self.assertEqual(ledger.current, {BLOG: {B: 2}})

    def test_unreachable_source_keeps_its_counts(self):
        """An outage must not reset dead URLs to zero — that defeats the cap."""
        ledger = AttemptLedger({BLOG: {A: MAX_FETCH_ATTEMPTS}, RESEARCH: {B: 1}})
        ledger.listed(RESEARCH)  # only this source answered
        ledger.failed(RESEARCH, B)
        self.assertEqual(
            ledger.current, {BLOG: {A: MAX_FETCH_ATTEMPTS}, RESEARCH: {B: 2}}
        )

    def test_sources_sharing_a_host_are_kept_apart(self):
        """Mem0 Blog and Mem0 Research both read mem0.ai but fail independently."""
        same_host_a = "https://mem0.ai/blog/x"
        same_host_b = "https://mem0.ai/research/y"
        ledger = AttemptLedger(
            {BLOG: {same_host_a: 1}, RESEARCH: {same_host_b: MAX_FETCH_ATTEMPTS}}
        )
        ledger.listed(BLOG)  # the blog sitemap answered; the research one did not
        self.assertEqual(
            ledger.current, {RESEARCH: {same_host_b: MAX_FETCH_ATTEMPTS}}
        )

    def test_nothing_listed_at_all_carries_everything(self):
        previous = {BLOG: {A: 1}, RESEARCH: {B: 2}}
        self.assertEqual(AttemptLedger(previous).current, previous)

    def test_success_leaves_no_trace(self):
        ledger = AttemptLedger({BLOG: {A: 2}})
        ledger.listed(BLOG)
        self.assertFalse(ledger.exhausted(BLOG, A))
        self.assertEqual(ledger.current, {})

    def test_garbage_is_ignored(self):
        """A hand-edited or half-written cache must not crash the run."""
        ledger = AttemptLedger(
            {BLOG: {A: "lots", B: None}, RESEARCH: "wat", "Empty": {}}
        )
        ledger.listed(BLOG)
        self.assertFalse(ledger.exhausted(BLOG, A))
        ledger.failed(BLOG, A)
        self.assertEqual(ledger.current, {BLOG: {A: 1}})

    def test_booleans_are_not_attempt_counts(self):
        ledger = AttemptLedger({BLOG: {A: True}})
        self.assertEqual(ledger.current, {})

    def test_non_mapping_previous_is_survivable(self):
        for junk in ("", "wat", [1, 2], 7):
            self.assertEqual(AttemptLedger(junk).current, {})

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
