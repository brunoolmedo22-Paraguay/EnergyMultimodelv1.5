"""Piso 3D-A — execução REAL do EMS V2 (Pyomo + HiGHS) sobre microrredes do CATÁLOGO, persistência, reabertura sem
otimizador, falhas e isolamento. Dados sintéticos de teste rotulados (``tests/piso3da_util.py``); nenhuma fixture
H1–H18 do ``ems_v2`` é usada: o oráculo é o resultado ANALÍTICO do caso (demanda 10 kW × 12 h, banco 20 kWh, tarifa
0,5 R$/kWh com pico 1,5 nas horas 8–9, c_thr = 0,01): com custo de continuação o banco é preservado para o pico ⇒
0,5·80 + 0,5·20 + 0,01·20 = R$ 50,2 (sem coordenação, com N = 3, seriam R$ 70,2).

Os testes que resolvem MILPs são pulados EXPLICITAMENTE sem Pyomo/HiGHS; os de bloqueio/solver ausente rodam sempre.
"""
from __future__ import annotations

import builtins
import io
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import piso3da_util as U  # noqa: E402

from ems_v2.milp.ambiente import verificar_ambiente  # noqa: E402
from integracao_v2 import estrategia as E  # noqa: E402
from integracao_v2 import execucao as X  # noqa: E402
from integracao_v2 import preflight as PF  # noqa: E402
from integracao_v2 import registro as RG  # noqa: E402
from seeds2.archive import exporter  # noqa: E402
from seeds2.archive.store import ArchiveStore  # noqa: E402
from seeds2.archive.view import StudyView  # noqa: E402
from seeds2.microgrid.registry import MicrogridRegistry  # noqa: E402
from seeds2.microgrid.store import RunNotFound, StoreError  # noqa: E402
from seeds2.operation import preflight as P16  # noqa: E402
from seeds2.operation import runner as R16  # noqa: E402
from seeds2.operation import service as SV  # noqa: E402

SOLVER = bool(verificar_ambiente().get("disponivel"))
requer_solver = pytest.mark.skipif(not SOLVER, reason="Pyomo/HiGHS não instalados (pip install -r requirements-ems_v2.txt)")


def _catalogo(raiz: Path, **kw):
    reg = MicrogridRegistry(raiz / "dados", adopt_legacy=False)
    cfg = U.config_bateria(**kw)
    reg.create(cfg)
    return reg, reg.open(cfg["installation"]["uid"])


def _executar(store, sc):
    return X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)


@pytest.fixture(scope="module")
def missao(tmp_path_factory):
    """UMA missão mínima real (compartilhada pelos testes de leitura): microrrede do catálogo → cenário v2 → HiGHS."""
    raiz = tmp_path_factory.mktemp("missao3da")
    reg, store = _catalogo(raiz)
    sc = U.criar_cenario_v2(store)
    return {"raiz": raiz, "reg": reg, "store": store, "sc": sc, "run": _executar(store, sc)}


# ====================================================================== execução real e persistência
@requer_solver
def test_missao_minima_de_microrrede_registrada_reproduz_o_resultado_analitico(missao):
    run = missao["run"]
    assert run.state == "concluida", run.error
    m = run.summary["mission"]
    assert run.summary["engine"] == E.MOTOR_V2 and run.manifest["engine"]["id"] == E.MOTOR_V2
    assert m["missao_uid"] == run.run_uid and m["missao_completa"] is True
    assert (m["intervalos_missao"], m["intervalos_aplicados"], m["fronteiras"], m["janelas"]) == (12, 12, 13, 12)
    assert m["custo_realizado_total_R"] == pytest.approx(50.2, abs=1e-9)          # analítico (não vem de fixture)
    assert m["custo_realizado_componentes_R"] == pytest.approx({"importacao_rede": 50.0, "throughput_bess": 0.2})
    assert m["custo_realizado_inclui_valor_futuro"] is False and m["custo_realizado_parcial"] is False
    assert m["energia_demanda_kWh"] == pytest.approx(120.0) and m["energia_nao_atendida_kWh"] == 0.0
    assert m["energia_importada_kWh"] == pytest.approx(100.0)
    b = m["baterias"][U.bateria_id(missao["sc"].document)]
    assert (b["energia_inicial_kWh"], b["energia_final_kWh"]) == (20.0, 0.0)
    assert b["energia_descarregada_kWh"] == pytest.approx(20.0) and b["energia_carregada_kWh"] == 0.0
    assert m["sinal_valor_futuro"]["valido"] == 12 and m["solver"]["janelas_otimas"] == 12
    assert run.manifest["engine"]["synthetic"] is True and "ENSAIO" in run.manifest["scope"]
    assert set(run.data) == set(RG.OBRIGATORIOS)


