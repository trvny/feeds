import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import weather

ATOM = "{http://www.w3.org/2005/Atom}"
SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Pogoda — Kościelec (Chrzanów)</title>
  <id>tag:travny,2026:weather:koscielec</id>
  <updated>2026-09-03T08:00:58Z</updated>
  <link rel="self" href="https://weather.trfny.com/feed.atom"/>
  <link rel="alternate" href="https://weather.trfny.com/"/>
  <author><name>travny weather aggregator</name></author>
  <entry>
    <title>Kościelec: zachmurzenie, 18.6°C</title>
    <id>tag:travny,2026:weather:koscielec:current:1</id>
    <updated>2026-09-03T08:00:58Z</updated>
    <published>2026-09-03T08:00:58Z</published>
    <category term="current_change"/>
    <content type="text">temperatura +5.2°C → 18.6°C.</content>
  </entry>
</feed>"""


class WeatherFeedTests(unittest.TestCase):
    def test_doc_source_points_at_native_atom(self):
        self.assertEqual(
            weather.doc_sources(), [("Pogoda — Kościelec (Atom)", weather.SOURCE_URL)]
        )

    def test_build_xml_preserves_id_only_entries_and_repoints_self(self):
        payload = weather.build_xml(SAMPLE)
        self.assertIsNotNone(payload)
        root = ET.fromstring(payload)
        entry = root.find(f"{ATOM}entry")
        self.assertIsNotNone(entry)
        self.assertIsNone(entry.find(f"{ATOM}link"))
        self.assertEqual(
            entry.findtext(f"{ATOM}id"),
            "tag:travny,2026:weather:koscielec:current:1",
        )
        self_links = [
            link for link in root.findall(f"{ATOM}link") if link.get("rel") == "self"
        ]
        self.assertEqual(len(self_links), 1)
        self.assertEqual(self_links[0].get("href"), weather._PUBLISHED_URL)

    def test_build_xml_rejects_entity_declarations(self):
        payload = """<!DOCTYPE feed [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<feed xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="https://weather.trfny.com/feed.atom"/>
  <entry><id>&xxe;</id></entry>
</feed>"""
        rendered = weather.build_xml(payload)
        self.assertIsNotNone(rendered)
        self.assertNotIn(b"root:", rendered)

    def test_clean_json_feed_drops_synthetic_tag_url(self):
        doc = {
            "items": [
                {"id": "tag:travny,2026:weather:1", "url": "tag:travny,2026:weather:1"},
                {"id": "web", "url": "https://example.com/weather"},
            ]
        }
        cleaned = weather.clean_json_feed(doc)
        self.assertNotIn("url", cleaned["items"][0])
        self.assertEqual(cleaned["items"][1]["url"], "https://example.com/weather")

    def test_main_keeps_last_good_output_on_empty_source(self):
        with (
            patch.object(weather, "_fetch_source", return_value=b"<feed></feed>"),
            patch.object(weather, "save_mirrored_atom") as save,
        ):
            self.assertFalse(weather.main())
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
