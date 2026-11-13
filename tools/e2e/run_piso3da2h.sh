#!/usr/bin/env bash
# E2E em navegador real do Piso 3D-A2-H (PEMFC/H₂ no EMS V2) com a política B04 do REPOSITÓRIO (b04-proposta-2,
# APROVADA pelo responsável no PR #23). Nenhuma aprovação simulada em nenhuma fase.
#
# Uso: tools/e2e/run_piso3da2h.sh <python COM Pyomo/HiGHS> <pasta de saída vazia> <python SEM solver>
#
# Fases (servidores Streamlit reais; nenhum serviço externo):
#   1. semente  — microrrede FICTÍCIA FV + eólica + bateria + PEMFC + PCC com declarações renováveis e PEMFC VAZIAS, e
#                 duas rodadas legadas gravadas nos contratos v1 (3D-A) e v2 (3D-A2-R);
#   2. bancada  — curva q(P) na bancada H₂ (PWL do modelo APROXIMADO, verificada MATEMATICAMENTE);
#   3. fluxo    — declarações preenchidas PELA INTERFACE → preflight normal → missão real (HiGHS) → rodada;
#   4. reabrir  — servidor NOVO (aplicação fechada e reaberta) com o python SEM solver e o motor e os modelos (renováveis
#                 e PEMFC) sabotados: rodada PEMFC e rodadas legadas reabertas; registro de chamadas VAZIO;
#   5. conferir — conferência QUANTITATIVA dos dados gravados (balanço, despacho, H₂, custos, aceitação), também sem
#                 solver e com os modelos sabotados.
set -euo pipefail
PY="$1"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"; PY_SEM="$3"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$RAIZ"
export NODE_PATH="${NODE_PATH:-/opt/node-tools/node_modules}"
PORTA="${PORTA:-8631}"; CAP="$OUT/capturas"; LOGM="$OUT/chamadas_ao_motor.log"; DADOS="$OUT/dados"
SEED="$OUT/seed_piso3da2h.json"
mkdir -p "$CAP"
source "$RAIZ/tools/e2e/servidor.sh"          # limpeza garantida do servidor e dos filhos, mesmo se uma fase falhar
servidor() { local py="$1" log="$2"; shift 2; e2e_servidor "$py" "$DADOS" "$PORTA" "$log" "$@"; }   # <python> <log> [VAR=valor…]
parar() { e2e_parar "$PORTA"; }
fase() { e2e_fase "$OUT/e2e_$1.log" node tools/e2e/e2e_piso3da2h.js "http://localhost:$PORTA" "$1" "$CAP" "$SEED"; }

echo "== 1. semente (python com solver: as rodadas legadas são executadas aqui)"
PYTHONDONTWRITEBYTECODE=1 "$PY" tools/e2e/seed_piso3da2h.py "$DADOS"
echo "== 2–3. bancada e fluxo completo (servidor COM solver; política B04 do repositório)"
servidor "$PY" "$OUT/servidor_fluxo.log"
fase bancada
fase fluxo
parar
echo "== 4. reabrir (aplicação reiniciada; python SEM solver; motor e modelos sabotados)"
"$PY_SEM" -c "import importlib.util as u; assert u.find_spec('pyomo') is None and u.find_spec('highspy') is None"
rm -f "$LOGM"
servidor "$PY_SEM" "$OUT/servidor_reabrir.log" PYTHONPATH="$RAIZ/tools/e2e/sabotage_v2" SEEDS2_E2E_ENGINE_LOG="$LOGM" \
    SEEDS2_E2E_ROOT="$RAIZ"
fase reabrir
parar
echo "== 5. conferência quantitativa dos dados gravados (sem solver, modelos sabotados)"
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$RAIZ/tools/e2e/sabotage_v2" SEEDS2_E2E_ENGINE_LOG="$LOGM" SEEDS2_E2E_ROOT="$RAIZ" \
    "$PY_SEM" tools/e2e/check_piso3da2h_rodada.py "$DADOS" "$SEED" | tee "$OUT/check_rodada.log"
[ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
if [ -s "$LOGM" ]; then echo "FALHA: motor ou modelo chamado na reabertura/conferência:"; cat "$LOGM"; exit 1; fi
echo "registro de chamadas ao motor/modelos na reabertura e na conferência: VAZIO"
grep -h "CONCLUÍDO" "$OUT"/e2e_*.log "$OUT/check_rodada.log"
