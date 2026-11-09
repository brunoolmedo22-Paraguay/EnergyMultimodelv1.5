"""Hotfix AUTORIZADO B3C4-10 (2ª auditoria do PR #17, HEAD auditado ``8f48aed``): resíduo numérico NEGATIVO do solver
nas variáveis de intercâmbio do PCC.

Reproduzido ANTES da correção (EVIDENCIA_3C4_EJECUCION §4.4): H9, perfil 3C-3 original, janela k = 10 (N_k = 2),
HiGHS ``optimal`` devolve ``P_imp[0] = -8.881784197001252e-16`` kW (variável NonNegativeReals, abaixo da cota 0 dentro
da tolerância de factibilidade primal 1e-7 do HiGHS); o auditor 3C-3 ACEITA a solução; ``plano_de_resultado_3c3``
(regra C-01, PR #16) a recusa ⇒ ``intercambio_programado_invalido`` ⇒ falha de integridade da missão.

Política ``residuo_numerico_pcc_v1`` (``ems_v2/rede/execucao.py``): SÓ na fronteira de extração dos resolvedores, SÓ
valores devolvidos pelo solver, ``v < 0`` com ``|v| <= min(16 u S_t, 1e-7, tolP_D07)`` ⇒ 0.0 com registro (bruto,
normalizado, diferença, limiar, escala, motivo); maiores ⇒ solução rejeitada. A regra C-01 NÃO muda: toda consigna/
programa externo com negativo (por menor que seja), NaN, ±Inf, bool ou incompleto continua recusado. A solução
normalizada é revalidada pelo auditor independente; a normalização é comprometida no registro 3C-0 (aviso + hash) e
no resumo da resolução, e é reconstruída na auditoria hierárquica a partir de artefatos selados.
"""
from __future__ import annotations

import math
from dataclasses import replace
from functools import lru_cache
from types import SimpleNamespace

import pytest

from ems_v2 import fixtures_3c3 as F3
from ems_v2 import fixtures_3c4 as F
from ems_v2.audit import Tolerancias
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.rede.execucao import (KAPPA_PCC, POLITICA_RESIDUO_PCC, TOL_FACTIBILIDADE_SOLVER, ExecutorAlgebricoConectado3C3,
                                  aviso_normalizacao_pcc, escala_balanco_pcc, limiar_residuo_pcc,
                                  normalizar_residuos_pcc, plano_de_resultado_3c3, programa_valido, validar_programa,
                                  valor_intercambio_valido)

from test_ems_v2_3c3_auditoria_pr16 import passo  # noqa: E402
from test_ems_v2_3c3_execucao import pol, res_g1  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic

try:
    import highspy  # noqa: F401
    import pyomo  # noqa: F401
    COM_SOLVER = True
except ImportError:
    COM_SOLVER = False
solver = pytest.mark.skipif(not COM_SOLVER, reason="Pyomo/HiGHS indisponíveis (requirements-ems_v2.txt)")

R_H9 = -8.881784197001252e-16           # valor literal devolvido pelo HiGHS em H9 (k = 10)
U = 2.0 ** -53
PCC = F3.PCC


def _desp(L=30.0, A=10.0, N=2):
    """Despacho extraído mínimo do G1 (carga L, FV A): as potências de decisão entram na escala S_t."""
    return {"renovaveis": {"syn-fv": {"P_R": (A,) * N}}, "baterias": {}, "geradores": {},
            "demandas": {"syn-carga": {"ell": (L,) * N}}, "descarte": None}


def _rede(imp, exp, sentidos="importacao_e_exportacao"):
    e = F3.caso_g1()
    return replace(e, pcc=F3.pcc(2, "B10", imp=imp, exp=exp, sentidos=sentidos))


