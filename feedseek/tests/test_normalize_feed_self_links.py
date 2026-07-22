import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from normalize_feed_self_links import (  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
