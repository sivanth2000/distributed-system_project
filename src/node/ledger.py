from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from threading import Lock
from typing import Any

from src.common.hashing import sha256_bytes
from src.common.merkle import merkle_root_hex

_LOCK = Lock()

def _data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "/app/data"))

def _ledger_path() -> Path:
    return _data_dir() / "ledger.json"

def _ensure_parent() -> None:
    _data_dir().mkdir(parents=True, exist_ok=True)

@dataclass(frozen=True)
class Block:
    index: int
    ts: float
    prev_hash: str
    merkle_root: str
    entries: list[dict[str, Any]]
    nonce: int
    hash: str

def _block_hash_payload(index: int, ts: float, prev_hash: str, merkle_root: str, entries: list[dict[str, Any]], nonce: int) -> bytes:
    payload = {
        "index": index,
        "ts": ts,
        "prev_hash": prev_hash,
        "merkle_root": merkle_root,
        "entries": entries,
        "nonce": nonce,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

def compute_hash(index: int, ts: float, prev_hash: str, merkle_root: str, entries: list[dict[str, Any]], nonce: int) -> str:
    return sha256_bytes(_block_hash_payload(index, ts, prev_hash, merkle_root, entries, nonce))

def _atomic_write_json(obj: Any) -> None:
    _ensure_parent()
    p = _ledger_path()
    tmp_fd, tmp_path = tempfile.mkstemp(prefix=".ledger.", dir=str(_data_dir()))
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

def _load_chain() -> list[dict]:
    _ensure_parent()
    p = _ledger_path()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))

def _save_chain(chain: list[dict]) -> None:
    _atomic_write_json(chain)

def _make_genesis() -> Block:
    ts = time.time()
    entries: list[dict[str, Any]] = []
    merkle = merkle_root_hex([])
    prev = "0" * 64
    nonce = 0
    h = compute_hash(0, ts, prev, merkle, entries, nonce)
    return Block(index=0, ts=ts, prev_hash=prev, merkle_root=merkle, entries=entries, nonce=nonce, hash=h)

def ensure_genesis() -> None:
    with _LOCK:
        chain = _load_chain()
        if chain:
            return
        g = _make_genesis()
        _save_chain([asdict(g)])

def chain() -> list[dict]:
    ensure_genesis()
    with _LOCK:
        return _load_chain()

def last_block() -> dict:
    c = chain()
    return c[-1]

def append_block(entries: list[dict[str, Any]], difficulty_prefix: str = "000") -> dict:
    """
    Append a block with PoW: block hash must start with difficulty_prefix.
    Entries should be a list of metadata dicts (key, oid, size, version, ts, writer).
    """
    ensure_genesis()
    with _LOCK:
        c = _load_chain()
        prev = c[-1]
        index = int(prev["index"]) + 1
        ts = time.time()
        prev_hash = prev["hash"]

        leaves = []
        for e in entries:
            # leaf = sha256(canonical entry json)
            leaf = sha256_bytes(json.dumps(e, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            leaves.append(leaf)
        merkle = merkle_root_hex(leaves)

        nonce = 0
        while True:
            h = compute_hash(index, ts, prev_hash, merkle, entries, nonce)
            if h.startswith(difficulty_prefix):
                break
            nonce += 1

        b = Block(index=index, ts=ts, prev_hash=prev_hash, merkle_root=merkle, entries=entries, nonce=nonce, hash=h)
        c.append(asdict(b))
        _save_chain(c)
        return asdict(b)

def verify_chain(chain_data: list[dict], difficulty_prefix: str = "000") -> dict:
    """
    Verify linkage, PoW, and merkle root matches entries.
    """
    if not chain_data:
        return {"ok": False, "detail": "empty_chain"}

    for i, b in enumerate(chain_data):
        # Check required fields
        for req in ("index","ts","prev_hash","merkle_root","entries","nonce","hash"):
            if req not in b:
                return {"ok": False, "detail": f"missing_field:{req}", "at": i}

        # Check index ordering
        if int(b["index"]) != i:
            return {"ok": False, "detail": "bad_index", "at": i}

        # Check prev linkage (except genesis)
        if i == 0:
            if b["prev_hash"] != "0" * 64:
                return {"ok": False, "detail": "bad_genesis_prev", "at": i}
        else:
            if b["prev_hash"] != chain_data[i-1]["hash"]:
                return {"ok": False, "detail": "bad_prev_hash", "at": i}

        # Recompute merkle
        leaves = []
        for e in b["entries"]:
            leaf = sha256_bytes(json.dumps(e, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            leaves.append(leaf)
        merkle = merkle_root_hex(leaves)
        if merkle != b["merkle_root"]:
            return {"ok": False, "detail": "bad_merkle", "at": i}

        # Recompute hash + pow
        h = compute_hash(int(b["index"]), float(b["ts"]), b["prev_hash"], b["merkle_root"], b["entries"], int(b["nonce"]))
        if h != b["hash"]:
            return {"ok": False, "detail": "bad_hash", "at": i}
        if not h.startswith(difficulty_prefix):
            # allow genesis to skip pow requirement
            if i != 0:
                return {"ok": False, "detail": "bad_pow", "at": i}

    return {"ok": True, "blocks": len(chain_data)}
