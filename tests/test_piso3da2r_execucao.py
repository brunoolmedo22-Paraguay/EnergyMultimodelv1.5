"""Piso 3D-A2-R — missões REAIS do EMS V2 (Pyomo + HiGHS) com FV, eólica, bateria e PCC sobre microrredes do CATÁLOGO.

Casos de validação da missão (dados SINTÉTICOS rotulados; modelos físicos reais do código; nenhuma fixture H1–H18):

1. FV com geração variável coerente com o clima; 2. eólica com curva válida do catálogo; 3. híbrida FV + eólica +
bateria + demanda + PCC; 4. potencial renovável acima da carga (limites, armazenamento e vertimento); 5. baixa
disponibilidade renovável (bateria e rede); 6. integridade por UID e conservação de energia; 7. previsão × realização e
não antecipação (intervenção); 8. persistência e reabertura SEM modelos nem otimizador; 9. compatibilidade com rodadas
3D-A (contrato v1) e V1.6; 10. estudo exportado/importado em outra instalação.

Os testes que resolvem MILPs são pulados EXPLICITAMENTE sem Pyomo/HiGHS.
"""
from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import piso3da2r_util as R  # noqa: E402
import piso3da_util as U  # noqa: E402

from ems_v2.milp.ambiente import verificar_ambiente  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from integracao_v2 import montagem as MT  # noqa: E402
from integracao_v2 import preflight as PF  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from seeds2.archive import exporter  # noqa: E402
from seeds2.archive.store import ArchiveStore  # noqa: E402
from seeds2.archive.view import StudyView  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402

SOLVER = bool(verificar_ambiente().get("disponivel"))
requer_solver = pytest.mark.skipif(not SOLVER, reason="Pyomo/HiGHS não instalados (pip install -r requirements-ems_v2.txt)")
pytestmark = requer_solver

GHI = [0, 0, 0, 0, 0, 0, 100, 350, 600, 800, 950, 1000]
TAMB = [20, 20, 20, 21, 21, 22, 23, 25, 27, 29, 30, 31]
VENTO = [2.0, 3.0, 4.2, 5.0, 6.3, 7.0, 8.0, 9.4, 10.0, 11.2, 12.0, 14.0]
# Híbrida: vento forte no meio da missão (excedente) e fraco no fim, quando a tarifa tem o pico (horas 8–9).
VENTO_H = [2.0, 3.0, 9.0, 10.0, 11.0, 12.0, 12.0, 10.0, 4.0, 3.0, 2.5, 2.0]
TOL = 1e-6


def _tabela(**extra):
    return lambda doc: R.clima_tabela(doc, {"ghi_W_m2": GHI, "temperature_C": TAMB, "wind_speed_m_s": VENTO, **extra})


def _catalogo(raiz: Path, **kw):
    reg = MicrogridRegistry(raiz / "dados", adopt_legacy=False)
    cfg = R.config_hibrida(**kw)
    reg.create(cfg)
    return reg, reg.open(cfg["installation"]["uid"])


def _executar(store, sc):
    run = X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    assert run.state == "concluida", (run.state, run.error, (run.outcome or {}).get("mission"))
    return run


def _ints(store, run, nome=RG.N_INTERVALOS):
    """CSV gravado com ``repr`` (double exato); lido em ida e volta exata para comparações bit a bit."""
    import io

    import pandas as pd
    return pd.read_csv(io.BytesIO(store.run_data(run.run_uid, nome)), float_precision="round_trip")


@pytest.fixture(scope="module")
def hibrida(tmp_path_factory):
    """Microrrede do catálogo com FV + eólica + banco 20 kWh + PCC (só importação, 50 kW); demanda 40 kW × 12 h."""
    raiz = tmp_path_factory.mktemp("hibrida3da2r")
    reg, store = _catalogo(raiz)
    sc = R.criar_cenario_hibrido(store, demanda_kW=40.0, clima=_tabela(wind_speed_m_s=VENTO_H))
    run = _executar(store, sc)
    return {"raiz": raiz, "reg": reg, "store": store, "sc": sc, "run": run, "ids": R.ids(sc.document)}