@requer_solver
def test_dados_por_intervalo_fronteira_e_janela(missao):
    store, run = missao["store"], missao["run"]
    bid = U.bateria_id(missao["sc"].document)
    it = RG.ler_csv(store, run, RG.N_INTERVALOS)
    fr = RG.ler_csv(store, run, RG.N_FRONTEIRAS)
    ja = RG.ler_csv(store, run, RG.N_JANELAS)
    pl = RG.ler_csv(store, run, RG.N_PLANOS)
    assert (len(it), len(fr), len(ja)) == (12, 13, 12)                 # N intervalos, N + 1 fronteiras
    assert list(it["intervalo"]) == list(range(12)) and list(fr["fronteira"]) == list(range(13))
    # o banco é preservado até o pico (horas 8–9) e só então descarrega — decisão explicada pelo custo de continuação
    assert list(it[f"{bid}|P_d_kW"]) == [0.0] * 8 + [10.0, 10.0] + [0.0, 0.0]
    assert list(it["pcc_importacao_realizada_kW"]) == [10.0] * 8 + [0.0, 0.0] + [10.0, 10.0]
    assert list(fr[f"{bid}|energia_kWh"]) == [20.0] * 9 + [10.0] + [0.0] * 3
    assert (it["residuo_balanco_kW"].abs() < 1e-9).all() and (it["demanda_nao_atendida_kW"] == 0).all()
    assert (it[f"{bid}|P_c_kW"] >= 0).all()                             # carga nunca aparece como geração negativa
    assert it["custo_realizado_acumulado_R"].iloc[-1] == pytest.approx(50.2)
    assert list(it["tarifa_importacao_decisao_R_kWh"]) == U.TARIFA_H2
    assert (ja["solver_classificacao"] == "otimo").all() and (ja["gap_rel"] == 0).all()
    assert (ja["sinal_situacao"] == "valido").all() and (ja["custo_futuro_estimado_R"] >= 0).all()
    assert ja["realizado_R"].sum() == pytest.approx(50.2)
    # custo realizado NUNCA contém o custo futuro: objetivo da janela ≠ custo realizado
    assert (ja["objetivo_R"] > ja["realizado_R"]).any()
    assert set(pl["janela"]) == set(range(12)) and pl.groupby("janela")["aplicado"].sum().eq(1).all()
    coord = RG.ler_json(store, run, RG.N_COORD)
    assert len(coord) == 12 and all(c["sinal"]["qualidade"]["estado"] == "valido" for c in coord)
    ind = RG.ler_json(store, run, RG.N_INDICE)
    assert ind["formato"] == RG.FORMATO and ind["run_uid"] == run.run_uid and ind["limitacoes"]
    aud = RG.ler_json(store, run, RG.N_AUDITORIA)
    assert aud["aceito"] is True and all(aud["verificacoes"].values())


@requer_solver
def test_rodada_finalizada_e_imutavel(missao):
    store, run = missao["store"], missao["run"]
    db = next(p for p in (missao["raiz"] / "dados").rglob("seeds2.db") if run.microgrid_uid in str(p))
    con = sqlite3.connect(db)
    try:
        for sql in ("UPDATE scenario_runs SET summary = '{}' WHERE run_uid = ?",
                    "UPDATE scenario_run_data SET content = x'00' WHERE run_uid = ?",
                    "DELETE FROM scenario_run_data WHERE run_uid = ?"):
            with pytest.raises(sqlite3.DatabaseError):
                con.execute(sql, (run.run_uid,))
    finally:
        con.close()
    with pytest.raises(StoreError):
        store.finish_run(run.run_uid, X.OWNER, outcome={}, summary={}, data={})


