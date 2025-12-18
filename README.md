## Quickstart

### Run 3-node cluster (Docker)
```bash
docker compose up --build -d
docker compose ps
Health checks
curl -s http://localhost:8001/health; echo
curl -s http://localhost:8002/health; echo
curl -s http://localhost:8003/health; echo
Store raw objects (content-addressed)
OID=$(printf "hello object" | curl -s -X POST --data-binary @- http://localhost:8001/objects | python3 -c "import sys,json; print(json.load(sys.stdin)['oid'])")
echo "OID=$OID"
curl -s http://localhost:8001/objects/$OID; echo
Quorum write + read (replicates metadata + object)
curl -s -X PUT --data-binary "replicated value v1" http://localhost:8001/quorum/keys/qkey1; echo
curl -i http://localhost:8002/quorum/keys/qkey1
curl -i http://localhost:8003/quorum/keys/qkey1
Mine + verify ledger (Merkle root + PoW)
curl -s -X POST http://localhost:8001/ledger/mine \
  -H "Content-Type: application/json" \
  -d '{"keys":["qkey1"],"difficulty_prefix":"000"}'; echo
curl -s http://localhost:8001/ledger/verify; echo
curl -s http://localhost:8001/ledger | python3 -c "import sys,json; j=json.load(sys.stdin); print('blocks', j['blocks']); print('last_hash', j['chain'][-1]['hash'])"
One-command smoke test
./scripts/smoke.sh


