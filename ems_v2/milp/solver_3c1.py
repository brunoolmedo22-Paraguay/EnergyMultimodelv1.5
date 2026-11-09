"""API de resolução do perfil 3C-1: ``resolver_3c1(entrada_3c1, configuracao, compromisso_parcial)``.

Interface NOVA e versionada; ``solver.resolver`` (3B-P) não foi alterado e continua recusando transições
(``transicao_nao_modelada_3BP``) e entradas que não sejam ``v1.1-3B-P``.

Fluxo (mesma disciplina do 3B-P): ambiente → configuração → ``preflight_3c1`` (contrato 3C-1 + base 3B-P +
compromisso parcial) → construção (``modelo_3c1``) → HiGHS (``pyomo.contrib.solver`` "highs", ``load_solutions=False``)
→ classificação → carga/extração (só se despachável) → coerência do objetivo → AUDITOR INDEPENDENTE 3C-1
(``compromisso.auditor``, sem Pyomo) + integridade do testemunho auxiliar 3B-P (z_b, δ, θ) → estado final.
Nenhuma solução rejeitada pela auditoria ou pela integridade é aceita (e, portanto, nunca vira plano 3C-0).
"""
from __future__ import annotations

import dataclasses
import math
import time

from .. import FORMULACAO_3C1, MOTOR_ID
from ..audit import CandidatoDespacho, Tolerancias
from ..compromisso.auditor import auditar_3c1
from ..compromisso.contrato import EntradaCommitment3C1, hash_entrada_3c1
from ..compromisso.memoria import garantia, memoria_terminal
from ..compromisso.preflight import preflight_3c1
from ..diagnostics import Constatacao, erro
from .ambiente import INTERFACE, verificar_ambiente
from .config import ConfiguracaoSolver, configuracao_registro, validar_configuracao
from .integridade import verificar_testemunho
from .resultado import classificar, gaps
from .resultado_3c1 import ResultadoResolucao3C1
from .solver import DESPACHAVEIS, OpcaoHighsInvalida, _executar_highs, _extrair, _finito, _hash_compromisso, _tamanho, _valor


def _extrair_3c1(mc3, e: EntradaCommitment3C1):
    cand, despacho, faltas = _extrair(mc3.base, e.base)
    m, N = mc3.modelo, mc3.base.N
    ger = {}
    for g in mc3.base.geradores:
        y = tuple(_valor(m.y[g, t], f"y[{g},{t}]", faltas) for t in range(N))
        z = tuple(_valor(m.z[g, t], f"z[{g},{t}]", faltas) for t in range(N))
        ger[g] = {**cand.geradores[g], "y": y, "z": z}
        despacho["geradores"][g] = {**despacho["geradores"][g], "y": y, "z": z}
    cand = dataclasses.replace(cand, geradores=ger)
    return cand, despacho, faltas