@requer_solver
def test_reabertura_verifica_tudo_sem_otimizador(missao, monkeypatch):
    """Reabrir = ler + reauditar. Pyomo/HiGHS e os resolvedores são SABOTADOS: qualquer uso faria o teste falhar."""
    store, run = missao["store"], missao["run"]
    real_import = builtins.__import__

    def bloqueado(nome, *a, **k):
        if nome.split(".")[0] in ("pyomo", "highspy"):
            raise AssertionError(f"reabertura importou {nome}")
        return real_import(nome, *a, **k)
    for mod in [m for m in sys.modules if m.split(".")[0] in ("pyomo", "highspy")]:
        monkeypatch.delitem(sys.modules, mod)
    monkeypatch.setattr(builtins, "__import__", bloqueado)
    monkeypatch.setattr(X, "submit", lambda *a, **k: (_ for _ in ()).throw(AssertionError("executou")))
    novo = MicrogridRegistry(missao["raiz"] / "dados", adopt_legacy=False).open(run.microgrid_uid)   # nova conexão
    lido = novo.get_run(run.run_uid)
    assert lido.summary == run.summary and lido.manifest == run.manifest and lido.data == run.data
    v = RG.verificar(novo, lido)
    assert v.ok, v.falhas()
    assert len(v.itens) >= 12 and v.auditoria["aceito"] is True
    assert v.evidencia.registro_missao.conteudo.custo_realizado_acumulado.total_R == pytest.approx(50.2)
    assert store.get_run(run.run_uid).finished_at == run.finished_at


@requer_solver
def test_adulteracao_da_evidencia_e_detectada(missao):
    store, run = missao["store"], missao["run"]

    class Adulterado:
        def __init__(self, nome, fn):
            self.nome, self.fn = nome, fn

        def run_data(self, uid, nome):
            b = store.run_data(uid, nome)
            return self.fn(b) if nome == self.nome else b
    v = RG.verificar(Adulterado(RG.N_INTERVALOS, lambda b: b.replace(b"10.0", b"11.0", 1)), run)
    assert not v.ok and any("DIFEREM" in t for t in v.falhas())
    v = RG.verificar(Adulterado(RG.N_MODELO, lambda b: b.replace(b'"valor": 20.0', b'"valor": 25.0', 1)), run)
    assert not v.ok
    textos = RG.desempacotar(store.run_data(run.run_uid, RG.N_SELADOS))
    nome = f"{run.run_uid}.missao.mpc3c2.json"
    textos[nome] = textos[nome].replace('"total_R":50.2', '"total_R":40.2')
    v = RG.verificar(Adulterado(RG.N_SELADOS, lambda b: RG.empacotar(textos)), run)
    assert not v.ok


@requer_solver
def test_pedido_idempotente_nao_executa_duas_vezes(tmp_path):
    _reg, store = _catalogo(tmp_path)
    sc = U.criar_cenario_v2(store)
    req = X.new_request_id()
    a = X.submit(store, sc.scenario_uid, sc.version, req, background=False)
    b = X.submit(store, sc.scenario_uid, sc.version, req, background=False)
    assert a.run_uid == b.run_uid and a.finished_at == b.finished_at
    assert len(store.list_runs(sc.scenario_uid)) == 1


@requer_solver
def test_laco_janela_a_janela_equivale_ao_laco_unico_do_motor(tmp_path):
    from ems_v2.mpc.orquestrador import executar_missao_simulada
    from integracao_v2 import montagem as MT
    _reg, store = _catalogo(tmp_path)
    pf = PF.preparar(store, U.criar_cenario_v2(store))
    uid = "ab" * 16
    c1, e1, _ = MT.construir_missao(pf.montagem, uid, pf.scenario)
    c2, e2, _ = MT.construir_missao(pf.montagem, uid, pf.scenario)
    r1 = X.executar_janela_a_janela(c1, e1)
    r2 = executar_missao_simulada(c2, e2)
    assert r1.situacao == r2.situacao == "encerrada"
    assert r1.registro_missao.impressao_deterministica == r2.registro_missao.impressao_deterministica


