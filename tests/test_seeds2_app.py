"""Interface SEEDS2 (Piso 1 refinado) com AppTest: comissionamento, reabertura, catálogo de tecnologias,
editores, confirmação de pendências, Gestão e ponte com o console V1.6.

Cada teste usa um ``SEEDS2_DATA_DIR`` próprio (catálogo + um banco por microrrede). "Reiniciar a aplicação" =
nova instância de ``AppTest`` (nova sessão, que começa no Gestor de microrredes) lendo o mesmo armazenamento;
a verificação é feita também diretamente no SQLite da microrrede.
O AppTest não executa o JavaScript dos componentes: a escolha no catálogo visual é simulada pelo estado do
diálogo (o clique real no cartão é verificado no E2E em navegador).
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
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.microgrid.store import MicrogridStore
from seeds2_fixtures import battery_params, module_array, pv_plant, v16_equivalent_config


def _sel(app, label_start):
    return next(s for s in app.selectbox if s.label.startswith(label_start))


def _num(app, label_start):
    return next(n for n in app.number_input if n.label.startswith(label_start))


def _txt(app, label_start):
    return next(t for t in app.text_input if t.label.startswith(label_start))


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


def _errors(app) -> str:
    return " | ".join(e.value.replace("\\", "") for e in app.error)


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir

    def tearDown(self):
        self._tmp.cleanup()

    _DEFAULT = object()

    def open(self, view: str | None = None, timeout: float = 120, tab: str | None = None, uid=_DEFAULT) -> AppTest:
        """Nova sessão. Com uma microrrede semeada (``seed``), ela é aberta na sessão (equivale a "ABRIR
        MICRORREDE" no Gestor); ``uid=None`` abre o Gestor."""
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=timeout)
        uid = getattr(self, "uid", None) if uid is self._DEFAULT else uid
        if uid:
            app.session_state["mg_active_uid"] = uid
        if view:
            app.session_state["seeds_route"] = {"view": view, "tab": tab}
        app.run()
        _ok(self, app)
        return app

    def novo(self, timeout: float = 120) -> AppTest:
        """Gestor → "＋ NOVA MICRORREDE" (clique real) → comissionamento."""
        app = self.open(uid=None, timeout=timeout)
        self.assertEqual(app.session_state["seeds_route"]["view"], "gestor")
        botao(app, "＋ NOVA MICRORREDE").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["view"], "comissionamento")
        return app

    def abrir_pelo_gestor(self, uid: str, timeout: float = 120) -> AppTest:
        """Nova sessão no Gestor → "ABRIR MICRORREDE" (clique real) na tarjeta da microrrede ``uid``."""
        app = self.open(uid=None, timeout=timeout)
        next(b for b in app.button if b.key == f"g_open_{uid}").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["mg_active_uid"], uid)
        return app

    def reg(self) -> MicrogridRegistry:
        return MicrogridRegistry(self.dir)

    def store(self, uid: str | None = None) -> MicrogridStore:
        r = self.reg()
        if uid is None:
            entries = r.entries()
            self.assertEqual(len(entries), 1, entries)
            uid = entries[0].uid
        return r.open(uid)

    def saved(self):
        """Configuração salva da ÚNICA microrrede do catálogo deste teste (None se o catálogo está vazio)."""
        return self.store().load() if self.reg().entries() else None

    def seed(self, cfg: dict | None = None) -> MicrogridStore:
        cfg = cfg or v16_equivalent_config("Planta Piloto")
        self.reg().create(cfg, origin="commissioning")
        self.uid = cfg["installation"]["uid"]
        return self.store(self.uid)

    # ---- diálogo de equipamento
    def pick(self, app, kind: str):
        """Escolha de tecnologia no catálogo (equivale ao clique no cartão do componente)."""
        dlg = dict(app.session_state["mg_dialog"])
        self.assertEqual(dlg["step"], "pick")
        draft = C.new_equipment(kind, "")
        if kind == "pv":
            draft["arrays"] = [C.new_array("Arranjo 01")]
        dlg.update(step="edit", draft=draft, kind=kind)
        app.session_state["mg_dialog"] = dlg
        app.run()
        _ok(self, app)

    def edit(self, app, eq_id: str, autosave: bool = False):
        eq = copy.deepcopy(C.find_equipment(app.session_state["mg_work"], eq_id))
        app.session_state["mg_dialog"] = {"type": "equipment", "id": eq_id, "step": "edit", "autosave": autosave,
                                          "token": 90 + len(eq_id), "draft": eq}
        app.run()
        _ok(self, app)


