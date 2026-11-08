"""Cálculo algébrico de referência (racionais exatos) contra resultados ANALÍTICOS literais dos documentos.

Os valores esperados são literais (05_FIXTURES_Y_PUERTAS / 03_ORDEN_EJECUTIVA_3A), nunca produzidos pelo auditor.
Sintético/algébrico: não é validação física.
"""
from fractions import Fraction

import pytest

from ems_v2 import fixtures as F
from ems_v2 import reference as R

pytestmark = pytest.mark.synthetic_algebraic
X = F.CASOS


def esperado(caso, chave):
    return Fraction(X[caso].esperado[chave])


def test_a03_descarga_um_passo_de_uma_hora():
    e = R.trajetoria_energia_bess(60, [0], [9], 0.9, 0.9, 60)
    assert e == (Fraction(60), Fraction(50)) and e[1] == esperado("A03", "e1_kWh")
    assert e[1] / 100 == esperado("A03", "soc1")


def test_a03_sessenta_passos_de_um_minuto_equivalem():
    e = R.trajetoria_energia_bess(60, [0] * 60, [9] * 60, 0.9, 0.9, 1)
    assert len(e) == 61 and e[-1] == Fraction(50)


def test_a04_carga():
    e = R.trajetoria_energia_bess(60, [10], [0], 0.9, 0.9, 60)
    assert e[-1] == Fraction(69) == esperado("A04", "e1_kWh") and e[-1] / 100 == esperado("A04", "soc1")


def test_recorrencia_sem_recorte():
    """A referência não satura: descarga além do conteúdo produz energia negativa (o auditor rejeita)."""
    e = R.trajetoria_energia_bess(5, [0], [9], 0.9, 0.9, 60)
    assert e[-1] == Fraction(-5)


def test_autodescarga_declarada():
    e = R.trajetoria_energia_bess(100, [0], [0], 1, 1, 60, alpha=Fraction(99, 100))
    assert e[-1] == 99


def test_b01a_indisponibilidade_nao_e_curtailment():
    r = R.renovavel_v11([100], [0], [0], 60, 0.5)
    assert r.A_utilizavel_kW == (0,) and r.C_oper_kW == (0,)
    assert r.E_indisp_kWh == esperado("B01A", "E_indisp_kWh") == 100
    assert r.E_curt_oper_kWh == 0 and r.custo_curt_oper_R == esperado("B01A", "custo_R") == 0


def test_b01b_curtailment_operacional():
    r = R.renovavel_v11([100], [1], [80], 60, 0.5)
    assert r.C_oper_kW == (Fraction(20),) and r.E_curt_oper_kWh == 20 and r.E_indisp_kWh == 0
    assert r.custo_curt_oper_R == esperado("B01B", "custo_R") == 10


def test_b01_rejeita_energia_inexistente_e_disponibilidade_fracionaria():
    with pytest.raises(R.ForaDoDominio):
        R.renovavel_v11([100], [0], [10], 60, 0.5)          # usar potência indisponível
    with pytest.raises(ValueError):
        R.renovavel_v11([100], [0.5], [10], 60, 0.5)
    with pytest.raises(ValueError):
        R.renovavel_v11([float("nan")], [1], [0], 60, 0.5)   # ausente nunca vira zero


def test_a05_feas_balanco_e_ganho_interno_sem_otimalidade():
    assert 20 - 10 - 10 == int(X["A05-FEAS"].esperado["residuo_balanco_kW"])
    e = R.trajetoria_energia_bess(50, [10], [0], 0.9, 0.9, 60)
    assert e[1] - e[0] == esperado("A05-FEAS", "delta_e_kWh") == 9
    assert X["A05-FEAS"].esperado["otimalidade"] == "nao_inferida"


def test_a06_pwl_sintetica():
    V = ((10, 0.7), (20, 1.1))
    q = R.vazao_pwl(V, 15, True)
    assert q == esperado("A06", "q_kg_h") == Fraction(9, 10)
    assert R.massa_h2_kg(q, 1) == esperado("A06", "massa_kg") == Fraction(3, 200)
    assert R.vazao_pwl(V, 10, True) == Fraction(7, 10) and R.vazao_pwl(V, 20, True) == Fraction(11, 10)
    assert R.vazao_pwl(V, 0, False) == 0
    with pytest.raises(R.ForaDoDominio):
        R.vazao_pwl(V, 5, True)                       # ON abaixo de P_min = 10 kW
    with pytest.raises(R.ForaDoDominio):
        R.vazao_pwl(V, 5, False)                      # OFF com potência


def test_b05a_massa_de_modo_sem_duplicar_arranque_somente_referencia():
    caso = X["B05A"]
    assert caso.etapa == "especificacao_3C" and not caso.executado_por_solver
    assert R.massa_modo_kg(0.02, 10) == esperado("B05A", "massa_kg") == Fraction(1, 300)


def test_casos_so_especificacao_nao_sao_resultados_executados():
    """Condição F: A05-OPT, A07, A08 e B05A continuam especificação/referência teórica."""
    for cid in ("A05-OPT", "A07", "A08", "B05A"):
        c = X[cid]
        assert c.etapa in ("especificacao_3B", "especificacao_3C") and c.executado_por_solver is False
        assert "TEÓRICO" in c.observacao or "referência" in c.observacao
    for cid in ("A01", "A02", "A03", "A04", "B01A", "B01B", "A05-FEAS", "A06"):
        assert X[cid].etapa == "referencia_3A" and X[cid].executado_por_solver is False
    assert set(c.etapa for c in X.values()) <= set(F.ETAPAS)
