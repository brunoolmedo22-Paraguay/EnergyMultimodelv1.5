"""Piso 2A — Centro de Operação: cenários operativos (persistência, isolamento, concorrência, vínculo com o
inventário) e regras de Inicialização (erro de coerência / advertência / capacidade pendente).

Sem interface (ver ``test_seeds2_piso2a_app.py``). Cada teste usa um ``SEEDS2_DATA_DIR`` temporário próprio.
"""
from __future__ import annotations

import copy
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np

from seeds2.microgrid import adapter as A
from seeds2.microgrid import config as C
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.microgrid.store import (LATEST_DB_VERSION, IdentityError, MicrogridDeletedError, MicrogridStore,
                                    ScenarioConflictError, ScenarioNotFound, StoreError)
from seeds2.operation import contracts
from seeds2.operation import initialization as I
from seeds2.operation import scenarios as S
from seeds2.operation import service
from seeds2_fixtures import v16_equivalent_config

RAIZ = Path(__file__).resolve().parents[1]


def _ids(doc: dict, kind: str) -> list[str]:
    return [e for e, r in doc["inventory_ref"]["equipment"].items() if r["kind"] == kind]


def _thermal_eq(**params) -> dict:
    p = {"dynamic": "local_generator", "pmax_kW": 100.0, "pmin_kW": 20.0, "cvu_rs_MWh": 900.0, "startup_cost_rs": 50.0}
    p.update(params)
    return C.new_equipment("thermal", "Gerador diesel", tag="GD-01", params=p)


def _complete(doc: dict, soc: float = 60.0) -> dict:
    """Estados iniciais coerentes para todos os equipamentos habilitados da fixture V1.6."""
    st = doc["initialization"]["equipment"]
    for e in _ids(doc, "battery"):
        st[e]["soc0_pct"] = soc
    for e in _ids(doc, "pemfc"):
        st[e].update(state="em_operacao", units_on=1, power_kW=10.0)
    for e in _ids(doc, "thermal"):
        st[e].update(state="desligada", power_kW=0.0)
    return doc


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        os.environ["SEEDS2_DATA_DIR"] = str(self.dir)
        self.reg = MicrogridRegistry(self.dir)

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, name: str = "Microrrede A", cfg: dict | None = None) -> tuple[str, MicrogridStore]:
        cfg = cfg or v16_equivalent_config(name)
        self.reg.create(cfg, origin="commissioning")
        uid = cfg["installation"]["uid"]
        return uid, self.reg.open(uid)


