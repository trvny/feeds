"""Tests for the post-generation feed metadata normalizer."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from normalize_feed_self_links import (  # noqa: E402  # pylint: disable=wrong-import-position
    CURRENT_PREFIX,
    LEGACY_PREFIX,
    normalize_feed_self_links,
)


class NormalizeFeedSelfLinksTests(unittest.TestCase):
    """Cover self-link cleanup and cross-reader Atom icon hints."""

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

    def test_mirrors_icon_in_compact_atom_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            feeds_dir = Path(tmp)
            feed = feeds_dir / "feed_compact.xml"
            feed.write_text(
                '<feed><icon>https://example.com/favicon.ico</icon></feed>',
                encoding="utf-8",
            )

            changed = normalize_feed_self_links(feeds_dir)
            content = feed.read_text(encoding="utf-8")

            self.assertEqual(changed, [feed])
            self.assertIn("<logo>https://example.com/favicon.ico</logo>", content)

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


if __name__ == "__main__":
    unittest.main()
