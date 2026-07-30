import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import ninegag  # noqa: E402


class NineGagTests(unittest.TestCase):
    def _page(self, posts):
        payload = json.dumps({"data": {"posts": posts}})
        return f"window._config = JSON.parse({json.dumps(payload)});"

    def test_missing_creation_timestamp_uses_first_seen_date(self):
        first_seen = datetime(2026, 7, 30, 3, 0, tzinfo=timezone.utc)
        page = self._page(
            [{"url": "https://9gag.com/gag/example", "title": "Example"}]
        )

        with (
            patch.object(ninegag, "get_html", return_value=page),
            patch.object(ninegag, "_first_seen_date", return_value=first_seen),
        ):
            entries = ninegag.scrape_hot(set())

        self.assertEqual(entries[0]["date"], first_seen)

    def test_creation_timestamp_is_preserved(self):
        page = self._page(
            [
                {
                    "url": "https://9gag.com/gag/example",
                    "title": "Example",
                    "creationTs": 1_700_000_000,
                }
            ]
        )

        with patch.object(ninegag, "get_html", return_value=page):
            entries = ninegag.scrape_hot(set())

        self.assertEqual(entries[0]["date"].timestamp(), 1_700_000_000)

    def test_cached_null_date_is_repaired_once(self):
        first_seen = datetime(2026, 7, 30, 3, 0, tzinfo=timezone.utc)
        entry = {
            "title": "Example",
            "link": "https://9gag.com/gag/example",
            "date": None,
            "source": ninegag.SOURCE,
        }

        with patch.object(ninegag, "_first_seen_date", return_value=first_seen):
            repaired = ninegag.repair_cached_date(entry)

        self.assertEqual(repaired["date"], first_seen)
        self.assertIsNone(entry["date"])


if __name__ == "__main__":
    unittest.main()
