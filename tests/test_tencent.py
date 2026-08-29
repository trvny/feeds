import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import tencent
from tencent import (
    BLOGS_URL,
    PRESS_URL,
    _collect_source,
    _page_url,
    doc_sources,
    parse_listing,
)


def async_html(items, total=None):
    """Build a minimal Tencent ``__ASYNC_DATA__`` listing fixture."""
    payload = [[], {"hash": [{"expressList": {"code": 0, "msg": "ok", "data": {
        "item": items,
        "num": len(items) if total is None else total,
    }}}]}]
    return "<script>window['__ASYNC_DATA__'] = " + json.dumps(payload) + "</script>"


class TencentFeedTests(unittest.TestCase):
    """Structured Tencent listing and pagination coverage."""

    def test_doc_sources_lists_both_requested_surfaces(self):
        self.assertEqual(
            doc_sources(),
            [("Tencent Cloud Blogs", BLOGS_URL), ("Tencent Cloud Press Center", PRESS_URL)],
        )

    def test_parse_blog_listing_uses_structured_async_data(self):
        html = async_html([
            {
                "newsId": "101483",
                "cateId": "800",
                "title": "Context Infrastructure for the AI Era",
                "description": "<p>Structured <b>description</b>.</p>",
                "newsTime": "2026-08-25",
                "thumbnail": "https://example.com/blog.jpg",
            }
        ], total=161)
        parsed = parse_listing(html, label="Tencent Cloud Blogs", category="800")
        self.assertIsNotNone(parsed)
        entries, total = parsed
        self.assertEqual(total, 161)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["link"], "https://www.tencentcloud.com/dynamic/blogs/sample-article/101483")
        self.assertEqual(entries[0]["description"], "Structured description .")
        self.assertEqual(entries[0]["date"].isoformat(), "2026-08-25T00:00:00+00:00")
        self.assertEqual(entries[0]["image"], "https://example.com/blog.jpg")

    def test_parse_press_listing_uses_news_details_route(self):
        html = async_html([
            {
                "newsId": "101494",
                "cateId": "400",
                "title": "Press release",
                "description": "News",
                "newsTime": "2026-08-28",
            }
        ])
        entries, _total = parse_listing(
            html, label="Tencent Cloud Press Center", category="400"
        )
        self.assertEqual(entries[0]["link"], "https://www.tencentcloud.com/dynamic/news-details/101494")

    def test_page_url_preserves_query_and_sets_page(self):
        url = _page_url(BLOGS_URL, 3)
        self.assertIn("lang=en", url)
        self.assertIn("pg=3", url)
        self.assertIn("from_qcintl=topnav", url)

    def test_collection_stops_after_page_containing_known_history(self):
        page_one = async_html([
            {"newsId": "new", "cateId": "800", "title": "New", "newsTime": "2026-08-29"},
            {"newsId": "known", "cateId": "800", "title": "Known", "newsTime": "2026-08-28"},
        ], total=24)
        fetched = []

        def fake_get_html(url):
            fetched.append(url)
            return page_one

        known = {"https://www.tencentcloud.com/dynamic/blogs/sample-article/known"}
        with patch.object(tencent.multi_rss, "get_html", side_effect=fake_get_html):
            entries = _collect_source(
                label="Tencent Cloud Blogs", url=BLOGS_URL, category="800", known_links=known
            )
        self.assertEqual([entry["title"] for entry in entries], ["New"])
        self.assertEqual(len(fetched), 1)

    def test_later_page_failure_discards_partial_source_batch(self):
        page_one = async_html([
            {"newsId": "one", "cateId": "800", "title": "One", "newsTime": "2026-08-29"},
        ], total=24)
        with patch.object(tencent.multi_rss, "get_html", side_effect=[page_one, None]):
            entries = _collect_source(
                label="Tencent Cloud Blogs", url=BLOGS_URL, category="800", known_links=set()
            )
        self.assertEqual(entries, [])

    def test_empty_page_before_advertised_end_discards_partial_batch(self):
        """An inconsistent empty continuation page must not advance cached history."""
        page_one = async_html([
            {"newsId": "one", "cateId": "800", "title": "One", "newsTime": "2026-08-29"},
        ], total=24)
        page_two = async_html([], total=24)
        with patch.object(tencent.multi_rss, "get_html", side_effect=[page_one, page_two]):
            entries = _collect_source(
                label="Tencent Cloud Blogs", url=BLOGS_URL, category="800", known_links=set()
            )
        self.assertEqual(entries, [])

    def test_malformed_async_payload_is_rejected(self):
        self.assertIsNone(parse_listing("<html></html>", label="Tencent", category="800"))


if __name__ == "__main__":
    unittest.main()
