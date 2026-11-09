"""API de resolução do perfil 3C-4: ``resolver_3c4(entrada_3c4, configuracao, compromisso_parcial)``.

Interface NOVA e versionada; ``resolver``/``resolver_3c1``/``resolver_3c3`` NÃO foram alterados e continuam recusando
entradas de outro perfil. Mesma disciplina: ambiente → configuração → ``validar_entrada_3c4`` + ``preflight_3c3`` →
construção (``modelo_3c4``, composição sobre o construtor 3C-3) → HiGHS (``load_solutions=False``) → classificação →
extração (só se despachável) → coerência do objetivo → AUDITOR 3C-3 (núcleo, custos 3C-3 SEM o termo terminal) +
AUDITOR TERMINAL 3C-4 independente + integridade 3B-P → estado. "optimal" do HiGHS nunca basta.

``visao_nucleo_3c3`` produz, de um resultado 3C-4 ACEITO, a visão do despacho sobre a entrada núcleo 3C-3 (C-3C4-01).
"""
from __future__ import annotations

import dataclasses
import math
import time

from .. import MOTOR_ID
from ..audit import CandidatoDespacho, Tolerancias
from ..compromisso.memoria import garantia, memoria_terminal
from ..diagnostics import Constatacao, ContratoInvalido, erro
from ..hierarquia import FORMULACAO_3C4
from ..hierarquia.auditor import CandidatoTerminal3C4, auditar_terminal_3c4
from ..hierarquia.contrato import EntradaHierarquica3C4, hash_entrada_3c4, validar_entrada_3c4
from ..rede import FORMULACAO_3C3
from ..rede.auditor import CandidatoRede3C3, auditar_3c3
from ..rede.contrato import hash_entrada_3c3, hash_perfil
from ..rede.preflight import preflight_3c3
from .ambiente import INTERFACE, verificar_ambiente
from .config import ConfiguracaoSolver, configuracao_registro, validar_configuracao
from .integridade import verificar_testemunho
from .resultado import classificar, gaps
from .resultado_3c3 import ResultadoResolucao3C3
from .resultado_3c4 import ResultadoNucleo3C3De3C4, ResultadoResolucao3C4
from .solver import DESPACHAVEIS, OpcaoHighsInvalida, _executar_highs, _finito, _hash_compromisso, _tamanho, _valor
from .solver_3c3 import _extrair_3c3

NAO_MODELADAS_3C4 = ("auxiliares_evento_M05", "potencias_de_extremo_M11_EXT", "multimodo_M20", "fluxo_AC", "tensao",
                     "potencia_reativa", "frequencia", "protecao", "incerteza_estocastica_do_valor_futuro")


def _extrair_terminal(mc) -> tuple[dict, list[str]]:
    import pyomo.environ as pe
    m = mc.modelo
    faltas: list[str] = []
    sel = {}
    if hasattr(m, "T4_s"):
        sel["s"] = tuple(_valor(m.T4_s[i], f"T4_s[{i}]", faltas) for i in m.T4_I)
    if hasattr(m, "T4_delta"):
        sel["segmentos"] = tuple(_valor(m.T4_delta[i, j], f"T4_delta[{i},{j}]", faltas) for (i, j) in m.T4_S)
    rep = {}
    if mc.chave_terminal is not None:
        v = float(pe.value(mc.expr_termos[mc.chave_terminal]))
        if not math.isfinite(v):
            faltas.append(mc.chave_terminal)
        rep[mc.chave_terminal] = v
    return {"selecao": sel, "reportado": rep}, faltas