class ComissionamentoTest(_Base):
    def test_primeiro_acesso_abre_o_gestor_e_nova_microrrede_o_assistente(self):
        app = self.open()
        self.assertEqual(app.session_state["seeds_route"]["view"], "gestor")
        self.assertNotIn("Nome da instalação *", [t.label for t in app.text_input])
        self.assertIsNone(self.saved())
        for view in ("gestao", "simulacao", "inicio", "comissionamento"):
            self.assertEqual(self.open(view).session_state["seeds_route"]["view"], "gestor")
        app = self.novo()
        self.assertIn("Nome da instalação *", [t.label for t in app.text_input])
        self.assertIn("Salvar e continuar →", [b.label for b in app.button])
        self.assertEqual(self.reg().entries(), [])                     # nada é criado antes da etapa 01

    def test_etapa01_campos_obrigatorios(self):                           # aceitação 1
        app = self.novo()
        botao(app, "Salvar e continuar →").click().run()
        msgs = _errors(app)
        for esperado in ("nome da instalação", "natureza da atividade", "modo de operação"):
            self.assertIn(esperado, msgs)
        self.assertIsNone(self.saved())                # nada salvo
        _txt(app, "Nome da instalação").input("Usina-escola")
        app.run()
        botao(app, "Salvar e continuar →").click().run()
        self.assertIn("natureza da atividade", _errors(app))
        self.assertIsNone(self.saved())
        _sel(app, "Natureza da atividade").select("laboratorio")
        _sel(app, "Modo de operação previsto").select("conectada")
        _txt(app, "País").input("Brasil")
        _txt(app, "Cidade / localidade").input("Foz do Iguaçu")
        _num(app, "Latitude").set_value(-25.44)
        _num(app, "Longitude").set_value(-54.58)
        _txt(app, "Fuso horário").input("America/Sao_Paulo")
        app.run()
        botao(app, "Salvar e continuar →").click().run()
        _ok(self, app)
        inst = self.saved().config["installation"]
        self.assertEqual((inst["name"], inst["nature"], inst["operation_mode"]), ("Usina-escola", "laboratorio", "conectada"))
        loc = inst["location"]
        self.assertEqual((loc["country"], loc["city"], loc["latitude"], loc["longitude"], loc["timezone"], loc["source"]),
                         ("Brasil", "Foz do Iguaçu", -25.44, -54.58, "America/Sao_Paulo", "manual"))
        self.assertEqual(loc["region"], "")                                # não inventado a partir das coordenadas

    def test_localizacao_rejeita_dados_invalidos(self):
        app = self.novo()
        _txt(app, "Nome da instalação").input("X")
        _sel(app, "Natureza da atividade").select("outra")
        _sel(app, "Modo de operação previsto").select("isolada")
        _num(app, "Latitude").set_value(10.0)                              # sem longitude
        _txt(app, "Fuso horário").input("Marte/Olympus")
        app.run()
        botao(app, "Salvar e continuar →").click().run()
        msgs = _errors(app)
        self.assertIn("latitude e longitude juntas", msgs)
        self.assertIn("Fuso horário IANA desconhecido", msgs)
        self.assertIsNone(self.saved())

    def _identificacao(self, app, name="Laboratório de Microrredes"):
        _txt(app, "Nome da instalação").input(name)
        _sel(app, "Natureza da atividade").select("laboratorio")
        _sel(app, "Modo de operação previsto").select("isolada")
        app.run()
        botao(app, "Salvar e continuar →").click().run()
        _ok(self, app)

    def _salvar(self, app, *, pending: bool = False):
        botao(app, "Salvar equipamento").click().run()
        _ok(self, app)
        if pending:
            self.assertEqual(app.session_state["mg_dialog"]["step"], "confirm")
            botao(app, "Salvar como pendente").click().run()
            _ok(self, app)

    def _inventario(self, app):
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "pv")
        _txt(app, "Nome do equipamento").input("Usina FV Norte")
        _sel(app, "Módulo FV").select("CS7L-590MS")
        _num(app, "Módulos em série").set_value(2)
        _num(app, "Strings em paralelo").set_value(10)
        app.run()
        self._salvar(app)
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "battery")
        _txt(app, "Nome do equipamento").input("Banco Li-ion")
        _num(app, "Energia nominal").set_value(100.0)
        _sel(app, "Modelo e célula").select("tremblay:liion_3p3v_2p3ah")
        _num(app, "Células em série").set_value(200)
        _num(app, "Ramos em paralelo").set_value(132)
        _num(app, "Taxa máxima de carga").set_value(0.5)
        _num(app, "Taxa máxima de descarga").set_value(1.0)
        app.run()
        self._salvar(app)
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "pemfc")
        _txt(app, "Nome do equipamento").input("PEMFC 1")
        _num(app, "Sistemas/stacks instalados").set_value(2)
        app.run()
        self._salvar(app)

    def test_comissionamento_completo_e_reabertura(self):
        app = self.novo()
        self._identificacao(app)
        self.assertEqual(app.session_state["mg_cstep"], 2)
        self._inventario(app)
        botao(app, "Continuar →").click().run()
        next(r for r in app.radio if r.label.startswith("Conexão com a rede")).set_value("isolada").run()
        _ok(self, app)
        self.assertEqual(self.saved().config["energy_balance"]["grid_connection"], "isolada")
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
        self.assertIn("EXPORTAR CONFIGURAÇÃO DA MICRORREDE (ZIP)", [b.label for b in app.button])
        self.assertIn("GERAR RELATÓRIO TÉCNICO (PDF)", [b.label for b in app.button])
        botao(app, "Ativar microrrede e concluir comissionamento").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["view"], "operacao")    # Piso 2A: Centro de Operação
        stored = self.saved()
        app2 = self.abrir_pelo_gestor(stored.config["installation"]["uid"])     # nova sessão → Gestor → ABRIR
        self.assertEqual(app2.session_state["seeds_route"]["view"], "operacao")
        self.assertNotIn("Nome da instalação *", [t.label for t in app2.text_input])
        w = app2.session_state["mg_work"]
        self.assertEqual(w, stored.config)
        names = {e["name"]: e for e in w["equipment"]}
        self.assertEqual(set(names), {"Usina FV Norte", "Banco Li-ion", "PEMFC 1"})
        arr = names["Usina FV Norte"]["arrays"][0]
        self.assertEqual((arr["reference"], arr["n_series"], arr["n_parallel"], arr["soiling_pct"], arr["soiling_default"]),
                         ("CS7L-590MS", 2, 10, 0.0, True))                # sujeira padrão 0 % (aceitação 9)
        bp = names["Banco Li-ion"]["params"]
        self.assertEqual((bp["energy_kWh"], bp["soc_min_pct"], bp["soc_max_pct"]), (100.0, 20.0, 80.0))   # aceitação 12
        self.assertNotIn("soc0_pct", bp)                                   # aceitação 11
        self.assertNotIn("topology", w)                                    # aceitação 15
        with sqlite3.connect(self.store().path) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM microgrid").fetchone()[0], 1)
        self.assertEqual(len(self.reg().entries()), 1)

    def test_comissionamento_retomado_apos_reinicio(self):
        app = self.novo()
        self._identificacao(app)
        self._inventario(app)
        self.assertEqual(len(self.saved().config["equipment"]), 3)
        app2 = self.abrir_pelo_gestor(self.saved().config["installation"]["uid"])   # retomada pelo Gestor
        self.assertEqual(app2.session_state["seeds_route"]["view"], "comissionamento")
        self.assertEqual(app2.session_state["mg_cstep"], 2)
        botao(app2, "← Voltar").click().run()
        _ok(self, app2)
        self.assertEqual(_txt(app2, "Nome da instalação").value, "Laboratório de Microrredes")
        self.assertEqual(len(self.saved().config["equipment"]), 3)


