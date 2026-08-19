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
        self.assertEqual(
            source_urls["Devin Desktop"],
            "https://docs.devin.ai/desktop/changelog/rss.xml",
        )
        self.assertEqual(
            github.DEVIN_RELEASE_NOTES_URL,
            "https://docs.devin.ai/release-notes/overview",
        )
        self.assertIn(github.collect_devin_release_notes, github.EXTRA_SCRAPERS)


if __name__ == "__main__":
    unittest.main()
