import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import download_soundtracks  # noqa: E402


class DownloadSoundtracksTests(unittest.TestCase):
    """Tests for the direct Download Soundtracks website scraper."""

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

    def test_homepage_parser_stamps_dateless_entry(self):
        html = """
        <article><h2><a href="/movie_soundtracks/no-date/">No Date</a></h2></article>
        """

        entries = download_soundtracks.parse_homepage(html)

        self.assertIsNotNone(entries[0]["date"])
        self.assertIsNotNone(entries[0]["date"].tzinfo)

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
        with patch.object(
            download_soundtracks, "get_html", side_effect=[html, None]
        ) as website:
            entries = download_soundtracks.scrape_download_soundtracks(set())

        self.assertEqual([entry["title"] for entry in entries], ["New Series"])
        self.assertEqual(
            website.call_args_list,
            [
                call(download_soundtracks.BLOG_URL),
                call("https://download-soundtracks.com/page/2/"),
            ],
        )

    def test_scraper_paginates_website(self):
        first = """
        <article><h2><a href="/movie_soundtracks/first/">First</a></h2></article>
        """
        second = """
        <article><h2><a href="/game_sountdtracks/second/">Second</a></h2></article>
        """
        with patch.object(
            download_soundtracks, "get_html", side_effect=[first, second, None]
        ):
            entries = download_soundtracks.scrape_download_soundtracks(set())

        self.assertEqual(
            [entry["title"] for entry in entries],
            ["First", "Second"],
        )

    def test_scraper_normalizes_duplicates_across_pages(self):
        first = """
        <article><h2><a href="/movie_soundtracks/same/">Same</a></h2></article>
        """
        second = """
        <article><h2><a href="http://www.download-soundtracks.com/movie_soundtracks/same/?utm_source=page2">Same duplicate</a></h2></article>
        <article><h2><a href="/movie_soundtracks/new/">New</a></h2></article>
        """
        with patch.object(
            download_soundtracks, "get_html", side_effect=[first, second, None]
        ):
            entries = download_soundtracks.scrape_download_soundtracks(set())

        self.assertEqual([entry["title"] for entry in entries], ["Same", "New"])

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
        with patch.object(
            download_soundtracks, "get_html", side_effect=[html, None]
        ):
            entries = download_soundtracks.scrape_download_soundtracks({known})

        self.assertEqual([entry["title"] for entry in entries], ["New Game"])

    def test_scraper_ignores_page_without_articles(self):
        html = """
        <html><body>
          <h1>Account disabled</h1>
          <p>Account disabled by server administrator due to DMCA request.</p>
        </body></html>
        """
        with patch.object(download_soundtracks, "get_html", return_value=html) as website:
            entries = download_soundtracks.scrape_download_soundtracks(set())

        self.assertEqual(entries, [])
        website.assert_called_once_with(download_soundtracks.BLOG_URL)

    def test_docs_list_all_crawled_pages(self):
        urls = [url for _, url in download_soundtracks.doc_sources()]

        self.assertEqual(
            urls,
            [download_soundtracks.BLOG_URL]
            + [
                f"https://download-soundtracks.com/page/{page}/"
                for page in range(2, download_soundtracks.MAX_PAGES + 1)
            ],
        )


if __name__ == "__main__":
    unittest.main()
