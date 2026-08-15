import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import openai


class ChatGPTHelpReleaseNotesTests(unittest.TestCase):
    HTML = """
    <article>
      <h1>ChatGPT — Release Notes</h1>
      <p>A changelog of the latest updates and release notes for ChatGPT</p>
      <h1>Aug 10, 2026</h1>
      <h2>Restaurant reservations in ChatGPT</h2>
      <p>ChatGPT can now help you find available restaurant reservations.</p>
      <h1>August 7, 2026</h1>
      <h2>Files and Projects in ChatGPT Voice</h2>
      <p>GPT-Live in ChatGPT Voice now supports file uploads and Projects.</p>
      <h2>Another update on the same day</h2>
      <p>This proves multiple entries under one date stay separate.</p>
      <h1>August 4th, 2026</h1>
      <h2>Large pastes are now handled as attachments for all plans</h2>
      <p>Long pastes are converted into attachments.</p>
    </article>
    """

    def test_parses_dated_sections_and_multiple_entries_per_day(self):
        with patch.object(openai, "_get_html", return_value=self.HTML):
            entries = openai.scrape_chatgpt_help_release_notes(set())

        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0]["title"], "Restaurant reservations in ChatGPT")
        self.assertEqual(entries[0]["date"].isoformat(), "2026-08-10T00:00:00+00:00")
        self.assertEqual(entries[1]["date"].isoformat(), "2026-08-07T00:00:00+00:00")
        self.assertEqual(entries[2]["date"].isoformat(), "2026-08-07T00:00:00+00:00")
        self.assertEqual(entries[3]["date"].isoformat(), "2026-08-04T00:00:00+00:00")
        self.assertTrue(entries[0]["link"].startswith(openai.CHATGPT_HELP_URL + "#chatgpt-2026-08-10-"))
        self.assertEqual(entries[0]["source"], openai.CHATGPT_HELP_LABEL)
        self.assertIn("available restaurant reservations", entries[0]["description"])

    def test_known_synthetic_link_is_skipped(self):
        known = {
            openai.CHATGPT_HELP_URL
            + "#chatgpt-2026-08-10-restaurant-reservations-in-chatgpt"
        }
        with patch.object(openai, "_get_html", return_value=self.HTML):
            entries = openai.scrape_chatgpt_help_release_notes(known)

        self.assertEqual(len(entries), 3)
        self.assertNotIn("Restaurant reservations in ChatGPT", {entry["title"] for entry in entries})

    def test_cap_limits_first_run_backfill(self):
        with patch.object(openai, "_get_html", return_value=self.HTML):
            entries = openai.scrape_chatgpt_help_release_notes(set(), cap=2)

        self.assertEqual(len(entries), 2)
        self.assertEqual(
            [entry["title"] for entry in entries],
            ["Restaurant reservations in ChatGPT", "Files and Projects in ChatGPT Voice"],
        )

    def test_warns_if_help_center_layout_loses_date_sections(self):
        html = "<article><h1>ChatGPT — Release Notes</h1><h2>Update without a date</h2></article>"
        with (
            patch.object(openai, "_get_html", return_value=html),
            patch.object(openai.logger, "warning") as warning,
        ):
            entries = openai.scrape_chatgpt_help_release_notes(set())

        self.assertEqual(entries, [])
        warning.assert_called_once_with(
            "  [ChatGPT release notes] no dated sections matched — layout may have changed"
        )


if __name__ == "__main__":
    unittest.main()
