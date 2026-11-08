"""API de resolução do Piso 3B-P: ``resolver(entrada, configuracao, compromisso_fixo)``.

Fluxo: ambiente → validação (contrato perfil 3B-P + configuração + pré-verificação) → construção Pyomo → HiGHS
(``pyomo.contrib.solver`` "highs", ``load_solutions=False``) → classificação da terminação → carga e extração do
incumbente (somente se a classificação admitir despacho) → AUDITORIA INDEPENDENTE (``ems_v2.audit``, sem Pyomo) →
estado final do despacho. Nenhuma solução rejeitada pelo auditor é aceita; nenhum valor ausente vira NaN/zero.

``_executor`` (parâmetro privado, só para testes) substitui a execução do HiGHS para simular terminações que não
podem ser provocadas de forma determinística (p. ex. limite de TEMPO com incumbente).
"""
from __future__ import annotations

import hashlib
import json
import math
import time

from .. import MOTOR_ID
from ..audit import CandidatoDespacho, Tolerancias, auditar
from ..contracts import EntradaModeloEMS, hash_entrada, validar_entrada
from ..diagnostics import Constatacao, erro
from .ambiente import INTERFACE, verificar_ambiente
from .config import ConfiguracaoSolver, configuracao_registro, preflight_3bp, validar_configuracao
from .resultado import ResultadoResolucao, classificar, gaps

DESPACHAVEIS = ("otimo", "factivel_nao_otimo")


