"""Interface SEEDS2 (Piso 1) com AppTest: comissionamento, reabertura, Gestão e ponte com o console V1.6.

Cada teste usa um ``SEEDS2_DATA_DIR`` próprio. "Reiniciar a aplicação" = nova instância de ``AppTest``
(nova sessão) lendo o mesmo armazenamento; a verificação é feita também diretamente no SQLite.
"""
from __future__ import annotations

import copy
import os
import sqlite3
import tempfile
import unittest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

if AppTest is not None:
    from apptest_utils import APP_PATH, botao, continuar

from seeds2.microgrid import config as C
from seeds2.microgrid.store import MicrogridStore
from seeds2_fixtures import v16_equivalent_config


def _sel(app, label_start):
    return next(s for s in app.selectbox if s.label.startswith(label_start))


def _num(app, label_start):
    return next(n for n in app.number_input if n.label.startswith(label_start))


def _txt(app, label_start):
    return next(t for t in app.text_input if t.label.startswith(label_start))


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir

    def tearDown(self):
        self._tmp.cleanup()

    def open(self, view: str | None = None, timeout: float = 120) -> AppTest:
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=timeout)
        if view:
            app.session_state["seeds_route"] = {"view": view, "tab": None}
        app.run()
        _ok(self, app)
        return app

    def seed(self, cfg: dict | None = None) -> MicrogridStore:
        s = MicrogridStore(self.dir)
        s.save(cfg or v16_equivalent_config("Planta Piloto"), 0, origin="commissioning")
        return s


