"""Piso 2A — Centro de Operação na interface (AppTest): início da microrrede comissionada, comissionamento
preservado, cenários (criar, editar, duplicar, retomar), Inicialização com validação, conflito entre sessões,
isolamento entre microrredes, ausência de controles fictícios e acesso às ferramentas V1.6.

O AppTest não executa o JavaScript dos componentes (barra superior): TROCAR MICRORREDE é simulado pelo mesmo
sinal que o componente produz (``seeds_switch_requested``); a navegação pela barra é simulada por
``seeds_route``. O clique real é verificado no E2E em navegador (``tools/e2e/e2e_piso2a_centro_operacao.js``).
"""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

if AppTest is not None:
    from apptest_utils import APP_PATH, botao, continuar

from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import service
from seeds2_fixtures import v16_equivalent_config

NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}
# Rótulos que aparentariam capacidades EMS ainda inexistentes (não podem existir como controles). "PREVIS" saiu da
# lista no Piso 2B: a etapa Previsões passou a existir de fato (ABRIR PREVISÕES); "GERAR PREVIS" continua proibido
# (nenhuma previsão meteorológica é gerada pelo software).
# Piso 2C: ABRIR ESTRATÉGIA EMS / ABRIR EXECUÇÃO são etapas reais; EXECUTAR só existe DENTRO da etapa 04 (após o
# preflight), nunca no painel nem nas etapas 01/02.
FAKE = ("EXECUTAR", "RODAR", "OTIMIZAR", "GERAR PREVIS", "INICIAR OPERA")


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


def _html(app) -> str:
    return "\n".join(h.proto.body for h in app.get("html"))


def _key(app, key):
    return next(b for b in app.button if b.key == key)


def _nums(app, label):
    return [n for n in app.number_input if n.label.startswith(label)]


def _batteries(doc: dict) -> list[str]:
    """Bancos na ORDEM DO INVENTÁRIO (a mesma dos cartões da Inicialização; o JSON canônico ordena por id)."""
    eqs = doc["inventory_ref"]["equipment"]
    return sorted((e for e, r in eqs.items() if r["kind"] == "battery"), key=lambda e: eqs[e]["position"])


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

    def session(self, uid: str | None = None, view: str | None = None, tab: str | None = None,
                timeout: float = 120, query: dict | None = None) -> AppTest:
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        app = AppTest.from_file(str(APP_PATH), default_timeout=timeout)
        if uid:
            app.session_state["mg_active_uid"] = uid
        if view:
            app.session_state["seeds_route"] = {"view": view, "tab": tab}
        for k, v in (query or {}).items():
            app.query_params[k] = v
        app.run()
        _ok(self, app)
        return app

    def abrir_pelo_gestor(self, uid: str) -> AppTest:
        app = self.session()
        _key(app, f"g_open_{uid}").click().run()
        _ok(self, app)
        return continuar(app, 120)

    def criar_cenario(self, app: AppTest, name: str, desc: str = "") -> AppTest:
        labels = [b.label for b in app.button]
        botao(app, "＋ NOVO CENÁRIO" if "＋ NOVO CENÁRIO" in labels else "＋ Novo").click().run()
        next(t for t in app.text_input if t.label.startswith("Nome do cenário")).input(name)
        if desc:
            next(t for t in app.text_area if t.label == "Descrição").input(desc)
        botao(app, "Criar cenário").click().run()
        _ok(self, app)
        return continuar(app, 120)

    def inicializacao(self, app: AppTest) -> AppTest:
        botao(app, "ABRIR INICIALIZAÇÃO").click().run()
        _ok(self, app)
        app = continuar(app, 120)
        self.assertEqual(app.session_state["seeds_route"], {"view": "operacao", "tab": "inicializacao"})
        return app