# =========================================================================== persistência e ciclo de vida
class CenarioPersistenciaTest(_Base):
    def test_criar_editar_duplicar_e_listar(self):
        uid, st = self.make()
        sc = service.create(st, name="  Operação   nominal ", description="Base do experimento")
        self.assertEqual((sc.version, sc.name, sc.origin, sc.microgrid_uid), (1, "Operação nominal", "new", uid))
        self.assertEqual(sc.base_revision, st.load().revision)
        self.assertEqual(sc.base_fingerprint, st.load().fingerprint)
        # equipamentos habilitados recebem estado padrão: disponível, demais campos NÃO definidos (nada inventado)
        states = sc.document["initialization"]["equipment"]
        self.assertEqual(len(states), 6)
        for e in _ids(sc.document, "battery"):
            self.assertEqual(states[e], {"availability": "disponivel", "note": "", "soc0_pct": None})
        # edição → nova versão
        doc = _complete(copy.deepcopy(sc.document))
        v2 = service.save(st, doc, 1)
        self.assertEqual(v2.version, 2)
        self.assertEqual(st.get_scenario(sc.scenario_uid).document, doc)
        self.assertEqual(st.get_scenario(sc.scenario_uid, version=1).document, sc.document)   # versão 1 imutável
        # mesmo conteúdo → não cria versão
        self.assertEqual(service.save(st, copy.deepcopy(doc), 2).version, 2)
        # duplicar = cenário independente
        dup = service.duplicate(st, sc.scenario_uid, name="Cópia — SOC baixo")
        self.assertNotEqual(dup.scenario_uid, sc.scenario_uid)
        self.assertEqual((dup.version, dup.origin), (1, "duplicate"))
        self.assertEqual(dup.document["lineage"]["duplicated_from"],
                         {"scenario_uid": sc.scenario_uid, "version": 2, "name": "Operação nominal"})
        self.assertEqual(dup.document["initialization"], doc["initialization"])
        d2 = copy.deepcopy(dup.document)
        for e in _ids(d2, "battery"):
            d2["initialization"]["equipment"][e]["soc0_pct"] = 25.0
        service.save(st, d2, 1)
        orig = st.get_scenario(sc.scenario_uid)
        self.assertEqual(orig.version, 2)                                    # o original não muda
        self.assertTrue(all(orig.document["initialization"]["equipment"][e]["soc0_pct"] == 60.0
                            for e in _ids(orig.document, "battery")))
        self.assertEqual([s.name for s in st.list_scenarios()], ["Operação nominal", "Cópia — SOC baixo"])
        self.assertEqual([h["version"] for h in st.scenario_history(sc.scenario_uid)], [2, 1])

    def test_cenario_nao_altera_a_configuracao_fisica(self):
        uid, st = self.make()
        before = st.load()
        hist = st.history()
        sc = service.create(st, name="Sem efeito no inventário")
        service.save(st, _complete(copy.deepcopy(sc.document), soc=5.0), 1)
        service.duplicate(st, sc.scenario_uid, name="Cópia")
        after = st.load()
        self.assertEqual((after.revision, after.fingerprint, after.config), (before.revision, before.fingerprint, before.config))
        self.assertEqual(st.history(), hist)
        # condições da rodada do Piso 1 e especificação V1.6 intactas
        self.assertEqual(after.config["run_conditions"], before.config["run_conditions"])
        self.assertEqual(A.build_plan(after.config).spec_fingerprint, A.build_plan(before.config).spec_fingerprint)

    def test_versoes_do_cenario_sao_imutaveis(self):
        _, st = self.make()
        sc = service.create(st, name="Imutável")
        with sqlite3.connect(st.path) as con:
            for sql in ("UPDATE scenario_versions SET note = 'x'", "DELETE FROM scenario_versions"):
                with self.assertRaises(sqlite3.IntegrityError):
                    con.execute(sql)
        self.assertEqual(st.get_scenario(sc.scenario_uid, 1).fingerprint, sc.fingerprint)

    def test_retomar_apos_reinicio_em_novo_processo(self):
        uid, st = self.make()
        sc = service.create(st, name="Persistente", description="sobrevive ao reinício")
        doc = _complete(copy.deepcopy(sc.document), soc=42.0)
        service.save(st, doc, 1)
        code = ("import json,sys; from seeds2.microgrid.registry import MicrogridRegistry; "
                "r=MicrogridRegistry(sys.argv[1]); s=r.open(sys.argv[2]); "
                "x=[(c.scenario_uid, c.name, c.version, c.document['initialization']) for c in s.list_scenarios()]; "
                "print(json.dumps(x))")
        out = subprocess.run([sys.executable, "-c", code, str(self.dir), uid], cwd=RAIZ, capture_output=True, text=True,
                             env={**os.environ, "PYTHONPATH": str(RAIZ), "PYTHONDONTWRITEBYTECODE": "1"},
                             check=True, timeout=120)
        got = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(got, [[sc.scenario_uid, "Persistente", 2, doc["initialization"]]])

    def test_esquema_v3_migra_banco_v2_sem_alterar_dados(self):
        uid, st = self.make()
        before = st.load()
        db = st.path
        with sqlite3.connect(db) as con:                 # reproduz um banco v2 (anterior ao Piso 2A e ao 2C)
            for t in ("scenario_run_data_open_only", "scenario_run_data_immutable_u", "scenario_run_data_immutable_d",
                      "scenario_runs_final_u", "scenario_runs_identity_u", "scenario_runs_immutable_d",
                      "scenario_versions_immutable_u", "scenario_versions_immutable_d"):
                con.execute(f"DROP TRIGGER {t}")
            con.execute("DROP TABLE scenario_run_data")
            con.execute("DROP TABLE scenario_runs")
            con.execute("DROP TABLE scenario_versions")
            con.execute("DROP TABLE scenarios")
            con.execute("PRAGMA user_version = 2")
        st2 = MicrogridRegistry(self.dir).open(uid)
        self.assertEqual(LATEST_DB_VERSION, 4)                         # Piso 2C: v4 (rodadas de cenário)
        self.assertEqual(st2.db_version(), 4)                          # v2 → v3 → v4 numa única migração
        self.assertTrue(db.with_name(db.name + ".bak-v2").is_file())       # cópia antes de migrar
        after = st2.load()
        self.assertEqual((after.revision, after.fingerprint), (before.revision, before.fingerprint))
        self.assertEqual(st2.list_scenarios(), [])
        self.assertEqual(service.create(st2, name="Após migração").version, 1)

    def test_backup_de_microrrede_continua_compativel(self):
        uid, st = self.make()
        service.create(st, name="Não vai no ZIP")
        data = st.export_backup()
        m = st.inspect_backup(data).manifest
        self.assertEqual(m["db_schema_version"], LATEST_DB_VERSION)     # formato do ZIP inalterado; esquema atual
        tgt = MicrogridRegistry(tempfile.mkdtemp(dir=self.dir))
        new_uid, stored = tgt.import_new(data)
        self.assertEqual(new_uid, uid)
        self.assertEqual(tgt.open(uid).list_scenarios(), [])            # o backup do Piso 1 não transporta cenários


