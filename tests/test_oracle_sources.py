import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import oracle
from utils import dedupe_entries


class OracleSourceTests(unittest.TestCase):
    def test_expected_native_sources_are_present(self):
        urls = {url for _, url, _ in oracle.SOURCES}
        self.assertEqual(
            urls,
            {
                "https://blogs.oracle.com/feed",
                "https://blogs.oracle.com/developers/feed",
                "https://blogs.oracle.com/connect/feed",
                "https://www.oracle.com/corporate/press/rss/rss-pr.xml",
                "https://blogs.oracle.com/java/feed",
                "https://blogs.oracle.com/linux/feed",
                "https://blogs.oracle.com/cloud-infrastructure/feed",
                "https://blogs.oracle.com/virtualization/feed",
                "https://blogs.oracle.com/scoter/feed",
                "https://forums.oracle.com/ords/apexds/feeds/domain/dev-community/",
                "https://inside.java/feed.xml",
                "https://rss.libsyn.com/shows/294923/destinations/2318780.xml",
            },
        )
        self.assertNotIn("https://dev.java/news/", urls)

    def test_specific_channels_precede_general_oracle_blog(self):
        labels = [label for label, _, _ in oracle.SOURCES]
        general = labels.index("Oracle Blogs")
        for label in (
            "Oracle Developers",
            "Oracle Java",
            "Oracle Linux",
            "Oracle Cloud Infrastructure",
            "Oracle Virtualization",
        ):
            self.assertLess(labels.index(label), general)

        entries = [
            {
                "title": "New Java feature",
                "link": "https://blogs.oracle.com/java/new-java-feature",
                "date": None,
                "source": "Oracle Java",
            },
            {
                "title": "New Java feature",
                "link": "https://blogs.oracle.com/post/new-java-feature",
                "date": None,
                "source": "Oracle Blogs",
            },
        ]
        deduped = dedupe_entries(entries)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["source"], "Oracle Java")

    def test_high_churn_and_niche_sources_have_small_caps(self):
        intake = {label: cap for label, _, cap in oracle.SOURCES}
        self.assertLessEqual(intake["Oracle Developer Community"], 10)
        self.assertLessEqual(intake["Oracle Scoter"], 8)
        self.assertLessEqual(intake["Inside Java Podcast"], 10)
        self.assertLessEqual(oracle.PER_SOURCE_QUOTA["Oracle Developer Community"], 14)
        self.assertLessEqual(oracle.PER_SOURCE_QUOTA["Inside Java Podcast"], 12)


if __name__ == "__main__":
    unittest.main()
