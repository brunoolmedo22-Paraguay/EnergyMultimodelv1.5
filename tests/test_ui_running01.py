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


    # ----------------------------------------------------------------- revisão do PR #27: visibilidade COMPUTADA e recusas
    # Re-montar o componente com novos dados = o ciclo do fragmento (1 s) no Streamlit; a resposta do servidor ao pedido
    # de cancelamento chega do mesmo jeito (``resposta_cancelamento``). Tudo aqui são dados de TESTE.
    _JS_UTIL = ("window.__vis = () => ['.mx-fundo', '.mx-faixa'].map((s) => { const e = document.querySelector('.pt.mx ' + s), "
                "r = e.getBoundingClientRect(); return [e.hidden, getComputedStyle(e).display, r.width > 0 && r.height > 0]; }); "
                "window.__rem = (mud) => window.__monta({ data: Object.assign({}, window.__D, mud), parentElement: document.getElementById('raiz'), "
                "setTriggerValue: (k, v) => window.__acoes.push(v) }); "
                "window.__btns = () => [...document.querySelectorAll('.pt.mx .mx-acoes button')].map((b) => b.textContent + (b.disabled ? ':off' : '')); "
                "window.__msg = () => { const m = document.querySelector('.pt.mx .mx-msg'); return [m.hidden || getComputedStyle(m).display === 'none' ? '' : m.textContent, m.dataset.recusa || null]; }; true")

    def test_visibilidade_computada_em_todos_os_fluxos(self):
        """``hidden`` tem de valer na TELA (display e caixa), não só no atributo — inclusive sem a regra geral
        ``.pt [hidden]`` (a regra explícita do modal basta sozinha)."""
        d = V2UI.dados_modal(_run(progress={"phase": "missao", "k": 8, "n": 12, "janelas": 8}), vivo=True)
        canc = V2UI.dados_modal(_run("interrompida", {"phase": "missao", "k": 9, "n": 12},
                                     {"kind": V2UI.CANCEL_KIND, "message": "Execução CANCELADA pelo usuário após 9 de 12."}), vivo=False)
        sem_geral = ("(() => { for (const sh of document.styleSheets) for (let i = sh.cssRules.length - 1; i >= 0; i--) "
                     "if (sh.cssRules[i].selectorText === '.pt [hidden]') sh.deleteRule(i); "
                     "return [...document.styleSheets].some((sh) => [...sh.cssRules].some((r) => r.selectorText === '.pt [hidden]')); })()")
        ABERTO, OCULTO = [[False, "grid", True], [True, "none", False]], [[True, "none", False], [False, "flex", True]]
        for nome, remover in (("com_regra_geral", False), ("so_regra_do_modal", True)):
            passos = [["avaliar", "u", self._JS_UTIL]] + ([["avaliar", "geral", sem_geral]] if remover else []) + [
                ["avaliar", "aberto", "window.__vis()"],
                ["clicar", ".pt.mx .mx-acoes .mx-pri"], ["avaliar", "ocultar", "window.__vis()"],
                ["avaliar", "ciclo_oculto", "(window.__rem({ k: 9, janelas: 9, fracao: 0.75 }), window.__vis())"],   # fragmento atualiza: segue oculto
                ["clicar", ".pt.mx .mx-reabrir"], ["avaliar", "reabrir", "window.__vis()"],
                ["tecla", "Escape"], ["avaliar", "escape", "window.__vis()"],
                ["clicar", ".pt.mx .mx-reabrir"], ["clicarEm", ".pt.mx .mx-fundo", [0.02, 0.02]], ["avaliar", "fora", "window.__vis()"],
                ["avaliar", "desfecho", "(window.__rem(" + json.dumps(canc) + "), window.__vis())"],                 # desfecho reabre
                ["avaliar", "acoes", "window.__acoes.length"]]
            r = P.bancada({"m": d}, passos=passos, componente="execucao")["m"]
            self.assertEqual(r["erros"], [], nome)
            v = r["vistas"]
            if remover:
                self.assertFalse(v["geral"], "a regra geral deveria ter sido removida neste cenário")
            self.assertEqual(v["aberto"], ABERTO, nome)
            for k in ("ocultar", "ciclo_oculto", "escape", "fora"):
                self.assertEqual(v[k], OCULTO, f"{nome}: {k}")
            self.assertEqual(v["reabrir"], ABERTO, nome)
            self.assertEqual(v["desfecho"], ABERTO, nome)
            self.assertEqual(v["acoes"], 0, nome)                                 # ocultar/Escape/fora/reabrir: nenhuma ação ao servidor

    def test_pedido_recusado_pelo_servidor_volta_ao_estado_real(self):
        d = V2UI.dados_modal(_run(progress={"phase": "missao", "k": 8, "n": 12, "janelas": 8}), vivo=True)
        resp = lambda situ, pedido="window.__acoes.at(-1).t": (  # noqa: E731
            "(window.__rem({ resposta_cancelamento: { pedido: " + pedido + ", situacao: '" + situ + "', mensagem: 'Motivo do servidor: " + situ + "' } }), "
            "[window.__btns(), window.__msg()])")
        tarde = "(window.__rem({ fase: 'auditoria', fase_rotulo: 'Auditoria', determinado: false, fracao: null, cancelavel: false, " \
                "motivo_cancelamento: 'auditoria e gravação em andamento', resposta_cancelamento: { pedido: window.__acoes.at(-1).t, situacao: 'tarde', " \
                "mensagem: 'A missão já terminou e a auditoria/gravação atômica está em andamento.' } }), [window.__btns(), window.__msg()])"
        passos = [["avaliar", "u", self._JS_UTIL],
                  ["clicar", ".pt.mx .mx-acoes .mx-perigo"],
                  ["avaliar", "duplo", "(() => { const b = document.querySelector('.pt.mx .mx-acoes .mx-perigo.on'); b.click(); b.click(); "
                                       "return [window.__acoes.length, window.__btns()]; })()"],                          # um pedido só
                  ["avaliar", "alheia", resp("tarde", "123")],                                 # resposta de OUTRO pedido: ignorada
                  ["avaliar", "ciclo", "(window.__rem({ k: 9, janelas: 9 }), window.__btns())"],  # ciclos sem resposta: pendente
                  ["avaliar", "recusa", resp("outro_processo")],
                  ["avaliar", "ciclo2", "(window.__rem({ k: 10, janelas: 10 }), [window.__btns(), window.__msg()])"],
                  # novo pedido, recusado por «tarde» (o servidor também passa a desabilitar o botão)
                  ["clicar", ".pt.mx .mx-acoes .mx-perigo"], ["avaliar", "limpa", "window.__msg()"],
                  ["clicar", ".pt.mx .mx-acoes .mx-perigo.on"], ["avaliar", "tarde", tarde],
                  ["avaliar", "n", "window.__acoes.map((a) => a.type)"]]
        r = P.bancada({"m": d}, passos=passos, componente="execucao")["m"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        self.assertEqual(v["duplo"], [1, ["OCULTAR PAINEL", "CANCELAMENTO SOLICITADO…:off"]])
        self.assertEqual(v["alheia"][0], ["OCULTAR PAINEL", "CANCELAMENTO SOLICITADO…:off"])
        self.assertEqual(v["ciclo"], ["OCULTAR PAINEL", "CANCELAMENTO SOLICITADO…:off"])
        self.assertEqual(v["recusa"][0], ["OCULTAR PAINEL", "CANCELAR EXECUÇÃO"])        # pendente limpo: nada foi cancelado
        self.assertEqual(v["recusa"][1], ["Cancelamento NÃO realizado — Motivo do servidor: outro_processo", "outro_processo"])
        self.assertEqual(v["ciclo2"][1][1], "outro_processo")                           # a justificativa permanece nos ciclos seguintes
        self.assertEqual(v["limpa"], ["", None])                                         # nova tentativa: confirmação de novo
        self.assertEqual(v["tarde"][0], ["OCULTAR PAINEL", "CANCELAR EXECUÇÃO:off"])
        self.assertIn("Cancelamento NÃO realizado — A missão já terminou", v["tarde"][1][0])
        self.assertEqual(v["n"], ["cancelar", "cancelar"])

    def test_pedido_aceito_e_pedido_sem_resposta(self):
        d = V2UI.dados_modal(_run(progress={"phase": "missao", "k": 8, "n": 12, "janelas": 8}), vivo=True)
        canc = V2UI.dados_modal(_run("interrompida", {"phase": "missao", "k": 8, "n": 12},
                                     {"kind": V2UI.CANCEL_KIND, "message": "Execução CANCELADA pelo usuário após 8 de 12."}), vivo=True)
        aceito = ("(window.__rem(Object.assign(" + json.dumps(canc) + ", { resposta_cancelamento: { pedido: window.__acoes.at(-1).t, "
                  "situacao: 'solicitado', mensagem: 'ok' } })), [document.querySelector('.pt.mx .mx-titulo').textContent, window.__btns()])")
        passos = [["avaliar", "u", self._JS_UTIL],
                  ["clicar", ".pt.mx .mx-acoes .mx-perigo"], ["clicar", ".pt.mx .mx-acoes .mx-perigo.on"],
                  ["avaliar", "espera", "new Promise((ok) => setTimeout(() => ok([window.__btns(), window.__msg()]), 21000))"],
                  ["clicar", ".pt.mx .mx-acoes .mx-perigo"], ["clicar", ".pt.mx .mx-acoes .mx-perigo.on"],
                  ["avaliar", "aceito", aceito]]
        r = P.bancada({"m": d}, passos=passos, componente="execucao")["m"]
        self.assertEqual(r["erros"], [])
        v = r["vistas"]
        self.assertEqual(v["espera"][0], ["OCULTAR PAINEL", "CANCELAR EXECUÇÃO"])         # sem resposta: não fica «solicitado» para sempre
        self.assertEqual(v["espera"][1][1], "sem_resposta")
        self.assertIn("nada indica que a rodada tenha sido cancelada", v["espera"][1][0])
        self.assertEqual(v["aceito"][0], "Cancelamento solicitado")                     # aceito: o estado GRAVADO decide
        self.assertEqual(v["aceito"][1], ["FECHAR", "VER DIAGNÓSTICO:off"])


class RespostaDoServidorTest(unittest.TestCase):
    """``_acao_modal`` grava a resposta REAL de ``cancelar`` vinculada ao pedido do navegador; ``acompanhar`` a entrega."""

    def test_resposta_vinculada_ao_pedido(self):
        ss = {}
        acao = {"type": "cancelar", "run": "a" * 32, "t": 1731500000123}
        with mock.patch.object(V2UI, "_ss", return_value=ss), mock.patch.object(V2UI.shell, "payload", return_value=acao), \
                mock.patch.object(V2UI, "cancelar", return_value=("tarde", "auditoria em andamento")) as canc:
            V2UI._acao_modal(object(), lambda uid: None)
        canc.assert_called_once()
        self.assertEqual(ss[V2UI.RESPOSTA_CANCEL + "a" * 32],
                         {"pedido": 1731500000123, "situacao": "tarde", "mensagem": "auditoria em andamento"})
        self.assertNotIn(V2UI.RERUN_APP, ss)                                      # cancelar não muda a página

    def test_fechar_e_diagnostico_pedem_rerun_da_pagina(self):
        """``st.rerun`` não tem efeito num callback de componente: FECHAR/VER DIAGNÓSTICO marcam ``RERUN_APP`` e o
        próximo ciclo do fragmento (``acompanhar``) o executa — como o «OK» da página."""
        for tipo in ("fechar", "diagnostico"):
            ss, abertas = {V2UI.SEGUIR: "a" * 32}, []
            with mock.patch.object(V2UI, "_ss", return_value=ss), \
                    mock.patch.object(V2UI.shell, "payload", return_value={"type": tipo, "run": "a" * 32, "t": 1}):
                V2UI._acao_modal(object(), abertas.append)
            self.assertTrue(ss.get(V2UI.RERUN_APP), tipo)
            self.assertNotIn(V2UI.SEGUIR, ss, tipo)
            self.assertEqual(abertas, ["a" * 32] if tipo == "diagnostico" else [], tipo)
            self.assertEqual(ss.get(f"op_v2_ok_{'a' * 32}"), True if tipo == "fechar" else None, tipo)
        ss = {V2UI.RERUN_APP: True}
        with mock.patch.object(V2UI, "_ss", return_value=ss), mock.patch.object(V2UI.st, "rerun", side_effect=RuntimeError("rerun")) as rr:
            with self.assertRaisesRegex(RuntimeError, "rerun"):
                V2UI.acompanhar(object(), _run(progress={"phase": "missao", "k": 1, "n": 12}), open_run=lambda u: None, vivo=True)
        rr.assert_called_once_with(scope="app")
        self.assertNotIn(V2UI.RERUN_APP, ss)                                      # uma vez só

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