# ================================================================================================ política (sem solver)
def test_residuo_do_h9_normalizado_com_registro_completo():
    e = F3.caso_g1()                                        # P̄_imp = 25, P̄_exp = 50; P_R = 10; ℓ = 30 (despacho sintético)
    pcc, normas, c = normalizar_residuos_pcc(e, {"P_imp": (R_H9, 20.0), "P_exp": (0.0, 0.0)}, _desp())
    assert c == [] and pcc == {"P_imp": (0.0, 20.0), "P_exp": (0.0, 0.0)}
    (n,) = normas
    S = math.fsum([1.0, 25.0, 50.0, 30.0, 10.0])
    assert (n.pcc_uid, n.grandeza, n.indice_janela) == (PCC, "P_imp", 0)
    assert (n.valor_bruto_kW, n.valor_normalizado_kW, n.diferenca_kW) == (R_H9, 0.0, -R_H9)
    assert n.escala_kW == S == 116.0 and n.limiar_kW == min(KAPPA_PCC * U * S, 1e-7, 1e-5 + 1e-7 * S)
    assert n.motivo == POLITICA_RESIDUO_PCC and "C-01 inalterada" in n.motivo
    a = aviso_normalizacao_pcc(n)
    assert a.severidade == "aviso" and a.codigo == "normalizacao_numerica_pcc" and a.caminho == f"pcc[{PCC}].P_imp[0]"
    for campo in (f"bruto={R_H9!r}", "normalizado=0.0", f"diferenca={-R_H9!r}", f"limiar={n.limiar_kW!r}",
                  "escala=116.0", "origem=solver"):
        assert campo in a.mensagem


def test_residuo_em_p_exp_recebe_o_mesmo_tratamento():
    pcc, normas, c = normalizar_residuos_pcc(F3.caso_g1(), {"P_imp": (20.0, 20.0), "P_exp": (0.0, R_H9)}, _desp())
    assert c == [] and pcc["P_exp"] == (0.0, 0.0) and pcc["P_imp"] == (20.0, 20.0)
    assert [(n.grandeza, n.indice_janela, n.valor_bruto_kW) for n in normas] == [("P_exp", 1, R_H9)]


@pytest.mark.parametrize("v", [-1e-9, -1e-6, -1e-3, -1.0, -20.0])
def test_negativo_maior_que_a_cota_rejeitado_sem_recorte(v):
    e = F3.caso_g1()
    pcc, normas, c = normalizar_residuos_pcc(e, {"P_imp": (v, 20.0), "P_exp": (0.0, 0.0)}, _desp())
    assert normas == () and pcc["P_imp"] == (v, 20.0)               # nada recortado
    assert [(x.codigo, x.severidade, x.caminho) for x in c] == [
        ("intercambio_negativo_fora_da_politica_numerica", "erro", f"pcc[{PCC}].P_imp[0]")]


def test_cota_exatamente_no_limiar_e_logo_acima():
    S = escala_balanco_pcc({"syn-fv|P_R": 10.0, "syn-carga|ell": 30.0}, 25.0, 50.0)
    eps = limiar_residuo_pcc(S, Tolerancias())
    ok = normalizar_residuos_pcc(F3.caso_g1(), {"P_imp": (-eps, 20.0), "P_exp": (0.0, 0.0)}, _desp())
    assert ok[2] == [] and ok[0]["P_imp"][0] == 0.0
    acima = -(eps + math.ulp(eps))
    ko = normalizar_residuos_pcc(F3.caso_g1(), {"P_imp": (acima, 20.0), "P_exp": (0.0, 0.0)}, _desp())
    assert ko[1] == () and {x.codigo for x in ko[2]} == {"intercambio_negativo_fora_da_politica_numerica"}


