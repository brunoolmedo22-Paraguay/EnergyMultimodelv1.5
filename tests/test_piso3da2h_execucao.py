"""Piso 3D-A2-H — PEMFC/H₂ no EMS V2: preflight (sem solver) e missões REAIS (Pyomo + HiGHS) sobre o CATÁLOGO.

A política B04 do repositório (``b04-proposta-2``) foi APROVADA pelo responsável no PR #23: as missões com PEMFC rodam
pelo caminho NORMAL (sem aprovação simulada). ``politica_pendente_no_teste`` simula a REVOGAÇÃO para provar que uma
política pendente continua bloqueando (``b04_aguardando_aprovacao``). Dados sintéticos rotulados; modelos reais.
"""
from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import piso3da2h_util as H  # noqa: E402
import piso3da2r_util as R  # noqa: E402

from ems_v2 import contracts as K  # noqa: E402
from ems_v2.milp.ambiente import verificar_ambiente  # noqa: E402
from integracao_v2 import curva_h2 as CH  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from integracao_v2 import preflight as PF  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from seeds2.archive import exporter  # noqa: E402
from seeds2.archive.store import ArchiveStore  # noqa: E402
from seeds2.archive.view import StudyView  # noqa: E402
from seeds2.microgrid import config as C  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402

SOLVER = bool(verificar_ambiente().get("disponivel"))
requer_solver = pytest.mark.skipif(not SOLVER, reason="Pyomo/HiGHS não instalados (pip install -r requirements-ems_v2.txt)")
VENTO = [2.0, 3.0, 9.0, 10.0, 11.0, 12.0, 12.0, 10.0, 4.0, 3.0, 2.5, 2.0]
GHI = [0, 0, 0, 0, 0, 0, 100, 350, 600, 800, 950, 1000]


def _loja(raiz: Path, **kw):
    reg = MicrogridRegistry(raiz / "dados", adopt_legacy=False)
    cfg = H.config_pemfc(**kw)
    reg.create(cfg)
    return reg, reg.open(cfg["installation"]["uid"])


def _clima(doc):
    return R.clima_tabela(doc, {"ghi_W_m2": GHI, "temperature_C": [20.0] * 12, "wind_speed_m_s": VENTO})


def _hibrido(store, **kw):
    return H.criar_cenario_pemfc(store, demanda_kW=40.0, renov=True, clima=_clima, pemfc_kw={"preco": 10.0},
                                 mutar=lambda doc: doc[E.CHAVE_BLOCO]["pcc"].update(limite_importacao_kW=25.0), **kw)


def _codigos(pf, nivel=PF.ERROR):
    return {i.code for i in pf.items if i.level == nivel}


# ====================================================================== preflight (sem solver)
def test_politica_aprovada_libera_pemfc_pelo_caminho_normal(tmp_path):
    _r, store = _loja(tmp_path)
    pf = PF.preparar(store, H.criar_cenario_pemfc(store))
    assert not {"b04_aguardando_aprovacao", "b04_reprovada"} & _codigos(pf)
    assert _codigos(pf) <= {"solver_indisponivel"}, [i.message for i in pf.items if i.level == PF.ERROR]
    g = pf.montagem.modelo.base.geradores[0]
    assert g.curva_h2.classificacao == "real_certificada_b04" and K.certificado_b04_registrado(g.curva_h2.procedencia.sha256)


def test_politica_pendente_bloqueia_pemfc(tmp_path):
    _r, store = _loja(tmp_path)
    with H.politica_pendente_no_teste():                                  # REVOGAÇÃO simulada da aprovação
        pf = PF.preparar(store, H.criar_cenario_pemfc(store))
    assert "b04_aguardando_aprovacao" in _codigos(pf) and not pf.ok
    assert any(i.area == "pemfc" and i.level == PF.OK and "curva q(P) do modelo físico" in i.message for i in pf.items)
    with H.politica_pendente_no_teste(), pytest.raises(X.PreflightV2Error):
        X.submit(store, pf.scenario.scenario_uid, pf.scenario.version, X.new_request_id(), background=False)
    assert store.list_runs() == []


