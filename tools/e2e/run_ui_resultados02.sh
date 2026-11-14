#!/usr/bin/env bash
# E2E do UI-RESULTADOS-02: exemplo C4 restaurado num diretório novo, servidor Streamlit (limpeza garantida por servidor.sh),
# roteiro no navegador real e conferência dos PDFs baixados.
# Uso: tools/e2e/run_ui_resultados02.sh <python> <pasta de saída> [pasta de capturas]
set -euo pipefail
PY="${1:-python}"; OUT="${2:-/tmp/e2e_ui_resultados02}"; CAPS="${3:-}"
AQUI="$(cd "$(dirname "$0")" && pwd)"; RAIZ="$(cd "$AQUI/../.." && pwd)"
source "$AQUI/servidor.sh"
rm -rf "$OUT"; mkdir -p "$OUT"; DADOS="$OUT/dados"; mkdir -p "$DADOS"
cd "$RAIZ"
PYTHONDONTWRITEBYTECODE=1 "$PY" "$AQUI/seed_ui_resultados02.py" "$DADOS" "$OUT/seed.json"
PORTA="${E2E_PORTA:-8771}"
e2e_servidor "$PY" "$DADOS" "$PORTA" "$OUT/servidor.log" SEEDS2_NAV_CLASSICA=0
e2e_fase "$OUT/e2e.log" node "$AQUI/e2e_ui_resultados02.js" "$PORTA" "$OUT/seed.json" "$OUT" ${CAPS:+"$CAPS"}
e2e_parar "$PORTA"
PYTHONDONTWRITEBYTECODE=1 "$PY" "$AQUI/check_ui_resultados02.py" "$DADOS" "$OUT/seed.json" "$OUT"
