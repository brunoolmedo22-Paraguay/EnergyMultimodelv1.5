"""Malha temporal (``TimeGrid``) — especificação v1.0 M01 e §13; adenda v1.1 §A e "Temporalidade".

* ``N`` intervalos de decisão ``I_t = [τ_k + tΔ, τ_k + (t+1)Δ)``, ``t = 0…N−1``, e ``N+1`` estados de fronteira
  ``k = 0…N``. O último estado NÃO é um intervalo adicional (sem integração do instante terminal).
* ``Δ`` em minutos, representável em segundos inteiros; ``h = Δ/60`` em horas, exato (``Fraction``).
* Horizonte de previsão ``H_f``, de otimização ``H_o = NΔ``, reotimização ``ρ = mΔ`` (``1 ≤ m ≤ N``) e missão
  ``T_M`` são campos DISTINTOS; ``H_f ≥ H_o`` quando declarado.
* Instantes exigem fuso/deslocamento explícito; tudo é normalizado para UTC.

Nada aqui otimiza nem interpola: a malha só define índices, durações e verificações de cardinalidade.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Sequence

from .diagnostics import Constatacao, ContratoInvalido, aviso, erro, pendente
from .units import exato


def ler_instante_utc(texto: str | None, caminho: str) -> tuple[datetime | None, list[Constatacao]]:
    """ISO 8601 com fuso explícito (``Z`` ou ``±hh:mm``). Sem fuso = ambíguo → rejeição."""
    if not isinstance(texto, str) or not texto.strip():
        return None, [erro("instante_ausente", caminho, "Instante ausente.")]
    try:
        dt = datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))
    except ValueError:
        return None, [erro("instante_invalido", caminho, f"Instante não ISO 8601: {texto!r}.")]
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None, [erro("fuso_ambiguo", caminho, f"Instante sem fuso/deslocamento explícito: {texto!r}.")]
    return dt.astimezone(timezone.utc), []


def _inteiro(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


@dataclass(frozen=True)
class MalhaTemporal:
    inicio_utc: str                         # τ_k — início da janela (com fuso explícito)
    delta_min: float                        # Δ [min]
    intervalos_otimizacao: int              # N  (H_o = NΔ)
    intervalos_reotimizacao: int            # m  (ρ = mΔ)
    intervalos_missao: int                  # K_M (T_M = K_M Δ)
    horizonte_previsao_min: float | None = None   # H_f [min]; None = não declarado (aviso)

    # ---------------------------------------------------------------- grandezas derivadas
    @property
    def N(self) -> int:
        return self.intervalos_otimizacao

    @property
    def delta_s(self) -> int:
        return int(exato(self.delta_min) * 60)

    @property
    def h_horas(self) -> Fraction:
        """h = Δ/60 [h], exato."""
        return exato(self.delta_min) / 60

    @property
    def horizonte_otimizacao_min(self) -> Fraction:
        return self.intervalos_otimizacao * exato(self.delta_min)

    @property
    def reotimizacao_min(self) -> Fraction:
        return self.intervalos_reotimizacao * exato(self.delta_min)

    @property
    def missao_min(self) -> Fraction:
        return self.intervalos_missao * exato(self.delta_min)

    @property
    def n_fronteiras(self) -> int:
        return self.intervalos_otimizacao + 1

    def inicio(self) -> datetime:
        dt, c = ler_instante_utc(self.inicio_utc, "malha.inicio_utc")
        if c:
            raise ContratoInvalido(c)
        return dt

    def inicios_intervalos_utc(self) -> list[datetime]:
        t0, d = self.inicio(), timedelta(seconds=self.delta_s)
        return [t0 + t * d for t in range(self.N)]

    def fronteiras_utc(self) -> list[datetime]:
        t0, d = self.inicio(), timedelta(seconds=self.delta_s)
        return [t0 + k * d for k in range(self.N + 1)]

    # ---------------------------------------------------------------- construção a partir de minutos
    @classmethod
    def de_minutos(cls, inicio_utc: str, *, delta_min: float, horizonte_min: float, reotimizacao_min: float,
                   missao_min: float, horizonte_previsao_min: float | None = None) -> "MalhaTemporal":
        """Exige divisibilidade EXATA de H_o, ρ e T_M por Δ (sem último intervalo curto implícito)."""
        c: list[Constatacao] = []
        try:
            d = exato(delta_min)
        except (TypeError, ValueError) as exc:
            raise ContratoInvalido([erro("delta_invalido", "malha.delta_min", str(exc))]) from None
        if d <= 0:
            raise ContratoInvalido([erro("delta_invalido", "malha.delta_min", "Δ deve ser > 0.")])
        nums = {}
        for nome, v in (("horizonte_min", horizonte_min), ("reotimizacao_min", reotimizacao_min),
                        ("missao_min", missao_min)):
            q = exato(v) / d
            if q.denominator != 1:
                c.append(erro(f"{nome.split('_')[0]}_nao_divisivel", f"malha.{nome}",
                              f"{v} min não é múltiplo inteiro de Δ = {delta_min} min."))
            nums[nome] = int(q) if q.denominator == 1 else 0
        if c:
            raise ContratoInvalido(c)
        m = cls(inicio_utc, delta_min, nums["horizonte_min"], nums["reotimizacao_min"], nums["missao_min"],
                horizonte_previsao_min)
        cv = validar_malha(m)
        if any(x.severidade == "erro" for x in cv):
            raise ContratoInvalido(cv)
        return m

    # ---------------------------------------------------------------- vetores
    def verificar_vetor_intervalos(self, valores: Sequence, caminho: str) -> list[Constatacao]:
        return _verificar_comprimento(valores, self.N, caminho, terminal=self.N + 1)

    def verificar_vetor_estados(self, valores: Sequence, caminho: str) -> list[Constatacao]:
        return _verificar_comprimento(valores, self.N + 1, caminho, terminal=None)


def _verificar_comprimento(valores: Sequence, esperado: int, caminho: str, terminal: int | None) -> list[Constatacao]:
    try:
        n = len(valores)
    except TypeError:
        return [erro("vetor_invalido", caminho, "Vetor ausente ou não sequencial.")]
    if n == esperado:
        return []
    if terminal is not None and n == terminal:
        return [erro("instante_terminal_como_intervalo", caminho,
                     f"{n} valores para {esperado} intervalos: o estado terminal (fronteira N) não é um intervalo "
                     "e não pode ser integrado.")]
    return [erro("comprimento_incompativel", caminho, f"Esperados {esperado} valores; recebidos {n}.")]


def validar_malha(m: MalhaTemporal) -> list[Constatacao]:
    out: list[Constatacao] = []
    _, c = ler_instante_utc(m.inicio_utc, "malha.inicio_utc")
    out += c
    dm = m.delta_min
    if isinstance(dm, bool) or not isinstance(dm, (int, float)) or not math.isfinite(dm) or dm <= 0:
        out.append(erro("delta_invalido", "malha.delta_min", "Δ deve ser número finito > 0."))
        return out
    if (exato(dm) * 60).denominator != 1:
        out.append(erro("delta_nao_inteiro_em_segundos", "malha.delta_min",
                        f"Δ = {dm} min não corresponde a um número inteiro de segundos."))
    for nome in ("intervalos_otimizacao", "intervalos_reotimizacao", "intervalos_missao"):
        v = getattr(m, nome)
        if not _inteiro(v) or v < 1:
            out.append(erro("contagem_invalida", f"malha.{nome}", f"Exigido inteiro >= 1; recebido {v!r}."))
    if out:
        return out
    if m.intervalos_reotimizacao > m.intervalos_otimizacao:
        out.append(erro("reotimizacao_maior_que_horizonte", "malha.intervalos_reotimizacao",
                        "ρ > H_o: exigido 1 <= m <= N."))
    if m.intervalos_otimizacao > m.intervalos_missao:
        out.append(pendente("horizonte_alem_da_missao", "malha.intervalos_otimizacao",
                            "H_o ultrapassa o fim da missão: cobertura estendida/obrigações pós-missão exigem política "
                            "explícita (Piso 3C); nenhuma previsão é inventada."))
    hf = m.horizonte_previsao_min
    if hf is None:
        out.append(aviso("horizonte_previsao_nao_declarado", "malha.horizonte_previsao_min",
                         "H_f não declarado: a cobertura é verificada série a série."))
    elif isinstance(hf, bool) or not isinstance(hf, (int, float)) or not math.isfinite(hf):
        out.append(erro("horizonte_previsao_invalido", "malha.horizonte_previsao_min", "H_f inválido."))
    elif exato(hf) < m.intervalos_otimizacao * exato(dm):
        out.append(erro("horizonte_previsao_insuficiente", "malha.horizonte_previsao_min",
                        f"H_f = {hf} min < H_o = {m.intervalos_otimizacao * exato(dm)} min."))
    return out


__all__ = ["MalhaTemporal", "ler_instante_utc", "validar_malha"]