def resolver_3c4(entrada: EntradaHierarquica3C4, configuracao: ConfiguracaoSolver, compromisso_parcial: dict | None = None,
                 *, tolerancias: Tolerancias = Tolerancias(), _executor=None, _adulterar=None) -> ResultadoResolucao3C4:
    """``_adulterar`` (privado, SÓ para testes adversariais H16): função ``(candidato_rede, terminal) → (…, …)``
    aplicada ANTES das auditorias, para demonstrar que uma solução/termo alterado após o solver é rejeitado."""
    t_ini = time.perf_counter()
    amb = verificar_ambiente()
    erros_config = validar_configuracao(configuracao)
    rede = getattr(entrada, "rede", None)
    b = getattr(rede, "base", None)
    term = getattr(entrada, "terminal", None)
    base = dict(motor_id=MOTOR_ID, versao_formulacao=getattr(entrada, "versao_formulacao", "?"),
                microrrede_uid=getattr(b, "microrrede_uid", "?"), cenario_uid=getattr(b, "cenario_uid", "?"),
                ambiente={**amb, "interface": INTERFACE}, hash_compromisso=_hash_compromisso(compromisso_parcial),
                configuracao=configuracao_registro(configuracao, valida=not erros_config),
                politica_permanencia=getattr(getattr(getattr(rede, "compromisso", None), "politica_permanencia", None),
                                             "tipo", None),
                modo_conexao=getattr(getattr(rede, "pcc", None), "modo", None),
                tipo_terminal=getattr(term, "tipo", None),
                hash_sinal=getattr(getattr(term, "sinal", None), "selo", None))

    def sem(classif, constat, tempos=None, tam=None, hash_e=None, term_=None, st=None, extra=None, disc=None, bloq=()):
        return ResultadoResolucao3C4(**base, hash_entrada=hash_e, classificacao=classif, terminacao=term_,
                                     status_solucao=st, solucao_primal=False, objetivo=None,
                                     limite_dual=(extra or {}).get("limite"), gap_abs=None, gap_rel=None,
                                     gap_highs=(extra or {}).get("gap_highs"), tempos_s=tempos or {}, tamanho=tam or {},
                                     candidato=None, despacho=None, custos_modelo={}, auditoria=None,
                                     estado_despacho="sem_despacho", aceito=False, constatacoes=tuple(constat),
                                     familias_nao_modeladas=NAO_MODELADAS_3C4, discretizacao=disc or {},
                                     transicoes_bloqueadas=tuple(bloq))

    if not amb["disponivel"] and _executor is None:
        return sem("solver_indisponivel", [erro("solver_indisponivel", "ambiente", str(amb["erro"]))])
    constat: list[Constatacao] = list(erros_config)
    if not isinstance(entrada, EntradaHierarquica3C4) or entrada.versao_formulacao != FORMULACAO_3C4:
        constat.append(erro("formulacao_nao_3c4", "entrada",
                            f"resolver_3c4 só resolve EntradaHierarquica3C4 declarada {FORMULACAO_3C4!r}; entradas "
                            "3A/3B-P/3C-1/3C-3 usam os seus próprios resolvedores (sem ganhar termo terminal)."))
        return sem("bloqueado_validacao", constat)
    rel = validar_entrada_3c4(entrada)
    constat += [c for c in rel.constatacoes if c.severidade != "aviso"]
    if rel.aceito:
        constat += preflight_3c3(entrada.rede, compromisso_parcial)
    if any(c.severidade in ("erro", "pendente") for c in constat):
        return sem("bloqueado_validacao", constat)
    he = hash_entrada_3c4(entrada)
    base["hash_entrada_nucleo_3c3"] = hash_entrada_3c3(entrada.rede)
    ec = entrada.rede.economia
    base["hash_tarifas"] = {g: hash_perfil(p) for g, p in (("importacao", ec.tarifa_importacao),
                                                           ("exportacao", ec.tarifa_exportacao)) if p is not None}
    from .modelo_3c4 import construir_modelo_3c4
    t0 = time.perf_counter()
    mc = construir_modelo_3c4(entrada, compromisso_parcial)
    t_cons = time.perf_counter() - t0
    tam = _tamanho(mc.modelo)
    disc = {k: dataclasses.asdict(v) for k, v in mc.discretizacao.items()}
    bloq = mc.transicoes_bloqueadas
    if mc.base.balanco_trivial_inviavel:
        constat.append(erro("balanco_trivialmente_inviavel", "M02",
                            f"Intervalos {mc.base.balanco_trivial_inviavel[:8]} sem decisão e com balanço ≠ 0."))
        return sem("inviavel", constat, {"construcao_s": t_cons}, tam, he, term_="trivialmente_inviavel_na_construcao",
                   disc=disc, bloq=bloq)
    try:
        exe = (_executor or _executar_highs)(mc.modelo, configuracao)
        if not isinstance(exe, dict):
            raise TypeError(f"executor devolveu {type(exe).__name__}, esperado dict")
    except Exception as exc:  # noqa: BLE001 — falha vira ERRO controlado, nunca factibilidade
        cod = "opcao_highs_invalida" if isinstance(exc, OpcaoHighsInvalida) else "falha_solver"
        constat.append(erro(cod, "solver", f"{type(exc).__name__}: {exc}"))
        return sem("erro", constat, {"construcao_s": t_cons, "total_s": time.perf_counter() - t_ini}, tam, he,
                   term_="excecao", disc=disc, bloq=bloq)
    tempos = {"construcao_s": t_cons, "solver_s": exe.get("tempo_solver_s"), "highs_s": exe.get("tempo_highs_s")}
    term_, st = exe.get("terminacao"), exe.get("status_solucao")
    classif = classificar(term_, st)
    inc, lim = exe.get("incumbente"), exe.get("limite")
    if classif not in DESPACHAVEIS:
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem(classif, constat, tempos, tam, he, term_, st, {"limite": _finito(lim), "gap_highs": exe.get("gap_highs")},
                   disc=disc, bloq=bloq)
    try:
        exe["carregar"]()
        cand, despacho, pcc, faltas = _extrair_3c3(mc.rede, entrada.rede)
        tinfo, f2 = _extrair_terminal(mc)
        faltas += f2
    except Exception as exc:  # noqa: BLE001
        constat.append(erro("falha_carregamento", "solucao", f"{type(exc).__name__}: {exc}"))
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem("erro", constat, tempos, tam, he, term_, st, {"limite": _finito(lim)}, disc=disc, bloq=bloq)
    if faltas:
        constat.append(erro("valor_nao_carregado", "solucao", f"{len(faltas)} variável(is) sem valor finito "
                                                              f"({faltas[:5]}): nenhum despacho."))
        tempos["total_s"] = time.perf_counter() - t_ini
        return sem(classif, constat, tempos, tam, he, term_, st, {"limite": _finito(lim)}, disc=disc, bloq=bloq)
    import pyomo.environ as pe
    custos_modelo = {k: float(pe.value(v)) for k, v in mc.expr_termos.items() if k in mc.termos}
    obj_modelo = float(pe.value(mc.modelo.J))
    custos_modelo["total"] = obj_modelo
    if inc is not None and math.isfinite(float(inc)) and abs(float(inc) - obj_modelo) > 1e-6 * max(1.0, abs(obj_modelo)):
        constat.append(erro("objetivo_incoerente", "solucao",
                            f"Objetivo do solver {inc} ≠ objetivo avaliado nos valores carregados {obj_modelo}."))
    termos3 = tuple(entrada.rede.termos)
    custos3 = {k: custos_modelo[k] for k in termos3 if k in custos_modelo}
    custos3["total"] = math.fsum(custos3.values())
    cbase = CandidatoDespacho(renovaveis=cand.renovaveis, baterias=cand.baterias, demandas=cand.demandas,
                              descarte=cand.descarte, geradores=cand.geradores)
    cr = CandidatoRede3C3(cbase, None if pcc is None else {k: tuple(v) for k, v in pcc.items()}, custos3)
    ct = CandidatoTerminal3C4(dict(cand.baterias), dict(cand.geradores), dict(tinfo["reportado"]),
                              custos_modelo["total"], dict(tinfo["selecao"]))
    if _adulterar is not None:
        cr, ct = _adulterar(cr, ct)
    aud = auditar_3c3(entrada.rede, cr, tolerancias, compromisso_parcial)
    aud_t = auditar_terminal_3c4(entrada, ct, aud.custos_reconstruidos.get("total"), tolerancias)
    integ = verificar_testemunho(entrada.base, despacho, tolerancias)
    ok_aud = aud.aceito and aud_t.aceito and not any(c.severidade in ("erro", "pendente") for c in constat)
    if not aud_t.aceito:
        constat += list(aud_t.constatacoes)
    ok = ok_aud and integ.aceito
    if not integ.aceito:
        constat.append(erro("testemunho_milp_invalido", "integridade",
                            f"Testemunho auxiliar do MILP inconsistente: famílias {sorted(integ.familias_reprovadas())}."))
    estado = (("aceito_otimo" if classif == "otimo" else "aceito_factivel_nao_otimo") if ok
              else "rejeitado_auditoria" if not ok_aud else "rejeitado_integridade")
    cand = cr.base
    if cr.pcc is not None:
        despacho = {**despacho, "pcc": {str(entrada.rede.pcc.uid): dict(cr.pcc)}}
    u = {g: [1 if x > 0.5 else 0 for x in cand.geradores[g]["u"]] for g in cand.geradores}
    p = {g: list(cand.geradores[g]["p"]) for g in cand.geradores}
    mem = memoria_terminal(entrada.compromisso, u, p) if entrada.base.geradores else ()
    gar, res = garantia(mem)
    eventos = {g: {"partidas": sum(1 for x in cand.geradores[g]["y"] if x > 0.5),
                   "paradas": sum(1 for x in cand.geradores[g]["z"] if x > 0.5)} for g in cand.geradores}
    gi = custos_modelo.get("importacao_rede", 0.0)
    ge = custos_modelo.get("exportacao_rede", 0.0)
    econ = {"gasto_importacao_R": gi, "receita_exportacao_R": -ge, "liquido_rede_R": gi + ge} if entrada.rede.conectado \
        else {}
    chave = mc.chave_terminal
    theta = ct.termo_reportado.get(chave) if chave else None
    ga, gr = gaps(inc, lim)
    tempos["total_s"] = time.perf_counter() - t_ini
    return ResultadoResolucao3C4(
        **base, hash_entrada=he, classificacao=classif, terminacao=term_, status_solucao=st, solucao_primal=True,
        objetivo=_finito(inc) if inc is not None else obj_modelo, limite_dual=_finito(lim), gap_abs=ga, gap_rel=gr,
        gap_highs=exe.get("gap_highs"), tempos_s=tempos, tamanho=tam, candidato=cand, despacho=despacho,
        custos_modelo=custos_modelo, auditoria=aud, estado_despacho=estado, aceito=ok, constatacoes=tuple(constat),
        familias_nao_modeladas=NAO_MODELADAS_3C4, integridade=integ, discretizacao=disc, eventos=eventos,
        memoria_terminal=mem, obrigacoes_residuais_s=res, garantia_permanencia=gar, transicoes_bloqueadas=bloq,
        intercambio={} if cr.pcc is None else dict(cr.pcc), economia_rede=econ,
        termo_terminal={"chave": chave, "valor_R": theta, "valor_recalculado_R": aud_t.valor_recalculado_R,
                        "energias_kWh": dict(aud_t.energias_terminais_kWh), "modo": aud_t.modo,
                        "estado_geradores": {k: list(v) for k, v in aud_t.estado_terminal.items()},
                        "selecao": {k: list(v) for k, v in tinfo["selecao"].items()}},
        custo_operativo_previsto_R=custos3["total"], custo_futuro_estimado_R=theta, auditoria_terminal=aud_t)


