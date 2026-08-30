import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from validate_feeds import JSON_FEED_VERSION, _entry_date, validate_json_sidecar  # noqa: E402


class EntryDateTests(unittest.TestCase):
    def test_atom_published_wins_over_synthetic_updated(self):
        entry = ET.fromstring(
            """
            <entry xmlns="http://www.w3.org/2005/Atom">
              <updated>2026-07-22T10:32:09+00:00</updated>
              <published>2025-01-02T03:04:05+00:00</published>
            </entry>
            """
        )
        self.assertEqual(_entry_date(entry), datetime.fromisoformat("2025-01-02T03:04:05+00:00"))

    def test_atom_updated_is_used_when_published_is_absent(self):
        entry = ET.fromstring(
            """
            <entry xmlns="http://www.w3.org/2005/Atom">
              <updated>2026-07-22T10:32:09Z</updated>
            </entry>
            """
        )
        self.assertEqual(_entry_date(entry), datetime.fromisoformat("2026-07-22T10:32:09+00:00"))


class JsonFeedContractTests(unittest.TestCase):
    def write_feed(self, doc):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "feed_demo.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def valid_doc(self):
        return {
            "version": JSON_FEED_VERSION,
            "title": "Demo",
            "items": [
                {"id": "one", "content_text": "First"},
                {"id": "two", "content_html": "<p>Second</p>"},
            ],
        }

    def test_valid_json_feed_matches_xml_count(self):
        result = validate_json_sidecar(self.write_feed(self.valid_doc()), expected_count=2)
        self.assertEqual(result["status"], "OK")

    def test_wrong_version_is_fatal_quality_error(self):
        doc = self.valid_doc()
        doc["version"] = "https://jsonfeed.org/version/1"
        result = validate_json_sidecar(self.write_feed(doc), expected_count=2)
        self.assertEqual(result["status"], "JSON_ERROR")

    def test_json_item_count_must_match_xml(self):
        result = validate_json_sidecar(self.write_feed(self.valid_doc()), expected_count=3)
        self.assertEqual(result["status"], "JSON_ERROR")
        self.assertIn("differs from XML", result["message"])

    def test_duplicate_ids_are_rejected(self):
        doc = self.valid_doc()
        doc["items"][1]["id"] = "one"
        result = validate_json_sidecar(self.write_feed(doc), expected_count=2)
        self.assertEqual(result["status"], "JSON_ERROR")

    def test_source_dependent_metadata_is_not_required(self):
        doc = {
            "version": JSON_FEED_VERSION,
            "title": "Sparse but valid",
            "items": [{"id": "one", "content_text": ""}],
        }
        result = validate_json_sidecar(self.write_feed(doc), expected_count=1)
        self.assertEqual(result["status"], "OK")


if __name__ == "__main__":
    unittest.main()