class CentroInicioTest(_Base):
    def test_microrrede_comissionada_abre_no_centro_de_operacao(self):
        uid = self.make("Planta Operacional")
        app = self.abrir_pelo_gestor(uid)
        self.assertEqual(app.session_state["seeds_route"]["view"], "operacao")
        self.assertEqual(app.session_state["mg_active_uid"], uid)
        html = _html(app)
        self.assertIn("Centro de Operação", html)
        self.assertIn("Planta Operacional", html)
        self.assertIn("Nenhum cenário nesta microrrede", html)
        self.assertIn("＋ NOVO CENÁRIO", [b.label for b in app.button])

    def test_microrrede_nao_comissionada_segue_no_comissionamento(self):
        uid = self.make("Em configuração", commissioned=False)
        app = self.abrir_pelo_gestor(uid)
        self.assertEqual(app.session_state["seeds_route"]["view"], "comissionamento")
        for view, tab in (("operacao", None), ("operacao", "inicializacao"), ("inicio", None)):
            a = self.session(uid, view, tab)
            self.assertEqual(a.session_state["seeds_route"]["view"], "comissionamento", view)
            self.assertNotIn("Centro de Operação", _html(a))
        self.assertEqual(self.reg().open(uid).list_scenarios(), [])

    def test_link_antigo_view_inicio_leva_ao_centro(self):
        uid = self.make("Link antigo")
        app = self.session(query={"mg": uid, "view": "inicio"})
        self.assertEqual((app.session_state["mg_active_uid"], app.session_state["seeds_route"]["view"]), (uid, "operacao"))

    def test_sem_controles_ficticios_e_etapas_futuras_identificadas(self):
        uid = self.make("Sem ficção")
        app = self.criar_cenario(self.abrir_pelo_gestor(uid), "Base")
        labels = [b.label.upper() for b in app.button]
        self.assertFalse([l for l in labels if any(f in l for f in FAKE)], labels)
        html = _html(app)
        for stage in ("Previsões", "Estratégia EMS", "Execução"):
            self.assertIn(stage, html)
        self.assertEqual(html.count("Não implementado"), 0)                    # Piso 2C: as 4 etapas são reais
        for b in ("ABRIR PREVISÕES", "ABRIR ESTRATÉGIA EMS", "ABRIR EXECUÇÃO"):
            self.assertIn(b, [x.label for x in app.button])
        self.assertIn("Não executável (v1)", html)                             # preflight da versão salva (sem estratégia)
        self.assertIn("As <b>bancadas</b> dos modelos (barra lateral) continuam independentes", html)   # UI-REDESIGN-01
        app = self.inicializacao(app)
        labels = [b.label.upper() for b in app.button]
        self.assertFalse([l for l in labels if any(f in l for f in FAKE)], labels)

    def test_ferramentas_v16_preservadas(self):
        uid = self.make("V1.6 intacta")
        app = self.session(uid, "operacao")
        for label in ("ABRIR SOLAR", "ABRIR EÓLICA", "ABRIR BATERIA", "ABRIR H₂ / PEMFC", "ABRIR TÉRMICA"):
            self.assertIn(label, [b.label for b in app.button])
        botao(app, "ABRIR BATERIA").click().run()
        _ok(self, app)
        self.assertEqual(app.session_state["energy_source"], "battery")
        sim = self.session(uid, "simulacao", timeout=240)
        self.assertEqual(sim.session_state["seeds_route"]["view"], "simulacao")
        self.assertEqual(sim.session_state["orq_mg_applied"]["microgrid_uid"], uid)   # console V1.6 com a config salva
        self.assertIn("orchestrator_page", sim.session_state)


