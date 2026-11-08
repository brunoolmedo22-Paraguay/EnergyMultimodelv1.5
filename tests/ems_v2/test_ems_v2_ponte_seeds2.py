"""Piso 3C-0 — adaptador SOMENTE LEITURA SEEDS2 → ponte, sobre microrredes REAIS do catálogo (diretório temporário).

Verifica isolamento entre microrredes, conservação de UID e procedência, ausência de agregação, leitura sem gravação,
coerência cenário × inventário e o bloqueio explícito de uma microrrede real por parâmetros que o inventário não tem.
As microrredes são fixtures de TESTE (``tests/seeds2_fixtures.py``), não instalações reais.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import sys
from pathlib import Path

import pytest

from ems_v2 import fixtures_3c0 as F
from ems_v2.ponte import cenario as CN, inventario as IV, projecao as PJ, requisitos as RQ
from ems_v2.ponte_seeds2 import leitor as L
from ems_v2.provenance import Procedencia
from seeds2.microgrid import config as C
from seeds2.microgrid.adapter import build_plan
from seeds2.microgrid.registry import MicrogridNotFound, MicrogridRegistry
from seeds2.operation import service as SV

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from seeds2_fixtures import battery_params, v16_equivalent_config  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic


def _config_b() -> dict:
    """Segunda microrrede, com inventário DIFERENTE: térmica + bateria com limites de SOC apenas sugeridos."""
    cfg = C.new_config("Microrrede B (teste)")
    cfg["installation"].update(nature="laboratorio", operation_mode="isolada")
    C.add_equipment(cfg, C.new_equipment("thermal", "Gerador diesel", tag="TER-01", params={
        "dynamic": "local_generator", "pmax_kW": 60.0, "pmin_kW": 15.0, "cvu_rs_MWh": 1200.0, "startup_cost_rs": 40.0}))
    b = C.add_equipment(cfg, C.new_equipment("battery", "Banco B", params=battery_params(
        np_=10, soc_limits_source="sugerido", energy_kWh=40.0)))
    cfg["run_conditions"]["battery_soc0_pct"][b["id"]] = 50.0
    cfg["energy_balance"]["grid_connection"] = "isolada"
    cfg["commissioning"].update(completed=True, step=5, completed_at=C.utc_now())
    return cfg


@pytest.fixture()
def catalogo(tmp_path):
    reg = MicrogridRegistry(tmp_path / "dados", adopt_legacy=False)
    a, b = v16_equivalent_config("Microrrede A (teste)"), _config_b()
    reg.create(a)
    reg.create(b)
    return reg, a, b


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_isolamento_entre_duas_microrredes_reais(catalogo):
    reg, a, b = catalogo
    ia, ib = L.ler_inventario(reg, a["installation"]["uid"]), L.ler_inventario(reg, b["installation"]["uid"])
    assert IV.validar_inventario(ia).aceito and IV.validar_inventario(ib).aceito
    ids_a = {e["id"] for e in a["equipment"]} | {x["id"] for e in a["equipment"] for x in e.get("arrays", [])}
    ids_b = {e["id"] for e in b["equipment"]}
    assert ia.uids() == ids_a and ib.uids() == ids_b and not ia.uids() & ib.uids()
    assert all(d.microrrede_uid == a["installation"]["uid"] for d in ia.dispositivos)
    assert all(d.microrrede_uid == b["installation"]["uid"] for d in ib.dispositivos)
    assert IV.hash_inventario(ia) != IV.hash_inventario(ib)
    misto = IV.InventarioMicrorrede(ia.versao_contrato, ia.identidade, ia.modo_operacao, ia.conexao_rede,
                                    ia.dispositivos + ib.dispositivos[:1], ia.retirados, ia.procedencia)
    assert "dispositivo_de_outra_microrrede" in IV.validar_inventario(misto).codigos()
    ma, mb = RQ.matriz_parametros(ia), RQ.matriz_parametros(ib)
    assert {c.uid for c in ma.entradas}.isdisjoint({c.uid for c in mb.entradas})


def test_conserva_uid_procedencia_e_nao_agrega(catalogo):
    reg, a, _ = catalogo
    st = reg.open(a["installation"]["uid"]).load()
    inv = L.ler_inventario(reg, a["installation"]["uid"])
    assert (inv.identidade.revisao_config, inv.identidade.impressao_config) == (st.revision, st.fingerprint)
    assert inv.identidade.incarnacao == reg.get(a["installation"]["uid"]).incarnation
    for eq in a["equipment"]:
        d = inv.dispositivo(eq["id"])
        assert d is not None and d.nome == eq["name"] and d.tag == eq["tag"]
        for v in d.valores:
            if v.origem == "inventario_declarado":
                assert v.procedencia.tipo == "declarado_seeds2" and v.procedencia.sha256 == st.fingerprint
                assert v.caminho_fonte.startswith(f"equipment[{eq['id']}]")
        for arr in eq.get("arrays", []):
            assert inv.dispositivo(arr["id"]).pai == eq["id"]
    pem = [d for d in inv.dispositivos if d.tipo == "pemfc"]
    assert sorted(d.quantidade for d in pem) == [1, 3]                       # dois registros, sem soma
    assert build_plan(a).spec["fc"]["N_fc"] == 4                             # o V1.6 agrega; a ponte não
    assert sum(len(IV.recursos_ems(d)) for d in pem) == 4                    # 3 + 1 unidades identificáveis
    bats = [d for d in inv.dispositivos if d.tipo == "bateria"]
    assert len(bats) == 2 and all(d.valor("model_n_parallel").numero == 66.0 for d in bats)
    m = RQ.matriz_parametros(inv)
    assert m.de(bats[0].uid, "s_min").classe == "disponivel_verificavel"     # origem 'instalacao'
    assert m.de(bats[0].uid, "C_b").classe == "derivavel"                    # parametrização do modelo científico
    assert m.de(pem[0].uid, "P_max").classe == "derivavel"


def test_valor_sugerido_do_seeds2_e_bloqueado(catalogo):
    reg, _, b = catalogo
    inv = L.ler_inventario(reg, b["installation"]["uid"])
    bat = next(d for d in inv.dispositivos if d.tipo == "bateria")
    assert bat.valor("soc_min_pct").origem == "inventario_sugerido_seeds2"
    c = RQ.matriz_parametros(inv).de(bat.uid, "s_min")
    assert (c.classe, c.codigo, c.bloqueia) == ("faltante_necessario", "valor_sugerido_nao_confirmado", True)
    ter = next(d for d in inv.dispositivos if d.tipo == "termica")
    cvu = RQ.matriz_parametros(inv, termos={"geracao_termica"}).de(ter.uid, "CVU")
    assert (cvu.numero, cvu.unidade, cvu.numero_bruto, cvu.unidade_bruta) == (1.2, "R$/kWh", 1200.0, "R$/MWh")


def test_leitura_nao_grava_nada(catalogo):
    reg, a, _ = catalogo
    uid = a["installation"]["uid"]
    db = reg.dir_for(uid) / "seeds2.db"
    cfg_antes = copy.deepcopy(reg.open(uid).load().config)
    st = reg.open(uid)
    sc = SV.create(st, name="Cenário de teste")
    antes = (_sha(db), st.history(), [e.uid for e in reg.entries()])
    for _ in range(2):
        L.ler_inventario(reg, uid)
        L.ler_cenario(reg, uid, sc.scenario_uid)
    assert (_sha(db), st.history(), [e.uid for e in reg.entries()]) == antes
    assert reg.open(uid).load().config == cfg_antes
    assert build_plan(cfg_antes).spec_fingerprint == build_plan(reg.open(uid).load().config).spec_fingerprint


def test_revisao_fixada_e_deriva_do_inventario(catalogo):
    reg, _, b = catalogo
    uid = b["installation"]["uid"]
    st = reg.open(uid)
    sc = SV.create(st, name="Cenário B")
    cfg = copy.deepcopy(st.load().config)
    ter = next(e for e in cfg["equipment"] if e["kind"] == "thermal")
    C.update_equipment(cfg, ter["id"], params={"pmax_kW": 70.0})
    st.save(cfg, st.load().revision, note="pmax alterado")
    v1, v2 = L.ler_inventario(reg, uid, revisao=1), L.ler_inventario(reg, uid)
    assert v1.dispositivo(ter["id"]).valor("pmax_kW").numero == 60.0
    assert v2.dispositivo(ter["id"]).valor("pmax_kW").numero == 70.0
    assert v1.identidade.impressao_inventario != v2.identidade.impressao_inventario
    cen = L.ler_cenario(reg, uid, sc.scenario_uid)
    assert cen.referencia_inventario.revisao_config == 1
    assert "inventario_divergente" in {c.codigo for c in CN.coerencia_cenario_inventario(cen, v2)}
    assert "inventario_divergente" not in {c.codigo for c in CN.coerencia_cenario_inventario(cen, v1)}


def test_cenario_real_condicoes_e_outra_microrrede(catalogo):
    reg, a, b = catalogo
    ua, ub = a["installation"]["uid"], b["installation"]["uid"]
    st = reg.open(ua)
    sc = SV.create(st, name="Cenário A")
    doc = copy.deepcopy(sc.document)
    bat_ids = [e["id"] for e in a["equipment"] if e["kind"] == "battery"]
    for bid in bat_ids:
        doc["initialization"]["equipment"][bid]["soc0_pct"] = 60.0
    for e in a["equipment"]:
        if e["kind"] == "pemfc":
            doc["initialization"]["equipment"][e["id"]].update(state="desligada", units_on=0, power_kW=0.0)
    sc2 = SV.save(st, doc, sc.version)
    cen = L.ler_cenario(reg, ua, sc.scenario_uid)
    assert cen.versao_cenario == sc2.version and cen.impressao_cenario == sc2.fingerprint
    assert CN.validar_cenario(cen).aceito
    soc = cen.condicao(bat_ids[0]).soc
    assert (soc.valor, soc.valor_bruto, soc.unidade_bruta) == (0.6, 60.0, "%")
    inv_a, inv_b = L.ler_inventario(reg, ua), L.ler_inventario(reg, ub)
    coer = CN.coerencia_cenario_inventario(cen, inv_a)
    arranjos = {x["id"] for e in a["equipment"] for x in e.get("arrays", [])}
    assert {(c.codigo, c.severidade) for c in coer} == {("disponibilidade_herdada_do_agrupador", "aviso")}
    assert {c.caminho for c in coer} == {f"condicoes_iniciais[{u}]" for u in arranjos}
    assert "cenario_de_outra_microrrede" in {c.codigo for c in CN.coerencia_cenario_inventario(cen, inv_b)}
    assert L.ler_cenario(reg, ua, sc.scenario_uid, 1).versao_cenario == 1


def test_microrrede_real_bloqueada_com_explicacao(catalogo):
    """A microrrede equivalente ao V1.6 NÃO pode ser executada pelo EMS V2 hoje: falta o que o inventário não tem."""
    reg, a, _ = catalogo
    ua = a["installation"]["uid"]
    st = reg.open(ua)
    sc = SV.create(st, name="Cenário A")
    inv, cen = L.ler_inventario(reg, ua), L.ler_cenario(reg, ua, sc.scenario_uid)
    pol = dataclasses.replace(F.politicas(), procedencia=Procedencia("decisao_responsavel", "teste"))
    prev = F.previsao()
    p = PJ.montar_entrada(inv, cen, prev, F.definicao(), pol, contexto="operacional")
    assert p.entrada is None
    por_simbolo = {(c.caminho.split(".")[-1], c.codigo, c.severidade) for c in p.constatacoes}
    for esperado in [("eta_c", "parametro_obrigatorio_ausente", "erro"), ("eta_d", "parametro_obrigatorio_ausente", "erro"),
                     ("Pc_max", "parametro_obrigatorio_ausente", "pendente"),
                     ("hipotese_autodescarga", "parametro_obrigatorio_ausente", "erro"),
                     ("P_min", "parametro_obrigatorio_ausente", "erro"),
                     ("curva_h2", "parametro_obrigatorio_ausente", "pendente")]:
        assert esperado in por_simbolo, esperado
    br = {c.codigo for c in L.constatacoes_previsoes_seeds2(sc.document)}
    assert {"previsoes_ausentes", "demanda_sem_uid_e_criticidade"} <= br


def test_microrrede_excluida_nao_e_lida(catalogo, monkeypatch):
    reg, _, b = catalogo
    ub = b["installation"]["uid"]
    monkeypatch.setenv("SEEDS2_DEV_MODE", "1")
    reg.delete(ub, expected_incarnation=reg.get(ub).incarnation)
    with pytest.raises(MicrogridNotFound):
        L.ler_inventario(reg, ub)