# ====================================================================== causalidade
@requer_solver
def test_realizacao_futura_nao_altera_decisoes_anteriores(tmp_path):
    """Intervenção: duas missões idênticas, exceto a demanda REALIZADA a partir do intervalo 9. Até lá, previsão,
    planos e consignas aplicadas têm de ser idênticos (o controlador nunca vê a realização futura)."""
    real_b = [10.0] * 9 + [13.0, 8.0, 12.0]
    _r, sa = _catalogo(tmp_path / "a")
    _r, sb = _catalogo(tmp_path / "b")
    ra = _executar(sa, U.criar_cenario_v2(sa))
    rb = _executar(sb, U.criar_cenario_v2(sb, realizada=real_b))
    assert ra.state == rb.state == "concluida", (ra.error, rb.error)
    ia, ib = RG.ler_csv(sa, ra, RG.N_INTERVALOS), RG.ler_csv(sb, rb, RG.N_INTERVALOS)
    assert list(ib["demanda_realizada_kW"]) == real_b and list(ib["demanda_prevista_kW"]) == [10.0] * 12
    ba, bb = U.bateria_id(sa.get_scenario(ra.scenario_uid).document), U.bateria_id(sb.get_scenario(rb.scenario_uid).document)
    for col_a, col_b in ((f"{ba}|P_d_kW", f"{bb}|P_d_kW"), ("pcc_importacao_programada_kW",) * 2,
                         ("pcc_importacao_realizada_kW",) * 2):
        assert list(ia[col_a][:9]) == list(ib[col_b][:9])
    # o erro de previsão é absorvido pelo PCC (ajuste local declarado) e aparece como DESVIO, nunca apagado
    assert ib["pcc_desvio_liquido_kW"].iloc[9] == pytest.approx(3.0)
    assert rb.summary["mission"]["energia_demanda_kWh"] == pytest.approx(sum(real_b))
    assert RG.verificar(sb, rb).ok


def test_previsao_emitida_depois_do_inicio_bloqueia(tmp_path):
    _reg, store = _catalogo(tmp_path)

    def mutar(doc):
        doc[E.CHAVE_BLOCO]["demanda"]["emissao_utc"] = "2026-01-01T03:00:00+00:00"
    pf = PF.preparar(store, U.criar_cenario_v2(store, mutar=mutar))
    assert not pf.ok and "previsao_nao_causal" in {i.code for i in pf.items if i.level == PF.ERROR}
    with pytest.raises(X.PreflightV2Error):
        X.submit(store, pf.scenario.scenario_uid, pf.scenario.version, X.new_request_id(), background=False)
    assert store.list_runs() == []


# ====================================================================== bloqueio, solver ausente, interrupção
def test_missao_bloqueada_nao_abre_rodada(tmp_path):
    _reg, store = _catalogo(tmp_path)

    def mutar(doc):
        doc[E.CHAVE_BLOCO]["pcc"]["tarifa_importacao_R_kWh"] = None
    sc = U.criar_cenario_v2(store, mutar=mutar)
    with pytest.raises(X.PreflightV2Error) as exc:
        X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    assert any("Tarifa de importação" in i.message for i in exc.value.preflight.items if i.level == PF.ERROR)
    assert store.list_runs() == [] and store.count_scenario_runs() == {}