class CenarioInterfaceTest(_Base):
    def test_criar_editar_salvar_e_retomar_apos_reinicio(self):
        uid = self.make("Retomada")
        app = self.criar_cenario(self.abrir_pelo_gestor(uid), "Operação de inverno", "SOC baixo")
        scn = app.session_state["op_scenario_uid"]
        self.assertIn("Operação de inverno", _html(app))
        app = self.inicializacao(app)
        socs = _nums(app, "SOC inicial")
        self.assertEqual(len(socs), 2)                                # um controle por banco instalado
        self.assertEqual(len([s for s in app.selectbox if s.label == "Estado operativo inicial"]), 2)   # 2 PEMFC
        self.assertEqual(len(_nums(app, "Potência inicial")), 2)       # sem térmica instalada → só PEMFC
        socs[0].set_value(10.0)
        socs[1].set_value(10.0)
        for sel in [s for s in app.selectbox if s.label == "Estado operativo inicial"]:
            sel.set_value("desligada")
        app.run()
        _ok(self, app)
        html = _html(app)
        self.assertIn("Advertência técnica", html)                    # SOC fora da restrição: aviso
        self.assertIn("Capacidade científica pendente", html)
        self.assertNotIn("PEMFC declarada desligada", html)
        botao(app, "SALVAR CENÁRIO").click().run()
        _ok(self, app)
        self.assertEqual([e.value for e in app.error], [])            # aviso não bloqueia
        st = self.reg().open(uid)
        sc = st.get_scenario(scn)
        self.assertEqual(sc.version, 2)
        bats = _batteries(sc.document)
        self.assertEqual([sc.document["initialization"]["equipment"][b]["soc0_pct"] for b in bats], [10.0, 10.0])
        # "reinício": nova sessão, Gestor → ABRIR → o cenário volta selecionado com os valores salvos
        app2 = self.inicializacao(self.abrir_pelo_gestor(uid))
        self.assertEqual(app2.session_state["op_scenario_uid"], scn)
        self.assertEqual([n.value for n in _nums(app2, "SOC inicial")], [10.0, 10.0])
        # recarga com ?sc= mantém o mesmo cenário
        app3 = self.session(query={"mg": uid, "view": "operacao", "sc": scn})
        self.assertEqual(app3.session_state["op_scenario_uid"], scn)

    def test_estado_contraditorio_e_recusado_sem_gravar(self):
        uid = self.make("Contradição")
        app = self.inicializacao(self.criar_cenario(self.abrir_pelo_gestor(uid), "Teste"))
        scn = app.session_state["op_scenario_uid"]
        next(s for s in app.selectbox if s.label == "Estado operativo inicial").set_value("desligada")
        _nums(app, "Potência inicial")[0].set_value(25.0)
        app.run()
        self.assertIn("desligada não pode entregar 25 kW", _html(app))
        self.assertIn("Erro de coerência", _html(app))
        botao(app, "SALVAR CENÁRIO").click().run()
        _ok(self, app)
        self.assertTrue(any("Nada foi gravado" in e.value.replace("\\", "") for e in app.error), [e.value for e in app.error])
        self.assertEqual(self.reg().open(uid).get_scenario(scn).version, 1)

    def test_duplicar_e_renomear_pela_interface(self):
        uid = self.make("Duplicação")
        app = self.criar_cenario(self.abrir_pelo_gestor(uid), "Original")
        orig = app.session_state["op_scenario_uid"]
        botao(app, "Duplicar").click().run()
        self.assertEqual(next(t for t in app.text_input if t.label.startswith("Nome do cenário")).value, "Cópia de Original")
        botao(app, "Duplicar cenário").click().run()
        _ok(self, app)
        app = continuar(app, 120)
        dup = app.session_state["op_scenario_uid"]
        self.assertNotEqual(dup, orig)
        botao(app, "Nome e descrição").click().run()
        next(t for t in app.text_input if t.label.startswith("Nome do cenário")).input("Cópia renomeada")
        botao(app, "Salvar nome e descrição").click().run()
        _ok(self, app)
        st = self.reg().open(uid)
        self.assertEqual([(s.name, s.version) for s in st.list_scenarios()], [("Original", 1), ("Cópia renomeada", 2)])
        self.assertEqual(st.get_scenario(dup).document["lineage"]["duplicated_from"]["scenario_uid"], orig)


