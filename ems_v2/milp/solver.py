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
from .integridade import verificar_testemunho
from .resultado import ResultadoResolucao, classificar, gaps

DESPACHAVEIS = ("otimo", "factivel_nao_otimo")


def _canonico(x):
    """Representação canônica SEM PERDA e com tipo explícito (1, 1.0 e True são distintos; NaN/Inf preservados por
    ``float.hex``). Nunca levanta exceção: tipos desconhecidos viram ``["obj", nome_do_tipo]`` (sem ``repr``, que
    poderia conter endereços de memória). A VALIDAÇÃO dos valores {0, 1} é responsabilidade do preflight."""
    if x is None:
        return ["none"]
    if isinstance(x, bool):
        return ["bool", x]
    if isinstance(x, int):
        return ["int", str(x)]
    if isinstance(x, float):
        return ["float", x.hex()]
    if isinstance(x, str):
        return ["str", x]
    if isinstance(x, (list, tuple)):
        return ["seq", [_canonico(v) for v in x]]
    if isinstance(x, dict):
        itens = [[_canonico(k), _canonico(v)] for k, v in x.items()]
        return ["map", sorted(itens, key=lambda kv: json.dumps(kv[0], separators=(",", ":")))]
    return ["obj", type(x).__name__]


def _hash_compromisso(c) -> str | None:
    """Identidade determinística do programa de compromisso tal como recebido (inclusive inválido)."""
    try:
        txt = json.dumps(_canonico(c), separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(txt.encode("utf-8")).hexdigest()
    except Exception:  # noqa: BLE001 — identidade nunca derruba a resolução
        return None


class OpcaoHighsInvalida(ValueError):
    """Opção do HiGHS recusada pelo próprio HiGHS (nome, tipo ou faixa)."""


def _validar_opcoes_highs(opcoes: dict) -> None:
    """O HiGHS ignora opções inválidas sem falhar a resolução: valida cada uma ANTES, para não registrar uma
    configuração que não foi aplicada."""
    import highspy

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    for k, v in opcoes.items():
        if h.setOptionValue(k, v) != highspy.HighsStatus.kOk:
            raise OpcaoHighsInvalida(f"Opção HiGHS recusada: {k}={v!r}.")


def _executar_highs(modelo, config: ConfiguracaoSolver) -> dict:
    import pyomo.environ  # noqa: F401 — registra a fábrica
    from pyomo.contrib.solver.common.factory import SolverFactory

    opt = SolverFactory("highs")
    _validar_opcoes_highs({"random_seed": config.semente, **config.opcoes_highs})
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
            dl = tuple(tuple(_valor(m.delta[g, s, t], f"delta[{g},{s},{t}]", f) for s in S) for t in T)
            th = tuple(tuple(_valor(m.theta[g, s, t], f"theta[{g},{s},{t}]", f) for s in S) for t in T)
            seg[g] = {"delta": dl, "theta": th, "segmento_ativo": tuple(
                (lambda at: at[0] if len(at) == 1 else None)([s for s in S if math.isfinite(dl[t][s]) and dl[t][s] > 0.5])
                for t in T)}
    cand = CandidatoDespacho(renovaveis=ren, baterias=bat, demandas=dem, descarte=desc, geradores=ger)
    despacho = {"renovaveis": ren, "baterias": {b: {**bat[b], "z_b": zb[b]} for b in bat}, "demandas": dem,
                "descarte": desc, "geradores": {g: {**ger[g], **seg.get(g, {})} for g in ger}}
    return cand, despacho, f


def resolver(entrada: EntradaModeloEMS, configuracao: ConfiguracaoSolver, compromisso_fixo: dict | None = None, *,
             tolerancias: Tolerancias = Tolerancias(), _executor=None) -> ResultadoResolucao:
    t_ini = time.perf_counter()
    amb = verificar_ambiente()
    erros_config = validar_configuracao(configuracao)        # valida ANTES de preparar os metadados (C-3B-03)
    base = dict(motor_id=MOTOR_ID, versao_formulacao=getattr(entrada, "versao_formulacao", "?"),
                microrrede_uid=getattr(entrada, "microrrede_uid", "?"), cenario_uid=getattr(entrada, "cenario_uid", "?"),
                ambiente={**amb, "interface": INTERFACE}, hash_compromisso=_hash_compromisso(compromisso_fixo),
                configuracao=configuracao_registro(configuracao, valida=not erros_config))

    def sem(classif: str, constat, tempos=None, tam=None, hash_e=None, term=None, st=None, extra=None) -> ResultadoResolucao:
        return ResultadoResolucao(**base, hash_entrada=hash_e, classificacao=classif, terminacao=term,
                                  status_solucao=st, solucao_primal=False, objetivo=None,
                                  limite_dual=(extra or {}).get("limite"), gap_abs=None, gap_rel=None,
                                  gap_highs=(extra or {}).get("gap_highs"), tempos_s=tempos or {}, tamanho=tam or {},
                                  candidato=None, despacho=None, custos_modelo={}, auditoria=None,
                                  estado_despacho="sem_despacho", aceito=False, constatacoes=tuple(constat))

    if not amb["disponivel"] and _executor is None:
        return sem("solver_indisponivel", [erro("solver_indisponivel", "ambiente", str(amb["erro"]))])
    constat: list[Constatacao] = list(erros_config)
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

    try:
        exe = (_executor or _executar_highs)(mc.modelo, configuracao)
        if not isinstance(exe, dict):
            raise TypeError(f"executor devolveu {type(exe).__name__}, esperado dict")
    except Exception as exc:  # noqa: BLE001 — falha do solver vira resultado de ERRO controlado, nunca factibilidade
        cod = "opcao_highs_invalida" if isinstance(exc, OpcaoHighsInvalida) else "falha_solver"
        constat.append(erro(cod, "solver", f"{type(exc).__name__}: {exc}"))
        return sem("erro", constat, {"construcao_s": t_cons, "total_s": time.perf_counter() - t_ini}, tam, he,
                   term="excecao")
    tempos = {"construcao_s": t_cons, "solver_s": exe.get("tempo_solver_s"), "highs_s": exe.get("tempo_highs_s")}
    term, st = exe.get("terminacao"), exe.get("status_solucao")
    classif = classificar(term, st)
    inc, lim = exe.get("incumbente"), exe.get("limite")
    if classif not in DESPACHAVEIS:
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem(classif, constat, tempos, tam, he, term, st, {"limite": _finito(lim), "gap_highs": exe.get("gap_highs")})

    try:
        exe["carregar"]()
        cand, despacho, faltas = _extrair(mc, entrada)
    except Exception as exc:  # noqa: BLE001
        constat.append(erro("falha_carregamento", "solucao", f"{type(exc).__name__}: {exc}"))
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem("erro", constat, tempos, tam, he, term, st, {"limite": _finito(lim)})
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
    integ = verificar_testemunho(entrada, despacho, tolerancias)
    ok_aud = aud.aceito and not any(c.severidade in ("erro", "pendente") for c in constat)
    ok = ok_aud and integ.aceito
    if not integ.aceito:
        constat.append(erro("testemunho_milp_invalido", "integridade",
                            f"Testemunho auxiliar do MILP inconsistente: famílias {sorted(integ.familias_reprovadas())}, "
                            f"constatações {sorted(integ.codigos())}. Despacho NÃO aceito."))
    estado = (("aceito_otimo" if classif == "otimo" else "aceito_factivel_nao_otimo") if ok
              else "rejeitado_auditoria" if not ok_aud else "rejeitado_integridade")
    ga, gr = gaps(inc, lim)
    tempos["total_s"] = time.perf_counter() - t_ini
    return ResultadoResolucao(**base, hash_entrada=he, classificacao=classif, terminacao=term, status_solucao=st,
                              solucao_primal=True, objetivo=_finito(inc) if inc is not None else obj_modelo,
                              limite_dual=_finito(lim), gap_abs=ga, gap_rel=gr, gap_highs=exe.get("gap_highs"),
                              tempos_s=tempos, tamanho=tam, candidato=cand, despacho=despacho,
                              custos_modelo=custos_modelo, auditoria=aud, estado_despacho=estado, aceito=ok,
                              constatacoes=tuple(constat), familias_nao_modeladas=aud.familias_nao_modeladas,
                              integridade=integ)


def _finito(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


__all__ = ["DESPACHAVEIS", "OpcaoHighsInvalida", "resolver"]
