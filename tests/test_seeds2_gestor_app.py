"""Gestor de microrredes na interface (AppTest): página inicial, criação, troca na mesma sessão e entre sessões,
isolamento do estado da sessão (inclusive console V1.6), exclusão por outra sessão, exportação/relatório sem
abrir a microrrede, exclusão definitiva protegida e rodada EMS real numa microrrede selecionada.

O AppTest não executa o JavaScript dos componentes: o botão "TROCAR MICRORREDE" da barra superior é simulado
pelo mesmo sinal que o componente produz (``seeds_switch_requested``); o clique real é verificado no E2E.
"""
from __future__ import annotations

import io
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

if AppTest is not None:
    from apptest_utils import APP_PATH, botao

from seeds2.microgrid import config as C
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2_fixtures import v16_equivalent_config

NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


def _html(app) -> str:
    return "\n".join(h.proto.body for h in app.get("html"))


def _key(app, key):
    return next(b for b in app.button if b.key == key)


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        self._env = mock.patch.dict(os.environ, NO_ADMIN)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def reg(self) -> MicrogridRegistry:
        return MicrogridRegistry(self.dir)

    def make(self, name: str, *, commissioned: bool = True) -> str:
        cfg = v16_equivalent_config(name)
        if not commissioned:
            cfg["commissioning"].update(completed=False, step=3, completed_at=None)
        self.reg().create(cfg)
        return cfg["installation"]["uid"]

    def session(self, uid: str | None = None, view: str | None = None, timeout: float = 120, state: dict | None = None) -> AppTest:
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=timeout)
        if uid:
            app.session_state["mg_active_uid"] = uid
        if view:
            app.session_state["seeds_route"] = {"view": view, "tab": None}
        for k, v in (state or {}).items():
            app.session_state[k] = v
        app.run()
        _ok(self, app)
        return app

    def switch(self, app: AppTest) -> AppTest:
        """TROCAR MICRORREDE (mesmo sinal do componente da barra superior)."""
        app.session_state["seeds_switch_requested"] = True
        app.run()
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["view"], "gestor")
        self.assertNotIn("mg_active_uid", app.session_state)
        return app

    def identificar(self, app: AppTest, name: str) -> None:
        next(t for t in app.text_input if t.label.startswith("Nome da instalação")).input(name)
        next(s for s in app.selectbox if s.label.startswith("Natureza")).select("laboratorio")
        next(s for s in app.selectbox if s.label.startswith("Modo de operação")).select("isolada")
        app.run()
        botao(app, "Salvar e continuar →").click().run()
        _ok(self, app)


class GestorPaginaTest(_Base):
    def test_inicio_sem_microrredes(self):                               # requisito 1
        app = self.session()
        self.assertEqual(app.session_state["seeds_route"]["view"], "gestor")
        body = _html(app)
        self.assertIn("GESTOR DE MICRORREDES", body)
        self.assertIn("Selecione, registre e gerencie suas instalações energéticas.", body)
        self.assertIn("Nenhuma microrrede registrada", body)
        # Piso 2D-A: ARQUIVO CIENTÍFICO acessível sem microrrede (importar/consultar estudos numa instalação vazia)
        self.assertEqual([b.label for b in app.button if not b.key.startswith("home_bench_")],
                         ["＋ NOVA MICRORREDE", "IMPORTAR MICRORREDE (ZIP)", "ARQUIVO CIENTÍFICO"])
        # UI-FINISH-01: as bancadas (bloco do celular; no desktop estão na barra lateral) — as MESMAS do Centro de Operação
        self.assertEqual([b.label for b in app.button if b.key.startswith("home_bench_")],
                         ["ABRIR SOLAR", "ABRIR EÓLICA", "ABRIR BATERIA", "ABRIR H₂ / PEMFC", "ABRIR TÉRMICA"])
        self.assertEqual(self.reg().entries(), [])

    def test_criar_varias_pelo_gestor_e_retomar_comissionamento(self):  # requisitos 2, 3, 11
        app = self.session()
        botao(app, "＋ NOVA MICRORREDE").click().run()
        self.identificar(app, "Microrrede A")
        uid_a = app.session_state["mg_active_uid"]
        self.assertEqual((app.session_state["seeds_route"]["view"], app.session_state["mg_cstep"]), ("comissionamento", 2))
        self.switch(app)
        botao(app, "＋ NOVA MICRORREDE").click().run()
        _ok(self, app)
        self.assertNotEqual(app.session_state["mg_work"]["installation"]["uid"], uid_a)   # rascunho novo, limpo
        self.assertEqual(next(t for t in app.text_input if t.label.startswith("Nome da instalação")).value, "")
        self.identificar(app, "Microrrede B")
        uid_b = app.session_state["mg_active_uid"]
        self.switch(app)
        self.assertEqual({e.uid for e in self.reg().entries()}, {uid_a, uid_b})
        body = _html(app)
        self.assertIn("Microrrede A", body)
        self.assertIn("Microrrede B", body)
        self.assertIn("Em configuração", body)
        # retomar A exatamente onde estava (etapa 02), em nova sessão
        app2 = self.session()
        _key(app2, f"g_open_{uid_a}").click().run()
        _ok(self, app2)
        self.assertEqual((app2.session_state["seeds_route"]["view"], app2.session_state["mg_cstep"]), ("comissionamento", 2))
        self.assertEqual(app2.session_state["mg_work"]["installation"]["name"], "Microrrede A")

    def test_abandonar_nova_microrrede_antes_da_etapa01_nao_cria_registro(self):
        app = self.session()
        botao(app, "＋ NOVA MICRORREDE").click().run()
        self.switch(app)
        self.assertEqual(self.reg().entries(), [])

    def test_ativa_abre_no_painel_habitual(self):
        uid = self.make("Ativa")
        app = self.session()
        _key(app, f"g_open_{uid}").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["view"], "operacao")    # Piso 2A: Centro de Operação
        self.assertIn("Ativa", _html(app))

    def test_recarga_com_parametro_mg_reabre_a_mesma_microrrede(self):
        uid = self.make("Recarga")
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=120)
        app.query_params["mg"] = uid
        app.query_params["view"] = "gestao"
        app.run()
        _ok(self, app)
        self.assertEqual((app.session_state["mg_active_uid"], app.session_state["seeds_route"]["view"]), (uid, "gestao"))
        bad = AppTest.from_file(str(APP_PATH), default_timeout=120)
        bad.query_params["mg"] = "../../etc"
        bad.run()
        _ok(self, bad)
        self.assertEqual(bad.session_state["seeds_route"]["view"], "gestor")


