import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import aws  # pylint: disable=wrong-import-position

_UNSET = object()


def _cursor(value: str) -> str:
    """Mark an opaque pagination cursor used only by test fixtures."""
    return value


def repost_page(page=1, total=24, entries=None, tokens=_UNSET, page_size=12):
    entries = entries or []
    if tokens is _UNSET:
        tokens = []
    response = {
        "totalCount": total,
        "nextToken": _cursor("next"),
        "pageSize": page_size,
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
        self.assertEqual(
            entry["link"], "https://repost.aws/articles/AR123/a-useful-article"
        )
        self.assertEqual(entry["date"].isoformat(), "2026-08-29T03:21:02.634000+00:00")
        self.assertEqual(entry["source"], "AWS re:Post Articles")

    def test_repost_page_rejects_malformed_payload(self):
        self.assertIsNone(aws.parse_repost_page("<html></html>"))
        self.assertIsNone(
            aws.parse_repost_page('<script id="__NEXT_DATA__">not json</script>')
        )

    def test_repost_rejects_boolean_metadata_and_tolerates_null_tokens(self):
        self.assertIsNone(aws.parse_repost_page(repost_page(page=True)))
        self.assertIsNone(aws.parse_repost_page(repost_page(page_size=False)))
        self.assertIsNone(aws.parse_repost_page(repost_page(total=True)))
        parsed = aws.parse_repost_page(repost_page(tokens=None))
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["tokens"], {})

    def test_repost_paginates_until_known_history(self):
        first = {
            "id": "AR1",
            "slug": "first",
            "title": "First",
            "description": "one",
            "language": "en",
            "createdAt": "2026-08-30T10:00:00Z",
        }
        second = {
            "id": "AR2",
            "slug": "second",
            "title": "Second",
            "description": "two",
            "language": "en",
            "createdAt": "2026-08-29T10:00:00Z",
        }
        cursor = f"page-two-{2}"
        html1 = repost_page(1, entries=[first], tokens=[{"page": 2, "token": cursor}])
        html2 = repost_page(2, entries=[second], tokens=[])
        known = {"https://repost.aws/articles/AR2/second"}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss, "get_html", side_effect=[html1, html2]
            ) as get_html,
        ):
            entries = aws.collect_repost(known, {})
        self.assertEqual([entry["title"] for entry in entries], ["First"])
        self.assertEqual(get_html.call_count, 2)
        self.assertIn(f"page={cursor}", get_html.call_args_list[1].args[0])

    def test_repost_initial_window_stops_at_safety_cap(self):
        item = {
            "id": "AR1",
            "slug": "first",
            "title": "First",
            "description": "one",
            "language": "en",
            "createdAt": "2026-08-30T10:00:00Z",
        }
        cursor = f"page-{2}"
        html = repost_page(
            1, total=100, entries=[item], tokens=[{"page": 2, "token": cursor}]
        )
        state = {}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 1),
            patch.object(aws.multi_rss, "get_html", return_value=html) as get_html,
        ):
            entries = aws.collect_repost(set(), state)
        self.assertEqual([entry["title"] for entry in entries], ["First"])
        self.assertEqual(state[aws.REPOST_CURSOR_KEY], {"page": 2, "token": cursor})
        get_html.assert_called_once_with(aws.REPOST_URL)

    def test_repost_bootstraps_with_only_unrelated_cached_links(self):
        item = {
            "id": "AR1",
            "slug": "first",
            "title": "First",
            "description": "one",
            "language": "en",
            "createdAt": "2026-08-30T10:00:00Z",
        }
        cursor = f"page-{2}"
        html = repost_page(
            1, total=100, entries=[item], tokens=[{"page": 2, "token": cursor}]
        )
        unrelated = {"https://aws.amazon.com/blogs/aws/example"}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 1),
            patch.object(aws.multi_rss, "get_html", return_value=html),
        ):
            entries = aws.collect_repost(unrelated, {})
        self.assertEqual([entry["title"] for entry in entries], ["First"])

    def test_repost_keeps_successful_pages_before_later_unavailable_failure(self):
        first = {
            "id": "AR1",
            "slug": "first",
            "title": "First",
            "description": "one",
            "language": "en",
            "createdAt": "2026-08-30T10:00:00Z",
        }
        cursor = f"page-{2}"
        html1 = repost_page(1, entries=[first], tokens=[{"page": 2, "token": cursor}])
        state = {}
        with patch.object(aws.multi_rss, "get_html", side_effect=[html1, None]):
            entries = aws.collect_repost(set(), state)
        self.assertEqual([entry["title"] for entry in entries], ["First"])
        self.assertEqual(
            state[aws.REPOST_CURSOR_KEY],
            {"page": 2, "token": cursor, "failures": 1},
        )

    def test_repost_failure_checkpoint_preserves_incremental_history_boundary(self):
        fresh = {
            "id": "AR1",
            "slug": "fresh-one",
            "title": "Fresh one",
            "description": "one",
            "language": "en",
            "createdAt": "2026-08-30T12:00:00Z",
        }
        known = "https://repost.aws/articles/AR10/known-ten"
        state = {}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(
                        1,
                        total=120,
                        entries=[fresh],
                        tokens=[{"page": 2, "token": _cursor("fresh-2")}],
                    ),
                    None,
                ],
            ),
        ):
            entries = aws.collect_repost({known}, state)
        self.assertEqual([entry["title"] for entry in entries], ["Fresh one"])
        self.assertEqual(
            state[aws.REPOST_FRESH_CURSOR_KEY],
            {"page": 2, "token": _cursor("fresh-2"), "failures": 1},
        )
        self.assertEqual(state[f"{aws.REPOST_FRESH_CURSOR_KEY}_boundary"], [known])

    def test_repost_resumes_from_saved_cursor_with_hard_cap(self):
        head = {
            "id": "ARH",
            "slug": "head",
            "title": "Fresh head",
            "description": "new",
            "language": "en",
            "createdAt": "2026-08-30T11:00:00Z",
        }
        archived = {
            "id": "AR2",
            "slug": "second",
            "title": "Second",
            "description": "two",
            "language": "en",
            "createdAt": "2026-08-29T10:00:00Z",
        }
        resume = "resume-page-2"
        next_cursor = _cursor("resume-page-3")
        state = {aws.REPOST_CURSOR_KEY: {"page": 2, "token": resume, "failures": 1}}
        head_html = repost_page(1, total=100, entries=[head])
        archive_html = repost_page(
            2,
            total=100,
            entries=[archived],
            tokens=[{"page": 3, "token": next_cursor}],
        )
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss, "get_html", side_effect=[head_html, archive_html]
            ) as get_html,
        ):
            entries = aws.collect_repost(set(), state)
        self.assertEqual(
            [entry["title"] for entry in entries], ["Fresh head", "Second"]
        )
        self.assertEqual(
            state[aws.REPOST_CURSOR_KEY], {"page": 3, "token": next_cursor}
        )
        self.assertEqual(get_html.call_count, 2)
        self.assertEqual(get_html.call_args_list[0].args[0], aws.REPOST_URL)
        self.assertIn(f"page={resume}", get_html.call_args_list[1].args[0])

    def test_repost_cursor_clears_when_cached_history_is_reached(self):
        head = {
            "id": "ARH",
            "slug": "head",
            "title": "Head",
            "description": "head",
            "language": "en",
            "createdAt": "2026-08-30T11:00:00Z",
        }
        archived = {
            "id": "AR2",
            "slug": "second",
            "title": "Second",
            "description": "two",
            "language": "en",
            "createdAt": "2026-08-29T10:00:00Z",
        }
        known = {
            "https://repost.aws/articles/ARH/head",
            "https://repost.aws/articles/AR2/second",
        }
        state = {aws.REPOST_CURSOR_KEY: {"page": 2, "token": _cursor("resume-page-2")}}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(1, total=100, entries=[head]),
                    repost_page(2, total=100, entries=[archived]),
                ],
            ),
        ):
            self.assertEqual(aws.collect_repost(known, state), [])
        self.assertNotIn(aws.REPOST_CURSOR_KEY, state)

    def test_repost_page_without_usable_entries_is_a_source_failure(self):
        head = {
            "id": "ARH",
            "slug": "head",
            "title": "Fresh head",
            "description": "new",
            "language": "en",
            "createdAt": "2026-08-30T11:00:00Z",
        }
        unusable = {
            "id": "AR2",
            "slug": "zweite",
            "title": "Zweite",
            "description": "zwei",
            "language": "de",
            "createdAt": "2026-08-29T10:00:00Z",
        }
        state = {aws.REPOST_CURSOR_KEY: {"page": 2, "token": _cursor("resume-page-2")}}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(1, total=100, entries=[head]),
                    repost_page(
                        2,
                        total=100,
                        entries=[unusable],
                        tokens=[{"page": 3, "token": _cursor("next")}],
                    ),
                ],
            ),
        ):
            entries = aws.collect_repost(set(), state)
        self.assertEqual([entry["title"] for entry in entries], ["Fresh head"])
        self.assertNotIn(aws.REPOST_CURSOR_KEY, state)

    def test_repost_parsed_failure_preserves_original_boundary_for_head_recovery(self):
        head = {
            "id": "ARH",
            "slug": "head",
            "title": "Known head",
            "description": "known",
            "language": "en",
            "createdAt": "2026-08-30T11:00:00Z",
        }
        unusable = {
            "id": "AR5",
            "slug": "fuenf",
            "title": "Fuenf",
            "description": "fuenf",
            "language": "de",
            "createdAt": "2026-08-25T10:00:00Z",
        }
        head_link = "https://repost.aws/articles/ARH/head"
        old_link = "https://repost.aws/articles/OLD/original-boundary"
        boundary_key = f"{aws.REPOST_CURSOR_KEY}_boundary"
        state = {
            aws.REPOST_CURSOR_KEY: {"page": 5, "token": _cursor("archive-5")},
            boundary_key: [old_link],
        }
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(1, total=120, entries=[head]),
                    repost_page(5, total=120, entries=[unusable]),
                ],
            ),
        ):
            entries = aws.collect_repost({head_link, old_link}, state)
        self.assertEqual(entries, [])
        self.assertNotIn(aws.REPOST_CURSOR_KEY, state)
        self.assertEqual(state[boundary_key], [old_link])

    def test_repost_stale_resume_cursor_resets_for_next_run(self):
        head = {
            "id": "ARH",
            "slug": "head",
            "title": "Fresh head",
            "description": "new",
            "language": "en",
            "createdAt": "2026-08-30T11:00:00Z",
        }
        state = {aws.REPOST_CURSOR_KEY: {"page": 3, "token": _cursor("stale")}}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(1, total=100, entries=[head]),
                    repost_page(2, total=100, entries=[]),
                ],
            ),
        ):
            entries = aws.collect_repost(set(), state)
        self.assertEqual([entry["title"] for entry in entries], ["Fresh head"])
        self.assertNotIn(aws.REPOST_CURSOR_KEY, state)

    def test_repost_dead_cursor_resets_after_two_failures(self):
        head = {
            "id": "ARH",
            "slug": "head",
            "title": "Fresh head",
            "description": "new",
            "language": "en",
            "createdAt": "2026-08-30T11:00:00Z",
        }
        state = {aws.REPOST_CURSOR_KEY: {"page": 2, "token": _cursor("dead")}}
        head_html = repost_page(1, total=100, entries=[head])
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[head_html, None, head_html, None],
            ) as get_html,
        ):
            first = aws.collect_repost(set(), state)
            self.assertEqual(
                state[aws.REPOST_CURSOR_KEY],
                {"page": 2, "token": _cursor("dead"), "failures": 1},
            )
            second = aws.collect_repost(set(), state)
        self.assertEqual([entry["title"] for entry in first], ["Fresh head"])
        self.assertEqual([entry["title"] for entry in second], ["Fresh head"])
        self.assertNotIn(aws.REPOST_CURSOR_KEY, state)
        self.assertEqual(get_html.call_count, 4)

    def test_repost_dead_cursor_restarts_from_head_with_original_boundary(self):
        head = {
            "id": "ARH",
            "slug": "known-head",
            "title": "Known head",
            "description": "known",
            "language": "en",
            "createdAt": "2026-08-30T12:00:00Z",
        }
        missing = {
            "id": "AR6",
            "slug": "missing-six",
            "title": "Missing six",
            "description": "missing",
            "language": "en",
            "createdAt": "2026-08-24T10:00:00Z",
        }
        old = {
            "id": "AR10",
            "slug": "old-ten",
            "title": "Old ten",
            "description": "old",
            "language": "en",
            "createdAt": "2026-08-20T10:00:00Z",
        }
        head_link = "https://repost.aws/articles/ARH/known-head"
        old_link = "https://repost.aws/articles/AR10/old-ten"
        boundary_key = f"{aws.REPOST_CURSOR_KEY}_boundary"
        state = {
            aws.REPOST_CURSOR_KEY: {
                "page": 5,
                "token": _cursor("dead-5"),
                "failures": 1,
            },
            boundary_key: [old_link],
        }
        head_html = repost_page(1, total=120, entries=[head])
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(aws.multi_rss, "get_html", side_effect=[head_html, None]),
        ):
            self.assertEqual(aws.collect_repost({head_link, old_link}, state), [])
        self.assertNotIn(aws.REPOST_CURSOR_KEY, state)
        self.assertEqual(state[boundary_key], [old_link])

        with (
            patch.object(aws, "MAX_REPOST_PAGES", 4),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    head_html,
                    repost_page(
                        1,
                        total=120,
                        entries=[head],
                        tokens=[{"page": 2, "token": _cursor("restart-2")}],
                    ),
                    repost_page(
                        2,
                        total=120,
                        entries=[missing],
                        tokens=[{"page": 3, "token": _cursor("restart-3")}],
                    ),
                    repost_page(3, total=120, entries=[old]),
                ],
            ) as get_html,
        ):
            entries = aws.collect_repost({head_link, old_link}, state)
        self.assertEqual([entry["title"] for entry in entries], ["Missing six"])
        self.assertEqual(get_html.call_count, 4)
        self.assertNotIn(aws.REPOST_CURSOR_KEY, state)
        self.assertNotIn(boundary_key, state)

    def test_repost_later_failure_tracks_the_page_that_failed(self):
        head = {
            "id": "ARH",
            "slug": "head",
            "title": "Known head",
            "description": "known",
            "language": "en",
            "createdAt": "2026-08-30T12:00:00Z",
        }
        archived = {
            "id": "AR5",
            "slug": "five",
            "title": "Archive five",
            "description": "five",
            "language": "en",
            "createdAt": "2026-08-25T10:00:00Z",
        }
        known = {"https://repost.aws/articles/ARH/head"}
        state = {aws.REPOST_CURSOR_KEY: {"page": 5, "token": _cursor("archive-5")}}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 4),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(1, total=120, entries=[head]),
                    repost_page(
                        5,
                        total=120,
                        entries=[archived],
                        tokens=[{"page": 6, "token": _cursor("archive-6")}],
                    ),
                    None,
                ],
            ),
        ):
            entries = aws.collect_repost(known, state)
        self.assertEqual([entry["title"] for entry in entries], ["Archive five"])
        self.assertEqual(
            state[aws.REPOST_CURSOR_KEY],
            {"page": 6, "token": _cursor("archive-6"), "failures": 1},
        )

    def test_repost_saved_freshness_cursor_rescans_head_until_known_overlap(self):
        fresh1 = {
            "id": "AR1",
            "slug": "fresh-one",
            "title": "Fresh one",
            "description": "one",
            "language": "en",
            "createdAt": "2026-08-30T13:00:00Z",
        }
        fresh2 = {
            "id": "AR2",
            "slug": "fresh-two",
            "title": "Fresh two",
            "description": "two",
            "language": "en",
            "createdAt": "2026-08-30T12:00:00Z",
        }
        seen3 = {
            "id": "AR3",
            "slug": "seen-three",
            "title": "Seen three",
            "description": "seen",
            "language": "en",
            "createdAt": "2026-08-30T11:00:00Z",
        }
        missing5 = {
            "id": "AR5",
            "slug": "missing-five",
            "title": "Missing five",
            "description": "missing",
            "language": "en",
            "createdAt": "2026-08-29T10:00:00Z",
        }
        old = "https://repost.aws/articles/AR10/old-ten"
        seen = "https://repost.aws/articles/AR3/seen-three"
        fresh_boundary_key = f"{aws.REPOST_FRESH_CURSOR_KEY}_boundary"
        state = {
            aws.REPOST_CURSOR_KEY: {"page": 8, "token": _cursor("archive-8")},
            aws.REPOST_FRESH_CURSOR_KEY: {"page": 5, "token": _cursor("saved-fresh-5")},
            fresh_boundary_key: [old],
        }
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 4),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(
                        1,
                        total=120,
                        entries=[fresh1],
                        tokens=[{"page": 2, "token": _cursor("live-2")}],
                    ),
                    repost_page(
                        2,
                        total=120,
                        entries=[fresh2],
                        tokens=[{"page": 3, "token": _cursor("live-3")}],
                    ),
                    repost_page(
                        3,
                        total=120,
                        entries=[seen3],
                        tokens=[{"page": 4, "token": _cursor("live-4")}],
                    ),
                    repost_page(
                        5,
                        total=120,
                        entries=[missing5],
                        tokens=[{"page": 6, "token": _cursor("saved-fresh-6")}],
                    ),
                ],
            ) as get_html,
        ):
            entries = aws.collect_repost({old, seen}, state)
        self.assertEqual(
            [entry["title"] for entry in entries],
            ["Fresh one", "Fresh two", "Missing five"],
        )
        self.assertEqual(get_html.call_count, 4)
        self.assertIn("page=live-2", get_html.call_args_list[1].args[0])
        self.assertIn("page=live-3", get_html.call_args_list[2].args[0])
        self.assertIn("page=saved-fresh-5", get_html.call_args_list[3].args[0])
        self.assertEqual(
            state[aws.REPOST_FRESH_CURSOR_KEY],
            {"page": 6, "token": _cursor("saved-fresh-6")},
        )
        self.assertEqual(state[fresh_boundary_key], [old])

    def test_repost_scans_all_fresh_pages_before_archive_resume(self):
        fresh1 = {
            "id": "AR1",
            "slug": "fresh-one",
            "title": "Fresh one",
            "description": "one",
            "language": "en",
            "createdAt": "2026-08-30T12:00:00Z",
        }
        fresh2 = {
            "id": "AR2",
            "slug": "fresh-two",
            "title": "Fresh two",
            "description": "two",
            "language": "en",
            "createdAt": "2026-08-30T11:00:00Z",
        }
        known3 = {
            "id": "AR3",
            "slug": "known-three",
            "title": "Known three",
            "description": "three",
            "language": "en",
            "createdAt": "2026-08-29T10:00:00Z",
        }
        archived = {
            "id": "AR8",
            "slug": "archive-eight",
            "title": "Archive eight",
            "description": "eight",
            "language": "en",
            "createdAt": "2026-08-20T10:00:00Z",
        }
        known = {"https://repost.aws/articles/AR3/known-three"}
        state = {aws.REPOST_CURSOR_KEY: {"page": 8, "token": _cursor("archive-8")}}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 4),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(
                        1,
                        total=120,
                        entries=[fresh1],
                        tokens=[{"page": 2, "token": _cursor("fresh-2")}],
                    ),
                    repost_page(
                        2,
                        total=120,
                        entries=[fresh2],
                        tokens=[{"page": 3, "token": _cursor("fresh-3")}],
                    ),
                    repost_page(3, total=120, entries=[known3]),
                    repost_page(
                        8,
                        total=120,
                        entries=[archived],
                        tokens=[{"page": 9, "token": _cursor("archive-9")}],
                    ),
                ],
            ) as get_html,
        ):
            entries = aws.collect_repost(known, state)
        self.assertEqual(
            [entry["title"] for entry in entries],
            ["Fresh one", "Fresh two", "Archive eight"],
        )
        self.assertEqual(get_html.call_count, 4)
        self.assertNotIn(aws.REPOST_FRESH_CURSOR_KEY, state)
        self.assertEqual(
            state[aws.REPOST_CURSOR_KEY], {"page": 9, "token": _cursor("archive-9")}
        )

    def test_repost_fresh_checkpoint_preserves_archive_cursor(self):
        fresh1 = {
            "id": "AR1",
            "slug": "fresh-one",
            "title": "Fresh one",
            "description": "one",
            "language": "en",
            "createdAt": "2026-08-30T12:00:00Z",
        }
        fresh2 = {
            "id": "AR2",
            "slug": "fresh-two",
            "title": "Fresh two",
            "description": "two",
            "language": "en",
            "createdAt": "2026-08-30T11:00:00Z",
        }
        state = {aws.REPOST_CURSOR_KEY: {"page": 8, "token": _cursor("archive-8")}}
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(
                        1,
                        total=120,
                        entries=[fresh1],
                        tokens=[{"page": 2, "token": _cursor("fresh-2")}],
                    ),
                    repost_page(
                        2,
                        total=120,
                        entries=[fresh2],
                        tokens=[{"page": 3, "token": _cursor("fresh-3")}],
                    ),
                ],
            ),
        ):
            entries = aws.collect_repost(
                {"https://repost.aws/articles/AR3/known-three"}, state
            )
        self.assertEqual(
            [entry["title"] for entry in entries], ["Fresh one", "Fresh two"]
        )
        self.assertEqual(
            state[aws.REPOST_FRESH_CURSOR_KEY], {"page": 3, "token": _cursor("fresh-3")}
        )
        self.assertEqual(
            state[aws.REPOST_CURSOR_KEY], {"page": 8, "token": _cursor("archive-8")}
        )

    def test_repost_archive_overlap_does_not_replace_original_history_boundary(self):
        known_head = {
            "id": "ARH",
            "slug": "known-head",
            "title": "Known head",
            "description": "known",
            "language": "en",
            "createdAt": "2026-08-30T12:00:00Z",
        }
        shifted = {
            "id": "AR8",
            "slug": "shifted-eight",
            "title": "Shifted eight",
            "description": "already collected",
            "language": "en",
            "createdAt": "2026-08-20T10:00:00Z",
        }
        missing = {
            "id": "AR9",
            "slug": "missing-nine",
            "title": "Missing nine",
            "description": "still needs collection",
            "language": "en",
            "createdAt": "2026-08-19T10:00:00Z",
        }
        known = {
            "https://repost.aws/articles/ARH/known-head",
            "https://repost.aws/articles/AR8/shifted-eight",
        }
        boundary_key = f"{aws.REPOST_CURSOR_KEY}_boundary"
        state = {
            aws.REPOST_CURSOR_KEY: {"page": 9, "token": _cursor("archive-9")},
            boundary_key: [],
        }
        with (
            patch.object(aws, "MAX_REPOST_PAGES", 2),
            patch.object(
                aws.multi_rss,
                "get_html",
                side_effect=[
                    repost_page(1, total=120, entries=[known_head]),
                    repost_page(
                        9,
                        total=120,
                        entries=[shifted, missing],
                        tokens=[{"page": 10, "token": _cursor("archive-10")}],
                    ),
                ],
            ),
        ):
            entries = aws.collect_repost(known, state)
        self.assertEqual([entry["title"] for entry in entries], ["Missing nine"])
        self.assertEqual(
            state[aws.REPOST_CURSOR_KEY], {"page": 10, "token": _cursor("archive-10")}
        )
        self.assertEqual(state[boundary_key], [])

    def test_multi_rss_round_trips_cache_state_for_repost_cursor(self):
        link = "https://example.com/cached"
        cache = {
            "entries": [
                {
                    "link": link,
                    "title": "Cached",
                    "description": "Cached",
                    "source": "Custom",
                    "date": "2026-08-01T00:00:00+00:00",
                }
            ],
            aws.REPOST_CURSOR_KEY: {"page": 2, "token": _cursor("old")},
            "last_updated": "2026-08-01T00:00:00+00:00",
        }
        cache_state = {"stale": True}
        states_seen = []

        def custom_scraper(_known_links):
            states_seen.append(dict(cache_state))
            cache_state[aws.REPOST_CURSOR_KEY] = {"page": 3, "token": _cursor("next")}
            return []

        fg = MagicMock()
        with (
            patch.object(aws.multi_rss, "load_cache", return_value=cache),
            patch.object(aws.multi_rss, "enrich_entries"),
            patch.object(aws.multi_rss, "save_cache") as save_cache,
            patch.object(aws.multi_rss, "generate_atom_feed", return_value=fg),
            patch.object(aws.multi_rss, "save_atom_feed"),
        ):
            result = aws.multi_rss.run(
                feed_name="example",
                title="Example",
                subtitle="Example",
                blog_url="https://example.com/",
                author="Example",
                extra_scrapers=(custom_scraper,),
                cache_state=cache_state,
            )

        self.assertTrue(result)
        self.assertEqual(
            states_seen, [{aws.REPOST_CURSOR_KEY: {"page": 2, "token": _cursor("old")}}]
        )
        self.assertEqual(
            save_cache.call_args.kwargs["extra"],
            {aws.REPOST_CURSOR_KEY: {"page": 3, "token": _cursor("next")}},
        )

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
