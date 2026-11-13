"""Bancada do componente Partitura (Piso 3D-B): página LOCAL, sem Streamlit, com o JavaScript e o CSS REAIS do
componente e um marco ``seeds2-trama-frame`` dado. Serve para exercitar no navegador marcos que a aplicação nunca
produziria por conta própria (dados ausentes, contratos antigos), sem tocar em rodadas nem em bancos.

Uso:  python tools/e2e/bancada_piso3db.py <marco.json> <saida.html>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ESTATICO = Path(__file__).resolve().parents[2] / "seeds2" / "ui" / "static" / "trama"


def pagina(frame: dict, outros: dict | None = None) -> str:
    """``outros``: marcos adicionais disponíveis em ``window.__OUTROS[nome]`` (para trocar de rodada na mesma página com
    ``window.__trocar(nome)``; ``window.__trocar(null)`` volta ao marco principal)."""
    js = ((ESTATICO / "trama.js").read_text("utf-8") + "\n" + (ESTATICO / "partitura.js").read_text("utf-8")
          .replace("export default function (component)", "window.__monta = function (component)"))
    if "window.__monta" not in js:
        raise RuntimeError("ponto de montagem do componente não encontrado em partitura.js")
    dados = json.dumps(frame, ensure_ascii=False, allow_nan=False).replace("</", "<\\/")
    mais = json.dumps(outros or {}, ensure_ascii=False, allow_nan=False).replace("</", "<\\/")
    return ("<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><title>Bancada Partitura</title><style>"
            "html,body{margin:0;background:#f4f4f2}" + (ESTATICO / "trama.css").read_text("utf-8") + tokens_gestor_css() + "</style></head><body>"
            "<div id=\"raiz\" style=\"padding:10px\"></div>"
            f"<script>window.__F = {dados}; window.__OUTROS = {mais};</script><script>{js}\n"
            "window.__trocar = (n) => window.__monta({ data: { frame: n ? window.__OUTROS[n] : window.__F }, "
            "parentElement: document.getElementById('raiz') }); window.__trocar(null);</script>"
            "</body></html>")


def pagina_componente(nome: str, dados: dict) -> str:
    """Página de bancada para um componente de PÁGINA do 3D-B2 (``planta``, ``sidebar``…): recebe ``dados`` como o Python
    os entrega; as ações devolvidas ficam em ``window.__acoes``."""
    from seeds2.ui.trama import icones_gestor_js, tokens_gestor_css     # mesma montagem de trama._pagina (UI-REDESIGN-01)

    js = ((ESTATICO / "trama.js").read_text("utf-8") + "\n" + icones_gestor_js() + "\n" + (ESTATICO / f"{nome}.js").read_text("utf-8")
          .replace("export default function (component)", "window.__monta = function (component)"))
    if "window.__monta" not in js:
        raise RuntimeError(f"ponto de montagem do componente não encontrado em {nome}.js")
    d = json.dumps(dados, ensure_ascii=False, allow_nan=False).replace("</", "<\\/")
    return ("<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><title>Bancada " + nome + "</title><style>"
            "html,body{margin:0;background:#f4f4f2}" + (ESTATICO / "trama.css").read_text("utf-8") + tokens_gestor_css() + "</style></head><body>"
            "<div id=\"raiz\" style=\"padding:10px\"></div>"
            f"<script>window.__D = {d}; window.__acoes = [];</script><script>{js}\n"
            "window.__monta({ data: window.__D, parentElement: document.getElementById('raiz'), "
            "setTriggerValue: (k, v) => window.__acoes.push(v) });</script></body></html>")


if __name__ == "__main__":
    marco, saida = Path(sys.argv[1]), Path(sys.argv[2])
    saida.write_text(pagina(json.loads(marco.read_text("utf-8"))), encoding="utf-8")
    print(f"OK: {saida}")
