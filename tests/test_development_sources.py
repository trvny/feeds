import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import development


class DevelopmentSourceTests(unittest.TestCase):
    def test_latest_packages_is_capped_at_three(self):
        source = next(item for item in development.SOURCES if item[0] == "Django Packages latest")
        self.assertEqual(source[2], 3)

    def test_direct_django_sources_precede_community_aggregator(self):
        labels = [label for label, _, _ in development.SOURCES]
        community = labels.index("Django Community")
        self.assertLess(labels.index("TestDriven.io"), community)
        self.assertLess(labels.index("Django News"), community)
        self.assertLess(labels.index("Django Weblog"), community)

    def test_rust_releases_parse_dates_and_skip_known_links(self):
        html = """
        <table>
          <tr><td class="bn"><a href="https://blog.rust-lang.org/2026/07/16/Rust-1.97.1/">Announcing Rust 1.97.1</a></td></tr>
          <tr><td class="bn"><a href="https://blog.rust-lang.org/2026/07/09/Rust-1.97.0/">Announcing Rust 1.97.0</a></td></tr>
        </table>
        """
        known = {"https://blog.rust-lang.org/2026/07/16/Rust-1.97.1/"}

        with patch.object(development, "get_html", return_value=html):
            entries = development.scrape_rust_releases(known)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Announcing Rust 1.97.0")
        self.assertEqual(entries[0]["source"], "Rust Releases")
        self.assertEqual(entries[0]["date"].isoformat(), "2026-07-09T00:00:00+00:00")

    def test_django_packages_changelog_parses_live_shape(self):
        html = """
        <div class="flex-shrink-0 md:w-1/3">
          <div class="text-muted-foreground mb-1 text-sm">March 7, 2026</div>
          <h2 class="text-foreground text-xl font-bold">
            <a href="/changelog/postgresql-fts/">🔎 PostgreSQL full-text search for djangopackages</a>
          </h2>
        </div>
        """

        with patch.object(development, "get_html", return_value=html):
            entries = development.scrape_django_packages_changelog(set())

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["link"],
            "https://djangopackages.org/changelog/postgresql-fts/",
        )
        self.assertEqual(entries[0]["date"].isoformat(), "2026-03-07T00:00:00+00:00")
        self.assertEqual(entries[0]["source"], "Django Packages changelog")


if __name__ == "__main__":
    unittest.main()
