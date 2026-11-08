"""Classificação da terminação do solver e estrutura do resultado (sem Pyomo; testável isoladamente).

Separação obrigatória (especificação v1.0 §17): ``classificacao`` (estado do solver), ``solucao_primal`` (há
incumbente carregado?), ``auditoria`` (resíduos independentes) e ``estado_despacho`` (aceitação final). Terminar
não implica ótimo; "ótimo" = critério de convergência do HiGHS satisfeito DENTRO dos gaps configurados.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import ROTULO_EVIDENCIA
from ..audit import CandidatoDespacho, RelatorioAuditoria
from ..diagnostics import Constatacao

LIMITES = {"maxTimeLimit", "iterationLimit", "objectiveLimit", "minStepLength", "interrupted"}
CLASSIFICACOES = {
    "otimo": "Convergência dentro dos gaps configurados, com solução ótima carregável",
    "factivel_nao_otimo": "Limite atingido (tempo/iterações/soluções) COM incumbente — não é ótimo",
    "sem_solucao": "Limite atingido SEM incumbente — nenhum despacho",
    "inviavel": "Inviabilidade provada (ou localmente) — nenhum despacho",
    "inviavel_ou_ilimitado": "Inviável ou ilimitado — nenhum despacho",
    "ilimitado": "Ilimitado — nenhum despacho (mesmo que o solver relate um ponto factível)",
    "erro": "Erro do solver/licença/modelo — nenhum despacho",
    "desconhecido": "Terminação não reconhecida — nenhum despacho",
    "bloqueado_validacao": "Entrada/configuração rejeitada antes de construir o modelo",
    "solver_indisponivel": "Pyomo/HiGHS indisponível — nada foi resolvido",
}
ESTADOS_DESPACHO = ("aceito_otimo", "aceito_factivel_nao_otimo", "rejeitado_auditoria", "rejeitado_integridade",
                    "sem_despacho")


def classificar(terminacao: str | None, status_solucao: str | None) -> str:
    """Mapeia (TerminationCondition.name, SolutionStatus.name) do ``pyomo.contrib.solver`` para a classificação.
    Função pura: qualquer combinação não prevista ⇒ ``desconhecido`` (nunca despacho)."""
    tem = status_solucao in ("optimal", "feasible")
    if terminacao == "convergenceCriteriaSatisfied":
        if status_solucao == "optimal":
            return "otimo"
        return "factivel_nao_otimo" if tem else "desconhecido"
    if terminacao in LIMITES:
        return "factivel_nao_otimo" if tem else "sem_solucao"
    if terminacao in ("provenInfeasible", "locallyInfeasible"):
        return "inviavel"
    if terminacao == "infeasibleOrUnbounded":
        return "inviavel_ou_ilimitado"
    if terminacao == "unbounded":
        return "ilimitado"
    if terminacao in ("error", "licensingProblems", "emptyModel", "invalidProblem"):
        return "erro"
    return "desconhecido"


def gaps(incumbente: float | None, limite: float | None) -> tuple[float | None, float | None]:
    """Convenção declarada (minimização): gap_abs = |incumbente − limite|; gap_rel = gap_abs / |incumbente|
    (denominador do HiGHS); com |incumbente| < 1e-9: gap_rel = 0 se gap_abs = 0, senão None (indefinido)."""
    if incumbente is None or limite is None:
        return None, None
    try:
        inc, lim = float(incumbente), float(limite)
    except (TypeError, ValueError):
        return None, None
    if not (abs(inc) < float("inf") and abs(lim) < float("inf")):
        return None, None
    ga = abs(inc - lim)
    if abs(inc) < 1e-9:
        return ga, (0.0 if ga == 0.0 else None)
    return ga, ga / abs(inc)


@dataclass(frozen=True)
class ResultadoResolucao:
    motor_id: str
    versao_formulacao: str
    hash_entrada: str | None
    hash_compromisso: str | None
    microrrede_uid: str
    cenario_uid: str
    classificacao: str
    terminacao: str | None
    status_solucao: str | None
    solucao_primal: bool
    objetivo: float | None
    limite_dual: float | None
    gap_abs: float | None
    gap_rel: float | None
    gap_highs: float | None
    tempos_s: dict[str, float]
    tamanho: dict[str, int]
    ambiente: dict
    configuracao: dict
    candidato: CandidatoDespacho | None
    despacho: dict | None
    custos_modelo: dict[str, float]
    auditoria: RelatorioAuditoria | None
    estado_despacho: str
    aceito: bool
    constatacoes: tuple[Constatacao, ...] = field(default_factory=tuple)
    familias_nao_modeladas: tuple[str, ...] = ()
    integridade: RelatorioAuditoria | None = None   # testemunho auxiliar do MILP (z_b, δ, θ) — C-3B-02
    rotulo: str = ROTULO_EVIDENCIA

    def codigos(self) -> set[str]:
        return {c.codigo for c in self.constatacoes}


__all__ = ["CLASSIFICACOES", "ESTADOS_DESPACHO", "LIMITES", "ResultadoResolucao", "classificar", "gaps"]
