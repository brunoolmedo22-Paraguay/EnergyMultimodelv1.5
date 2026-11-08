"""Piso 3B-P — puerta G3B-P: casos analíticos resolvidos pelo MILP Pyomo + HiGHS REAL.

Os valores esperados são ANALÍTICOS (literais dos documentos / derivação comentada nas fixtures) ou obtidos por
ENUMERAÇÃO independente (sem Pyomo). Tolerâncias de asserção dos testes: 1e-6 nas unidades de cada grandeza
(kW, kWh, R$) e 1e-9 kg/h — explícitas e separadas das tolerâncias PROVISÓRIAS do auditor, que também precisa
aceitar cada despacho. Sintético/algébrico: não é validação física.
"""
from fractions import Fraction

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2 import fixtures_3b as X  # noqa: E402
from ems_v2 import reference as R  # noqa: E402
from ems_v2.milp.config import CONFIG_ANALITICA as CFG  # noqa: E402
from ems_v2.milp.modelo import construir_modelo  # noqa: E402
from ems_v2.milp.resultado import classificar  # noqa: E402
from ems_v2.milp.solver import _executar_highs, _extrair, resolver  # noqa: E402
from ems_v2.audit import auditar  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
KW = KWH = RS = 1e-6
KGH = 1e-9


def ok(f, *a, **kw):
    e, cp = f(*a, **kw)
    r = resolver(e, CFG, cp)
    assert r.classificacao == "otimo" and r.estado_despacho == "aceito_otimo" and r.aceito, (
        r.classificacao, r.estado_despacho, r.constatacoes, r.auditoria and r.auditoria.reprovados[:3])
    assert r.solucao_primal and r.auditoria.aceito and r.objetivo is not None
    return e, r


def test_ambiente_registrado_no_resultado():
    _, r = ok(X.a02)
    amb = r.ambiente
    assert amb["disponivel"] and amb["versoes"] == {"pyomo": "6.10.1", "highspy": "1.15.1"} and not amb["divergencias"]
    assert amb["interface"] == "pyomo.contrib.solver:highs" and amb["versao_highs"].startswith("1.15")
    assert r.configuracao == {"time_limit_s": 60.0, "threads": 1, "rel_gap": 0.0, "abs_gap": 0.0, "semente": 0,
                              "opcoes_highs": {}}
    assert len(r.hash_entrada) == 64 and set(r.tempos_s) >= {"construcao_s", "solver_s", "total_s"}
    assert r.rotulo.startswith("sintetico/algebrico")


# ----------------------------------------------------------------------------- A01, A02 (M01, M02, M03-v1.1)
def test_a01_sessenta_intervalos_sem_energia_terminal():
    e, r = ok(X.a01)
    P = r.despacho["renovaveis"]["syn-fv"]["P_R"]
    assert len(P) == 60 and r.despacho["demandas"]["syn-carga"]["ell"] == (0.0,) * 60
    assert sum(P) * float(e.malha.h_horas) == pytest.approx(60.0, abs=KWH)       # 60 kWh, não 61
    assert e.malha.n_fronteiras == 61


def test_a02_um_sexto_de_kWh():
    e, r = ok(X.a02)
    assert r.despacho["renovaveis"]["syn-fv"]["P_R"] == pytest.approx((10.0,), abs=KW)
    assert sum(r.despacho["renovaveis"]["syn-fv"]["P_R"]) * float(e.malha.h_horas) == pytest.approx(1 / 6, abs=KWH)


# ----------------------------------------------------------------------------- A03, A04 (M06–M08)
@pytest.mark.parametrize("delta,N", [(60, 1), (1, 60), (15, 4)])
def test_a03_descarga_com_eficiencia(delta, N):
    _, r = ok(X.a03, delta, N)
    b = r.despacho["baterias"]["syn-bess"]
    assert len(b["e"]) == N + 1 and len(b["P_d"]) == N
    assert b["P_d"] == pytest.approx((9.0,) * N, abs=KW) and b["P_c"] == pytest.approx((0.0,) * N, abs=KW)
    assert b["e"][-1] == pytest.approx(50.0, abs=KWH) and b["e"][0] == pytest.approx(60.0, abs=KWH)