def resolver_cobertura_3c4(entrada: EntradaHierarquica3C4, configuracao: ConfiguracaoSolver, faixas: dict) -> dict:
    """C-3C4-A02 — CERTIFICADO DE COBERTURA do planejador: o MESMO MILP 3C-4 da entrada, mas com a energia INICIAL de
    cada banco em ``faixas`` (uid → (E_lo, E_hi)) como VARIÁVEL de decisão (M08ini desativada; cotas da faixa), e o
    mesmo objetivo. Responde, sobre TODA a faixa (não só em pontos amostrados):

    * ``inviavel`` — o solver provou que NENHUMA energia inicial da faixa admite cauda factível (prova do B&B do HiGHS;
      não é uma prova independente — sem certificado de Farkas para MILP);
    * ``otimo``/``factivel_nao_otimo`` — existe energia factível; devolve um ponto E* (minimizador de V na faixa) que o
      planejador REAVALIA pela resolução auditada normal (nada é aceito sem auditoria);
    * outra classificação ⇒ indeterminado (limite de tempo, erro): o planejador não conclui nada.

    O despacho com energia inicial livre NÃO é auditável contra a entrada (e0 diferente): serve só como certificado de
    (in)viabilidade e para propor E*."""
    t0 = time.perf_counter()
    out = {"classificacao": "erro", "terminacao": None, "status_solucao": None, "energias": None, "objetivo": None,
           "limite_dual": None, "tempo_s": None, "constatacoes": ()}
    rel = validar_entrada_3c4(entrada)
    c = [x for x in rel.constatacoes if x.severidade != "aviso"]
    if rel.aceito:
        c += [x for x in preflight_3c3(entrada.rede, None) if x.severidade in ("erro", "pendente")]
    bats = {str(b.uid) for b in entrada.base.baterias}
    if set(faixas) != bats or any(not (isinstance(v, (tuple, list)) and len(v) == 2 and v[0] <= v[1]) for v in
                                  faixas.values()):
        c.append(erro("faixas_de_cobertura_invalidas", "faixas", f"Exigidas faixas (lo <= hi) para {sorted(bats)}."))
    if c:
        out.update(classificacao="bloqueado_validacao", constatacoes=tuple(c))
        return out
    from .modelo_3c4 import construir_modelo_3c4
    mc = construir_modelo_3c4(entrada, None)
    m = mc.modelo
    for u, (lo, hi) in faixas.items():
        m.M08ini[u].deactivate()
        m.e[u, 0].setlb(max(float(lo), m.e[u, 0].lb))
        m.e[u, 0].setub(min(float(hi), m.e[u, 0].ub))
    try:
        exe = _executar_highs(m, configuracao)
    except Exception as exc:  # noqa: BLE001
        out.update(constatacoes=(erro("falha_solver", "cobertura", f"{type(exc).__name__}: {exc}"),),
                   tempo_s=time.perf_counter() - t0)
        return out
    classif = classificar(exe.get("terminacao"), exe.get("status_solucao"))
    out.update(classificacao=classif, terminacao=exe.get("terminacao"), status_solucao=exe.get("status_solucao"),
               objetivo=_finito(exe.get("incumbente")), limite_dual=_finito(exe.get("limite")))
    if classif in DESPACHAVEIS:
        exe["carregar"]()
        faltas: list[str] = []
        out["energias"] = {u: _valor(m.e[u, 0], f"e[{u},0]", faltas) for u in sorted(faixas)}
        if faltas:
            out.update(classificacao="erro", energias=None)
    out["tempo_s"] = time.perf_counter() - t0
    return out


