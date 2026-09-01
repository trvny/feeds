import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import openoffice


def blog_html(posts):
    payload = {"props": {"pageProps": {"allPosts": posts}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'


def node(
    post_id="1", *, title="Post", uri="/2026/08/post/", date="2026-08-28T12:00:00"
):
    return {
        "id": post_id,
        "title": title,
        "uri": uri,
        "date": date,
        "firstImgPost": "https://static-blog.onlyoffice.com/fallback.png",
        "featuredImage": {
            "node": {"sourceUrl": "https://static-blog.onlyoffice.com/featured.png"}
        },
        "author": {"node": {"name": "Alice"}},
    }


def posts(edges, *, has_next=False, cursor=None):
    return {
        "edges": [{"node": item} for item in edges],
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
    }


class OpenOfficeFeedTests(unittest.TestCase):
    def test_doc_sources_are_the_requested_surfaces(self):
        self.assertEqual(
            openoffice.doc_sources(),
            [
                ("ONLYOFFICE Blog", "https://www.onlyoffice.com/blog"),
                ("ONLYOFFICE API Changelog", "https://api.onlyoffice.com/changelog/"),
            ],
        )

    def test_changelog_uses_native_rss(self):
        self.assertEqual(
            openoffice.SOURCES,
            (
                (
                    "ONLYOFFICE API Changelog",
                    "https://api.onlyoffice.com/changelog/rss.xml",
                    100,
                ),
            ),
        )

    def test_parse_blog_page_uses_structured_next_data(self):
        parsed = openoffice.parse_blog_page(blog_html(posts([node()])))
        self.assertIsNotNone(parsed)
        entries, has_next, cursor = parsed
        self.assertFalse(has_next)
        self.assertIsNone(cursor)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["title"], "Post")
        self.assertEqual(entry["link"], "https://www.onlyoffice.com/blog/2026/08/post")
        self.assertEqual(entry["date"].tzinfo, pytz.UTC)
        self.assertEqual(entry["source"], "ONLYOFFICE Blog")
        self.assertEqual(
            entry["image"], "https://static-blog.onlyoffice.com/featured.png"
        )
        self.assertIn("Alice", entry["description"])

    def test_malformed_blog_payload_is_rejected(self):
        self.assertIsNone(openoffice.parse_blog_page("<html></html>"))
        self.assertIsNone(
            openoffice.parse_blog_page(
                blog_html(
                    {"edges": [], "pageInfo": {"hasNextPage": True, "endCursor": None}}
                )
            )
        )

    def test_collection_pages_until_known_history(self):
        first = node("1", title="Fresh", uri="/2026/08/fresh/")
        known = node("2", title="Known", uri="/2026/08/known/")
        initial = blog_html(posts([first], has_next=True, cursor="cursor-2"))
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": posts([known], has_next=False)}
        with (
            patch.object(openoffice.multi_rss, "get_html", return_value=initial),
            patch.object(openoffice.requests, "post", return_value=response) as post,
        ):
            entries = openoffice.collect_onlyoffice_blog(
                {"https://www.onlyoffice.com/blog/2026/08/known"}
            )
        self.assertEqual([entry["title"] for entry in entries], ["Fresh"])
        body = json.loads(post.call_args.kwargs["data"])
        self.assertEqual(body["endCursor"], "cursor-2")
        self.assertEqual(
            post.call_args.kwargs["headers"]["Content-Type"], "text/plain;charset=UTF-8"
        )

    def test_known_history_stops_before_older_entries_on_same_page(self):
        fresh = node("1", title="Fresh", uri="/2026/08/fresh/")
        known = node("2", title="Known", uri="/2026/08/known/")
        older = node("3", title="Older", uri="/2026/08/older/")
        initial = blog_html(
            posts([fresh, known, older], has_next=True, cursor="cursor-2")
        )
        with patch.object(openoffice.multi_rss, "get_html", return_value=initial):
            entries = openoffice.collect_onlyoffice_blog(
                {"https://www.onlyoffice.com/blog/2026/08/known"}
            )
        self.assertEqual([entry["title"] for entry in entries], ["Fresh"])

    def test_later_api_failure_is_retried_on_the_next_run(self):
        first = node("1", title="Fresh", uri="/2026/08/fresh/")
        second = node("2", title="Second", uri="/2026/08/second/")
        initial = blog_html(posts([first], has_next=True, cursor="cursor-2"))
        page_two = (
            [openoffice._blog_entry(second)],
            False,
            None,
        )
        with (
            patch.object(openoffice.multi_rss, "get_html", return_value=initial),
            patch.object(openoffice, "_fetch_more_posts", side_effect=[None, page_two]),
        ):
            first_run = openoffice.collect_onlyoffice_blog(set())
            second_run = openoffice.collect_onlyoffice_blog(set())
        self.assertEqual(first_run, [])
        self.assertEqual([entry["title"] for entry in second_run], ["Fresh", "Second"])

    def test_known_post_on_initial_page_avoids_load_more(self):
        known = node("1", title="Known", uri="/2026/08/known/")
        initial = blog_html(posts([known], has_next=True, cursor="cursor-2"))
        with (
            patch.object(openoffice.multi_rss, "get_html", return_value=initial),
            patch.object(openoffice, "_fetch_more_posts") as fetch_more,
        ):
            entries = openoffice.collect_onlyoffice_blog(
                {"https://www.onlyoffice.com/blog/2026/08/known"}
            )
        self.assertEqual(entries, [])
        fetch_more.assert_not_called()


if __name__ == "__main__":
    unittest.main()
