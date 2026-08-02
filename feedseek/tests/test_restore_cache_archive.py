import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import restore_cache_archive as cache_archive  # noqa: E402

UnsafeArchiveError = cache_archive.UnsafeArchiveError
restore_cache_archive = cache_archive.restore_cache_archive


class RestoreCacheArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.archive = self.root / "cache.tar.gz"
        self.destination = self.root / "restore"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_archive(self, members):
        with tarfile.open(self.archive, mode="w:gz") as bundle:
            for name, kind, value in members:
                member = tarfile.TarInfo(name)
                if kind == "file":
                    payload = value.encode()
                    member.size = len(payload)
                    bundle.addfile(member, io.BytesIO(payload))
                elif kind == "dir":
                    member.type = tarfile.DIRTYPE
                    bundle.addfile(member)
                elif kind == "dir_payload":
                    payload = value.encode()
                    member.type = tarfile.DIRTYPE
                    member.size = len(payload)
                    bundle.addfile(member, io.BytesIO(payload))
                elif kind == "symlink":
                    member.type = tarfile.SYMTYPE
                    member.linkname = value
                    bundle.addfile(member)
                elif kind == "hardlink":
                    member.type = tarfile.LNKTYPE
                    member.linkname = value
                    bundle.addfile(member)
                else:
                    raise AssertionError(f"unknown test member kind: {kind}")

    def write_pax_archive(self, metadata_size):
        with tarfile.open(
            self.archive,
            mode="w:gz",
            format=tarfile.PAX_FORMAT,
            pax_headers={"comment": "x" * metadata_size},
        ) as bundle:
            member = tarfile.TarInfo("cache")
            member.type = tarfile.DIRTYPE
            bundle.addfile(member)

    def test_restores_regular_cache_files(self):
        self.write_archive(
            [
                ("cache", "dir", ""),
                ("cache/source.json", "file", '{"ok": true}'),
            ]
        )

        restored = restore_cache_archive(self.archive, self.destination)

        self.assertEqual(restored, self.destination / "cache")
        self.assertEqual((restored / "source.json").read_text(), '{"ok": true}')

    def test_rejects_cache_root_symlink(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.write_archive([("cache", "symlink", str(outside))])

        with self.assertRaises(UnsafeArchiveError):
            restore_cache_archive(self.archive, self.destination)

    def test_rejects_nested_links(self):
        self.write_archive(
            [
                ("cache", "dir", ""),
                ("cache/link", "hardlink", "cache/source.json"),
            ]
        )

        with self.assertRaises(UnsafeArchiveError):
            restore_cache_archive(self.archive, self.destination)

    def test_rejects_parent_traversal(self):
        self.write_archive([("cache/../outside", "file", "nope")])

        with self.assertRaises(UnsafeArchiveError):
            restore_cache_archive(self.archive, self.destination)

    def test_rejects_members_outside_cache(self):
        self.write_archive([("outside/source.json", "file", "nope")])

        with self.assertRaises(UnsafeArchiveError):
            restore_cache_archive(self.archive, self.destination)

    def test_stops_when_member_cap_is_exceeded(self):
        self.write_archive(
            [
                ("cache", "dir", ""),
                ("cache/one", "dir", ""),
                ("cache/two", "dir", ""),
            ]
        )

        with patch.object(cache_archive, "MAX_MEMBERS", 2):
            with self.assertRaisesRegex(UnsafeArchiveError, "too many members"):
                restore_cache_archive(self.archive, self.destination)

    def test_rejects_directory_payload(self):
        self.write_archive([("cache", "dir_payload", "unexpected payload")])

        with self.assertRaisesRegex(UnsafeArchiveError, "contains a payload"):
            restore_cache_archive(self.archive, self.destination)

    def test_rejects_oversized_pax_metadata(self):
        self.write_pax_archive(metadata_size=8192)

        with patch.object(cache_archive, "MAX_DECOMPRESSED_SIZE", 4096):
            with self.assertRaisesRegex(UnsafeArchiveError, "decompressed size"):
                restore_cache_archive(self.archive, self.destination)


if __name__ == "__main__":
    unittest.main()
