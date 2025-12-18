from __future__ import annotations
import hashlib

def sha256_bytes(data: bytes) -> str:
    """Return lowercase hex SHA-256 of data."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
