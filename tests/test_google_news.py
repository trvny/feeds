"""Google News links are wrappers; readers should get the article instead.

Offline: resolve_entries is driven with a stub resolver. What matters here is
the bookkeeping - which entries get asked, what is written where, and that the
entry's identity is left alone.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from google_news import MAX_ATTEMPTS, entry_url, is_wrapper, resolve_entries  # noqa: E402

WRAPPER = "https://news.google.com/rss/articles/CBMiabc123"
ARTICLE = "https://www.reuters.com/world/a-story-2026-08-12/"


class WrapperDetectionTests(unittest.TestCase):
    def test_recognises_a_wrapper(self):
        self.assertTrue(is_wrapper(WRAPPER))

    def test_leaves_ordinary_links_alone(self):
        for url in (ARTICLE, "https://news.google.com/", "", None):
            with self.subTest(url=url):
                self.assertFalse(is_wrapper(url))


class ResolveEntriesTests(unittest.TestCase):
    def test_publishes_the_article_but_keeps_the_wrapper_as_identity(self):
        # Overwriting link would rewrite make_entry_id for 2257 published
        # entries, and every reader would show them as unread again.
        entry = {"link": WRAPPER, "title": "t"}
        resolve_entries([entry], resolver=lambda url, session: ARTICLE)
        self.assertEqual(entry["link"], WRAPPER)
        self.assertEqual(entry["article_url"], ARTICLE)
        self.assertEqual(entry_url(entry), ARTICLE)

    def test_an_already_resolved_entry_is_not_asked_again(self):
        entry = {"link": WRAPPER, "article_url": ARTICLE, "title": "t"}
        asked = []
        resolve_entries([entry], resolver=lambda url, session: asked.append(url))
        self.assertEqual(asked, [])

    def test_plain_links_are_not_asked_about(self):
        asked = []
        resolve_entries(
            [{"link": ARTICLE, "title": "t"}], resolver=lambda url, session: asked.append(url)
        )
        self.assertEqual(asked, [])

    def test_a_failed_resolution_stays_pending(self):
        # Google throttling is not the same answer as "no such article".
        entry = {"link": WRAPPER, "title": "t"}
        resolve_entries([entry], resolver=lambda url, session: None)
        self.assertNotIn("article_url", entry)
        self.assertEqual(entry_url(entry), WRAPPER)

    def test_a_wrapper_that_never_resolves_stops_being_asked(self):
        """Staying pending is right for a blip, wrong forever.

        Without a cap the same links rebuild the pending list on every
        two-hourly run and are re-fetched indefinitely.
        """
        entry = {"link": WRAPPER, "title": "t"}
        for expected in range(1, MAX_ATTEMPTS + 1):
            resolve_entries([entry], resolver=lambda url, session: None)
            self.assertEqual(entry["resolve_attempts"], expected)

        asked = []
        resolve_entries(
            [entry],
            resolver=lambda url, session: (asked.append(url), None)[1],
        )
        self.assertEqual(asked, [], "capped entry must not be asked again")

    def test_a_changed_wrapper_starts_the_count_over(self):
        entry = {"link": WRAPPER, "title": "t", "resolve_attempts": MAX_ATTEMPTS,
                 "resolve_attempt_url": "https://news.google.com/rss/articles/OLD"}
        resolve_entries([entry], resolver=lambda url, session: ARTICLE)
        self.assertEqual(entry["article_url"], ARTICLE)

    def test_a_resolved_link_leaves_no_attempt_residue(self):
        entry = {"link": WRAPPER, "title": "t"}
        resolve_entries([entry], resolver=lambda url, session: None)
        self.assertIn("resolve_attempts", entry)
        resolve_entries([entry], resolver=lambda url, session: ARTICLE)
        self.assertNotIn("resolve_attempts", entry)
        self.assertNotIn("resolve_attempt_url", entry)

    def test_a_resolution_that_returns_another_wrapper_is_rejected(self):
        entry = {"link": WRAPPER, "title": "t"}
        resolve_entries([entry], resolver=lambda url, session: WRAPPER)
        self.assertNotIn("article_url", entry)

    def test_budget_is_capped_and_spent_on_the_newest(self):
        entries = [{"link": f"{WRAPPER}{i}", "title": str(i)} for i in range(6)]
        asked = []

        def resolver(url, session):
            asked.append(url)
            return ARTICLE

        resolve_entries(entries, limit=2, resolver=resolver)
        self.assertEqual(sorted(asked), sorted(f"{WRAPPER}{i}" for i in (4, 5)))

    def test_a_raising_resolver_does_not_sink_the_feed(self):
        entries = [{"link": f"{WRAPPER}{i}", "title": str(i)} for i in range(2)]

        def resolver(url, session):
            if url.endswith("0"):
                raise RuntimeError("boom")
            return ARTICLE

        self.assertEqual(resolve_entries(entries, resolver=resolver), 1)


if __name__ == "__main__":
    unittest.main()
