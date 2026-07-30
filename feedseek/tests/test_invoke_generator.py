import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from feedgen.feed import FeedGenerator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from invoke_generator import invoke, preserve_atom_publication_dates  # noqa: E402


class InvokeGeneratorTests(unittest.TestCase):
    def _script(self, source: str) -> Path:
        directory = Path(tempfile.mkdtemp())
        path = directory / "generator.py"
        path.write_text(source, encoding="utf-8")
        return path

    def _atom_entry(self, *, explicit_updated=None) -> str:
        fg = FeedGenerator()
        fg.id("https://example.com/")
        fg.title("Example")
        fg.author({"name": "Example"})
        fe = fg.add_entry()
        fe.id("https://example.com/post")
        fe.title("Post")
        fe.link(href="https://example.com/post")
        fe.published(datetime(2020, 1, 2, tzinfo=timezone.utc))
        if explicit_updated is not None:
            fe.updated(explicit_updated)
        return fg.atom_str(pretty=True).decode()

    def test_explicit_false_is_a_failed_generation(self):
        script = self._script("def main(full=False):\n    return False\n")
        self.assertFalse(invoke(script))

    def test_none_remains_backward_compatible_success(self):
        script = self._script("def main():\n    pass\n")
        self.assertTrue(invoke(script))

    def test_integer_exit_statuses_are_normalized(self):
        success = self._script("def main():\n    return 0\n")
        failure = self._script("def main():\n    return 1\n")
        self.assertTrue(invoke(success))
        self.assertFalse(invoke(failure))

    def test_full_reset_signature_is_supported(self):
        script = self._script(
            "def main(full_reset=False):\n"
            "    return full_reset\n"
        )
        self.assertTrue(invoke(script, full=True))
        self.assertFalse(invoke(script, full=False))

    def test_generator_receives_isolated_argv(self):
        script = self._script(
            "import argparse\n"
            "def main():\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--full', action='store_true')\n"
            "    return 0 if parser.parse_args().full else 1\n"
        )
        self.assertTrue(invoke(script, full=True))
        self.assertFalse(invoke(script, full=False))

    def test_decorators_can_resolve_dynamic_module(self):
        script = self._script(
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Item:\n"
            "    value: int\n"
            "def main():\n"
            "    return Item(1).value == 1\n"
        )
        self.assertTrue(invoke(script))

    def test_implicit_atom_update_uses_publication_date(self):
        with preserve_atom_publication_dates():
            xml = self._atom_entry()

        self.assertIn("<published>2020-01-02T00:00:00+00:00</published>", xml)
        self.assertIn("<updated>2020-01-02T00:00:00+00:00</updated>", xml)

    def test_explicit_atom_update_is_preserved(self):
        updated = datetime(2026, 7, 30, 2, 0, tzinfo=timezone.utc)
        with preserve_atom_publication_dates():
            xml = self._atom_entry(explicit_updated=updated)

        self.assertIn("<published>2020-01-02T00:00:00+00:00</published>", xml)
        self.assertIn("<updated>2026-07-30T02:00:00+00:00</updated>", xml)


if __name__ == "__main__":
    unittest.main()