def test_solver_ausente_bloqueia_sem_recaida_no_motor_v16(tmp_path, monkeypatch):
    _reg, store = _catalogo(tmp_path)
    sc = U.criar_cenario_v2(store)
    ausente = {"disponivel": False, "erro": "Pyomo e/ou highspy não instalados (simulado)", "versoes": {}}
    monkeypatch.setattr(PF, "verificar_ambiente", lambda: dict(ausente))
    monkeypatch.setattr(R16, "_execute", lambda *a, **k: (_ for _ in ()).throw(AssertionError("motor V1.6 chamado")))
    with pytest.raises(X.PreflightV2Error) as exc:
        X.submit(store, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
    assert "solver_indisponivel" in {i.code for i in exc.value.preflight.items if i.level == PF.ERROR}
    assert store.list_runs() == []
    with pytest.raises(R16.PreflightError):                 # e o runner V1.6 também recusa o cenário V2
        R16.submit(store, sc.scenario_uid, sc.version, R16.new_request_id(), background=False)
    assert store.list_runs() == []


@requer_solver
def test_solver_que_desaparece_durante_a_execucao_falha_sem_resultados(tmp_path, monkeypatch):
    _reg, store = _catalogo(tmp_path)
    sc = U.criar_cenario_v2(store)
    monkeypatch.setattr(X, "verificar_ambiente", lambda: {"disponivel": False, "erro": "removido (simulado)"})
    run = _executar(store, sc)
    assert run.state == "falhou" and run.error["kind"] == "solver_indisponivel"
    assert run.data == {} and run.summary is None
    assert RG.verificar(store, run).ok                      # nada a reconstruir; nenhum dado indevido


@requer_solver
def test_missao_interrompida_pelo_controlador_guarda_evidencia_parcial(tmp_path):
    """Operação ISOLADA declarada (sem recurso de equilíbrio): a demanda realizada difere da prevista no intervalo 5 ⇒ a
    consigna é inexequível e o controlador interrompe. Nunca 'concluída'; custo parcial rotulado; evidência auditável."""
    _reg, store = _catalogo(tmp_path, modo="isolada")
    real = [1.0] * 5 + [1.5] + [1.0] * 6
    sc = U.criar_cenario_v2(store, demanda_kW=1.0, isolado=True, realizada=real)
    run = _executar(store, sc)
    assert run.state == "interrompida", (run.state, run.error)
    assert run.error["kind"] == "missao_interrompida" and run.error["classe_falha"] == "consigna_inexequivel"
    assert (run.error["intervalos_aplicados"], run.error["intervalos_missao"]) == (5, 12)
    assert run.data == {} and run.summary is None            # nenhum resultado "concluído"
    ev = run.outcome["evidence"]
    assert ev["parcial"] is True and "não é custo da missão" in ev["aviso"]
    assert len(ev["vistas"]["intervalos"]["linhas"]) == 5 and len(ev["vistas"]["fronteiras"]["linhas"]) == 6
    v = RG.verificar(store, run)
    assert v.ok, v.falhas()
    assert v.evidencia.registro_missao.conteudo.intervalos_aplicados == 5


@requer_solver
def test_missao_inviavel_desde_a_primeira_janela(tmp_path):
    """PCC com limite contratado insuficiente e banco pequeno: a 1ª janela é INVIÁVEL — sem energia inventada."""
    _reg, store = _catalogo(tmp_path)

    def mutar(doc):
        doc[E.CHAVE_BLOCO]["pcc"]["limite_importacao_kW"] = 2.0
    run = _executar(store, U.criar_cenario_v2(store, mutar=mutar))
    assert run.state == "interrompida" and run.error["intervalos_aplicados"] < 12
    assert run.error["classe_falha"] in ("inviavel", "bloqueado_validacao")
    assert run.data == {} and RG.verificar(store, run).ok


# ====================================================================== isolamento entre microrredes
@requer_solver
def test_duas_microrredes_isoladas(tmp_path):
    reg = MicrogridRegistry(tmp_path / "dados", adopt_legacy=False)
    ca, cb = U.config_bateria("Microrrede A"), U.config_bateria("Microrrede B", energia_kWh=10.0)
    reg.create(ca)
    reg.create(cb)
    sa, sb = reg.open(ca["installation"]["uid"]), reg.open(cb["installation"]["uid"])
    ra = _executar(sa, U.criar_cenario_v2(sa))
    rb = _executar(sb, U.criar_cenario_v2(sb, tarifa=[0.5] * 12))
    assert ra.state == rb.state == "concluida"
    assert ra.microgrid_uid != rb.microgrid_uid and ra.run_uid != rb.run_uid
    ma, mb = ra.summary["mission"], rb.summary["mission"]
    assert ma["custo_realizado_total_R"] == pytest.approx(50.2)
    assert mb["custo_realizado_total_R"] == pytest.approx(0.5 * 110 + 0.01 * 10)      # tarifa plana, banco de 10 kWh
    assert set(ma["baterias"]) == {U.bateria_id(ca)} and set(mb["baterias"]) == {U.bateria_id(cb)}
    for store, alheia in ((sa, rb), (sb, ra)):
        with pytest.raises(RunNotFound):
            store.get_run(alheia.run_uid)
        with pytest.raises(StoreError):
            store.run_data(alheia.run_uid, RG.N_INDICE)
    assert [r.run_uid for r in sa.list_runs()] == [ra.run_uid] and [r.run_uid for r in sb.list_runs()] == [rb.run_uid]
    assert RG.verificar(sa, ra).ok and RG.verificar(sb, rb).ok
    assert not RG.verificar(sa, rb).ok                      # evidência de B lida no banco de A: recusada


# ====================================================================== Arquivo Científico
@requer_solver
def test_estudo_exportado_e_importado_em_outra_instalacao_sem_recalcular(missao, tmp_path, monkeypatch):
    store, sc, run = missao["store"], missao["sc"], missao["run"]
    pacote, _info = exporter.export_bytes(store, sc.scenario_uid)
    monkeypatch.setattr(X, "submit", lambda *a, **k: (_ for _ in ()).throw(AssertionError("executou")))
    arquivo = ArchiveStore(tmp_path / "outra_instalacao")
    res = arquivo.import_package(pacote)
    view = StudyView(arquivo, res.study.archive_uid)
    arq = view.get_run(run.run_uid)
    assert arq.state == "concluida" and arq.manifest == run.manifest and arq.summary == run.summary
    assert {n: d["sha256"] for n, d in arq.data.items()} == {n: d["sha256"] for n, d in run.data.items()}
    for nome in run.data:
        assert view.run_data(run.run_uid, nome) == store.run_data(run.run_uid, nome)
    v = RG.verificar(view, arq)
    assert v.ok, v.falhas()
    assert view.version_document(sc.version)[E.CHAVE_MOTOR] == E.MOTOR_V2
    assert view.version_document(sc.version)[E.CHAVE_BLOCO] == sc.document[E.CHAVE_BLOCO]


@requer_solver
def test_estudo_com_rodada_interrompida_respeita_o_formato_v1(tmp_path):
    _reg, store = _catalogo(tmp_path / "o", modo="isolada")
    sc = U.criar_cenario_v2(store, demanda_kW=1.0, isolado=True, realizada=[1.0] * 5 + [1.5] + [1.0] * 6)
    run = _executar(store, sc)
    assert run.state == "interrompida"
    pacote, _ = exporter.export_bytes(store, sc.scenario_uid)
    arquivo = ArchiveStore(tmp_path / "d")
    view = StudyView(arquivo, arquivo.import_package(pacote).study.archive_uid)
    arq = view.get_run(run.run_uid)
    assert arq.state == "interrompida" and arq.data == {} and arq.error == run.error
    assert RG.verificar(view, arq).ok


# ====================================================================== V1.6 intacto
def test_cenario_v16_nao_e_afetado_pela_camada_v2(tmp_path):
    _reg, store = _catalogo(tmp_path)
    sc = SV.create(store, name="Cenário V1.6")
    pf = P16.prepare(store, sc)
    assert not any(E.MOTOR_V2 in i.message for i in pf.items)
    assert json.loads(json.dumps(sc.document)).get(E.CHAVE_MOTOR) is None
    pf2 = PF.preparar(store, sc)                              # e o preflight V2 recusa um cenário que não o selecionou
    assert not pf2.ok and any(i.area == "motor" for i in pf2.items if i.level == PF.ERROR)
    _ = (io, pd)