def test_a04_carga_com_eficiencia():
    _, r = ok(X.a04)
    b = r.despacho["baterias"]["syn-bess"]
    assert b["P_c"] == pytest.approx((10.0,), abs=KW) and b["e"] == pytest.approx((60.0, 69.0), abs=KWH)
    assert r.objetivo == pytest.approx(0.0, abs=RS)


# ----------------------------------------------------------------------------- B01 (M03-v1.1, custo)
def test_b01a_indisponibilidade_sem_penalidade():
    _, r = ok(X.b01a)
    v = r.despacho["renovaveis"]["syn-fv"]
    assert v["P_R"] == pytest.approx((0.0,), abs=KW) and v["C_oper"] == pytest.approx((0.0,), abs=KW)
    assert r.objetivo == pytest.approx(0.0, abs=RS)
    assert r.auditoria.kpis_reconstruidos["E_indisp_kWh"]["syn-fv"] == pytest.approx(100.0, abs=KWH)
    assert r.auditoria.custos_reconstruidos["curtailment_operacional"] == pytest.approx(0.0, abs=RS)


def test_b01b_custo_operacional_reconstruido():
    _, r = ok(X.b01b)
    v = r.despacho["renovaveis"]["syn-fv"]
    assert v["P_R"] == pytest.approx((80.0,), abs=KW) and v["C_oper"] == pytest.approx((20.0,), abs=KW)
    assert r.objetivo == pytest.approx(10.0, abs=RS)
    assert r.auditoria.custos_reconstruidos["total"] == pytest.approx(10.0, abs=RS)
    assert r.custos_modelo["curtailment_operacional"] == pytest.approx(10.0, abs=RS)
    assert r.auditoria.kpis_reconstruidos["E_curt_oper_kWh"]["syn-fv"] == pytest.approx(20.0, abs=KWH)


# ----------------------------------------------------------------------------- A05 (B02)
def _resolver_fixado(e, cp, fixar):
    mc = construir_modelo(e, cp)
    fixar(mc.modelo)
    exe = _executar_highs(mc.modelo, CFG)
    cl = classificar(exe["terminacao"], exe["status_solucao"])
    if cl != "otimo":
        return cl, None, None
    exe["carregar"]()
    cand, desp, faltas = _extrair(mc, e)
    assert not faltas
    return cl, desp, auditar(e, cand)


def test_a05_feas_carregar_e_verter_sao_ambos_factiveis_com_objetivo_nulo():
    e, cp = X.a05_feas()
    assert e.politica_objetivo.termos == ()
    cl1, d1, a1 = _resolver_fixado(e, cp, lambda m: m.P_c["syn-bess", 0].fix(10.0))
    cl2, d2, a2 = _resolver_fixado(e, cp, lambda m: m.P_c["syn-bess", 0].fix(0.0))
    assert cl1 == cl2 == "otimo" and a1.aceito and a2.aceito
    assert d1["baterias"]["syn-bess"]["e"][1] == pytest.approx(59.0, abs=KWH)            # +9 kWh internos
    assert d1["renovaveis"]["syn-fv"]["C_oper"] == pytest.approx((0.0,), abs=KW)
    assert d2["renovaveis"]["syn-fv"]["C_oper"] == pytest.approx((10.0,), abs=KW)
    assert d2["baterias"]["syn-bess"]["e"][1] == pytest.approx(50.0, abs=KWH)
    # o próprio resolver também entrega UM ponto factível, sem otimalidade inferida (objetivo identicamente nulo)
    r = resolver(e, CFG, cp)
    assert r.aceito and r.objetivo == pytest.approx(0.0, abs=RS) and r.custos_modelo == {"total": 0.0}


def test_a05_opt_solver_encontra_a_carga():
    _, r = ok(X.a05_opt)
    b, v = r.despacho["baterias"]["syn-bess"], r.despacho["renovaveis"]["syn-fv"]
    assert b["P_c"] == pytest.approx((10.0,), abs=KW) and v["C_oper"] == pytest.approx((0.0,), abs=KW)
    assert b["e"][1] == pytest.approx(59.0, abs=KWH)
    assert r.custos_modelo["curtailment_operacional"] == pytest.approx(0.0, abs=RS)
    assert r.auditoria.custos_reconstruidos["curtailment_operacional"] == pytest.approx(0.0, abs=RS)
    assert r.gap_abs == pytest.approx(0.0, abs=RS)


