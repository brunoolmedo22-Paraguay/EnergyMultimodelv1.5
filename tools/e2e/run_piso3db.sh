#!/usr/bin/env bash
# E2E em navegador real do Piso 3D-B (B0/B1/B3) — Partitura (motor gráfico Trama) na aplicação Streamlit REAL.
#
# Uso: tools/e2e/run_piso3db.sh <python COM Pyomo/HiGHS> <pasta de saída vazia>
#
# Fases (servidor Streamlit real; nenhum serviço externo):
#   1. semente  — microrrede FICTÍCIA FV + eólica + bateria + PEMFC + PCC com DUAS missões V2 reais (HiGHS), uma microrrede
#                 V1.6 com rodada concluída e o cenário V2 arquivado no Arquivo Científico;
#   2. consulta — servidor NOVO com o solver BLOQUEADO e o motor e os modelos físicos sabotados (tools/e2e/sabotage_v2):
#                 a Partitura é aberta, percorrida e reaberta; o registro de chamadas ao motor/modelos deve ficar VAZIO.
set -euo pipefail
PY="$1"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$RAIZ"
export NODE_PATH="${NODE_PATH:-/opt/node-tools/node_modules}"
PORTA="${PORTA:-8641}"; CAP="$OUT/capturas"; LOGM="$OUT/chamadas_ao_motor.log"; DADOS="$OUT/dados"; SEED="$OUT/seed_piso3db.json"
source "$RAIZ/tools/e2e/servidor.sh"          # limpeza garantida do servidor e dos filhos, mesmo se uma fase falhar
echo "== 1. semente (python com solver: a missão V2 e a rodada V1.6 são executadas aqui)"
PYTHONDONTWRITEBYTECODE=1 "$PY" tools/e2e/seed_piso3db.py "$DADOS"
echo "== 2. consulta (servidor SEM solver; motor e modelos sabotados)"
rm -f "$LOGM"
e2e_servidor "$PY" "$DADOS" "$PORTA" "$OUT/servidor.log" PYTHONPATH="$RAIZ/tools/e2e/sabotage_v2" \
    SEEDS2_E2E_ENGINE_LOG="$LOGM" SEEDS2_E2E_ROOT="$RAIZ"
e2e_fase "$OUT/e2e_partitura.log" node tools/e2e/e2e_piso3db_partitura.js "http://localhost:$PORTA" "$SEED" "$CAP"
echo "== 3. plataforma (3D-B2: navegação e páginas; mesmo servidor sem solver)"
e2e_fase "$OUT/e2e_plataforma.log" node tools/e2e/e2e_piso3db_plataforma.js "http://localhost:$PORTA" "$SEED" "$CAP"
e2e_parar "$PORTA"
if [ -s "$LOGM" ]; then echo "FALHA: motor, solver ou modelo chamado na consulta:"; cat "$LOGM"; exit 1; fi
echo "registro de chamadas ao motor/solver/modelos na consulta: VAZIO"
grep -h "CONCLUÍDO" "$OUT/e2e_partitura.log" "$OUT/e2e_plataforma.log"
