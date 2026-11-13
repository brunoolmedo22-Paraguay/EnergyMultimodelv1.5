#!/usr/bin/env bash
# E2E em navegador real do UI-FINISH-01 — catálogo e bancadas, etapa 04 (cartão de rodada), modal (overlay estável) e
# exportações (gráficos PNG/SVG claro/escuro; PDF, ZIP e Excel da rodada V2; estudo arquivado).
#
# Uso: tools/e2e/run_ui_finish.sh <python COM Pyomo/HiGHS> <pasta de saída vazia>
#
#   1. semente  — tools/e2e/seed_ui_finish.py (dados FICTÍCIOS rotulados; missões V2 reais com HiGHS);
#   2. preparo  — servidor COM solver: catálogo, bancadas, etapa 04, modal durante uma missão longa (cancelada no fim);
#   3. exportar — servidor NOVO com o solver BLOQUEADO e motor/modelos sabotados (tools/e2e/sabotage_v2): gráficos e
#                 documentos da rodada e do estudo arquivado; o registro de chamadas ao motor deve ficar VAZIO;
#   4. arquivos — tools/e2e/check_ui_finish.py confere os arquivos baixados contra os dados gravados.
set -euo pipefail
PY="$1"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$RAIZ"
export NODE_PATH="${NODE_PATH:-/opt/node-tools/node_modules}"
PORTA="${PORTA:-8651}"; DADOS="$OUT/dados"; SEED="$OUT/seed_ui_finish.json"; LOGM="$OUT/chamadas_ao_motor.log"
source "$RAIZ/tools/e2e/servidor.sh"
echo "== 1. semente"
PYTHONDONTWRITEBYTECODE=1 "$PY" tools/e2e/seed_ui_finish.py "$DADOS"
echo "== 2. preparo (servidor com solver)"
e2e_servidor "$PY" "$DADOS" "$PORTA" "$OUT/servidor_preparo.log" SEEDS2_NAV_CLASSICA=0
e2e_fase "$OUT/e2e_preparo.log" node tools/e2e/e2e_ui_finish.js "http://localhost:$PORTA" "$SEED" "$OUT" preparo
e2e_parar "$PORTA"
echo "== 3. exportar (servidor SEM solver; motor e modelos sabotados)"
rm -f "$LOGM"
e2e_servidor "$PY" "$DADOS" "$PORTA" "$OUT/servidor_exportar.log" PYTHONPATH="$RAIZ/tools/e2e/sabotage_v2" \
    SEEDS2_E2E_ENGINE_LOG="$LOGM" SEEDS2_E2E_ROOT="$RAIZ" SEEDS2_NAV_CLASSICA=0
e2e_fase "$OUT/e2e_exportar.log" node tools/e2e/e2e_ui_finish.js "http://localhost:$PORTA" "$SEED" "$OUT" exportar
e2e_parar "$PORTA"
if [ -s "$LOGM" ]; then echo "FALHA: motor, solver ou modelo chamado ao EXPORTAR:"; sort "$LOGM" | uniq -c; exit 1; fi
echo "registro de chamadas ao motor/solver/modelos nas exportações: VAZIO"
echo "== 4. arquivos baixados × dados gravados"
PYTHONDONTWRITEBYTECODE=1 "$PY" tools/e2e/check_ui_finish.py "$DADOS" "$SEED" "$OUT" | tee "$OUT/check_arquivos.log"
grep -h "CONCLUÍDO" "$OUT/e2e_preparo.log" "$OUT/e2e_exportar.log" "$OUT/check_arquivos.log"
