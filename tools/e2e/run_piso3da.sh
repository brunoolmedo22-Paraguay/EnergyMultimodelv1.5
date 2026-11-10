#!/usr/bin/env bash
# Roteiro REPRODUTÍVEL do E2E em navegador real do Piso 3D-A (motor V2 experimental MILP–MPC).
#
# Uso:  tools/e2e/run_piso3da.sh <python COM Pyomo/HiGHS> <python SEM solver> <pasta de saída vazia>
#
# Fases (servidores Streamlit reais; nenhum serviço externo):
#   1. semente  — duas microrredes fictícias do catálogo (tools/e2e/seed_piso3da.py), dados sintéticos de teste;
#   2. operar   — servidor COM solver; ao sinal KILL_NOW o servidor é derrubado com kill -9 DURANTE uma rodada V2;
#   3. reinicio — novo servidor sobre o mesmo diretório: rodada concluída reaberta sem reotimizar; rodada derrubada
#                 "Interrompida";
#   4. tablet   — rodada V2 em tablet;
#   5. importar — instalação LIMPA, SEM solver, com os motores sabotados (tools/e2e/sabotage_v2): o estudo exportado na
#                 fase 2 é importado e consultado; o registro de chamadas ao motor tem de ficar VAZIO.
set -euo pipefail
PY_SOLVER="$1"; PY_SEM="$2"; OUT="$(mkdir -p "$3" && cd "$3" && pwd)"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RAIZ"
export NODE_PATH="${NODE_PATH:-/opt/node-tools/node_modules}"
ORIG="$OUT/origem"; DEST="$OUT/destino"; CAP="$OUT/capturas"; LOGM="$OUT/chamadas_ao_motor.log"
mkdir -p "$DEST" "$CAP"
PORTA_A="${PORTA_A:-8611}"; PORTA_B="${PORTA_B:-8612}"; PORTA_C="${PORTA_C:-8613}"

servidor() {   # <python> <dados> <porta> <log> [VAR=valor…]
  local py="$1" dados="$2" porta="$3" log="$4"; shift 4
  env PYTHONDONTWRITEBYTECODE=1 SEEDS2_DATA_DIR="$dados" "$@" "$py" -m streamlit run app.py --server.headless true \
      --server.port "$porta" --browser.gatherUsageStats false >"$log" 2>&1 &
  echo $!
}
esperar() { for _ in $(seq 1 90); do curl -sf "http://localhost:$1/_stcore/health" >/dev/null 2>&1 && return 0; sleep 1; done; echo "servidor $1 não respondeu"; return 1; }

echo "== 1. semente"; "$PY_SOLVER" tools/e2e/seed_piso3da.py "$ORIG"

echo "== 2. operar (servidor com solver; kill -9 durante a missão longa)"
PID=$(servidor "$PY_SOLVER" "$ORIG" "$PORTA_A" "$OUT/servidor_operar.log"); esperar "$PORTA_A"
node tools/e2e/e2e_piso3da_v2.js "http://localhost:$PORTA_A" operar "$CAP" >"$OUT/e2e_operar.log" 2>&1 &
NODE=$!
for _ in $(seq 1 1200); do
  grep -q "KILL_NOW" "$OUT/e2e_operar.log" 2>/dev/null && break
  kill -0 "$NODE" 2>/dev/null || break
  sleep 0.5
done
if grep -q "KILL_NOW" "$OUT/e2e_operar.log"; then kill -9 "$PID"; echo "servidor $PID derrubado com kill -9 durante a rodada"; fi
wait "$NODE" || { tail -5 "$OUT/e2e_operar.log"; kill -9 "$PID" 2>/dev/null || true; exit 1; }
grep -c "ok —" "$OUT/e2e_operar.log" | sed 's/^/operar: verificações ok = /'

echo "== 3. reinício (mesmo diretório, novo processo)"
PID=$(servidor "$PY_SOLVER" "$ORIG" "$PORTA_B" "$OUT/servidor_reinicio.log"); esperar "$PORTA_B"
node tools/e2e/e2e_piso3da_v2.js "http://localhost:$PORTA_B" reinicio "$CAP" | tee "$OUT/e2e_reinicio.log" | tail -2
echo "== 4. tablet"
node tools/e2e/e2e_piso3da_v2.js "http://localhost:$PORTA_B" tablet "$CAP" | tee "$OUT/e2e_tablet.log" | tail -2
kill "$PID" 2>/dev/null || true

echo "== 5. importar (instalação limpa, SEM solver, motores sabotados)"
"$PY_SEM" -c "import importlib.util as u; assert u.find_spec('pyomo') is None and u.find_spec('highspy') is None"
rm -f "$LOGM"
PID=$(servidor "$PY_SEM" "$DEST" "$PORTA_C" "$OUT/servidor_importar.log" PYTHONPATH="$RAIZ/tools/e2e/sabotage_v2" \
      SEEDS2_E2E_ENGINE_LOG="$LOGM" SEEDS2_E2E_ROOT="$RAIZ"); esperar "$PORTA_C"
node tools/e2e/e2e_piso3da_v2.js "http://localhost:$PORTA_C" importar "$CAP" | tee "$OUT/e2e_importar.log" | tail -2
kill "$PID" 2>/dev/null || true
if [ -s "$LOGM" ]; then echo "FALHA: o motor foi chamado na instalação de consulta:"; cat "$LOGM"; exit 1; fi
echo "registro de chamadas ao motor na instalação de consulta: VAZIO"
grep -h "CONCLUÍDO" "$OUT"/e2e_*.log
echo "E2E 3D-A concluído — capturas em $CAP"