# =========================================================================== vínculo com o inventário
class CenarioInventarioTest(_Base):
    def test_vinculo_com_a_revisao_e_deriva_explicita(self):
        uid, st = self.make()
        sc = service.create(st, name="Referência")
        ref = sc.document["inventory_ref"]
        saved = st.load()
        self.assertEqual((ref["config_revision"], ref["config_fingerprint"]), (saved.revision, saved.fingerprint))
        self.assertEqual(ref["inventory_fingerprint"], S.inventory_fingerprint(saved.config))
        order = sorted(ref["equipment"], key=lambda e: ref["equipment"][e]["position"])     # ordem do inventário
        self.assertEqual(order, [e["id"] for e in saved.config["equipment"]])
        d = S.drift(sc.document, saved.config, saved.revision)
        self.assertEqual((d.same_revision, d.stale, d.added, d.removed, d.changed), (True, False, [], [], []))
        # mudança não física (descrição) → nova revisão sem deriva de inventário
        cfg = copy.deepcopy(saved.config)
        cfg["installation"]["description"] = "nova descrição"
        r2 = st.save(cfg, saved.revision)
        d = S.drift(sc.document, r2.config, r2.revision)
        self.assertEqual((d.same_revision, d.stale), (False, False))
        # mudança física: retira um banco, altera a PEMFC A (3 → 2) e inclui uma térmica
        cfg = copy.deepcopy(r2.config)
        bat = _ids(sc.document, "battery")[0]
        fc_a = next(e for e, r in ref["equipment"].items() if r["name"] == "Bloco PEMFC A")
        C.retire_equipment(cfg, bat, "teste")
        C.update_equipment(cfg, fc_a, params={"quantity": 2})
        th = C.add_equipment(cfg, _thermal_eq())
        r3 = st.save(cfg, r2.revision)
        d = S.drift(sc.document, r3.config, r3.revision)
        self.assertTrue(d.stale)
        self.assertEqual((d.added, d.removed, d.changed), ([th["id"]], [bat], [fc_a]))
        # o cenário salvo continua na revisão original até a atualização EXPLÍCITA
        self.assertEqual(st.get_scenario(sc.scenario_uid).base_revision, 1)
        doc = copy.deepcopy(sc.document)
        doc["initialization"]["equipment"][bat]["soc0_pct"] = 55.0
        doc["initialization"]["equipment"][fc_a].update(state="em_operacao", units_on=3, power_kW=20.0)
        cur = service.save(st, doc, 1)
        rb = service.rebase(st, sc.scenario_uid, cur.version)
        self.assertEqual((rb.version, rb.base_revision, rb.base_fingerprint), (3, r3.revision, r3.fingerprint))
        ini = rb.document["initialization"]
        self.assertNotIn(bat, ini["equipment"])
        self.assertEqual(ini["orphaned"][bat]["state"]["soc0_pct"], 55.0)          # preservado, não aplicado
        self.assertEqual(ini["orphaned"][bat]["orphaned_at_revision"], r3.revision)
        self.assertEqual(ini["equipment"][th["id"]], I.default_state("thermal"))     # novo equipamento: não definido
        msgs = [f.message for f in S.findings(rb.document) if f.level == I.ERROR]
        self.assertTrue(any("3 unidade(s) em operação" in m and "2 instalada(s)" in m for m in msgs), msgs)
        self.assertIn("revisão 1 → 3", st.scenario_history(sc.scenario_uid)[0]["note"])
        # revisões do inventário e versões do cenário são numerações independentes
        self.assertEqual(st.load().revision, r3.revision)

    def test_revisao_base_inexistente_ou_divergente_e_recusada(self):
        _, st = self.make()
        sc = service.create(st, name="Base")
        doc = copy.deepcopy(sc.document)
        doc["scenario_uid"] = S.new_scenario_uid()
        doc["inventory_ref"]["config_revision"] = 99
        with self.assertRaises(StoreError):
            st.create_scenario(doc)
        doc["inventory_ref"]["config_revision"] = 1
        doc["inventory_ref"]["config_fingerprint"] = "0" * 64
        with self.assertRaises(StoreError):
            st.create_scenario(doc)
        self.assertEqual(len(st.list_scenarios()), 1)

    def test_microrrede_nao_comissionada_nao_cria_cenario(self):
        cfg = v16_equivalent_config("Em configuração")
        cfg["commissioning"].update(completed=False, step=2, completed_at=None)
        uid, st = self.make(cfg=cfg)
        with self.assertRaises(StoreError):
            service.create(st, name="Prematuro")
        self.assertEqual(st.list_scenarios(), [])


