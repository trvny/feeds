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


if __name__ == "__main__":
    unittest.main()
