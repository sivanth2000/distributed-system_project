from __future__ import annotations

from typing import Any

import requests

from src.node import storage, kv

DEFAULT_TIMEOUT = 2.0


def _post_object(peer_base: str, data: bytes, timeout: float) -> str | None:
    try:
        r = requests.post(f"{peer_base}/objects", data=data, timeout=timeout)
        if r.status_code != 200:
            return None
        j = r.json()
        return j.get("oid")
    except Exception:
        return None


def _put_meta_exact(peer_base: str, key: str, meta: dict, timeout: float) -> bool:
    try:
        r = requests.put(f"{peer_base}/internal/keys/{key}", json=meta, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def quorum_put(
    *,
    key: str,
    data: bytes,
    node_id: str,
    peers: list[str],
    w: int | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Quorum write:
      - store object locally
      - create local meta (version++, ts, writer)
      - replicate object+exact meta to peers
      - succeed if acks >= w
    """
    if not data:
        raise ValueError("empty data")

    oid = storage.put_bytes(data)
    meta = kv.set_meta(key=key, oid=oid, size=len(data), node_id=node_id)

    total_replicas = 1 + len(peers)
    if w is None:
        w = total_replicas // 2 + 1

    acks = 1  # local ack
    failed: list[dict[str, str]] = []

    for peer in peers:
        remote_oid = _post_object(peer, data, timeout=timeout)
        if remote_oid != oid:
            failed.append({"peer": peer, "stage": "object", "detail": f"oid_mismatch_or_fail ({remote_oid})"})
            continue

        ok_meta = _put_meta_exact(peer, key, meta, timeout=timeout)
        if not ok_meta:
            failed.append({"peer": peer, "stage": "meta", "detail": "fail"})
            continue

        acks += 1

    return {
        "ok": acks >= w,
        "w": int(w),
        "acks": int(acks),
        "replicas": int(total_replicas),
        "failed": failed,
        "meta": meta,
    }