class IsolamentoSessaoTest(_Base):
    def test_troca_na_mesma_sessao_nao_contamina_estado(self):          # requisito 8
        a, b = self.make("Microrrede A"), self.make("Microrrede B")
        app = self.session(a, "simulacao", timeout=240)
        self.assertEqual(app.session_state["orq_mg_applied"]["microgrid_uid"], a)
        self.assertEqual(app.session_state["orq_spec_origin"]["microgrid_uid"], a)
        # estados próprios de A que não podem reaparecer em B
        app.session_state["mg_ack_fp"] = "x" * 64
        app.session_state["mg_dialog"] = {"type": "equipment", "id": None, "step": "pick", "token": 1}
        app.session_state["orq_result_item"] = {"id": 1, "resultado": {}, "origem": {"origin": "microrrede", "microgrid_uid": a}}
        app.session_state["orq_manual"] = True
        app.session_state["orchestrator_page"] = "Modelos"
        self.switch(app)
        for k in ("mg_ack_fp", "mg_dialog", "orq_result_item", "orq_manual", "orq_mg_applied", "orq_model_spec",
                  "orq_load", "mg_plan", "mg_work", "orchestrator_page", "orq_history"):
            self.assertNotIn(k, app.session_state, k)
        self.assertIsNone(app.session_state["mg_saved"])                  # Gestor: nenhuma configuração carregada
        _key(app, f"g_open_{b}").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["mg_active_uid"], b)
        self.assertEqual(app.session_state["mg_work"]["installation"]["uid"], b)
        app.session_state["seeds_route"] = {"view": "simulacao", "tab": None}
        app.run()
        _ok(self, app)
        self.assertEqual(app.session_state["orq_mg_applied"]["microgrid_uid"], b)
        self.assertEqual(app.session_state["orq_spec_origin"]["microgrid_uid"], b)
        self.assertIsNone(app.session_state["orq_result_item"])
        self.assertNotIn("mg_ack_fp", app.session_state)

    def test_sessoes_diferentes_com_microrredes_diferentes(self):        # requisito 9
        a, b = self.make("Microrrede A"), self.make("Microrrede B")
        s1 = self.session(a, "gestao")
        s2 = self.session(b, "gestao")
        s1.session_state["mg_work"]["installation"]["description"] = "edição pendente em A"
        s1.run()
        s2.run()
        _ok(self, s1)
        _ok(self, s2)
        self.assertEqual(s1.session_state["mg_work"]["installation"]["uid"], a)
        self.assertEqual(s2.session_state["mg_work"]["installation"]["uid"], b)
        self.assertNotEqual(s2.session_state["mg_work"]["installation"]["description"], "edição pendente em A")
        self.assertEqual(self.reg().open(a).load().revision, 1)          # pendência não gravada em lugar nenhum
        self.assertEqual(self.reg().open(b).load().revision, 1)

    def test_microrrede_excluida_por_outra_sessao_volta_ao_gestor(self):  # requisito 18
        a, b = self.make("A"), self.make("B")
        app = self.session(a, "gestao")
        self.reg().delete(a)                                              # outra sessão/processo excluiu
        app.run()
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["view"], "gestor")
        self.assertNotIn("mg_active_uid", app.session_state)
        self.assertTrue(any("excluída" in w.value for w in app.warning))
        self.assertFalse(self.reg().dir_for(a).exists())                  # nada recriado
        self.assertEqual([e.uid for e in self.reg().entries()], [b])

    def test_sessao_antiga_nao_escreve_na_microrrede_reimportada_com_o_mesmo_uid(self):   # H-01
        a = self.make("Original")
        reg = self.reg()
        z = reg.open(a).export_backup()
        app = self.session(a, "gestao")
        self.assertEqual(app.session_state["mg_active_inc"], reg.get(a).incarnation)
        app.session_state["mg_work"]["installation"]["description"] = "edição pendente da sessão antiga"
        app.run()
        _ok(self, app)
        reg.delete(a)                                                     # outra sessão exclui...
        reg.import_new(z)                                                 # ...e reimporta o MESMO uid
        app.run()
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["view"], "gestor")
        self.assertNotIn("mg_active_uid", app.session_state)
        self.assertTrue(any("excluída" in w.value for w in app.warning))
        fresh = self.reg().open(a).load()
        self.assertEqual(fresh.revision, 1)
        self.assertNotEqual(fresh.config["installation"]["description"], "edição pendente da sessão antiga")


