import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import theysaidso  # noqa: E402


TEST_DAY = datetime(2026, 7, 22, tzinfo=timezone.utc)
CANONICAL_LINK = "https://theysaidso.com/bible#2026-07-22"


def api_response() -> Mock:
    response = Mock()
    response.status_code = 200
    response.headers = {}
    response.text = ""
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
    return response


def fallback_entry() -> dict:
    return {
        "title": "John 3:16",
        "link": "https://www.biblegateway.com/passage/?search=John+3%3A16",
        "date": TEST_DAY,
        "description": "For God so loved the world",
        "source": "Verse of the Day (Bible Gateway)",
    }


class TheySaidSoTests(unittest.TestCase):
    def test_missing_api_key_uses_canonicalized_bible_gateway_fallback(self):
        with (
            patch.object(theysaidso, "API_KEY", ""),
            patch.object(
                theysaidso, "scrape_feed", return_value=[fallback_entry()]
            ) as scrape_feed,
        ):
            result = theysaidso.scrape_verse_of_day(set())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["link"], CANONICAL_LINK)
        scrape_feed.assert_called_once_with(
            "Verse of the Day (Bible Gateway)",
            theysaidso.BIBLEGATEWAY_VOTD_FEED,
            set(),
            cap=1,
        )

    def test_successful_theysaidso_verse_skips_fallback(self):
        with (
            patch.object(theysaidso, "API_KEY", "test-key"),
            patch.object(
                theysaidso.requests, "get", return_value=api_response()
            ),
            patch.object(theysaidso, "scrape_feed") as scrape_feed,
        ):
            result = theysaidso.scrape_verse_of_day(set())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["link"], CANONICAL_LINK)
        scrape_feed.assert_not_called()

    def test_cached_primary_verse_does_not_trigger_fallback(self):
        with (
            patch.object(theysaidso, "API_KEY", "test-key"),
            patch.object(
                theysaidso.requests, "get", return_value=api_response()
            ),
            patch.object(theysaidso, "scrape_feed") as scrape_feed,
        ):
            result = theysaidso.scrape_verse_of_day({CANONICAL_LINK})

        self.assertEqual(result, [])
        scrape_feed.assert_not_called()

    def test_recovered_primary_does_not_duplicate_cached_fallback_day(self):
        with (
            patch.object(theysaidso, "API_KEY", "test-key"),
            patch.object(
                theysaidso.requests, "get", return_value=api_response()
            ),
            patch.object(theysaidso, "scrape_feed") as scrape_feed,
        ):
            result = theysaidso.scrape_verse_of_day({CANONICAL_LINK})

        self.assertEqual(result, [])
        scrape_feed.assert_not_called()

    def test_fallback_does_not_duplicate_cached_primary_day(self):
        with (
            patch.object(theysaidso, "API_KEY", ""),
            patch.object(theysaidso, "scrape_feed", return_value=[fallback_entry()]),
        ):
            result = theysaidso.scrape_verse_of_day({CANONICAL_LINK})

        self.assertEqual(result, [])

    def test_real_api_shape_is_parsed(self):
        with (
            patch.object(theysaidso, "API_KEY", "test-key"),
            patch.object(
                theysaidso.requests, "get", return_value=api_response()
            ),
        ):
            entries = theysaidso.scrape_votd(set())

        self.assertIsNotNone(entries)
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["title"], "John 3:16 — For God so loved the world"
        )
        self.assertEqual(entries[0]["link"], CANONICAL_LINK)
        self.assertEqual(entries[0]["source"], "Verse of the Day (They Said So)")


if __name__ == "__main__":
    unittest.main()
