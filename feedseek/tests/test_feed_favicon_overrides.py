import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import daily_quote  # noqa: E402
import medium  # noqa: E402
import nasa  # noqa: E402
import usgov  # noqa: E402
import wykop  # noqa: E402


class FeedFaviconOverrideTests(unittest.TestCase):
    def test_medium_uses_representative_icon(self):
        with patch.object(medium, "run", return_value=True) as run:
            self.assertTrue(medium.main())

        self.assertEqual(
            run.call_args.kwargs["icon"],
            "https://icons.duckduckgo.com/ip3/medium.com.ico",
        )

    def test_nasa_uses_representative_icon(self):
        with patch.object(nasa, "run", return_value=True) as run:
            self.assertTrue(nasa.main())

        self.assertEqual(
            run.call_args.kwargs["icon"],
            "https://icons.duckduckgo.com/ip3/nasa.gov.ico",
        )

    def test_usgov_uses_representative_icon(self):
        # Was pinned to the DuckDuckGo proxy, which 404s on usa.gov — the test
        # passed while the published feed carried a dead <icon>.
        with patch.object(usgov, "run", return_value=True) as run:
            self.assertTrue(usgov.main())

        self.assertEqual(
            run.call_args.kwargs["icon"],
            "https://www.google.com/s2/favicons?domain=usa.gov&sz=64",
        )

    def test_daily_quote_uses_wikiquote_icon(self):
        xml = daily_quote.generate_atom_feed([]).atom_str().decode()

        self.assertIn(
            "<icon>https://icons.duckduckgo.com/ip3/en.wikiquote.org.ico</icon>",
            xml,
        )

    def test_wykop_uses_explicit_proxy_icon(self):
        # Same story as usgov: DuckDuckGo has no icon for wykop.pl.
        xml = wykop.generate_atom_feed([]).atom_str().decode()

        self.assertIn(
            "<icon>https://www.google.com/s2/favicons?domain=wykop.pl&amp;sz=64</icon>",
            xml,
        )


if __name__ == "__main__":
    unittest.main()
