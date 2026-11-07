"""Utilitários compartilhados pelos testes de interface (streamlit.testing).

SEEDS2: o console V1.6 é exibido na área **Simulação** de uma microrrede comissionada e ABERTA na sessão
(Gestor de microrredes). ``abrir`` prepara essa microrrede no catálogo de um diretório temporário
(``SEEDS2_DATA_DIR``) com o inventário equivalente à configuração padrão da V1.6, abre-a na sessão (equivale a
"ABRIR MICRORREDE" no Gestor) e mostra a vista Simulação; as verificações dos testes V1.6 permanecem as mesmas.

Limitação conhecida do ``AppTest``: quando um clique dispara ``st.rerun()``, a
árvore resultante mistura os elementos da execução final com elementos
obsoletos da execução abortada. Esses widgets obsoletos não têm mais estado e
fazem o próximo ``.run()`` falhar com ``KeyError: st.session_state has no key
"$$ID-..."``. Não é um defeito da aplicação: no navegador o frontend descarta
esses elementos.

``continuar`` contorna isso de forma transparente: abre uma sessão nova do
``app.py`` com o estado de aplicação produzido pela interação anterior (sem
estados de widgets) e a executa. Assim, as verificações seguintes olham apenas
para o que a interface realmente renderiza naquele estado.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
ENV = "SEEDS2_DATA_DIR"

# Chaves de estado da aplicação (não de widgets) que definem a navegação e a
# rodada integrada do Orchestrator V1.6.
_CHAVES_FIXAS = ("energy_source", "current_page", "orchestrator_page")
# Estado de navegação do shell SEEDS2 (não são widgets).
_CHAVES_EXTRAS = ("seeds_route", "seeds_last_view", "mg_ack_fp", "mg_active_uid", "mg_creating", "seeds_url_checked",
                  # Centro de Operação (Piso 2A): cenário selecionado e cópia de trabalho (estado de aplicação)
                  "op_scenario_uid", "op_work", "op_work_uid", "op_base_version", "op_base_fp", "op_token",
                  "op_conflict", "op_stale", "op_form", "op_flash", "op_url_checked",
                  # Previsões (Piso 2B): dados pendentes ainda não gravados (estado de aplicação)
                  "op_blobs",
                  # Execução (Piso 2C): rodada aberta (estado de aplicação)
                  "op_run_uid")
# Previsões (Piso 2B): estado de aplicação por slot (tabela manual, CSV enviado, token do editor, verificação) e a
# fonte escolhida e a aba ativa (chaves fixas — valores transportáveis entre execuções).
_PREFIXOS_EXTRAS = ("op_fcs_", "opw_fc_src_", "opw_fc_tab",
                    "op_ex_")      # Piso 2C: cache do preflight e pedido de execução pendente (estado de aplicação)
_V16_DIR: str | None = None
_V16_UID: str | None = None


def instalacao_v16() -> str:
    """Diretório com um catálogo contendo UMA microrrede comissionada equivalente à configuração padrão da V1.6
    (criado uma vez)."""
    global _V16_DIR, _V16_UID
    if _V16_DIR is None:
        from seeds2.microgrid.registry import MicrogridRegistry
        from seeds2_fixtures import v16_equivalent_config

        _V16_DIR = tempfile.mkdtemp(prefix="seeds2_v16_")
        atexit.register(shutil.rmtree, _V16_DIR, True)
        cfg = v16_equivalent_config("Microrrede equivalente V1.6")
        MicrogridRegistry(_V16_DIR).create(cfg, origin="commissioning")
        _V16_UID = cfg["installation"]["uid"]
    return _V16_DIR


def uid_v16() -> str:
    instalacao_v16()
    return _V16_UID


def _todas_as_chaves(app: AppTest) -> list[str]:
    """Chaves do session_state do AppTest (API mudou entre Streamlit 1.49 e 1.66)."""
    ss = app.session_state
    if hasattr(ss, "keys"):
        return [str(k) for k in ss.keys()]
    return [str(k) for k in ss.filtered_state]


def _chaves_de_aplicacao(app: AppTest) -> list[str]:
    chaves = [k for k in _CHAVES_FIXAS if k in app.session_state]
    chaves += [k for k in _todas_as_chaves(app)
               if (k.startswith("orq_") and not k.startswith("orq_nav_")) or k in _CHAVES_EXTRAS
               or k.startswith(_PREFIXOS_EXTRAS)]
    return chaves


def abrir(timeout: float = 60, view: str = "simulacao", data_dir: str | None = None, uid: str | None = None) -> AppTest:
    os.environ[ENV] = data_dir or instalacao_v16()
    app = AppTest.from_file(str(APP_PATH), default_timeout=timeout)
    app.session_state["seeds_route"] = {"view": view, "tab": None}
    app.session_state["mg_active_uid"] = uid or uid_v16()          # microrrede aberta nesta sessão
    return app.run()


def continuar(app: AppTest, timeout: float = 60) -> AppTest:
    novo = AppTest.from_file(str(APP_PATH), default_timeout=timeout)
    for chave in _chaves_de_aplicacao(app):
        novo.session_state[chave] = app.session_state[chave]
    return novo.run()


def botao(app: AppTest, rotulo: str):
    """Retorna o botão com rótulo exato; falha com mensagem clara se ausente."""
    for b in app.button:
        if b.label == rotulo:
            return b
    raise AssertionError(f"Botão {rotulo!r} não encontrado. Disponíveis: {[b.label for b in app.button]}")