# =========================================================================== isolamento entre microrredes
class CenarioIsolamentoTest(_Base):
    def test_duas_microrredes_com_cenarios_independentes(self):
        ua, a = self.make("A")
        ub, b = self.make("B")
        sa = service.create(a, name="Cenário de A")
        sb1 = service.create(b, name="Cenário de B1")
        service.create(b, name="Cenário de B2")
        self.assertEqual([s.name for s in a.list_scenarios()], ["Cenário de A"])
        self.assertEqual([s.name for s in b.list_scenarios()], ["Cenário de B1", "Cenário de B2"])
        with self.assertRaises(ScenarioNotFound):
            b.get_scenario(sa.scenario_uid)
        with self.assertRaises(ScenarioNotFound):
            a.get_scenario(sb1.scenario_uid)
        # documento de A nunca é gravado em B (nem como novo, nem como edição)
        foreign = copy.deepcopy(sa.document)
        with self.assertRaises(IdentityError):
            b.create_scenario(foreign)
        with self.assertRaises(ScenarioNotFound):
            b.save_scenario(foreign, 1)
        # os bancos são arquivos distintos: nenhuma tabela global de cenários
        self.assertNotEqual(a.path, b.path)
        with sqlite3.connect(self.dir / "registry.db") as con:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertFalse(any("scenario" in t for t in tables))

    def test_exclusao_e_reimportacao_sem_contaminacao(self):
        uid, st = self.make()
        old_inc = st.incarnation
        sc = service.create(st, name="Antes da exclusão")
        old_doc = copy.deepcopy(sc.document)
        backup = st.export_backup()
        self.reg.delete(uid)
        new_uid, _ = self.reg.import_new(backup)                       # mesmo UID, nova incarnação
        self.assertEqual(new_uid, uid)
        fresh = self.reg.open(uid)
        self.assertNotEqual(fresh.incarnation, old_inc)
        self.assertEqual(fresh.list_scenarios(), [])                   # nada do cenário antigo
        # a referência antiga é recusada (lápide/incarnação), sem gravar na microrrede reimportada
        for call in (lambda: st.list_scenarios(), lambda: st.get_scenario(sc.scenario_uid),
                     lambda: st.save_scenario(old_doc, 1), lambda: service.create(st, name="x")):
            with self.assertRaises(MicrogridDeletedError):
                call()
        # documento da incarnação antiga não entra na nova, mesmo com identificador novo
        stale = copy.deepcopy(old_doc)
        stale["scenario_uid"] = S.new_scenario_uid()
        with self.assertRaises(IdentityError):
            fresh.create_scenario(stale)
        self.assertEqual(fresh.list_scenarios(), [])
        self.assertEqual(service.create(fresh, name="Nova incarnação").document["microgrid"]["incarnation"],
                         fresh.incarnation)