class ExportacaoExclusaoTest(_Base):
    def test_zip_e_pdf_pelo_gestor_sem_abrir_a_microrrede(self):         # requisitos 12–13
        from pypdf import PdfReader

        from seeds2.microgrid.store import inspect_backup_data

        a = self.make("Ativa A")
        b = self.make("Em configuração B", commissioned=False)
        app = self.session()
        _key(app, f"g_zip_{a}").click().run()
        _ok(self, app)
        fp, name, data = app.session_state["gestor_zip"][a]
        self.assertTrue(name.endswith(".seeds2backup.zip") and a[:8] in name)
        rep = inspect_backup_data(data)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(rep.config["installation"]["uid"], a)
        self.assertIn("⬇ Baixar ZIP", [d.proto.label for d in app.get("download_button")])
        _key(app, f"g_pdf_{b}").click().run()
        _ok(self, app)
        fp_b, name_b, pdf = app.session_state["gestor_pdf"][b]
        self.assertTrue(name_b.endswith(".pdf") and b[:8] in name_b)
        text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("PRELIMINAR", text)
        self.assertIn("Em configuração B", text)
        self.assertIn("⬇ Baixar relatório PDF", [d.proto.label for d in app.get("download_button")])
        self.assertNotIn("mg_active_uid", app.session_state)             # nenhuma microrrede foi aberta
        self.assertEqual(app.session_state["seeds_route"]["view"], "gestor")

    def _abrir_exclusao(self, uid: str) -> AppTest:
        app = self.session()
        _key(app, f"g_del_{uid}").click().run()
        _ok(self, app)
        return app

    def test_exclusao_desativada_por_padrao(self):
        a = self.make("A")
        app = self._abrir_exclusao(a)
        self.assertTrue(any("desativada" in w.value for w in app.warning))
        self.assertNotIn("EXCLUIR DEFINITIVAMENTE", [x.label for x in app.button])
        self.assertTrue(self.reg().exists(a))

    def test_exclusao_exige_nome_exato_e_nao_afeta_outra(self):          # requisitos 16–17
        a, b = self.make("Microrrede de testes"), self.make("Microrrede de produção")
        snap = sqlite3.connect(self.reg().open(b).path).execute("SELECT document, revision FROM microgrid").fetchall()
        with mock.patch.dict(os.environ, {"SEEDS2_DEV_MODE": "1"}):
            app = self._abrir_exclusao(a)
            body = _html(app)
            self.assertIn("Microrrede de testes", body)
            self.assertIn(a, body)
            self.assertIn("Preparar ZIP antes de excluir", [x.label for x in app.button])
            name = next(t for t in app.text_input if t.label.startswith("Digite o nome exato"))
            name.input("Microrrede de produção").run()
            self.assertTrue(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)
            name = next(t for t in app.text_input if t.label.startswith("Digite o nome exato"))
            name.input("Microrrede de testes").run()
            self.assertFalse(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)
            botao(app, "EXCLUIR DEFINITIVAMENTE").click().run()
            _ok(self, app)
        self.assertFalse(self.reg().exists(a))
        self.assertFalse(self.reg().dir_for(a).exists())
        self.assertEqual(sqlite3.connect(self.reg().open(b).path).execute("SELECT document, revision FROM microgrid").fetchall(), snap)
        self.assertTrue(any("excluída definitivamente" in s.value for s in app.success))

    def test_dialogo_de_exclusao_vinculado_a_incarnacao(self):                # H-02 na interface
        a = self.make("Vinculada")
        reg = self.reg()
        z = reg.open(a).export_backup()
        with mock.patch.dict(os.environ, {"SEEDS2_DEV_MODE": "1"}):
            app = self._abrir_exclusao(a)                                 # diálogo aberto com a incarnação atual
            reg.delete(a)                                                 # outra sessão exclui...
            reg.import_new(z)                                             # ...e reimporta o MESMO uid
            new_inc = self.reg().get(a).incarnation
            app.run()
            _ok(self, app)
            self.assertTrue(any("substituída" in w.value for w in app.warning))
            self.assertNotIn("EXCLUIR DEFINITIVAMENTE", [x.label for x in app.button])
        e = self.reg().get(a)
        self.assertEqual(e.incarnation, new_inc)                          # a nova microrrede segue intacta
        self.assertEqual(self.reg().open(a).load().revision, 1)

    def test_exclusao_protegida_por_credencial(self):
        a = self.make("Protegida")
        with mock.patch.dict(os.environ, {"SEEDS2_ADMIN_PASSWORD": "segredo-adm"}):
            app = self._abrir_exclusao(a)
            next(t for t in app.text_input if t.label.startswith("Digite o nome exato")).input("Protegida").run()
            cred = next(t for t in app.text_input if t.label == "Credencial administrativa")
            self.assertEqual(cred.proto.type, cred.proto.PASSWORD)
            cred.input("errada").run()
            botao(app, "EXCLUIR DEFINITIVAMENTE").click().run()
            _ok(self, app)
            self.assertTrue(any("Credencial administrativa inválida" in e.value for e in app.error))
            self.assertTrue(self.reg().exists(a))
            next(t for t in app.text_input if t.label == "Credencial administrativa").input("segredo-adm").run()
            botao(app, "EXCLUIR DEFINITIVAMENTE").click().run()
            _ok(self, app)
            self.assertNotIn("segredo-adm", _html(app))
        self.assertFalse(self.reg().exists(a))


