import os
from fastapi import FastAPI

def _env_list(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]
NODE_ID = os.getenv("NODE_ID", "node0")
PEERS = _env_list("PEERS")

app = FastAPI(title="DS Ledger Storage Node", version="0.1.0")

@app.get("/health")
def health():
    return {
        "ok": True,
        "node_id": NODE_ID,
        "peers": PEERS,
        "peers_count": len(PEERS),
    }
