import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import aibridge  # noqa: E402


class AiBridgeTests(unittest.TestCase):
    def test_repairs_answer_ai_toolcalling_entry(self):
        original = {
            "title": "The unauthorized tool call problem",
            "link": aibridge.ANSWER_AI_TOOLCALLING,
            "date": None,
            "description": "Getting requirements to build wheel ... done",
            "source": "Answer.AI",
        }

        repaired = aibridge.repair_answer_ai_entry(original)

        self.assertIsNot(repaired, original)
        self.assertIsNone(original["date"])
        self.assertEqual(
            repaired["date"], datetime(2026, 2, 18, tzinfo=timezone.utc)
        )
        self.assertEqual(
            repaired["description"], aibridge.ANSWER_AI_TOOLCALLING_DESCRIPTION
        )

    def test_answer_ai_scraper_applies_repair_to_fresh_entries(self):
        source_entry = {
            "title": "The unauthorized tool call problem",
            "link": aibridge.ANSWER_AI_TOOLCALLING,
            "date": datetime(2026, 7, 30, tzinfo=timezone.utc),
            "description": "bad generated summary",
            "source": "Answer.AI",
        }
        known_links = {"https://example.com/already-seen"}

        with patch.object(aibridge, "scrape_feed", return_value=[source_entry]) as scrape:
            entries = aibridge.scrape_answer_ai(known_links)

        scrape.assert_called_once_with(
            "Answer.AI", aibridge.ANSWER_AI_FEED, known_links, cap=40
        )
        self.assertEqual(
            entries[0]["date"], datetime(2026, 2, 18, tzinfo=timezone.utc)
        )
        self.assertEqual(
            entries[0]["description"], aibridge.ANSWER_AI_TOOLCALLING_DESCRIPTION
        )

    def test_minimax_news_scraper_parses_listing_cards(self):
        html = """
        <main>
          <a href="/news/minimax-m25/">
            <span>2026.2.12</span>
            <h3>MiniMax M2.5:\n Built for Real-World Productivity.</h3>
            <p>Frontier coding and agentic productivity model.</p>
            <span>Read More</span>
          </a>
          <a href="/news/minimax-m25">
            <span>2026.2.12</span><h3>Duplicate spelling</h3>
          </a>
          <a href="https://www.minimax.io/news/already-seen/">
            <span>Mar. 02 , 2026</span><h3>Already seen</h3>
          </a>
          <a href="/about">About MiniMax</a>
        </main>
        """
        known_links = {"https://www.minimax.io/news/already-seen"}

        with patch.object(aibridge, "get_html", return_value=html):
            entries = aibridge.scrape_minimax_news(known_links)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "MiniMax")
        self.assertEqual(
            entries[0]["link"], "https://www.minimax.io/news/minimax-m25"
        )
        self.assertEqual(
            entries[0]["title"], "MiniMax M2.5: Built for Real-World Productivity."
        )
        self.assertEqual(
            entries[0]["date"], datetime(2026, 2, 12, tzinfo=timezone.utc)
        )
        self.assertEqual(
            entries[0]["description"],
            "Frontier coding and agentic productivity model.",
        )

    def test_minimax_news_scraper_uses_hydration_paths_as_fallback(self):
        listing_html = r'<script>window.__next_f.push(["\/news\/minimax-agent"])</script>'
        article_html = """
        <html>
          <head>
            <meta name="description" content="MiniMax Agent launch details.">
          </head>
          <body>
            <span>06.19.2025</span>
            <h1>MiniMax Agent — Code is Cheap, Show Me the Requirement</h1>
          </body>
        </html>
        """

        with patch.object(
            aibridge, "get_html", side_effect=[listing_html, article_html]
        ) as get_html:
            entries = aibridge.scrape_minimax_news(set())

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["link"], "https://www.minimax.io/news/minimax-agent"
        )
        self.assertEqual(
            entries[0]["date"], datetime(2025, 6, 19, tzinfo=timezone.utc)
        )
        self.assertEqual(entries[0]["description"], "MiniMax Agent launch details.")
        self.assertEqual(get_html.call_count, 2)


if __name__ == "__main__":
    unittest.main()
