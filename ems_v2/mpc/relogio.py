"""Relógio lógico da missão e janelas do horizonte recedente (3C-2).

Definições (reutilizando ``MalhaTemporal``): fronteiras globais τ_k = τ_0 + kΔ, k = 0…K_M; a janela que começa em τ_k
otimiza N_k intervalos e aplica no máximo m_k = min(m, K_M − k) intervalos (o último bloco pode ser menor que m).

* ``janela_reduzida``: N_k = min(N, K_M − k) (especificação v1.0 §13: "N_k = min(N, K_M − k) sem inventar previsões");
* ``horizonte_estendido_declarado``: N_k = N; os N_k − (K_M − k) intervalos pós-missão são planejados com a cobertura
  declarada, mas nunca aplicados nem contabilizados.

A política de permanência 3C-1 da janela é a "final" quando o horizonte da janela alcança/ultrapassa o fim da missão
(k + N_k >= K_M) e a "intermediária" caso contrário. O contador global NUNCA retrocede e a soma dos intervalos
aplicados nunca excede K_M (``RelogioMissao``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from ..diagnostics import ContratoInvalido, erro
from ..timegrid import MalhaTemporal
from .contrato import ConfiguracaoMPC


@dataclass(frozen=True)
class JanelaMPC:
    indice_janela: int
    k: int                                  # fronteira GLOBAL de início (τ_k)
    inicio_utc: str
    N_k: int                                # intervalos otimizados nesta janela
    m_k: int                                # intervalos a aplicar (<= m, <= K_M − k)
    intervalos_restantes: int               # K_M − k
    intervalos_pos_missao: int              # max(0, N_k − (K_M − k)) — só horizonte estendido
    reduzida: bool                          # N_k < N (registro de cada acortamento)
    final: bool                             # k + m_k == K_M
    alcanca_fim_da_missao: bool             # k + N_k >= K_M
    politica_permanencia: str               # política 3C-1 aplicada nesta janela
    intervalos_missao_entrada: int          # campo ``intervalos_missao`` da malha da entrada 3C-1 da janela

    def malha(self, base: MalhaTemporal) -> MalhaTemporal:
        """Malha da entrada 3C-1 da janela (mesmo Δ e H_f declarados da missão)."""
        return MalhaTemporal(self.inicio_utc, base.delta_min, self.N_k, self.m_k, self.intervalos_missao_entrada,
                             base.horizonte_previsao_min)


def instante_fronteira(malha: MalhaTemporal, k: int) -> str:
    return (malha.inicio() + timedelta(seconds=malha.delta_s * k)).isoformat()


def janela_em(cfg: ConfiguracaoMPC, indice_janela: int, k: int) -> JanelaMPC:
    m = cfg.malha
    K, N, mm = m.intervalos_missao, m.intervalos_otimizacao, m.intervalos_reotimizacao
    if isinstance(k, bool) or not isinstance(k, int) or not 0 <= k < K:
        raise ContratoInvalido([erro("fronteira_fora_da_missao", "relogio.k", f"k = {k!r} fora de [0, {K}).")])
    resto = K - k
    pt = cfg.politica_terminal
    if pt.tipo == "janela_reduzida":
        Nk, pos, ent = min(N, resto), 0, resto
    else:
        Nk = N
        pos = max(0, N - resto)
        ent = max(N, resto)                 # decisão D-3C2-04: a política de cobertura pós-missão vive no contrato MPC
    mk = min(mm, resto)
    alc = k + Nk >= K
    return JanelaMPC(indice_janela, k, instante_fronteira(m, k), Nk, mk, resto, pos, Nk < N, k + mk == K, alc,
                     pt.permanencia_janela_final if alc else pt.permanencia_janelas_intermediarias, ent)


def cronograma_nominal(cfg: ConfiguracaoMPC) -> tuple[JanelaMPC, ...]:
    """Janelas se todo bloco for integralmente aplicado (k = 0, m, 2m, …)."""
    out, k, j = [], 0, 0
    while k < cfg.malha.intervalos_missao:
        jan = janela_em(cfg, j, k)
        out.append(jan)
        k, j = k + jan.m_k, j + 1
    return tuple(out)


class RelogioMissao:
    """Contador global monotônico da missão. ``avancar`` só aceita 1 <= n <= m_k da janela corrente."""

    def __init__(self, cfg: ConfiguracaoMPC, *, k: int = 0, indice_janela: int = 0):
        self.cfg = cfg
        self._k, self._j = k, indice_janela
        self._aplicados = k
        if k < 0 or k > cfg.malha.intervalos_missao:
            raise ContratoInvalido([erro("fronteira_fora_da_missao", "relogio.k", f"k = {k}.")])

    @property
    def k(self) -> int:
        return self._k

    @property
    def indice_janela(self) -> int:
        return self._j

    @property
    def encerrado(self) -> bool:
        return self._k >= self.cfg.malha.intervalos_missao

    @property
    def instante_utc(self) -> str:
        return instante_fronteira(self.cfg.malha, self._k)

    def janela_atual(self) -> JanelaMPC:
        return janela_em(self.cfg, self._j, self._k)

    def avancar(self, aplicados: int) -> None:
        jan = self.janela_atual()
        if isinstance(aplicados, bool) or not isinstance(aplicados, int) or not 1 <= aplicados <= jan.m_k:
            raise ContratoInvalido([erro("avanco_invalido", "relogio.avancar",
                                         f"{aplicados!r} intervalos: exigido 1 <= n <= m_k = {jan.m_k}.")])
        self._k += aplicados
        self._aplicados += aplicados
        self._j += 1
        if self._aplicados > self.cfg.malha.intervalos_missao:      # defesa: nunca ocorre com 1 <= n <= m_k
            raise ContratoInvalido([erro("missao_excedida", "relogio", "Σ intervalos aplicados > K_M.")])


__all__ = ["JanelaMPC", "RelogioMissao", "cronograma_nominal", "instante_fronteira", "janela_em"]