class DialogoEquipamentoTest(_Base):
    def setUp(self):
        super().setUp()
        self.seed()

    def test_catalogo_de_tecnologias_e_navegacao(self):                  # aceitação 3
        app = self.open("gestao")
        n = len(self.saved().config["equipment"])
        botao(app, "＋ Adicionar equipamento").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["mg_dialog"]["step"], "pick")
        self.assertNotIn("Nome do equipamento *", [t.label for t in app.text_input])   # catálogo antes do formulário
        self.pick(app, "wind")
        self.assertIn("Nome do equipamento *", [t.label for t in app.text_input])
        botao(app, "← Voltar às tecnologias").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["mg_dialog"]["step"], "pick")
        self.pick(app, "thermal")
        botao(app, "Cancelar").click().run()
        _ok(self, app)
        self.assertNotIn("mg_dialog", app.session_state)
        self.assertEqual(len(app.session_state["mg_work"]["equipment"]), n)   # nada criado sem confirmação
        eq = app.session_state["mg_work"]["equipment"][0]
        self.edit(app, eq["id"])                                             # existente: direto ao editor
        self.assertEqual(app.session_state["mg_dialog"]["step"], "edit")
        self.assertNotIn("← Voltar às tecnologias", [b.label for b in app.button])

    def test_confirmacao_de_equipamento_incompleto(self):                 # aceitação 4
        app = self.open("gestao")
        n = len(app.session_state["mg_work"]["equipment"])
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "battery")
        botao(app, "Salvar equipamento").click().run()                      # 1) sem nome: bloqueia
        self.assertIn("Informe o nome do equipamento", _errors(app))
        self.assertEqual(app.session_state["mg_dialog"]["step"], "edit")
        _txt(app, "Nome do equipamento").input("Banco recém-comprado")
        _num(app, "Energia nominal").set_value(-5.0)                        # 3) fisicamente inválido: bloqueia
        app.run()
        botao(app, "Salvar equipamento").click().run()
        self.assertIn("Energia nominal", _errors(app))
        self.assertEqual(app.session_state["mg_dialog"]["step"], "edit")
        _num(app, "Energia nominal").set_value(50.0)
        app.run()
        botao(app, "Salvar equipamento").click().run()                      # 2) faltam parâmetros: confirmação
        self.assertEqual(app.session_state["mg_dialog"]["step"], "confirm")
        body = " ".join(m.value for m in app.markdown) + " ".join(h.proto.body for h in app.get("html"))
        self.assertIn("Equipamento com configuração pendente", body)
        self.assertIn("Células em série (Ns)", body)
        self.assertEqual(len(app.session_state["mg_work"]["equipment"]), n)  # ainda não registrado
        botao(app, "Voltar à configuração").click().run()
        self.assertEqual(app.session_state["mg_dialog"]["step"], "edit")
        self.assertEqual(_txt(app, "Nome do equipamento").value, "Banco recém-comprado")   # nada perdido
        botao(app, "Salvar equipamento").click().run()
        botao(app, "Salvar como pendente").click().run()
        _ok(self, app)
        eq = next(e for e in app.session_state["mg_work"]["equipment"] if e["name"] == "Banco recém-comprado")
        self.assertEqual(eq["params"]["energy_kWh"], 50.0)
        self.assertTrue(C.missing_required(eq))

    def test_equipamento_completo_salva_sem_aviso(self):
        app = self.open("gestao")
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "thermal")
        _txt(app, "Nome do equipamento").input("Gerador diesel reserva")
        _sel(app, "Dinâmica operacional").select("local_generator")
        for lab, v in (("Potência máxima", 80.0), ("Potência mínima técnica", 20.0), ("CVU", 1100.0), ("Custo de partida", 50.0)):
            _num(app, lab).set_value(v)
        app.run()
        botao(app, "Salvar equipamento").click().run()
        _ok(self, app)
        self.assertNotIn("mg_dialog", app.session_state)                   # sem passo de confirmação
        th = next(e for e in app.session_state["mg_work"]["equipment"] if e["kind"] == "thermal")
        self.assertIsNone(th["params"]["ramp_kW_min"])
        self.assertTrue(C.is_configured(th))

    def test_usina_fv_com_varios_arranjos(self):                          # aceitação 5
        app = self.open("gestao")
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "pv")
        _txt(app, "Nome do equipamento").input("Usina composta")
        _sel(app, "Módulo FV").select("CS7L-590MS")
        _num(app, "Módulos em série").set_value(14)
        _num(app, "Strings em paralelo").set_value(3)
        app.run()
        botao(app, "＋ Adicionar arranjo").click().run()
        _ok(self, app)
        arrays = app.session_state["mg_dialog"]["draft"]["arrays"]
        self.assertEqual([a["name"] for a in arrays], ["Arranjo 01", "Arranjo 02"])
        second = arrays[1]["id"]
        next(r for r in app.radio if r.key and second in r.key).set_value("declarado").run()
        next(n for n in app.number_input if n.key and second in n.key and n.label.startswith("Potência nominal declarada")).set_value(12.5)
        app.run()
        body = " ".join(h.proto.body for h in app.get("html"))
        self.assertIn("37,28 kWp", body)                                   # 24,78 calculada + 12,50 declarada
        self.assertIn("572,6 V", body)                                     # Voc do arranjo 01 (14 × 40,9 V)
        botao(app, "Salvar equipamento").click().run()
        _ok(self, app)
        plant = next(e for e in app.session_state["mg_work"]["equipment"] if e["name"] == "Usina composta")
        self.assertEqual([a["mode"] for a in plant["arrays"]], ["modulo", "declarado"])
        self.assertIsNone(plant["arrays"][1]["reference"])                 # nada inventado
        self.assertEqual(plant["arrays"][1]["declared_kWp"], 12.5)
        self.edit(app, plant["id"])                                        # retirar um arranjo preserva o outro
        rm = next(b for b in app.button if b.label == "Retirar arranjo" and b.key and second in b.key)
        rm.click().run()
        botao(app, "Salvar equipamento").click().run()
        _ok(self, app)
        plant = next(e for e in app.session_state["mg_work"]["equipment"] if e["name"] == "Usina composta")
        self.assertEqual([a["name"] for a in plant["arrays"]], ["Arranjo 01"])

    def test_eolica_mostra_curva_do_catalogo(self):                       # aceitação 10 (interface)
        app = self.open("gestao")
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "wind")
        self.assertEqual(len(app.get("plotly_chart")), 0)
        _sel(app, "Aerogerador").select("Nordex N117/2400")
        app.run()
        self.assertEqual(len(app.get("plotly_chart")), 1)
        self.assertTrue(any("Tabela de potência do fabricante" in s.value for s in app.success))
        _sel(app, "Aerogerador").select("EWT DW61-1MW")
        app.run()
        self.assertTrue(any("digitalizada" in w.value and "não é medição certificada" in w.value for w in app.warning))

    def test_bateria_formulario_por_datasheet(self):                      # aceitação 11–13 (interface)
        app = self.open("gestao")
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "battery")
        labels = [n.label for n in app.number_input]
        self.assertNotIn("SOC inicial [%] *", labels)
        self.assertEqual(_num(app, "SOC mínimo").value, 20.0)
        self.assertEqual(_num(app, "SOC máximo").value, 80.0)
        _num(app, "Capacidade nominal").set_value(200.0)
        _num(app, "Corrente máx. contínua de descarga").set_value(100.0)
        app.run()
        body = " ".join(h.proto.body for h in app.get("html"))
        self.assertIn("0,500 C — estimativa (C = I_máx/Q)", body)
        self.assertNotIn("Taxa máx. de carga", body)                       # sem corrente de carga → não inventa

    def test_pemfc_criar_no_modellab_abre_link_real(self):
        app = self.open("gestao")
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "pemfc")
        next(r for r in app.radio if r.label == "Origem do dispositivo").set_value(C.PEMFC_IMPORT_REF).run()
        _ok(self, app)
        links = [b for b in app.get("link_button")]
        self.assertTrue(any(l.proto.url == "https://pemfc-modelab.streamlit.app/?view=home" for l in links))
        self.assertIn("IMPORTAR DISPOSITIVO DO PEMFC MODELLAB", " ".join(f.label for f in app.get("file_uploader")))