# ----------------------------------------------------------------------------- A06 (M10, M14–M16)
def test_a06_pwl_sintetica_milp():
    e, r = ok(X.a06, preco_h2=10.0)
    g = r.despacho["geradores"]["syn-fc"]
    assert g["u"] == (1.0,) and g["p"] == pytest.approx((15.0,), abs=KW) and g["q"] == pytest.approx((0.9,), abs=KGH)
    assert g["q"][0] * float(e.malha.h_horas) == pytest.approx(0.015, abs=KGH)              # kg em 1 min
    assert r.custos_modelo["combustivel_h2"] == pytest.approx(10.0 * 0.015, abs=RS)
    assert r.auditoria.custos_reconstruidos["combustivel_h2"] == pytest.approx(0.15, abs=RS)
    assert g["segmento_ativo"] == (0,)
    assert set(r.familias_nao_modeladas) == {"rampas_M11", "permanencias_M12"}


def test_a06_on_a_5_kW_e_inviavel_e_off_tem_p_q_nulos():
    e, cp = X.a06(carga=5.0, p_ant=10.0)           # ON fixo, P_min = 10 kW: 5 kW não pertence ao domínio ON
    r = resolver(e, CFG, cp)
    assert r.classificacao == "inviavel" and not r.aceito and r.despacho is None
    e, cp = X.a06(carga=5.0)                       # estado inicial ON a 5 kW: rejeitado pelo contrato (antes do solver)
    r = resolver(e, CFG, cp)
    assert r.classificacao == "bloqueado_validacao" and "on_fora_do_dominio" in r.codigos()
    e, cp = X.a06(carga=0.0, ligado=False)
    _, r = ok(lambda: (e, cp))
    g = r.despacho["geradores"]["syn-fc"]
    assert g["u"] == (0.0,) and g["p"] == pytest.approx((0.0,), abs=KW) and g["q"] == pytest.approx((0.0,), abs=KGH)


@pytest.mark.parametrize("carga", [10.0, 11.0, 13.5, 14.0, 15.0, 16.0, 17.2, 20.0])
def test_pwl_nao_convexa_quatro_vertices_vazao_exata(carga):
    """Curva não convexa: q do MILP = interpolação EXATA (racional) do segmento adjacente, inclusive nos vértices."""
    _, r = ok(X.a06, carga=carga, curva=X.CURVA_NAO_CONVEXA, preco_h2=7.0)
    g = r.despacho["geradores"]["syn-fc"]
    esperado = float(R.vazao_pwl(X.CURVA_NAO_CONVEXA, Fraction(str(carga)), True))
    assert g["p"][0] == pytest.approx(carga, abs=KW) and g["q"][0] == pytest.approx(esperado, abs=KGH)


def _oraculo_pwl_bateria(carga, c_h2, c_thr, pdmax, curva):
    """Enumeração INDEPENDENTE (sem Pyomo): custo(p) linear por partes ⇒ mínimo em um ponto de quebra."""
    P = [Fraction(str(x)) for x, _ in curva]
    lo, hi = max(P[0], Fraction(str(carga)) - Fraction(str(pdmax))), min(P[-1], Fraction(str(carga)))
    candidatos = sorted({lo, hi} | {x for x in P if lo <= x <= hi})
    custos = [(Fraction(str(c_h2)) * R.vazao_pwl(curva, p, True) + Fraction(str(c_thr)) * (Fraction(str(carga)) - p), p)
              for p in candidatos]
    return min(custos)


@pytest.mark.parametrize("c_thr", [0.0, 0.2, 1.0, 1.5, 3.0])
def test_pwl_nao_convexa_com_bateria_igual_a_enumeracao(c_thr):
    e, cp = X.pwl_com_bateria(c_thr=c_thr)
    r = resolver(e, CFG, cp)
    assert r.aceito and r.classificacao == "otimo"
    custo_ref, p_ref = _oraculo_pwl_bateria(18.0, 10.0, c_thr, 6.0, X.CURVA_NAO_CONVEXA)
    assert r.objetivo == pytest.approx(float(custo_ref), abs=RS)          # h = 1 h
    g = r.despacho["geradores"]["syn-fc"]
    q_ref = float(R.vazao_pwl(X.CURVA_NAO_CONVEXA, Fraction(str(g["p"][0])).limit_denominator(10**9), True))
    assert g["q"][0] == pytest.approx(q_ref, abs=1e-7)
    if c_thr == 1.0:                                                       # caso documentado: vértice interno
        assert float(p_ref) == 16.0 and g["p"][0] == pytest.approx(16.0, abs=KW)
        assert g["q"][0] == pytest.approx(1.05, abs=KGH) and r.objetivo == pytest.approx(12.5, abs=RS)


