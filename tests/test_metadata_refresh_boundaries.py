import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import multi_rss  # noqa: E402
from entry_refresh import merge_refreshed_entries  # noqa: E402


class MetadataRefreshBoundaryTests(unittest.TestCase):
    def test_cross_source_duplicate_does_not_refresh_cached_metadata(self):
        date = datetime(2026, 8, 1, tzinfo=timezone.utc)
        cached = [
            {
                "link": "http://www.example.com/post/?utm_source=legacy",
                "title": "Primary source title",
                "source": "Primary",
                "date": date,
                "entry_id": "tag:example.test,2026:persisted",
            }
        ]
        fresh = [
            {
                "link": "https://example.com/post",
                "title": "Duplicate source title",
                "source": "Secondary",
                "date": date,
            }
        ]

        merged = merge_refreshed_entries(fresh, cached)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["title"], "Primary source title")
        self.assertEqual(merged[0]["source"], "Primary")
        self.assertEqual(merged[0]["entry_id"], "tag:example.test,2026:persisted")

    def test_custom_scraper_entries_stay_on_add_only_merge_path(self):
        cached = {
            "entries": [
                {
                    "link": "http://www.example.com/post/?utm_source=legacy",
                    "title": "Cached title",
                    "source": "Custom",
                    "date": "2026-08-01T00:00:00+00:00",
                }
            ]
        }
        native = {
            "link": "https://native.example/new",
            "title": "Native article",
            "source": "Native",
            "date": datetime(2026, 8, 24, tzinfo=timezone.utc),
        }
        custom = {
            "link": "https://example.com/post",
            "title": "Custom variant",
            "source": "Custom",
            "date": datetime(2026, 8, 24, tzinfo=timezone.utc),
        }
        fg = MagicMock()

        def custom_scraper(_known_links):
            return [custom]

        with (
            patch.object(multi_rss, "load_cache", return_value=cached),
            patch.object(multi_rss, "scrape_feed", return_value=[native]),
            patch.object(
                multi_rss,
                "merge_refreshed_entries",
                wraps=multi_rss.merge_refreshed_entries,
            ) as refresh_merge,
            patch.object(
                multi_rss,
                "merge_entries",
                wraps=multi_rss.merge_entries,
            ) as add_only_merge,
            patch.object(multi_rss, "enrich_entries"),
            patch.object(multi_rss, "save_cache"),
            patch.object(multi_rss, "generate_atom_feed", return_value=fg),
            patch.object(multi_rss, "save_atom_feed"),
        ):
            self.assertTrue(
                multi_rss.run(
                    feed_name="example",
                    title="Example",
                    subtitle="Example",
                    blog_url="https://example.com/",
                    author="Example",
                    sources=(("Native", "https://native.example/feed.xml", 20),),
                    extra_scrapers=(custom_scraper,),
                )
            )

        self.assertEqual(refresh_merge.call_args.args[0], [native])
        self.assertEqual(add_only_merge.call_args.args[0], [custom])


if __name__ == "__main__":
    unittest.main()
