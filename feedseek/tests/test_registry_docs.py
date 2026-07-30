import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
FEEDSEEK = ROOT / "feedseek"


def load_registry():
    data = yaml.safe_load((FEEDSEEK / "feeds.yaml").read_text(encoding="utf-8"))
    return data["feeds"]


class RegistryDocsTests(unittest.TestCase):
    def test_every_registered_feed_has_a_generator_and_readme_row(self):
        registry = load_registry()
        missing_scripts = sorted(
            name
            for name, config in registry.items()
            if not (FEEDSEEK / "feed_generators" / config["script"]).is_file()
        )
        self.assertEqual(missing_scripts, [])

        readme = (FEEDSEEK / "README.md").read_text(encoding="utf-8")
        documented = set(re.findall(r"\[feed_([A-Za-z0-9_-]+)\.xml\]\(", readme))
        self.assertEqual(documented, set(registry))

    def test_readme_feed_counts_match_registry(self):
        expected = len(load_registry())
        polish = (ROOT / "README.md").read_text(encoding="utf-8")
        english = (ROOT / "docs" / "README-EN.md").read_text(encoding="utf-8")

        counts = [
            int(re.search(r"feeds-(\d+)-d6541a", polish).group(1)),
            int(re.search(r"feeds\.yaml \((\d+) źródeł\)", polish).group(1)),
            int(re.search(r"feeds-(\d+)-d6541a", english).group(1)),
            int(re.search(r"feeds\.yaml \((\d+) sources\)", english).group(1)),
        ]
        self.assertEqual(counts, [expected] * len(counts))

    def test_public_feed_list_only_references_registered_feeds(self):
        registry = set(load_registry())
        lines = (FEEDSEEK / "site" / "published_feeds.txt").read_text(encoding="utf-8").splitlines()
        published = [
            line.split("|", 1)[0].strip()
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        ]

        self.assertEqual(len(published), len(set(published)))
        self.assertEqual(sorted(set(published) - registry), [])


if __name__ == "__main__":
    unittest.main()
