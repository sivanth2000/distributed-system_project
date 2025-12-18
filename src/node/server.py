import os
from fastapi import FastAPI, Request, Response, HTTPException

from src.node import storage
from src.node import kv
from src.node import quorum


def _env_list(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


NODE_ID = os.getenv("NODE_ID", "node0")
PEERS = _env_list("PEERS")

app = FastAPI(title="DS Ledger Storage Node", version="0.5.0")


@app.get("/health")
def health():
    return {
        "ok": True,
        "node_id": NODE_ID,
        "peers": PEERS,
        "peers_count": len(PEERS),
    }


@app.get("/storage/stats")
def storage_stats():
    return storage.stats()


@app.post("/objects")
async def put_object(request: Request):
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="empty body")
    oid = storage.put_bytes(data)
    return {"oid": oid, "bytes": len(data)}


@app.get("/objects/{oid}")
def get_object(oid: str):
    try:
        data = storage.get_bytes(oid)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    return Response(content=data, media_type="application/octet-stream")


@app.get("/keys")
def list_keys():
    return {"keys": kv.all_keys()}


@app.get("/keys/{key}")
def get_key(key: str):
    meta = kv.get_meta(key)
    if meta is None:
        raise HTTPException(status_code=404, detail="not found")
    return meta


# Local-only write (no replication)
@app.put("/keys/{key}")
async def put_key(key: str, request: Request):
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="empty body")
    oid = storage.put_bytes(data)
    meta = kv.set_meta(key=key, oid=oid, size=len(data), node_id=NODE_ID)
    return meta


# Quorum write (replicates object + exact metadata to peers)
@app.put("/quorum/keys/{key}")
async def put_key_quorum(key: str, request: Request, w: int | None = None):
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="empty body")

    try:
        result = quorum.quorum_put(
            key=key,
            data=data,
            node_id=NODE_ID,
            peers=PEERS,
            w=w,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result["ok"]:
        raise HTTPException(status_code=503, detail=result)

    return result


# Internal endpoint: write metadata EXACTLY as provided (for replication).
@app.put("/internal/keys/{key}")
async def internal_put_key_exact(key: str, request: Request):
    meta = await request.json()
    if not isinstance(meta, dict):
        raise HTTPException(status_code=400, detail="meta must be a JSON object")
    meta["key"] = key  # force path to be source of truth
    try:
        out = kv.set_meta_exact(meta)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return out