class ComissionamentoTest(_Base):
    def test_primeiro_acesso_abre_o_assistente(self):
        app = self.open()
        self.assertEqual(app.session_state["seeds_route"]["view"], "comissionamento")
        self.assertIn("Nome da instalação *", [t.label for t in app.text_input])
        self.assertIn("Salvar e continuar →", [b.label for b in app.button])
        self.assertIsNone(MicrogridStore(self.dir).load())               # nada é gravado sem ação do usuário
        # Gestão/Simulação não são acessíveis antes do comissionamento
        for view in ("gestao", "simulacao", "inicio"):
            a = self.open(view)
            self.assertEqual(a.session_state["seeds_route"]["view"], "comissionamento")

    def _identificacao(self, app, name="Laboratório de Microrredes"):
        _txt(app, "Nome da instalação").input(name)
        _sel(app, "Natureza da atividade").select("laboratorio")
        _sel(app, "Modo de operação previsto").select("isolada")
        botao(app, "Salvar e continuar →").click().run()
        _ok(self, app)

    def _add(self, app, kind_label: str, name: str, ref: str | None, nums: dict[str, float], **extra_sel):
        botao(app, "＋ Adicionar equipamento").click().run()
        _ok(self, app)
        tec = next(r for r in app.radio if r.label == "Tecnologia *")
        tec.set_value(kind_label).run()
        _txt(app, "Nome do equipamento").input(name)
        if ref:
            next(s for s in app.selectbox if "(referência)" in s.label).select(ref)
        for lab, v in extra_sel.items():
            _sel(app, lab).select(v)
        for lab, v in nums.items():
            _num(app, lab).set_value(v)
        app.run()
        botao(app, "Salvar equipamento").click().run()
        _ok(self, app)

    def test_comissionamento_completo_e_reabertura(self):
        app = self._identificacao_e_inventario()
        botao(app, "Continuar →").click().run()
        next(r for r in app.radio if r.label == "Tipo de barramento").set_value("CC")
        next(r for r in app.radio if r.label == "Conexão com a rede elétrica").set_value("isolada")
        botao(app, "Salvar configuração elétrica").click().run()
        _ok(self, app)
        botao(app, "Continuar →").click().run()
        next(r for r in app.radio if r.label == "Fonte da demanda").set_value("walkforward").run()
        _sel(app, "Cenário").select("Ideal")
        _sel(app, "Perfil").select("Normal")
        _sel(app, "Início").select(12)
        app.run()
        botao(app, "Salvar demanda").click().run()
        _ok(self, app)
        botao(app, "Continuar →").click().run()
        self.assertEqual(app.session_state["mg_cstep"], 5)
        botao(app, "Ativar microrrede e concluir comissionamento").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["view"], "inicio")

        # ---- "dia seguinte": nova sessão, mesmo armazenamento
        stored = MicrogridStore(self.dir).load()
        self.assertTrue(stored.config["commissioning"]["completed"])
        app2 = self.open()
        self.assertEqual(app2.session_state["seeds_route"]["view"], "inicio")
        self.assertNotIn("Nome da instalação *", [t.label for t in app2.text_input])   # não repete o assistente
        w = app2.session_state["mg_work"]
        self.assertEqual(w, stored.config)
        names = {e["name"]: e for e in w["equipment"]}
        self.assertEqual(set(names), {"Arranjo FV Norte", "Banco Li-ion", "PEMFC 1"})
        self.assertEqual(names["Arranjo FV Norte"]["params"],
                         {"reference": "CS7L-590MS", "n_series": 2, "n_parallel": 10, "soiling_pct": 1.5})
        self.assertEqual(names["Banco Li-ion"]["params"]["soc_min_pct"], 20.0)
        self.assertEqual(w["topology"]["bus_kind"], "CC")
        self.assertEqual(w["demand"]["walkforward"], {"scenario": "Ideal", "profile": "Normal", "start_hour": 12})
        with sqlite3.connect(os.path.join(self.dir, "seeds2.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM microgrid").fetchone()[0], 1)
            origins = {r[0] for r in con.execute("SELECT origin FROM revisions")}
        self.assertEqual(origins, {"commissioning"})

    def _identificacao_e_inventario(self):
        app = self.open()
        self._identificacao(app)
        self.assertEqual(app.session_state["mg_cstep"], 2)
        self._add(app, "pv", "Arranjo FV Norte", "CS7L-590MS",
                  {"Módulos em série": 2, "Strings em paralelo": 10, "Perdas por sujeira": 1.5})
        self._add(app, "battery", "Banco Li-ion", "tremblay:liion_3p3v_2p3ah",
                  {"Células em série": 200, "Ramos em paralelo": 132, "SOC inicial": 60.0, "SOC mínimo": 20.0,
                   "SOC máximo": 90.0, "Taxa máxima de descarga": 1.0, "Taxa máxima de carga": 0.5})
        self._add(app, "pemfc", "PEMFC 1", None, {"Sistemas/stacks instalados": 2})
        return app

    def test_comissionamento_retomado_apos_reinicio(self):
        app = self._identificacao_e_inventario()
        self.assertEqual(len(MicrogridStore(self.dir).load().config["equipment"]), 3)
        app2 = self.open()                                           # reinício no meio do comissionamento
        self.assertEqual(app2.session_state["seeds_route"]["view"], "comissionamento")
        self.assertEqual(app2.session_state["mg_cstep"], 2)
        self.assertEqual(len(app2.session_state["mg_work"]["equipment"]), 3)
        botao(app2, "← Voltar").click().run()                        # voltar não perde dados
        _ok(self, app2)
        self.assertEqual(_txt(app2, "Nome da instalação").value, "Laboratório de Microrredes")
        self.assertEqual(len(MicrogridStore(self.dir).load().config["equipment"]), 3)

    def test_equipamento_pode_ser_registrado_sem_parametros_tecnicos(self):
        app = self.open()
        self._identificacao(app)
        botao(app, "＋ Adicionar equipamento").click().run()
        next(r for r in app.radio if r.label == "Tecnologia *").set_value("wind").run()
        _txt(app, "Nome do equipamento").input("Aerogerador futuro")
        app.run()
        self.assertTrue(any("não tecnicamente configurado" in i.value for i in app.info))
        botao(app, "Salvar equipamento").click().run()
        _ok(self, app)
        eq = MicrogridStore(self.dir).load().config["equipment"][0]
        self.assertEqual(eq["params"], {"reference": None, "count": None, "apply_grid_loss": False})