# ====================================================================== 1 e 2 — tecnologias isoladas
def test_caso1_fv_variavel_coerente_com_o_clima(tmp_path):
    _reg, store = _catalogo(tmp_path, eolica=False)
    sc = R.criar_cenario_hibrido(store, demanda_kW=10.0, clima=_tabela())
    run = _executar(store, sc)
    df = _ints(store, run)
    (arr,) = [c.split("|")[0] for c in df.columns if c.endswith("|P_R_kW")]
    esperado = R.potencia_fv_independente(GHI, TAMB)
    assert np.allclose(df[f"{arr}|A_observada_kW"], esperado, rtol=1e-12, atol=1e-12)
    assert np.allclose(df[f"{arr}|A_prevista_kW"], esperado, rtol=1e-12, atol=1e-12)
    assert (df[f"{arr}|P_R_kW"] <= df[f"{arr}|A_utilizavel_kW"] + TOL).all()
    assert (df[f"{arr}|P_R_kW"].iloc[:6] == 0).all() and df[f"{arr}|P_R_kW"].iloc[11] > 4.0   # noite × fim da manhã
    assert df[f"{arr}|vertimento_kW"].abs().max() < TOL          # potencial < demanda: nada é vertido
    ren = run.summary["mission"]["renovaveis"][arr]
    assert ren["tecnologia"] == "fv" and ren["energia_aproveitada_kWh"] == pytest.approx(float(esperado.sum()))
    assert RG.verificar(store, run).ok


def test_caso2_eolica_com_curva_valida_do_catalogo(tmp_path):
    _reg, store = _catalogo(tmp_path, fv=False)
    sc = R.criar_cenario_hibrido(store, demanda_kW=150.0, clima=_tabela(),
                                 mutar=lambda doc: doc["milp_mpc"]["pcc"].update(limite_importacao_kW=200.0))
    run = _executar(store, sc)
    df = _ints(store, run)
    wt = R.ids(sc.document)["eolica"]
    esperado = R.potencia_eolica_independente(VENTO)
    assert np.allclose(df[f"{wt}|A_observada_kW"], esperado, rtol=0, atol=1e-12)
    assert (df[f"{wt}|P_R_kW"] <= df[f"{wt}|A_utilizavel_kW"] + TOL).all()
    assert df[f"{wt}|P_R_kW"].iloc[0] == 0.0                      # 2 m/s < cut-in
    doc = RG.ler_json(store, run, RG.N_RENOV)
    (r,) = doc["recursos"]
    assert r["parametros"]["aerogerador"] == R.TURBINA and r["parametros"]["situacao_integracao"] == "restricted_domain"
    assert any("cubo" in h for h in r["hipoteses"]) and r["parametros"]["hipotese_densidade"] == "referencia_do_catalogo"


# ====================================================================== 3–6 — híbrida
def test_caso3_hibrida_completa_concluida_e_verificada(hibrida):
    store, run, ids = hibrida["store"], hibrida["run"], hibrida["ids"]
    m = run.summary["mission"]
    assert m["missao_completa"] and m["energia_nao_atendida_kWh"] == 0.0
    assert set(m["renovaveis"]) == {*hibrida["store"].get_run(run.run_uid).summary["mission"]["renovaveis"]}
    assert {v["tecnologia"] for v in m["renovaveis"].values()} == {"fv", "eolica"}
    assert set(run.data) == set(RG.OBRIGATORIOS) | {RG.N_RENOV}
    ind = RG.ler_json(store, run, RG.N_INDICE)
    assert ind["versao"] == 2 and RG.N_RENOV in ind["arquivos"]
    v = RG.verificar(store, run)
    assert v.ok, v.falhas()
    assert any("PREVISTO entregue a cada janela" in t for _, t in v.itens)
    assert any("REALIZADO observado" in t for _, t in v.itens)
    _ = ids


