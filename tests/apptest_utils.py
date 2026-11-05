"""Utilitários compartilhados pelos testes de interface (streamlit.testing).

SEEDS2 (Piso 1): o console V1.6 passou a ser exibido na área **Simulação** de uma microrrede já
comissionada. ``abrir`` prepara essa instalação num diretório temporário (``SEEDS2_DATA_DIR``) com o
inventário equivalente à configuração padrão da V1.6 e abre a vista Simulação; as verificações dos
testes V1.6 permanecem as mesmas.

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
_CHAVES_EXTRAS = ("seeds_route", "seeds_last_view", "mg_ack_fp")
_V16_DIR: str | None = None


def instalacao_v16() -> str:
    """Diretório com uma microrrede comissionada equivalente à configuração padrão da V1.6 (criado uma vez)."""
    global _V16_DIR
    if _V16_DIR is None:
        from seeds2.microgrid.store import MicrogridStore
        from seeds2_fixtures import v16_equivalent_config

        _V16_DIR = tempfile.mkdtemp(prefix="seeds2_v16_")
        atexit.register(shutil.rmtree, _V16_DIR, True)
        MicrogridStore(_V16_DIR).save(v16_equivalent_config("Microrrede equivalente V1.6"), 0, origin="commissioning")
    return _V16_DIR


def _todas_as_chaves(app: AppTest) -> list[str]:
    """Chaves do session_state do AppTest (API mudou entre Streamlit 1.49 e 1.66)."""
    ss = app.session_state
    if hasattr(ss, "keys"):
        return [str(k) for k in ss.keys()]
    return [str(k) for k in ss.filtered_state]


def _chaves_de_aplicacao(app: AppTest) -> list[str]:
    chaves = [k for k in _CHAVES_FIXAS if k in app.session_state]
    chaves += [k for k in _todas_as_chaves(app)
               if (k.startswith("orq_") and not k.startswith("orq_nav_")) or k in _CHAVES_EXTRAS]
    return chaves


def abrir(timeout: float = 60, view: str = "simulacao", data_dir: str | None = None) -> AppTest:
    os.environ[ENV] = data_dir or instalacao_v16()
    app = AppTest.from_file(str(APP_PATH), default_timeout=timeout)
    app.session_state["seeds_route"] = {"view": view, "tab": None}
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