@pytest.mark.parametrize("imp,exp,v,normaliza", [
    (5.0, 5.0, -1e-12, False),          # S = 51 ⇒ ε = 16 u 51 ≈ 9,1e-14 < 1e-12
    (5000.0, 5000.0, -1e-12, True),     # S = 10041 ⇒ ε ≈ 1,8e-11 > 1e-12
    (5.0, 5.0, R_H9, True),
    (1e9, 1e9, -9e-8, True),            # 16 u S ≈ 3,6e-6 ⇒ ε limitado pela tolerância do SOLVER 1e-7
    (1e9, 1e9, -2e-7, False),           # acima da tolerância de factibilidade do solver ⇒ nunca resíduo
])
def test_limites_contratuais_distintos_escalam_a_cota(imp, exp, v, normaliza):
    e = _rede(imp, exp)
    pcc, normas, c = normalizar_residuos_pcc(e, {"P_imp": (v, 20.0), "P_exp": (0.0, 0.0)}, _desp())
    S = math.fsum([1.0, imp, exp, 30.0, 10.0])
    eps = min(KAPPA_PCC * U * S, TOL_FACTIBILIDADE_SOLVER, 1e-5 + 1e-7 * S)
    assert (-v <= eps) is normaliza
    if normaliza:
        assert c == [] and pcc["P_imp"][0] == 0.0 and normas[0].limiar_kW == eps and normas[0].escala_kW == S
    else:
        assert normas == () and {x.codigo for x in c} == {"intercambio_negativo_fora_da_politica_numerica"}


def test_cota_limitada_pela_tolerancia_D07():
    tol = Tolerancias(potencia_abs_kW=1e-18, potencia_rel_escala=0.0)       # D07 mais estrita que 16 u S
    pcc, normas, c = normalizar_residuos_pcc(F3.caso_g1(), {"P_imp": (R_H9, 20.0), "P_exp": (0.0, 0.0)}, _desp(), tol)
    assert normas == () and {x.codigo for x in c} == {"intercambio_negativo_fora_da_politica_numerica"}
    assert limiar_residuo_pcc(86.0, tol) == 1e-18


@pytest.mark.parametrize("pcc", [{"P_imp": (0.0, 20.0), "P_exp": (0.0, 0.0)},
                                 {"P_imp": (0.0, 0.0), "P_exp": (20.0, 1e-300)},
                                 {"P_imp": (-0.0, 25.0), "P_exp": (0.0, 0.0)},
                                 {"P_imp": (20.0, 20.0), "P_exp": (0.0, 0.0), "w": (1.0, 1.0)}])
def test_zero_e_positivos_inalterados(pcc):
    novo, normas, c = normalizar_residuos_pcc(F3.caso_g1(), pcc, _desp())
    assert c == [] and normas == ()
    assert {k: tuple(v) for k, v in novo.items()} == pcc
    assert all(a is b for k in pcc for a, b in zip(novo[k], pcc[k]))             # MESMOS objetos (nenhuma cópia)


@pytest.mark.parametrize("ruim", [float("nan"), float("inf"), -float("inf"), True, False, None, "0", -1e-300j])
def test_valor_extraido_nao_finito_ou_nao_real_rejeitado(ruim):
    pcc, normas, c = normalizar_residuos_pcc(F3.caso_g1(), {"P_imp": (20.0, 20.0), "P_exp": (ruim, 0.0)}, _desp())
    assert normas == () and {x.codigo for x in c} == {"intercambio_extraido_invalido"}


def test_isolado_ou_sem_pcc_nao_toca_em_nada():
    e = F3.caso_isolado_equivalente()
    assert normalizar_residuos_pcc(e, None, {}) == (None, (), [])
    x = {"P_imp": (R_H9,), "P_exp": (0.0,)}
    assert normalizar_residuos_pcc(e, x, {}) == (x, (), [])


# ================================================================================================ C-01 intacta
@pytest.mark.parametrize("v", [R_H9, -5e-324, -0.5 * TOL_FACTIBILIDADE_SOLVER, float("nan"), float("inf"), True, None])
def test_c01_valor_externo_continua_invalido(v):
    assert valor_intercambio_valido(v) is False
    assert programa_valido([20.0, v], 2) is False
    assert {c.codigo for c in validar_programa({0: (20.0, 0.0), 1: (v, 0.0)})} == {"programa_pcc_invalido"}
    assert {c.codigo for c in validar_programa({0: (0.0, v)})} == {"programa_pcc_invalido"}