def test_caso4_excedente_renovavel_respeita_limites_armazena_e_verte(hibrida):
    store, run, ids = hibrida["store"], hibrida["run"], hibrida["ids"]
    df = _ints(store, run)
    rens = [c.split("|")[0] for c in df.columns if c.endswith("|P_R_kW")]
    disp = sum(df[f"{u}|A_utilizavel_kW"] for u in rens)
    exced = disp > 40.0 + 10.0                                    # potencial > demanda + carga máxima do banco
    assert exced.sum() >= 5
    vert = sum(df[f"{u}|vertimento_kW"] for u in rens)
    assert (vert[exced] > 0).all()                               # PCC só importa: o excedente é vertido
    for u in rens:
        assert (df[f"{u}|vertimento_kW"] >= -TOL).all() and (df[f"{u}|P_R_kW"] >= -TOL).all()
    b = ids["bateria"]
    assert (df[f"{b}|P_c_kW"] <= 5.0 + TOL).all() and (df[f"{b}|P_d_kW"] <= 10.0 + TOL).all()
    assert df.loc[exced, "pcc_importacao_realizada_kW"].abs().max() < TOL
    fr = _ints(store, run, RG.N_FRONTEIRAS)
    assert (fr[f"{b}|energia_kWh"] >= -TOL).all() and (fr[f"{b}|energia_kWh"] <= 20.0 + TOL).all()
    assert df.loc[exced, f"{b}|P_c_kW"].sum() > 0                # o excedente também carrega o banco
    ind = run.summary["mission"]["indicadores_selados"]
    assert ind["E_curtailment_kWh"] == pytest.approx(float(vert.sum()))


def test_caso5_baixa_disponibilidade_renovavel_usa_bateria_e_rede(hibrida):
    store, run, ids = hibrida["store"], hibrida["run"], hibrida["ids"]
    df = _ints(store, run)
    rens = [c.split("|")[0] for c in df.columns if c.endswith("|P_R_kW")]
    b = ids["bateria"]
    ren = sum(df[f"{u}|P_R_kW"] for u in rens)
    baixo = sum(df[f"{u}|A_utilizavel_kW"] for u in rens) < 40.0      # potencial abaixo da demanda
    assert list(np.flatnonzero(baixo)) == [0, 1, 8, 9, 10, 11]
    for g in np.flatnonzero(baixo):
        assert ren.iloc[g] + df[f"{b}|P_d_kW"].iloc[g] - df[f"{b}|P_c_kW"].iloc[g] \
            + df["pcc_importacao_realizada_kW"].iloc[g] == pytest.approx(40.0, abs=1e-6)
    assert (df["pcc_importacao_realizada_kW"][baixo] > 0).all()
    assert df[f"{b}|P_d_kW"].iloc[8] > 0 and df[f"{b}|P_d_kW"].iloc[9] > 0  # bateria na ponta (tarifa 1,5)


def test_caso6_integridade_por_uid_e_conservacao_de_energia(hibrida):
    store, run = hibrida["store"], hibrida["run"]
    df = _ints(store, run)
    assert df["residuo_balanco_kW"].abs().max() < 1e-6
    doc = RG.ler_json(store, run, RG.N_RENOV)
    serie = {r["uid"]: r["potencial_kW"] for r in doc["recursos"]}
    rens = [c.split("|")[0] for c in df.columns if c.endswith("|P_R_kW")]
    assert sorted(rens) == sorted(serie)
    for u in rens:
        assert list(df[f"{u}|A_observada_kW"]) == serie[u]       # bit a bit: o que a planta realizou = o derivado
        e = 0.0
        for g in range(12):
            e += df[f"{u}|P_R_kW"].iloc[g]
            assert df[f"{u}|E_aproveitada_acum_kWh"].iloc[g] == pytest.approx(e, abs=1e-9)
    m = run.summary["mission"]
    usada = sum(v["energia_aproveitada_kWh"] for v in m["renovaveis"].values())
    b = hibrida["ids"]["bateria"]
    bat = m["baterias"][b]
    # Σ demanda atendida = Σ renovável aproveitada + descarga − carga + importação (h = 1 h)
    assert m["energia_atendida_kWh"] == pytest.approx(usada + bat["energia_descarregada_kWh"] - bat["energia_carregada_kWh"]
                                                      + m["energia_importada_kWh"], abs=1e-6)
    assert m["indicadores_selados"]["E_renovavel_usada_kWh"] == pytest.approx(usada)


