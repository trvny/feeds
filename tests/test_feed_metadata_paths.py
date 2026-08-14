import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATORS_DIR = ROOT / "feed_generators"
LEGACY_RAW_PATH = "/main/feedseek/feeds/"
NORMALIZER = "normalize_feed_self_links.py"


class FeedMetadataPathTests(unittest.TestCase):
    def test_generators_do_not_hardcode_nested_legacy_feed_paths(self):
        offenders = []
        for path in sorted(GENERATORS_DIR.glob("*.py")):
            if path.name == NORMALIZER:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            strings = (
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            )
            if any("raw.githubusercontent.com" in value and LEGACY_RAW_PATH in value for value in strings):
                offenders.append(path.name)

        self.assertEqual(
            offenders,
            [],
            "Generators must not publish self links from nested /feedseek/feeds/: "
            + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
