import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import audacity


class AudacitySourcesTests(unittest.TestCase):
    def test_requested_native_sources_are_registered(self):
        sources = {label: url for label, url, _cap in audacity.SOURCES}
        self.assertEqual(
            sources["Audacity Forum"],
            "https://forum.audacityteam.org/latest.rss",
        )
        self.assertEqual(sources["MuseHub Blog"], "https://blog.musehub.com/feed/")

    def test_requested_html_sources_are_registered(self):
        self.assertEqual(audacity.AUDACITY_BLOG_URL, "https://www.audacityteam.org/blog/")
        self.assertEqual(
            audacity.MUSEHUB_PRODUCTS_URL,
            "https://www.musehub.com/pl-pl/new-products",
        )

    def test_audacity_blog_card_is_parsed(self):
        html = """
        <a href="/blog/audacity-4">
          <img src="/_astro/audacity.webp" />
          <small>Thursday, September 3, 2026</small>
          <h4>Audacity 4.0</h4>
          <p>A major new release.</p>
        </a>
        """
        with patch.object(audacity, "get_html", return_value=html):
            entries = audacity.scrape_audacity_blog(set())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Audacity 4.0")
        self.assertEqual(entries[0]["link"], "https://www.audacityteam.org/blog/audacity-4")
        self.assertEqual(entries[0]["date"].isoformat(), "2026-09-03T00:00:00+00:00")
        self.assertEqual(entries[0]["source"], "Audacity Blog")
        self.assertEqual(entries[0]["description"], "A major new release.")

    def test_musehub_new_product_card_is_parsed_and_cache_gated(self):
        html = """
        <article>
          <a href="/pl-pl/plugin/example"><h3>Example FX</h3></a>
          <p>Short.</p><p>A useful audio effect.</p>
          <img src="https://cdn.example/icon.png" />
        </article>
        """
        with patch.object(audacity, "get_html", return_value=html):
            entries = audacity.scrape_musehub_products(set())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["link"], "https://www.musehub.com/pl-pl/plugin/example")
        self.assertEqual(entries[0]["description"], "A useful audio effect.")
        self.assertEqual(entries[0]["source"], "MuseHub New Products")
        self.assertIsNotNone(entries[0]["date"].tzinfo)

        with patch.object(audacity, "get_html", return_value=html):
            cached = audacity.scrape_musehub_products({entries[0]["link"]})
        self.assertEqual(cached, [])


if __name__ == "__main__":
    unittest.main()