def test_c01_programa_incompleto_continua_invalido():
    assert programa_valido([20.0], 2) is False and programa_valido((20.0, 20.0, 0.0), 2) is False
    assert {c.codigo for c in validar_programa({0: (20.0,)})} == {"programa_pcc_invalido"}


@pytest.mark.parametrize("sentido", ["P_imp", "P_exp"])
@pytest.mark.parametrize("tipo", ["sem_ajuste", "ajuste_local_algebrico"])
@pytest.mark.parametrize("com_programa", [False, True])
def test_c01_consigna_externa_minima_negativa_recusada_pelo_executor(sentido, tipo, com_programa):
    extra = {f"{PCC}|P_imp": 20.0, f"{PCC}|P_exp": 0.0}
    extra[f"{PCC}|{sentido}"] = R_H9                       # MESMO valor que a política normaliza vindo do solver
    ps = passo(tipo, com_programa, extra)
    assert not ps.exequivel and ps.falha == "dados" and ps.aplicado == {}
    assert {c.codigo for c in ps.constatacoes} == {"intercambio_programado_invalido"}


def test_c01_programa_externo_com_residuo_recusado_na_construcao():
    with pytest.raises(ContratoInvalido) as exc:
        ExecutorAlgebricoConectado3C3(F3.caso_g1(), {}, pol(), programa={0: (R_H9, 0.0), 1: (20.0, 0.0)})
    assert exc.value.codigos == {"programa_pcc_invalido"}


@pytest.mark.parametrize("imp", [(R_H9, 20.0), (20.0, -5e-324)])
def test_c01_resultado_que_contorna_o_resolvedor_continua_recusado_no_plano(imp):
    """Um resultado com resíduo que NÃO passou pela extração do resolvedor (fabricado/externo) não vira plano."""
    e = F3.caso_g1()
    r = SimpleNamespace(**{**vars(res_g1(e)), "intercambio": {"P_imp": imp, "P_exp": (0.0, 0.0)}})
    with pytest.raises(ContratoInvalido) as exc:
        plano_de_resultado_3c3(r, e)
    assert exc.value.codigos == {"intercambio_programado_invalido"}


# ================================================================================================ resolvedores (HiGHS)
def _resolver_3c3_com(e, f):
    import ems_v2.milp.solver_3c3 as S3
    from ems_v2.milp.config import CONFIG_ANALITICA
    real = S3.normalizar_residuos_pcc
    S3.normalizar_residuos_pcc = f
    try:
        return S3.resolver_3c3(e, CONFIG_ANALITICA)
    finally:
        S3.normalizar_residuos_pcc = real


def _injetar(g, t, v):
    """Simula o solver devolvendo ``v`` em ``g[t]`` (a política REAL é aplicada depois)."""
    def f(e, pcc, d, tol):
        x = {k: list(w) for k, w in pcc.items()}
        x[g][t] = v
        return normalizar_residuos_pcc(e, {k: tuple(w) for k, w in x.items()}, d, tol)
    return f


@solver
def test_resolver_3c3_sem_residuo_identico_e_sem_registro():
    from ems_v2.milp.config import CONFIG_ANALITICA
    from ems_v2.milp.solver_3c3 import resolver_3c3
    r = resolver_3c3(F3.caso_g1(), CONFIG_ANALITICA)
    assert r.aceito and r.intercambio["P_imp"] == (20.0, 20.0) and r.normalizacoes_numericas == ()
    assert "normalizacao_numerica_pcc" not in {c.codigo for c in r.constatacoes}


