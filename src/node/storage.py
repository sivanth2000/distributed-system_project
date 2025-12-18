from __future__ import annotations

import os
import tempfile
from pathlib import Path

from src.common.hashing import sha256_bytes
def _data_dir() -> Path:
    # In Docker we use /app/data via volume; locally we can override with DATA_DIR=./data/local
    return Path(os.getenv("DATA_DIR", "/app/data"))


def _objects_dir() -> Path:
    return _data_dir() / "objects"
def ensure_dirs() -> None:
    _objects_dir().mkdir(parents=True, exist_ok=True)


def object_path(oid: str) -> Path:
    return _objects_dir() / oid
def put_bytes(data: bytes) -> str:
    """
    Store bytes under SHA-256 hex oid. Idempotent if already exists.
    Writes atomically (temp file then rename).
    """
    ensure_dirs()
    oid = sha256_bytes(data)
    final_path = object_path(oid)
    if final_path.exists():
        return oid

    fd, tmp_path = tempfile.mkstemp(prefix=f".{oid}.", dir=str(_objects_dir()))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)
    finally:
        # If something failed before rename, clean up temp file
        if os.path.exists(tmp_path) and not final_path.exists():
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return oid
def get_bytes(oid: str) -> bytes:
    p = object_path(oid)
    if not p.exists():
        raise FileNotFoundError(oid)
    return p.read_bytes()


def stats() -> dict:
    ensure_dirs()
    files = list(_objects_dir().glob("*"))
    total_bytes = 0
    count = 0
    for f in files:
        if f.is_file() and not f.name.startswith("."):
            count += 1
            total_bytes += f.stat().st_size
    return {"objects": count, "bytes": total_bytes}