class GestaoTest(_Base):
    def test_editar_parametro_gera_revisao_sem_nova_microrrede(self):
        s = self.seed()
        uid = s.load().config["installation"]["uid"]
        app = self.open("gestao")
        bat = next(e for e in app.session_state["mg_work"]["equipment"] if e["kind"] == "battery")
        app.session_state["mg_dialog"] = {"type": "equipment", "id": bat["id"], "autosave": False, "token": 99}
        app.run()
        _ok(self, app)
        _num(app, "SOC mínimo").set_value(25.0)
        app.run()
        botao(app, "Aplicar").click().run()
        _ok(self, app)
        self.assertEqual(MicrogridStore(self.dir).load().revision, 1)          # ainda pendente
        self.assertTrue(any(c.key == "mg_pending" for c in app.get("flex_container")) or
                        "Salvar alterações" in [b.label for b in app.button])
        botao(app, "Salvar alterações").click().run()
        _ok(self, app)
        st2 = MicrogridStore(self.dir).load()
        self.assertEqual(st2.revision, 2)
        self.assertEqual(st2.config["installation"]["uid"], uid)
        self.assertEqual(next(e for e in st2.config["equipment"] if e["id"] == bat["id"])["params"]["soc_min_pct"], 25.0)
        with sqlite3.connect(os.path.join(self.dir, "seeds2.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM microgrid").fetchone()[0], 1)

    def test_descartar_edicao_pendente(self):
        self.seed()
        app = self.open("gestao")
        eq = copy.deepcopy(app.session_state["mg_work"]["equipment"][0])
        app.session_state["mg_dialog"] = {"type": "equipment", "id": eq["id"], "autosave": False, "token": 7}
        app.run()
        _txt(app, "Nome do equipamento").input("Nome provisório")
        app.run()
        botao(app, "Aplicar").click().run()
        self.assertEqual(app.session_state["mg_work"]["equipment"][0]["name"], "Nome provisório")   # pendente
        botao(app, "Descartar").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["mg_work"]["equipment"][0]["name"], eq["name"])
        self.assertEqual(MicrogridStore(self.dir).load().revision, 1)

    def test_incorporar_e_retirar_equipamento(self):
        self.seed()
        app = self.open("gestao")
        botao(app, "＋ Adicionar equipamento").click().run()
        next(r for r in app.radio if r.label == "Tecnologia *").set_value("thermal").run()
        _txt(app, "Nome do equipamento").input("Gerador diesel reserva")
        _sel(app, "Dinâmica operacional").select("local_generator")
        for lab, v in (("Potência máxima", 80.0), ("Potência mínima técnica", 20.0), ("CVU", 1100.0), ("Custo de partida", 50.0)):
            _num(app, lab).set_value(v)
        app.run()
        botao(app, "Aplicar").click().run()
        botao(app, "Salvar alterações").click().run()
        _ok(self, app)
        cfg = MicrogridStore(self.dir).load().config
        th = next(e for e in cfg["equipment"] if e["kind"] == "thermal")
        self.assertIsNone(th["params"]["ramp_kW_min"])              # opcional não declarado continua vazio
        # retirar
        app = self.open("gestao")
        app.session_state["mg_dialog"] = {"type": "equipment", "id": th["id"], "autosave": False, "token": 3}
        app.run()
        _txt(app, "Motivo da retirada").input("devolvido ao fornecedor")
        next(c for c in app.checkbox if c.label.startswith("Confirmo a retirada")).check().run()
        botao(app, "Retirar equipamento").click().run()
        botao(app, "Salvar alterações").click().run()
        _ok(self, app)
        cfg = MicrogridStore(self.dir).load().config
        self.assertNotIn(th["id"], [e["id"] for e in cfg["equipment"]])
        self.assertEqual(cfg["retired"][-1]["id"], th["id"])
        self.assertEqual(cfg["retired"][-1]["retired_reason"], "devolvido ao fornecedor")

    def test_validacao_impede_aplicar_dados_fisicamente_invalidos(self):
        self.seed()
        app = self.open("gestao")
        bat = next(e for e in app.session_state["mg_work"]["equipment"] if e["kind"] == "battery")
        app.session_state["mg_dialog"] = {"type": "equipment", "id": bat["id"], "autosave": False, "token": 5}
        app.run()
        _num(app, "SOC mínimo").set_value(95.0)
        app.run()
        self.assertTrue(any("SOC mínimo deve ser menor" in e.value for e in app.error))
        self.assertTrue(botao(app, "Aplicar").disabled)

    def test_conflito_entre_sessoes_nao_sobrescreve(self):
        s = self.seed()
        app = self.open("gestao")
        eq = app.session_state["mg_work"]["equipment"][0]
        app.session_state["mg_dialog"] = {"type": "equipment", "id": eq["id"], "autosave": False, "token": 11}
        app.run()
        _txt(app, "TAG").input("SESSAO-A")
        app.run()
        botao(app, "Aplicar").click().run()
        other = copy.deepcopy(s.load().config)                         # outra sessão salva antes
        other["installation"]["description"] = "alterado pela sessão B"
        s.save(other, 1)
        botao(app, "Salvar alterações").click().run()
        _ok(self, app)
        self.assertIn("mg_conflict", app.session_state)
        final = MicrogridStore(self.dir).load()
        self.assertEqual(final.revision, 2)
        self.assertEqual(final.config["installation"]["description"], "alterado pela sessão B")

    def test_historico_e_backup_disponiveis(self):
        self.seed()
        app = self.open()
        app.session_state["seeds_route"] = {"view": "gestao", "tab": "historico"}
        app.run()
        _ok(self, app)
        botao(app, "Preparar backup da revisão salva").click().run()
        _ok(self, app)
        name, data = app.session_state["mg_bk"]
        self.assertTrue(name.endswith(".seeds2backup.zip"))
        self.assertTrue(MicrogridStore(self.dir).inspect_backup(data).ok)


