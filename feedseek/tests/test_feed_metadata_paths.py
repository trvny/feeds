import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATORS_DIR = ROOT / "feed_generators"
LEGACY_RAW_FEED_PREFIX = "https://raw.githubusercontent.com/trvny/feeds/main/feeds/"
NORMALIZER = "normalize_feed_self_links.py"


class FeedMetadataPathTests(unittest.TestCase):
    def test_generators_do_not_hardcode_legacy_raw_feed_root(self):
        offenders = []
        for path in sorted(GENERATORS_DIR.glob("*.py")):
            if path.name == NORMALIZER:
                continue
            if LEGACY_RAW_FEED_PREFIX in path.read_text(encoding="utf-8"):
                offenders.append(path.name)

        self.assertEqual(
            offenders,
            [],
            "Generators must publish self links from /feedseek/feeds/: "
            + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