class GestaoTest(_Base):
    def test_editar_parametro_gera_revisao_sem_nova_microrrede(self):
        s = self.seed()
        uid = s.load().config["installation"]["uid"]
        app = self.open("gestao")
        bat = next(e for e in app.session_state["mg_work"]["equipment"] if e["kind"] == "battery")
        self.edit(app, bat["id"])
        _num(app, "SOC mínimo").set_value(25.0)
        app.run()
        botao(app, "Salvar equipamento").click().run()
        _ok(self, app)
        self.assertEqual(self.saved().revision, 1)          # ainda pendente
        botao(app, "Salvar alterações").click().run()
        _ok(self, app)
        st2 = self.saved()
        self.assertEqual(st2.revision, 2)
        self.assertEqual(st2.config["installation"]["uid"], uid)
        self.assertEqual(C.find_equipment(st2.config, bat["id"])["params"]["soc_min_pct"], 25.0)
        with sqlite3.connect(self.store().path) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM microgrid").fetchone()[0], 1)

    def test_descartar_edicao_pendente(self):
        self.seed()
        app = self.open("gestao")
        eq = copy.deepcopy(app.session_state["mg_work"]["equipment"][0])
        self.edit(app, eq["id"])
        _txt(app, "Nome do equipamento").input("Nome provisório")
        app.run()
        botao(app, "Salvar equipamento").click().run()
        self.assertEqual(app.session_state["mg_work"]["equipment"][0]["name"], "Nome provisório")
        botao(app, "Descartar").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["mg_work"]["equipment"][0]["name"], eq["name"])
        self.assertEqual(self.saved().revision, 1)

    def test_incorporar_e_retirar_equipamento(self):
        self.seed()
        app = self.open("gestao")
        botao(app, "＋ Adicionar equipamento").click().run()
        self.pick(app, "wind")
        _txt(app, "Nome do equipamento").input("Aerogerador novo")
        _sel(app, "Aerogerador").select("EWT DW61-1MW")
        _num(app, "Quantidade").set_value(1)
        app.run()
        botao(app, "Salvar equipamento").click().run()
        botao(app, "Salvar alterações").click().run()
        _ok(self, app)
        cfg = self.saved().config
        w = next(e for e in cfg["equipment"] if e["kind"] == "wind")
        app = self.open("gestao")
        self.edit(app, w["id"])
        _txt(app, "Motivo da retirada").input("devolvido ao fornecedor")
        next(c for c in app.checkbox if c.label.startswith("Confirmo a retirada")).check().run()
        botao(app, "Retirar equipamento").click().run()
        botao(app, "Salvar alterações").click().run()
        _ok(self, app)
        cfg = self.saved().config
        self.assertNotIn(w["id"], [e["id"] for e in cfg["equipment"]])
        self.assertEqual(cfg["retired"][-1]["retired_reason"], "devolvido ao fornecedor")

    def test_conflito_entre_sessoes_nao_sobrescreve(self):
        s = self.seed()
        app = self.open("gestao")
        eq = app.session_state["mg_work"]["equipment"][0]
        self.edit(app, eq["id"])
        _txt(app, "TAG").input("SESSAO-A")
        app.run()
        botao(app, "Salvar equipamento").click().run()
        other = copy.deepcopy(s.load().config)
        other["installation"]["description"] = "alterado pela sessão B"
        s.save(other, 1)
        botao(app, "Salvar alterações").click().run()
        _ok(self, app)
        self.assertIn("mg_conflict", app.session_state)
        final = self.saved()
        self.assertEqual(final.revision, 2)
        self.assertEqual(final.config["installation"]["description"], "alterado pela sessão B")

    def test_identificacao_antiga_incompleta_pode_ser_completada(self):   # aceitação 1 (atualização compatível)
        cfg = v16_equivalent_config("Instalação antiga")
        cfg["installation"]["nature"] = None
        cfg["installation"]["operation_mode"] = None
        n = len(cfg["equipment"])
        self.seed(cfg)
        app = self.open("gestao")
        self.assertTrue(any("Identificação incompleta" in w.value for w in app.warning))
        botao(app, "Completar identificação").click().run()
        app = continuar(app)
        self.assertEqual(app.session_state["seeds_route"]["tab"], "instalacao")
        botao(app, "Aplicar à edição").click().run()
        self.assertIn("natureza da atividade", _errors(app))
        _sel(app, "Natureza da atividade").select("industrial")
        _sel(app, "Modo de operação previsto").select("isolada")
        app.run()
        botao(app, "Aplicar à edição").click().run()
        botao(app, "Salvar alterações").click().run()
        _ok(self, app)
        st2 = self.saved().config
        self.assertEqual((st2["installation"]["nature"], st2["installation"]["operation_mode"]), ("industrial", "isolada"))
        self.assertEqual(len(st2["equipment"]), n)                          # inventário preservado

    def test_balanco_sem_acoplamentos_eletricos(self):                    # aceitação 15 (interface)
        self.seed()
        app = self.open("gestao", tab="balanco")
        labels = " ".join([s.label for s in app.selectbox] + [r.label for r in app.radio] + [n.label for n in app.number_input])
        for termo in ("Acoplamento", "Tensão nominal", "barramento", "Barramento"):
            self.assertNotIn(termo, labels)
        next(r for r in app.radio if r.label.startswith("Conexão com a rede")).set_value("conectada").run()
        _ok(self, app)
        self.assertTrue(any("equivale a uma compra física" in h.proto.body for h in app.get("html")))

    def test_relatorio_e_backup_disponiveis_na_gestao(self):              # aceitação 16–17 (interface)
        self.seed()
        app = self.open("gestao", tab="historico")
        botao(app, "EXPORTAR CONFIGURAÇÃO DA MICRORREDE (ZIP)").click().run()
        _ok(self, app)
        fp, name, data = app.session_state["mg_exp_zip_data"]
        self.assertTrue(name.endswith(".seeds2backup.zip"))
        self.assertTrue(self.store().inspect_backup(data).ok)
        botao(app, "GERAR RELATÓRIO TÉCNICO (PDF)").click().run()
        _ok(self, app)
        fp, name, pdf = app.session_state["mg_exp_pdf_data"]
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertTrue(name.endswith(".pdf"))


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
        self.assertEqual(item["origem"]["run_conditions"]["battery_soc0_pct"],
                         {e["id"]: 60.0 for e in saved.config["equipment"] if e["kind"] == "battery"})
        runs = self.store().runs()
        self.assertEqual((runs[0]["config_revision"], runs[0]["config_fingerprint"]), (1, saved.fingerprint))
        cfg = copy.deepcopy(saved.config)
        cfg["equipment"][0]["arrays"][0]["n_parallel"] = 6
        s.save(cfg, 1)
        app2 = continuar(app, timeout=240)
        _ok(self, app2)
        self.assertTrue(any("Resultado de configuração anterior" in h.proto.body for h in app2.get("html")))
        self.assertEqual(app2.session_state["orq_model_spec"]["solar"]["n_parallel"], 11)

    def test_soc_inicial_definido_nas_condicoes_da_rodada(self):          # aceitação 11 (condição de rodada)
        cfg = v16_equivalent_config()
        cfg["run_conditions"]["battery_soc0_pct"] = {}
        s = self.seed(cfg)
        app = self.open("simulacao", timeout=240)
        self.assertFalse(app.session_state["orq_spec_origin"]["represented"] and
                         any(m["kind"] == "battery" for m in app.session_state["orq_spec_origin"]["represented"]))
        for n in [x for x in app.number_input if x.label.endswith("SOC inicial [%]")]:
            n.set_value(55.0)
        app.run()
        botao(app, "Salvar condições da rodada").click().run()
        _ok(self, app)
        st2 = s.load()
        self.assertEqual(set(st2.config["run_conditions"]["battery_soc0_pct"].values()), {55.0})
        self.assertEqual(s.history()[0]["origin"], "run_conditions")
        app2 = self.open("simulacao", timeout=240)
        self.assertEqual(app2.session_state["orq_model_spec"]["battery"]["soc0"], 0.55)

    def test_exclusoes_exigem_confirmacao_e_ficam_registradas(self):
        cfg = v16_equivalent_config("Planta com exclusões")
        C.add_equipment(cfg, C.new_equipment("thermal", "UTE grande porte", params={
            "dynamic": "thermal_plant", "pmax_kW": 500.0, "pmin_kW": 100.0, "cvu_rs_MWh": 420.0, "startup_cost_rs": 0.0}))
        C.add_equipment(cfg, pv_plant("Usina antiga", C.new_array("Arranjo legado", mode="declarado", declared_kWp=20.0)))
        self.seed(cfg)
        app = self.open("simulacao", timeout=240)
        self.assertFalse(app.session_state["orq_run_gate"]["ok"])
        botao(app, "◎  Otimizador").click().run()
        self.assertTrue(botao(app, "▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO").disabled)
        app = continuar(app, timeout=240)
        next(c for c in app.checkbox if c.label.startswith("Confirmo executar esta rodada SEM")).check().run()
        app = continuar(app, timeout=240)
        self.assertTrue(app.session_state["orq_run_gate"]["ok"])
        botao(app, "▶ CALCULAR MODELOS E RODAR OTIMIZAÇÃO").click().run()
        _ok(self, app)
        excl = self.store().runs()[0]["excluded"]
        self.assertEqual(sorted(e["name"] for e in excl), ["UTE grande porte", "Usina antiga · Arranjo legado"])

    def test_alteracao_manual_no_console_desvincula_da_microrrede(self):
        self.seed()
        app = self.open("simulacao", timeout=240)
        app.session_state["orq_model_spec"]["fc"]["N_fc"] = 2
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