class CenarioSessoesTest(_Base):
    def test_duas_sessoes_sem_sobrescrita_silenciosa(self):
        uid = self.make("Compartilhada")
        st = self.reg().open(uid)
        scn = service.create(st, name="Comum").scenario_uid
        a = self.inicializacao(self.abrir_pelo_gestor(uid))
        b = self.inicializacao(self.abrir_pelo_gestor(uid))
        _nums(a, "SOC inicial")[0].set_value(30.0)
        a.run()
        _nums(b, "SOC inicial")[0].set_value(70.0)
        b.run()
        botao(a, "SALVAR CENÁRIO").click().run()
        _ok(self, a)
        botao(b, "SALVAR CENÁRIO").click().run()
        _ok(self, b)
        b = continuar(b, 120)
        self.assertTrue(any("alterado por outra sessão" in e.value for e in b.error), [e.value for e in b.error])
        cur = st.get_scenario(scn)
        bat = _batteries(cur.document)[0]                               # o banco do 1º cartão da interface
        self.assertEqual((cur.version, cur.document["initialization"]["equipment"][bat]["soc0_pct"]), (2, 30.0))
        self.assertEqual(b.session_state["op_work"]["initialization"]["equipment"][bat]["soc0_pct"], 70.0)  # preservado
        botao(b, "Recarregar versão salva (descarta as alterações desta sessão)").click().run()
        _ok(self, b)
        b = continuar(b, 120)
        self.assertEqual(_nums(b, "SOC inicial")[0].value, 30.0)

    def test_troca_de_microrrede_isola_cenarios(self):
        ua, ub = self.make("A"), self.make("B")
        sa = service.create(self.reg().open(ua), name="Só de A").scenario_uid
        app = self.abrir_pelo_gestor(ua)
        self.assertEqual(app.session_state["op_scenario_uid"], sa)
        app.session_state["seeds_switch_requested"] = True             # TROCAR MICRORREDE
        app.run()
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["view"], "gestor")
        for k in ("op_scenario_uid", "op_work", "op_work_uid", "op_base_version", "op_base_fp"):
            self.assertNotIn(k, app.session_state)                     # estado do cenário de A limpo na troca
        _key(app, f"g_open_{ub}").click().run()
        app = continuar(app, 120)
        self.assertEqual(app.session_state["mg_active_uid"], ub)
        self.assertNotIn("Só de A", _html(app))
        self.assertIn("Nenhum cenário nesta microrrede", _html(app))
        # um cenário de A na URL de B é ignorado
        app2 = self.session(query={"mg": ub, "view": "operacao", "sc": sa})
        self.assertNotIn("op_scenario_uid", app2.session_state)
        self.assertNotIn("Só de A", _html(app2))

    def test_microrrede_excluida_e_reimportada_nao_traz_cenarios_antigos(self):
        uid = self.make("Reimportada")
        st = self.reg().open(uid)
        service.create(st, name="Antigo")
        backup = st.export_backup()
        app = self.abrir_pelo_gestor(uid)
        self.assertIn("Antigo", _html(app))
        reg = self.reg()
        reg.delete(uid)
        reg.import_new(backup)
        app.run()                                                     # a sessão antiga volta ao Gestor
        _ok(self, app)
        app = continuar(app, 120)
        self.assertEqual(app.session_state["seeds_route"]["view"], "gestor")
        fresh = self.abrir_pelo_gestor(uid)
        self.assertEqual(fresh.session_state["seeds_route"]["view"], "operacao")
        self.assertIn("Nenhum cenário nesta microrrede", _html(fresh))
        self.assertNotIn("Antigo", _html(fresh))