class SimulacaoPorMicrorredeTest(_Base):
    def test_rodada_ems_real_e_resultados_nao_vazam_entre_microrredes(self):   # requisitos 7, 10, 18, 24
        a = self.make("Gêmea A")
        b, _ = self.reg().import_copy(self.reg().open(a).export_backup())   # mesma especificação científica
        app = self.session(a, "simulacao", timeout=300)
        fp_a = app.session_state["orq_mg_applied"]["spec_fingerprint"]
        botao(app, "◎  Otimizador").click().run()
        botao(app, "▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO").click().run()
        _ok(self, app)
        item = app.session_state["orq_result_item"]
        self.assertEqual(item["origem"]["microgrid_uid"], a)
        runs_a = self.reg().open(a).runs()
        self.assertEqual(len(runs_a), 1)
        self.assertEqual(runs_a[0]["summary"]["microgrid_uid"], a)
        self.assertEqual(self.reg().open(b).runs(), [])
        self.switch(app)
        _key(app, f"g_open_{b}").click().run()
        app.session_state["seeds_route"] = {"view": "resultados", "tab": None}
        app.run()
        _ok(self, app)
        self.assertEqual(app.session_state["orq_mg_applied"]["spec_fingerprint"], fp_a)   # mesma especificação...
        self.assertIsNone(app.session_state["orq_result_item"])                         # ...sem resultado herdado
        self.assertNotIn("Rodadas registradas desta microrrede", _html(app))
        # defesa adicional: mesmo que um resultado de A chegasse à sessão de B, nunca seria apresentado como válido
        app.session_state["orq_result_item"] = item
        app.run()
        _ok(self, app)
        self.assertIn("Resultado de OUTRA microrrede", _html(app))
        # voltar a A: rodada persistida exibida (resumo gravado, sem inventar séries)
        self.switch(app)
        _key(app, f"g_open_{a}").click().run()
        app.session_state["seeds_route"] = {"view": "resultados", "tab": None}
        app.run()
        _ok(self, app)
        self.assertIn("Rodadas registradas desta microrrede", _html(app))


if __name__ == "__main__":
    unittest.main()
