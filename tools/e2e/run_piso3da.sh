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

source "$RAIZ/tools/e2e/servidor.sh"          # limpeza garantida dos servidores e dos filhos, mesmo se uma fase falhar
fase() { e2e_fase "$OUT/e2e_$2.log" node tools/e2e/e2e_piso3da_v2.js "http://localhost:$1" "$2" "$CAP"; }

echo "== 1. semente"; "$PY_SOLVER" tools/e2e/seed_piso3da.py "$ORIG"

echo "== 2. operar (servidor com solver; kill -9 durante a missão longa)"
e2e_servidor "$PY_SOLVER" "$ORIG" "$PORTA_A" "$OUT/servidor_operar.log"
node tools/e2e/e2e_piso3da_v2.js "http://localhost:$PORTA_A" operar "$CAP" >"$OUT/e2e_operar.log" 2>&1 &
NODE=$!
for _ in $(seq 1 1200); do
  grep -q "KILL_NOW" "$OUT/e2e_operar.log" 2>/dev/null && break
  kill -0 "$NODE" 2>/dev/null || break
  sleep 0.5
done
if grep -q "KILL_NOW" "$OUT/e2e_operar.log"; then e2e_matar "$PORTA_A"; echo "servidor derrubado com kill -9 durante a rodada"; fi
wait "$NODE" || { tail -5 "$OUT/e2e_operar.log"; exit 1; }
e2e_parar "$PORTA_A"
grep -c "ok —" "$OUT/e2e_operar.log" | sed 's/^/operar: verificações ok = /'

echo "== 3. reinício (mesmo diretório, novo processo)"
e2e_servidor "$PY_SOLVER" "$ORIG" "$PORTA_B" "$OUT/servidor_reinicio.log"
fase "$PORTA_B" reinicio
echo "== 4. tablet"
fase "$PORTA_B" tablet
e2e_parar "$PORTA_B"

echo "== 5. importar (instalação limpa, SEM solver, motores sabotados)"
"$PY_SEM" -c "import importlib.util as u; assert u.find_spec('pyomo') is None and u.find_spec('highspy') is None"
rm -f "$LOGM"
e2e_servidor "$PY_SEM" "$DEST" "$PORTA_C" "$OUT/servidor_importar.log" PYTHONPATH="$RAIZ/tools/e2e/sabotage_v2" \
    SEEDS2_E2E_ENGINE_LOG="$LOGM" SEEDS2_E2E_ROOT="$RAIZ"
fase "$PORTA_C" importar
e2e_parar "$PORTA_C"
if [ -s "$LOGM" ]; then echo "FALHA: o motor foi chamado na instalação de consulta:"; cat "$LOGM"; exit 1; fi
echo "registro de chamadas ao motor na instalação de consulta: VAZIO"
grep -h "CONCLUÍDO" "$OUT"/e2e_*.log
echo "E2E 3D-A concluído — capturas em $CAP"