class BackupEscopoTest(_Base):
    """Correção de auditoria do PR #6: o backup ZIP (formato 2) NÃO contém cenários do Piso 2A. Toda exportação,
    restauração e exclusão o declara; a exclusão de uma microrrede com cenários exige consentimento específico."""

    def _texts(self, app) -> str:
        parts = [_html(app)] + [c.value for c in app.caption] + [w.value for w in app.warning] + \
                [e.value for e in app.error] + [m.value for m in app.markdown] + [c.label for c in app.checkbox]
        return "\n".join(parts).replace("\\", "")

    def _dialogo(self, uid: str) -> AppTest:
        app = self.session()
        _key(app, f"g_del_{uid}").click().run()
        _ok(self, app)
        return app

    def _nome(self, app, nome: str) -> None:
        next(t for t in app.text_input if t.label.startswith("Digite o nome exato")).input(nome).run()

    def test_exclusao_com_cenarios_exige_consentimento_especifico(self):
        uid = self.make("Com cenários")
        st = self.reg().open(uid)
        service.create(st, name="C1")
        service.create(st, name="C2")
        with mock.patch.dict(os.environ, {"SEEDS2_DEV_MODE": "1"}):
            app = self._dialogo(uid)
            txt = self._texts(app)
            self.assertIn("Cenários operativos (Piso 2A)</td><td><b>2</b>", _html(app))     # contagem no resumo
            self.assertIn("2 cenário(s) operativo(s)", txt)
            self.assertIn("não podem ser recuperados pelo ZIP atual", txt)
            self.assertIn("Não inclui os cenários operativos", txt)                          # alcance do ZIP
            self._nome(app, "Com cenários")                                                  # confirmação genérica...
            self.assertTrue(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)                  # ...não basta
            ck = next(c for c in app.checkbox if c.label.startswith("Entendo que os 2 cenário(s)"))
            self.assertIn("ZIP atual não permite recuperá-los", ck.label)
            ck.check().run()
            self.assertFalse(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)                # consentimento consciente
            botao(app, "EXCLUIR DEFINITIVAMENTE").click().run()
            _ok(self, app)
        self.assertFalse(self.reg().exists(uid))                                             # exclusão continua possível
        self.assertFalse(self.reg().dir_for(uid).exists())

    def test_exclusao_sem_cenarios_mantem_a_confirmacao_existente(self):
        uid = self.make("Sem cenários")
        with mock.patch.dict(os.environ, {"SEEDS2_DEV_MODE": "1"}):
            app = self._dialogo(uid)
            self.assertIn("Cenários operativos (Piso 2A)</td><td><b>0</b>", _html(app))
            self.assertFalse([c for c in app.checkbox if c.label.startswith("Entendo que")])
            self._nome(app, "Sem cenários")
            self.assertFalse(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)
            botao(app, "EXCLUIR DEFINITIVAMENTE").click().run()
            _ok(self, app)
        self.assertFalse(self.reg().exists(uid))

    def test_cenario_criado_durante_o_dialogo_exige_nova_confirmacao(self):
        uid = self.make("Corrida")
        st = self.reg().open(uid)
        service.create(st, name="C1")
        with mock.patch.dict(os.environ, {"SEEDS2_DEV_MODE": "1"}):
            app = self._dialogo(uid)
            self._nome(app, "Corrida")
            next(c for c in app.checkbox if c.label.startswith("Entendo que os 1 cenário(s)")).check().run()
            self.assertFalse(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)
            service.create(st, name="C2 (outra sessão)")                                    # outra sessão cria cenário
            botao(app, "EXCLUIR DEFINITIVAMENTE").click().run()
            _ok(self, app)
            self.assertTrue(self.reg().exists(uid))                                          # nada excluído
            self.assertEqual(len(self.reg().open(uid).list_scenarios()), 2)
            ck = next(c for c in app.checkbox if c.label.startswith("Entendo que os 2 cenário(s)"))
            self.assertFalse(ck.value)                                                       # consentimento renovado
            self.assertTrue(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)

    def test_exclusao_desativada_continua_informando_os_cenarios(self):
        uid = self.make("Protegida")
        service.create(self.reg().open(uid), name="C1")
        app = self._dialogo(uid)                                                             # sem credencial nem DEV_MODE
        self.assertIn("Cenários operativos (Piso 2A)</td><td><b>1</b>", _html(app))
        self.assertNotIn("EXCLUIR DEFINITIVAMENTE", [b.label for b in app.button])
        self.assertTrue(self.reg().exists(uid))

    def test_exportacao_e_restauracao_declaram_que_o_zip_nao_inclui_cenarios(self):
        uid = self.make("Avisos")
        # Gestão → Relatório, histórico e backups: exportar (aviso) e restaurar (escopo)
        app = self.session(uid, "gestao", "historico")
        txt = self._texts(app)
        self.assertIn("Não inclui os cenários operativos do Centro de Operação (Piso 2A)", txt)
        self.assertIn("nem as rodadas científicas executadas e seus resultados (Piso 2C", txt)
        self.assertIn("nenhum cenário operativo nem rodada científica é restaurado", txt)
        # Gestão → exportação ZIP da configuração (componente comum de exportações)
        self.assertIn("EXPORTAR CONFIGURAÇÃO DA MICRORREDE (ZIP)", [b.label for b in app.button])
        # Gestor: botão ZIP do cartão (ajuda + legenda do arquivo preparado) e diálogo de importação
        g = self.session()
        zb = _key(g, f"g_zip_{uid}")
        self.assertIn("NÃO inclui os cenários operativos nem as rodadas científicas", zb.help)
        zb.click().run()
        _ok(self, g)
        self.assertTrue(any("não inclui cenários nem rodadas científicas" in c.value for c in g.caption),
                        [c.value for c in g.caption])
        botao(g, "IMPORTAR MICRORREDE (ZIP)").click().run()
        _ok(self, g)
        self.assertIn("nenhum cenário operativo nem rodada científica é restaurado", self._texts(g))


if __name__ == "__main__":
    unittest.main()
