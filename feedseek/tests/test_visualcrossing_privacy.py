import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import visualcrossing  # noqa: E402


class VisualCrossingPrivacyTests(unittest.TestCase):
    def test_day_title_uses_coarse_public_location(self):
        data = {
            "resolvedAddress": "ul. Kasztanowa 6, 32-500 Chrzanów, Polska",
            "tzoffset": 2,
            "days": [
                {
                    "datetime": "2026-07-30",
                    "conditions": "Słonecznie",
                    "tempmin": 15,
                    "tempmax": 27,
                }
            ],
        }

        title = visualcrossing.build_day_entries(data)[0]["title"]

        self.assertTrue(title.startswith("Chrzanów 32-500 — "))
        self.assertNotIn("Kasztanowa", title)

    def test_cached_precise_locations_are_redacted(self):
        cached = [
            {
                "guid": "day",
                "kind": "day",
                "title": "ul. Kasztanowa 6, 32-500 Chrzanów — czwartek: Słonecznie",
                "date": "2026-07-30T00:00:00+02:00",
                "updated": "2026-07-30T10:00:00+00:00",
            },
            {
                "guid": "alert",
                "kind": "alert",
                "title": "⚠️ ul. Kasztanowa 6, 32-500 Chrzanów — Burza",
                "date": "2026-07-30T12:00:00+02:00",
                "updated": "2026-07-30T10:00:00+00:00",
            },
        ]

        redacted = visualcrossing._deserialize(cached)

        self.assertEqual(
            redacted[0]["title"],
            "Chrzanów 32-500 — czwartek: Słonecznie",
        )
        self.assertEqual(
            redacted[1]["title"],
            "⚠️ Chrzanów 32-500 — Burza",
        )


if __name__ == "__main__":
    unittest.main()