@solver
@pytest.mark.parametrize("caso,g,t", [("g2", "P_imp", 1), ("g1", "P_exp", 0)])
def test_resolver_3c3_residuo_do_solver_normalizado_e_revalidado(caso, g, t):
    e = F3.caso_g1() if caso == "g1" else F3.caso_g2()
    r = _resolver_3c3_com(e, _injetar(g, t, R_H9))
    assert r.aceito and r.estado_despacho == "aceito_otimo" and r.auditoria.aceito
    assert r.intercambio[g][t] == 0.0 and r.despacho["pcc"][PCC][g][t] == 0.0
    (n,) = r.normalizacoes_numericas
    assert (n.grandeza, n.indice_janela, n.valor_bruto_kW) == (g, t, R_H9)
    assert [c.codigo for c in r.constatacoes] == ["normalizacao_numerica_pcc"]
    p, pr = plano_de_resultado_3c3(r, e)                    # C-01 aceita o programa normalizado (0.0)
    assert (pr.importacao_programada_kW if g == "P_imp" else pr.exportacao_programada_kW)[t] == 0.0


@solver
@pytest.mark.parametrize("v", [-1e-6, -1e-3, float("nan")])
def test_resolver_3c3_residuo_fora_da_politica_rejeita_a_solucao(v):
    r = _resolver_3c3_com(F3.caso_g2(), _injetar("P_imp", 1, v))
    assert not r.aceito and r.estado_despacho == "rejeitado_auditoria" and r.normalizacoes_numericas == ()
    assert {c.codigo for c in r.constatacoes} <= {"intercambio_negativo_fora_da_politica_numerica",
                                                    "intercambio_extraido_invalido"}
    with pytest.raises(ContratoInvalido):
        plano_de_resultado_3c3(r, F3.caso_g2())


def _zera_importacao(e, pcc, d, tol):
    return {**pcc, "P_imp": (0.0,) + tuple(pcc["P_imp"][1:])}, (), []


def _troca_mantendo_balanco(e, pcc, d, tol):          # +5 importados e +5 exportados: balanço intacto
    return {**pcc, "P_imp": (25.0,) + tuple(pcc["P_imp"][1:]), "P_exp": (5.0,) + tuple(pcc["P_exp"][1:])}, (), []


@solver
@pytest.mark.parametrize("f,familias", [(_zera_importacao, {"balanco", "custo"}),
                                        (_troca_mantendo_balanco, {"pcc_sentido", "pcc_exclusividade", "custo"})])
def test_transformacao_que_quebra_balanco_ou_economia_rejeitada(f, familias):
    r = _resolver_3c3_com(F3.caso_g1(), f)
    assert not r.aceito and r.estado_despacho == "rejeitado_auditoria"
    assert familias <= set(r.auditoria.familias_reprovadas())


@solver
def test_resolver_3c4_normalizacao_maliciosa_rejeitada_pelo_auditor():
    from ems_v2.milp.config import CONFIG_ANALITICA
    from ems_v2.milp.solver_3c4 import resolver_3c4
    from test_ems_v2_3c4_apoio import entrada, entrada4, sinal, termo
    e4 = entrada4(entrada(), termo(sinal()))
    ok = resolver_3c4(e4, CONFIG_ANALITICA)
    assert ok.aceito and ok.normalizacoes_numericas == ()
    imp = ok.intercambio["P_imp"]
    t = next(i for i, v in enumerate(imp) if v > 0)

    def zera(e, pcc, d, tol):
        x = list(pcc["P_imp"])
        x[t] = 0.0
        return {**pcc, "P_imp": tuple(x)}, (), []
    r = resolver_3c4(e4, CONFIG_ANALITICA, _normalizar=zera)
    assert not r.aceito and r.estado_despacho == "rejeitado_auditoria"
    assert {"balanco", "custo"} <= set(r.auditoria.familias_reprovadas())

    def residuo(e, pcc, d, tol):
        x = list(pcc["P_exp"])
        x[t] = R_H9                                           # P_exp é 0 onde há importação
        return normalizar_residuos_pcc(e, {**pcc, "P_exp": tuple(x)}, d, tol)
    r = resolver_3c4(e4, CONFIG_ANALITICA, _normalizar=residuo)
    assert r.aceito and [n.grandeza for n in r.normalizacoes_numericas] == ["P_exp"]
    assert r.intercambio["P_exp"][t] == 0.0 and r.termo_terminal["valor_R"] == ok.termo_terminal["valor_R"]


