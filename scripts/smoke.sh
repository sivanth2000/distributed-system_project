set -euo pipefail

cleanup () {
  docker compose down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_health () {
  local port="$1"
  for i in {1..80}; do
    if curl -sf "http://localhost:${port}/health" >/dev/null; then
      return 0
    fi
    sleep 0.25
  done
  echo "ERROR: node on port ${port} did not become healthy"
  exit 1
}

echo "[smoke] clean start..."
docker compose down -v >/dev/null 2>&1 || true

echo "[smoke] building + starting cluster..."
docker compose up --build -d >/dev/null

echo "[smoke] waiting for health..."
wait_health 8001
wait_health 8002
wait_health 8003

KEY="smoke_$(date +%s)"
VAL="hello smoke $(date -Is)"

echo "[smoke] quorum write to node1: key=${KEY}"
curl -s -X PUT --data-binary "${VAL}" "http://localhost:8001/quorum/keys/${KEY}" > /tmp/smoke_put.json

echo "[smoke] quorum read from node2 and verify body..."
BODY="$(curl -sf "http://localhost:8002/quorum/keys/${KEY}")"
if [[ "${BODY}" != "${VAL}" ]]; then
  echo "ERROR: read mismatch"
  echo "expected: ${VAL}"
  echo "got:      ${BODY}"
  exit 1
fi

echo "[smoke] mine ledger block on node1..."
curl -s -X POST "http://localhost:8001/ledger/mine" \
  -H "Content-Type: application/json" \
  -d "{\"keys\":[\"${KEY}\"],\"difficulty_prefix\":\"000\"}" > /tmp/smoke_mine.json

echo "[smoke] verify ledger..."
python3 - <<'PY'
import json, urllib.request
j = json.loads(urllib.request.urlopen("http://localhost:8001/ledger/verify").read())
assert j.get("ok") is True, j
print("[smoke] ledger OK, blocks =", j.get("blocks"))
PY

echo "[smoke] ✅ SMOKE_OK"
