from __future__ import annotations

from typing import Any

import requests

from src.node import kv, storage

DEFAULT_TIMEOUT = 2.0


def _get_meta(base: str, key: str, timeout: float) -> dict | None:
    try:
        r = requests.get(f"{base}/keys/{key}", timeout=timeout)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _get_object(base: str, oid: str, timeout: float) -> bytes | None:
    try:
        r = requests.get(f"{base}/objects/{oid}", timeout=timeout)
        if r.status_code != 200:
            return None
        return r.content
    except Exception:
        return None


def _put_meta_exact(base: str, key: str, meta: dict, timeout: float) -> bool:
    try:
        r = requests.put(f"{base}/internal/keys/{key}", json=meta, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _rank(m: dict) -> tuple[int, float]:
    return (int(m.get("version", 0)), float(m.get("ts", 0.0)))


def quorum_fetch(
    *,
    key: str,
    peers: list[str],
    r: int | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    repair: bool = True,
) -> dict[str, Any]:
    """
    Quorum read:
      - use local meta + peer meta
      - pick winner by highest (version, ts)
      - fetch object bytes from local or any peer that has winner oid
      - optional read-repair: push winner meta to stale replicas (and local)
    Returns dict with: ok, winner, data (bytes), repaired (list), etc.
    """
    sources: list[tuple[str, dict]] = []

    local_meta = kv.get_meta(key)
    if isinstance(local_meta, dict) and "oid" in local_meta:
        sources.append(("local", local_meta))

    for p in peers:
        m = _get_meta(p, key, timeout=timeout)
        if isinstance(m, dict) and "oid" in m:
            sources.append((p, m))

    total = 1 + len(peers)
    if r is None:
        r = total // 2 + 1

    if len(sources) < r:
        return {"ok": False, "detail": "not_enough_metadata", "r": int(r), "got": len(sources), "total": total}

    winner_from, winner_meta = sorted(sources, key=lambda sm: _rank(sm[1]), reverse=True)[0]
    winner_oid = winner_meta["oid"]

    data: bytes | None = None
    # Try local first if it matches
    if local_meta is not None and local_meta.get("oid") == winner_oid:
        try:
            data = storage.get_bytes(winner_oid)
        except FileNotFoundError:
            data = None

    # Try peers that claim the winner oid
    if data is None:
        for src, m in sources:
            if src == "local":
                continue
            if m.get("oid") == winner_oid:
                data = _get_object(src, winner_oid, timeout=timeout)
                if data is not None:
                    break

    if data is None:
        return {"ok": False, "detail": "object_missing", "winner": winner_meta}

    repaired: list[str] = []
    if repair:
        # Repair peers that are stale
        for src, m in sources:
            if _rank(m) < _rank(winner_meta):
                if src == "local":
                    kv.set_meta_exact(winner_meta)
                    repaired.append("local")
                else:
                    if _put_meta_exact(src, key, winner_meta, timeout=timeout):
                        repaired.append(src)

        # Also repair local even if it wasn't in sources (missing)
        if local_meta is None:
            kv.set_meta_exact(winner_meta)
            repaired.append("local")

    return {
        "ok": True,
        "winner": winner_meta,
        "winner_from": winner_from,
        "bytes": len(data),
        "repaired": repaired,
        "data": data,
    }