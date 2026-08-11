import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from normalize_feed_self_links import (  # noqa: E402
    ATOM_ICON_OVERRIDES,
    CURRENT_PREFIX,
    LEGACY_PREFIX,
    normalize_feed_self_links,
)


class NormalizeFeedSelfLinksTests(unittest.TestCase):
    def test_rewrites_legacy_prefix_without_touching_other_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            feeds_dir = Path(tmp)
            legacy = feeds_dir / "feed_jbzd.xml"
            current = feeds_dir / "feed_trojka.xml"
            legacy.write_text(
                f'<feed><link href="{LEGACY_PREFIX}feed_jbzd.xml" rel="self"/></feed>',
                encoding="utf-8",
            )
            current.write_text(
                f'<feed><link href="{CURRENT_PREFIX}feed_trojka.xml" rel="self"/></feed>',
                encoding="utf-8",
            )

            changed = normalize_feed_self_links(feeds_dir)

            self.assertEqual(changed, [legacy])
            self.assertIn(
                f'{CURRENT_PREFIX}feed_jbzd.xml',
                legacy.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                current.read_text(encoding="utf-8"),
                f'<feed><link href="{CURRENT_PREFIX}feed_trojka.xml" rel="self"/></feed>',
            )

    def test_ignores_non_xml_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            feeds_dir = Path(tmp)
            sidecar = feeds_dir / "feed_jbzd.json"
            sidecar.write_text(LEGACY_PREFIX, encoding="utf-8")

            changed = normalize_feed_self_links(feeds_dir)

            self.assertEqual(changed, [])
            self.assertEqual(sidecar.read_text(encoding="utf-8"), LEGACY_PREFIX)

    def test_mirrors_atom_icon_into_missing_logo(self):
        with tempfile.TemporaryDirectory() as tmp:
            feeds_dir = Path(tmp)
            feed = feeds_dir / "feed_daily_digest.xml"
            feed.write_text(
                """<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Daily Digest</title>
  <icon>https://icons.example/digest.ico</icon>
</feed>
""",
                encoding="utf-8",
            )

            changed = normalize_feed_self_links(feeds_dir)
            content = feed.read_text(encoding="utf-8")

            self.assertEqual(changed, [feed])
            self.assertIn("<icon>https://icons.example/digest.ico</icon>", content)
            self.assertIn("<logo>https://icons.example/digest.ico</logo>", content)

    def test_preserves_existing_distinct_logo_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            feeds_dir = Path(tmp)
            feed = feeds_dir / "feed_brand.xml"
            original = """<feed xmlns="http://www.w3.org/2005/Atom">
  <icon>https://example.com/favicon.png</icon>
  <logo>https://example.com/full-logo.png</logo>
</feed>
"""
            feed.write_text(original, encoding="utf-8")

            changed = normalize_feed_self_links(feeds_dir)

            self.assertEqual(changed, [])
            self.assertEqual(feed.read_text(encoding="utf-8"), original)

    def test_trojka_uses_raster_icon_in_logo_slot_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            feeds_dir = Path(tmp)
            feed = feeds_dir / "feed_trojka.xml"
            icon = "https://trojka.polskieradio.pl/assets/favicon-32x32.png"
            feed.write_text(
                f"""<feed xmlns="http://www.w3.org/2005/Atom">
  <icon>{icon}</icon>
  <logo>https://trojka.polskieradio.pl/logo_100_black.svg</logo>
</feed>
""",
                encoding="utf-8",
            )

            changed = normalize_feed_self_links(feeds_dir)
            content = feed.read_text(encoding="utf-8")

            self.assertEqual(changed, [feed])
            self.assertIn(f"<icon>{icon}</icon>", content)
            self.assertIn(f"<logo>{icon}</logo>", content)
            self.assertNotIn("logo_100_black.svg", content)

    def test_youtube_gets_its_own_advertised_favicon(self):
        with tempfile.TemporaryDirectory() as tmp:
            feeds_dir = Path(tmp)
            feed = feeds_dir / "feed_youtube.xml"
            feed.write_text(
                """<feed xmlns="http://www.w3.org/2005/Atom">
  <icon>https://blog.youtube/favicon.ico</icon>
</feed>
""",
                encoding="utf-8",
            )

            changed = normalize_feed_self_links(feeds_dir)
            content = feed.read_text(encoding="utf-8")
            expected = ATOM_ICON_OVERRIDES["youtube"]

            self.assertEqual(changed, [feed])
            self.assertIn(f"<icon>{expected}</icon>", content)
            self.assertIn(f"<logo>{expected}</logo>", content)


if __name__ == "__main__":
    unittest.main()
