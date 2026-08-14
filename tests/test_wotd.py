import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import wotd  # noqa: E402


class WotdTests(unittest.TestCase):
    def test_urban_dictionary_prefers_written_on_timestamp(self):
        payload = {
            "list": [
                {
                    "word": "flophouse",
                    "permalink": "https://www.urbandictionary.com/define.php?term=flophouse",
                    "definition": "A place to crash.",
                    "date": "November 21",
                    "written_on": "2007-11-21T00:00:00.000Z",
                }
            ]
        }

        with patch.object(wotd, "get_html", return_value=json.dumps(payload)):
            entries = wotd.scrape_urban_dictionary(set())

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["date"], datetime(2007, 11, 21, tzinfo=timezone.utc)
        )

    def test_urban_dictionary_rejects_non_object_payload(self):
        with patch.object(wotd, "get_html", return_value="null"):
            entries = wotd.scrape_urban_dictionary(set())

        self.assertEqual(entries, [])

    def test_urban_cache_transform_replaces_stale_cached_entry(self):
        link = "https://www.urbandictionary.com/define.php?term=flophouse"
        stale = {
            "title": "flophouse — Urban Dictionary",
            "link": link,
            "date": datetime(2026, 11, 21, tzinfo=timezone.utc),
            "description": "A place to crash.",
            "source": "Urban Dictionary",
        }
        fresh = {
            **stale,
            "date": datetime(2007, 11, 21, tzinfo=timezone.utc),
        }

        transform = wotd._urban_cache_transform([fresh])

        self.assertEqual(transform(stale), fresh)

    def test_prefetched_urban_scraper_keeps_link_deduplication(self):
        entry = {
            "title": "flophouse — Urban Dictionary",
            "link": "https://www.urbandictionary.com/define.php?term=flophouse",
            "date": datetime(2007, 11, 21, tzinfo=timezone.utc),
            "description": "A place to crash.",
            "source": "Urban Dictionary",
        }
        scraper = wotd._prefetched_urban_scraper([entry])

        self.assertEqual(scraper(set()), [entry])
        self.assertEqual(scraper({entry["link"]}), [])


if __name__ == "__main__":
    unittest.main()
