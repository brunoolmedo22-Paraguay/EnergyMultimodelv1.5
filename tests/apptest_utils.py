"""Utilitários compartilhados pelos testes de interface (streamlit.testing).

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

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

# Chaves de estado da aplicação (não de widgets) que definem a navegação e a
# rodada integrada do Orchestrator V1.6.
_CHAVES_FIXAS = ("energy_source", "current_page", "orchestrator_page")


def _chaves_de_aplicacao(app: AppTest) -> list[str]:
    chaves = [k for k in _CHAVES_FIXAS if k in app.session_state]
    chaves += [k for k in app.session_state.filtered_state
               if k.startswith("orq_") and not k.startswith("orq_nav_")]
    return chaves


def abrir(timeout: float = 60) -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=timeout).run()


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
