"""Instrumentação para campanhas computacionais futuras (3C-0 §3.7).

* ``Cronometro`` — duração por FASE (preparação de dados, construção do modelo, resolução, processamento do
  resultado, avanço da simulação, persistência), com relógio injetável (testes determinísticos).
* ``classificar_desfecho`` — distingue êxito, inviabilidade, timeout, erro numérico, erro de integração e bloqueio
  por validação/preflight a partir do resultado 3B-P ou de uma exceção da integração.
* ``estatisticas`` — n, média, p50, p95, p99 e máximo por PERCENTIL DE POSTO MAIS PRÓXIMO (definição declarada; sem
  interpolação). Nenhuma meta de desempenho é afirmada aqui: os números são o que foi medido.
"""
from __future__ import annotations

import math
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator

FASES = {
    "preparacao_dados": "Leitura do inventário/cenário/previsões e projeção para a entrada canônica",
    "construcao_modelo": "Construção do modelo de otimização",
    "resolucao": "Resolução pelo solver",
    "processamento_resultado": "Extração, auditoria e conversão do resultado em plano",
    "avanco_simulacao": "Execução do plano (avanço do estado)",
    "persistencia": "Gravação do registro selado",
}
DESFECHOS = {
    "exito": "Despacho aceito (ótimo ou factível auditado) e executado/registrado",
    "inviavel": "Inviabilidade provada (ou inviável-ou-ilimitado) — nenhum despacho",
    "timeout": "Limite de tempo/recursos do solver: sem incumbente, ou incumbente não ótimo rotulado como tal",
    "erro_numerico": "Erro do solver, terminação desconhecida, problema ilimitado ou solução rejeitada pela auditoria/integridade",
    "erro_integracao": "Falha da ponte/ambiente (dados, adaptador, solver indisponível, exceção não científica)",
    "bloqueado_validacao": "Bloqueado ANTES de resolver (preflight/contrato)",
}


@dataclass
class Cronometro:
    relogio: Callable[[], float] = time.perf_counter
    duracoes_s: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def fase(self, nome: str) -> Iterator[None]:
        if nome not in FASES:
            raise ValueError(f"Fase desconhecida: {nome!r}")
        t0 = self.relogio()
        try:
            yield
        finally:
            self.duracoes_s[nome] = self.duracoes_s.get(nome, 0.0) + (self.relogio() - t0)

    def registrar(self, nome: str, duracao_s: float | None) -> None:
        """Incorpora uma duração MEDIDA por outro componente (p. ex. ``ResultadoResolucao.tempos_s``); None é ignorado
        (nunca vira zero)."""
        if nome not in FASES:
            raise ValueError(f"Fase desconhecida: {nome!r}")
        if duracao_s is not None and math.isfinite(float(duracao_s)):
            self.duracoes_s[nome] = self.duracoes_s.get(nome, 0.0) + float(duracao_s)

    def total_s(self) -> float:
        return sum(self.duracoes_s.values())


_MAPA_3BP = {"otimo": "exito", "inviavel": "inviavel", "inviavel_ou_ilimitado": "inviavel", "sem_solucao": "timeout",
             "ilimitado": "erro_numerico", "erro": "erro_numerico", "desconhecido": "erro_numerico",
             "bloqueado_validacao": "bloqueado_validacao", "solver_indisponivel": "erro_integracao"}


def classificar_desfecho(resultado=None, excecao: BaseException | None = None) -> tuple[str, str]:
    """(desfecho, justificativa). ``factivel_nao_otimo`` só é êxito se aceito pela auditoria; por limite de tempo
    sem convergência é rotulado ``timeout`` (incumbente não ótimo), nunca êxito silencioso."""
    if excecao is not None:
        return "erro_integracao", f"{type(excecao).__name__}: {excecao}"
    if resultado is None:
        return "erro_integracao", "Nenhum resultado produzido."
    cl = getattr(resultado, "classificacao", None)
    est = getattr(resultado, "estado_despacho", None)
    if est in ("rejeitado_auditoria", "rejeitado_integridade"):
        return "erro_numerico", f"Solução {cl} rejeitada ({est})."
    if cl == "factivel_nao_otimo":
        if getattr(resultado, "terminacao", None) == "maxTimeLimit":
            return "timeout", "Limite de tempo com incumbente (não ótimo)."
        return ("exito" if getattr(resultado, "aceito", False) else "erro_numerico"), f"Incumbente não ótimo ({est})."
    if cl in _MAPA_3BP:
        d = _MAPA_3BP[cl]
        if d == "exito" and not getattr(resultado, "aceito", False):
            return "erro_numerico", f"Ótimo não aceito ({est})."
        return d, f"Classificação 3B-P {cl!r}."
    return "erro_numerico", f"Classificação não reconhecida {cl!r}."


@dataclass(frozen=True)
class Estatisticas:
    n: int
    media: float | None
    p50: float | None
    p95: float | None
    p99: float | None
    maximo: float | None
    definicao: str = "percentil de posto mais próximo: valor de ordem ceil(p·n) (1-indexado), sem interpolação"


def percentil_posto(valores: list[float], p: float) -> float | None:
    if not valores:
        return None
    if not 0 < p <= 1:
        raise ValueError("p em (0, 1].")
    ordenados = sorted(valores)
    return ordenados[max(1, math.ceil(p * len(ordenados))) - 1]


def estatisticas(valores) -> Estatisticas:
    vs = [float(v) for v in valores]
    if any(not math.isfinite(v) for v in vs):
        raise ValueError("Duração não finita na amostra (registre a falha como desfecho, não como tempo).")
    if not vs:
        return Estatisticas(0, None, None, None, None, None)
    return Estatisticas(len(vs), sum(vs) / len(vs), percentil_posto(vs, 0.50), percentil_posto(vs, 0.95),
                        percentil_posto(vs, 0.99), max(vs))


__all__ = ["Cronometro", "DESFECHOS", "Estatisticas", "FASES", "classificar_desfecho", "estatisticas", "percentil_posto"]