class SimulacaoTest(_Base):
    def test_configuracao_persistida_e_transferida_e_rodada_registrada(self):
        from orchestrator_runtime import default_model_spec

        s = self.seed()
        saved = s.load()
        app = self.open("simulacao", timeout=240)
        spec = app.session_state["orq_model_spec"]
        ref = default_model_spec()
        for k in ("solar", "fc", "battery"):
            self.assertEqual(spec[k], ref[k])
        self.assertEqual(app.session_state["orq_spec_origin"]["config_fingerprint"], saved.fingerprint)
        self.assertTrue(app.session_state["orq_run_gate"]["ok"])
        botao(app, "◎  Otimizador").click().run()
        botao(app, "▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO").click().run()
        _ok(self, app)
        item = app.session_state["orq_result_item"]
        self.assertEqual(item["origem"]["origin"], "microrrede")
        self.assertEqual(item["origem"]["config_revision"], 1)
        runs = MicrogridStore(self.dir).runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual((runs[0]["config_revision"], runs[0]["config_fingerprint"]), (1, saved.fingerprint))
        self.assertAlmostEqual(runs[0]["summary"]["custo_total_rs"], item["resultado"]["rel"]["custo_total_rs"])

        # ---- a configuração muda: o resultado anterior é identificado como obsoleto
        cfg = copy.deepcopy(saved.config)
        cfg["equipment"][0]["params"]["n_parallel"] = 6
        s.save(cfg, 1)
        app2 = continuar(app, timeout=240)
        _ok(self, app2)
        self.assertEqual(app2.session_state["seeds_route"]["view"], "resultados")
        self.assertTrue(any("Resultado de configuração anterior" in h.proto.body for h in app2.get("html")),
                        "banner de resultado obsoleto ausente")
        self.assertEqual(app2.session_state["orq_spec_origin"]["config_revision"], 2)
        self.assertEqual(app2.session_state["orq_model_spec"]["solar"]["n_parallel"], 11)

    def test_exclusoes_exigem_confirmacao_e_ficam_registradas(self):
        cfg = v16_equivalent_config("Planta com exclusões")
        C.add_equipment(cfg, C.new_equipment("thermal", "UTE grande porte", params={
            "dynamic": "thermal_plant", "pmax_kW": 500.0, "pmin_kW": 100.0, "cvu_rs_MWh": 420.0, "startup_cost_rs": 0.0}))
        self.seed(cfg)
        app = self.open("simulacao", timeout=240)
        self.assertFalse(app.session_state["orq_run_gate"]["ok"])
        botao(app, "◎  Otimizador").click().run()
        self.assertTrue(botao(app, "▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO").disabled)
        app = continuar(app, timeout=240)
        ack = next(c for c in app.checkbox if c.label.startswith("Confirmo executar esta rodada SEM"))
        ack.check().run()
        app = continuar(app, timeout=240)
        self.assertTrue(app.session_state["orq_run_gate"]["ok"])
        botao(app, "▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO").click().run()
        _ok(self, app)
        excl = MicrogridStore(self.dir).runs()[0]["excluded"]
        self.assertEqual([e["name"] for e in excl], ["UTE grande porte"])

    def test_alteracao_manual_no_console_desvincula_da_microrrede(self):
        self.seed()
        app = self.open("simulacao", timeout=240)
        app.session_state["orq_model_spec"]["fc"]["N_fc"] = 2           # como se editado na página Modelos V1.6
        app.run()
        _ok(self, app)
        self.assertEqual(app.session_state["orq_spec_origin"]["origin"], "manual")

    def test_bloqueio_sem_demanda(self):
        cfg = v16_equivalent_config()
        cfg["demand"]["source"] = "nao_definida"
        cfg["demand"]["provenance"] = "nao_declarado"
        self.seed(cfg)
        app = self.open("simulacao", timeout=240)
        self.assertFalse(app.session_state["orq_run_gate"]["ok"])
        self.assertIn("Demanda", app.session_state["orq_run_gate"]["message"])


class InicioTest(_Base):
    def test_inicio_mostra_identidade_e_bancadas_acessiveis(self):
        self.seed()
        app = self.open()
        self.assertEqual(app.session_state["seeds_route"]["view"], "inicio")
        self.assertTrue(any("Planta Piloto" in h.proto.body for h in app.get("html")))
        botao(app, "ABRIR EÓLICA").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["energy_source"], "wind")


if __name__ == "__main__":
    unittest.main()
