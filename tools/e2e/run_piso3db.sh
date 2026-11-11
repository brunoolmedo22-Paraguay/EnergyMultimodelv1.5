#!/usr/bin/env bash
# E2E em navegador real do Piso 3D-B0/B1 — Partitura (motor gráfico Trama) na aplicação Streamlit REAL.
#
# Uso: tools/e2e/run_piso3db.sh <python COM Pyomo/HiGHS> <pasta de saída vazia>
#
# Fases (servidor Streamlit real; nenhum serviço externo):
#   1. semente  — microrrede FICTÍCIA FV + eólica + bateria + PEMFC + PCC com UMA missão V2 real (HiGHS), uma microrrede
#                 V1.6 com rodada concluída e o cenário V2 arquivado no Arquivo Científico;
#   2. consulta — servidor NOVO com o solver BLOQUEADO e o motor e os modelos físicos sabotados (tools/e2e/sabotage_v2):
#                 a Partitura é aberta, percorrida e reaberta; o registro de chamadas ao motor/modelos deve ficar VAZIO.
set -euo pipefail
PY="$1"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$RAIZ"
export NODE_PATH="${NODE_PATH:-/opt/node-tools/node_modules}"
PORTA="${PORTA:-8641}"; CAP="$OUT/capturas"; LOGM="$OUT/chamadas_ao_motor.log"; DADOS="$OUT/dados"; SEED="$OUT/seed_piso3db.json"
PID=""
trap '[ -n "$PID" ] && kill "$PID" 2>/dev/null || true' EXIT
echo "== 1. semente (python com solver: a missão V2 e a rodada V1.6 são executadas aqui)"
PYTHONDONTWRITEBYTECODE=1 "$PY" tools/e2e/seed_piso3db.py "$DADOS"
echo "== 2. consulta (servidor SEM solver; motor e modelos sabotados)"
rm -f "$LOGM"
if curl -sf "http://localhost:$PORTA/_stcore/health" >/dev/null 2>&1; then echo "porta $PORTA ocupada" >&2; exit 2; fi
env PYTHONDONTWRITEBYTECODE=1 SEEDS2_DATA_DIR="$DADOS" PYTHONPATH="$RAIZ/tools/e2e/sabotage_v2" SEEDS2_E2E_ENGINE_LOG="$LOGM" \
    SEEDS2_E2E_ROOT="$RAIZ" "$PY" -m streamlit run app.py --server.headless true --server.port "$PORTA" \
    --browser.gatherUsageStats false >"$OUT/servidor.log" 2>&1 &
PID=$!
for _ in $(seq 1 120); do curl -sf "http://localhost:$PORTA/_stcore/health" >/dev/null 2>&1 && break; sleep 1; done
node tools/e2e/e2e_piso3db_partitura.js "http://localhost:$PORTA" "$SEED" "$CAP" | tee "$OUT/e2e_partitura.log"
[ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
if [ -s "$LOGM" ]; then echo "FALHA: motor, solver ou modelo chamado na consulta:"; cat "$LOGM"; exit 1; fi
echo "registro de chamadas ao motor/solver/modelos na consulta: VAZIO"
grep -h "CONCLUÍDO" "$OUT/e2e_partitura.log"
