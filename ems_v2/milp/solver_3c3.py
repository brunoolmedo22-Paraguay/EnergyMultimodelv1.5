"""API de resolução do perfil 3C-3: ``resolver_3c3(entrada_3c3, configuracao, compromisso_parcial)``.

Interface NOVA e versionada; ``resolver`` (3B-P) e ``resolver_3c1`` (3C-1) NÃO foram alterados e continuam recusando
qualquer entrada que não seja do seu perfil (uma ``EntradaRede3C3`` não é aceita por ``resolver_3c1``).

Fluxo (mesma disciplina 3B-P/3C-1): ambiente → configuração → ``preflight_3c3`` (contrato 3C-3 + núcleo 3C-1 + PCC +
tarifas + compromisso parcial) → construção (``modelo_3c3``, composição sobre o construtor 3C-1) → HiGHS
(``load_solutions=False``) → classificação → carga/extração (só se despachável) → coerência do objetivo → AUDITOR
INDEPENDENTE 3C-3 (``rede.auditor``: compõe o auditor 3C-1 e substitui o balanço pelo balanço com PCC) + integridade
do testemunho auxiliar 3B-P (z_b, δ, θ) + integralidade/coerência do indicador de sentido w → estado final.
Nenhuma solução rejeitada pela auditoria ou pela integridade é aceita: "optimal" do HiGHS NÃO basta.
"""
from __future__ import annotations

import dataclasses
import math
import time

from .. import MOTOR_ID
from ..audit import CandidatoDespacho, Tolerancias
from ..compromisso.memoria import garantia, memoria_terminal
from ..diagnostics import Constatacao, erro
from ..rede import FORMULACAO_3C3
from ..rede.auditor import CandidatoRede3C3, auditar_3c3
from ..rede.contrato import EntradaRede3C3, hash_entrada_3c3, hash_perfil
from ..rede.execucao import aviso_normalizacao_pcc, normalizar_residuos_pcc
from ..rede.preflight import preflight_3c3
from .ambiente import INTERFACE, verificar_ambiente
from .config import ConfiguracaoSolver, configuracao_registro, validar_configuracao
from .integridade import verificar_testemunho
from .resultado import classificar, gaps
from .resultado_3c3 import ResultadoResolucao3C3
from .solver import DESPACHAVEIS, OpcaoHighsInvalida, _executar_highs, _finito, _hash_compromisso, _tamanho, _valor
from .solver_3c1 import _extrair_3c1


def _extrair_3c3(mc, e: EntradaRede3C3):
    cand, despacho, faltas = _extrair_3c1(mc.nucleo, e.compromisso)
    if not mc.conectado:
        return cand, despacho, None, faltas
    m, N = mc.modelo, mc.nucleo.base.N
    pcc = {"P_imp": tuple(_valor(m.P_imp[t], f"P_imp[{t}]", faltas) for t in range(N)),
           "P_exp": tuple(_valor(m.P_exp[t], f"P_exp[{t}]", faltas) for t in range(N))}
    if mc.dois_sentidos:
        pcc["w"] = tuple(_valor(m.w_pcc[t], f"w_pcc[{t}]", faltas) for t in range(N))
    despacho = {**despacho, "pcc": {str(e.pcc.uid): dict(pcc)}}
    return cand, despacho, pcc, faltas


