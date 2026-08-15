import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import redhat
from utils import merge_entries


class RedHatSourceTests(unittest.TestCase):
    def test_specific_channels_precede_general_blog(self):
        labels = [label for label, _, _ in redhat.SOURCES]
        general = labels.index("Red Hat Blog")
        self.assertLess(labels.index("Red Hat Enterprise Linux"), general)
        self.assertLess(labels.index("Red Hat Security"), general)
        self.assertLess(labels.index("Red Hat Satellite"), general)

        specific = {
            "link": "https://www.redhat.com/en/blog/example",
            "date": None,
            "source": "Red Hat Security",
        }
        general_entry = {**specific, "source": "Red Hat Blog"}
        merged = merge_entries([specific, general_entry], [])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "Red Hat Security")

    def test_legacy_sources_and_rhsa_have_small_intake_caps(self):
        caps = {label: cap for label, _, cap in redhat.SOURCES}
        self.assertLessEqual(caps["Red Hat Security Blog (legacy)"], 4)
        self.assertLessEqual(caps["Red Hat Satellite Blog (legacy)"], 4)
        self.assertLessEqual(caps["Red Hat Performance Blog (legacy)"], 4)
        self.assertLessEqual(caps["Red Hat Insights Blog (legacy)"], 4)
        self.assertLessEqual(caps["Red Hat Security Errata"], 15)
        self.assertLessEqual(redhat.PER_SOURCE_QUOTA["Red Hat Security Errata"], 14)

    def test_newsroom_parses_cards_deduplicates_and_sorts(self):
        html = """
        <div>
          <rh-card>
            <h3><a href="/en/about/press-releases/older">Older release</a></h3>
            <p>May 28, 2026</p>
          </rh-card>
          <rh-card>
            <h3><a href="/en/about/press-releases/newer">Newer release</a></h3>
            <p>July 8, 2026</p>
          </rh-card>
          <rh-card>
            <h3><a href="/en/about/press-releases/newer">Newer release</a></h3>
            <p>July 8, 2026</p>
          </rh-card>
          <a href="/en/blog/not-a-press-release">Ignore me</a>
        </div>
        """
        with patch.object(redhat, "get_html", return_value=html):
            entries = redhat.scrape_newsroom(
                {"https://www.redhat.com/en/about/press-releases/older"}
            )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Newer release")
        self.assertEqual(entries[0]["source"], "Red Hat Newsroom")
        self.assertEqual(entries[0]["date"].isoformat(), "2026-07-08T00:00:00+00:00")

    def test_security_changelog_parses_dated_topics_and_resets_sections(self):
        html = """
        <h3>Navigation heading</h3>
        <h2>July 17, 2026</h2>
        <h3>OVAL</h3>
        <p>New OVAL data.</p>
        <ul><li>Schema change.</li></ul>
        <h3>CSAF</h3>
        <p>New CSAF data.</p>
        <h2>Select Your Language</h2>
        <h3>Footer heading</h3>
        <h2>June 12, 2026 (announced later)</h2>
        <h3>VEX</h3>
        <p>VEX update.</p>
        """
        with patch.object(redhat, "get_html", return_value=html):
            entries = redhat.scrape_security_data_changelog(set())

        self.assertEqual([entry["title"] for entry in entries], ["OVAL", "CSAF", "VEX"])
        self.assertEqual(entries[0]["date"].isoformat(), "2026-07-17T00:00:00+00:00")
        self.assertEqual(entries[2]["date"].isoformat(), "2026-06-12T00:00:00+00:00")
        self.assertIn("New OVAL data", entries[0]["description"])
        self.assertTrue(entries[0]["link"].startswith(redhat.SECURITY_CHANGELOG_URL + "#security-data-"))
        self.assertEqual(entries[0]["source"], "Red Hat Security Data Changelog")

    def test_security_changelog_caps_before_known_link_filter(self):
        blocks = []
        for day in range(30, 0, -1):
            blocks.append(f"<h2>July {day}, 2026</h2><h3>Topic {day}</h3><p>Change {day}</p>")
        html = "".join(blocks)

        with patch.object(redhat, "get_html", return_value=html):
            first = redhat.scrape_security_data_changelog(set())
            known = {entry["link"] for entry in first}
            second = redhat.scrape_security_data_changelog(known)

        self.assertEqual(len(first), redhat.SECURITY_CHANGELOG_CAP)
        self.assertEqual(second, [])


if __name__ == "__main__":
    unittest.main()
