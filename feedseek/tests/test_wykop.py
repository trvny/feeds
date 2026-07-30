import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import wykop  # noqa: E402


class WykopTests(unittest.TestCase):
    def test_canonicalizes_comment_permalink_to_finding_id(self):
        item = BeautifulSoup(
            """<item>
            <guid>https://wykop.pl/link/123456/example/komentarz/987</guid>
            <link>https://example.com/article?utm_source=wykop</link>
            </item>""",
            "xml",
        ).item

        self.assertEqual(wykop.finding_id(item), "123456")
        self.assertEqual(
            wykop.canonical_item_link(item), "https://wykop.pl/link/123456"
        )

    def test_parses_media_categories_and_clean_text(self):
        item = BeautifulSoup(
            """<item xmlns:media="http://search.yahoo.com/mrss/">
            <title>  Przykładowe znalezisko  </title>
            <guid>https://wykop.pl/link/123456/example</guid>
            <link>https://example.com/news?utm_source=wykop</link>
            <pubDate>Wed, 29 Jul 2026 12:00:00 +0000</pubDate>
            <description><![CDATA[
              <p>Opis <strong>znaleziska</strong>.</p><script>trash()</script>
              <img src="//cdn.example.com/image.jpg">
            ]]></description>
            <media:thumbnail url="https://cdn.example.com/better.jpg" />
            <category>technologia</category>
            </item>""",
            "xml",
        ).item

        entry = wykop.parse_item(item, "Wykopalisko")

        self.assertEqual(entry["link"], "https://wykop.pl/link/123456")
        self.assertEqual(entry["description"], "Opis znaleziska .")
        self.assertEqual(entry["image"], "https://cdn.example.com/better.jpg")
        self.assertEqual(entry["source"], "example.com")
        self.assertEqual(entry["categories"], ["technologia"])
        self.assertEqual(entry["feed_sources"], ["Wykopalisko"])

    def test_dedupe_keeps_richest_and_combines_metadata(self):
        older = datetime(2026, 7, 28, tzinfo=timezone.utc)
        newer = datetime(2026, 7, 29, tzinfo=timezone.utc)
        sparse = {
            "title": "Tytuł",
            "link": "https://wykop.pl/link/123456",
            "date": newer,
            "description": "Tytuł",
            "source": "Wykop",
            "image": "https://cdn.example.com/image.jpg",
            "external_link": None,
            "feed_sources": ["Komentowane"],
            "categories": ["news"],
        }
        rich = {
            "title": "Tytuł",
            "link": "https://wykop.pl/link/123456/example",
            "date": older,
            "description": "Znacznie bogatszy opis znaleziska z dodatkowymi informacjami.",
            "source": "example.com",
            "image": None,
            "external_link": "https://example.com/article",
            "feed_sources": ["Wykopalisko", "Wykopane"],
            "categories": ["technologia"],
        }

        [entry] = wykop.dedupe_richest([sparse, rich])

        self.assertEqual(entry["description"], rich["description"])
        self.assertEqual(entry["image"], sparse["image"])
        self.assertEqual(entry["date"], older)
        self.assertEqual(
            entry["feed_sources"], ["Wykopane", "Komentowane", "Wykopalisko"]
        )
        self.assertEqual(entry["categories"], ["news", "technologia"])

    def test_dedupe_uses_normalized_title_as_secondary_key(self):
        first = {
            "title": "Ten sam NEWS!",
            "link": "https://wykop.pl/link/111",
            "date": datetime(2026, 7, 29, tzinfo=timezone.utc),
            "description": "Ten sam NEWS!",
            "source": "Wykop",
            "image": None,
            "external_link": None,
            "feed_sources": ["Wykopane"],
            "categories": [],
        }
        richer = {
            "title": "ten sam news",
            "link": "https://wykop.pl/link/222",
            "date": datetime(2026, 7, 28, tzinfo=timezone.utc),
            "description": "Pełny opis tej samej publikacji z drugiego widoku.",
            "source": "example.com",
            "image": "https://cdn.example.com/image.jpg",
            "external_link": "https://example.com/article",
            "feed_sources": ["Wykopalisko"],
            "categories": ["news"],
        }

        [entry] = wykop.dedupe_richest([first, richer])

        self.assertEqual(entry["description"], richer["description"])
        self.assertEqual(entry["feed_sources"], ["Wykopane", "Wykopalisko"])

    def test_title_identity_preserves_polish_letters(self):
        common = {
            "date": datetime(2026, 7, 29, tzinfo=timezone.utc),
            "description": "Opis",
            "source": "Wykop",
            "image": None,
            "external_link": None,
            "feed_sources": ["Wykopane"],
            "categories": [],
        }
        entries = wykop.dedupe_richest(
            [
                {**common, "title": "Ćma", "link": "https://wykop.pl/link/333"},
                {**common, "title": "Ma", "link": "https://wykop.pl/link/444"},
            ]
        )

        self.assertEqual(len(entries), 2)

    def test_source_failure_is_isolated(self):
        valid = """<rss><channel><item>
          <title>Drugie źródło działa</title>
          <guid>https://wykop.pl/link/42/example</guid>
          <description>Opis</description>
        </item></channel></rss>"""

        with patch.object(wykop, "get_html", side_effect=[None, valid, None]):
            entries = wykop.scrape_all()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["link"], "https://wykop.pl/link/42")
        self.assertEqual(entries[0]["feed_sources"], ["Komentowane"])

    def test_feed_description_uses_required_wording(self):
        self.assertEqual(wykop.SUBTITLE, "Znaleziska z Wykopaliska")


if __name__ == "__main__":
    unittest.main()
