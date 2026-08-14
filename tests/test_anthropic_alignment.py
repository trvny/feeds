import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_refreshes_known_entry_without_losing_cached_metadata(self):
        link = "https://alignment.anthropic.com/2025/wont-vs-cant/"
        listing = """
        <main>
          <span>February 2025</span>
          <a href="/2025/wont-vs-cant/">Won't vs. Can't</a>
        </main>
        """
        cached = {
            "title": "Won't vs. Can't",
            "link": link,
            "date": None,
            "description": "Rich cached summary",
            "source": alignment.ALIGNMENT_LABEL,
            "image": "https://example.com/image.png",
            alignment.PRESERVE_MISSING_DATE: True,
        }

        with (
            patch.object(alignment, "fetch_page", return_value=listing),
            patch.object(
                alignment,
                "_alignment_meta",
                side_effect=lambda _link, fallback_date=None: {
                    "title": None,
                    "summary": None,
                    "image": None,
                    "date": fallback_date,
                },
            ),
        ):
            entries = alignment.scrape_alignment(
                {link},
                refresh_entries={link: cached},
            )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["date"].isoformat(), "2025-02-01T00:00:00+00:00")
        self.assertEqual(entries[0]["title"], "Won't vs. Can't")
        self.assertEqual(entries[0]["description"], "Rich cached summary")
        self.assertEqual(entries[0]["image"], "https://example.com/image.png")
        self.assertNotIn(alignment.PRESERVE_MISSING_DATE, entries[0])

    def test_failed_index_keeps_cached_entry_undated_for_retry(self):
        cached = {
            "title": "Old",
            "link": "https://alignment.anthropic.com/2025/old-post/",
            "date": None,
            "description": "Cached",
            "source": alignment.ALIGNMENT_LABEL,
            "image": None,
        }
        feed = MagicMock()

        with (
            patch.object(alignment, "load_cache", return_value={"entries": [cached]}),
            patch.object(alignment.anthropic_base, "scrape_all", return_value=[]),
            patch.object(alignment, "scrape_alignment", return_value=[]),
            patch.object(alignment, "save_cache") as save_cache,
            patch.object(alignment.anthropic_base, "generate_atom_feed", return_value=feed) as generate,
            patch.object(alignment.anthropic_base, "save_atom_feed"),
        ):
            self.assertTrue(alignment.main())

        saved_entries = save_cache.call_args.args[1]
        self.assertIsNone(saved_entries[0]["date"])
        self.assertTrue(saved_entries[0][alignment.PRESERVE_MISSING_DATE])

        rendered_entries = generate.call_args.args[0]
        self.assertEqual(rendered_entries[0]["date"].isoformat(), "2025-01-01T00:00:00+00:00")
        self.assertIsNone(saved_entries[0]["date"])


if __name__ == "__main__":
    unittest.main()
