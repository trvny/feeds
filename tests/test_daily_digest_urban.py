import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import daily_digest  # noqa: E402


FIXED_NOW = datetime(2026, 8, 21, 12, 0, tzinfo=pytz.UTC)


class DailyDigestUrbanDictionaryTests(unittest.TestCase):
    def test_uses_words_of_the_day_endpoint(self):
        self.assertEqual(
            daily_digest.URBAN_WOTD_URL,
            "https://api.urbandictionary.com/v0/words_of_the_day",
        )

    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    @patch.object(daily_digest, "fetch_json")
    def test_adapter_builds_one_featured_word(self, fetch_json, _mock_today):
        fetch_json.return_value = {
            "list": [{
                "word": "Overstand",
                "definition": "To understand a topic or statement to the highest extent.",
                "example": "He finally overstood the plan.",
                "author": "Elf Eater",
                "date": "2026-08-21",
                "permalink": (
                    "https://www.urbandictionary.com/define.php?term=Overstand&defid=68480"
                ),
            }]
        }

        [entry] = daily_digest.adapt_urban_wotd()

        fetch_json.assert_called_once_with(daily_digest.URBAN_WOTD_URL, retries=2)
        self.assertEqual(entry["guid"], "urban_word:2026-08-21")
        self.assertEqual(entry["title"], "Urban Word of the Day — Overstand")
        self.assertIn("Example: He finally overstood the plan.", entry["description"])
        self.assertIn("by Elf Eater", entry["description"])
        self.assertEqual(entry["source"], "Urban Dictionary")
        self.assertEqual(entry["category"], "urban_word")

    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    @patch.object(daily_digest, "_cached_guids", return_value={"urban_word:2026-08-21"})
    @patch.object(daily_digest, "adapt_urban_wotd")
    @patch.object(daily_digest, "adapt_anycrap", return_value=[])
    @patch.object(daily_digest, "adapt_critter", return_value=[])
    @patch.object(daily_digest, "adapt_holidays", return_value=[])
    @patch.object(daily_digest, "fetch_json")
    def test_cached_word_is_not_refetched(
        self,
        fetch_json,
        _mock_holidays,
        _mock_critter,
        _mock_anycrap,
        adapt_urban_wotd,
        _mock_cached,
        _mock_today,
    ):
        fetch_json.side_effect = lambda url: (
            {"data": {}} if "onthisday" in url else []
        )

        daily_digest.collect_entries()

        adapt_urban_wotd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