# ================================================================================================ missão H9 (HiGHS)
@lru_cache(maxsize=None)
def _h9(estr):
    from ems_v2.hierarquia import experimentos as X
    return X.executar(F.h9_pemfc(), estr)


def _janela_normalizada(x):
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC
    r = x.resultado
    idx = [i for i, w in enumerate(r.registros) for z in r.registros_3c0
           if z.execucao_uid == w.conteudo.execucao_uid and CHAVE_HASH_NORMALIZACOES_PCC in z.hashes]
    assert len(idx) == 1
    i = idx[0]
    r0 = next(z for z in r.registros_3c0 if z.execucao_uid == r.registros[i].conteudo.execucao_uid)
    return i, r0


@solver
@pytest.mark.parametrize("estr", ["mpc_sem_sinal", "hier_ref_dura"])
def test_h9_residuo_normalizado_comprometido_e_reconstruido(estr):
    from ems_v2.hierarquia.auditoria import reconstruir_normalizacoes_pcc
    from ems_v2.ponte.canonico import sha256
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC
    x = _h9(estr)
    r = x.resultado
    assert r.situacao == "encerrada" and x.controlador.k == 12
    i, r0 = _janela_normalizada(x)
    w = r.registros[i].conteudo
    assert (w.janela.k, w.janela.N_k) == (10, 2)
    assert "normalizacao_numerica_pcc" in w.resolucao.codigos                    # origem: resolução do SOLVER
    (av,) = [c for c in r0.constatacoes if c.codigo == "normalizacao_numerica_pcc"]
    assert av.caminho == f"pcc[{F.PCC}].P_imp[0]" and f"bruto={R_H9!r}" in av.mensagem
    nz, c = reconstruir_normalizacoes_pcc(x.modelo, r.registros, r.registros_3c0, r.anexos_3c3)
    assert c == [] and [(n.grandeza, n.indice_janela, n.valor_bruto_kW) for n in nz] == [("P_imp", 0, R_H9)]
    assert r0.hashes[CHAVE_HASH_NORMALIZACOES_PCC] == sha256(nz)
    ax = next(a for a in r.anexos_3c3 if a.conteudo.execucao_uid == r0.execucao_uid)
    assert ax.conteudo.plano_rede.importacao_programada_kW[0] == 0.0            # programa = 0.0, não o bruto
    # janelas SEM normalização: nenhum aviso, nenhuma chave nova (registros/hashes históricos inalterados)
    outras = [z for z in r.registros_3c0 if z is not r0]
    assert all(CHAVE_HASH_NORMALIZACOES_PCC not in z.hashes and
               "normalizacao_numerica_pcc" not in {k.codigo for k in z.constatacoes} for z in outras)


@solver
def test_h9_auditorias_integrais_aceitam():
    from ems_v2.rede.auditoria import auditar_missao_conectada
    x = _h9("mpc_sem_sinal")
    r, c = x.resultado, x.controlador
    a3 = auditar_missao_conectada(r.registro_missao, r.registros, r.livro, x.modelo, c.cfg_rede,
                                  registros_3c0=r.registros_3c0, anexos=r.anexos_3c3, registro_rede=r.registro_rede,
                                  verdade=x.entorno._verdade)
    assert a3.aceito
    h = _auditar_hier(_h9("hier_ref_dura"))
    assert h.aceito and h.verificacoes["normalizacoes_pcc"] and len(h.normalizacoes_pcc) == 1


def _auditar_hier(x, **over):
    from ems_v2.hierarquia.auditoria import auditar_missao_hierarquica
    r, c = x.resultado, x.controlador
    a = dict(registros_3c0=r.registros_3c0, anexos=r.anexos_3c3, registro_rede=r.registro_rede,
             coordenacoes=r.coordenacoes, registro_hierarquico=r.registro_hierarquico, verdade=x.entorno._verdade)
    a.update(over)
    return auditar_missao_hierarquica(r.registro_missao, r.registros, r.livro, x.modelo, c.cfg_rede, c.cfg_plan, **a)


