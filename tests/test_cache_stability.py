"""Cache writes should reflect state changes, not cron executions."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import utils


class CacheStabilityTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.cache_file = Path(self.tempdir.name) / "demo_posts.json"
        self.file_patch = mock.patch.object(
            utils, "get_cache_file", return_value=self.cache_file
        )
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)
        self.entries = [
            {
                "title": "Example",
                "link": "https://example.com/post",
                "date": "2026-08-25T06:00:00+00:00",
            }
        ]

    def test_unchanged_payload_does_not_rewrite_cache(self):
        utils.save_cache("demo", self.entries)
        before = json.loads(self.cache_file.read_text(encoding="utf-8"))

        with mock.patch.object(utils, "write_atomically") as write:
            utils.save_cache("demo", self.entries)

        write.assert_not_called()
        after = json.loads(self.cache_file.read_text(encoding="utf-8"))
        self.assertEqual(after["last_updated"], before["last_updated"])

    def test_entry_change_rewrites_cache(self):
        utils.save_cache("demo", self.entries)
        changed = [dict(self.entries[0], title="Updated title")]

        with mock.patch.object(utils, "write_atomically") as write:
            utils.save_cache("demo", changed)

        write.assert_called_once()

    def test_extra_change_rewrites_cache(self):
        utils.save_cache("demo", self.entries, extra={"failures": 1})

        with mock.patch.object(utils, "write_atomically") as write:
            utils.save_cache("demo", self.entries, extra={"failures": 2})

        write.assert_called_once()

    def test_boolean_and_integer_are_distinct_json_values(self):
        utils.save_cache("demo", self.entries, extra={"flag": 1})

        with mock.patch.object(utils, "write_atomically") as write:
            utils.save_cache("demo", self.entries, extra={"flag": True})

        write.assert_called_once()

    def test_missing_timestamp_is_repaired(self):
        self.cache_file.write_text(
            json.dumps({"entries": self.entries}), encoding="utf-8"
        )

        with mock.patch.object(utils, "write_atomically") as write:
            utils.save_cache("demo", self.entries)

        write.assert_called_once()

    def test_invalid_timestamp_is_repaired(self):
        self.cache_file.write_text(
            json.dumps({"last_updated": "nope", "entries": self.entries}),
            encoding="utf-8",
        )

        with mock.patch.object(utils, "write_atomically") as write:
            utils.save_cache("demo", self.entries)

        write.assert_called_once()


if __name__ == "__main__":
    unittest.main()
