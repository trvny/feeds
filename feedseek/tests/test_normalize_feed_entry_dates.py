import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from normalize_feed_entry_dates import normalize_atom_xml  # noqa: E402


class NormalizeFeedEntryDatesTests(unittest.TestCase):
    def test_replaces_feedgen_build_timestamp_with_published_date(self):
        xml = """
        <feed xmlns="http://www.w3.org/2005/Atom">
          <updated>2026-07-30T02:33:56.345673+00:00</updated>
          <entry>
            <updated>2026-07-30T02:33:56.346547+00:00</updated>
            <published>2026-07-27T14:34:00+00:00</published>
          </entry>
        </feed>
        """

        normalized, count = normalize_atom_xml(xml)

        self.assertEqual(count, 1)
        self.assertIn(
            "<updated>2026-07-27T14:34:00+00:00</updated>", normalized
        )

    def test_preserves_real_article_update(self):
        xml = """
        <feed xmlns="http://www.w3.org/2005/Atom">
          <updated>2026-07-30T02:33:56+00:00</updated>
          <entry>
            <updated>2026-07-29T10:00:00+00:00</updated>
            <published>2026-07-20T10:00:00+00:00</published>
          </entry>
        </feed>
        """

        normalized, count = normalize_atom_xml(xml)

        self.assertEqual(count, 0)
        self.assertEqual(normalized, xml)

    def test_preserves_dateless_entry(self):
        xml = """
        <feed xmlns="http://www.w3.org/2005/Atom">
          <updated>2026-07-30T02:33:56+00:00</updated>
          <entry>
            <updated>2026-07-30T02:33:56+00:00</updated>
          </entry>
        </feed>
        """

        normalized, count = normalize_atom_xml(xml)

        self.assertEqual(count, 0)
        self.assertEqual(normalized, xml)


if __name__ == "__main__":
    unittest.main()
