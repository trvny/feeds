import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import aws  # pylint: disable=wrong-import-position


def repost_page(page=1, total=24, entries=None, tokens=None):
    entries = entries or []
    tokens = tokens or []
    response = {
        "totalCount": total,
        "nextToken": "next",
        "pageSize": 12,
        "page": page,
        "pagingTokens": tokens,
        "articles": entries,
        "tagName": "",
        "tagDesc": "",
        "topicName": "",
    }
    anchors = "".join(
        f'<a href="/articles/{item["id"]}/{item["slug"]}">{item["title"]}</a>'
        for item in entries
    )
    payload = {"props": {"pageProps": {"response": response}}}
    data = json.dumps(payload)
    return (
        f'<html><body>{anchors}<script id="__NEXT_DATA__" '
        f'type="application/json">{data}</script></body></html>'
    )


class AwsFeedTests(unittest.TestCase):
    """Regression coverage for the combined AWS feed."""
    def test_doc_sources_match_requested_surfaces(self):
        self.assertEqual(
            [url for _label, url in aws.doc_sources()],
            [
                "https://aws.amazon.com/about-aws/whats-new/recent/feed/",
                "https://aws.amazon.com/blogs/",
                "https://repost.aws/articles",
                "https://aws.amazon.com/blogs/aws/",
                "https://raw.githubusercontent.com/aws/aws-cli/v2/CHANGELOG.rst",
                "https://aws.amazon.com/blogs/developer/",
                "https://aws.amazon.com/blogs/opensource/",
            ],
        )

    def test_native_sources_use_official_rss_feeds(self):
        self.assertEqual(
            [url for _label, url, _cap in aws.SOURCES],
            [
                "https://aws.amazon.com/about-aws/whats-new/recent/feed/",
                "https://aws.amazon.com/blogs/aws/feed/",
                "https://aws.amazon.com/blogs/developer/feed/",
                "https://aws.amazon.com/blogs/opensource/feed/",
            ],
        )

    def test_repost_page_uses_structured_next_data(self):
        item = {
            "id": "AR123",
            "slug": "a-useful-article",
            "title": "A useful article",
            "description": "Useful AWS details",
            "language": "en",
            "createdAt": "2026-08-29T03:21:02.634Z",
        }
        parsed = aws.parse_repost_page(repost_page(entries=[item], total=1))
        self.assertIsNotNone(parsed)
        entry = parsed["entries"][0]
        self.assertEqual(entry["link"], "https://repost.aws/articles/AR123/a-useful-article")
        self.assertEqual(entry["date"].isoformat(), "2026-08-29T03:21:02.634000+00:00")
        self.assertEqual(entry["source"], "AWS re:Post Articles")

    def test_repost_page_rejects_malformed_payload(self):
        self.assertIsNone(aws.parse_repost_page("<html></html>"))
        self.assertIsNone(aws.parse_repost_page('<script id="__NEXT_DATA__">not json</script>'))

    def test_repost_paginates_until_known_history(self):
        first = {
            "id": "AR1", "slug": "first", "title": "First", "description": "one",
            "language": "en", "createdAt": "2026-08-30T10:00:00Z",
        }
        second = {
            "id": "AR2", "slug": "second", "title": "Second", "description": "two",
            "language": "en", "createdAt": "2026-08-29T10:00:00Z",
        }
        cursor = f"page-two-{2}"
        html1 = repost_page(1, entries=[first], tokens=[{"page": 2, "token": cursor}])
        html2 = repost_page(2, entries=[second], tokens=[])
        known = {"https://repost.aws/articles/AR2/second"}
        with patch.object(aws.multi_rss, "get_html", side_effect=[html1, html2]) as get_html:
            entries = aws.collect_repost(known)
        self.assertEqual([entry["title"] for entry in entries], ["First"])
        self.assertEqual(get_html.call_count, 2)
        self.assertIn(f"page={cursor}", get_html.call_args_list[1].args[0])

    def test_repost_initial_window_stops_at_safety_cap(self):
        item = {
            "id": "AR1", "slug": "first", "title": "First", "description": "one",
            "language": "en", "createdAt": "2026-08-30T10:00:00Z",
        }
        cursor = f"page-{2}"
        html = repost_page(1, total=100, entries=[item], tokens=[{"page": 2, "token": cursor}])
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 1),
            patch.object(aws.multi_rss, "get_html", return_value=html) as get_html,
        ):
            entries = aws.collect_repost(set())
        self.assertEqual([entry["title"] for entry in entries], ["First"])
        get_html.assert_called_once_with(aws.REPOST_URL)

    def test_repost_discards_partial_batch_on_later_failure(self):
        first = {
            "id": "AR1", "slug": "first", "title": "First", "description": "one",
            "language": "en", "createdAt": "2026-08-30T10:00:00Z",
        }
        cursor = f"page-{2}"
        html1 = repost_page(1, entries=[first], tokens=[{"page": 2, "token": cursor}])
        with patch.object(aws.multi_rss, "get_html", side_effect=[html1, None]):
            self.assertEqual(aws.collect_repost(set()), [])

    def test_cli_release_dates_and_changelog_are_joined(self):
        atom = """<feed xmlns='http://www.w3.org/2005/Atom'>
          <entry><title>2.36.34</title><updated>2026-08-28T18:18:17Z</updated><link href='https://github.com/aws/aws-cli/releases/tag/2.36.34'/></entry>
          <entry><title>1.46.1</title><updated>2026-08-27T20:03:39Z</updated><link href='https://github.com/aws/aws-cli/releases/tag/1.46.1'/></entry>
        </feed>"""
        releases = aws.parse_cli_release_dates(atom)
        self.assertEqual(list(releases), ["2.36.34"])
        changelog = (
            "2.36.34\n" + "=" * 7 + "\n"
            "* api-change:``ec2``: New thing\n"
            "* enhancement:CLI: Better output\n\n"
            "2.36.33\n" + "=" * 7 + "\n"
            "* api-change:``s3``: Older thing\n"
        )
        entries = aws.parse_cli_changelog(changelog, releases)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "AWS CLI 2.36.34")
        self.assertIn("api-change:ec2: New thing", entries[0]["description"])
        self.assertEqual(entries[0]["date"].isoformat(), "2026-08-28T18:18:17+00:00")

    def test_cli_changelog_skips_known_release(self):
        link = "https://github.com/aws/aws-cli/releases/tag/2.36.34"
        releases = {"2.36.34": (aws.multi_rss.parse_date("2026-08-28T18:18:17Z"), link)}
        changelog = "2.36.34\n" + "=" * 7 + "\n* fix: something\n"
        self.assertEqual(aws.parse_cli_changelog(changelog, releases, {link}), [])


if __name__ == "__main__":
    unittest.main()
