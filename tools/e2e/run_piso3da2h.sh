#!/usr/bin/env bash
# E2E em navegador real do Piso 3D-A2-H (PEMFC/H₂ no EMS V2).
#
# Uso: tools/e2e/run_piso3da2h.sh <python COM Pyomo/HiGHS> <pasta de saída vazia> [python SEM solver]
#
# Fases (servidores Streamlit reais; nenhum serviço externo):
#   1. bloqueio — política B04 do REPOSITÓRIO (pendente): execução bloqueada e explicada; curva q(P) na bancada H₂;
#   2. fluxo    — APROVAÇÃO B04 SIMULADA só no servidor de teste (tools/e2e/aprovacao_b04_simulada): declarações PEMFC
#                 preenchidas PELA INTERFACE → preflight → missão real (HiGHS) → rodada com aceitação separada;
#   3. reabrir  — servidor NOVO sobre o mesmo diretório, com o python SEM solver (se informado), aprovação simulada e
#                 motor + modelos PEMFC sabotados: a rodada é reaberta pela interface; o registro de chamadas ao
#                 motor/modelos tem de ficar VAZIO.
set -euo pipefail
PY="$1"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"; PY_SEM="${3:-$1}"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$RAIZ"
export NODE_PATH="${NODE_PATH:-/opt/node-tools/node_modules}"
PORTA="${PORTA:-8631}"; CAP="$OUT/capturas"; LOGM="$OUT/chamadas_ao_motor.log"; LOGA="$OUT/aprovacao_simulada.log"
mkdir -p "$CAP"
PID=""
trap '[ -n "$PID" ] && kill "$PID" 2>/dev/null || true' EXIT
livre() { ! curl -sf "http://localhost:$PORTA/_stcore/health" >/dev/null 2>&1; }
servidor() {   # <python> <dados> <log> [VAR=valor…]
  local py="$1" dados="$2" log="$3"; shift 3
  livre || { echo "porta $PORTA ocupada (servidor antigo?)" >&2; exit 2; }
  env PYTHONDONTWRITEBYTECODE=1 SEEDS2_DATA_DIR="$dados" "$@" "$py" -m streamlit run app.py --server.headless true \
      --server.port "$PORTA" --browser.gatherUsageStats false >"$log" 2>&1 &
  PID=$!
  for _ in $(seq 1 120); do curl -sf "http://localhost:$PORTA/_stcore/health" >/dev/null 2>&1 && return 0; sleep 1; done
  echo "servidor não respondeu" >&2; exit 1
}
parar() { kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; PID=""; sleep 1; }

echo "== 1. bloqueio (política B04 do repositório: pendente)"
PYTHONDONTWRITEBYTECODE=1 "$PY" tools/e2e/seed_piso3da2h.py "$OUT/dados_bloqueio" bloqueio
servidor "$PY" "$OUT/dados_bloqueio" "$OUT/servidor_bloqueio.log"
node tools/e2e/e2e_piso3da2h.js "http://localhost:$PORTA" bloqueio "$CAP" | tee "$OUT/e2e_bloqueio.log"
[ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
parar

echo "== 2. fluxo completo (APROVAÇÃO B04 SIMULADA no servidor de teste)"
PYTHONDONTWRITEBYTECODE=1 "$PY" tools/e2e/seed_piso3da2h.py "$OUT/dados_fluxo" fluxo
servidor "$PY" "$OUT/dados_fluxo" "$OUT/servidor_fluxo.log" PYTHONPATH="$RAIZ/tools/e2e/aprovacao_b04_simulada" \
    SEEDS2_E2E_APROVACAO_B04_SIMULADA=1 SEEDS2_E2E_APROVACAO_LOG="$LOGA" SEEDS2_E2E_ROOT="$RAIZ"
node tools/e2e/e2e_piso3da2h.js "http://localhost:$PORTA" fluxo "$CAP" | tee "$OUT/e2e_fluxo.log"
[ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
parar

echo "== 3. reabrir (servidor novo, python $(basename "$(dirname "$(dirname "$PY_SEM")")"), motor e modelos PEMFC sabotados)"
rm -f "$LOGM"
servidor "$PY_SEM" "$OUT/dados_fluxo" "$OUT/servidor_reabrir.log" PYTHONPATH="$RAIZ/tools/e2e/aprovacao_b04_simulada" \
    SEEDS2_E2E_APROVACAO_B04_SIMULADA=1 SEEDS2_E2E_APROVACAO_LOG="$LOGA" SEEDS2_E2E_ROOT="$RAIZ" SEEDS2_E2E_ENGINE_LOG="$LOGM"
node tools/e2e/e2e_piso3da2h.js "http://localhost:$PORTA" reabrir "$CAP" | tee "$OUT/e2e_reabrir.log"
[ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
parar
if [ -s "$LOGM" ]; then echo "FALHA: motor ou modelo chamado na reabertura:"; cat "$LOGM"; exit 1; fi
echo "registro de chamadas ao motor/modelos na reabertura: VAZIO"
echo "ativações da aprovação SIMULADA (só servidores de teste):"; cat "$LOGA"
grep -h "CONCLUÍDO" "$OUT"/e2e_*.log
