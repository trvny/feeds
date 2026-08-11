import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from jsonfeed import build_json_feed  # noqa: E402


class JsonFeedIconTests(unittest.TestCase):
    def _build(self, metadata: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feed_test.xml"
            path.write_text(
                f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>https://example.com/</id>
  <title>Test</title>
  <updated>2026-08-11T00:00:00+00:00</updated>
  <link href="https://example.com/" rel="alternate"/>
{metadata}
</feed>
""",
                encoding="utf-8",
            )
            return build_json_feed(path, "test")

    def test_exposes_favicon_and_large_icon_separately(self):
        doc = self._build(
            "  <icon>https://example.com/favicon.png</icon>\n"
            "  <logo>https://example.com/logo.png</logo>"
        )

        self.assertEqual(doc["favicon"], "https://example.com/favicon.png")
        self.assertEqual(doc["icon"], "https://example.com/logo.png")

    def test_icon_falls_back_to_favicon(self):
        doc = self._build("  <icon>https://example.com/favicon.png</icon>")

        self.assertEqual(doc["favicon"], "https://example.com/favicon.png")
        self.assertEqual(doc["icon"], "https://example.com/favicon.png")


if __name__ == "__main__":
    unittest.main()
