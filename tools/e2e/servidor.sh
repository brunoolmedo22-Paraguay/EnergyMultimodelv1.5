# shellcheck shell=bash
# Biblioteca dos roteiros E2E (run_piso3d*.sh): servidores Streamlit com LIMPEZA GARANTIDA.
#
#   e2e_servidor <python> <dados> <porta> <log> [VAR=valor…]
#       exige a porta LIVRE (um servidor que sobrou de outra execução faria o roteiro operar sobre o diretório errado),
#       inicia o servidor num GRUPO DE PROCESSOS próprio, regista-o e espera responder; se não responder, falha.
#   e2e_parar <porta>   encerra o servidor dessa porta e TODOS os seus processos filhos (TERM no grupo, depois KILL) e
#                       espera a porta fechar.
#   e2e_matar <porta>   kill -9 imediato do grupo (simulação de queda do servidor durante uma rodada).
#   e2e_fase <log> <comando…>   executa uma fase (node …), copia a saída para <log> e FALHA o roteiro se a fase falhar.
#
# Ao carregar, instala uma armadilha: em QUALQUER saída do roteiro (sucesso, falha de uma fase com `set -e`, Ctrl-C,
# TERM) todos os servidores iniciados por e2e_servidor são encerrados com os seus filhos. Uso: `source servidor.sh`.
declare -A E2E_GRUPOS=()

e2e_porta_ocupada() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

e2e_servidor() {
  local py="$1" dados="$2" porta="$3" log="$4"; shift 4
  if e2e_porta_ocupada "$porta"; then
    echo "E2E: a porta $porta já está ocupada (servidor de outra execução?). Encerre-o ou escolha outra porta." >&2
    return 2
  fi
  # SEEDS2_NAV_CLASSICA=1: os roteiros dos pisos anteriores navegam pelos links da barra superior (navegação clássica);
  # um roteiro que queira a barra compacta do 3D-B2 passa SEEDS2_NAV_CLASSICA=0 nos argumentos (o último vence).
  local lanca=(env PYTHONDONTWRITEBYTECODE=1 SEEDS2_NAV_CLASSICA=1 SEEDS2_DATA_DIR="$dados" "$@" "$py" -m streamlit run app.py
               --server.headless true --server.port "$porta" --browser.gatherUsageStats false)
  if command -v setsid >/dev/null 2>&1; then setsid "${lanca[@]}" >"$log" 2>&1 &
  else "${lanca[@]}" >"$log" 2>&1 &
  fi
  local pid=$! grupo=""
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    grupo="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')"; [ -n "$grupo" ] && break; sleep 0.1
  done
  E2E_GRUPOS[$porta]="${grupo:-$pid}:$pid"
  for _ in $(seq 1 "${E2E_ESPERA:-120}"); do
    curl -sf "http://localhost:$porta/_stcore/health" >/dev/null 2>&1 && return 0
    kill -0 "$pid" 2>/dev/null || { echo "E2E: o servidor da porta $porta terminou ao iniciar (ver $log)." >&2; return 1; }
    sleep 1
  done
  echo "E2E: o servidor da porta $porta não respondeu (ver $log)." >&2
  return 1
}

_e2e_sinal() {   # <sinal> <porta>
  local reg="${E2E_GRUPOS[$2]:-}"; [ -n "$reg" ] || return 0
  local grupo="${reg%%:*}" pid="${reg##*:}"
  # o grupo só é sinalizado se NÃO for o do próprio roteiro (sem setsid o servidor herda o grupo do roteiro)
  if [ "$grupo" != "$(ps -o pgid= -p $$ | tr -d ' ')" ]; then kill "-$1" -- "-$grupo" 2>/dev/null || true; fi
  pkill "-$1" -P "$pid" 2>/dev/null || true
  kill "-$1" "$pid" 2>/dev/null || true
}

e2e_matar() { _e2e_sinal KILL "$1"; unset "E2E_GRUPOS[$1]"; }

e2e_parar() {
  local porta="$1"; [ -n "${E2E_GRUPOS[$porta]:-}" ] || return 0
  _e2e_sinal TERM "$porta"
  for _ in $(seq 1 50); do e2e_porta_ocupada "$porta" || break; sleep 0.2; done
  _e2e_sinal KILL "$porta"
  for _ in $(seq 1 25); do e2e_porta_ocupada "$porta" || break; sleep 0.2; done
  unset "E2E_GRUPOS[$porta]"
}

e2e_limpar() { local p; for p in "${!E2E_GRUPOS[@]}"; do e2e_parar "$p"; done; }

e2e_fase() {
  local log="$1"; shift
  local rc=0
  "$@" 2>&1 | tee "$log" || rc="${PIPESTATUS[0]}"          # com `set -e` + pipefail a falha não pode abortar antes do aviso
  [ "$rc" -eq 0 ] || { echo "E2E: fase falhou (código $rc): $*" >&2; return "$rc"; }
}

trap e2e_limpar EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
