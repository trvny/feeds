import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import daily_digest  # noqa: E402


FIXED_NOW = datetime(2026, 7, 30, 12, 0, tzinfo=pytz.UTC)


class DailyDigestViewBitsTests(unittest.TestCase):
    def test_uses_viewbits_daily_endpoints_and_limits_headlines(self):
        self.assertEqual(
            daily_digest.SOURCES["quote"],
            "https://api.viewbits.com/v1/zenquotes?mode=today",
        )
        self.assertEqual(
            daily_digest.SOURCES["jester"],
            "https://api.viewbits.com/v1/jester?mode=today",
        )
        self.assertEqual(
            daily_digest.SOURCES["headlines"],
            "https://api.viewbits.com/v1/headlines?limit=10",
        )

    def test_headline_adapter_enforces_limit_locally(self):
        data = [
            {
                "title": f"Headline {index}",
                "description": f"Description {index}",
                "link": f"https://example.com/{index}",
            }
            for index in range(15)
        ]

        entries = daily_digest.adapt_headlines(data)

        self.assertEqual(len(entries), 10)
        self.assertEqual(entries[-1]["title"], "Headline 9")

    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_jester_adapter_builds_daily_entry(self, _mock_today):
        [entry] = daily_digest.adapt_jester(
            {
                "text": "A very serious joke.",
                "source": "example.com",
                "url": "https://example.com/joke",
            }
        )

        self.assertEqual(entry["guid"], "jester:2026-07-30")
        self.assertEqual(entry["title"], "Joke of the Day")
        self.assertEqual(entry["description"], "A very serious joke.")
        self.assertEqual(entry["link"], "https://example.com/joke")
        self.assertEqual(entry["source"], "example.com")
        self.assertEqual(entry["category"], "joke")

    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_on_this_day_groups_and_caps_items(self, _mock_today):
        data = {
            "data": {
                "Events": [
                    {
                        "text": f"Historical event {index}",
                        "links": [{"link": f"https://example.com/event-{index}"}],
                    }
                    for index in range(7)
                ],
                "Births": [{"text": "A notable person was born."}],
                "Deaths": [],
            }
        }

        entries = daily_digest.adapt_on_this_day(data)

        self.assertEqual(len(entries), 2)
        events, births = entries
        self.assertEqual(events["guid"], "onthisday:on_this_day_event:2026-07-30")
        self.assertEqual(events["title"], "On This Day — July 30")
        self.assertEqual(events["link"], "https://example.com/event-0")
        self.assertEqual(events["description"].count("Historical event"), 5)
        self.assertNotIn("Historical event 5", events["description"])
        self.assertEqual(births["title"], "Born on This Day — July 30")

    @patch.object(daily_digest, "adapt_critter", return_value=[])
    @patch.object(daily_digest, "adapt_holidays", return_value=[])
    @patch.object(daily_digest, "_today_utc", return_value=FIXED_NOW)
    def test_collect_entries_requests_on_this_day_for_today(
        self, _mock_today, _mock_holidays, _mock_critter
    ):
        responses = {
            daily_digest.SOURCES["quote"]: [{"q": "Quote", "a": "Author"}],
            daily_digest.SOURCES["fact"]: {"text": "Fact"},
            daily_digest.SOURCES["lifehack"]: {"text": "Hack"},
            daily_digest.SOURCES["fortune"]: {"text": "Fortune"},
            daily_digest.SOURCES["jester"]: {"text": "Joke"},
            daily_digest.SOURCES["headlines"]: [],
            "https://api.viewbits.com/v1/onthisday?m=7&d=30": {"data": {}},
        }

        with patch.object(
            daily_digest,
            "fetch_json",
            side_effect=lambda url: responses[url],
        ) as fetch_json:
            daily_digest.collect_entries()

        requested_urls = [call.args[0] for call in fetch_json.call_args_list]
        self.assertIn(
            "https://api.viewbits.com/v1/onthisday?m=7&d=30",
            requested_urls,
        )


if __name__ == "__main__":
    unittest.main()
