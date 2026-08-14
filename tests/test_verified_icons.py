"""Feeds whose site serves no usable /favicon.ico get a working <icon> anyway.

Offline by design: it asserts the wiring, not the live HTTP status. Whether the
URLs still resolve is what tools/check_feed_icons.py is for — a network probe in
CI would make an unrelated third-party hiccup fail the build, and the previous
tests here showed the opposite failure mode, pinning two proxy URLs that had
been returning 404 for who knows how long.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from feedgen.feed import FeedGenerator  # noqa: E402

from utils import (  # noqa: E402
    VERIFIED_ICONS,
    favicon_url,
    large_icon,
    setup_feed_links,
    verified_icon,
)


def feed_with(feed_name, blog_url, icon=None):
    fg = FeedGenerator()
    fg.id(blog_url)
    fg.title(feed_name)
    setup_feed_links(fg, blog_url, feed_name, icon=icon)
    return fg


def icon_of(feed_name, blog_url, icon=None):
    return feed_with(feed_name, blog_url, icon).icon()


class LargeIconTests(unittest.TestCase):
    def test_a_proxied_icon_is_offered_at_display_size(self):
        # Atom <logo> and JSON Feed "icon" are the big ones; S2 takes the size
        # as a parameter, so it costs nothing to ask for it.
        self.assertEqual(
            large_icon("https://www.google.com/s2/favicons?domain=news.mit.edu&sz=64"),
            "https://www.google.com/s2/favicons?domain=news.mit.edu&sz=256",
        )

    def test_any_other_icon_is_left_exactly_as_it_is(self):
        # A site's own /favicon.ico has no size dial; inventing one would 404.
        for url in ("https://example.com/favicon.ico", "", "https://x.test/i.png?sz=1"):
            with self.subTest(url=url):
                self.assertEqual(large_icon(url), url)

    def test_feeds_get_both_an_icon_and_a_logo(self):
        fg = feed_with("mit", "https://news.mit.edu/")
        self.assertTrue(fg.icon())
        self.assertTrue(fg.logo())
        self.assertIn("sz=256", fg.logo())


class VerifiedIconTests(unittest.TestCase):
    def test_listed_feed_gets_the_proxy_instead_of_a_dead_guess(self):
        # mit's own /favicon.ico 404s, so the guess produced an <icon> no reader
        # could load.
        self.assertEqual(
            icon_of("mit", "https://news.mit.edu/"),
            "https://www.google.com/s2/favicons?domain=news.mit.edu&sz=64",
        )

    def test_unlisted_feed_still_guesses_its_own_favicon(self):
        # 73 of 90 feeds serve a working /favicon.ico; they must not be rerouted
        # through a third party for no reason.
        self.assertEqual(
            icon_of("some_feed", "https://example.com/blog"),
            "https://example.com/favicon.ico",
        )

    def test_explicit_icon_still_wins(self):
        self.assertEqual(
            icon_of("mit", "https://news.mit.edu/", icon="https://x.test/i.png"),
            "https://x.test/i.png",
        )

    def test_verified_icon_returns_none_for_unlisted_feed(self):
        self.assertIsNone(verified_icon("definitely_not_a_feed"))

    def test_every_listed_feed_is_registered(self):
        # A stale key would silently do nothing; catch renames and deletions.
        import yaml

        registry = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "feeds.yaml").read_text(
                encoding="utf-8"
            )
        )["feeds"]
        unknown = sorted(set(VERIFIED_ICONS) - set(registry))
        self.assertEqual(unknown, [], "VERIFIED_ICONS names a feed that no longer exists")

    def test_entries_are_bare_domains_not_urls(self):
        # The value is fed to favicon_proxy(), which builds the URL itself, so a
        # full URL slipped in here would produce a nonsense proxy query.
        for name, domain in VERIFIED_ICONS.items():
            with self.subTest(feed=name):
                self.assertNotIn("://", domain)
                self.assertNotIn("/", domain)
                self.assertIn(".", domain)


if __name__ == "__main__":
    unittest.main()