def _hash_compromisso(c: dict | None) -> str:
    dado = {str(k): [int(x) for x in v] for k, v in sorted((c or {}).items())} if isinstance(c, dict) else None
    try:
        return hashlib.sha256(json.dumps(dado, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    except (TypeError, ValueError):
        return hashlib.sha256(repr(c).encode()).hexdigest()


def _executar_highs(modelo, config: ConfiguracaoSolver) -> dict:
    import pyomo.environ  # noqa: F401 — registra a fábrica
    from pyomo.contrib.solver.common.factory import SolverFactory

    opt = SolverFactory("highs")
    kw = dict(load_solutions=False, raise_exception_on_nonoptimal_result=False, threads=config.threads,
              rel_gap=config.rel_gap, abs_gap=config.abs_gap,
              solver_options={"random_seed": config.semente, **config.opcoes_highs})
    if config.time_limit_s is not None:
        kw["time_limit"] = config.time_limit_s
    t0 = time.perf_counter()
    r = opt.solve(modelo, **kw)
    dt = time.perf_counter() - t0
    gap_highs = None
    try:  # atributo privado da interface; ausência ⇒ None registrado (nunca zero)
        g = opt._solver_model.getInfo().mip_gap
        gap_highs = float(g) if math.isfinite(float(g)) else None
    except Exception:  # noqa: BLE001
        gap_highs = None
    return {"terminacao": r.termination_condition.name, "status_solucao": r.solution_status.name,
            "incumbente": r.incumbent_objective, "limite": r.objective_bound, "gap_highs": gap_highs,
            "tempo_solver_s": dt, "tempo_highs_s": r.timing_info.get("highs_time"),
            "carregar": r.solution_loader.load_vars}


def _tamanho(modelo) -> dict[str, int]:
    import pyomo.environ as pe
    vs = list(modelo.component_data_objects(pe.Var, active=True))
    return {"variaveis": len(vs), "variaveis_livres": sum(1 for v in vs if not v.fixed),
            "binarias_livres": sum(1 for v in vs if v.is_binary() and not v.fixed),
            "restricoes": sum(1 for _ in modelo.component_data_objects(pe.Constraint, active=True))}


def _valor(var, rot: str, faltas: list[str]) -> float:
    v = var.value
    if v is None or isinstance(v, bool) or not math.isfinite(float(v)):
        faltas.append(rot)
        return float("nan")
    return float(v)


def _extrair(mc, e: EntradaModeloEMS) -> tuple[CandidatoDespacho, dict, list[str]]:
    m, N = mc.modelo, mc.N
    f: list[str] = []
    T = range(N)
    ren = {r: {"P_R": tuple(_valor(m.P_R[r, t], f"P_R[{r},{t}]", f) for t in T),
               "C_oper": tuple(_valor(m.C_oper[r, t], f"C_oper[{r},{t}]", f) for t in T)} for r in mc.renovaveis}
    bat = {b: {"P_c": tuple(_valor(m.P_c[b, t], f"P_c[{b},{t}]", f) for t in T),
               "P_d": tuple(_valor(m.P_d[b, t], f"P_d[{b},{t}]", f) for t in T),
               "e": tuple(_valor(m.e[b, k], f"e[{b},{k}]", f) for k in range(N + 1))} for b in mc.baterias}
    zb = {b: tuple(_valor(m.z_b[b, t], f"z_b[{b},{t}]", f) for t in T) for b in mc.baterias}
    dem = {}
    for k in mc.demandas:   # classes sem autorização não têm variável ℓ: corte estruturalmente nulo pela política
        dem[k] = {"ell": tuple(_valor(m.ell[k, t], f"ell[{k},{t}]", f) for t in T) if k in mc.demandas_autorizadas
                  else tuple(0.0 for _ in T)}
    desc = tuple(_valor(m.d[t], f"d[{t}]", f) for t in T) if mc.com_descarte else None
    ger = {}
    seg = {}
    for g in mc.geradores:
        ger[g] = {"u": tuple(_valor(m.u[g, t], f"u[{g},{t}]", f) for t in T),
                  "p": tuple(_valor(m.p[g, t], f"p[{g},{t}]", f) for t in T)}
        if g in mc.geradores_pwl:
            ger[g]["q"] = tuple(_valor(m.q[g, t], f"q[{g},{t}]", f) for t in T)
            S = sorted({s for (gg, s) in m.GS if gg == g})
            seg[g] = tuple(next((s for s in S if (m.delta[g, s, t].value or 0) > 0.5), None) for t in T)
    cand = CandidatoDespacho(renovaveis=ren, baterias=bat, demandas=dem, descarte=desc, geradores=ger)
    despacho = {"renovaveis": ren, "baterias": {b: {**bat[b], "z_b": zb[b]} for b in bat}, "demandas": dem,
                "descarte": desc, "geradores": {g: {**ger[g], **({"segmento_ativo": seg[g]} if g in seg else {})}
                                                for g in ger}}
    return cand, despacho, f


def resolver(entrada: EntradaModeloEMS, configuracao: ConfiguracaoSolver, compromisso_fixo: dict | None = None, *,
             tolerancias: Tolerancias = Tolerancias(), _executor=None) -> ResultadoResolucao:
    t_ini = time.perf_counter()
    amb = verificar_ambiente()
    base = dict(motor_id=MOTOR_ID, versao_formulacao=getattr(entrada, "versao_formulacao", "?"),
                microrrede_uid=getattr(entrada, "microrrede_uid", "?"), cenario_uid=getattr(entrada, "cenario_uid", "?"),
                ambiente={**amb, "interface": INTERFACE}, hash_compromisso=_hash_compromisso(compromisso_fixo),
                configuracao=configuracao_registro(configuracao) if isinstance(configuracao, ConfiguracaoSolver) else {})

    def sem(classif: str, constat, tempos=None, tam=None, hash_e=None, term=None, st=None, extra=None) -> ResultadoResolucao:
        return ResultadoResolucao(**base, hash_entrada=hash_e, classificacao=classif, terminacao=term,
                                  status_solucao=st, solucao_primal=False, objetivo=None,
                                  limite_dual=(extra or {}).get("limite"), gap_abs=None, gap_rel=None,
                                  gap_highs=(extra or {}).get("gap_highs"), tempos_s=tempos or {}, tamanho=tam or {},
                                  candidato=None, despacho=None, custos_modelo={}, auditoria=None,
                                  estado_despacho="sem_despacho", aceito=False, constatacoes=tuple(constat))

    if not amb["disponivel"] and _executor is None:
        return sem("solver_indisponivel", [erro("solver_indisponivel", "ambiente", str(amb["erro"]))])
    constat: list[Constatacao] = list(validar_configuracao(configuracao))
    rel = validar_entrada(entrada)
    constat += list(rel.constatacoes)
    if rel.aceito:
        constat += preflight_3bp(entrada, compromisso_fixo)
    if any(c.severidade in ("erro", "pendente") for c in constat):
        return sem("bloqueado_validacao", constat)
    he = hash_entrada(entrada)

    from .modelo import construir_modelo
    t0 = time.perf_counter()
    mc = construir_modelo(entrada, compromisso_fixo or {})
    t_cons = time.perf_counter() - t0
    tam = _tamanho(mc.modelo)
    if mc.balanco_trivial_inviavel:
        constat.append(erro("balanco_trivialmente_inviavel", "M02",
                            f"Intervalos {mc.balanco_trivial_inviavel[:8]} sem nenhuma decisão e com balanço ≠ 0: "
                            "inviável sem chamar o solver (nenhuma folga é criada)."))
        return sem("inviavel", constat, {"construcao_s": t_cons}, tam, he, term="trivialmente_inviavel_na_construcao")

    exe = (_executor or _executar_highs)(mc.modelo, configuracao)
    tempos = {"construcao_s": t_cons, "solver_s": exe.get("tempo_solver_s"), "highs_s": exe.get("tempo_highs_s")}
    term, st = exe.get("terminacao"), exe.get("status_solucao")
    classif = classificar(term, st)
    inc, lim = exe.get("incumbente"), exe.get("limite")
    if classif not in DESPACHAVEIS:
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem(classif, constat, tempos, tam, he, term, st, {"limite": _finito(lim), "gap_highs": exe.get("gap_highs")})

    exe["carregar"]()
    cand, despacho, faltas = _extrair(mc, entrada)
    if faltas:
        constat.append(erro("valor_nao_carregado", "solucao", f"{len(faltas)} variável(is) sem valor finito "
                                                              f"({faltas[:5]}): nenhum despacho."))
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem(classif, constat, tempos, tam, he, term, st, {"limite": _finito(lim)})
    import pyomo.environ as pe
    custos_modelo = {k: float(pe.value(v)) for k, v in mc.expr_termos.items()}
    obj_modelo = float(pe.value(mc.modelo.J))
    custos_modelo["total"] = obj_modelo
    if inc is not None and math.isfinite(float(inc)) and abs(float(inc) - obj_modelo) > 1e-6 * max(1.0, abs(obj_modelo)):
        constat.append(erro("objetivo_incoerente", "solucao",
                            f"Objetivo do solver {inc} ≠ objetivo avaliado nos valores carregados {obj_modelo}."))
    cand = CandidatoDespacho(renovaveis=cand.renovaveis, baterias=cand.baterias, demandas=cand.demandas,
                             descarte=cand.descarte, geradores=cand.geradores, custos_reportados=dict(custos_modelo))
    aud = auditar(entrada, cand, tolerancias, compromisso_fixo=compromisso_fixo if entrada.geradores else None)
    ok = aud.aceito and not any(c.severidade in ("erro", "pendente") for c in constat)
    estado = ("aceito_otimo" if classif == "otimo" else "aceito_factivel_nao_otimo") if ok else "rejeitado_auditoria"
    ga, gr = gaps(inc, lim)
    tempos["total_s"] = time.perf_counter() - t_ini
    return ResultadoResolucao(**base, hash_entrada=he, classificacao=classif, terminacao=term, status_solucao=st,
                              solucao_primal=True, objetivo=_finito(inc) if inc is not None else obj_modelo,
                              limite_dual=_finito(lim), gap_abs=ga, gap_rel=gr, gap_highs=exe.get("gap_highs"),
                              tempos_s=tempos, tamanho=tam, candidato=cand, despacho=despacho,
                              custos_modelo=custos_modelo, auditoria=aud, estado_despacho=estado, aceito=ok,
                              constatacoes=tuple(constat), familias_nao_modeladas=aud.familias_nao_modeladas)


def _finito(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


__all__ = ["DESPACHAVEIS", "resolver"]
