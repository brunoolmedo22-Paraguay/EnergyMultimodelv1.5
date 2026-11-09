"""Piso 3C-3 — MILP de UMA janela com PCC contra HiGHS real (G1–G4, G9, G10, G12 estático, G14 MILP).

Resultados ESPERADOS = valores analíticos das docstrings de ``ems_v2.fixtures_3c3`` (nunca tirados do Pyomo).
Sem Pyomo/HiGHS: pulados explicitamente.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

import pyomo.environ as pe  # noqa: E402

from ems_v2 import fixtures_3c2 as F2  # noqa: E402
from ems_v2 import fixtures_3c3 as F  # noqa: E402
from ems_v2.milp.config import CONFIG_ANALITICA as C  # noqa: E402
from ems_v2.milp.modelo_3c3 import construir_modelo_3c3  # noqa: E402
from ems_v2.milp.solver import _executar_highs  # noqa: E402
from ems_v2.milp.solver_3c1 import resolver_3c1  # noqa: E402
from ems_v2.milp.solver_3c3 import resolver_3c3  # noqa: E402
from ems_v2.rede.auditor import CandidatoRede3C3, auditar_3c3  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
AP = dict(abs=1e-7)


def ok(r):
    assert r.aceito and r.estado_despacho == "aceito_otimo", ([c.codigo for c in r.constatacoes], r.auditoria and
                                                               r.auditoria.familias_reprovadas())
    return r


def test_g1_importacao_necessaria_diferenca_exata_dentro_do_limite():
    r = ok(resolver_3c3(F.caso_g1(), C))
    assert r.intercambio["P_imp"] == pytest.approx((20.0, 20.0), **AP) and max(r.intercambio["P_exp"]) <= 1e-9
    assert r.objetivo == pytest.approx(8.0, **AP) and r.custos_modelo["importacao_rede"] == pytest.approx(8.0, **AP)
    assert r.economia_rede["gasto_importacao_R"] == pytest.approx(8.0, **AP)
    assert r.economia_rede["receita_exportacao_R"] == pytest.approx(0.0, **AP)
    assert r.versao_formulacao == "v1.1-3C-3" and r.modo_conexao == "conectado" and set(r.hash_tarifas) == {
        "importacao", "exportacao"}
    assert "balanco" in r.auditoria.familias_verificadas and "pcc_exclusividade" in r.auditoria.familias_verificadas


def test_g1_limite_insuficiente_e_inviavel():
    e = F.caso_g1()
    e = replace(e, pcc=replace(e.pcc, limite_importacao=replace(e.pcc.limite_importacao, valores=(19.0, 25.0))))
    r = resolver_3c3(e, C)
    assert r.classificacao == "inviavel" and not r.aceito and r.despacho is None


def test_g2_exportacao_remunerada_e_sem_remuneracao_decisao_economica():
    r = ok(resolver_3c3(F.caso_g2(), C))
    assert r.intercambio["P_exp"] == pytest.approx((20.0, 20.0), **AP) and r.objetivo == pytest.approx(-3.0, **AP)
    assert r.economia_rede["receita_exportacao_R"] == pytest.approx(3.0, **AP)
    assert r.custos_modelo["exportacao_rede"] == pytest.approx(-3.0, **AP)          # crédito com sinal negativo
    s = ok(resolver_3c3(F.caso_g2("sem"), C))
    assert s.intercambio["P_exp"] == pytest.approx((20.0, 20.0), **AP) and s.objetivo == pytest.approx(0.0, **AP)
    assert "exportacao_rede" not in s.custos_modelo                                    # nenhum crédito presumido


def test_g3_exportacao_proibida_excedente_so_com_recursos_autorizados():
    r = ok(resolver_3c3(F.caso_g3(), C))
    assert r.intercambio["P_exp"] == (0.0, 0.0) and "w" not in r.intercambio
    assert r.objetivo == pytest.approx(0.875, **AP)
    assert r.candidato.baterias["syn-bess"]["P_c"] == pytest.approx((15.0, 15.0), **AP)
    assert r.candidato.renovaveis["syn-fv"]["C_oper"] == pytest.approx((5.0, 5.0), **AP)


def test_g4_pcc_indisponivel_nao_inventa_energia():
    r = resolver_3c3(F.caso_g4(), C)
    assert r.classificacao == "inviavel" and r.despacho is None and not r.aceito
    b = ok(resolver_3c3(F.caso_g4(com_bess=True), C))
    assert max(b.intercambio["P_imp"] + b.intercambio["P_exp"]) <= 1e-9 and b.objetivo == pytest.approx(0.5, **AP)


def test_g9_mudanca_tarifaria_troca_decisoes_com_fisica_igual():
    a, b = ok(resolver_3c3(F.caso_g9("A"), C)), ok(resolver_3c3(F.caso_g9("B"), C))
    assert a.intercambio["P_imp"] == pytest.approx((20.0, 0.0), **AP)
    assert b.intercambio["P_imp"] == pytest.approx((0.0, 20.0), **AP)
    assert a.objetivo == pytest.approx(1.25, **AP) == b.objetivo
    assert a.candidato.baterias["syn-bess"]["P_d"] == pytest.approx((0.0, 20.0), **AP)
    assert b.candidato.baterias["syn-bess"]["P_d"] == pytest.approx((20.0, 0.0), **AP)


def test_g10_exclusividade_impede_arbitragem_simultanea_e_relaxacao_a_demonstra():
    r = ok(resolver_3c3(F.caso_g10(), C))
    assert max(r.intercambio["P_imp"]) <= 1e-9 and max(r.intercambio["P_exp"]) <= 1e-9 and r.objetivo == pytest.approx(0.0, **AP)
    assert all(min(i, x) <= 1e-9 for i, x in zip(r.intercambio["P_imp"], r.intercambio["P_exp"]))
    # contraprova 1: SEM nenhuma exclusividade (só os limites contratados) o modelo arbitra 50 kW nos dois sentidos
    e = F.caso_g10()
    mc0 = construir_modelo_3c3(e)
    m0 = mc0.modelo
    m0.PCC1_imp.deactivate()
    m0.PCC1_exp.deactivate()
    m0.lim_i = pe.Constraint(m0.T, rule=lambda m, t: m.P_imp[t] <= 50.0)
    m0.lim_e = pe.Constraint(m0.T, rule=lambda m, t: m.P_exp[t] <= 50.0)
    _executar_highs(m0, C)["carregar"]()
    assert pe.value(m0.J) == pytest.approx(-10.0, abs=1e-6)
    # contraprova 2: relaxação LINEAR de w (envoltória convexa) ainda admite fluxos simultâneos (25 + 25 kW: R$ −5)
    mc = construir_modelo_3c3(e)
    mc.modelo.w_pcc.domain = pe.UnitInterval
    exe = _executar_highs(mc.modelo, C)
    exe["carregar"]()
    assert pe.value(mc.modelo.J) == pytest.approx(-5.0, abs=1e-6)
    pi = tuple(pe.value(mc.modelo.P_imp[t]) for t in range(2))
    px = tuple(pe.value(mc.modelo.P_exp[t]) for t in range(2))
    assert min(pi) > 1.0 and min(px) > 1.0
    # o auditor independente REJEITA essa candidata relaxada (exclusividade e integralidade de w)
    cand = r.candidato
    cr = CandidatoRede3C3(cand, {"P_imp": pi, "P_exp": px, "w": tuple(pe.value(mc.modelo.w_pcc[t]) for t in range(2))},
                          {"curtailment_operacional": 0.0, "importacao_rede": 0.25 * 0.1 * sum(pi),
                           "exportacao_rede": -0.25 * 0.5 * sum(px), "total": pe.value(mc.modelo.J)})
    aud = auditar_3c3(e, cr)
    assert not aud.aceito and "pcc_exclusividade" in aud.familias_reprovadas()


def test_isolado_declarado_identico_ao_3c1():
    e = F.caso_isolado_equivalente()
    r3 = ok(resolver_3c3(e, C))
    r1 = resolver_3c1(e.compromisso, C)
    assert r1.aceito and r3.objetivo == pytest.approx(r1.objetivo, abs=0) and r3.intercambio == {}
    assert r3.candidato.baterias == r1.candidato.baterias and r3.candidato.renovaveis == r1.candidato.renovaveis
    assert r3.tamanho == r1.tamanho                     # nenhuma variável/restrição acrescentada


def test_m02_3c3_sem_pcc_coincide_com_m02_do_nucleo_e_modelo_linear_sem_folga():
    e = F.caso_g3()
    mc = construir_modelo_3c3(e)        # a verificação termo a termo roda na construção (levanta se divergir)
    m = mc.modelo
    assert not m.M02.active and m.M02_3c3.active
    from pyomo.repn import generate_standard_repn
    for c in m.component_data_objects(pe.Constraint, active=True):
        assert generate_standard_repn(c.body).polynomial_degree() <= 1
    assert not list(m.component_objects(pe.SOSConstraint))
    nomes = {v.name for v in m.component_objects(pe.Var)}
    assert nomes == {"P_R", "C_oper", "P_c", "P_d", "z_b", "e", "ell", "u", "p", "delta", "theta", "q", "y", "z",
                     "P_imp", "P_exp"}


def test_nucleo_com_commitment_preservado_com_pcc():
    """PEMFC 3C-1 (rampas, permanências, eventos) + PCC: transições continuam auditadas pelo núcleo."""
    mod = F2.modelo("3C3", 4, [30.0] * 4, [10.0] * 4)
    e = F.rede(mod, F.pcc(4, "3C3c", imp=50.0, exp=50.0), F.economia("3C3c", c_imp=2.0, c_exp=0.1, N=4), "3C3c")
    r = ok(resolver_3c3(e, C))
    fam = set(r.auditoria.familias_verificadas)
    assert {"transicao_M09", "rampa_M11a", "permanencia_M12", "balanco", "pcc_capacidade"} <= fam
    assert r.discretizacao and F2.FC in r.eventos


def test_resolver_3c1_recusa_entrada_3c3_e_resolver_3c3_recusa_3c1():
    assert resolver_3c1(F.caso_g1(), C).classificacao == "bloqueado_validacao"
    r = resolver_3c3(F.caso_g1().compromisso, C)
    assert r.classificacao == "bloqueado_validacao" and "formulacao_nao_3c3" in r.codigos()


# ------------------------------------------------------------------------------------------- G14 (MILP)
def _adult_pimp(cr):
    return replace(cr, pcc={**cr.pcc, "P_imp": (cr.pcc["P_imp"][0] + 1.0,) + tuple(cr.pcc["P_imp"][1:])})


def _adult_custo(cr):
    return replace(cr, custos_reportados={**cr.custos_reportados,
                                          "importacao_rede": cr.custos_reportados["importacao_rede"] - 0.5,
                                          "total": cr.custos_reportados["total"] - 0.5})


def _adult_simultaneo(cr):
    return replace(cr, pcc={**cr.pcc, "P_imp": tuple(x + 3.0 for x in cr.pcc["P_imp"]),
                            "P_exp": tuple(x + 3.0 for x in cr.pcc["P_exp"])})


@pytest.mark.parametrize("adult,familia", [(_adult_pimp, "balanco"), (_adult_custo, "custo"),
                                           (_adult_simultaneo, "pcc_exclusividade")])
def test_g14_solucao_alterada_apos_o_solver_e_rejeitada(adult, familia):
    r = resolver_3c3(F.caso_g1(), C, _adulterar=adult)
    assert r.classificacao == "otimo" and not r.aceito and r.estado_despacho == "rejeitado_auditoria"
    assert familia in r.auditoria.familias_reprovadas()


def test_g14_disponibilidade_e_tarifa_adulteradas_na_auditoria():
    e = F.caso_g1()
    r = ok(resolver_3c3(e, C))
    cr = CandidatoRede3C3(r.candidato, dict(r.intercambio), dict(r.custos_modelo))
    assert auditar_3c3(e, cr).aceito
    # a mesma solução contra um PCC indisponível em t = 0: rejeitada (capacidade e a = 0)
    ind = replace(e, pcc=replace(e.pcc, disponibilidade=replace(e.pcc.disponibilidade, serie=replace(
        e.pcc.disponibilidade.serie, valores=(0.0, 1.0)))))
    a = auditar_3c3(ind, cr)
    assert not a.aceito and "pcc_capacidade" in a.familias_reprovadas() and "intercambio_com_pcc_indisponivel" in a.codigos()
    # tarifa trocada depois da resolução: custo reportado não confere
    t2 = replace(e, economia=replace(e.economia, tarifa_importacao=F.tarifa("importacao", [0.9, 0.8], "G1")))
    b = auditar_3c3(t2, cr)
    assert not b.aceito and "custo" in b.familias_reprovadas()
