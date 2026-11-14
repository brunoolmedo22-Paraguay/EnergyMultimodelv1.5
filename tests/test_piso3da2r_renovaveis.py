"""Piso 3D-A2-R — potencial renovável por UID a partir dos modelos físicos REAIS do SEEDS2 e preflight V2 (sem solver).

Microrredes do CATÁLOGO em diretório temporário; equipamentos reais dos catálogos (módulo CS6K-275P; aerogerador Vergnet
GEV MP C 275 kW); clima SINTÉTICO rotulado do Piso 2B. Os oráculos de potência (``potencia_*_independente``) são equações
reescritas no teste a partir das fichas do catálogo — não chamam o código sob teste. Nenhum teste chama o otimizador.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import piso3da2r_util as R  # noqa: E402
import piso3da_util as U  # noqa: E402

from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import preflight as PF  # noqa: E402
from integracao_v2 import renovaveis as RN  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.operation import preflight as P16  # noqa: E402
from seeds2.operation import scenarios as S  # noqa: E402
from seeds2.operation import service as SV  # noqa: E402

GHI = [0, 0, 0, 0, 0, 0, 100, 350, 600, 800, 950, 1000]
TAMB = [20, 20, 20, 21, 21, 22, 23, 25, 27, 29, 30, 31]
VENTO = [2.0, 3.0, 4.2, 5.0, 6.3, 7.0, 8.0, 9.4, 10.0, 11.2, 12.0, 14.0]


def _loja(tmp_path, **kw):
    reg = MicrogridRegistry(tmp_path / "dados", adopt_legacy=False)
    cfg = R.config_hibrida(**kw)
    reg.create(cfg)
    return reg.open(cfg["installation"]["uid"])


def _codigos(pf, nivel=PF.ERROR):
    return {i.code for i in pf.items if i.level == nivel}


def _erros(pf):
    return [i.message for i in pf.items if i.level == PF.ERROR]


def _tabela(**extra):
    return lambda doc: R.clima_tabela(doc, {"ghi_W_m2": GHI, "temperature_C": TAMB, "wind_speed_m_s": VENTO, **extra})


def _apto(pf):
    assert _codigos(pf) <= {"solver_indisponivel"}, _erros(pf)


# ====================================================================== estratégia (formato 2)
def test_novo_bloco_tem_secoes_de_renovaveis_vazias_e_formato_1_continua_legivel(tmp_path):
    store = _loja(tmp_path)
    doc = SV.create(store, name="x").document
    b = E.novo_bloco(doc)
    ids = R.ids(doc)
    assert b["format_version"] == E.FORMATO >= 2 and b["clima"] == {"semantica": None, "emissao_utc": None}
    assert set(b["renovaveis"]) == {ids["fv"], ids["eolica"]}
    assert b["renovaveis"][ids["fv"]]["eta_conversao_barramento"] is None            # nenhum valor físico presumido
    assert b["renovaveis"][ids["eolica"]]["hipotese_densidade"] is None
    assert E.erros_estruturais(b, doc) == []
    cams = {c for c, _ in E.pendencias(b, doc)}
    assert {"clima.semantica", "clima.emissao_utc", f"renovaveis.{ids['fv']}.eta_conversao_barramento",
            f"renovaveis.{ids['eolica']}.hipotese_densidade", f"renovaveis.{ids['fv']}.procedencia"} <= cams
    v1 = {k: v for k, v in copy.deepcopy(b).items() if k not in ("clima", "renovaveis", "pemfc")}
    v1["format_version"] = 1                                                      # bloco gravado pelo Piso 3D-A
    assert E.erros_estruturais(v1, doc) == []
    assert ("renovaveis" in {c for c, _ in E.pendencias(v1, doc)})                # renováveis participantes ⇒ pendente
    v2 = {k: v for k, v in copy.deepcopy(b).items() if k != "pemfc"}
    v2["format_version"] = 2                                                  # bloco gravado pelo Piso 3D-A2-R
    assert E.erros_estruturais(v2, doc) == []
    up = E.atualizar_bloco(v1, doc)
    assert up["format_version"] == E.FORMATO and set(up["renovaveis"]) == set(b["renovaveis"])


def test_valores_fora_do_dominio_e_declaracao_orfa_sao_erros_estruturais(tmp_path):
    store = _loja(tmp_path)
    doc = SV.create(store, name="x").document
    b = E.novo_bloco(doc)
    ids = R.ids(doc)
    b["renovaveis"][ids["fv"]]["eta_conversao_barramento"] = 1.2
    b["renovaveis"][ids["eolica"]]["hipotese_densidade"] = "ar_padrao_presumido"
    b["renovaveis"]["eq-000000000000"] = copy.deepcopy(b["renovaveis"][ids["fv"]])
    b["clima"]["semantica"] = "qualquer"
    txt = " | ".join(E.erros_estruturais(b, doc))
    assert "(0, 1]" in txt and "densidade" in txt and "órfã" in txt and "semântica" in txt


# ====================================================================== adaptador × oráculo independente
def test_potencial_fv_por_arranjo_igual_ao_oraculo_noct_e_nulo_a_noite(tmp_path):
    store = _loja(tmp_path, eolica=False, arranjos=2)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=_tabela(), renov_kw={"eta": 0.96}))
    _apto(pf)
    ds = pf.montagem.renovaveis
    assert len(ds) == 2 and all(d.tecnologia == "fv" and d.uid.startswith("arr-") for d in ds)
    assert {d.registro for d in ds} == {R.ids(pf.scenario.document)["fv"]}          # associação à usina preservada
    esperado = R.potencia_fv_independente(GHI, TAMB, eta=0.96)
    for d in ds:
        assert np.allclose(d.potencia_kW, esperado, rtol=1e-12, atol=1e-12)
        assert d.potencia_kW[:6] == (0.0,) * 6
        assert d.parametros["n_modulos"] == 20 and d.parametros["eta_conversao_barramento"] == 0.96
    # o modelo do núcleo recebe o potencial NO BARRAMENTO com base declarada e disponibilidade separada
    rs = {str(r.uid): r for r in pf.montagem.modelo.base.renovaveis}
    assert set(rs) == {d.uid for d in ds}
    assert all(r.base_potencial == "antes_da_disponibilidade" and r.tecnologia == "fv" for r in rs.values())


def test_potencial_eolico_igual_a_curva_do_catalogo_com_densidade_de_referencia(tmp_path):
    store = _loja(tmp_path, fv=False)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=_tabela()))
    _apto(pf)
    (d,) = pf.montagem.renovaveis
    assert d.uid == R.ids(pf.scenario.document)["eolica"] and d.tecnologia == "eolica"
    assert np.allclose(d.potencia_kW, R.potencia_eolica_independente(VENTO), rtol=0, atol=1e-12)
    assert d.potencia_kW[0] == 0.0 and d.potencia_kW[1] == 0.0                         # abaixo do cut-in (3,5 m/s)
    assert d.diagnostico["densidade"]["referencia"] == 12 and d.parametros["perda_generica_aplicada"] is False


def test_densidade_calculada_exige_pressao_e_usa_o_modelo(tmp_path):
    store = _loja(tmp_path, fv=False)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=_tabela(),
                                                    renov_kw={"densidade": "calculada_do_clima_previsto"}))
    assert "clima_insuficiente" in _codigos(pf), _erros(pf)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=_tabela(pressure_hPa=[950.0] * 12),
                                                    renov_kw={"densidade": "calculada_do_clima_previsto"}))
    _apto(pf)
    (d,) = pf.montagem.renovaveis
    assert d.diagnostico["densidade"]["seco"] == 12 and d.diagnostico["densidade"]["referencia"] == 0
    ref = R.potencia_eolica_independente(VENTO)
    assert sum(d.potencia_kW) < sum(ref)              # ar menos denso (950 hPa, ~25 °C) ⇒ menos potência que ρ_ref


def test_perda_generica_do_inventario_e_a_unica_perda_aplicada(tmp_path):
    store = _loja(tmp_path, fv=False, perda_generica=True)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=_tabela()))
    _apto(pf)
    (d,) = pf.montagem.renovaveis
    assert np.allclose(d.potencia_kW, R.potencia_eolica_independente(VENTO) * 0.97, rtol=1e-12, atol=1e-12)


def test_subamostras_sao_agregadas_pela_media_aritmetica_sem_interpolacao(tmp_path):
    store = _loja(tmp_path, eolica=False)
    g30 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 50, 150, 300, 400, 550, 650, 750, 850, 900, 1000, 980, 1010]
    t30 = [20.0 + 0.5 * i for i in range(24)]
    cl = lambda doc: R.clima_tabela(doc, {"ghi_W_m2": g30, "temperature_C": t30}, passo_s=1800)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=cl))
    _apto(pf)
    (d,) = pf.montagem.renovaveis
    sub = R.potencia_fv_independente(g30, t30)
    assert pf.montagem.clima.n == 2
    assert np.allclose(d.potencia_kW, sub.reshape(12, 2).mean(axis=1), rtol=1e-12, atol=1e-12)


def test_sujeira_zero_automatica_e_aceita_no_ems_v2_sem_confirmacao(tmp_path):
    """Zero automático do cadastro é hipótese válida, não impedimento de execução."""
    store = _loja(tmp_path, eolica=False, sujeira=None, arranjos=2)
    sc = R.criar_cenario_hibrido(store, clima=_tabela())
    fv = next(e for e in sc.document["inventory_ref"]["equipment"].values() if e["kind"] == "pv")
    assert len(fv["arrays"]) == 2
    assert all(a["soiling_pct"] == 0.0 and a["soiling_default"] for a in fv["arrays"])
    pf = PF.preparar(store, sc)
    _apto(pf)
    assert len(pf.montagem.renovaveis) == 2
    esperado = R.potencia_fv_independente(GHI, TAMB, sujeira=0.0)
    for d in pf.montagem.renovaveis:
        assert d.parametros["sujeira_pct"] == 0.0
        assert np.allclose(d.potencia_kW, esperado, rtol=1e-12, atol=1e-12)


def test_sujeira_realmente_ausente_continua_invalida(tmp_path):
    """Não converter None em zero silenciosamente; aceitar apenas zero numérico."""
    store = _loja(tmp_path, eolica=False)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=_tabela()))
    _apto(pf)
    cfg = R.config_hibrida(eolica=False)
    eq = next(e for e in cfg["equipment"] if e["kind"] == "pv")
    eq["arrays"][0]["soiling_pct"] = None
    with pytest.raises(RN.DerivacaoInvalida, match="NÃO declaradas"):
        RN.derivar_fv(eq, 1.0, pf.montagem.clima, 12)


# ====================================================================== bloqueios legíveis
@pytest.mark.parametrize("caso, codigo", [
    ("passo_que_nao_divide", "clima_insuficiente"), ("cobertura_incompleta", "clima_insuficiente"),
    ("emissao_futura", "previsao_nao_causal")])
def test_clima_insuficiente_ou_futuro_bloqueia(tmp_path, caso, codigo):
    store = _loja(tmp_path)
    if caso == "passo_que_nao_divide":
        n = 30
        cl = lambda doc: R.clima_tabela(doc, {"ghi_W_m2": [500.0] * n, "temperature_C": [25.0] * n,
                                              "wind_speed_m_s": [8.0] * n}, passo_s=2400)
        pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=cl))
    elif caso == "cobertura_incompleta":
        cl = lambda doc: R.clima_tabela(doc, {"ghi_W_m2": GHI[:10], "temperature_C": TAMB[:10],
                                              "wind_speed_m_s": VENTO[:10]})
        pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=cl))
    else:
        pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=_tabela(),
                                                        renov_kw={"emissao": "2026-01-01T02:00:00+00:00"}))
    assert codigo in _codigos(pf), _erros(pf)
    assert not pf.ok and pf.montagem is None or pf.montagem.modelo is None


def test_clima_ausente_bloqueia_sem_perfil_substituto(tmp_path):
    store = _loja(tmp_path)

    def mutar(doc):
        doc["forecasts"].pop("climate")
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, mutar=mutar))
    assert not pf.ok and any("CLIMÁTICA ausente" in m for m in _erros(pf))


@pytest.mark.parametrize("kw, trecho", [
    ({"turbina": R.TURBINA_ANALISE, "fv": False}, "ANÁLISE de pontos"),
    ({"eolica": False, "modo_arranjo": "declarado"}, "potência declarada"),
])
def test_equipamento_nao_derivavel_bloqueia_com_diagnostico(tmp_path, kw, trecho):
    store = _loja(tmp_path, **kw)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=_tabela()))
    assert not pf.ok
    msgs = [i.message for i in pf.items if i.level == PF.ERROR]
    assert any(trecho in m for m in msgs), msgs


def test_curva_legada_sem_corte_nao_e_extrapolada(tmp_path):
    store = _loja(tmp_path, fv=False, turbina="Nordex N117/2400")
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, clima=_tabela(wind_speed_m_s=VENTO[:-1] + [22.0])))
    assert "renovavel_nao_derivavel" in _codigos(pf) and any("extrapolação" in m for m in _erros(pf))


def test_declaracoes_renovaveis_ausentes_bloqueiam_sem_valor_de_respaldo(tmp_path):
    store = _loja(tmp_path)

    def mutar(doc):
        doc[E.CHAVE_BLOCO]["renovaveis"][R.ids(doc)["fv"]]["eta_conversao_barramento"] = None
        doc[E.CHAVE_BLOCO]["clima"]["semantica"] = None
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, mutar=mutar))
    assert "nao_declarado" in _codigos(pf) and pf.montagem is None
    txt = " | ".join(_erros(pf))
    assert "eta_conversao_barramento" in txt and "clima.semantica" in txt


def test_renovaveis_indisponiveis_sao_excluidas_e_a_missao_so_bateria_continua_apta(tmp_path):
    store = _loja(tmp_path)

    def mutar(doc):
        for k in ("fv", "eolica"):
            doc["initialization"]["equipment"][R.ids(doc)[k]]["availability"] = "indisponivel"
        doc["forecasts"].pop("climate")                     # sem renováveis participantes o clima não é exigido
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, mutar=mutar))
    _apto(pf)
    assert {x["kind"] for x in pf.excluded} == {"pv", "wind"} and pf.montagem.renovaveis == []
    assert pf.montagem.modelo.base.renovaveis == () and pf.montagem.doc_renovaveis is None


def test_custo_de_vertimento_declarado_chega_ao_modelo_por_uid(tmp_path):
    store = _loja(tmp_path)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, renov_kw={"c_curt": 0.05}))
    _apto(pf)
    rs = pf.montagem.modelo.base.renovaveis
    assert len(rs) == 2 and all(r.custo_curtailment.valor == 0.05 for r in rs)
    assert "curtailment_operacional" in pf.montagem.modelo.base.politica_objetivo.termos


def test_cenario_v2_com_renovaveis_continua_recusado_pelo_motor_v16(tmp_path):
    store = _loja(tmp_path)
    sc = R.criar_cenario_hibrido(store)
    assert S.engine(sc.document) == E.MOTOR_V2
    p16 = P16.prepare(store, sc)
    assert not p16.ok


def test_documento_de_derivacao_e_deterministico_e_comprometido(tmp_path):
    store = _loja(tmp_path)
    sc = R.criar_cenario_hibrido(store, clima=_tabela())
    a, b = PF.preparar(store, sc), PF.preparar(store, sc)
    assert a.montagem.doc_renovaveis == b.montagem.doc_renovaveis
    assert a.montagem.hashes["renovaveis"] == RN.sha_documento(a.montagem.doc_renovaveis)
    assert a.engine_inputs()["hashes"]["renovaveis"] == a.montagem.hashes["renovaveis"]
    doc = a.montagem.doc_renovaveis
    assert doc["clima"]["sha256_serie_normalizada"] == sc.document["forecasts"]["climate"]["data"]
    assert doc["realizacao"]["tipo"] == "igual_a_previsao" and len(doc["recursos"]) == 2
    assert all(len(r["potencial_kW"]) == 12 and r["hipoteses"] for r in doc["recursos"])
    _ = U
