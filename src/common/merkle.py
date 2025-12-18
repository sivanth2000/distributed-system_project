from __future__ import annotations

from typing import Iterable

from src.common.hashing import sha256_bytes


def merkle_root_hex(leaves_hex: Iterable[str]) -> str:
    """
    Compute a Merkle root from an iterable of leaf hashes (hex strings).
    If there are 0 leaves, returns sha256("").
    If odd number at a level, duplicates the last element.
    """
    level = [h.lower() for h in leaves_hex if h]

    if not level:
        return sha256_bytes(b"")

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        nxt: list[str] = []
        for i in range(0, len(level), 2):
            left = level[i].encode("utf-8")
            right = level[i + 1].encode("utf-8")
            nxt.append(sha256_bytes(left + b"|" + right))
        level = nxt

    return level[0]
