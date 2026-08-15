import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import ubuntu
from utils import dedupe_entries


class UbuntuSourceTests(unittest.TestCase):
    def test_expected_sources_are_present(self):
        urls = {url for _, url, _ in ubuntu.SOURCES}
        self.assertEqual(
            urls,
            {
                "https://ubuntu.com/blog/feed",
                "https://canonical.com/blog/feed",
                "https://ubuntustudio.org/feed/",
                "https://planet.ubuntu.com/feed",
                "https://www.omgubuntu.co.uk/feed",
                "https://feeds.feedburner.com/UbuntuhandbookNewsTutorialsHowtosForUbuntuLinux",
            },
        )

    def test_official_ubuntu_precedes_canonical_for_title_dedupe(self):
        labels = [label for label, _, _ in ubuntu.SOURCES]
        self.assertLess(labels.index("Ubuntu Blog"), labels.index("Canonical Blog"))

        entries = [
            {
                "title": "Canonical launches Ubuntu Core 26",
                "link": "https://ubuntu.com/blog/ubuntu-core-26",
                "date": None,
                "source": "Ubuntu Blog",
            },
            {
                "title": "Canonical launches Ubuntu Core 26",
                "link": "https://canonical.com/blog/ubuntu-core-26",
                "date": None,
                "source": "Canonical Blog",
            },
        ]
        deduped = dedupe_entries(entries)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["source"], "Ubuntu Blog")

    def test_no_high_volume_source_can_dominate_feed(self):
        self.assertLessEqual(ubuntu.PER_SOURCE_QUOTA["Planet Ubuntu"], 30)
        self.assertLessEqual(ubuntu.PER_SOURCE_QUOTA["OMG! Ubuntu"], 30)
        self.assertLessEqual(ubuntu.PER_SOURCE_QUOTA["UbuntuHandbook"], 20)
        self.assertLessEqual(max(cap for _, _, cap in ubuntu.SOURCES), 24)


if __name__ == "__main__":
    unittest.main()