def visao_nucleo_3c3(res: ResultadoResolucao3C4, e: EntradaHierarquica3C4) -> ResultadoNucleo3C3De3C4:
    """Visão do despacho 3C-4 sobre a entrada NÚCLEO 3C-3 (C-3C4-01). Recusa resultado não aceito ou de outra entrada."""
    if not isinstance(res, ResultadoResolucao3C4) or res.versao_formulacao != FORMULACAO_3C4:
        raise ContratoInvalido([erro("resultado_nao_3c4", "resultado", "Visão núcleo só de resultado 3C-4.")])
    he = hash_entrada_3c4(e)
    if res.hash_entrada is not None and res.hash_entrada != he:
        raise ContratoInvalido([erro("resultado_de_outra_entrada", "resultado.hash_entrada", "Hash 3C-4 divergente.")])
    campos = {f.name: getattr(res, f.name) for f in dataclasses.fields(ResultadoResolucao3C3)}
    campos.update(versao_formulacao=FORMULACAO_3C3,
                  hash_entrada=hash_entrada_3c3(e.rede) if res.hash_entrada is not None else None)
    return ResultadoNucleo3C3De3C4(**campos, hash_entrada_3c4=res.hash_entrada, resultado_3c4=res)


__all__ = ["NAO_MODELADAS_3C4", "resolver_3c4", "resolver_cobertura_3c4", "visao_nucleo_3c3"]
