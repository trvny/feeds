import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import xai


class XaiLegacyCacheTests(unittest.TestCase):
    def test_legacy_cache_is_seeded_when_grouped_cache_has_no_x_api(self):
        legacy = {
            "entries": [
                {
                    "title": "Legacy X API update",
                    "link": "https://docs.x.com/changelog#legacy",
                    "date": "2026-08-01T00:00:00+00:00",
                    "description": "Legacy update",
                }
            ]
        }
        with patch.object(xai, "load_cache", return_value=legacy):
            seeded = xai._seed_legacy_x_api_cache([])

        self.assertEqual(len(seeded), 1)
        self.assertEqual(seeded[0]["source"], "X API changelog")

    def test_existing_grouped_x_api_skips_legacy_cache(self):
        cached = [
            {
                "title": "Current X API update",
                "link": "https://docs.x.com/changelog#current",
                "source": "X API changelog",
            }
        ]
        with patch.object(xai, "load_cache") as load_cache:
            seeded = xai._seed_legacy_x_api_cache(cached)

        load_cache.assert_not_called()
        self.assertIs(seeded, cached)


if __name__ == "__main__":
    unittest.main()
