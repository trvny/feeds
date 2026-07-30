import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import anthropic_with_alignment as alignment  # noqa: E402


class AnthropicAlignmentTests(unittest.TestCase):
    def test_index_reads_plain_text_month_labels(self):
        soup = BeautifulSoup(
            """
            <main>
              <div class="month">February 2025</div>
              <article><a href="/2025/wont-vs-cant/">Won't vs. Can't</a></article>
              <div class="month">January 2026</div>
              <article><a href="/2026/petri-v2/">Petri 2.0</a></article>
            </main>
            """,
            "html.parser",
        )

        rows = list(alignment._alignment_index(soup))

        self.assertEqual(rows[0][0], "https://alignment.anthropic.com/2025/wont-vs-cant/")
        self.assertEqual(rows[0][1].isoformat(), "2025-02-01T00:00:00+00:00")
        self.assertEqual(rows[1][1].isoformat(), "2026-01-01T00:00:00+00:00")

    def test_refreshes_known_undated_entry(self):
        link = "https://alignment.anthropic.com/2025/wont-vs-cant/"
        listing = """
        <main>
          <span>February 2025</span>
          <a href="/2025/wont-vs-cant/">Won't vs. Can't</a>
        </main>
        """

        with (
            patch.object(alignment, "fetch_page", return_value=listing),
            patch.object(
                alignment,
                "_alignment_meta",
                side_effect=lambda _link, fallback_date=None: {
                    "title": "Won't vs. Can't",
                    "summary": "Summary",
                    "image": None,
                    "date": fallback_date,
                },
            ),
        ):
            entries = alignment.scrape_alignment({link}, refresh_links={link})

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["date"].isoformat(), "2025-02-01T00:00:00+00:00")

    def test_cached_undated_entry_gets_stable_year_fallback(self):
        repaired = alignment.repair_cached_alignment_entry(
            {
                "title": "Old",
                "link": "https://alignment.anthropic.com/2025/old-post/",
                "date": None,
                "source": alignment.ALIGNMENT_LABEL,
            }
        )

        self.assertEqual(repaired["date"].isoformat(), "2025-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
