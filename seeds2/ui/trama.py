"""Motor gráfico TRAMA e instrumento PARTITURA (Piso 3D-B0) — componente v2 local do SEEDS2.

* ``static/trama/trama.js``      — motor de raias temporais em SVG (uma malha, várias raias, um cursor; sem dependências);
* ``static/trama/partitura.js``  — instrumento de rodada (lente Operação, inspetor, explorador de recursos);
* ``static/trama/trama.css``     — estilos, todos sob ``.pt`` (o componente usa o isolamento de estilos padrão do
  ``st.components.v2``: nenhuma regra alcança o restante da aplicação).

O componente só recebe o marco de dados ``seeds2-trama-frame`` (montado pela camada de integração a partir dos dados
PERSISTIDOS da rodada) e não devolve nada ao Python: cursor, fixação, foco, zoom e painéis são estado do navegador, logo
não provocam reruns. Reexecutar o script com o mesmo marco (mesmo ``hash``) não redesenha nada.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

STATIC = Path(__file__).resolve().parent / "static" / "trama"
FRAME_FORMAT = "seeds2-trama-frame"
# A Partitura usa a largura da janela; o restante da aplicação mantém a largura de leitura do shell. ``--seeds-rail`` é a
# largura do trilho da barra lateral (0 quando ela não está na página ou em telas estreitas).
WIDE_CSS = ("<style>.block-container { max-width: none !important; padding-left: calc(var(--seeds-rail, 0px) + 1.4rem) "
            "!important; padding-right: 1.4rem !important; }</style>")
# Barra lateral (Piso 3D-B2-A): o trilho é fixo; o conteúdo da página desloca-se a largura dele. Em telas estreitas vira uma
# barra inferior e o conteúdo ganha espaço embaixo. O invólucro do componente não ocupa lugar no fluxo da página.
RAIL_CSS = ("<style>:root { --seeds-rail: 56px; } .block-container { padding-left: calc(var(--seeds-rail) + 1.6rem) !important; }"
            " .st-key-seeds_sidebar { position: absolute; width: 0; height: 0; }"
            " @media (max-width: 760px) { :root { --seeds-rail: 0px; } .block-container { padding-left: 1rem !important; "
            "padding-bottom: 6.5rem !important; } }</style>")


def _src(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def component():
    """Componente v2 (registrar a cada execução é inócuo, como em ``shell.component``)."""
    return st.components.v2.component("seeds_partitura", js=_src("trama.js") + "\n" + _src("partitura.js"),
                                      css=_src("trama.css"))


def _pagina(nome: str):
    """Componente v2 de PÁGINA na linguagem Partitura: motor Trama + ``<nome>.js``, estilos de ``trama.css`` (sob ``.pt``)."""
    return st.components.v2.component(f"seeds_{nome}", js=_src("trama.js") + "\n" + _src(f"{nome}.js"), css=_src("trama.css"))


def sidebar(dados: dict, *, on_action) -> None:
    """Barra lateral da plataforma (só navegação; os destinos são decididos pelo shell)."""
    st.html(RAIL_CSS)
    _pagina("sidebar")(key="seeds_sidebar", data=dados, on_action_change=on_action)


def pagina(nome: str, dados: dict, *, key: str, on_action=None, wide: bool = True) -> None:
    """Componente de página (Planta, Catálogo, Caderno, Folha) com os dados já montados pelo chamador."""
    if wide:
        st.html(WIDE_CSS)
    _pagina(nome)(key=key, data=dados, **({"on_action_change": on_action} if on_action else {}))


def partitura(frame: dict, *, key: str, wide: bool = True) -> None:
    """Desenha o instrumento Partitura de UMA rodada a partir do marco ``frame`` (somente leitura)."""
    if not isinstance(frame, dict) or frame.get("formato") != FRAME_FORMAT:
        raise ValueError("Marco de dados inválido para a Partitura.")
    if wide:
        st.html(WIDE_CSS)
    component()(key=key, data={"frame": frame})


__all__ = ["FRAME_FORMAT", "component", "pagina", "partitura", "sidebar"]