def test_declaracoes_ausentes_e_termo_de_combustivel_bloqueiam_sem_padrao(tmp_path):
    _r, store = _loja(tmp_path)

    def mutar(doc):
        x = doc[E.CHAVE_BLOCO]["pemfc"][H.pemfc_id(doc)]
        x["p_min_kW"] = None
        x["condicoes"]["pressao_catodo_kPag"] = None
        x["preco_h2_R_kg"] = None
        doc[E.CHAVE_BLOCO]["objetivo"]["termos"].remove("combustivel_h2")
    pf = PF.preparar(store, H.criar_cenario_pemfc(store, mutar=mutar))
    txt = " | ".join(i.message for i in pf.items if i.level == PF.ERROR)
    assert "nao_declarado" in _codigos(pf)
    assert "p_min_kW" in txt and "pressao_catodo_kPag" in txt and "preco_h2_R_kg" in txt and "combustivel_h2" in txt


def test_bloco_formato_2_com_pemfc_participante_fica_pendente(tmp_path):
    _r, store = _loja(tmp_path)

    def mutar(doc):
        b = doc[E.CHAVE_BLOCO]
        b.pop("pemfc")
        b["format_version"] = 2
    pf = PF.preparar(store, H.criar_cenario_pemfc(store, mutar=mutar))
    assert any("pemfc" in i.message.lower() and "formato 2" in i.message for i in pf.items if i.level == PF.ERROR)


def test_pemfc_indisponivel_e_excluida_e_missao_sem_ela_continua_apta(tmp_path):
    _r, store = _loja(tmp_path)

    def mutar(doc):
        doc["initialization"]["equipment"][H.pemfc_id(doc)].update(availability="indisponivel", state="desligada",
                                                                     units_on=0, power_kW=0.0)
    pf = PF.preparar(store, H.criar_cenario_pemfc(store, mutar=mutar))
    assert _codigos(pf) <= {"solver_indisponivel"}, [i.message for i in pf.items if i.level == PF.ERROR]
    assert {x["kind"] for x in pf.excluded} == {"pemfc"} and pf.montagem.modelo.base.geradores == ()


def test_termica_continua_bloqueada_por_m19(tmp_path):
    reg = MicrogridRegistry(tmp_path / "dados", adopt_legacy=False)
    cfg = H.config_pemfc()
    C.add_equipment(cfg, C.new_equipment("thermal", "Gerador diesel", tag="TER-01", params={
        "dynamic": "local_generator", "pmax_kW": 60.0, "pmin_kW": 15.0, "cvu_rs_MWh": 1200.0, "startup_cost_rs": 40.0}))
    reg.create(cfg)
    store = reg.open(cfg["installation"]["uid"])
    pf = PF.preparar(store, H.criar_cenario_pemfc(store))
    assert any("M19" in i.message for i in pf.items if i.level == PF.ERROR)


def test_curva_gerada_uma_vez_por_configuracao_e_massas_do_modelo_dinamico(tmp_path):
    _r, sa = _loja(tmp_path / "a")
    _r, sb = _loja(tmp_path / "b")                 # outra microrrede, MESMA configuração física declarada
    pa = PF.preparar(sa, H.criar_cenario_pemfc(sa, pemfc_kw={"p_min": 11.5}))
    n = CH.GERACOES["n"]
    pb = PF.preparar(sb, H.criar_cenario_pemfc(sb, pemfc_kw={"p_min": 11.5}))
    pa2 = PF.preparar(sa, pa.scenario)
    assert CH.GERACOES["n"] == n                 # reutilizada (mesma impressão digital), nunca regenerada
    ua, ub = next(iter(pa.montagem.pemfc.values())), next(iter(pb.montagem.pemfc.values()))
    assert ua["curva"] is ub["curva"] is next(iter(pa2.montagem.pemfc.values()))["curva"]
    m = ua["massas_eventos"]
    # massas ADICIONAIS (auditoria do PR #23, A): a partida já é coberta pela contabilidade instantânea (m_SU = 0); a
    # parada ocorre no intervalo desligado (m_SD > 0); durações lidas do modelo dinâmico
    assert m["m_partida_kg"] == 0.0 and m["duracao_partida_s"] == pytest.approx(30.0) and m["m_parada_kg"] > 0
    doc = pa.montagem.doc_pemfc
    assert pa.montagem.hashes["pemfc"] and list(doc["registros"]) == [H.pemfc_id(pa.scenario.document)]
    g = pa.montagem.modelo.base.geradores[0]
    assert g.curva_h2.classificacao == "real_certificada_b04" and g.preco_h2.valor == 40.0