# ====================================================================== 7 — causalidade
def test_caso7_realizacao_renovavel_futura_nao_altera_decisoes_anteriores(tmp_path):
    """Intervenção na REALIZAÇÃO do potencial renovável a partir do intervalo 8 (a previsão é a mesma): até lá as
    consignas aplicadas são idênticas; a diferença é absorvida pelo ajuste local do PCC e fica registrada."""
    from ems_v2.ponte import cenario as CN

    _reg, store = _catalogo(tmp_path, fv=False)
    pf = PF.preparar(store, R.criar_cenario_hibrido(store, demanda_kW=40.0, clima=_tabela()))
    assert pf.ok, [i.message for i in pf.items if i.level == PF.ERROR]
    mont = pf.montagem
    wt = R.ids(pf.scenario.document)["eolica"]
    series = []
    for s in mont.verdade.series:
        if s.uid == wt and s.grandeza == "potencia":
            v = list(s.serie.valores)
            v[8:] = [x * 0.5 for x in v[8:]]
            s = CN.SerieRecurso(s.uid, s.grandeza, type(s.serie)(**{**s.serie.__dict__, "valores": tuple(v)}))
        series.append(s)
    verdade_b = CN.Realizacao(mont.verdade.realizacao_uid, mont.verdade.natureza, tuple(series), mont.verdade.procedencia)
    uid = "cd" * 16
    ca, ea, _ = MT.construir_missao(mont, uid, pf.scenario)
    ra = X.executar_janela_a_janela(ca, ea)
    mont.verdade = verdade_b
    cb, eb, _ = MT.construir_missao(mont, uid, pf.scenario)
    rb = X.executar_janela_a_janela(cb, eb)
    assert ra.situacao == rb.situacao == "encerrada"

    def aplicados(res):
        return {p.indice_global: dict(p.aplicado) for r in res.registros for p in r.conteudo.passos}
    pa, pb = aplicados(ra), aplicados(rb)
    assert all(pa[g] == pb[g] for g in range(8))
    obs_b = {p.indice_global: p.entorno_observado[f"{wt}|potencia"] for r in rb.registros for p in r.conteudo.passos}
    assert obs_b[9] == pytest.approx(0.5 * R.potencia_eolica_independente(VENTO)[9])
    prev_b = [r.conteudo.previsao.serie(wt, "potencia").serie.valores for r in rb.registros]
    prev_a = [r.conteudo.previsao.serie(wt, "potencia").serie.valores for r in ra.registros]
    assert prev_a == prev_b                                      # o controlador nunca recebeu a realização


# ====================================================================== 8 — reabertura sem modelos
def test_caso8_reabertura_sem_modelos_fisicos_nem_otimizador(hibrida, monkeypatch):
    store, run = hibrida["store"], hibrida["run"]
    real_import = builtins.__import__

    def bloqueado(nome, *a, **k):
        if nome.split(".")[0] in ("pyomo", "highspy"):
            raise AssertionError(f"reabertura importou {nome}")
        return real_import(nome, *a, **k)
    for mod in [m for m in sys.modules if m.split(".")[0] in ("pyomo", "highspy")]:
        monkeypatch.delitem(sys.modules, mod)
    monkeypatch.setattr(builtins, "__import__", bloqueado)
    import models.wind_model as WM
    import simulation.multimodel as MM
    from integracao_v2 import renovaveis as RN
    sab = lambda *a, **k: (_ for _ in ()).throw(AssertionError("modelo físico executado na reabertura"))  # noqa: E731
    for alvo, nome in ((MM, "simulate_noct_efficiency_model"), (WM, "run_wind_model"), (RN, "derivar_fv"),
                       (RN, "derivar_eolica"), (X, "submit"), (PF, "preparar")):
        monkeypatch.setattr(alvo, nome, sab)
    novo = MicrogridRegistry(hibrida["raiz"] / "dados", adopt_legacy=False).open(run.microgrid_uid)
    lido = novo.get_run(run.run_uid)
    v = RG.verificar(novo, lido)
    assert v.ok, v.falhas()


def test_caso8_adulteracao_da_derivacao_renovavel_e_detectada(hibrida):
    store, run = hibrida["store"], hibrida["run"]

    class Adulterado:
        def __init__(self, nome, fn):
            self.nome, self.fn = nome, fn

        def run_data(self, uid, nome):
            b = store.run_data(uid, nome)
            return self.fn(b) if nome == self.nome else b
    doc = RG.ler_json(store, run, RG.N_RENOV)
    doc["recursos"][0]["potencial_kW"][5] += 1.0
    from integracao_v2 import renovaveis as RN
    v = RG.verificar(Adulterado(RG.N_RENOV, lambda b: RN.bytes_documento(doc)), run)
    assert not v.ok and any("comprometida no manifesto" in t for t in v.falhas())


