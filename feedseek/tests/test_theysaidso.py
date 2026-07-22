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
    def test_repair_mojibake_fixes_utf8_decoded_as_latin1(self):
        self.assertEqual(
            theysaidso.repair_mojibake("FranÃ§ois-RenÃ© de Chateaubriand"),
            "François-René de Chateaubriand",
        )

    def test_repair_mojibake_restores_c1_smart_apostrophe(self):
        self.assertEqual(theysaidso.repair_mojibake("Itâ\x80\x99s"), "It’s")

    def test_repair_mojibake_keeps_non_breaking_space_byte_pair_together(self):
        self.assertEqual(theysaidso.repair_mojibake("BonjourÂ !"), "Bonjour !")

    def test_repair_mojibake_preserves_correct_unicode(self):
        value = "François-René — déjà vu"
        self.assertEqual(theysaidso.repair_mojibake(value), value)

    def test_repair_cached_entry_repairs_text_without_mutating_source(self):
        original = {
            "title": "FranÃ§ois-RenÃ©",
            "description": "Itâ\x80\x99s by FranÃ§ois-RenÃ©",
            "source": "Art",
            "link": "https://example.com/quote",
            "date": TEST_DAY,
        }

        repaired = theysaidso.repair_cached_entry(original)

        self.assertEqual(repaired["title"], "François-René")
        self.assertEqual(repaired["description"], "It’s by François-René")
        self.assertEqual(repaired["link"], original["link"])
        self.assertEqual(original["title"], "FranÃ§ois-RenÃ©")

    def test_scrape_qod_repairs_raw_xml_before_sanitization(self):
        rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel><item>
          <guid>https://theysaidso.com/quote/example</guid>
          <link>https://theysaidso.com/quote-of-the-day/art</link>
          <description>Itâ\x80\x99s art. - FranÃ§ois-RenÃ©</description>
          <pubDate>Wed, 22 Jul 2026 02:52:42 +0000</pubDate>
        </item></channel></rss>"""

        with patch.object(theysaidso, "get_html", return_value=rss):
            entries = theysaidso.scrape_qod(set())

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "It’s art. - François-René")
        self.assertEqual(entries[0]["source"], "Art")

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
