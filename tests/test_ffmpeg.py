import sys
import unittest
from datetime import datetime
from pathlib import Path

import pytz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import ffmpeg  # noqa: E402


class FFmpegTests(unittest.TestCase):
    def test_news_title_date_parses_ordinal_and_plain_days(self):
        self.assertEqual(
            ffmpeg.news_title_date(
                "June 24th, 2026, Ampere Server Donation"
            ),
            datetime(2026, 6, 24, tzinfo=pytz.UTC),
        )
        self.assertEqual(
            ffmpeg.news_title_date("October 28, 2013, FFmpeg 2.1"),
            datetime(2013, 10, 28, tzinfo=pytz.UTC),
        )

    def test_news_title_date_rejects_unexpected_titles(self):
        self.assertIsNone(ffmpeg.news_title_date("FFmpeg development update"))

    def test_cache_repair_replaces_first_seen_news_date(self):
        entry = {
            "title": "August 22nd, 2015, FFmpeg 2.8",
            "source": "FFmpeg News",
            "date": datetime(2026, 7, 30, tzinfo=pytz.UTC),
        }

        repaired = ffmpeg.repair_news_date(entry)

        self.assertEqual(
            repaired["date"], datetime(2015, 8, 22, tzinfo=pytz.UTC)
        )
        self.assertEqual(
            entry["date"], datetime(2026, 7, 30, tzinfo=pytz.UTC)
        )

    def test_cache_repair_leaves_code_dates_untouched(self):
        date = datetime(2026, 7, 30, tzinfo=pytz.UTC)
        entry = {
            "title": "June 24th, 2015, commit title",
            "source": "FFmpeg Code",
            "date": date,
        }

        self.assertEqual(ffmpeg.repair_news_date(entry)["date"], date)


if __name__ == "__main__":
    unittest.main()
