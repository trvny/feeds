import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATORS_DIR = ROOT / "feed_generators"
LEGACY_RAW_PATH = "/main/feedseek/feeds/"
NORMALIZER = "normalize_feed_self_links.py"


def string_template(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            value.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
            else "{}"
            for value in node.values
        )
    return None


class FeedMetadataPathTests(unittest.TestCase):
    def test_generators_do_not_hardcode_nested_legacy_feed_paths(self):
        offenders = []
        for path in sorted(GENERATORS_DIR.glob("*.py")):
            if path.name == NORMALIZER:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            templates = (string_template(node) for node in ast.walk(tree))
            if any(template and LEGACY_RAW_PATH in template for template in templates):
                offenders.append(path.name)

        self.assertEqual(
            offenders,
            [],
            "Generators must not publish self links from nested /feedseek/feeds/: "
            + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
