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
# A Partitura usa a largura da janela; o restante da aplicação mantém a largura de leitura do shell.
WIDE_CSS = ("<style>.block-container { max-width: none !important; padding-left: 1.4rem !important; "
            "padding-right: 1.4rem !important; }</style>")


def _src(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def component():
    """Componente v2 (registrar a cada execução é inócuo, como em ``shell.component``)."""
    return st.components.v2.component("seeds_partitura", js=_src("trama.js") + "\n" + _src("partitura.js"),
                                      css=_src("trama.css"))


def partitura(frame: dict, *, key: str, wide: bool = True) -> None:
    """Desenha o instrumento Partitura de UMA rodada a partir do marco ``frame`` (somente leitura)."""
    if not isinstance(frame, dict) or frame.get("formato") != FRAME_FORMAT:
        raise ValueError("Marco de dados inválido para a Partitura.")
    if wide:
        st.html(WIDE_CSS)
    component()(key=key, data={"frame": frame})


__all__ = ["FRAME_FORMAT", "component", "partitura"]
