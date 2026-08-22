"""A published artifact is replaced whole or not at all.

Feeds and caches are written straight to the paths the scheduled job commits,
and that job stages feeds/ and cache/ whether or not generation succeeded. So a
write interrupted halfway - by the per-generator timeout, by the job timeout,
by a crash - used to commit a truncated file over a good one.
"""

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


if __name__ == "__main__":
    unittest.main()
