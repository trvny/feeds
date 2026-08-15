import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import cognition  # noqa: E402


class CognitionSourceTests(unittest.TestCase):
    def test_research_wins_when_cognition_post_is_cross_listed(self):
        research = """
        <a href="/research/example">Example research 08.14.26 Research summary</a>
        """
        blog = """
        <a href="/research/example">Example research 08.14.26 Research summary</a>
        <a href="/blog/example">Example blog 08.13.26 Blog summary</a>
        """

        with patch.object(cognition, "_fetch", side_effect=[research, blog]):
            entries = cognition.collect_cognition(set())

        self.assertEqual(
            [entry["link"] for entry in entries],
            [
                "https://cognition.com/research/example",
                "https://cognition.com/blog/example",
            ],
        )
        self.assertEqual(entries[0]["source"], "Cognition Research")
        self.assertEqual(entries[1]["source"], "Cognition Blog")
        self.assertEqual(entries[0]["description"], "Research summary")

    def test_devin_release_notes_become_one_entry_per_date(self):
        markdown = (
            "## August 14, 2026\n"
            "- Added a feature.\n\n"
            "## August 13, 2026\n"
            "- Fixed a bug.\n"
        )

        with patch.object(cognition, "_fetch", return_value=markdown):
            entries = cognition.collect_devin_release_notes(set())

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["title"], "Devin updates — August 14, 2026")
        self.assertEqual(
            entries[0]["link"],
            "https://docs.devin.ai/release-notes/overview#august-14-2026",
        )
        self.assertIn("Added a feature", entries[0]["description"])
        self.assertEqual(entries[1]["date"].isoformat(), "2026-08-13T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
