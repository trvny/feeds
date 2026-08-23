import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import restore_cache_archive as cache_archive  # noqa: E402

UnsafeArchiveError = cache_archive.UnsafeArchiveError
merge_restored_cache = cache_archive.merge_restored_cache
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

    def write_cache(self, directory, name, updated, marker):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(
            json.dumps({"last_updated": updated, "entries": [{"marker": marker}]}),
            encoding="utf-8",
        )

    def write_legacy_cache(self, directory, name, marker):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(
            json.dumps([{"marker": marker}]), encoding="utf-8"
        )

    def read_marker(self, directory, name):
        data = json.loads((directory / name).read_text(encoding="utf-8"))
        entries = data if isinstance(data, list) else data["entries"]
        return entries[0]["marker"]

    def test_restores_regular_cache_files(self):
        self.write_archive(
            [
                ("cache", "dir", ""),
                ("cache/source.json", "file", '{"ok": true}'),
            ]
        )

        restored = restore_cache_archive(self.archive, self.destination)

        self.assertEqual(restored, self.destination / "cache")
        self.assertEqual(
            (restored / "source.json").read_text(encoding="utf-8"), '{"ok": true}'
        )

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

    def test_merge_uses_newer_restored_cache(self):
        restored = self.root / "restored"
        current = self.root / "current"
        self.write_cache(restored, "source.json", "2026-08-23T12:00:00+00:00", "r2")
        self.write_cache(current, "source.json", "2026-08-23T10:00:00+00:00", "repo")

        stats = merge_restored_cache(restored, current)

        self.assertEqual(stats, (1, 0, 0))
        self.assertEqual(self.read_marker(current, "source.json"), "r2")

    def test_merge_keeps_newer_repository_cache(self):
        restored = self.root / "restored"
        current = self.root / "current"
        self.write_cache(restored, "source.json", "2026-08-23T10:00:00+00:00", "r2")
        self.write_cache(current, "source.json", "2026-08-23T12:00:00+00:00", "repo")

        stats = merge_restored_cache(restored, current)

        self.assertEqual(stats, (0, 1, 0))
        self.assertEqual(self.read_marker(current, "source.json"), "repo")

    def test_merge_adds_restored_only_cache(self):
        restored = self.root / "restored"
        current = self.root / "current"
        self.write_cache(restored, "new.json", "2026-08-23T12:00:00Z", "r2")

        stats = merge_restored_cache(restored, current)

        self.assertEqual(stats, (0, 0, 1))
        self.assertEqual(self.read_marker(current, "new.json"), "r2")

    def test_merge_does_not_replace_with_invalid_restored_json(self):
        restored = self.root / "restored"
        current = self.root / "current"
        restored.mkdir()
        (restored / "source.json").write_text("not json", encoding="utf-8")
        self.write_cache(current, "source.json", "2026-08-23T12:00:00+00:00", "repo")

        stats = merge_restored_cache(restored, current)

        self.assertEqual(stats, (0, 1, 0))
        self.assertEqual(self.read_marker(current, "source.json"), "repo")

    def test_merge_keeps_existing_legacy_list_cache(self):
        restored = self.root / "restored"
        current = self.root / "current"
        self.write_legacy_cache(restored, "legacy.json", "r2")
        self.write_legacy_cache(current, "legacy.json", "repo")

        stats = merge_restored_cache(restored, current)

        self.assertEqual(stats, (0, 1, 0))
        self.assertEqual(self.read_marker(current, "legacy.json"), "repo")

    def test_merge_adds_restored_only_legacy_list_cache(self):
        restored = self.root / "restored"
        current = self.root / "current"
        self.write_legacy_cache(restored, "legacy.json", "r2")

        stats = merge_restored_cache(restored, current)

        self.assertEqual(stats, (0, 0, 1))
        self.assertEqual(self.read_marker(current, "legacy.json"), "r2")


if __name__ == "__main__":
    unittest.main()
