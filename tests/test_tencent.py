import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import tencent


def async_html(items, total=None, *, include_total=True, semicolon=False):
    data = {"item": items}
    if include_total:
        data["num"] = len(items) if total is None else total
    payload = [[], {"hash": [{"expressList": {"code": 0, "msg": "ok", "data": data}}]}]
    terminator = ";</script>" if semicolon else "</script>"
    return "<script>window['__ASYNC_DATA__'] = " + json.dumps(payload) + terminator


class TencentFeedTests(unittest.TestCase):
    def test_doc_sources_lists_requested_surfaces(self):
        self.assertEqual(
            tencent.doc_sources(),
            [
                ("Tencent Newsroom", tencent.NEWSROOM_URL),
                ("Tencent Cloud Blogs", tencent.BLOGS_URL),
                ("Tencent Music Press Releases", tencent.MUSIC_RSS_URL),
            ],
        )

    def test_native_sources_use_discovered_rss_endpoints(self):
        self.assertEqual(
            tencent._NATIVE_SOURCES,
            (
                (
                    "Tencent Newsroom",
                    "https://www.tencent.com/newsroom/all-news/feed/",
                    100,
                ),
                ("Tencent Music Press Releases", tencent.MUSIC_RSS_URL, 100),
            ),
        )

    def test_parse_cloud_listing_uses_structured_async_data(self):
        html = async_html(
            [
                {
                    "newsId": "101483",
                    "cateId": "800",
                    "title": "Context Infrastructure for the AI Era",
                    "description": "<p>Structured <b>description</b>.</p>",
                    "newsTime": "2026-08-25",
                    "thumbnail": "https://example.com/blog.jpg",
                }
            ],
            total=161,
        )
        parsed = tencent.parse_listing(html)
        self.assertIsNotNone(parsed)
        entries, total = parsed
        self.assertEqual(total, 161)
        self.assertEqual(
            entries[0]["link"],
            "https://www.tencentcloud.com/dynamic/blogs/sample-article/101483",
        )
        self.assertEqual(entries[0]["description"], "Structured description .")
        self.assertEqual(entries[0]["image"], "https://example.com/blog.jpg")

    def test_parse_listing_accepts_optional_semicolon_and_integer_string_total(self):
        html = async_html(
            [{"newsId": "semi", "cateId": "800", "title": "Semicolon"}],
            total="12",
            semicolon=True,
        )
        entries, total = tencent.parse_listing(html)
        self.assertEqual(total, 12)
        self.assertEqual([entry["title"] for entry in entries], ["Semicolon"])

    def test_parse_listing_rejects_bad_totals(self):
        item = {"newsId": "one", "cateId": "800", "title": "One"}
        for html in (
            async_html([item], include_total=False),
            async_html([item], total="invalid"),
            async_html([item], total=-1),
            async_html([item], total=True),
            async_html([item, item], total=1),
        ):
            self.assertIsNone(tencent.parse_listing(html))

    def test_page_url_preserves_fetch_query_and_sets_page(self):
        url = tencent._page_url(tencent._BLOGS_FETCH_URL, 3)
        self.assertIn("lang=en", url)
        self.assertIn("pg=3", url)
        self.assertIn("from_qcintl=topnav", url)

    def test_collection_stops_at_known_cloud_history(self):
        page = async_html(
            [
                {
                    "newsId": "new",
                    "cateId": "800",
                    "title": "New",
                    "newsTime": "2026-08-29",
                },
                {
                    "newsId": "known",
                    "cateId": "800",
                    "title": "Known",
                    "newsTime": "2026-08-28",
                },
            ],
            total=24,
        )
        known = {"https://www.tencentcloud.com/dynamic/blogs/sample-article/known"}
        with patch.object(tencent.multi_rss, "get_html", return_value=page) as fetch:
            entries = tencent._collect_cloud(known)
        self.assertEqual([entry["title"] for entry in entries], ["New"])
        self.assertEqual(fetch.call_count, 1)

    def test_later_page_failure_discards_partial_cloud_batch(self):
        page_one = async_html(
            [
                {
                    "newsId": "one",
                    "cateId": "800",
                    "title": "One",
                    "newsTime": "2026-08-29",
                }
            ],
            total=24,
        )
        with patch.object(tencent.multi_rss, "get_html", side_effect=[page_one, None]):
            self.assertEqual(tencent._collect_cloud(set()), [])

    def test_empty_page_before_advertised_end_discards_partial_cloud_batch(self):
        page_one = async_html(
            [
                {
                    "newsId": "one",
                    "cateId": "800",
                    "title": "One",
                    "newsTime": "2026-08-29",
                }
            ],
            total=24,
        )
        page_two = async_html([], total=24)
        with patch.object(
            tencent.multi_rss, "get_html", side_effect=[page_one, page_two]
        ):
            self.assertEqual(tencent._collect_cloud(set()), [])

    def test_retired_press_center_cache_is_filtered(self):
        self.assertFalse(
            tencent._keep_current_source({"source": "Tencent Cloud Press Center"})
        )
        self.assertTrue(tencent._keep_current_source({"source": "Tencent Cloud Blogs"}))


if __name__ == "__main__":
    unittest.main()
