import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import palantir  # noqa: E402


class PalantirRegressionTests(unittest.TestCase):
    def test_palantir_host_check_requires_an_exact_hostname(self):
        self.assertTrue(
            palantir._is_palantir_url(
                "https://www.palantir.com/blog/example/"
            )
        )
        self.assertFalse(
            palantir._is_palantir_url(
                "https://www.palantir.com.evil.example/blog/example/"
            )
        )
        self.assertFalse(
            palantir._is_palantir_url(
                "https://notpalantir.com/blog/example/"
            )
        )

    def test_internal_card_without_dates_gets_one_frozen_fallback(self):
        listing = """
        <article>
          <h2><a href="/blog/undated-post/">Undated Palantir post</a></h2>
          <p>No date is exposed.</p>
        </article>
        """
        fixed_now = datetime(2026, 7, 29, 16, 50, tzinfo=timezone.utc)
        metadata = {
            "title": "Undated Palantir post",
            "description": "No date is exposed.",
            "date": None,
            "image": None,
        }

        with (
            patch.object(palantir, "get_html", return_value=listing),
            patch.object(palantir, "_article_meta", return_value=metadata),
            patch.object(palantir, "datetime") as datetime_mock,
        ):
            datetime_mock.now.return_value = fixed_now
            entries = palantir.scrape_listing(
                "Blog",
                palantir.BLOG_URL,
                set(),
                set(),
                internal_prefix="/blog/",
            )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["date"], fixed_now)
        datetime_mock.now.assert_called_once_with(timezone.utc)


if __name__ == "__main__":
    unittest.main()
