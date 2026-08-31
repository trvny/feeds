import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import saas  # pylint: disable=wrong-import-position


class SaasPostmanTests(unittest.TestCase):
    def test_postman_blog_already_uses_native_feed(self):
        feeds = {label: url for label, url, _cap in saas.NATIVE_FEEDS}
        self.assertEqual(feeds["Postman"], "https://blog.postman.com/feed/")

    def test_release_notes_source_is_documented_with_human_page(self):
        sources = dict(saas.doc_sources())
        self.assertEqual(
            sources["Postman App Release Notes"],
            "https://www.postman.com/release-notes/postman-app/",
        )

    def test_release_notes_parser_keeps_only_latest_major(self):
        payload = {
            "notes": [
                {
                    "version": "12.25.7",
                    "content": (
                        "## Postman 12.25.7\nAugust 28, 2026\n\n"
                        "### Bug Fixes\nSome **critical** fixes.\n"
                    ),
                    "createdAt": "2026-08-28T02:32:56.000Z",
                },
                {
                    "version": "12.25.6",
                    "content": (
                        "## Postman 12.25.6\nAugust 27, 2026\n\n"
                        "### What's New\nSee [datasets](https://example.com).\n"
                    ),
                    "createdAt": "2026-08-27T02:32:56.000Z",
                },
                {
                    "version": "11.99.0",
                    "content": "## Postman v11.99.0\nJanuary 1, 2026\nOld major",
                    "createdAt": "2026-01-01T00:00:00.000Z",
                },
                {
                    "version": "99.bad",
                    "content": "Malformed version must not become the newest major",
                    "createdAt": "2026-08-29T00:00:00.000Z",
                },
            ]
        }
        entries = saas.parse_postman_app_release_notes(json.dumps(payload))
        self.assertEqual([entry["title"] for entry in entries], ["Postman 12.25.7", "Postman 12.25.6"])
        self.assertEqual(
            entries[0]["link"],
            "https://www.postman.com/release-notes/postman-app/#12-25-7",
        )
        self.assertEqual(entries[0]["date"].isoformat(), "2026-08-28T00:00:00+00:00")
        self.assertEqual(entries[0]["description"], "Bug Fixes Some critical fixes.")
        self.assertIn("See datasets.", entries[1]["description"])

    def test_release_notes_parser_uses_created_at_when_visible_date_missing(self):
        raw = json.dumps({
            "notes": [{
                "version": "12.1.0",
                "content": "## Postman 12.1.0\n\n### Improvements\nFaster startup.",
                "createdAt": "2026-03-02T13:14:15.000Z",
            }]
        })
        entries = saas.parse_postman_app_release_notes(raw)
        self.assertEqual(entries[0]["date"].isoformat(), "2026-03-02T13:14:15+00:00")

    def test_release_notes_parser_skips_known_links_and_bad_payloads(self):
        raw = json.dumps({"notes": [{
            "version": "12.25.7",
            "content": "## Postman 12.25.7\nAugust 28, 2026",
            "createdAt": "2026-08-28T02:32:56.000Z",
        }]})
        known = {"https://www.postman.com/release-notes/postman-app/#12-25-7"}
        self.assertEqual(saas.parse_postman_app_release_notes(raw, known), [])
        self.assertEqual(saas.parse_postman_app_release_notes("not json"), [])
        self.assertEqual(saas.parse_postman_app_release_notes("[]"), [])

    def test_collector_isolates_upstream_failure(self):
        with patch.object(saas.multi_rss, "get_html", return_value=None):
            self.assertEqual(saas.collect_postman_app_release_notes(set()), [])


if __name__ == "__main__":
    unittest.main()
