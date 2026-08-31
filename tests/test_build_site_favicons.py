import html
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "site" / "build_site.py"
SPEC = importlib.util.spec_from_file_location("build_site", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load {MODULE_PATH}")
build_site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_site)


class SiteFaviconTests(unittest.TestCase):
    def _parse(self, xml):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feed_test.xml"
            path.write_text(xml, encoding="utf-8")
            return build_site.parse_feed(path)

    def test_atom_icon_and_logo_are_read(self):
        feed = self._parse(
            """<?xml version="1.0"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
              <title>Test</title>
              <link rel="alternate" href="https://example.com/news"/>
              <icon>https://example.com/icon.png</icon>
              <logo>/logo.svg</logo>
            </feed>
            """
        )

        self.assertEqual(feed["icon"], "https://example.com/icon.png")
        self.assertEqual(feed["logo"], "/logo.svg")

    def test_rss_channel_image_is_read(self):
        feed = self._parse(
            """<?xml version="1.0"?>
            <rss version="2.0"><channel>
              <title>Test</title>
              <link>https://example.com/</link>
              <description>Test feed</description>
              <image><url>https://example.com/rss.png</url></image>
            </channel></rss>
            """
        )

        self.assertEqual(feed["icon"], "https://example.com/rss.png")

    def test_feed_icon_precedes_service_fallbacks(self):
        candidates = build_site.favicon_candidates(
            {
                "source": "https://trojka.polskieradio.pl/news",
                "icon": "https://trojka.polskieradio.pl/assets/favicon-32x32.png",
                "logo": "https://trojka.polskieradio.pl/logo.svg",
            }
        )

        self.assertEqual(
            candidates[0],
            "https://trojka.polskieradio.pl/assets/favicon-32x32.png",
        )
        self.assertEqual(candidates[-1], build_site.FAVICON_SVG)

    def test_google_proxy_icon_does_not_mask_origin_favicon(self):
        candidates = build_site.favicon_candidates(
            {
                "source": "https://www.usa.gov/",
                "icon": "https://www.google.com/s2/favicons?domain=usa.gov&sz=64",
                "logo": "",
            }
        )

        self.assertEqual(candidates[0], "https://www.usa.gov/favicon.ico")
        self.assertIn("https://icons.duckduckgo.com/ip3/usa.gov.ico", candidates)
        self.assertEqual(candidates[-1], build_site.FAVICON_SVG)

    def test_rendered_card_embeds_remaining_fallbacks(self):
        card = build_site.render_card(
            {
                "filename": "feed_test.xml",
                "title": "Test",
                "subtitle": "",
                "source": "https://example.com/",
                "icon": "https://example.com/icon.png",
                "logo": "",
                "entries": 1,
                "updated": None,
            },
            "https://feeds.example/",
        )

        marker = 'data-fallbacks="'
        start = card.index(marker) + len(marker)
        encoded = card[start : card.index('"', start)]
        fallbacks = json.loads(html.unescape(encoded))
        self.assertIn("https://example.com/favicon.ico", fallbacks)
        self.assertEqual(fallbacks[-1], build_site.FAVICON_SVG)

    def test_autodiscovery_advertises_xml_and_json_feed(self):
        links = build_site.render_autodiscovery(
            [{"filename": "feed_test.xml", "title": "Test", "format": "atom"}],
            "https://feeds.example/",
        )

        self.assertIn('type="application/atom+xml"', links)
        self.assertIn('href="https://feeds.example/feed_test.xml"', links)
        self.assertIn('type="application/feed+json"', links)
        self.assertIn('href="https://feeds.example/feed_test.json"', links)

    def test_publication_requires_json_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            xml = directory / "feed_test.xml"
            xml.write_text("<feed />", encoding="utf-8")
            original = build_site.FEEDS_DIR
            build_site.FEEDS_DIR = directory
            self.addCleanup(setattr, build_site, "FEEDS_DIR", original)

            with self.assertRaisesRegex(SystemExit, "feed_test.json"):
                build_site.require_json_sidecars(
                    [{"filename": "feed_test.xml", "title": "Test"}]
                )

    def test_publication_accepts_xml_json_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "feed_test.xml").write_text("<feed />", encoding="utf-8")
            (directory / "feed_test.json").write_text("{}", encoding="utf-8")
            original = build_site.FEEDS_DIR
            build_site.FEEDS_DIR = directory
            self.addCleanup(setattr, build_site, "FEEDS_DIR", original)

            build_site.require_json_sidecars(
                [{"filename": "feed_test.xml", "title": "Test"}]
            )


if __name__ == "__main__":
    unittest.main()
