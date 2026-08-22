"""An entry with no picture should get the one its own article already has.

Offline by design: every test drives the parser directly or hands
backfill_images a stub lookup. The point under test is the budget and the
bookkeeping - what gets asked, what gets remembered, what gets retried - not
whether some site is up right now.
"""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from article_image import backfill_images, page_image  # noqa: E402

BASE = "https://example.com/news/story"


def page(head: str) -> str:
    return f"<html><head>{head}</head><body><p>text</p></body></html>"


class PageImageTests(unittest.TestCase):
    def test_reads_open_graph(self):
        url, width, height = page_image(
            page('<meta property="og:image" content="https://cdn.test/a.jpg">'), BASE
        )
        self.assertEqual(url, "https://cdn.test/a.jpg")
        self.assertIsNone(width)
        self.assertIsNone(height)

    def test_carries_declared_dimensions(self):
        url, width, height = page_image(
            page(
                '<meta property="og:image" content="https://cdn.test/a.jpg">'
                '<meta property="og:image:width" content="1200">'
                '<meta property="og:image:height" content="630">'
            ),
            BASE,
        )
        self.assertEqual((url, width, height), ("https://cdn.test/a.jpg", 1200, 630))

    def test_falls_back_to_twitter_card(self):
        url, _, _ = page_image(
            page('<meta name="twitter:image" content="https://cdn.test/t.png">'), BASE
        )
        self.assertEqual(url, "https://cdn.test/t.png")

    def test_falls_back_to_json_ld(self):
        # News sites that skip Open Graph still ship this for Google.
        url, _, _ = page_image(
            page(
                '<script type="application/ld+json">'
                '{"@type":"NewsArticle","url":"https://example.com/news/story",'
                '"image":{"@type":"ImageObject","url":"https://cdn.test/ld.jpg"}}'
                "</script>"
            ),
            BASE,
        )
        self.assertEqual(url, "https://cdn.test/ld.jpg")

    def test_json_ld_never_returns_the_article_url_as_its_image(self):
        # The Article node has a "url" too; returning it would attach the page
        # to itself and readers would render a broken image.
        url, _, _ = page_image(
            page(
                '<script type="application/ld+json">'
                '{"@type":"NewsArticle","url":"https://example.com/news/story"}'
                "</script>"
            ),
            BASE,
        )
        self.assertIsNone(url)

    def test_invalid_json_ld_does_not_raise(self):
        url, _, _ = page_image(
            page('<script type="application/ld+json">{not json,,}</script>'), BASE
        )
        self.assertIsNone(url)

    def test_relative_urls_are_absolutized(self):
        url, _, _ = page_image(
            page('<meta property="og:image" content="/img/a.jpg">'), BASE
        )
        self.assertEqual(url, "https://example.com/img/a.jpg")

    def test_rejects_data_uris_and_placeholders(self):
        for content in ("data:image/png;base64,AAA", "https://cdn.test/placeholder.png"):
            with self.subTest(content=content):
                url, _, _ = page_image(
                    page(f'<meta property="og:image" content="{content}">'), BASE
                )
                self.assertIsNone(url)

    def test_no_metadata_yields_nothing(self):
        self.assertEqual(page_image(page("<title>x</title>"), BASE), (None, None, None))


