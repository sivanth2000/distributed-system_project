from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from threading import Lock

_LOCK = Lock()


def _data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "/app/data"))


def _kv_path() -> Path:
    return _data_dir() / "kv.json"


def _ensure_parent() -> None:
    _data_dir().mkdir(parents=True, exist_ok=True)


def _load_all() -> dict:
    _ensure_parent()
    p = _kv_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _atomic_write_json(obj: dict) -> None:
    _ensure_parent()
    p = _kv_path()
    tmp_fd, tmp_path = tempfile.mkstemp(prefix=".kv.", dir=str(_data_dir()))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, p)
    finally:
        if os.path.exists(tmp_path) and not p.exists():
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def get_meta(key: str) -> dict | None:
    with _LOCK:
        db = _load_all()
        return db.get(key)


def set_meta(key: str, oid: str, size: int, node_id: str) -> dict:
    """
    Local upsert metadata for key. Increments version (local-only).
    """
    now = time.time()
    with _LOCK:
        db = _load_all()
        prev = db.get(key)
        version = int(prev.get("version", 0)) + 1 if isinstance(prev, dict) else 1
        meta = {
            "key": key,
            "oid": oid,
            "size": int(size),
            "version": version,
            "ts": now,
            "writer": node_id,
        }
        db[key] = meta
        _atomic_write_json(db)
        return meta


def set_meta_exact(meta: dict) -> dict:
    """
    Write metadata exactly as provided (used for replication).
    Must include: key, oid, size, version, ts, writer.
    """
    for req in ("key", "oid", "size", "version", "ts", "writer"):
        if req not in meta:
            raise ValueError(f"meta missing field: {req}")
    key = str(meta["key"])
    with _LOCK:
        db = _load_all()
        db[key] = meta
        _atomic_write_json(db)
    return meta


def all_keys() -> list[str]:
    with _LOCK:
        db = _load_all()
        return sorted(db.keys())