#!/usr/bin/env python3
"""Build a classic multi-image favicon.ico from the existing PNG icons."""

from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / "assets" / "icons"
OUTPUT = ROOT / "feedseek" / "public" / "favicon.ico"
SOURCES = [
    (16, ICONS / "favicon-16x16.png"),
    (32, ICONS / "favicon-32x32.png"),
    (96, ICONS / "favicon-96x96.png"),
]


def main() -> None:
    images = [(size, path.read_bytes()) for size, path in SOURCES]
    header_size = 6 + 16 * len(images)
    offset = header_size
    entries: list[bytes] = []
    payloads: list[bytes] = []

    for size, payload in images:
        dimension = 0 if size >= 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        payloads.append(payload)
        offset += len(payload)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(
        struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(payloads)
    )
    print(f"Built {OUTPUT} with sizes: {', '.join(str(size) for size, _ in images)}")


if __name__ == "__main__":
    main()
