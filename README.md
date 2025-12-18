
# Distributed Storage + Ledger (3-node cluster)

A small **distributed object + key-value storage system** with:
- **Content-addressed object store** (`/objects`, SHA-256 OIDs)
- **Key → metadata mapping** (`/keys/*`) with versioning
- **Quorum replication** for writes + reads (`/quorum/keys/*`) and **read-repair**
- A simple **blockchain-style ledger** that records key snapshots, with **Merkle root** + **Proof-of-Work** mining (`/ledger/*`)

This is an implementation-oriented distributed systems project (distributed storage + “small blockchain” style ledger), matching common DS project categories. :contentReference[oaicite:0]{index=0}

---

## Features

### Storage
- `POST /objects` stores raw bytes and returns an **OID** (SHA-256 of the bytes).
- `GET /objects/{oid}` returns the bytes.
- `GET /storage/stats` returns total object count and bytes.

### Key-value metadata
- Keys map to an object OID + metadata:
  - `version` auto-increments on updates
  - `ts` (timestamp)
  - `writer` (node id)

### Quorum replication (3 nodes)
- **Quorum write** replicates to multiple nodes and returns ACK summary.
- **Quorum read** reads from multiple nodes and returns the “best” value; can repair stale replicas.

### Ledger
- `POST /ledger/mine` mines a block that contains key entries (key → oid snapshot).
- Each block includes:
  - `prev_hash`
  - `merkle_root` of entries
  - `nonce`
  - PoW `hash` that must start with a difficulty prefix (default examples use `"000"`).
- `GET /ledger/verify` validates chain integrity + PoW + Merkle roots.

---

## Quickstart

### Run 3-node cluster (Docker)

```bash
docker compose up --build -d
docker compose ps
````

Health checks:

```bash
curl -s http://localhost:8001/health; echo
curl -s http://localhost:8002/health; echo
curl -s http://localhost:8003/health; echo
```

---

## API Examples

### 1) Object store (single node)

```bash
OID=$(printf "hello object" | curl -s -X POST --data-binary @- http://localhost:8001/objects \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['oid'])")

echo "OID=$OID"
curl -s "http://localhost:8001/objects/$OID"; echo
```

### 2) Quorum write + quorum read

Write via node1 (replicates to the cluster):

```bash
curl -s -X PUT --data-binary "replicated value v1" \
  "http://localhost:8001/quorum/keys/qkey1"; echo
```

Read from node2 and node3:

```bash
curl -i "http://localhost:8002/quorum/keys/qkey1"
curl -i "http://localhost:8003/quorum/keys/qkey1"
```

> The quorum read response includes headers like:
>
> * `x-ds-key`, `x-ds-oid`, `x-ds-version`, `x-ds-writer`

### 3) Mine a ledger block from keys

```bash
curl -s -X POST "http://localhost:8001/ledger/mine" \
  -H "Content-Type: application/json" \
  -d '{"keys":["qkey1"],"difficulty_prefix":"000"}'; echo
```

Verify chain:

```bash
curl -s "http://localhost:8001/ledger/verify"; echo
```

View chain summary:

```bash
curl -s "http://localhost:8001/ledger" \
 | python3 -c "import sys,json; j=json.load(sys.stdin); print('blocks', j['blocks']); print('last_hash', j['chain'][-1]['hash'])"
```

---

## Smoke Test (recommended)

Run the end-to-end smoke test:

```bash
./scripts/smoke.sh
```

It will:

1. Start the 3-node cluster
2. Wait for `/health`
3. Quorum write a fresh key
4. Quorum read it back from another node
5. Mine a ledger block containing that key
6. Verify the ledger

---

## Endpoints (high-level)

### Node health / stats

* `GET /health`
* `GET /storage/stats`

### Objects (content-addressed)

* `POST /objects`  (raw bytes → `{ "oid": "..." }`)
* `GET /objects/{oid}`

### Local key metadata (single node)

* `PUT /keys/{key}` (raw bytes)
* `GET /keys/{key}` (metadata JSON)
* `GET /keys` (list keys)

### Quorum key operations (cluster)

* `PUT /quorum/keys/{key}` (replicated write)
* `GET /quorum/keys/{key}` (quorum read, may trigger read-repair depending on config/implementation)

### Ledger

* `POST /ledger/mine` (JSON: `{ "keys": [...], "difficulty_prefix": "000" }`)
* `GET /ledger`
* `GET /ledger/verify`

---

## Data / Persistence

Docker mounts each node’s local data directory:

* `./data/node1` → `/app/data`
* `./data/node2` → `/app/data`
* `./data/node3` → `/app/data`

So data persists across container restarts unless you delete `./data/`.

---

## Troubleshooting

### Ports already in use

Stop the cluster and try again:

```bash
docker compose down
docker compose up --build -d
```

### Clean everything (including volumes/data)

```bash
docker compose down -v
rm -rf data/
```

---

## Repo Tips

* `.dockerignore` avoids sending local venv/data into Docker build context.
* `.gitignore` keeps `data/`, `.venv/`, logs, and backups out of git.
* GitHub Actions workflow runs `./scripts/smoke.sh` on push / PR (CI).
