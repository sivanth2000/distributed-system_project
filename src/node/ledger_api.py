from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.node import kv, ledger

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("")
def get_chain():
    c = ledger.chain()
    return {"blocks": len(c), "chain": c}


@router.get("/verify")
def verify_chain():
    c = ledger.chain()
    return ledger.verify_chain(c)


class MineReq(BaseModel):
    keys: list[str] = Field(default_factory=list)
    difficulty_prefix: str = "000"  # fast default; you can set to "0000" later


@router.post("/mine")
def mine_block(req: MineReq):
    if not req.keys:
        raise HTTPException(status_code=400, detail="keys required")

    missing: list[str] = []
    entries: list[dict] = []
    for k in req.keys:
        m = kv.get_meta(k)
        if not m:
            missing.append(k)
        else:
            entries.append(m)

    if missing:
        raise HTTPException(status_code=404, detail={"missing_keys": missing})

    b = ledger.append_block(entries=entries, difficulty_prefix=req.difficulty_prefix)
    return {"ok": True, "mined": b, "entries": len(entries), "difficulty_prefix": req.difficulty_prefix}