def _alterar_aviso(r0, **campos):
    """Reescreve o aviso de normalização do registro 3C-0 com campos alterados (``rehash`` recompõe o hash)."""
    from ems_v2.ponte.canonico import sha256
    from ems_v2.rede.auditoria import _RE_NORMALIZACAO
    from ems_v2.rede.execucao import NormalizacaoNumericaPCC
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC
    rehash = campos.pop("rehash", False)
    cs = list(r0.constatacoes)
    j = next(k for k, c in enumerate(cs) if c.codigo == "normalizacao_numerica_pcc")
    m = _RE_NORMALIZACAO.match(cs[j].mensagem)
    n = NormalizacaoNumericaPCC(F.PCC, "P_imp", 0, float(m["bruto"]), float(m["norm"]), float(m["dif"]),
                                float(m["lim"]), float(m["esc"]), m["motivo"])
    n = replace(n, **campos)
    cs[j] = aviso_normalizacao_pcc(n)
    hashes = dict(r0.hashes)
    if rehash:
        hashes[CHAVE_HASH_NORMALIZACOES_PCC] = sha256((n,))
    return replace(r0, constatacoes=tuple(cs), hashes=hashes)


ADULTERACOES = {
    # correção NÃO justificada: bruto bem além da cota (hash recomposto pelo adulterador)
    "bruto_fora_da_cota": (dict(valor_bruto_kW=-1e-3, diferenca_kW=1e-3, rehash=True),
                           {"normalizacao_pcc_fora_da_politica"}),
    # limiar inflado para "justificar" um bruto maior
    "limiar_inflado": (dict(valor_bruto_kW=-1e-9, diferenca_kW=1e-9, limiar_kW=1e-7, rehash=True),
                       {"normalizacao_pcc_fora_da_politica"}),
    # escala alterada (não reconstruível do plano + modelo)
    "escala_alterada": (dict(escala_kW=1e9, rehash=True), {"normalizacao_pcc_fora_da_politica"}),
    # diferença incoerente com o bruto
    "diferenca_incoerente": (dict(diferenca_kW=1.0, rehash=True), {"normalizacao_pcc_fora_da_politica"}),
    # motivo/política trocados
    "motivo_trocado": (dict(motivo="recorte_livre", rehash=True), {"normalizacao_pcc_fora_da_politica"}),
    # aviso alterado SEM recompor o hash comprometido antes do selo
    "aviso_sem_rehash": (dict(valor_bruto_kW=-1e-14, diferenca_kW=1e-14), {"normalizacao_pcc_nao_comprometida"}),
}


@solver
@pytest.mark.parametrize("nome", sorted(ADULTERACOES))
def test_auditoria_detecta_normalizacao_alterada_ou_injustificada(nome):
    from ems_v2.hierarquia.auditoria import reconstruir_normalizacoes_pcc
    campos, esperado = ADULTERACOES[nome]
    x = _h9("hier_ref_dura")
    r = x.resultado
    i, r0 = _janela_normalizada(x)
    alt = [(_alterar_aviso(z, **dict(campos)) if z is r0 else z) for z in r.registros_3c0]
    nz, c = reconstruir_normalizacoes_pcc(x.modelo, r.registros, alt, r.anexos_3c3)
    assert esperado <= {k.codigo for k in c}
    h = _auditar_hier(x, registros_3c0=alt)
    assert not h.aceito and h.verificacoes["normalizacoes_pcc"] is False


