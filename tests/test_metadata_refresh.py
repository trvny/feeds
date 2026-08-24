import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import multi_rss  # noqa: E402
import utils  # noqa: E402
from entry_refresh import merge_refreshed_entries, refresh_cached_entry  # noqa: E402


class SafeMetadataRefreshTests(unittest.TestCase):
    def test_default_merge_entries_remains_add_only(self):
        cached = [
            {
                "link": "https://example.com/post",
                "title": "Old title",
                "date": datetime(2026, 8, 1, tzinfo=timezone.utc),
            }
        ]
        fresh = [
            {
                "link": "https://example.com/post",
                "title": "New title",
                "date": datetime(2026, 8, 2, tzinfo=timezone.utc),
            }
        ]

        merged = utils.merge_entries(fresh, cached)

        self.assertEqual(merged[0]["title"], "Old title")

    def test_refresh_updates_upstream_metadata_but_preserves_local_state(self):
        old_date = datetime(2026, 8, 1, tzinfo=timezone.utc)
        new_date = datetime(2026, 8, 2, tzinfo=timezone.utc)
        cached = {
            "link": "https://example.com/post",
            "title": "Old title",
            "description": "Old description",
            "source": "Old source",
            "date": old_date,
            "image": "https://example.com/old.jpg",
            "image_width": 1200,
            "image_height": 630,
            "entry_id": "tag:example.test,2026:persisted",
            "article_url": "https://example.com/resolved-post",
            "image_checked": True,
            "image_attempts": 2,
            "custom_cache_state": "keep-me",
        }
        fresh = {
            "link": cached["link"],
            "title": "New title",
            "description": "New description",
            "source": "New source",
            "date": new_date,
            "image": "https://example.com/new.jpg",
        }

        refreshed = refresh_cached_entry(cached, fresh)

        self.assertEqual(refreshed["title"], "New title")
        self.assertEqual(refreshed["description"], "New description")
        self.assertEqual(refreshed["source"], "New source")
        self.assertEqual(refreshed["date"], new_date)
        self.assertEqual(refreshed["image"], "https://example.com/new.jpg")
        self.assertNotIn("image_width", refreshed)
        self.assertNotIn("image_height", refreshed)
        self.assertEqual(refreshed["entry_id"], cached["entry_id"])
        self.assertEqual(refreshed["article_url"], cached["article_url"])
        self.assertTrue(refreshed["image_checked"])
        self.assertEqual(refreshed["image_attempts"], 2)
        self.assertEqual(refreshed["custom_cache_state"], "keep-me")

    def test_missing_fresh_metadata_does_not_erase_richer_cached_values(self):
        cached = {
            "link": "https://example.com/post",
            "title": "Old title",
            "description": "A detailed cached summary.",
            "image": "https://example.com/cached.jpg",
            "date": datetime(2026, 8, 1, tzinfo=timezone.utc),
        }
        fresh = {
            "link": cached["link"],
            "title": "Updated title",
            "description": "Updated title",
            "image": None,
            "date": datetime(2026, 8, 2, tzinfo=timezone.utc),
        }

        refreshed = refresh_cached_entry(cached, fresh)

        self.assertEqual(refreshed["title"], "Updated title")
        self.assertEqual(refreshed["description"], "A detailed cached summary.")
        self.assertEqual(refreshed["image"], "https://example.com/cached.jpg")

    def test_duplicate_new_entries_still_keep_first_occurrence(self):
        date = datetime(2026, 8, 1, tzinfo=timezone.utc)
        first = {
            "link": "https://example.com/post",
            "title": "First source",
            "date": date,
        }
        second = {
            "link": first["link"],
            "title": "Second source",
            "date": date,
        }

        merged = merge_refreshed_entries([first, second], [])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["title"], "First source")


class MultiRssMetadataRefreshTests(unittest.TestCase):
    def test_dateless_cached_item_keeps_first_seen_date(self):
        link = "https://example.com/dateless"
        first_seen = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        xml = f"""
        <rss><channel><item>
          <title>Dateless post</title>
          <link>{link}</link>
          <description>Summary</description>
        </item></channel></rss>
        """

        with patch.object(multi_rss, "get_html", return_value=xml):
            entries = multi_rss.scrape_feed(
                "Native",
                "https://example.com/feed.xml",
                set(),
                cached_dates={link: first_seen},
            )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["date"], first_seen)

    def test_run_refreshes_native_entry_and_keeps_custom_scraper_cache_gated(self):
        link = "https://example.com/post"
        old_date = datetime(2026, 8, 1, tzinfo=timezone.utc)
        new_date = datetime(2026, 8, 2, tzinfo=timezone.utc)
        cache = {
            "entries": [
                {
                    "link": link,
                    "title": "Old title",
                    "description": "Old description",
                    "source": "Native",
                    "date": old_date.isoformat(),
                    "entry_id": "tag:example.test,2026:persisted",
                    "image": "https://example.com/old.jpg",
                }
            ]
        }
        fresh = {
            "link": link,
            "title": "New title",
            "description": "New description",
            "source": "Native",
            "date": new_date,
            "image": "https://example.com/new.jpg",
        }
        custom_known_links = []

        def custom_scraper(known_links):
            custom_known_links.append(set(known_links))
            return []

        fg = MagicMock()
        with (
            patch.object(multi_rss, "load_cache", return_value=cache),
            patch.object(multi_rss, "scrape_feed", return_value=[fresh]) as scrape,
            patch.object(multi_rss, "enrich_entries"),
            patch.object(multi_rss, "save_cache") as save_cache,
            patch.object(multi_rss, "generate_atom_feed", return_value=fg),
            patch.object(multi_rss, "save_atom_feed"),
        ):
            result = multi_rss.run(
                feed_name="example",
                title="Example",
                subtitle="Example",
                blog_url="https://example.com/",
                author="Example",
                sources=(("Native", "https://example.com/feed.xml", 20),),
                extra_scrapers=(custom_scraper,),
            )

        self.assertTrue(result)
        scrape_args, scrape_kwargs = scrape.call_args
        self.assertEqual(scrape_args[2], set())
        self.assertEqual(scrape_kwargs["cached_dates"], {link: old_date})
        self.assertEqual(custom_known_links, [{link}])

        saved = save_cache.call_args.args[1]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["title"], "New title")
        self.assertEqual(saved[0]["description"], "New description")
        self.assertEqual(saved[0]["image"], "https://example.com/new.jpg")
        self.assertEqual(saved[0]["entry_id"], "tag:example.test,2026:persisted")


if __name__ == "__main__":
    unittest.main()
