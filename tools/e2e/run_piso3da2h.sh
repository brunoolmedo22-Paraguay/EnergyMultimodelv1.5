#!/usr/bin/env bash
# E2E em navegador real do Piso 3D-A2-H. Uso: tools/e2e/run_piso3da2h.sh <python> <pasta de saída vazia>
set -euo pipefail
PY="$1"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$RAIZ"
export NODE_PATH="${NODE_PATH:-/opt/node-tools/node_modules}"
PORTA="${PORTA:-8631}"
if curl -sf "http://localhost:$PORTA/_stcore/health" >/dev/null 2>&1; then echo "porta $PORTA ocupada (servidor antigo?)" >&2; exit 2; fi
PYTHONDONTWRITEBYTECODE=1 "$PY" tools/e2e/seed_piso3da2h.py "$OUT/dados"
env PYTHONDONTWRITEBYTECODE=1 SEEDS2_DATA_DIR="$OUT/dados" "$PY" -m streamlit run app.py --server.headless true \
    --server.port "$PORTA" --browser.gatherUsageStats false >"$OUT/servidor.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 90); do curl -sf "http://localhost:$PORTA/_stcore/health" >/dev/null 2>&1 && break; sleep 1; done
node tools/e2e/e2e_piso3da2h.js "http://localhost:$PORTA" "$OUT/capturas" | tee "$OUT/e2e.log"; RC=${PIPESTATUS[0]}
exit "$RC"
