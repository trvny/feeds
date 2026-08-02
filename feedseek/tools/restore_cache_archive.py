#!/usr/bin/env python3
"""Safely restore the Feedseek cache from a gzip-compressed tar archive."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
from pathlib import Path

MAX_MEMBERS = 10_000
MAX_TOTAL_SIZE = 128 * 1024 * 1024


class UnsafeArchiveError(ValueError):
    """Raised when an archive contains unsafe or unexpected members."""


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


def restore_cache_archive(archive: Path, destination: Path) -> Path:
    """Extract only regular files and directories rooted below cache/."""

    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    validated: list[tuple[tarfile.TarInfo, Path]] = []
    seen: set[tuple[str, ...]] = set()
    total_size = 0

    with tarfile.open(archive, mode="r:gz") as bundle:
        members = bundle.getmembers()
        if not members:
            raise UnsafeArchiveError("archive is empty")
        if len(members) > MAX_MEMBERS:
            raise UnsafeArchiveError("archive contains too many members")

        for member in members:
            parts = _safe_parts(member)
            if parts in seen:
                raise UnsafeArchiveError(f"duplicate member: {member.name!r}")
            seen.add(parts)

            if member.isdir():
                pass
            elif member.isfile():
                if member.size < 0:
                    raise UnsafeArchiveError(f"negative file size: {member.name!r}")
                total_size += member.size
                if total_size > MAX_TOTAL_SIZE:
                    raise UnsafeArchiveError("archive expands beyond the size limit")
            else:
                raise UnsafeArchiveError(
                    f"links and special files are forbidden: {member.name!r}"
                )

            target = root.joinpath(*parts)
            if os.path.commonpath((str(root), str(target.resolve(strict=False)))) != str(
                root
            ):
                raise UnsafeArchiveError(f"member escapes destination: {member.name!r}")
            validated.append((member, target))

        cache_dir = root / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        for member, target in validated:
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise UnsafeArchiveError(f"cannot read member: {member.name!r}")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)

    if cache_dir.is_symlink() or not cache_dir.is_dir():
        raise UnsafeArchiveError("cache root is not a real directory")
    return cache_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    try:
        restored = restore_cache_archive(args.archive, args.destination)
    except (OSError, tarfile.TarError, UnsafeArchiveError) as exc:
        print(f"Cache archive rejected: {exc}", file=sys.stderr)
        return 1

    print(f"Validated cache archive at {restored}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
