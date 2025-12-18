A small distributed storage demo:
- Content-addressed object store (SHA-256 OIDs)
- Key→metadata index (versioned)
- Quorum replication (write + read with read-repair)
- Simple PoW ledger that commits metadata entries, with Merkle root per block
- Dockerized 3-node cluster + smoke test + GitHub Actions CI

## Quickstart (Docker, 3 nodes)

```bash
docker compose up --build -d
docker compose ps

curl -s http://localhost:8001/health; echo
curl -s http://localhost:8002/health; echo
curl -s http://localhost:8003/health; echo
Object store demo
bash
Copy code
OID=$(printf "hello object" | curl -s -X POST --data-binary @- http://localhost:8001/objects | python3 -c "import sys,json; print(json.load(sys.stdin)['oid'])")
echo "OID=$OID"
curl -s http://localhost:8001/objects/$OID; echo
Quorum key write/read demo
bash
Copy code
curl -s -X PUT --data-binary "replicated value v1" http://localhost:8001/quorum/keys/qkey1; echo

# Read from other nodes (body is the stored value)
curl -i http://localhost:8002/quorum/keys/qkey1
curl -i http://localhost:8003/quorum/keys/qkey1
Ledger demo
bash
Copy code
curl -s -X POST http://localhost:8001/ledger/mine \
  -H "Content-Type: application/json" \
  -d '{"keys":["qkey1"],"difficulty_prefix":"000"}'; echo

curl -s http://localhost:8001/ledger/verify; echo
curl -s http://localhost:8001/ledger | python3 -c "import sys,json; j=json.load(sys.stdin); print('blocks', j['blocks']); print('last_hash', j['chain'][-1]['hash'])"
Smoke test
bash
Copy code
./scripts/smoke.sh
Failure demo (optional)
This shows quorum write succeeds even if one node is down (because W=2).

bash
Copy code
docker compose up --build -d
docker compose stop node3

curl -s -X PUT --data-binary "value with node3 down" http://localhost:8001/quorum/keys/failkey1; echo
curl -s http://localhost:8002/quorum/keys/failkey1; echo

docker compose start node3
curl -s http://localhost:8003/quorum/keys/failkey1; echo
Developer notes
FastAPI docs: http://localhost:8001/docs

Data persistence: each node stores data under ./data/node{1,2,3} via Docker volumes.
EOF

python
Copy code

---

## 4) Add a short REPORT.md (for grading)
```bash
cat > REPORT.md <<'EOF'
# DS Ledger Storage — Report

## Overview
This project implements a small distributed storage system with:
1) a content-addressed object store (SHA-256),
2) a versioned key→metadata index,
3) quorum-based replication (write + read + read-repair),
4) a simple proof-of-work ledger that commits metadata entries into blocks with a Merkle root.

A Docker Compose cluster runs 3 nodes locally.

## Architecture
Each node runs a FastAPI server with local persistence:
- objects: `/app/data/objects/<oid>`
- key metadata: `/app/data/kv.json`
- ledger: stored locally per node under `/app/data` (implementation file controls exact location)

Nodes are configured with:
- `NODE_ID` (e.g., node1)
- `PEERS` (comma-separated peer base URLs)

## Data model
### Object (content-addressed)
- OID = SHA-256 hex digest of the raw bytes.
- Storing the same bytes twice returns the same OID.

### Key metadata (versioned)
Each key maps to metadata:
- `key`, `oid`, `size`, `version`, `ts`, `writer`
Version increments on every update.

## Replication: quorum write/read
### Quorum write
- Client writes a value for a key to `/quorum/keys/{key}`.
- The node stores the object locally and replicates the exact metadata + object to peers.
- Success requires meeting a write quorum (W=2 by default).
- The response includes acks and any failed peers.

### Quorum read + read-repair
- Client reads from `/quorum/keys/{key}`.
- The node queries peers, picks the newest metadata (highest version / freshest), fetches the object bytes, and returns them.
- If any replicas are behind, the node repairs them by pushing the newest metadata/object.

## Ledger
The ledger commits a set of key metadata entries into a mined block:
- Each block includes `prev_hash`, `entries`, `merkle_root`, `nonce`, and `hash`.
- PoW condition: block hash must start with a configured prefix (default “000”).
- `/ledger/verify` validates chain linkage, Merkle roots, and PoW.

## How to run
```bash
docker compose up --build -d
./scripts/smoke.sh
Demo checklist
GET /health on all 3 nodes

POST /objects then GET /objects/{oid}

PUT /quorum/keys/{key} then read from node2/node3

POST /ledger/mine then GET /ledger/verify

Failure demo: stop one node, write + read still works
EOF

yaml
Copy code

---

## 5) Quick sanity checks + run smoke
```bash
python -m py_compile $(git ls-files '*.py')
./scripts/smoke.sh