# ====================================================================== missões reais
@pytest.fixture(scope="module")
def hibrida(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("hibrida3da2h")
    reg, store = _loja(raiz, fv=True, eolica=True)
    sc = _hibrido(store)
    if not SOLVER:
        return {"raiz": raiz, "store": store, "sc": sc, "run": None}
    n0 = CH.GERACOES["n"]
    run = X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    n1 = CH.GERACOES["n"]
    return {"raiz": raiz, "reg": reg, "store": store, "sc": sc, "run": run, "geracoes": (n0, n1)}


def _ints(store, run, nome=RG.N_INTERVALOS):
    import io

    import pandas as pd
    return pd.read_csv(io.BytesIO(store.run_data(run.run_uid, nome)), float_precision="round_trip")


@requer_solver
def test_missao_hibrida_fv_eolica_bateria_pemfc_pcc_concluida(hibrida):
    run, store = hibrida["run"], hibrida["store"]
    assert run.state == "concluida", (run.error, (run.outcome or {}).get("mission"))
    m = run.summary["mission"]
    assert m["missao_completa"] and m["energia_nao_atendida_kWh"] == 0.0
    assert set(run.data) == set(RG.OBRIGATORIOS) | {RG.N_RENOV, RG.N_PEMFC, RG.N_PEMFC_DIN}
    assert RG.ler_json(store, run, RG.N_INDICE)["versao"] == 3
    assert RG.verificar(store, run).ok
    n0, n1 = hibrida["geracoes"]
    assert n1 - n0 <= 1                          # no máximo UMA geração para a missão inteira (12 janelas MPC)
    assert len(run.summary["mission"]) and m["janelas"] == 12


@requer_solver
def test_potencia_consumo_custo_e_conservacao_por_unidade(hibrida):
    run, store = hibrida["run"], hibrida["store"]
    df = _ints(store, run)
    doc = RG.ler_json(store, run, RG.N_PEMFC)
    eid = next(iter(doc["registros"]))
    x = doc["registros"][eid]
    curva_v = np.array(x["curva"]["vertices_kW_kg_h"])
    u, p = df[f"{eid}|u"], df[f"{eid}|p_kW"]
    lo, hi = x["curva"]["dominio_kW"]
    assert ((u == 0) | ((p >= lo - 1e-6) & (p <= hi + 1e-6))).all() and ((u == 1) | (p == 0)).all()
    q = np.where(u == 1, np.interp(p, curva_v[:, 0], curva_v[:, 1]), 0.0)
    msu, msd = x["massas_eventos"]["m_partida_kg"], x["massas_eventos"]["m_parada_kg"]
    m_esp = q * 1.0 + msu * df[f"{eid}|partida"] + msd * df[f"{eid}|parada"]          # Δ = 60 min ⇒ h = 1
    assert np.allclose(df[f"{eid}|m_h2_kg"], m_esp, rtol=1e-12, atol=1e-12)
    assert np.allclose(df[f"{eid}|custo_h2_R"], 10.0 * m_esp, rtol=1e-12, atol=1e-12)
    r = run.summary["mission"]["pemfc"][eid]
    assert r["energia_kWh"] == pytest.approx(float(p.sum())) and r["massa_h2_kg"] == pytest.approx(float(m_esp.sum()))
    assert run.summary["mission"]["custo_realizado_componentes_R"]["combustivel_h2"] == pytest.approx(r["custo_h2_R"])
    assert df["residuo_balanco_kW"].abs().max() < 1e-6
    assert r["energia_kWh"] > 0 and r["partidas"] >= 1                       # a PEMFC foi despachada


@requer_solver
def test_verificacao_dinamica_registra_partida_e_coerencia(hibrida):
    run, store = hibrida["run"], hibrida["store"]
    din = RG.ler_json(store, run, RG.N_PEMFC_DIN)
    (u, v), = din["unidades"].items()
    assert din["tolerancias"]["energia_rel"] == 0.02 and v["coerente"] is din["coerente"] is True
    part = [x for x in v["intervalos"] if "STARTUP" in x["estados"]]
    assert part and all(x["deficit_kWh"] > 0 for x in part)            # partida física ≠ abstração instantânea
    assert v["energia_entregue_kWh"] == pytest.approx(v["energia_solicitada_kWh"], rel=0.02)
    assert v["h2_modelo_dinamico_kg"] == pytest.approx(v["h2_ems_kg"], rel=0.02)
    assert v["h2_ems_kg"] >= v["h2_modelo_dinamico_kg"]                 # termo de evento nunca subestima a massa total
    assert run.summary["execution"]["pemfc_dinamica"][u]["coerente"] is True
    acc = run.summary["execution"]["aceitacao"]
    assert acc["classificacao"] == "algebrica_aprovada_dinamica_coerente" and acc["fisica"]["estado"] == "nao_validada"


@requer_solver
def test_reabertura_sem_modelos_curva_nem_solver_e_com_registro_limpo(hibrida, monkeypatch):
    run, store = hibrida["run"], hibrida["store"]
    real_import = builtins.__import__

    def bloqueado(nome, *a, **k):
        if nome.split(".")[0] in ("pyomo", "highspy"):
            raise AssertionError(f"reabertura importou {nome}")
        return real_import(nome, *a, **k)
    for mod in [m for m in sys.modules if m.split(".")[0] in ("pyomo", "highspy")]:
        monkeypatch.delitem(sys.modules, mod)
    monkeypatch.setattr(builtins, "__import__", bloqueado)
    import h2_pemfc.models.equivalent_65kw_power_request as PRM
    from integracao_v2 import pemfc_dinamica as DY
    sab = lambda *a, **k: (_ for _ in ()).throw(AssertionError("modelo PEMFC executado na reabertura"))  # noqa: E731
    for alvo, nome in ((CH, "obter_curva"), (CH, "_gerar"), (DY, "verificar_despacho"), (DY, "massas_eventos"),
                       (PRM.Equivalent65kWHorizonPowerRequestModel, "solve_requested_power"), (X, "submit"),
                       (PF, "preparar")):
        monkeypatch.setattr(alvo, nome, sab)
    monkeypatch.setattr(K, "_CERTIFICADOS_B04", {})          # processo "novo": nenhum certificado registrado
    v = RG.verificar(MicrogridRegistry(hibrida["raiz"] / "dados", adopt_legacy=False).open(run.microgrid_uid), run)
    assert v.ok, v.falhas()
    assert any("re-registrado" in t for _, t in v.itens)


@requer_solver
def test_adulteracao_da_curva_certificado_ou_dinamica_e_detectada(hibrida, monkeypatch):
    run, store = hibrida["run"], hibrida["store"]

    class Adulterado:
        def __init__(self, nome, fn):
            self.nome, self.fn = nome, fn

        def run_data(self, uid, nome):
            b = store.run_data(uid, nome)
            return self.fn(b) if nome == self.nome else b
    doc = RG.ler_json(store, run, RG.N_PEMFC)
    eid = next(iter(doc["registros"]))
    doc["registros"][eid]["certificado_b04"]["validacao"][10][1] *= 0.97     # valor "do modelo" adulterado
    monkeypatch.setattr(K, "_CERTIFICADOS_B04", {})
    v = RG.verificar(Adulterado(RG.N_PEMFC, lambda b: json.dumps(doc).encode()), run)
    assert not v.ok
    din = RG.ler_json(store, run, RG.N_PEMFC_DIN)
    (u, d), = din["unidades"].items()
    d["intervalos"][0]["p_solicitada_kW"] += 1.0
    v = RG.verificar(Adulterado(RG.N_PEMFC_DIN, lambda b: json.dumps(din).encode()), run)
    assert not v.ok and any("consignas aplicadas" in t for t in v.falhas())


@requer_solver
def test_estudo_com_pemfc_exportado_e_importado_sem_recalcular(hibrida, tmp_path, monkeypatch):
    store, sc, run = hibrida["store"], hibrida["sc"], hibrida["run"]
    pacote, _ = exporter.export_bytes(store, sc.scenario_uid)
    monkeypatch.setattr(CH, "obter_curva", lambda *a, **k: (_ for _ in ()).throw(AssertionError("curva regenerada")))
    monkeypatch.setattr(K, "_CERTIFICADOS_B04", {})
    arquivo = ArchiveStore(tmp_path / "outra")
    view = StudyView(arquivo, arquivo.import_package(pacote).study.archive_uid)
    arq = view.get_run(run.run_uid)
    assert view.run_data(run.run_uid, RG.N_PEMFC) == store.run_data(run.run_uid, RG.N_PEMFC)
    v = RG.verificar(view, arq)
    assert v.ok, v.falhas()


@requer_solver
def test_sem_aprovacao_a_reabertura_nao_certifica_a_curva(hibrida, monkeypatch):
    """Política NÃO aprovada no processo de leitura: o certificado gravado não é registrado e a evidência não é aceita —
    nenhuma curva fica certificada por declaração ou hash."""
    monkeypatch.setattr(K, "_CERTIFICADOS_B04", {})
    run, store = hibrida["run"], hibrida["store"]
    doc = RG.ler_json(store, run, RG.N_PEMFC)
    eid = next(iter(doc["registros"]))
    doc["registros"][eid]["certificado_b04"]["politica"]["situacao"] = "proposta_congelada_pendente_de_aprovacao"

    class Fonte:
        def run_data(self, uid, nome):
            return json.dumps(doc).encode() if nome == RG.N_PEMFC else store.run_data(uid, nome)
    v = RG.verificar(Fonte(), run)
    assert not v.ok
    with H.politica_pendente_no_teste():           # dados INTACTOS, núcleo com a política REVOGADA: certificado recusado
        v = RG.verificar(store, run)
    assert not v.ok and any("re-registrado" in t for t in v.falhas())
    assert RG.verificar(store, run).ok              # política aprovada (repositório): a mesma evidência é aceita


@requer_solver
def test_rodada_renovavel_gravada_no_contrato_v2_continua_legivel(tmp_path, monkeypatch):
    """Rodada FV + eólica (sem PEMFC) gravada EXATAMENTE como o Piso 3D-A2-R gravava (v2): verificada no contrato v3."""
    reg = MicrogridRegistry(tmp_path / "dados", adopt_legacy=False)
    cfg = R.config_hibrida()
    reg.create(cfg)
    store = reg.open(cfg["installation"]["uid"])
    sc = R.criar_cenario_hibrido(store, demanda_kW=40.0, clima=_clima)
    atual = RG.VERSAO
    monkeypatch.setattr(RG, "VERSAO", 2)
    run = X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    monkeypatch.undo()
    assert run.state == "concluida", run.error
    assert atual == 3 and 2 in RG.VERSOES_LEGIVEIS
    assert RG.ler_json(store, run, RG.N_INDICE)["versao"] == 2
    assert RG.N_RENOV in run.data and RG.N_PEMFC not in run.data
    v = RG.verificar(store, run)
    assert v.ok, v.falhas()
