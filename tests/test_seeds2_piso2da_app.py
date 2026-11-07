"""Piso 2D-A — Arquivo Científico na interface (AppTest).

Cobre: acesso pelo Centro de Operação (cartão + aba) e pelo Gestor SEM microrrede; EXPORTAR CENÁRIO COMPLETO (pacote
preparado e verificável); ARQUIVAR NESTA INSTALAÇÃO; importação numa instalação VAZIA com relatório de verificação
(contagens, datas, versões de software, tamanho) e confirmação explícita; pacote corrompido recusado sem botão de
importação; duplicata reconhecida e cópia identificável; estudo aberto com configuração, previsões (gráficos),
rodadas e resultados (KPIs e curvas originais), procedência e integridade — tudo com ``run_optimizer`` e
``build_exchange_package`` SABOTADOS (abrir/navegar/recarregar nunca os chama); reabertura numa nova sessão pela URL
(``?view=arquivo&tab=estudo&study=…&srun=…``); importação com microrrede aberta não altera a microrrede; aviso da
exclusão aponta o Arquivo Científico sem enfraquecer os consentimentos.

Desenho real, download/upload no navegador, reinício do servidor e tablet: ``tools/e2e/e2e_piso2da_arquivo.js``.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

if AppTest is not None:
    from apptest_utils import APP_PATH, botao, continuar

import orchestrator_runtime as RT
from seeds2 import APP_VERSION
from seeds2.archive import exporter
from seeds2.archive import format as FMT
from seeds2.archive.store import ArchiveStore
from seeds2.microgrid.registry import MicrogridRegistry
from seeds2.operation import runner
from seeds2_fixtures import v16_equivalent_config
from test_seeds2_piso2c import ready

NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}
_SRC: dict = {}


def _source() -> dict:
    """Instalação de ORIGEM (uma vez): microrrede com um cenário executado de verdade (Piso 2C) e o pacote exportado."""
    if not _SRC:
        tmp = tempfile.TemporaryDirectory()
        reg = MicrogridRegistry(tmp.name)
        cfg = v16_equivalent_config("Industrial A")
        reg.create(cfg, origin="commissioning")
        st = reg.open(cfg["installation"]["uid"])
        sc = ready(st, name="Alta demanda")
        run = runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        assert run.state == "concluida"
        data, man = exporter.export_bytes(st, sc.scenario_uid)
        _SRC.update(tmp=tmp, reg=reg, store=st, uid=cfg["installation"]["uid"], scenario=sc, run=run, pkg=data, man=man)
    return _SRC


def _ok(tc, app):
    tc.assertEqual(len(app.exception), 0, [e.value for e in app.exception])


def _html(app) -> str:
    return "\n".join(h.proto.body for h in app.get("html"))


def _texts(app) -> str:
    parts = [_html(app)] + [c.value for c in app.caption] + [w.value for w in app.warning] + [i.value for i in app.info] + \
            [e.value for e in app.error] + [m.value for m in app.markdown] + [c.label for c in app.checkbox] + \
            [s.value for s in app.success]
    return "\n".join(parts).replace("\\", "").replace("**", "")


def _charts(app) -> list[dict]:
    return [json.loads(c.proto.spec) for c in app.get("plotly_chart")]


def _titles(app) -> list[str]:
    return [c["layout"]["title"]["text"].split("<br>")[0] for c in _charts(app)]


@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class _Base(unittest.TestCase):
    def setUp(self):
        self.src = _source()
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        self._env = mock.patch.dict(os.environ, NO_ADMIN)
        self._env.start()
        # Abrir, navegar ou importar estudos NUNCA pode chamar o motor (qualquer chamada falha o teste).
        self._no_engine = [mock.patch.object(RT, "run_optimizer", side_effect=AssertionError("run_optimizer chamado")),
                           mock.patch.object(RT, "build_exchange_package",
                                             side_effect=AssertionError("build_exchange_package chamado"))]
        for p in self._no_engine:
            p.start()

    def tearDown(self):
        for p in self._no_engine:
            p.stop()
        self._env.stop()
        self._tmp.cleanup()

    def gestor_archive(self) -> AppTest:
        app = AppTest.from_file(str(APP_PATH), default_timeout=90)
        app.run()
        _ok(self, app)
        botao(app, "ARQUIVO CIENTÍFICO").click().run()
        app = continuar(app, timeout=90)
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["view"], "arquivo")
        return app

    def upload(self, app: AppTest, data: bytes, name: str = f"estudo{FMT.SUFFIX}") -> AppTest:
        up = next(u for u in app.file_uploader if (u.key or "").startswith("ar_upload_"))
        up.set_value((name, data, "application/zip"))
        app.run()
        _ok(self, app)
        return app

    def import_clean(self) -> tuple[AppTest, str]:
        app = self.upload(self.gestor_archive(), self.src["pkg"])
        next(c for c in app.checkbox if (c.key or "").startswith("ar_confirm_")).check().run()
        botao(app, "CONFIRMAR IMPORTAÇÃO").click().run()
        app = continuar(app, timeout=90)
        _ok(self, app)
        studies = ArchiveStore(self.dir).list_studies()
        self.assertEqual(len(studies), 1)
        return app, studies[0].archive_uid


class GestorImportacaoTest(_Base):
    def test_instalacao_vazia_importa_verifica_e_abre_sem_executar(self):
        app = self.upload(self.gestor_archive(), self.src["pkg"])
        txt = _texts(app)
        self.assertIn("Verificação concluída", txt)
        self.assertIn("Alta demanda", txt)
        self.assertIn("Industrial A", txt)
        self.assertIn("1 concluída", txt)                                   # rodadas por estado
        self.assertIn(APP_VERSION, txt)                                     # versão do SEEDS2 que exportou
        self.assertIn("compactado", txt)                                    # tamanho
        self.assertIn("Não é uma assinatura digital", txt)
        imp = botao(app, "CONFIRMAR IMPORTAÇÃO")
        self.assertTrue(imp.disabled)                                       # confirmação explícita obrigatória
        self.assertEqual(ArchiveStore(self.dir).list_studies(), [])        # inspecionar não grava
        next(c for c in app.checkbox if (c.key or "").startswith("ar_confirm_")).check().run()
        botao(app, "CONFIRMAR IMPORTAÇÃO").click().run()
        app = continuar(app, timeout=90)
        _ok(self, app)
        self.assertIn("Importado", _texts(app))                             # cartão do estudo (aquisição)
        self.assertIn("Verificado na importação", _texts(app))
        self.assertEqual(MicrogridRegistry(self.dir).entries(), [])         # nenhuma microrrede criada
        self.assertEqual(sorted(os.listdir(self.dir)) and [p for p in os.listdir(self.dir) if p == "microgrids"],
                         ["microgrids"])
        self.assertEqual(list((Path(self.dir) / "microgrids").iterdir()), [])
        botao(app, "ABRIR ESTUDO").click().run()
        app = continuar(app, timeout=90)
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"]["tab"], "estudo")
        txt = _texts(app)
        self.assertIn("Estudo arquivado · somente leitura", txt)
        self.assertIn("não executa modelos nem o otimizador", txt)
        self.assertIn(self.src["uid"], txt)                                 # identidade de origem preservada

    def test_secoes_do_estudo_configuracao_previsoes_rodadas_integridade(self):
        app, uid = self.import_clean()
        botao(app, "ABRIR ESTUDO").click().run()
        app = continuar(app, timeout=90)
        app.radio(key="ar_section").set_value("Configuração").run()
        _ok(self, app)
        txt = _texts(app)
        for s in ("Inventário de referência", "Estados iniciais", "Estratégia EMS", "Janela temporal da missão",
                  "GWO", "America/Sao_Paulo"):
            self.assertIn(s, txt)
        self.assertGreaterEqual(len(app.dataframe), 2)
        app.radio(key="ar_section").set_value("Previsões").run()
        _ok(self, app)
        self.assertEqual(len(_charts(app)), 2)                               # demanda + clima, dados do estudo
        self.assertTrue(any("Demanda" in t for t in _titles(app)))
        app.radio(key="ar_section").set_value("Rodadas e resultados").run()
        _ok(self, app)
        b = next(b for b in app.button if b.label == "Consultar")
        b.click().run()
        app = continuar(app, timeout=90)
        _ok(self, app)
        self.assertEqual(app.radio(key="ar_section").value, "Rodadas e resultados")
        titles = _titles(app)
        self.assertIn("Demanda e potência por fonte", titles)
        self.assertIn("Estado de carga da bateria", titles)
        txt = _texts(app)
        self.assertIn("R$ 88,32", txt)                                      # custo original da rodada
        self.assertIn("não recalculados", txt)
        app.radio(key="ar_section").set_value("Integridade").run()
        botao(app, "VERIFICAR INTEGRIDADE AGORA").click().run()
        _ok(self, app)
        self.assertTrue(any("Integridade confirmada" in s.value for s in app.success))
        app.radio(key="ar_section").set_value("Procedência").run()
        _ok(self, app)
        self.assertIn(self.src["scenario"].scenario_uid, _texts(app))

    def test_reabrir_pela_url_em_nova_sessao_mesmo_estudo(self):
        _, uid = self.import_clean()
        run_uid = self.src["run"].run_uid
        app = AppTest.from_file(str(APP_PATH), default_timeout=90)
        app.query_params.update({"view": "arquivo", "tab": "estudo", "study": uid, "srun": run_uid})
        app.run()
        _ok(self, app)
        self.assertEqual(app.radio(key="ar_section").value, "Rodadas e resultados")
        self.assertIn("Demanda e potência por fonte", _titles(app))
        self.assertIn("R$ 88,32", _texts(app))

    def test_pacote_corrompido_recusado_sem_botao_de_importar(self):
        import io
        import zipfile

        zin = zipfile.ZipFile(io.BytesIO(self.src["pkg"]))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for i in zin.infolist():
                b = zin.read(i)
                if i.filename.endswith("despacho_ems.csv"):
                    b = b.replace(b"0", b"1", 3)
                z.writestr(i.filename, b)
        app = self.upload(self.gestor_archive(), buf.getvalue())
        txt = _texts(app)
        self.assertIn("Integridade violada", txt)
        self.assertIn("Pacote rejeitado", txt)
        self.assertFalse(any(b.label == "CONFIRMAR IMPORTAÇÃO" for b in app.button))
        self.assertEqual(ArchiveStore(self.dir).list_studies(), [])

    def test_duplicata_reconhecida_e_copia_identificavel(self):
        app, uid = self.import_clean()
        app = self.upload(app, self.src["pkg"])
        self.assertIn("já está no Arquivo Científico", _texts(app))
        self.assertTrue(any(b.label == "ABRIR ESTUDO EXISTENTE" for b in app.button))
        next(c for c in app.checkbox if (c.key or "").startswith("ar_copy_")).check().run()
        next(c for c in app.checkbox if (c.key or "").startswith("ar_confirm_")).check().run()
        botao(app, "IMPORTAR OUTRA CÓPIA").click().run()
        app = continuar(app, timeout=90)
        _ok(self, app)
        studies = ArchiveStore(self.dir).list_studies()
        self.assertEqual(len(studies), 2)
        self.assertEqual(studies[1].copy_of, uid)
        self.assertEqual({s.origin_scenario_uid for s in studies}, {self.src["scenario"].scenario_uid})


class CentroDeOperacaoTest(_Base):
    def _centro(self) -> tuple[AppTest, str]:
        reg = MicrogridRegistry(self.dir)
        cfg = v16_equivalent_config("Destino B")
        reg.create(cfg, origin="commissioning")
        app = AppTest.from_file(str(APP_PATH), default_timeout=90)
        app.session_state["seeds_route"] = {"view": "operacao", "tab": None}
        app.session_state["mg_active_uid"] = cfg["installation"]["uid"]
        app.run()
        _ok(self, app)
        return app, cfg["installation"]["uid"]

    def test_cartao_no_painel_e_importacao_no_contexto_nao_altera_a_microrrede(self):
        app, uid = self._centro()
        self.assertIn("Arquivo Científico", _html(app))
        st_before = MicrogridRegistry(self.dir).open(uid)
        rev, scn = st_before.load().revision, st_before.list_scenarios()
        botao(app, "ABRIR ARQUIVO CIENTÍFICO").click().run()
        app = continuar(app, timeout=90)
        _ok(self, app)
        self.assertEqual(app.session_state["seeds_route"], {"view": "operacao", "tab": "arquivo"})
        self.assertIn("Esta microrrede ainda não tem cenários operativos para exportar.", _texts(app))
        app = self.upload(app, self.src["pkg"])
        next(c for c in app.checkbox if (c.key or "").startswith("ar_confirm_")).check().run()
        botao(app, "CONFIRMAR IMPORTAÇÃO").click().run()
        app = continuar(app, timeout=90)
        _ok(self, app)
        s = ArchiveStore(self.dir).list_studies()[0]
        self.assertEqual(s.context_microgrid_uid, uid)                      # contexto apenas registrado
        self.assertEqual(s.origin_microgrid_uid, self.src["uid"])           # atribuição à origem
        st = MicrogridRegistry(self.dir).open(uid)
        self.assertEqual((st.load().revision, st.list_scenarios(), st.list_runs()), (rev, scn, []))

    def test_exportar_e_arquivar_cenario_da_microrrede_ativa(self):
        for p in self._no_engine:                       # esta instalação precisa executar UMA rodada de origem
            p.stop()
        reg = MicrogridRegistry(self.dir)
        cfg = v16_equivalent_config("Origem C")
        reg.create(cfg, origin="commissioning")
        st = reg.open(cfg["installation"]["uid"])
        sc = ready(st, name="Experimento C")
        runner.submit(st, sc.scenario_uid, sc.version, runner.new_request_id(), background=False)
        for p in self._no_engine:
            p.start()
        app = AppTest.from_file(str(APP_PATH), default_timeout=90)
        app.session_state["seeds_route"] = {"view": "operacao", "tab": "arquivo"}
        app.session_state["mg_active_uid"] = cfg["installation"]["uid"]
        app.run()
        _ok(self, app)
        self.assertIn("Exportar cenário completo", _texts(app))
        botao(app, "PREPARAR EXPORTAÇÃO").click().run()
        _ok(self, app)
        self.assertTrue(any(d.label == "⬇ EXPORTAR CENÁRIO COMPLETO" for d in app.get("download_button")))
        prep = app.session_state["ar_export"]
        self.assertTrue(prep["filename"].endswith(FMT.SUFFIX))
        rep = FMT.inspect(Path(prep["path"]))
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual((rep.summary["versions"], rep.summary["runs"]), (2, 1))
        self.assertNotIn("pkg", json.dumps({k: str(type(app.session_state[k])) for k in ("ar_export",)}))
        self.assertLess(len(json.dumps(prep)), 2000)                        # só metadados na sessão (nunca o pacote)
        botao(app, "ARQUIVAR NESTA INSTALAÇÃO").click().run()
        app = continuar(app, timeout=90)
        _ok(self, app)
        studies = ArchiveStore(self.dir).list_studies()
        self.assertEqual([(s.acquisition, s.scenario_name) for s in studies], [("arquivado", "Experimento C")])
        self.assertIn("Origem: esta microrrede", _html(app))
        self.assertEqual(st.list_runs()[0].state, "concluida")              # rodada original intacta


class ExclusaoTest(_Base):
    def test_dialogo_de_exclusao_aponta_o_arquivo_cientifico_e_mantem_consentimentos(self):
        for p in self._no_engine:
            p.stop()
        reg = MicrogridRegistry(self.dir)
        cfg = v16_equivalent_config("Com estudos")
        reg.create(cfg, origin="commissioning")
        ready(reg.open(cfg["installation"]["uid"]), name="Cenário X")
        with mock.patch.dict(os.environ, {"SEEDS2_DEV_MODE": "1"}):
            app = AppTest.from_file(str(APP_PATH), default_timeout=90)
            app.run()
            botao(app, "Excluir").click().run()
            _ok(self, app)
            txt = _texts(app)
            self.assertIn("EXPORTAR CENÁRIO COMPLETO", txt)
            self.assertIn("não substitui o backup completo da instalação", txt)
            self.assertIn("Para preservar cenários, versões, previsões e rodadas use EXPORTAR CENÁRIO COMPLETO", txt)
            self.assertTrue(any("cenário(s) operativo(s) desta microrrede serão excluídos" in c.label for c in app.checkbox))
            self.assertTrue(botao(app, "EXCLUIR DEFINITIVAMENTE").disabled)


if __name__ == "__main__":
    unittest.main()
