import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import anthropic as alignment  # noqa: E402


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

    def test_reads_transformer_circuits_native_atom_feed(self):
        known = "https://transformer-circuits.pub/2026/known/index.html"
        raw = f"""
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Transformer Circuits Thread</title>
          <entry>
            <title>Fresh interpretability post</title>
            <link href="https://transformer-circuits.pub/2026/fresh/index.html" />
            <updated>2026-07-15T12:00:00Z</updated>
            <summary>Fresh summary</summary>
          </entry>
          <entry>
            <title>Known post</title>
            <link href="{known}" />
            <updated>2026-07-01T12:00:00Z</updated>
          </entry>
        </feed>
        """

        with patch.object(alignment, "fetch_page", return_value=raw):
            entries = alignment.scrape_transformer_circuits({known})

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Fresh interpretability post")
        self.assertEqual(
            entries[0]["link"],
            "https://transformer-circuits.pub/2026/fresh/index.html",
        )
        self.assertEqual(entries[0]["date"].isoformat(), "2026-07-15T12:00:00+00:00")
        self.assertEqual(entries[0]["description"], "Fresh summary")
        self.assertEqual(entries[0]["source"], alignment.TRANSFORMER_CIRCUITS_LABEL)

    def test_feed_selection_ranks_retryable_fallback_before_limit(self):
        recent = {
            "title": "Recent dated article",
            "link": "https://www.anthropic.com/news/recent",
            "date": alignment.anthropic_base.parse_date("September 1, 2026"),
            "description": "Recent",
            "source": "Anthropic Newsroom",
        }
        undated = [
            {
                "title": f"Retryable {i}",
                "link": f"https://alignment.anthropic.com/2025/retry-{i}/",
                "date": None,
                "description": "Cached",
                "source": alignment.ALIGNMENT_LABEL,
                alignment.PRESERVE_MISSING_DATE: True,
            }
            for i in range(alignment.anthropic_base.MAX_ENTRIES + 5)
        ]
        merged = alignment.sort_posts_for_feed([recent, *undated], date_field="date")

        selected = alignment._select_feed_items(
            merged, alignment.anthropic_base.MAX_ENTRIES
        )

        self.assertEqual(len(selected), alignment.anthropic_base.MAX_ENTRIES)
        self.assertIn(recent["link"], {entry["link"] for entry in selected})
        self.assertTrue(all(entry["date"] is None for entry in undated))

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
            patch.object(alignment, "scrape_transformer_circuits", return_value=[]),
            patch.object(alignment, "save_cache") as save_cache,
            patch.object(alignment.anthropic_base, "generate_atom_feed", return_value=feed) as generate,
            patch.object(alignment, "save_atom_feed") as save_feed,
        ):
            self.assertTrue(alignment.main())

        saved_entries = save_cache.call_args.args[1]
        self.assertIsNone(saved_entries[0]["date"])
        self.assertTrue(saved_entries[0][alignment.PRESERVE_MISSING_DATE])
        self.assertEqual(saved_entries[0]["entry_id"], cached["link"])

        rendered_entries = generate.call_args.args[0]
        self.assertEqual(rendered_entries[0]["entry_id"], cached["link"])
        self.assertEqual(rendered_entries[0]["date"].isoformat(), "2025-01-01T00:00:00+00:00")
        self.assertIsNone(saved_entries[0]["date"])
        save_feed.assert_called_once_with(feed, alignment.FEED_NAME)


if __name__ == "__main__":
    unittest.main()
