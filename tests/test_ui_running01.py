"""UI-RUNNING-01 — modal de acompanhamento da execução V2 e cancelamento cooperativo.

* O modal só MOSTRA o progresso que o runner já grava (``run.progress``): porcentagem só na fase «missao» com k < n,
  indeterminado nas demais, 100 % só com a rodada concluída (nada estimado).
* Ocultar o painel é estado do navegador; CANCELAR é real: ``integracao_v2.ui.cancelar`` usa a API existente
  ``fail_run(estado='interrompida')`` (transação condicionada a «em execução por este dono»); o runner, inalterado, sai no
  próximo ``beat`` sem gravar nada. Testado com HiGHS real e uma pausa DETERMINÍSTICA entre janelas (só no teste).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

import piso3db_util as P  # noqa: E402
from integracao_v2 import ui as V2UI  # noqa: E402

NO_ADMIN = {"SEEDS2_DEV_MODE": "", "SEEDS2_ADMIN_PASSWORD": ""}


def _run(state="em_execucao", progress=None, error=None, uid="a" * 32):
    return SimpleNamespace(run_uid=uid, state=state, progress=progress, error=error, scenario_version=3,
                           created_at="2026-11-13T10:00:00+00:00", final=state != "em_execucao",
                           manifest={"scenario": {"name": "Dia útil"}, "mission": {"N": 6, "m": 2, "H_L": 12, "delta_min": 60}})


# =========================================================================================== dados do modal (sem navegador)
class DadosDoModalTest(unittest.TestCase):
    def test_progresso_so_dos_contadores_reais(self):
        d = V2UI.dados_modal(_run(progress={"phase": "missao", "k": 3, "n": 12, "janelas": 3}), vivo=True)
        self.assertEqual((d["situacao"], d["determinado"], d["fracao"], d["cancelavel"]), ("andamento", True, 0.25, True))
        self.assertEqual((d["N"], d["m"], d["H_L"], d["cenario"], d["curto"]), (6, 2, 12, "Dia útil", "a" * 8))
        d = V2UI.dados_modal(_run(progress={"phase": "missao", "k": 12, "n": 12, "janelas": 12}), vivo=True)
        self.assertEqual((d["determinado"], d["fracao"]), (False, None))          # todos aplicados ≠ concluída: sem 100 %
        for fase in ("fila", "montagem", "preparando"):
            d = V2UI.dados_modal(_run(progress={"phase": fase}), vivo=True)
            self.assertEqual((d["determinado"], d["fracao"], d["k"], d["n"]), (False, None, None, None), fase)
        d = V2UI.dados_modal(_run(progress=None), vivo=True)
        self.assertEqual((d["fase"], d["determinado"]), ("preparando", False))
        d = V2UI.dados_modal(_run("concluida", {"phase": "concluida"}), vivo=False)
        self.assertEqual((d["situacao"], d["fracao"], d["mensagem"]), ("concluida", 1.0, ""))

    def test_cancelamento_disponivel_so_quando_seguro(self):
        for fase in ("auditoria", "gravando"):
            d = V2UI.dados_modal(_run(progress={"phase": fase}), vivo=True)
            self.assertFalse(d["cancelavel"])
            self.assertIn("auditoria e gravação", d["motivo_cancelamento"])
        d = V2UI.dados_modal(_run(progress={"phase": "missao", "k": 1, "n": 4}), vivo=False)
        self.assertFalse(d["cancelavel"])
        self.assertIn("outro processo", d["motivo_cancelamento"])

    def test_desfechos(self):
        canc = {"kind": V2UI.CANCEL_KIND, "message": "Execução CANCELADA pelo usuário após 2 de 4 intervalo(s)."}
        self.assertEqual(V2UI.dados_modal(_run("interrompida", {"phase": "missao", "k": 2, "n": 4}, canc), vivo=True)["situacao"], "cancelando")
        d = V2UI.dados_modal(_run("interrompida", {"phase": "missao", "k": 2, "n": 4}, canc), vivo=False)
        self.assertEqual((d["situacao"], d["mensagem"]), ("cancelada", canc["message"]))
        d = V2UI.dados_modal(_run("falhou", {"phase": "montagem"}, {"kind": "falha", "message": "RuntimeError: x"}), vivo=False)
        self.assertEqual((d["situacao"], d["titulo_falha"], d["mensagem"]), ("falha", "Falha na execução", "RuntimeError: x"))
        d = V2UI.dados_modal(_run("interrompida", {}, {"kind": "missao_interrompida", "message": "inviável"}), vivo=False)
        self.assertEqual((d["situacao"], d["titulo_falha"]), ("falha", "Missão interrompida"))     # erro ≠ cancelamento


@unittest.skipUnless(P.NODE, "Node.js não instalado")
class ProgressoPuroTest(unittest.TestCase):
    def test_texto_e_porcentagem(self):
        casos = [V2UI.dados_modal(_run(progress={"phase": "missao", "k": 8, "n": 12, "janelas": 8}), vivo=True),
                 V2UI.dados_modal(_run(progress={"phase": "auditoria"}), vivo=True),
                 V2UI.dados_modal(_run("concluida", {"phase": "concluida"}), vivo=False),
                 V2UI.dados_modal(_run("interrompida", {"phase": "missao", "k": 5, "n": 12},
                                       {"kind": V2UI.CANCEL_KIND, "message": "x"}), vivo=False)]
        r = P.node("return Fs.map((d) => api.progressoMx(d));", *casos, componente="execucao", puros="progressoMx")
        self.assertEqual(r[0], {"pct": 66, "rotulo": "Intervalo 8 de 12 · 8 janela(s) resolvida(s)", "largura": 66})
        self.assertEqual(r[1]["pct"], None)
        self.assertEqual(r[1]["largura"], None)                                  # indeterminado: nenhuma barra «cheia»
        self.assertEqual(r[2]["largura"], 100)
        self.assertEqual(r[3], {"pct": None, "rotulo": "Parou em 5 de 12 intervalos", "largura": None})


@unittest.skipUnless(P.NODE and P.navegador_disponivel(), "Chromium/Playwright (Node) não instalados")
class ModalNoNavegadorTest(unittest.TestCase):
    """Componente REAL na bancada (dados de TESTE montados por ``dados_modal``; nenhum progresso simulado na aplicação)."""

    def test_dialogo_acessivel_ocultar_reabrir_e_confirmar_cancelamento(self):
        d = V2UI.dados_modal(_run(progress={"phase": "missao", "k": 8, "n": 12, "janelas": 8}), vivo=True)
        passos = [["texto", "t"],
                  ["avaliar", "dlg", "(() => { const c = document.querySelector('.pt.mx .mx-card'); return [c.getAttribute('role'), c.getAttribute('aria-modal'), "
                                     "c.getAttribute('aria-labelledby'), document.querySelector('.pt.mx .mx-barra').getAttribute('aria-valuenow'), "
                                     "!document.querySelector('.pt.mx .mx-fundo').hidden]; })()"],
                  ["clicar", ".pt.mx .mx-acoes .mx-perigo"], ["avaliar", "conf", "document.querySelector('.pt.mx .mx-acoes').textContent"],
                  ["clicar", ".pt.mx .mx-acoes .mx-perigo.on"], ["avaliar", "acoes", "window.__acoes.map((a) => [a.type, a.run])"],
                  ["avaliar", "oculta", "(document.querySelector('.pt.mx .mx-acoes .mx-pri').click(), [document.querySelector('.pt.mx .mx-fundo').hidden, "
                                        "document.querySelector('.pt.mx .mx-faixa').hidden, sessionStorage.getItem('seeds2.execucao.oculto.' + 'a'.repeat(32))])"],
                  ["avaliar", "reabre", "(document.querySelector('.pt.mx .mx-reabrir').click(), document.querySelector('.pt.mx .mx-fundo').hidden)"],
                  ["avaliar", "esc", "(document.querySelector('.pt.mx .mx-card').dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })), "
                                     "document.querySelector('.pt.mx .mx-fundo').hidden)"],
                  ["avaliar", "svg", "[document.querySelectorAll('.pt.mx .mx-svg .mx-no').length, document.querySelector('.pt.mx .mx-svg').getAttribute('aria-hidden')]"]]
        r = P.bancada({"m": d}, passos=passos, componente="execucao")["m"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        for t in ("SEEDS2", "RUNNING SIMULATION", "Simulação em andamento", "Dia útil · versão 3", "Intervalo 8 de 12", "66 %",
                  "OCULTAR PAINEL", "CANCELAR EXECUÇÃO", "N = 6 · m = 2 · H_L = 12", "continua no servidor"):
            self.assertIn(t, v["t"])
        self.assertEqual(v["dlg"], ["dialog", "true", "mx-titulo", "66", True])
        self.assertIn("Cancelar esta rodada?", v["conf"])                         # confirmação explícita antes do pedido
        self.assertEqual(v["acoes"], [["cancelar", "a" * 32]])                    # o servidor decide; nada é simulado aqui
        self.assertEqual(v["oculta"], [True, False, "andamento"])                 # ocultar ≠ cancelar: nenhuma ação enviada
        self.assertFalse(v["reabre"])
        self.assertTrue(v["esc"])                                                 # Escape oculta (nunca cancela)
        self.assertEqual(v["svg"], [5, "true"])                                   # animação decorativa, fora da leitura

    def test_estados_finais_e_indisponibilidade(self):
        canc = V2UI.dados_modal(_run("interrompida", {"phase": "missao", "k": 5, "n": 12},
                                     {"kind": V2UI.CANCEL_KIND, "message": "Execução CANCELADA pelo usuário após 5 de 12."}), vivo=False)
        falha = V2UI.dados_modal(_run("falhou", {"phase": "montagem"}, {"kind": "falha", "message": "RuntimeError: contrato inválido"}), vivo=False)
        tarde = V2UI.dados_modal(_run(progress={"phase": "auditoria"}), vivo=True)
        fim = V2UI.dados_modal(_run("concluida", {"phase": "concluida"}), vivo=False)
        pega = "[document.querySelector('.pt.mx .mx-titulo').textContent, [...document.querySelectorAll('.pt.mx .mx-acoes button')].map((b) => b.textContent + (b.disabled ? ':off' : '')), " \
               "document.querySelector('.pt.mx .mx-barra').className, document.querySelector('.pt.mx').classList.contains('parado')]"
        r = P.bancada({"canc": canc, "falha": falha, "tarde": tarde, "fim": fim},
                      passos=[["texto", "t"], ["avaliar", "x", pega]], componente="execucao")
        self.assertEqual(r["canc"]["vistas"]["x"][:2], ["Cancelada", ["FECHAR", "VER DIAGNÓSTICO"]])
        self.assertIn("Execução CANCELADA pelo usuário", r["canc"]["vistas"]["t"])
        self.assertIn("Parou em 5 de 12 intervalos", r["canc"]["vistas"]["t"])
        self.assertTrue(r["canc"]["vistas"]["x"][3])                              # animação parada fora de andamento
        self.assertEqual(r["falha"]["vistas"]["x"][0], "Falha na execução")
        self.assertIn("RuntimeError: contrato inválido", r["falha"]["vistas"]["t"])
        self.assertEqual(r["tarde"]["vistas"]["x"][1], ["OCULTAR PAINEL", "CANCELAR EXECUÇÃO:off"])
        self.assertIn("indet", r["tarde"]["vistas"]["x"][2])                      # sem porcentagem fora da fase «missao»
        self.assertIn("auditoria e gravação em andamento", r["tarde"]["vistas"]["t"])
        self.assertEqual(r["fim"]["vistas"]["x"][0], "Concluída")
        for k in ("canc", "falha", "tarde", "fim"):
            self.assertEqual(r[k]["erros"], [], k)


# =========================================================================================== cancelamento real (HiGHS)
@unittest.skipUnless(P.SOLVER, "Pyomo/HiGHS não instalados")
class CancelamentoRealTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _cenario(self, nome):
        import piso3da_util as U
        uid, st = P._abrir(self.dir, U.config_bateria(nome))
        return uid, st, U.criar_cenario_v2(st, soc0=50.0, horas=24, N=4, m=2, H_L=8, tarifa=[0.5] * 16 + [1.5] * 4 + [0.5] * 4)

    def test_cancelar_entre_janelas_encerra_sem_gravar_e_libera_a_microrrede(self):
        from integracao_v2 import execucao as X
        from seeds2.operation import runner

        uid, st, sc = self._cenario("Cancelamento (teste)")
        pausa, liberar = threading.Event(), threading.Event()
        original = X.executar_janela_a_janela

        def pausado(ctrl, entorno, ao_avancar=None):                     # SÓ NO TESTE: pausa determinística após a 2ª janela
            def avancar():
                ao_avancar()
                if len(ctrl.registros) == 2:
                    pausa.set()
                    liberar.wait(60)
            return original(ctrl, entorno, avancar)
        with mock.patch.object(X, "executar_janela_a_janela", pausado):
            run = X.submit(st, sc.scenario_uid, sc.version, X.new_request_id(), background=True)
            self.assertTrue(pausa.wait(240))
            vivo = st.get_run(run.run_uid)
            self.assertEqual((vivo.state, vivo.progress["phase"], vivo.progress["k"]), ("em_execucao", "missao", 4))
            sit, msg = V2UI.cancelar(st, run.run_uid)
            self.assertEqual(sit, "solicitado", msg)
            r = st.get_run(run.run_uid)
            self.assertEqual((r.state, r.error["kind"]), ("interrompida", V2UI.CANCEL_KIND))
            self.assertIn("após 4 de 24 intervalo(s)", r.error["message"])   # 24 intervalos, 12 janelas (m = 2)
            self.assertTrue(runner.is_running_here(run.run_uid))           # a janela em curso ainda termina no solver…
            self.assertEqual(V2UI.dados_modal(r, vivo=True)["situacao"], "cancelando")
            liberar.set()
            self.assertTrue(runner.wait(run.run_uid, 240))                 # …e a thread sai no próximo beat
        r = st.get_run(run.run_uid)
        self.assertEqual((r.state, r.data, r.summary), ("interrompida", {}, None))   # nada gravado como resultado
        self.assertEqual(r.error["kind"], V2UI.CANCEL_KIND)                 # o runner não sobrescreveu o desfecho
        self.assertEqual(V2UI.dados_modal(r, vivo=False)["situacao"], "cancelada")
        self.assertEqual(V2UI.cancelar(st, run.run_uid)[0], "finalizada")   # pedido repetido: nada muda
        # a microrrede fica livre e uma nova rodada conclui normalmente (nenhuma reexecução automática da cancelada)
        nova = X.submit(st, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
        self.assertEqual(nova.state, "concluida", nova.error)
        self.assertEqual(sorted(x.state for x in st.list_runs()), ["concluida", "interrompida"])

    def test_cancelar_recusa_rodada_concluida_de_outro_processo_ou_na_gravacao(self):
        uid, st, sc = self._cenario("Recusas (teste)")
        from integracao_v2 import execucao as X
        run = X.submit(st, sc.scenario_uid, sc.version, X.new_request_id(), background=False)
        self.assertEqual(run.state, "concluida")
        self.assertEqual(V2UI.cancelar(st, run.run_uid)[0], "finalizada")
        self.assertEqual(st.get_run(run.run_uid).state, "concluida")         # a rodada concluída fica intacta
        self.assertEqual(V2UI.cancelar(st, "f" * 32)[0], "inexistente")
        falso = SimpleNamespace(run_uid="b" * 32, state="em_execucao", progress={"phase": "gravando"})
        with mock.patch.object(st, "get_run", return_value=falso), mock.patch.object(X, "is_running_here", return_value=True), \
                mock.patch.object(st, "fail_run", side_effect=AssertionError("não deveria gravar")):
            self.assertEqual(V2UI.cancelar(st, "b" * 32)[0], "tarde")
        falso.progress = {"phase": "missao", "k": 1, "n": 4}
        with mock.patch.object(st, "get_run", return_value=falso), mock.patch.object(X, "is_running_here", return_value=False), \
                mock.patch.object(st, "fail_run", side_effect=AssertionError("não deveria gravar")):
            self.assertEqual(V2UI.cancelar(st, "b" * 32)[0], "outro_processo")


# =========================================================================================== interface (AppTest)
@unittest.skipIf(AppTest is None, "Streamlit não instalado")
class DesfechoNaPaginaTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        os.environ["SEEDS2_DATA_DIR"] = self.dir
        self._env = mock.patch.dict(os.environ, NO_ADMIN)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def test_falha_acompanhada_fica_visivel_ate_ser_dispensada(self):
        import piso3da_util as U
        from apptest_utils import APP_PATH
        from integracao_v2 import execucao as X
        from seeds2.microgrid.registry import MicrogridRegistry

        cfg = U.config_bateria("Desfecho (teste)")
        MicrogridRegistry(self.dir).create(cfg)
        uid = cfg["installation"]["uid"]
        st = MicrogridRegistry(self.dir).open(uid)
        sc = U.criar_cenario_v2(st)
        # rodada V2 que FALHOU, gravada pela API do armazenamento exatamente como o runner a grava (dados de teste)
        run, _ = st.start_run(run_uid="c" * 32, request_id="pedido-teste-01", scenario_uid=sc.scenario_uid,
                              scenario_version=sc.version, scenario_fingerprint=sc.fingerprint,
                              manifest={"engine": {"id": "milp_mpc_v1"}, "scenario": {"name": sc.name}}, owner=X.OWNER)
        st.fail_run(run.run_uid, X.OWNER, {"kind": "falha", "message": "RuntimeError: falha de teste na montagem"})

        def sessao():
            os.environ["SEEDS2_DATA_DIR"] = self.dir
            app = AppTest.from_file(str(APP_PATH), default_timeout=240)
            app.session_state["mg_active_uid"] = uid
            app.session_state["seeds_route"] = {"view": "operacao", "tab": "execucao"}
            app.session_state[V2UI.SEGUIR] = "c" * 32
            app.query_params["sc"] = sc.scenario_uid
            return app
        app = sessao()
        app.run()
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        html = "\n".join(h.proto.body for h in app.get("html"))
        self.assertIn("Falha na execução · rodada cccccccc", html)
        self.assertIn("RuntimeError: falha de teste na montagem", html)
        self.assertEqual(app.session_state[V2UI.SEGUIR], "c" * 32)                 # nada é dispensado sozinho
        ok = next(b for b in app.button if b.key == f"op_v2_ok_btn_{'c' * 32}")
        ok.click().run()
        self.assertNotIn(V2UI.SEGUIR, app.session_state)
        self.assertEqual(st.get_run("c" * 32).state, "falhou")                    # a interface não altera o desfecho
        # sessão sem acompanhamento (recarga em outra aba): nenhum desfecho antigo aparece
        app = sessao()
        app.session_state[V2UI.SEGUIR] = None
        app.run()
        self.assertNotIn("Falha na execução · rodada", "\n".join(h.proto.body for h in app.get("html")))


if __name__ == "__main__":
    unittest.main()