class BackfillTests(unittest.TestCase):
    def entries(self, count, **extra):
        return [
            {"link": f"https://example.com/{i}", "title": str(i), **extra}
            for i in range(count)
        ]

    def test_fills_missing_images_and_leaves_existing_alone(self):
        entries = self.entries(2)
        entries[0]["image"] = "https://cdn.test/kept.jpg"
        asked = []

        def lookup(url, session):
            asked.append(url)
            return "https://cdn.test/new.jpg", 800, 400, True

        found = backfill_images(entries, lookup=lookup)
        self.assertEqual(found, 1)
        self.assertEqual(asked, ["https://example.com/1"])
        self.assertEqual(entries[0]["image"], "https://cdn.test/kept.jpg")
        self.assertEqual(entries[1]["image"], "https://cdn.test/new.jpg")
        self.assertEqual(entries[1]["image_width"], 800)

    def test_settled_miss_is_remembered_so_it_is_not_refetched(self):
        entries = self.entries(1)
        backfill_images(entries, lookup=lambda url, session: (None, None, None, True))
        self.assertTrue(entries[0]["image_checked"])
        # Second run must not spend budget on it again.
        asked = []
        backfill_images(
            entries,
            lookup=lambda url, session: (asked.append(url), (None, None, None, True))[1],
        )
        self.assertEqual(asked, [])

    def test_transient_failure_stays_pending(self):
        # A timeout must not brand an article imageless forever.
        entries = self.entries(1)
        backfill_images(entries, lookup=lambda url, session: (None, None, None, False))
        self.assertNotIn("image_checked", entries[0])
        self.assertNotIn("image", entries[0])

    def test_budget_is_capped_and_spent_on_the_newest(self):
        # Entries arrive oldest-first, so the tail is what a reader sees first.
        entries = self.entries(10)
        asked = []

        def lookup(url, session):
            asked.append(url)
            return "https://cdn.test/x.jpg", None, None, True

        backfill_images(entries, limit=3, lookup=lookup)
        self.assertEqual(
            sorted(asked),
            sorted(f"https://example.com/{i}" for i in (7, 8, 9)),
        )

    def test_wall_clock_budget_stops_a_hung_origin_from_blocking_the_run(self):
        # 55 feeds each waiting out an unresponsive host would threaten the
        # scheduled job's timeout, so slow work is abandoned, not awaited.
        entries = self.entries(4)

        def lookup(url, session):
            if url.endswith(("2", "3")):
                time.sleep(0.6)
            return "https://cdn.test/fast.jpg", None, None, True

        found = backfill_images(entries, workers=4, max_seconds=0.15, lookup=lookup)
        self.assertEqual(found, 2)
        self.assertEqual(entries[0]["image"], "https://cdn.test/fast.jpg")
        # The slow two keep no verdict at all, so the next run retries them.
        for entry in entries[2:]:
            self.assertNotIn("image", entry)
            self.assertNotIn("image_checked", entry)

    def test_results_land_on_the_right_entry_when_they_finish_out_of_order(self):
        entries = self.entries(3)

        def lookup(url, session):
            if url.endswith("0"):
                time.sleep(0.2)  # finishes last despite being submitted first
            return f"https://cdn.test/{url[-1]}.jpg", None, None, True

        backfill_images(entries, workers=3, lookup=lookup)
        self.assertEqual(
            [e["image"] for e in entries],
            ["https://cdn.test/0.jpg", "https://cdn.test/1.jpg", "https://cdn.test/2.jpg"],
        )

    def test_a_raising_lookup_does_not_sink_the_feed(self):
        entries = self.entries(2)

        def lookup(url, session):
            if url.endswith("0"):
                raise RuntimeError("boom")
            return "https://cdn.test/ok.jpg", None, None, True

        self.assertEqual(backfill_images(entries, lookup=lookup), 1)
        self.assertEqual(entries[1]["image"], "https://cdn.test/ok.jpg")

    def test_entries_sharing_one_link_are_left_alone(self):
        # foobar2000 publishes 326 changelog entries across four URLs; one
        # picture repeated 326 times reads as a rendering bug, not illustration.
        entries = [{"link": "https://example.com/changelog", "title": str(i)} for i in range(3)]
        entries.append({"link": "https://example.com/article", "title": "own page"})
        asked = []

        def lookup(url, session):
            asked.append(url)
            return "https://cdn.test/x.jpg", None, None, True

        backfill_images(entries, lookup=lookup)
        self.assertEqual(asked, ["https://example.com/article"])

    def test_a_resolved_wrapper_is_what_gets_asked(self):
        # A Google News wrapper has no og:image; the article behind it does.
        entries = [
            {
                "link": "https://news.google.com/rss/articles/CBMiABC",
                "article_url": "https://www.reuters.com/world/story",
                "title": "t",
            }
        ]
        asked = []

        def lookup(url, session):
            asked.append(url)
            return None, None, None, True

        backfill_images(entries, lookup=lookup)
        self.assertEqual(asked, ["https://www.reuters.com/world/story"])

    def test_a_zero_budget_means_none_not_unlimited(self):
        # FEEDSEEK_IMAGE_LOOKUPS=0 is how you turn this off for one run; the
        # obvious reading of "if limit" turned it into no ceiling at all.
        entries = self.entries(5)
        asked = []
        backfill_images(entries, limit=0, lookup=lambda url, s: asked.append(url))
        self.assertEqual(asked, [])

    def test_nothing_to_do_makes_no_requests(self):
        entries = self.entries(3, image="https://cdn.test/a.jpg")
        called = []
        self.assertEqual(
            backfill_images(entries, lookup=lambda *a: called.append(a)), 0
        )
        self.assertEqual(called, [])

    def test_non_http_links_are_skipped(self):
        entries = [{"link": "magnet:?xt=urn:btih:abc", "title": "t"}]
        called = []
        backfill_images(entries, lookup=lambda *a: called.append(a))
        self.assertEqual(called, [])

    def test_transient_failure_is_retried_up_to_max_attempts(self):
        entries = self.entries(1)
        backfill_images(entries, lookup=lambda url, session: (None, None, None, False))
        self.assertEqual(entries[0]["image_attempts"], 1)
        self.assertEqual(entries[0]["image_attempt_url"], "https://example.com/0")
        self.assertNotIn("image_checked", entries[0])

        backfill_images(entries, lookup=lambda url, session: (None, None, None, False))
        self.assertEqual(entries[0]["image_attempts"], 2)
        self.assertEqual(entries[0]["image_attempt_url"], "https://example.com/0")
        self.assertNotIn("image_checked", entries[0])

        backfill_images(entries, lookup=lambda url, session: (None, None, None, False))
        self.assertEqual(entries[0]["image_attempts"], 3)
        self.assertEqual(entries[0]["image_attempt_url"], "https://example.com/0")
        self.assertNotIn("image_checked", entries[0])

        # Fourth run: must not be retried anymore (same URL, max attempts reached)
        called = []
        backfill_images(
            entries,
            lookup=lambda url, session: (called.append(url), (None, None, None, False))[1],
        )
        self.assertEqual(called, [])

    def test_successful_lookup_after_failures_cleans_up_attempts(self):
        entries = self.entries(1)
        call_count = [0]

        def lookup(url, session):
            call_count[0] += 1
            if call_count[0] <= 1:
                return None, None, None, False
            return "https://cdn.test/ok.jpg", 800, 400, True

        backfill_images(entries, lookup=lookup)
        self.assertEqual(entries[0]["image_attempts"], 1)
        self.assertEqual(entries[0]["image_attempt_url"], "https://example.com/0")
        self.assertNotIn("image", entries[0])

        backfill_images(entries, lookup=lookup)
        self.assertEqual(entries[0]["image"], "https://cdn.test/ok.jpg")
        self.assertNotIn("image_attempts", entries[0])
        self.assertNotIn("image_attempt_url", entries[0])

    def test_wrapper_url_failures_do_not_block_real_article_url(self):
        # After MAX_ATTEMPTS failures against a Google News wrapper URL,
        # setting article_url to the real article URL makes it eligible again.
        entries = [
            {
                "link": "https://news.google.com/rss/articles/CBMiABC",
                "article_url": "https://news.google.com/rss/articles/CBMiABC",
                "title": "t",
            }
        ]
        # Fail 3 times against the wrapper URL
        for _ in range(3):
            backfill_images(
                entries,
                lookup=lambda url, session: (None, None, None, False),
            )
        # After 3 failures, attempts should be capped for the wrapper URL
        self.assertEqual(entries[0]["image_attempts"], 3)
        self.assertEqual(entries[0]["image_attempt_url"], "https://news.google.com/rss/articles/CBMiABC")
        self.assertNotIn("image_checked", entries[0])
        
        # Fourth run with same wrapper URL: should not be retried
        called = []
        backfill_images(
            entries,
            lookup=lambda url, session: (called.append(url), (None, None, None, False))[1],
        )
        self.assertEqual(called, [])
        
        # Now set article_url to the real article - should be eligible again
        entries[0]["article_url"] = "https://www.reuters.com/world/story"
        called = []
        backfill_images(
            entries,
            lookup=lambda url, session: (called.append(url), ("https://cdn.test/ok.jpg", 800, 400, True))[1],
        )
        # Should have been looked up with the new URL
        self.assertEqual(called, ["https://www.reuters.com/world/story"])
        self.assertEqual(entries[0]["image"], "https://cdn.test/ok.jpg")
        # On successful lookup, attempt tracking is cleaned up
        self.assertNotIn("image_attempts", entries[0])
        self.assertNotIn("image_attempt_url", entries[0])


    def test_shared_target_is_skipped_even_when_siblings_are_resolved(self):
        """A shared page stays off-limits once its siblings stop being pending.

        The duplicate guard exists so one page's picture is not stamped onto
        every entry that links to it. Counting only pending entries would let
        the last unresolved sibling look unique and collect it anyway.
        """
        entries = self.entries(2)
        for entry in entries:
            entry["link"] = "https://example.test/shared"
        entries[0]["image"] = "https://cdn.test/already.jpg"

        called = []
        backfill_images(
            entries,
            lookup=lambda url, session: (called.append(url), (None, None, None, True))[1],
        )
        self.assertEqual(called, [])

    def test_lookup_abandoned_by_the_time_budget_still_counts_an_attempt(self):
        """A hung origin must reach the cap like any other dead end.

        The wall-clock budget abandons the future without a result, so nothing
        in the completion loop ever sees it. Left uncounted, an origin that
        hangs rather than refusing would be asked again on every run forever.
        """
        entries = self.entries(1)

        def hangs(url, session):
            time.sleep(0.4)
            return None, None, None, True

        backfill_images(entries, lookup=hangs, max_seconds=0.05, workers=1)
        self.assertEqual(entries[0]["image_attempts"], 1)
        self.assertEqual(entries[0]["image_attempt_url"], entries[0]["link"])

    def test_queued_lookups_are_not_charged_an_attempt(self):
        """Only a lookup that actually ran counts against the cap.

        The budget expires with far more lookups submitted than workers, so
        most futures are still queued. Charging those would retire entries
        that were never fetched at all - the opposite of what the cap is for.
        """
        entries = self.entries(3)

        def hangs(url, session):
            time.sleep(0.4)
            return None, None, None, True

        backfill_images(entries, lookup=hangs, max_seconds=0.05, workers=1)
        charged = [e for e in entries if e.get("image_attempts")]
        self.assertEqual(len(charged), 1, "only the one that started may be charged")

if __name__ == "__main__":
    unittest.main()
