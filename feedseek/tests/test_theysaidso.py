import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import theysaidso  # noqa: E402


class TheySaidSoTests(unittest.TestCase):
    def test_missing_api_key_uses_bible_gateway_fallback(self):
        fallback_entry = {
            "title": "John 3:16",
            "link": "https://www.biblegateway.com/passage/?search=John+3%3A16",
            "date": None,
            "description": "For God so loved the world",
            "source": "Verse of the Day (Bible Gateway)",
        }

        with (
            patch.object(theysaidso, "API_KEY", ""),
            patch.object(
                theysaidso, "scrape_feed", return_value=[fallback_entry]
            ) as scrape_feed,
        ):
            result = theysaidso.scrape_verse_of_day(set())

        self.assertEqual(result, [fallback_entry])
        scrape_feed.assert_called_once_with(
            "Verse of the Day (Bible Gateway)",
            theysaidso.BIBLEGATEWAY_VOTD_FEED,
            set(),
            cap=1,
        )

    def test_successful_theysaidso_verse_skips_fallback(self):
        primary_entry = {
            "title": "John 3:16 — For God so loved the world",
            "link": "https://theysaidso.com/verse/abc123",
            "date": None,
            "description": "For God so loved the world — John 3:16",
            "source": "Verse of the Day (They Said So)",
        }

        with (
            patch.object(
                theysaidso, "scrape_votd", return_value=[primary_entry]
            ) as scrape_votd,
            patch.object(theysaidso, "scrape_feed") as scrape_feed,
        ):
            result = theysaidso.scrape_verse_of_day(set())

        self.assertEqual(result, [primary_entry])
        scrape_votd.assert_called_once_with(set())
        scrape_feed.assert_not_called()

    def test_real_api_shape_is_parsed(self):
        response = Mock()
        response.status_code = 200
        response.headers = {}
        response.json.return_value = {
            "contents": {
                "verse": {
                    "id": "abc123",
                    "book": 43,
                    "chapter": 3,
                    "verse": 16,
                    "text": "For God so loved the world",
                    "date": "2026-07-22",
                }
            }
        }

        with (
            patch.object(theysaidso, "API_KEY", "test-key"),
            patch.object(theysaidso.requests, "get", return_value=response),
        ):
            entries = theysaidso.scrape_votd(set())

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["title"], "John 3:16 — For God so loved the world"
        )
        self.assertEqual(entries[0]["link"], "https://theysaidso.com/verse/abc123")
        self.assertEqual(entries[0]["source"], "Verse of the Day (They Said So)")


if __name__ == "__main__":
    unittest.main()
