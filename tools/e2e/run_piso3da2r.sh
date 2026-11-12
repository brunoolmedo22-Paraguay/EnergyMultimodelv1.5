#!/usr/bin/env bash
# Roteiro REPRODUTÍVEL do E2E em navegador real do Piso 3D-A2-R (FV + eólica no motor V2 MILP–MPC).
#
# Uso:  tools/e2e/run_piso3da2r.sh <python COM Pyomo/HiGHS> <python SEM solver> <pasta de saída vazia>
#
# Fases (servidores Streamlit reais; nenhum serviço externo):
#   1. semente  — microrrede híbrida fictícia do catálogo (tools/e2e/seed_piso3da2r.py), dados sintéticos rotulados;
#   2. operar   — servidor COM solver: preflight, missão real, rodada, recarga, exportação do estudo;
#   3. reinicio — servidor NOVO sobre o mesmo diretório: rodada reaberta sem reotimizar nem reexecutar modelos;
#   4. tablet   — rodada em tablet;
#   5. importar — instalação LIMPA, SEM solver, com motores e modelos físicos sabotados (tools/e2e/sabotage_v2); o
#                 registro de chamadas ao motor/modelos tem de ficar VAZIO.
set -euo pipefail
PY_SOLVER="$1"; PY_SEM="$2"; OUT="$(mkdir -p "$3" && cd "$3" && pwd)"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RAIZ"
export NODE_PATH="${NODE_PATH:-/opt/node-tools/node_modules}"
ORIG="$OUT/origem"; DEST="$OUT/destino"; CAP="$OUT/capturas"; LOGM="$OUT/chamadas_ao_motor.log"
mkdir -p "$DEST" "$CAP"
PORTA_A="${PORTA_A:-8621}"; PORTA_B="${PORTA_B:-8622}"; PORTA_C="${PORTA_C:-8623}"

source "$RAIZ/tools/e2e/servidor.sh"          # limpeza garantida dos servidores e dos filhos, mesmo se uma fase falhar
fase() { e2e_fase "$OUT/e2e_$2.log" node tools/e2e/e2e_piso3da2r.js "http://localhost:$1" "$2" "$CAP"; }

echo "== 1. semente"; PYTHONDONTWRITEBYTECODE=1 "$PY_SOLVER" tools/e2e/seed_piso3da2r.py "$ORIG"
echo "== 2. operar"
e2e_servidor "$PY_SOLVER" "$ORIG" "$PORTA_A" "$OUT/servidor_operar.log"
fase "$PORTA_A" operar
e2e_parar "$PORTA_A"
echo "== 3. reinício (mesmo diretório, novo processo)"
e2e_servidor "$PY_SOLVER" "$ORIG" "$PORTA_B" "$OUT/servidor_reinicio.log"
fase "$PORTA_B" reinicio
echo "== 4. tablet"
fase "$PORTA_B" tablet
e2e_parar "$PORTA_B"
echo "== 5. importar (instalação limpa, SEM solver, motores e modelos sabotados)"
"$PY_SEM" -c "import importlib.util as u; assert u.find_spec('pyomo') is None and u.find_spec('highspy') is None"
rm -f "$LOGM"
e2e_servidor "$PY_SEM" "$DEST" "$PORTA_C" "$OUT/servidor_importar.log" PYTHONPATH="$RAIZ/tools/e2e/sabotage_v2" \
    SEEDS2_E2E_ENGINE_LOG="$LOGM" SEEDS2_E2E_ROOT="$RAIZ"
fase "$PORTA_C" importar
e2e_parar "$PORTA_C"
if [ -s "$LOGM" ]; then echo "FALHA: motor ou modelo físico chamado na instalação de consulta:"; cat "$LOGM"; exit 1; fi
echo "registro de chamadas ao motor/modelos na instalação de consulta: VAZIO"
grep -h "CONCLUÍDO" "$OUT"/e2e_*.log
echo "E2E 3D-A2-R concluído — capturas em $CAP"
