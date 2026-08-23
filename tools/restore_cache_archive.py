#!/usr/bin/env python3
"""Safely restore the Feedseek cache from a gzip-compressed tar archive."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

MAX_MEMBERS = 10_000
MAX_TOTAL_SIZE = 128 * 1024 * 1024
MAX_DECOMPRESSED_SIZE = MAX_TOTAL_SIZE + (MAX_MEMBERS * 1024) + 1024


class UnsafeArchiveError(ValueError):
    """Raised when an archive contains unsafe or unexpected members."""


class _BoundedReader:
    """Expose at most a fixed number of decompressed bytes."""

    def __init__(self, source: BinaryIO, limit: int):
        self.source = source
        self.limit = limit
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        remaining = self.limit - self.bytes_read
        request_size = remaining + 1 if size < 0 or size > remaining else size
        data = self.source.read(request_size)
        self.bytes_read += len(data)
        if self.bytes_read > self.limit:
            raise UnsafeArchiveError("archive exceeds the decompressed size limit")
        return data


def _safe_parts(member: tarfile.TarInfo) -> tuple[str, ...]:
    raw_name = member.name.rstrip("/")
    if not raw_name or raw_name.startswith("/") or "\\" in raw_name:
        raise UnsafeArchiveError(f"unsafe member path: {member.name!r}")

    parts = tuple(raw_name.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise UnsafeArchiveError(f"unsafe member path: {member.name!r}")
    if parts[0] != "cache":
        raise UnsafeArchiveError(f"member outside cache/: {member.name!r}")
    return parts


def _safe_target(root: Path, parts: tuple[str, ...], member_name: str) -> Path:
    target = root.joinpath(*parts)
    if os.path.commonpath((str(root), str(target.resolve(strict=False)))) != str(root):
        raise UnsafeArchiveError(f"member escapes destination: {member_name!r}")
    return target


def restore_cache_archive(archive: Path, destination: Path) -> Path:
    """Stream regular cache files into an isolated destination."""

    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    cache_dir = root / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    seen: set[tuple[str, ...]] = set()
    total_size = 0
    member_count = 0

    with archive.open("rb") as raw_archive:
        with gzip.GzipFile(fileobj=raw_archive, mode="rb") as decompressed:
            bounded = _BoundedReader(decompressed, MAX_DECOMPRESSED_SIZE)
            with tarfile.open(fileobj=bounded, mode="r|") as bundle:
                for member in bundle:
                    member_count += 1
                    if member_count > MAX_MEMBERS:
                        raise UnsafeArchiveError("archive contains too many members")

                    parts = _safe_parts(member)
                    if parts in seen:
                        raise UnsafeArchiveError(f"duplicate member: {member.name!r}")
                    seen.add(parts)
                    target = _safe_target(root, parts, member.name)

                    if member.isdir():
                        if member.size != 0:
                            raise UnsafeArchiveError(
                                f"directory contains a payload: {member.name!r}"
                            )
                        target.mkdir(parents=True, exist_ok=True)
                        continue

                    if not member.isfile():
                        raise UnsafeArchiveError(
                            f"links and special files are forbidden: {member.name!r}"
                        )
                    if parts == ("cache",):
                        raise UnsafeArchiveError("cache root must be a directory")
                    if member.size < 0:
                        raise UnsafeArchiveError(
                            f"negative file size: {member.name!r}"
                        )

                    total_size += member.size
                    if total_size > MAX_TOTAL_SIZE:
                        raise UnsafeArchiveError(
                            "archive expands beyond the file-size limit"
                        )

                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = bundle.extractfile(member)
                    if source is None:
                        raise UnsafeArchiveError(
                            f"cannot read member: {member.name!r}"
                        )
                    with source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)

    if member_count == 0:
        raise UnsafeArchiveError("archive is empty")
    if cache_dir.is_symlink() or not cache_dir.is_dir():
        raise UnsafeArchiveError("cache root is not a real directory")
    return cache_dir


def _cache_timestamp(path: Path) -> datetime | None:
    """Return a cache file's normalized last_updated timestamp when usable."""
    try:
        with path.open(encoding="utf-8") as file:
            value = json.load(file).get("last_updated")
        if not isinstance(value, str):
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _replace_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".r2.tmp")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def merge_restored_cache(restored: Path, current: Path) -> tuple[int, int, int]:
    """Merge an R2 snapshot without replacing newer repository cache files.

    Existing JSON cache files are compared by their top-level ``last_updated``
    value. A restored file replaces the repository seed only when it is newer;
    files that exist only in either copy are preserved. Invalid restored JSON
    never overwrites an existing repository cache.
    """
    current.mkdir(parents=True, exist_ok=True)
    restored_used = 0
    current_kept = 0
    added = 0

    for source in sorted(path for path in restored.rglob("*") if path.is_file()):
        relative = source.relative_to(restored)
        target = current / relative

        if not target.exists():
            if source.suffix == ".json" and _cache_timestamp(source) is None:
                current_kept += 1
                continue
            _replace_file(source, target)
            added += 1
            continue

        if source.suffix != ".json":
            current_kept += 1
            continue

        restored_timestamp = _cache_timestamp(source)
        current_timestamp = _cache_timestamp(target)
        if restored_timestamp is None:
            current_kept += 1
            continue
        if current_timestamp is None or restored_timestamp > current_timestamp:
            _replace_file(source, target)
            restored_used += 1
        else:
            current_kept += 1

    return restored_used, current_kept, added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--merge-into",
        type=Path,
        help="merge the validated snapshot into an existing cache directory",
    )
    args = parser.parse_args()

    try:
        restored = restore_cache_archive(args.archive, args.destination)
        if args.merge_into is not None:
            restored_used, current_kept, added = merge_restored_cache(
                restored, args.merge_into
            )
    except (OSError, tarfile.TarError, UnsafeArchiveError) as exc:
        print(f"Cache archive rejected: {exc}", file=sys.stderr)
        return 1

    if args.merge_into is None:
        print(f"Validated cache archive at {restored}")
    else:
        print(
            "Merged R2 cache snapshot: "
            f"{restored_used} newer restored, {current_kept} current kept, "
            f"{added} restored-only added"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