def resolver_3c1(entrada: EntradaCommitment3C1, configuracao: ConfiguracaoSolver, compromisso_parcial: dict | None = None,
                 *, tolerancias: Tolerancias = Tolerancias(), _executor=None) -> ResultadoResolucao3C1:
    t_ini = time.perf_counter()
    amb = verificar_ambiente()
    erros_config = validar_configuracao(configuracao)
    b = getattr(entrada, "base", None)
    base = dict(motor_id=MOTOR_ID, versao_formulacao=getattr(entrada, "versao_formulacao", "?"),
                microrrede_uid=getattr(b, "microrrede_uid", "?"), cenario_uid=getattr(b, "cenario_uid", "?"),
                ambiente={**amb, "interface": INTERFACE}, hash_compromisso=_hash_compromisso(compromisso_parcial),
                configuracao=configuracao_registro(configuracao, valida=not erros_config),
                politica_permanencia=getattr(getattr(entrada, "politica_permanencia", None), "tipo", None))
    nao_mod = ("auxiliares_evento_M05", "potencias_de_extremo_M11_EXT", "multimodo_M20", "terminal_energia",
               "valor_futuro")

    def sem(classif, constat, tempos=None, tam=None, hash_e=None, term=None, st=None, extra=None, disc=None, bloq=()):
        return ResultadoResolucao3C1(**base, hash_entrada=hash_e, classificacao=classif, terminacao=term,
                                     status_solucao=st, solucao_primal=False, objetivo=None,
                                     limite_dual=(extra or {}).get("limite"), gap_abs=None, gap_rel=None,
                                     gap_highs=(extra or {}).get("gap_highs"), tempos_s=tempos or {}, tamanho=tam or {},
                                     candidato=None, despacho=None, custos_modelo={}, auditoria=None,
                                     estado_despacho="sem_despacho", aceito=False, constatacoes=tuple(constat),
                                     familias_nao_modeladas=nao_mod, discretizacao=disc or {},
                                     transicoes_bloqueadas=tuple(bloq))

    if not amb["disponivel"] and _executor is None:
        return sem("solver_indisponivel", [erro("solver_indisponivel", "ambiente", str(amb["erro"]))])
    constat: list[Constatacao] = list(erros_config)
    if not isinstance(entrada, EntradaCommitment3C1) or entrada.versao_formulacao != FORMULACAO_3C1:
        constat.append(erro("formulacao_nao_3c1", "entrada",
                            f"resolver_3c1 só resolve EntradaCommitment3C1 declarada {FORMULACAO_3C1!r}; entradas 3A/3B-P "
                            "usam solver.resolver (sem ganhar capacidades implicitamente)."))
        return sem("bloqueado_validacao", constat)
    constat += preflight_3c1(entrada, compromisso_parcial)
    if any(c.severidade in ("erro", "pendente") for c in constat):
        return sem("bloqueado_validacao", constat)
    he = hash_entrada_3c1(entrada)
    from .modelo_3c1 import construir_modelo_3c1
    t0 = time.perf_counter()
    mc3 = construir_modelo_3c1(entrada, compromisso_parcial)
    t_cons = time.perf_counter() - t0
    tam = _tamanho(mc3.modelo)
    disc = {k: dataclasses.asdict(v) for k, v in mc3.discretizacao.items()}
    if mc3.base.balanco_trivial_inviavel:
        constat.append(erro("balanco_trivialmente_inviavel", "M02",
                            f"Intervalos {mc3.base.balanco_trivial_inviavel[:8]} sem decisão e com balanço ≠ 0."))
        return sem("inviavel", constat, {"construcao_s": t_cons}, tam, he, term="trivialmente_inviavel_na_construcao",
                   disc=disc, bloq=mc3.transicoes_bloqueadas)
    try:
        exe = (_executor or _executar_highs)(mc3.modelo, configuracao)
        if not isinstance(exe, dict):
            raise TypeError(f"executor devolveu {type(exe).__name__}, esperado dict")
    except Exception as exc:  # noqa: BLE001 — falha vira ERRO controlado, nunca factibilidade
        cod = "opcao_highs_invalida" if isinstance(exc, OpcaoHighsInvalida) else "falha_solver"
        constat.append(erro(cod, "solver", f"{type(exc).__name__}: {exc}"))
        return sem("erro", constat, {"construcao_s": t_cons, "total_s": time.perf_counter() - t_ini}, tam, he,
                   term="excecao", disc=disc, bloq=mc3.transicoes_bloqueadas)
    tempos = {"construcao_s": t_cons, "solver_s": exe.get("tempo_solver_s"), "highs_s": exe.get("tempo_highs_s")}
    term, st = exe.get("terminacao"), exe.get("status_solucao")
    classif = classificar(term, st)
    inc, lim = exe.get("incumbente"), exe.get("limite")
    if classif not in DESPACHAVEIS:
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem(classif, constat, tempos, tam, he, term, st, {"limite": _finito(lim), "gap_highs": exe.get("gap_highs")},
                   disc=disc, bloq=mc3.transicoes_bloqueadas)
    try:
        exe["carregar"]()
        cand, despacho, faltas = _extrair_3c1(mc3, entrada)
    except Exception as exc:  # noqa: BLE001
        constat.append(erro("falha_carregamento", "solucao", f"{type(exc).__name__}: {exc}"))
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem("erro", constat, tempos, tam, he, term, st, {"limite": _finito(lim)}, disc=disc,
                   bloq=mc3.transicoes_bloqueadas)
    if faltas:
        constat.append(erro("valor_nao_carregado", "solucao", f"{len(faltas)} variável(is) sem valor finito "
                                                              f"({faltas[:5]}): nenhum despacho."))
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem(classif, constat, tempos, tam, he, term, st, {"limite": _finito(lim)}, disc=disc,
                   bloq=mc3.transicoes_bloqueadas)
    import pyomo.environ as pe
    custos_modelo = {k: float(pe.value(v)) for k, v in mc3.expr_termos.items() if k in mc3.termos}
    obj_modelo = float(pe.value(mc3.modelo.J))
    custos_modelo["total"] = obj_modelo
    if inc is not None and math.isfinite(float(inc)) and abs(float(inc) - obj_modelo) > 1e-6 * max(1.0, abs(obj_modelo)):
        constat.append(erro("objetivo_incoerente", "solucao",
                            f"Objetivo do solver {inc} ≠ objetivo avaliado nos valores carregados {obj_modelo}."))
    cand = CandidatoDespacho(renovaveis=cand.renovaveis, baterias=cand.baterias, demandas=cand.demandas,
                             descarte=cand.descarte, geradores=cand.geradores, custos_reportados=dict(custos_modelo))
    aud = auditar_3c1(entrada, cand, tolerancias, compromisso_parcial)
    integ = verificar_testemunho(entrada.base, despacho, tolerancias)
    ok_aud = aud.aceito and not any(c.severidade in ("erro", "pendente") for c in constat)
    ok = ok_aud and integ.aceito
    if not integ.aceito:
        constat.append(erro("testemunho_milp_invalido", "integridade",
                            f"Testemunho auxiliar do MILP inconsistente: famílias {sorted(integ.familias_reprovadas())}. "
                            "Despacho NÃO aceito."))
    estado = (("aceito_otimo" if classif == "otimo" else "aceito_factivel_nao_otimo") if ok
              else "rejeitado_auditoria" if not ok_aud else "rejeitado_integridade")
    u = {g: [1 if x > 0.5 else 0 for x in cand.geradores[g]["u"]] for g in cand.geradores}
    p = {g: list(cand.geradores[g]["p"]) for g in cand.geradores}
    mem = memoria_terminal(entrada, u, p) if entrada.base.geradores else ()
    gar, res = garantia(mem)
    eventos = {g: {"partidas": sum(1 for x in cand.geradores[g]["y"] if x > 0.5),
                   "paradas": sum(1 for x in cand.geradores[g]["z"] if x > 0.5)} for g in cand.geradores}
    ga, gr = gaps(inc, lim)
    tempos["total_s"] = time.perf_counter() - t_ini
    return ResultadoResolucao3C1(
        **base, hash_entrada=he, classificacao=classif, terminacao=term, status_solucao=st, solucao_primal=True,
        objetivo=_finito(inc) if inc is not None else obj_modelo, limite_dual=_finito(lim), gap_abs=ga, gap_rel=gr,
        gap_highs=exe.get("gap_highs"), tempos_s=tempos, tamanho=tam, candidato=cand, despacho=despacho,
        custos_modelo=custos_modelo, auditoria=aud, estado_despacho=estado, aceito=ok, constatacoes=tuple(constat),
        familias_nao_modeladas=aud.familias_nao_modeladas, integridade=integ, discretizacao=disc, eventos=eventos,
        memoria_terminal=mem, obrigacoes_residuais_s=res, garantia_permanencia=gar,
        transicoes_bloqueadas=mc3.transicoes_bloqueadas)


__all__ = ["resolver_3c1"]