@solver
def test_auditoria_detecta_normalizacao_sem_origem_no_solver_e_sem_registro():
    from ems_v2.hierarquia.auditoria import reconstruir_normalizacoes_pcc
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC
    x = _h9("hier_ref_dura")
    r = x.resultado
    i, r0 = _janela_normalizada(x)
    # (a) a resolução selada não registra a normalização ⇒ origem no solver não provada
    w = r.registros[i]
    regs = list(r.registros)
    regs[i] = replace(w, conteudo=replace(w.conteudo, resolucao=replace(
        w.conteudo.resolucao, codigos=tuple(k for k in w.conteudo.resolucao.codigos
                                            if k != "normalizacao_numerica_pcc"))))
    assert {k.codigo for k in reconstruir_normalizacoes_pcc(x.modelo, regs, r.registros_3c0, r.anexos_3c3)[1]} == {
        "normalizacao_pcc_sem_origem_no_solver"}
    # (b) aviso removido, hash mantido ⇒ não comprometida
    sem_aviso = replace(r0, constatacoes=tuple(k for k in r0.constatacoes if k.codigo != "normalizacao_numerica_pcc"))
    alt = [sem_aviso if z is r0 else z for z in r.registros_3c0]
    assert "normalizacao_pcc_nao_comprometida" in {
        k.codigo for k in reconstruir_normalizacoes_pcc(x.modelo, r.registros, alt, r.anexos_3c3)[1]}
    # (c) aviso mantido, hash removido ⇒ não comprometida
    sem_hash = replace(r0, hashes={k: v for k, v in r0.hashes.items() if k != CHAVE_HASH_NORMALIZACOES_PCC})
    alt = [sem_hash if z is r0 else z for z in r.registros_3c0]
    assert "normalizacao_pcc_nao_comprometida" in {
        k.codigo for k in reconstruir_normalizacoes_pcc(x.modelo, r.registros, alt, r.anexos_3c3)[1]}
    # (d) aviso ilegível
    cs = [replace(k, mensagem="bruto=?") if k.codigo == "normalizacao_numerica_pcc" else k for k in r0.constatacoes]
    alt = [replace(r0, constatacoes=tuple(cs)) if z is r0 else z for z in r.registros_3c0]
    assert "normalizacao_pcc_ilegivel" in {
        k.codigo for k in reconstruir_normalizacoes_pcc(x.modelo, r.registros, alt, r.anexos_3c3)[1]}


@solver
def test_auditoria_detecta_normalizacao_injetada_em_janela_com_importacao_real():
    """Um "resíduo" atribuído a uma janela cujo programa NÃO é 0.0 (consigna real) é recusado."""
    from ems_v2.hierarquia.auditoria import reconstruir_normalizacoes_pcc
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC
    from ems_v2.ponte.canonico import sha256
    x = _h9("hier_ref_dura")
    r = x.resultado
    i, r0 = _janela_normalizada(x)
    alvo = None
    for j, w in enumerate(r.registros):
        ax = next(a for a in r.anexos_3c3 if a.conteudo.execucao_uid == w.conteudo.execucao_uid)
        if ax.conteudo.plano_rede.importacao_programada_kW[0] > 0:
            alvo = (j, next(z for z in r.registros_3c0 if z.execucao_uid == w.conteudo.execucao_uid))
            break
    assert alvo is not None
    j, z = alvo
    (av,) = [k for k in r0.constatacoes if k.codigo == "normalizacao_numerica_pcc"]
    nz = reconstruir_normalizacoes_pcc(x.modelo, r.registros, r.registros_3c0, r.anexos_3c3)[0]
    z2 = replace(z, constatacoes=z.constatacoes + (av,), hashes={**z.hashes, CHAVE_HASH_NORMALIZACOES_PCC: sha256(nz)})
    w = r.registros[j]
    regs = list(r.registros)
    regs[j] = replace(w, conteudo=replace(w.conteudo, resolucao=replace(
        w.conteudo.resolucao, codigos=tuple(w.conteudo.resolucao.codigos) + ("normalizacao_numerica_pcc",))))
    alt = [z2 if q is z else q for q in r.registros_3c0]
    assert "normalizacao_pcc_fora_da_politica" in {
        k.codigo for k in reconstruir_normalizacoes_pcc(x.modelo, regs, alt, r.anexos_3c3)[1]}