# =========================================================================== concorrência entre sessões
class CenarioConcorrenciaTest(_Base):
    def test_duas_sessoes_sem_sobrescrita_silenciosa(self):
        uid, st = self.make()
        sc = service.create(st, name="Compartilhado")
        s1 = self.reg.open(uid)                                       # duas "sessões" (instâncias independentes)
        s2 = MicrogridRegistry(self.dir).open(uid)
        d1 = _complete(copy.deepcopy(s1.get_scenario(sc.scenario_uid).document), soc=30.0)
        d2 = _complete(copy.deepcopy(s2.get_scenario(sc.scenario_uid).document), soc=70.0)
        self.assertEqual(service.save(s1, d1, 1).version, 2)
        with self.assertRaises(ScenarioConflictError) as cm:
            service.save(s2, d2, 1)
        self.assertEqual((cm.exception.expected, cm.exception.current), (1, 2))
        cur = st.get_scenario(sc.scenario_uid)
        self.assertEqual(cur.document, d1)                            # a gravação de s1 permanece
        self.assertEqual([h["version"] for h in st.scenario_history(sc.scenario_uid)], [2, 1])
        # s2 recarrega e reaplica conscientemente
        self.assertEqual(service.save(s2, d2, cur.version).version, 3)

    def test_gravacoes_simultaneas_um_unico_vencedor(self):
        uid, st = self.make()
        sc = service.create(st, name="Corrida")
        barrier = threading.Barrier(2)
        out: dict[int, str] = {}

        def worker(i: int, soc: float) -> None:
            s = MicrogridRegistry(self.dir).open(uid)
            doc = _complete(copy.deepcopy(sc.document), soc=soc)
            barrier.wait()
            try:
                service.save(s, doc, 1)
                out[i] = "ok"
            except ScenarioConflictError:
                out[i] = "conflito"

        ts = [threading.Thread(target=worker, args=(i, 30.0 + 10 * i)) for i in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(60)
        self.assertEqual(sorted(out.values()), ["conflito", "ok"])
        self.assertEqual(st.get_scenario(sc.scenario_uid).version, 2)
        self.assertEqual(len(st.scenario_history(sc.scenario_uid)), 2)


# =========================================================================== regras de inicialização
class InicializacaoRegrasTest(_Base):
    def setUp(self):
        super().setUp()
        cfg = v16_equivalent_config("Regras")
        C.add_equipment(cfg, _thermal_eq())
        self.uid, self.st = self.make(cfg=cfg)
        self.sc = service.create(self.st, name="Regras")
        self.doc = copy.deepcopy(self.sc.document)
        self.refs = self.doc["inventory_ref"]["equipment"]
        self.bat = _ids(self.doc, "battery")[0]
        self.fc = next(e for e, r in self.refs.items() if r["name"] == "Bloco PEMFC A")   # 3 sistemas
        self.th = _ids(self.doc, "thermal")[0]

    def levels(self, eq_id: str, **state) -> dict[str, list[str]]:
        kind = self.refs[eq_id]["kind"]
        s = {**I.default_state(kind), **state}
        out: dict[str, list[str]] = {}
        for f in I.validate_state(eq_id, kind, s, self.refs[eq_id]):
            out.setdefault(f.level, []).append(f.message)
        return out

    def test_soc_fora_do_recomendado_avisa_sem_bloquear(self):
        for soc in (0.0, 5.0, 10.0, 95.0, 100.0):
            lv = self.levels(self.bat, soc0_pct=soc)
            self.assertNotIn(I.ERROR, lv, (soc, lv))
            self.assertIn(I.WARNING, lv, soc)
            self.assertIn(I.PENDING, lv, soc)                         # incompatibilidade registrada do EMS V1.6
        doc = _complete(copy.deepcopy(self.doc), soc=5.0)
        self.assertEqual(service.save(self.st, doc, 1).version, 2)     # salva normalmente
        lv = self.levels(self.bat, soc0_pct=50.0)
        self.assertEqual(lv, {})                                      # dentro da restrição: sem constatações

    def test_hierarquia_dos_limites_de_soc(self):
        self.assertIn("limite físico", " ".join(self.levels(self.bat, soc0_pct=120.0)[I.ERROR]))
        self.assertIn("limite físico", " ".join(self.levels(self.bat, soc0_pct=-1.0)[I.ERROR]))
        self.assertIn("restrição operacional declarada", self.levels(self.bat, soc0_pct=10.0)[I.WARNING][0])
        ref = dict(self.refs[self.bat], soc_limits_source="sugerido")
        f = I.validate_state(self.bat, "battery", {**I.default_state("battery"), "soc0_pct": 10.0}, ref)
        self.assertIn("intervalo recomendado", next(x.message for x in f if x.level == I.WARNING))
        self.assertEqual(self.levels(self.bat)[I.INCOMPLETE], ["SOC inicial não definido."])

    def test_pemfc_estados_coerentes_e_contraditorios(self):
        # desligada é coerente, mas o EMS V1.6 não interpreta o estado declarado (assume n_ini = N_fc) → pendente
        self.assertEqual(list(self.levels(self.fc, state="desligada")), [I.PENDING])
        self.assertEqual(list(self.levels(self.fc, state="desligada", power_kW=0.0, units_on=0)), [I.PENDING])
        err = self.levels(self.fc, state="desligada", power_kW=25.0)[I.ERROR]
        self.assertIn("desligada não pode entregar 25 kW", err[0])
        self.assertIn(I.ERROR, self.levels(self.fc, state="desligada", units_on=2))
        ok = self.levels(self.fc, state="em_operacao", units_on=2, power_kW=30.0)
        self.assertNotIn(I.ERROR, ok)
        self.assertIn(I.PENDING, ok)                                  # n_ini do EMS V1.6 não é interpretado
        self.assertIn(I.ERROR, self.levels(self.fc, state="em_operacao", units_on=4, power_kW=30.0))     # > instaladas
        self.assertIn(I.ERROR, self.levels(self.fc, state="em_operacao", units_on=0, power_kW=0.0))
        unit = self.refs[self.fc]["unit_max_kW"]
        self.assertIn(I.ERROR, self.levels(self.fc, state="em_operacao", units_on=1, power_kW=unit * 1.5))
        self.assertIn(I.ERROR, self.levels(self.fc, availability="indisponivel", state="em_operacao", units_on=1, power_kW=5.0))
        self.assertIn(I.INCOMPLETE, self.levels(self.fc, state="em_operacao", units_on=1))
        partida = self.levels(self.fc, state="em_partida", units_on=1)
        self.assertNotIn(I.ERROR, partida)
        self.assertTrue(any("não modela a física de partida" in w for w in partida[I.WARNING]))
        doc = copy.deepcopy(self.doc)
        doc["initialization"]["equipment"][self.fc].update(state="desligada", power_kW=25.0)
        with self.assertRaises(S.ScenarioValidationError):
            service.save(self.st, doc, 1)
        self.assertEqual(self.st.get_scenario(self.sc.scenario_uid).version, 1)        # nada gravado

    def test_termica_estados(self):
        self.assertEqual(list(self.levels(self.th, state="desligada", power_kW=0.0)), [I.PENDING])
        self.assertIn(I.ERROR, self.levels(self.th, state="desligada", power_kW=40.0))
        self.assertIn(I.ERROR, self.levels(self.th, state="em_operacao", power_kW=150.0))   # > Pmáx
        below = self.levels(self.th, state="em_operacao", power_kW=10.0)[I.ERROR]        # < Pmín técnica
        self.assertIn("potência mínima técnica", below[0])
        ok = self.levels(self.th, state="em_operacao", power_kW=50.0)
        self.assertNotIn(I.ERROR, ok)
        self.assertIn(I.PENDING, ok)
        self.assertNotIn(I.ERROR, self.levels(self.th, state="em_partida", power_kW=5.0))   # partida abaixo de Pmín
        self.assertIn(I.ERROR, self.levels(self.th, availability="indisponivel", state="em_partida"))

    def test_renovaveis_apenas_disponibilidade(self):
        pv = _ids(self.doc, "pv")[0]
        self.assertEqual(self.levels(pv), {})                          # nenhuma potência inicial exigida
        self.assertIn(I.PENDING, self.levels(pv, availability="indisponivel"))
        self.assertEqual(I.FIELDS["pv"], ("availability", "note"))
        self.assertIn(I.ERROR, self.levels(pv, power_kW=10.0))         # campo inexistente para fonte ambiental

    def test_estados_estruturalmente_invalidos(self):
        self.assertIn(I.ERROR, self.levels(self.bat, soc0_pct="60"))
        self.assertIn(I.ERROR, self.levels(self.bat, availability="talvez"))
        self.assertIn(I.ERROR, self.levels(self.fc, state="ligada"))
        self.assertIn(I.ERROR, self.levels(self.fc, state="em_operacao", units_on=1.5))
        doc = copy.deepcopy(self.doc)
        doc["initialization"]["equipment"]["eq-000000000000"] = {"availability": "disponivel"}
        self.assertTrue(any(f.level == I.ERROR for f in S.findings(doc)))

    def test_soc_iniciais_diferentes_entre_bancos_e_pendencia_global(self):
        doc = _complete(copy.deepcopy(self.doc), soc=60.0)
        doc["initialization"]["equipment"][self.th].update(state="desligada")
        self.assertFalse([f for f in S.findings(doc) if f.eq_id is None])
        doc["initialization"]["equipment"][self.bat]["soc0_pct"] = 40.0
        glob = [f for f in S.findings(doc) if f.eq_id is None]
        self.assertEqual([f.level for f in glob], [I.PENDING])

    def test_prontidao_nunca_declara_execucao(self):
        """Piso 2C: a prontidão do DOCUMENTO nunca declara o cenário executável — a decisão é do preflight científico
        (``executable`` = None); Estratégia e Execução são etapas reais e começam não definidas."""
        doc = _complete(copy.deepcopy(self.doc))
        doc["initialization"]["equipment"][self.th].update(state="desligada")
        rd = S.readiness(doc, S.findings(doc), None)
        self.assertEqual(rd["stages"]["inicializacao"][0], "ok")
        self.assertIsNone(rd["executable"])
        self.assertEqual(rd["stages"]["estrategia"][:2], ("warn", "Não definida"))
        self.assertEqual(rd["stages"]["execucao"][:2], ("warn", "Janela não definida"))
        # Piso 2B: Previsões passou a ser uma etapa real; sem previsões, ela é declarada incompleta (nunca pronta)
        self.assertEqual(rd["stages"]["previsoes"], ("warn", "Incompletas", "falta: demanda, clima"))
        self.assertEqual(S.readiness(self.doc, S.findings(self.doc), None)["stages"]["inicializacao"][1], "Incompleta")


# =========================================================================== contratos dos próximos pisos
class ContratosTest(_Base):
    def test_previsoes_estrategia_e_referencia_de_execucao(self):
        _, st = self.make()
        sc = service.create(st, name="Contratos")
        doc = copy.deepcopy(sc.document)
        self.assertEqual(doc["forecasts"], {})
        self.assertIsNone(doc["ems_strategy"])
        fi = contracts.ForecastInput(slot="demand", source_type="sintetico", provenance="sintetico", step_s=60)
        doc["forecasts"] = {"demand": fi.as_dict()}
        self.assertEqual(S.structural_errors(doc), [])
        bad = copy.deepcopy(doc)
        bad["forecasts"]["demand"]["provenance"] = "medido"           # sintético nunca é medido
        self.assertTrue(S.structural_errors(bad))
        bad = copy.deepcopy(doc)
        bad["forecasts"]["chuva"] = fi.as_dict()
        self.assertTrue(S.structural_errors(bad))
        bad = copy.deepcopy(sc.document)
        bad["ems_strategy"] = {"metodo": "GA"}                         # não implementado → recusado
        with self.assertRaises(S.ScenarioValidationError):
            service.save(st, bad, 1)
        ref = contracts.run_reference(st.get_scenario(sc.scenario_uid))
        self.assertEqual((ref.scenario_uid, ref.scenario_version, ref.config_revision, ref.microgrid_incarnation),
                         (sc.scenario_uid, 1, sc.base_revision, st.incarnation))


# =========================================================================== EMS V1.6 inalterado
class EMSInalteradoTest(_Base):
    def test_rodada_ems_identica_com_e_sem_cenarios(self):
        """Criar/editar cenários não altera a especificação transferida ao console V1.6 nem o despacho."""
        import orchestrator_runtime as RT

        uid, st = self.make()
        saved = st.load()
        plan0 = A.build_plan(saved.config, revision=saved.revision, fingerprint=saved.fingerprint)
        sc = service.create(st, name="Cenário qualquer")
        doc = _complete(copy.deepcopy(sc.document), soc=5.0)
        service.save(st, doc, 1)
        saved1 = st.load()
        plan1 = A.build_plan(saved1.config, revision=saved1.revision, fingerprint=saved1.fingerprint)
        self.assertEqual(plan1.spec, plan0.spec)
        self.assertEqual(plan1.spec_fingerprint, plan0.spec_fingerprint)
        carga = A.build_load(plan1.load_descriptor, st.get_blob)
        opt = RT.default_optimizer_config()
        with tempfile.TemporaryDirectory() as pkg, tempfile.TemporaryDirectory() as pkg2:
            p1, _ = RT.build_exchange_package(carga, plan1.spec, opt, destino=Path(pkg))
            r1, _ = RT.run_optimizer(p1, opt)
            p2, _ = RT.build_exchange_package(carga, RT.default_model_spec(), opt, destino=Path(pkg2))
            r2, _ = RT.run_optimizer(p2, opt)
        np.testing.assert_array_equal(r1["P_kW"], r2["P_kW"])
        self.assertEqual(r1["rel"]["custo_total_rs"], r2["rel"]["custo_total_rs"])


if __name__ == "__main__":
    unittest.main()
