import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from validate_feeds import _entry_date  # noqa: E402


class EntryDateTests(unittest.TestCase):
    def test_atom_published_wins_over_synthetic_updated(self):
        entry = ET.fromstring(
            """
            <entry xmlns="http://www.w3.org/2005/Atom">
              <updated>2026-07-22T10:32:09+00:00</updated>
              <published>2025-01-02T03:04:05+00:00</published>
            </entry>
            """
        )
        self.assertEqual(_entry_date(entry), datetime.fromisoformat("2025-01-02T03:04:05+00:00"))

    def test_atom_updated_is_used_when_published_is_absent(self):
        entry = ET.fromstring(
            """
            <entry xmlns="http://www.w3.org/2005/Atom">
              <updated>2026-07-22T10:32:09Z</updated>
            </entry>
            """
        )
        self.assertEqual(_entry_date(entry), datetime.fromisoformat("2026-07-22T10:32:09+00:00"))


if __name__ == "__main__":
    unittest.main()