def resolver_3c3(entrada: EntradaRede3C3, configuracao: ConfiguracaoSolver, compromisso_parcial: dict | None = None,
                 *, tolerancias: Tolerancias = Tolerancias(), _executor=None, _adulterar=None) -> ResultadoResolucao3C3:
    """``_adulterar`` (privado, SÓ para testes adversariais G14): função aplicada à candidata extraída ANTES da
    auditoria, para demonstrar que uma solução alterada após o solver é rejeitada."""
    t_ini = time.perf_counter()
    amb = verificar_ambiente()
    erros_config = validar_configuracao(configuracao)
    nuc = getattr(entrada, "compromisso", None)
    b = getattr(nuc, "base", None)
    base = dict(motor_id=MOTOR_ID, versao_formulacao=getattr(entrada, "versao_formulacao", "?"),
                microrrede_uid=getattr(b, "microrrede_uid", "?"), cenario_uid=getattr(b, "cenario_uid", "?"),
                ambiente={**amb, "interface": INTERFACE}, hash_compromisso=_hash_compromisso(compromisso_parcial),
                configuracao=configuracao_registro(configuracao, valida=not erros_config),
                politica_permanencia=getattr(getattr(nuc, "politica_permanencia", None), "tipo", None),
                modo_conexao=getattr(getattr(entrada, "pcc", None), "modo", None))
    nao_mod = ("auxiliares_evento_M05", "potencias_de_extremo_M11_EXT", "multimodo_M20", "terminal_energia",
               "valor_futuro", "fluxo_AC", "tensao", "potencia_reativa", "frequencia", "protecao")

    def sem(classif, constat, tempos=None, tam=None, hash_e=None, term=None, st=None, extra=None, disc=None, bloq=()):
        return ResultadoResolucao3C3(**base, hash_entrada=hash_e, classificacao=classif, terminacao=term,
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
    if not isinstance(entrada, EntradaRede3C3) or entrada.versao_formulacao != FORMULACAO_3C3:
        constat.append(erro("formulacao_nao_3c3", "entrada",
                            f"resolver_3c3 só resolve EntradaRede3C3 declarada {FORMULACAO_3C3!r}; entradas 3A/3B-P/3C-1 "
                            "usam os seus próprios resolvedores (sem ganhar capacidades implicitamente)."))
        return sem("bloqueado_validacao", constat)
    constat += preflight_3c3(entrada, compromisso_parcial)
    if any(c.severidade in ("erro", "pendente") for c in constat):
        return sem("bloqueado_validacao", constat)
    he = hash_entrada_3c3(entrada)
    ht = {g: hash_perfil(p) for g, p in (("importacao", entrada.economia.tarifa_importacao),
                                         ("exportacao", entrada.economia.tarifa_exportacao)) if p is not None}
    base["hash_tarifas"] = ht
    from .modelo_3c3 import construir_modelo_3c3
    t0 = time.perf_counter()
    mc = construir_modelo_3c3(entrada, compromisso_parcial)
    t_cons = time.perf_counter() - t0
    tam = _tamanho(mc.modelo)
    disc = {k: dataclasses.asdict(v) for k, v in mc.discretizacao.items()}
    if mc.base.balanco_trivial_inviavel:
        constat.append(erro("balanco_trivialmente_inviavel", "M02",
                            f"Intervalos {mc.base.balanco_trivial_inviavel[:8]} sem decisão e com balanço ≠ 0."))
        return sem("inviavel", constat, {"construcao_s": t_cons}, tam, he, term="trivialmente_inviavel_na_construcao",
                   disc=disc, bloq=mc.transicoes_bloqueadas)
    try:
        exe = (_executor or _executar_highs)(mc.modelo, configuracao)
        if not isinstance(exe, dict):
            raise TypeError(f"executor devolveu {type(exe).__name__}, esperado dict")
    except Exception as exc:  # noqa: BLE001 — falha vira ERRO controlado, nunca factibilidade
        cod = "opcao_highs_invalida" if isinstance(exc, OpcaoHighsInvalida) else "falha_solver"
        constat.append(erro(cod, "solver", f"{type(exc).__name__}: {exc}"))
        return sem("erro", constat, {"construcao_s": t_cons, "total_s": time.perf_counter() - t_ini}, tam, he,
                   term="excecao", disc=disc, bloq=mc.transicoes_bloqueadas)
    tempos = {"construcao_s": t_cons, "solver_s": exe.get("tempo_solver_s"), "highs_s": exe.get("tempo_highs_s")}
    term, st = exe.get("terminacao"), exe.get("status_solucao")
    classif = classificar(term, st)
    inc, lim = exe.get("incumbente"), exe.get("limite")
    if classif not in DESPACHAVEIS:
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem(classif, constat, tempos, tam, he, term, st, {"limite": _finito(lim), "gap_highs": exe.get("gap_highs")},
                   disc=disc, bloq=mc.transicoes_bloqueadas)
    try:
        exe["carregar"]()
        cand, despacho, pcc, faltas = _extrair_3c3(mc, entrada)
    except Exception as exc:  # noqa: BLE001
        constat.append(erro("falha_carregamento", "solucao", f"{type(exc).__name__}: {exc}"))
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem("erro", constat, tempos, tam, he, term, st, {"limite": _finito(lim)}, disc=disc,
                   bloq=mc.transicoes_bloqueadas)
    if faltas:
        constat.append(erro("valor_nao_carregado", "solucao", f"{len(faltas)} variável(is) sem valor finito "
                                                              f"({faltas[:5]}): nenhum despacho."))
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem(classif, constat, tempos, tam, he, term, st, {"limite": _finito(lim)}, disc=disc,
                   bloq=mc.transicoes_bloqueadas)
    # B3C4-10 (hotfix autorizado, PR #17): resíduos NEGATIVOS do solver em P_imp/P_exp — só valores extraídos do
    # solver, só |v| <= ε_pcc (rede.execucao.normalizar_residuos_pcc); maiores ⇒ rejeição; auditoria revalida tudo.
    pcc, normas, cn = normalizar_residuos_pcc(entrada, pcc, despacho, tolerancias)
    constat += cn + [aviso_normalizacao_pcc(n) for n in normas]
    if pcc is not None:
        despacho = {**despacho, "pcc": {str(entrada.pcc.uid): dict(pcc)}}
    import pyomo.environ as pe
    custos_modelo = {k: float(pe.value(v)) for k, v in mc.expr_termos.items() if k in mc.termos}
    obj_modelo = float(pe.value(mc.modelo.J))
    custos_modelo["total"] = obj_modelo
    if inc is not None and math.isfinite(float(inc)) and abs(float(inc) - obj_modelo) > 1e-6 * max(1.0, abs(obj_modelo)):
        constat.append(erro("objetivo_incoerente", "solucao",
                            f"Objetivo do solver {inc} ≠ objetivo avaliado nos valores carregados {obj_modelo}."))
    cbase = CandidatoDespacho(renovaveis=cand.renovaveis, baterias=cand.baterias, demandas=cand.demandas,
                              descarte=cand.descarte, geradores=cand.geradores)
    cr = CandidatoRede3C3(cbase, None if pcc is None else {k: tuple(v) for k, v in pcc.items()}, dict(custos_modelo))
    if _adulterar is not None:
        cr = _adulterar(cr)
    aud = auditar_3c3(entrada, cr, tolerancias, compromisso_parcial)
    integ = verificar_testemunho(entrada.base, despacho, tolerancias)
    ok_aud = aud.aceito and not any(c.severidade in ("erro", "pendente") for c in constat)
    ok = ok_aud and integ.aceito
    if not integ.aceito:
        constat.append(erro("testemunho_milp_invalido", "integridade",
                            f"Testemunho auxiliar do MILP inconsistente: famílias {sorted(integ.familias_reprovadas())}. "
                            "Despacho NÃO aceito."))
    estado = (("aceito_otimo" if classif == "otimo" else "aceito_factivel_nao_otimo") if ok
              else "rejeitado_auditoria" if not ok_aud else "rejeitado_integridade")
    cand = cr.base
    if cr.pcc is not None:
        despacho = {**despacho, "pcc": {str(entrada.pcc.uid): dict(cr.pcc)}}
    u = {g: [1 if x > 0.5 else 0 for x in cand.geradores[g]["u"]] for g in cand.geradores}
    p = {g: list(cand.geradores[g]["p"]) for g in cand.geradores}
    mem = memoria_terminal(entrada.compromisso, u, p) if entrada.base.geradores else ()
    gar, res = garantia(mem)
    eventos = {g: {"partidas": sum(1 for x in cand.geradores[g]["y"] if x > 0.5),
                   "paradas": sum(1 for x in cand.geradores[g]["z"] if x > 0.5)} for g in cand.geradores}
    gi = custos_modelo.get("importacao_rede", 0.0)
    ge = custos_modelo.get("exportacao_rede", 0.0)
    econ = {"gasto_importacao_R": gi, "receita_exportacao_R": -ge, "liquido_rede_R": gi + ge} if entrada.conectado else {}
    ga, gr = gaps(inc, lim)
    tempos["total_s"] = time.perf_counter() - t_ini
    return ResultadoResolucao3C3(
        **base, hash_entrada=he, classificacao=classif, terminacao=term, status_solucao=st, solucao_primal=True,
        objetivo=_finito(inc) if inc is not None else obj_modelo, limite_dual=_finito(lim), gap_abs=ga, gap_rel=gr,
        gap_highs=exe.get("gap_highs"), tempos_s=tempos, tamanho=tam, candidato=cand, despacho=despacho,
        custos_modelo=custos_modelo, auditoria=aud, estado_despacho=estado, aceito=ok, constatacoes=tuple(constat),
        familias_nao_modeladas=aud.familias_nao_modeladas, integridade=integ, discretizacao=disc, eventos=eventos,
        memoria_terminal=mem, obrigacoes_residuais_s=res, garantia_permanencia=gar,
        transicoes_bloqueadas=mc.transicoes_bloqueadas, intercambio={} if cr.pcc is None else dict(cr.pcc),
        economia_rede=econ, normalizacoes_numericas=normas)


__all__ = ["resolver_3c3"]
