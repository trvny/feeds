import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import saas


class CodeRabbitSaasTests(unittest.TestCase):
    def test_newsroom_scraper_parses_cards_and_skips_known_links(self):
        html = """
        <main>
          <a href="/newsroom/new-story">
            <time datetime="2026-08-12">August 12, 2026</time>
            <span>CodeRabbit</span>
            <h3>New CodeRabbit story</h3>
            <p>Useful newsroom summary.</p>
          </a>
          <a href="/newsroom/known-story">
            <time datetime="2026-08-11">August 11, 2026</time>
            <h3>Known story</h3>
          </a>
        </main>
        """
        known = {"https://www.coderabbit.ai/newsroom/known-story"}
        with patch.object(saas.multi_rss, "get_html", return_value=html):
            entries = saas.collect_coderabbit_newsroom(known)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "CodeRabbit Newsroom")
        self.assertEqual(
            entries[0]["link"], "https://www.coderabbit.ai/newsroom/new-story"
        )
        self.assertEqual(entries[0]["title"], "New CodeRabbit story")
        self.assertEqual(entries[0]["description"], "Useful newsroom summary.")
        self.assertEqual(entries[0]["date"], datetime(2026, 8, 12, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()
