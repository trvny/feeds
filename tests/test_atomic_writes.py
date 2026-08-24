"""A published artifact is replaced whole or not at all.

Feeds and caches are written straight to the paths the scheduled job commits,
and that job stages feeds/ and cache/ whether or not generation succeeded. So a
write interrupted halfway - by the per-generator timeout, by the job timeout,
by a crash - used to commit a truncated file over a good one.
"""

import ast
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

from utils import write_atomically  # noqa: E402


class WriteAtomicallyTests(unittest.TestCase):
    def test_replaces_the_previous_file(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "feed.xml"
            target.write_text("old", encoding="utf-8")
            write_atomically(target, lambda p: p.write_text("new", encoding="utf-8"))
            self.assertEqual(target.read_text(encoding="utf-8"), "new")

    def test_a_failed_write_leaves_the_previous_file_untouched(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "feed.xml"
            target.write_text("last good", encoding="utf-8")

            def half_a_write(path):
                path.write_text("truncat", encoding="utf-8")
                raise RuntimeError("killed mid-write")

            with self.assertRaises(RuntimeError):
                write_atomically(target, half_a_write)
            self.assertEqual(target.read_text(encoding="utf-8"), "last good")

    def test_a_failed_write_leaves_no_temp_file_behind(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "feed.xml"
            target.write_text("last good", encoding="utf-8")

            def explodes(path):
                path.write_text("partial", encoding="utf-8")
                raise RuntimeError("killed mid-write")

            with self.assertRaises(RuntimeError):
                write_atomically(target, explodes)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["feed.xml"])

    def test_writes_a_file_that_did_not_exist_yet(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "feed.xml"
            write_atomically(target, lambda p: p.write_text("first", encoding="utf-8"))
            self.assertEqual(target.read_text(encoding="utf-8"), "first")

    def test_the_temp_file_is_a_sibling(self):
        """os.replace is only atomic within one filesystem, so it must not
        borrow the system temp directory, which is frequently another volume."""
        seen = []
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "feed.xml"
            write_atomically(
                target,
                lambda p: (seen.append(p), p.write_text("x", encoding="utf-8"))[1],
            )
        self.assertEqual(seen[0].parent, target.parent)


class GeneratorWriterPolicyTests(unittest.TestCase):
    def test_generators_use_the_shared_writer(self):
        generators_dir = Path(__file__).resolve().parents[1] / "feed_generators"
        offenders = []
        for path in sorted(generators_dir.glob("*.py")):
            if path.name == "utils.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"atom_file", "rss_file"}
                ):
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(
            offenders,
            [],
            "Use utils.save_atom_feed instead of direct feedgen file writers",
        )


class FeedgenIsPatchedTests(unittest.TestCase):
    """Direct feedgen file writes stay atomic as defense in depth."""

    def feed(self):
        from feedgen.feed import FeedGenerator

        fg = FeedGenerator()
        fg.id("https://example.test/")
        fg.title("t")
        fg.link(href="https://example.test/", rel="alternate")
        fg.description("d")
        return fg

    def test_a_direct_atom_file_call_goes_through_the_helper(self):
        from feedgen.feed import FeedGenerator

        self.assertTrue(getattr(FeedGenerator.atom_file, "_feedseek_atomic", False))
        self.assertTrue(getattr(FeedGenerator.rss_file, "_feedseek_atomic", False))

    def test_a_direct_call_leaves_the_previous_feed_on_failure(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "feed_x.xml"
            target.write_text("last good", encoding="utf-8")
            fg = self.feed()
            # An unwritable directory name is the cheapest way to make the
            # underlying write fail after the wrapper has taken over.
            with self.assertRaises(Exception):
                fg.atom_file(str(Path(tmp) / "nope" / "feed_x.xml"), pretty=True)
            self.assertEqual(target.read_text(encoding="utf-8"), "last good")

    def test_a_direct_call_still_writes_the_feed(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "feed_x.xml"
            self.feed().atom_file(str(target), pretty=True)
            self.assertIn("<feed", target.read_text(encoding="utf-8"))
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["feed_x.xml"])


if __name__ == "__main__":
    unittest.main()
