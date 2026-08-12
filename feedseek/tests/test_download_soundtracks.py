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

    def test_homepage_parser_leaves_dateless_entry_for_central_freeze(self):
        html = """
        <article><h2><a href="/movie_soundtracks/no-date/">No Date</a></h2></article>
        """

        entry = download_soundtracks.parse_homepage(html)[0]

        self.assertIsNone(entry["date"])

    def test_homepage_parser_accepts_entry_title_class(self):
        html = """
        <article>
          <div class="entry-title"><a href="/movie_soundtracks/class-title/">Class Title</a></div>
        </article>
        """

        entries = download_soundtracks.parse_homepage(html)

        self.assertEqual([entry["title"] for entry in entries], ["Class Title"])

    def test_homepage_parser_publishes_normalized_link(self):
        raw = "http://www.download-soundtracks.com/movie_soundtracks/score/?utm_source=home#track"
        html = f"""
        <article><h2><a href="{raw}">Score</a></h2></article>
        """

        entry = download_soundtracks.parse_homepage(html)[0]

        self.assertEqual(entry["link"], download_soundtracks.normalize_link(raw))

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

    def test_scraper_stops_when_listing_page_repeats(self):
        html = """
        <article><h2><a href="/movie_soundtracks/same/">Same</a></h2></article>
        """
        with patch.object(download_soundtracks, "get_html", return_value=html) as website:
            entries = download_soundtracks.scrape_download_soundtracks(set())

        self.assertEqual([entry["title"] for entry in entries], ["Same"])
        self.assertEqual(website.call_count, 2)

    def test_scraper_continues_past_one_cached_only_page(self):
        known = "https://download-soundtracks.com/movie_soundtracks/known/"
        first = f"""
        <article><h2><a href="{known}">Known</a></h2></article>
        """
        second = """
        <article><h2><a href="/movie_soundtracks/backfill/">Backfill</a></h2></article>
        """
        with patch.object(
            download_soundtracks, "get_html", side_effect=[first, second, None]
        ):
            entries = download_soundtracks.scrape_download_soundtracks({known})

        self.assertEqual([entry["title"] for entry in entries], ["Backfill"])

    def test_scraper_stops_after_consecutive_cached_only_pages(self):
        first_link = "https://download-soundtracks.com/movie_soundtracks/known-one/"
        second_link = "https://download-soundtracks.com/movie_soundtracks/known-two/"
        first = f"""
        <article><h2><a href="{first_link}">Known One</a></h2></article>
        """
        second = f"""
        <article><h2><a href="{second_link}">Known Two</a></h2></article>
        """
        with patch.object(
            download_soundtracks, "get_html", side_effect=[first, second]
        ) as website:
            entries = download_soundtracks.scrape_download_soundtracks(
                {first_link, second_link}
            )

        self.assertEqual(entries, [])
        self.assertEqual(website.call_count, download_soundtracks.MAX_STALE_PAGES)

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


if __name__ == "__main__":
    unittest.main()