# ----------------------------------------------------------------------------- A07, A08 (M04, M10)
def test_a07_minimo_tecnico_sem_sumidouro_e_inviavel():
    e, cp = X.a07()
    r = resolver(e, CFG, cp)
    assert r.classificacao == "inviavel" and r.terminacao == "provenInfeasible" and r.status_solucao == "noSolution"
    assert not r.aceito and r.despacho is None and r.candidato is None and r.objetivo is None
    assert r.estado_despacho == "sem_despacho" and e.politica_servico.descarte is None


def test_a08_servico_duro_inviavel():
    e, cp = X.a08(False)
    r = resolver(e, CFG, cp)
    assert r.classificacao == "inviavel" and not r.aceito and r.despacho is None


def test_a08_servico_degradado_minima_ens_5_kWh():
    e, r = ok(X.a08, True)
    ell = r.despacho["demandas"]["syn-carga"]["ell"]
    assert ell == pytest.approx((5.0,), abs=KW)
    assert sum(ell) * float(e.malha.h_horas) == pytest.approx(5.0, abs=KWH)                # ENS = 5 kWh
    assert r.despacho["geradores"]["syn-ger"]["p"] == pytest.approx((5.0,), abs=KW)
    assert r.objetivo == pytest.approx(2.0 * 5.0, abs=RS)                                  # V = 2 R$/kWh declarado
    assert r.auditoria.custos_reconstruidos["energia_nao_suprida"] == pytest.approx(10.0, abs=RS)


# ----------------------------------------------------------------------------- integridade analítica
def test_duas_baterias_heterogeneas_analitico():
    _, r = ok(X.duas_baterias)
    a, b = r.despacho["baterias"]["syn-bess-a"], r.despacho["baterias"]["syn-bess-b"]
    assert b["P_c"] == pytest.approx((6.25,), abs=KW) and a["P_c"] == pytest.approx((8.75,), abs=KW)
    assert a["e"] == pytest.approx((50.0, 57.875), abs=KWH) and b["e"] == pytest.approx((95.0, 100.0), abs=KWH)
    assert r.despacho["renovaveis"]["syn-fv"]["C_oper"] == pytest.approx((0.0,), abs=KW)
    assert r.objetivo == pytest.approx(1.1875, abs=RS)


def test_exclusividade_impede_ciclar_para_esconder_vertimento():
    _, r = ok(X.exclusividade)
    b = r.despacho["baterias"]["syn-bess"]
    assert b["P_c"] == pytest.approx((1 / 0.9,), abs=KW) and b["P_d"] == pytest.approx((0.0,), abs=KW)
    assert min(b["P_c"][0], b["P_d"][0]) <= KW and b["z_b"] == (1.0,)
    assert r.objetivo == pytest.approx(20 - 1 / 0.9, abs=RS)                # > 17,2 da solução com simultaneidade


def test_varios_uids_distintos():
    e, r = ok(X.multi_uid)
    d = r.despacho
    assert set(d["renovaveis"]) == {"syn-fv-a", "syn-fv-b"} and set(d["baterias"]) == {"syn-bess-a", "syn-bess-b"}
    assert set(d["demandas"]) == {"syn-carga-a", "syn-carga-b"} and set(d["geradores"]) == {"syn-fc", "syn-ter"}
    assert d["geradores"]["syn-ter"]["p"] == pytest.approx((0.0,) * 3, abs=KW)          # térmica OFF fixa
    assert d["renovaveis"]["syn-fv-b"]["P_R"][1] == pytest.approx(0.0, abs=KW)            # indisponível em t = 1
    for b in d["baterias"].values():
        assert len(b["e"]) == 4 and all(min(c, x) <= KW for c, x in zip(b["P_c"], b["P_d"]))
    assert r.auditoria.custos_reconstruidos["total"] == pytest.approx(r.objetivo, abs=RS)
