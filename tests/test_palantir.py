import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import palantir  # noqa: E402


class PalantirTests(unittest.TestCase):
    def test_listing_link_normalizes_internal_article(self):
        self.assertEqual(
            palantir._listing_link(
                "/blog/building-with-palantir-aip/?utm_source=test",
                internal_prefix="/blog/",
            ),
            "https://www.palantir.com/blog/building-with-palantir-aip/",
        )

    def test_listing_link_rejects_index_and_wrong_section(self):
        self.assertIsNone(
            palantir._listing_link("/blog/", internal_prefix="/blog/")
        )
        self.assertIsNone(
            palantir._listing_link(
                "/newsroom/press-releases/example/",
                internal_prefix="/blog/",
            )
        )

    def test_scrape_listing_parses_blog_card_and_article_meta(self):
        listing = """
        <article>
          <h2><a href="/blog/building-with-palantir-aip/">
            Building with Palantir AIP
          </a></h2>
          <p>A practical guide.</p>
          <time datetime="2026-07-20"></time>
        </article>
        """
        article_meta = {
            "title": "Building with Palantir AIP",
            "description": "Article description",
            "date": datetime(2026, 7, 20, tzinfo=timezone.utc),
            "image": "https://www.palantir.com/image.jpg",
        }
        with (
            patch.object(palantir, "get_html", return_value=listing),
            patch.object(
                palantir,
                "_article_meta",
                return_value=article_meta,
            ),
        ):
            entries = palantir.scrape_listing(
                "Blog",
                palantir.BLOG_URL,
                set(),
                set(),
                internal_prefix="/blog/",
            )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "Blog")
        self.assertEqual(
            entries[0]["link"],
            "https://www.palantir.com/blog/building-with-palantir-aip/",
        )
        self.assertEqual(entries[0]["description"], "Article description")

    def test_media_listing_accepts_external_story(self):
        listing = """
        <article>
          <h3><a href="https://example.com/palantir-profile">
            A profile of Palantir
          </a></h3>
          <p>External coverage.</p>
          <time datetime="2026-07-18"></time>
        </article>
        """
        with patch.object(palantir, "get_html", return_value=listing):
            entries = palantir.scrape_listing(
                "Media Coverage",
                palantir.MEDIA_URL,
                set(),
                set(),
                allow_external=True,
                fetch_article=False,
            )

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["link"],
            "https://example.com/palantir-profile",
        )
        self.assertEqual(entries[0]["source"], "Media Coverage")

    def test_announcements_are_split_into_dated_entries(self):
        html = """
        <main>
          <h2>Announcements</h2>
          <h2>Investigate dataset history with Time Travel</h2>
          <p>Date published: 2026-07-23</p>
          <p>Time Travel is now available in Dataset Preview.</p>
          <h3>Getting started</h3>
          <p>Open the Time Travel tab.</p>
          <h2>Agents authenticate automatically</h2>
          <p>Date published: 2026-07-21</p>
          <p>Agents now use scoped permissions.</p>
        </main>
        """
        with patch.object(palantir, "get_html", return_value=html):
            entries = palantir.scrape_announcements(set())

        self.assertEqual(len(entries), 2)
        self.assertEqual(
            entries[0]["link"],
            (
                "https://www.palantir.com/docs/foundry/announcements"
                "#2026-07-23-investigate-dataset-history-with-time-travel"
            ),
        )
        self.assertEqual(entries[0]["source"], "Foundry Announcements")
        self.assertNotIn("Date published", entries[0]["description"])

    def test_release_notes_create_one_entry_per_date(self):
        html = """
        <main>
          <h2>Release notes</h2>
          <h2>July 23, 2026</h2>
          <h3>Features</h3>
          <p>Time Travel is now available.</p>
          <h2>July 21, 2026</h2>
          <h3>Enhancements</h3>
          <p>Restricted Views support Global Branching.</p>
        </main>
        """
        with patch.object(palantir, "get_html", return_value=html):
            entries = palantir.scrape_release_notes(set())

        self.assertEqual(len(entries), 2)
        self.assertEqual(
            entries[0]["link"],
            (
                "https://www.palantir.com/docs/foundry/release-notes"
                "#2026-07-23"
            ),
        )
        self.assertEqual(entries[0]["source"], "Foundry Release Notes")
        self.assertIn("Features", entries[0]["description"])


if __name__ == "__main__":
    unittest.main()
