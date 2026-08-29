import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from uber import SOURCES, doc_sources, parse_listing  # noqa: E402


class UberFeedTests(unittest.TestCase):
    """Parser coverage for the three Uber editorial surfaces."""

    def test_doc_sources_lists_all_requested_surfaces(self):
        self.assertEqual(
            doc_sources(),
            [(label, url) for label, url, _prefix, _locale in SOURCES],
        )

    def test_parse_us_listing_uses_card_heading_and_datetime(self):
        html = """
        <article>
          <a href="/us/en/blog/software-factory/">
            <img src="/images/factory.jpg">
            <span>AI / ML</span>
            <h3>Running a Software Factory Efficiently at Uber Scale</h3>
            <time datetime="2026-08-27">August 27, 2026</time>
          </a>
        </article>
        """
        entries = parse_listing(
            html,
            label="Uber Blog US",
            base_url="https://www.uber.com/us/en/blog/",
            path_prefix="/us/en/blog/",
            locale="en",
        )
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(
            entry["link"], "https://www.uber.com/us/en/blog/software-factory/"
        )
        self.assertEqual(
            entry["title"], "Running a Software Factory Efficiently at Uber Scale"
        )
        self.assertEqual(entry["date"].isoformat(), "2026-08-27T00:00:00+00:00")
        self.assertEqual(entry["source"], "Uber Blog US")
        self.assertEqual(entry["image"], "https://www.uber.com/images/factory.jpg")

    def test_parse_polish_listing_understands_polish_months(self):
        html = """
        <div class="card">
          <a href="/pl/pl/blog/husker-share/"><h3>Przedstawiamy Husker Share</h3></a>
          <span>Szkolnictwo wyższe</span>
          <span>14 sierpnia 2026</span>
        </div>
        """
        entries = parse_listing(
            html,
            label="Uber Blog PL",
            base_url="https://www.uber.com/pl/pl/blog/",
            path_prefix="/pl/pl/blog/",
            locale="pl",
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["date"].isoformat(), "2026-08-14T00:00:00+00:00")
        self.assertEqual(entries[0]["source"], "Uber Blog PL")

    def test_parse_listing_skips_known_and_navigation_links(self):
        html = """
        <div><a href="/us/en/blog/">Blog</a></div>
        <article>
          <a href="/us/en/newsroom/live-video-teen-trips/">
            <h3>Introducing Live Video on Teen Trips</h3>
            <span>August 25, 2026</span>
          </a>
        </article>
        """
        known = {"https://www.uber.com/us/en/newsroom/live-video-teen-trips/"}
        entries = parse_listing(
            html,
            label="Uber Newsroom US",
            base_url="https://www.uber.com/us/en/newsroom/",
            path_prefix="/us/en/newsroom/",
            locale="en",
            known_links=known,
        )
        self.assertEqual(entries, [])


if __name__ == "__main__":
    unittest.main()
