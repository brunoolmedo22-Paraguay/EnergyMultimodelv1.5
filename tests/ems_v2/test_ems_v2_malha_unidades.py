"""Malha temporal (M01, §13), unidades e cadeia bruto → normalizado. Sintético/algébrico."""
from fractions import Fraction

import pytest

from ems_v2 import fixtures as F
from ems_v2 import reference as R
from ems_v2.audit import auditar
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.parameters import Parametro, validar_parametro
from ems_v2.provenance import Procedencia
from ems_v2.timegrid import MalhaTemporal, validar_malha
from ems_v2.units import exato, para_canonica

pytestmark = pytest.mark.synthetic_algebraic
P = Procedencia("sintetico", "teste", "malha")


def test_a01_60_intervalos_61_fronteiras_60_kWh():
    e, c = F.a01()
    m = e.malha
    assert m.N == 60 and m.n_fronteiras == 61
    assert len(m.inicios_intervalos_utc()) == 60 and len(m.fronteiras_utc()) == 61
    assert (m.fronteiras_utc()[-1] - m.fronteiras_utc()[0]).total_seconds() == 3600
    assert R.energia_kWh([60] * 60, 1) == Fraction(60) == exato(F.CASOS["A01"].esperado["energia_kWh"])
    assert auditar(e, c).aceito


def test_a02_10_kW_um_minuto_um_sexto_exato():
    assert R.energia_kWh([10], 1) == Fraction(1, 6) == exato(F.CASOS["A02"].esperado["energia_kWh"])
    e, c = F.a02()
    assert e.malha.N == 1 and auditar(e, c).aceito


def test_instante_terminal_nao_e_integrado():
    m = F.malha(1, 60)
    assert m.verificar_vetor_intervalos([60.0] * 60, "x") == []
    cods = {c.codigo for c in m.verificar_vetor_intervalos([60.0] * 61, "x")}
    assert cods == {"instante_terminal_como_intervalo"}
    assert m.verificar_vetor_estados([0.0] * 61, "e") == []
    assert {c.codigo for c in m.verificar_vetor_estados([0.0] * 60, "e")} == {"comprimento_incompativel"}


def test_h_exato_e_energia_por_duracao():
    assert F.malha(1, 1).h_horas == Fraction(1, 60)
    assert F.malha(0.5, 2).h_horas == Fraction(1, 120)
    assert F.malha(60, 1).h_horas == 1


@pytest.mark.parametrize("delta,cod", [(0.0001, "delta_nao_inteiro_em_segundos"), (0, "delta_invalido"),
                                       (-1, "delta_invalido"), (float("nan"), "delta_invalido")])
def test_delta_invalido(delta, cod):
    m = MalhaTemporal(F.INICIO, delta, 1, 1, 1, 1)
    assert cod in {c.codigo for c in validar_malha(m)}


def test_campos_temporais_separados_e_regras():
    m = MalhaTemporal.de_minutos(F.INICIO, delta_min=1, horizonte_min=30, reotimizacao_min=1, missao_min=120,
                                 horizonte_previsao_min=120)
    assert (m.N, m.intervalos_reotimizacao, m.intervalos_missao) == (30, 1, 120)
    assert m.horizonte_otimizacao_min == 30 and m.reotimizacao_min == 1 and m.missao_min == 120
    with pytest.raises(ContratoInvalido) as ex:
        MalhaTemporal.de_minutos(F.INICIO, delta_min=2, horizonte_min=31, reotimizacao_min=2, missao_min=60)
    assert "horizonte_nao_divisivel" in ex.value.codigos
    with pytest.raises(ContratoInvalido) as ex:
        MalhaTemporal.de_minutos(F.INICIO, delta_min=1, horizonte_min=5, reotimizacao_min=6, missao_min=60)
    assert "reotimizacao_maior_que_horizonte" in ex.value.codigos
    with pytest.raises(ContratoInvalido) as ex:
        MalhaTemporal.de_minutos(F.INICIO, delta_min=1, horizonte_min=30, reotimizacao_min=1, missao_min=60,
                                 horizonte_previsao_min=20)
    assert "horizonte_previsao_insuficiente" in ex.value.codigos
    with pytest.raises(ContratoInvalido) as ex:
        MalhaTemporal.de_minutos(F.INICIO, delta_min=1, horizonte_min=30, reotimizacao_min=1, missao_min=60.5)
    assert "missao_nao_divisivel" in ex.value.codigos


