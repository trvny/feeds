import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import dwutygodnik  # noqa: E402


class DwutygodnikTests(unittest.TestCase):
    def test_listing_extracts_articles_and_poetry(self):
        html = """
        <main>
          <article>
            <a href="/artykul/12345-nowy-film.html">
              <h2>Nowy film i stare pytania</h2>
              <img src="/media/film.jpg">
            </a>
            <a href="/film">Film</a>
            <time datetime="2026-07-29T10:00:00+02:00"></time>
            <p>Krótki opis tekstu filmowego.</p>
          </article>
          <div class="card">
            <h3><a href="https://dwutygodnik.com/wiersz/11522-lukasz-kaminski.html">
              Łukasz Kamiński
            </a></h3>
            <span>28 lipca 2026</span>
          </div>
        </main>
        """

        entries = dwutygodnik.parse_listing(html)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["source"], "Dwutygodnik / Film")
        self.assertEqual(entries[0]["image"], "https://www.dwutygodnik.com/media/film.jpg")
        self.assertEqual(entries[0]["date"].date().isoformat(), "2026-07-29")
        self.assertEqual(entries[1]["source"], "Dwutygodnik / Poezja")
        self.assertEqual(entries[1]["date"].date().isoformat(), "2026-07-28")

    def test_listing_rejects_navigation_and_other_hosts(self):
        html = """
        <a href="/film"><h2>Film</h2></a>
        <a href="https://stypendiawarszawy.dwutygodnik.com/artykul/1-test.html">
          <h2>Stypendia</h2>
        </a>
        <a href="/artykul/777-prawdziwy-tekst.html"><h2>Prawdziwy tekst</h2></a>
        """

        entries = dwutygodnik.parse_listing(html)

        self.assertEqual([entry["title"] for entry in entries], ["Prawdziwy tekst"])

    def test_sitemap_uses_original_links_and_last_modified_dates(self):
        xml = """
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://www.dwutygodnik.com/artykul/12000-nowy-esej.html</loc>
            <lastmod>2026-07-30</lastmod>
          </url>
          <url>
            <loc>https://www.dwutygodnik.com/wiersz/11999-trzy-wiersze.html</loc>
            <lastmod>2026-07-29</lastmod>
          </url>
          <url><loc>https://www.dwutygodnik.com/o-nas</loc></url>
        </urlset>
        """

        entries = dwutygodnik.parse_sitemap(xml)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["title"], "Nowy esej")
        self.assertEqual(entries[0]["date"].date().isoformat(), "2026-07-30")
        self.assertEqual(entries[1]["source"], "Dwutygodnik / Poezja")

    def test_google_news_is_used_only_after_direct_sources_fail(self):
        google_xml = """
        <rss><channel><item>
          <title>Tekst z indeksu - Dwutygodnik.com</title>
          <link>https://news.google.com/rss/articles/example</link>
          <pubDate>Wed, 29 Jul 2026 08:00:00 GMT</pubDate>
          <description>Opis tekstu</description>
        </item></channel></rss>
        """

        with patch.object(
            dwutygodnik,
            "get_html",
            side_effect=[None, None, google_xml],
        ):
            entries = dwutygodnik.scrape_dwutygodnik(set())

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Tekst z indeksu")
        self.assertEqual(entries[0]["date"].date().isoformat(), "2026-07-29")

    def test_known_links_are_not_emitted_again(self):
        link = "https://www.dwutygodnik.com/artykul/12345-nowy-film.html"
        html = f'<a href="{link}"><h2>Nowy film i stare pytania</h2></a>'

        self.assertEqual(dwutygodnik.parse_listing(html, {link}), [])


if __name__ == "__main__":
    unittest.main()
