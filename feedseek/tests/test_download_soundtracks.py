import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import download_soundtracks  # noqa: E402


class DownloadSoundtracksTests(unittest.TestCase):
    def test_homepage_parser_extracts_post_metadata(self):
        html = """
        <article>
          <h2><a href="/movie_soundtracks/example-score/">Example Score</a></h2>
          <a rel="category tag" href="/category/movie_soundtracks/">Movie Soundtracks</a>
          <time datetime="2026-07-29T12:30:00+00:00">July 29, 2026</time>
          <img data-src="/images/example.jpg">
          <div class="entry-summary"><p>Genre: Score. Audio codec: FLAC.</p></div>
        </article>
        """

        entries = download_soundtracks.parse_homepage(html)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Example Score")
        self.assertEqual(
            entries[0]["link"],
            "https://download-soundtracks.com/movie_soundtracks/example-score/",
        )
        self.assertEqual(
            entries[0]["source"],
            "Download Soundtracks / Movie Soundtracks",
        )
        self.assertEqual(entries[0]["date"].isoformat(), "2026-07-29T12:30:00+00:00")
        self.assertEqual(
            entries[0]["image"],
            "https://download-soundtracks.com/images/example.jpg",
        )
        self.assertIn("Audio codec", entries[0]["description"])

    def test_homepage_parser_skips_known_and_non_article_links(self):
        known = "https://download-soundtracks.com/game_sountdtracks/known-game/"
        html = f"""
        <article><h2><a href="{known}">Known Game</a></h2></article>
        <article><h2><a href="https://example.com/wrong-host/">Wrong host</a></h2></article>
        <article><h2><a href="/category/movie_soundtracks/">Category</a></h2></article>
        <article><h2><a href="/trailer-music/new-album/">New Album</a></h2></article>
        """

        entries = download_soundtracks.parse_homepage(html, {known})

        self.assertEqual([entry["title"] for entry in entries], ["New Album"])

    def test_scraper_reads_website_directly(self):
        html = """
        <article>
          <h2><a href="/television-soundtracks/new-series/">New Series</a></h2>
        </article>
        """
        with patch.object(download_soundtracks, "get_html", return_value=html) as website:
            entries = download_soundtracks.scrape_download_soundtracks(set())

        self.assertEqual([entry["title"] for entry in entries], ["New Series"])
        website.assert_called_once_with(download_soundtracks.BLOG_URL)

    def test_scraper_skips_known_website_entry(self):
        known = "https://download-soundtracks.com/movie_soundtracks/known-score"
        html = """
        <article>
          <h2><a href="http://www.download-soundtracks.com/movie_soundtracks/known-score/?utm_source=homepage">Known Score</a></h2>
        </article>
        <article>
          <h2><a href="/game_sountdtracks/new-game/">New Game</a></h2>
        </article>
        """
        with patch.object(download_soundtracks, "get_html", return_value=html):
            entries = download_soundtracks.scrape_download_soundtracks({known})

        self.assertEqual([entry["title"] for entry in entries], ["New Game"])

    def test_scraper_ignores_host_disabled_page(self):
        html = """
        <html><body>
          <h1>Account disabled</h1>
          <p>Account disabled by server administrator due to DMCA request.</p>
        </body></html>
        """
        with patch.object(download_soundtracks, "get_html", return_value=html):
            entries = download_soundtracks.scrape_download_soundtracks(set())

        self.assertEqual(entries, [])

    def test_docs_point_to_website_not_native_feed(self):
        self.assertEqual(
            download_soundtracks.doc_sources(),
            [("Website", "https://download-soundtracks.com/")],
        )


if __name__ == "__main__":
    unittest.main()
