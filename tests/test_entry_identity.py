import ast
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import multi_rss  # noqa: E402
import utils  # noqa: E402
from entry_identity import ENTRY_ID_FIELD, entry_id_for  # noqa: E402


class EntryIdentityTests(unittest.TestCase):
    def test_persisted_id_wins_over_changed_link(self):
        entry = {
            "link": "https://example.com/new-location",
            ENTRY_ID_FIELD: "tag:example.test,2026:old-reader-id",
        }
        with patch.object(utils, "make_entry_id") as make_id:
            actual = entry_id_for("example", entry)

        self.assertEqual(actual, "tag:example.test,2026:old-reader-id")
        make_id.assert_not_called()

    def test_unseeded_entry_uses_the_existing_url_fallback(self):
        link = "https://example.com/article"
        self.assertEqual(
            entry_id_for("example", {"link": link}),
            utils.make_entry_id("example", link),
        )

    def test_unseeded_entry_without_link_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no 'link'"):
            entry_id_for("example", {})


class EntryIdentityPolicyTests(unittest.TestCase):
    def test_renderers_do_not_call_legacy_id_seed_directly(self):
        generators = Path(__file__).resolve().parents[1] / "feed_generators"
        infrastructure = {"entry_identity.py", "invoke_generator.py", "utils.py"}
        offenders = []

        for path in sorted(generators.glob("*.py")):
            if path.name in infrastructure:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                direct = isinstance(func, ast.Name) and func.id == "make_entry_id"
                qualified = isinstance(func, ast.Attribute) and func.attr == "make_entry_id"
                if direct or qualified:
                    offenders.append(f"{path.name}:{node.lineno}")

        self.assertEqual(
            offenders,
            [],
            "renderers must use entry_identity.entry_id_for: " + ", ".join(offenders),
        )


class MultiRssEntryIdentityTests(unittest.TestCase):
    def _article(self, **overrides):
        article = {
            "title": "Article",
            "link": "https://example.com/article",
            "description": "Description",
            "source": "Example",
            "image": None,
            "date": datetime(2026, 8, 24, tzinfo=timezone.utc),
        }
        article.update(overrides)
        return article

    def _xml(self, article):
        feed = multi_rss.generate_atom_feed(
            [article],
            feed_name="example",
            feed_id="https://example.com/feed",
            title="Example feed",
            subtitle="Example subtitle",
            blog_url="https://example.com/",
            author="Example",
        )
        return feed.atom_str(pretty=True).decode()

    def test_renderer_prefers_persisted_id(self):
        persisted = "tag:example.test,2026:persisted"
        xml = self._xml(
            self._article(
                link="https://example.com/moved",
                entry_id=persisted,
            )
        )
        self.assertIn(f"<id>{persisted}</id>", xml)

    def test_renderer_keeps_legacy_fallback_for_unseeded_entry(self):
        article = self._article()
        expected = utils.make_entry_id("example", article["link"])
        xml = self._xml(article)
        self.assertIn(f"<id>{expected}</id>", xml)


if __name__ == "__main__":
    unittest.main()
