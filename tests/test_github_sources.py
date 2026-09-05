import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import github


class GitHubSourceTests(unittest.TestCase):
    def test_requested_engineering_sources_are_wired_in(self):
        source_urls = {label: url for label, url, _ in github.SOURCES}

        self.assertEqual(
            source_urls["Mergify Changelog"],
            "https://docs.mergify.com/changelog/rss.xml",
        )
        self.assertNotIn("Devin Desktop", source_urls)
        self.assertEqual(github.EXTRA_SCRAPERS, (github.scrape_beeware_news,))
        self.assertFalse(github._active_cache_entry({"source": "Devin Desktop"}))
        self.assertFalse(github._active_cache_entry({"source": "Devin Release Notes"}))
        self.assertTrue(github._active_cache_entry({"source": "GitHub Changelog"}))


if __name__ == "__main__":
    unittest.main()
