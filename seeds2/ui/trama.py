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


# UI-REDESIGN-01 — identidade das tecnologias REUTILIZADA do Gestor (sem cópia nem alteração dele): os ícones são o objeto
# ``ICONS`` de ``static/inventory.js`` (o mesmo de ``techpicker.js``) e as cores, os tokens ``--k-*`` de ``static/kit.css``.
# Lidos a cada registro do componente, ficam sempre iguais aos do Gestor.
def _trecho(texto: str, inicio: str, fim: str, origem: str) -> str:
    i = texto.find(inicio)
    j = texto.find(fim, i + len(inicio)) if i >= 0 else -1
    if i < 0 or j < 0:
        raise RuntimeError(f"Identidade do Gestor não encontrada em {origem}")
    return texto[i + len(inicio):j]


def icones_gestor_js() -> str:
    """``const ICONES_GESTOR = {pv, wind, battery, pemfc, thermal}`` — SVG do Gestor (``inventory.js``)."""
    corpo = _trecho((STATIC.parent / "inventory.js").read_text(encoding="utf-8"), "const ICONS = {", "\n};", "static/inventory.js")
    return "const ICONES_GESTOR = {" + corpo + "\n};"


def tokens_gestor_css() -> str:
    """Cores das tecnologias do Gestor (``--k-pv`` … ``--k-load`` de ``kit.css``) disponíveis sob ``.pt``."""
    kit = (STATIC.parent / "kit.css").read_text(encoding="utf-8")
    linha = "--k-pv:" + _trecho(kit, "--k-pv:", "\n", "static/kit.css")
    tokens = [t.strip() for t in linha.split(";") if t.strip().startswith("--k-")]
    if not tokens:
        raise RuntimeError("Tokens de cor do Gestor não encontrados em static/kit.css")
    return ".pt { " + " ".join(t + ";" for t in tokens) + " }"


def _pagina(nome: str):
    """Componente v2 de PÁGINA na linguagem Partitura: motor Trama + ícones/cores do Gestor + ``<nome>.js``, estilos de
    ``trama.css`` (sob ``.pt``)."""
    return st.components.v2.component(f"seeds_{nome}", js=_src("trama.js") + "\n" + icones_gestor_js() + "\n" + _src(f"{nome}.js"),
                                      css=_src("trama.css") + "\n" + tokens_gestor_css())


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


__all__ = ["FRAME_FORMAT", "component", "icones_gestor_js", "pagina", "partitura", "sidebar", "tokens_gestor_css"]