# ====================================================================== 9 — compatibilidade
def test_caso9_rodada_no_contrato_v1_do_3da_continua_legivel(tmp_path, monkeypatch):
    reg = MicrogridRegistry(tmp_path / "dados", adopt_legacy=False)
    cfg = U.config_bateria()
    reg.create(cfg)
    store = reg.open(cfg["installation"]["uid"])
    monkeypatch.setattr(RG, "VERSAO", 1)                         # grava exatamente como o Piso 3D-A gravava
    run = _executar(store, U.criar_cenario_v2(store))
    monkeypatch.undo()
    assert RG.VERSAO == 2
    assert RG.ler_json(store, run, RG.N_INDICE)["versao"] == 1 and RG.N_RENOV not in run.data
    assert "renovaveis" not in run.summary["mission"]
    v = RG.verificar(store, run)
    assert v.ok, v.falhas()
    assert run.summary["mission"]["custo_realizado_total_R"] == pytest.approx(50.2)
    cols = list(_ints(store, run).columns)
    assert not any("P_R" in c for c in cols)                     # vistas idênticas às do 3D-A (sem renováveis)


def test_caso9_missao_isolada_hibrida_sem_pcc(tmp_path):
    _reg, store = _catalogo(tmp_path, modo="isolada")
    sc = R.criar_cenario_hibrido(store, demanda_kW=5.0, soc0=100.0, isolado=True,
                                 clima=lambda doc: R.clima_tabela(doc, {"ghi_W_m2": GHI, "temperature_C": TAMB,
                                                                        "wind_speed_m_s": [6.0] * 12}))
    run = _executar(store, sc)
    df = _ints(store, run)
    m = run.summary["mission"]
    assert m["pcc_modo"] == "isolado_declarado" and m["custo_realizado_componentes_R"].get("importacao_rede") is None
    assert df["residuo_balanco_kW"].abs().max() < 1e-6
    assert sum(v["energia_vertida_kWh"] for v in m["renovaveis"].values()) > 0
    assert RG.verificar(store, run).ok


# ====================================================================== 10 — arquivo científico
def test_caso10_estudo_hibrido_exportado_e_importado_sem_recalcular(hibrida, tmp_path, monkeypatch):
    store, sc, run = hibrida["store"], hibrida["sc"], hibrida["run"]
    pacote, _info = exporter.export_bytes(store, sc.scenario_uid)
    import models.wind_model as WM
    import simulation.multimodel as MM
    sab = lambda *a, **k: (_ for _ in ()).throw(AssertionError("executou"))  # noqa: E731
    for alvo, nome in ((MM, "simulate_noct_efficiency_model"), (WM, "run_wind_model"), (X, "submit")):
        monkeypatch.setattr(alvo, nome, sab)
    arquivo = ArchiveStore(tmp_path / "outra_instalacao")
    view = StudyView(arquivo, arquivo.import_package(pacote).study.archive_uid)
    arq = view.get_run(run.run_uid)
    assert arq.state == "concluida" and arq.summary == run.summary
    assert view.run_data(run.run_uid, RG.N_RENOV) == store.run_data(run.run_uid, RG.N_RENOV)
    v = RG.verificar(view, arq)
    assert v.ok, v.falhas()
    assert json.loads(view.run_data(run.run_uid, RG.N_RENOV))["realizacao"]["tipo"] == "igual_a_previsao"


def test_missao_isolada_interrompida_guarda_evidencia_parcial_com_renovaveis(tmp_path):
    """Isolada e sem ajuste: demanda REALIZADA acima da capacidade num intervalo ⇒ inexequível ⇒ interrompida, com a
    derivação renovável anexada à evidência PARCIAL (nunca dados de rodada concluída)."""
    _reg, store = _catalogo(tmp_path, modo="isolada")
    sc = R.criar_cenario_hibrido(store, demanda_kW=5.0, soc0=50.0, isolado=True, realizada=[5.0] * 6 + [500.0] + [5.0] * 5,
                                 clima=_tabela())
    run = X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    assert run.state == "interrompida" and not run.data, (run.state, run.error)
    evd = (run.outcome or {}).get("evidence")
    assert evd and evd["parcial"] is True and len(evd["renovaveis"]["recursos"]) == 2
    assert run.outcome["mission"]["intervalos_aplicados"] == 6           # interrompida no intervalo do pico de demanda
    v = RG.verificar(store, run)
    assert v.ok, v.falhas()
