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

        with patch.object(aibridge, "get_html", return_value=html) as get_html:
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
        self.assertEqual(get_html.call_count, 1)

    def test_minimax_news_scraper_uses_hydration_paths_as_fallback(self):
        listing_html = r'<script>window.__next_f.push(["\/news\/minimax-agent"])</script>'
        article_html = """
        <html>
          <head>
            <meta name="description" content="MiniMax Agent launch details.">
          </head>
          <body>
            <nav><h2>Company</h2></nav>
            <main>
              <span>06.19.2025</span>
              <h1>MiniMax Agent — Code is Cheap, Show Me the Requirement</h1>
            </main>
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
            entries[0]["title"],
            "MiniMax Agent — Code is Cheap, Show Me the Requirement",
        )
        self.assertEqual(
            entries[0]["date"], datetime(2025, 6, 19, tzinfo=timezone.utc)
        )
        self.assertEqual(entries[0]["description"], "MiniMax Agent launch details.")
        self.assertEqual(get_html.call_count, 2)

    def test_minimax_hydration_scan_ignores_foreign_news_urls(self):
        listing_html = (
            '<script>const external="https://techcrunch.com/news/not-minimax";'
            'const local="/news/real-minimax";</script>'
        )
        article_html = "<main><h1>Real MiniMax</h1><time datetime='2026-05-25'></time></main>"

        with patch.object(
            aibridge, "get_html", side_effect=[listing_html, article_html]
        ) as get_html:
            entries = aibridge.scrape_minimax_news(set())

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["link"], "https://www.minimax.io/news/real-minimax"
        )
        self.assertEqual(
            entries[0]["date"], datetime(2026, 5, 25, tzinfo=timezone.utc)
        )
        self.assertEqual(get_html.call_count, 2)

    def test_minimax_known_cards_do_not_log_layout_warning(self):
        listing_html = """
        <a href="/news/already-known">
          <span>2026-05-25</span><h3>Already known</h3>
        </a>
        """
        known_links = {"https://www.minimax.io/news/already-known"}

        with (
            patch.object(aibridge, "get_html", return_value=listing_html),
            patch.object(aibridge.logger, "warning") as warning,
        ):
            entries = aibridge.scrape_minimax_news(known_links)

        self.assertEqual(entries, [])
        warning.assert_not_called()

    def test_minimax_anchor_without_date_fetches_article_metadata(self):
        listing_html = """
        <a href="/news/hyperbond">
          <h3>MiniMax and Hyperbond Studio</h3>
          <p>Partner update.</p>
        </a>
        """
        article_html = """
        <html>
          <head><meta property="og:title" content="Wrong fallback title"></head>
          <body>
            <nav><h1>Navigation heading</h1></nav>
            <main>
              <time datetime="2026-02-04"></time>
              <h1>MiniMax and Hyperbond Studio: Bringing AI Companions to Life</h1>
              <p>Speech 2.8 powers every AI companion.</p>
            </main>
          </body>
        </html>
        """

        with patch.object(
            aibridge, "get_html", side_effect=[listing_html, article_html]
        ) as get_html:
            entries = aibridge.scrape_minimax_news(set())

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["title"],
            "MiniMax and Hyperbond Studio: Bringing AI Companions to Life",
        )
        self.assertEqual(
            entries[0]["date"], datetime(2026, 2, 4, tzinfo=timezone.utc)
        )
        self.assertEqual(
            entries[0]["description"], "Speech 2.8 powers every AI companion."
        )
        self.assertEqual(get_html.call_count, 2)

    def test_minimax_month_name_date_accepts_ordinal_suffix(self):
        entry = aibridge._minimax_entry(
            "https://www.minimax.io/news/hyperbond",
            "<main><h1>Hyperbond</h1><p>Feb. 4th, 2026 Partner news</p></main>",
            full_page=True,
            fallback_date=False,
        )

        self.assertEqual(entry["date"], datetime(2026, 2, 4, tzinfo=timezone.utc))


    def test_pllum_blog_scraper_parses_listing_cards_and_dedupes(self):
        html = """
        <main>
          <article>
            <a href="/blog/posts/trzecie-sniadanie" aria-label="Trzecie Śniadanie z PLLuM za nami"></a>
            <h2>Trzecie Śniadanie z PLLuM za nami</h2>
            <div class="text-base line-clamp-3">Krótki opis wydarzenia.</div>
            <time datetime="2026-06-29T00:00:00.000Z">2026-06-29</time>
          </article>
          <article>
            <a href="/blog/posts/already-seen" aria-label="Already seen"></a>
            <h2>Already seen</h2>
            <time datetime="2026-05-21T00:00:00.000Z">2026-05-21</time>
          </article>
        </main>
        """
        known_links = {"https://pllum.org.pl/blog/posts/already-seen"}

        with patch.object(aibridge, "get_html", return_value=html):
            entries = aibridge.scrape_pllum_blog(known_links)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "PLLuM")
        self.assertEqual(entries[0]["link"], "https://pllum.org.pl/blog/posts/trzecie-sniadanie")
        self.assertEqual(entries[0]["title"], "Trzecie Śniadanie z PLLuM za nami")
        self.assertEqual(entries[0]["date"], datetime(2026, 6, 29, tzinfo=timezone.utc))
        self.assertEqual(entries[0]["description"], "Krótki opis wydarzenia.")


if __name__ == "__main__":
    unittest.main()