def test_horizonte_alem_da_missao_e_hf_nao_declarado():
    cods = {(c.codigo, c.severidade) for c in validar_malha(MalhaTemporal(F.INICIO, 1, 30, 1, 10))}
    assert ("horizonte_alem_da_missao", "pendente") in cods
    assert ("horizonte_previsao_nao_declarado", "aviso") in cods


@pytest.mark.parametrize("inicio", ["2026-01-01T00:00:00", "2026-01-01 00:00", "ontem"])
def test_fuso_ambiguo_ou_invalido_rejeitado(inicio):
    cods = {c.codigo for c in validar_malha(MalhaTemporal(inicio, 1, 1, 1, 1, 1))}
    assert cods & {"fuso_ambiguo", "instante_invalido"}


def test_fuso_com_deslocamento_normalizado_para_utc():
    m = MalhaTemporal("2026-01-01T00:00:00-03:00", 1, 1, 1, 1, 1)
    assert validar_malha(m) == [] and m.inicio().hour == 3


def test_conversoes_explicitas():
    assert para_canonica(2500, "W")[:2] == (2.5, "kW")
    v, u, t = para_canonica(300, "R$/MWh")
    assert (v, u) == (0.3, "R$/kWh") and t.fator == "1/1000"
    assert para_canonica(69, "%")[:2] == (0.69, "1")
    assert para_canonica(10, "kW")[2] is None
    with pytest.raises(ContratoInvalido) as ex:
        para_canonica(1, "cv")
    assert "unidade_desconhecida" in ex.value.codigos


def test_parametro_bruto_preservado_e_cadeia_verificada():
    p = Parametro.de_bruto(5000, "W", P)
    assert (p.valor, p.unidade, p.valor_bruto, p.unidade_bruta) == (5.0, "kW", 5000.0, "W") and p.transformacoes
    assert validar_parametro(p, "p", unidade="kW", dominio="positivo") == []
    adulterado = Parametro(6.0, "kW", P, 5000.0, "W", p.transformacoes)
    assert "cadeia_transformacao_inconsistente" in {c.codigo for c in validar_parametro(adulterado, "p", unidade="kW",
                                                                                         dominio="positivo")}
    sem_registro = Parametro(5.0, "kW", P, 5000.0, "W")
    assert "transformacao_nao_registrada" in {c.codigo for c in validar_parametro(sem_registro, "p", unidade="kW",
                                                                                   dominio="positivo")}


@pytest.mark.parametrize("p,unidade,dominio,cod", [
    (None, "kW", "positivo", "parametro_ausente"),
    (Parametro(None, "kW", P), "kW", "positivo", "parametro_ausente"),
    (Parametro(float("nan"), "kW", P), "kW", "positivo", "valor_nao_finito"),
    (Parametro(0.0, "kWh", P), "kWh", "positivo", "capacidade_nula"),
    (Parametro(-1.0, "kW", P), "kW", "nao_negativo", "quantidade_negativa"),
    (Parametro(0.0, "1", P), "1", "eficiencia", "eficiencia_fora_do_dominio"),
    (Parametro(1.1, "1", P), "1", "eficiencia", "eficiencia_fora_do_dominio"),
    (Parametro(5.0, "W", P), "kW", "positivo", "unidade_nao_canonica"),
    (Parametro(5.0, "kWh", P), "kW", "positivo", "unidade_incompativel"),
    (Parametro(5.0, "kW", None), "kW", "positivo", "sem_procedencia"),
    (Parametro(5.0, "kW", Procedencia("nao_declarado", "x")), "kW", "positivo", "procedencia_nao_declarada"),
    (Parametro(True, "1", P), "1", "fracao", "parametro_nao_numerico"),
])
def test_parametros_invalidos(p, unidade, dominio, cod):
    assert cod in {c.codigo for c in validar_parametro(p, "p", unidade=unidade, dominio=dominio)}


def test_parametro_opcional_ausente_e_pendente_nao_presumido():
    c = validar_parametro(None, "p", unidade="R$/kWh", dominio="nao_negativo", obrigatorio=False)
    assert [(x.codigo, x.severidade) for x in c] == [("parametro_ausente", "pendente")]