class InsercaoHtmlTest(_Base):
    PAYLOAD = '<img src=x onerror="alert(1)">[link](http://exemplo.invalid)'

    def test_nome_malicioso_no_comissionamento_e_na_gestao(self):
        cfg = v16_equivalent_config("Planta")
        cfg["equipment"][0]["name"] = self.PAYLOAD
        cfg["commissioning"].update(completed=False, step=4, completed_at=None)
        self.seed(cfg)
        app = self.open()
        self.assertEqual(app.session_state["mg_cstep"], 4)
        body = "\n".join(h.proto.body for h in app.get("html"))
        self.assertIn("&lt;img src=x onerror=", body)
        self.assertNotIn("<img src=x", body)
        cfg["commissioning"].update(completed=True, step=5)
        self.store().save(cfg, 1)
        app = self.open("gestao")
        self.edit(app, cfg["equipment"][0]["id"])
        label = next(c.label for c in app.get("expander") if "Retirar" in c.label) if False else None
        conf = next(c.label for c in app.checkbox if c.label.startswith("Confirmo a retirada"))
        self.assertIn("\\<img", conf)
        self.assertIn("\\[link\\]\\(http\\:", conf)

    def test_nome_de_csv_malicioso_no_console_v16(self):
        cfg = v16_equivalent_config()
        s = self.seed(cfg)
        h = s.put_blob(b"t_min,P_kW\n" + b"".join(f"{i},{80 + i % 3}\n".encode() for i in range(40)), "x.csv")
        cfg["demand"].update(source="csv", provenance="medido",
                             csv={"blob": h, "filename": "<b>carga</b><script>x</script>.csv", "start_min": 0, "duration_min": 30})
        s.save(cfg, 1)
        app = self.open("simulacao", timeout=240)
        app.session_state["orchestrator_page"] = "Visão Geral"
        app.run()
        _ok(self, app)
        card = next(m.value for m in app.markdown if 'class="ready-card"><small>1 · CARGA' in m.value)
        self.assertIn("&lt;b&gt;carga&lt;/b&gt;&lt;script&gt;", card)
        self.assertNotIn("<script>", card)


class InicioTest(_Base):
    def test_inicio_mostra_identidade_e_bancadas_acessiveis(self):
        # Piso 2A: o início da microrrede comissionada é o Centro de Operação; as bancadas V1.6 continuam acessíveis.
        self.seed()
        app = self.open()
        self.assertEqual(app.session_state["seeds_route"]["view"], "operacao")
        self.assertTrue(any("Planta Piloto" in h.proto.body for h in app.get("html")))
        self.assertTrue(any("Centro de Operação" in h.proto.body for h in app.get("html")))
        botao(app, "ABRIR EÓLICA").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["energy_source"], "wind")


if __name__ == "__main__":
    unittest.main()
