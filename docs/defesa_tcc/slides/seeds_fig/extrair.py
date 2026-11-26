"""Figuras do SEEDS para a defesa, desenhadas pelo PRÓPRIO motor gráfico da Partitura (Trama) sobre o marco de uma rodada.

A página de bancada carrega o JavaScript e o CSS REAIS de `seeds2/ui/static/trama/` (lidos do repositório, sem alteração
em disco). Na cópia em memória só se acrescenta: (1) o ponto de montagem `window.__monta` (como `tools/e2e/bancada_piso3db.py`);
(2) a exposição de `lanesOperacao`, `svgPdf`, `K`, `lab` e `M` no objeto que a Partitura já devolve; (3) a família da fonte nos
textos serializados por `svgPdf`. As raias, escalas, cores e rótulos são os da interface; nada é recalculado aqui.
O SVG sai com cores explícitas (a mesma serialização do relatório PDF do SEEDS); as hachuras viram padrões SVG.

Uso (na raiz do repositório):
  python3 docs/defesa_tcc/slides/seeds_fig/extrair.py <marco.json> <saida.svg> <largura> <altura> '{"lanes": ["prefixo", ...], "labW": 75, "major": 4}'
  → grava <saida.svg> e <saida>.json (geometria: padL, padR, K, topo/altura de cada raia, para anotações no slide)."""
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
EST = RAIZ / "seeds2" / "ui" / "static" / "trama"
FONTES = Path(__file__).resolve().parents[1] / "assets" / "fonts_seeds.css"


INJ_SEEDS = ('const inj = [{ v: A.wtP, c: COR.wt, k: "wt" }, { v: A.fvP, c: COR.fv, k: "fv" }, { v: A.pd, c: COR.bat, k: "bat" }, '
             '{ v: A.fcP, c: COR.fc, k: "fc" }, { v: A.impR, c: COR.grid, k: "grid" }];')
# Ordem de empilhamento da Fig. 7.1 do artigo: rede embaixo, renováveis acima e armazenamento por cima — a parcela suprida pela
# rede (carga líquida) fica legível direto no gráfico. Só muda a ORDEM das camadas; valores, escalas e cores são os mesmos.
INJ_ARTIGO = ('const inj = [{ v: A.impR, c: COR.grid, k: "grid" }, { v: A.wtP, c: COR.wt, k: "wt" }, { v: A.fvP, c: COR.fv, k: "fv" }, '
              '{ v: A.fcP, c: COR.fc, k: "fc" }, { v: A.pd, c: COR.bat, k: "bat" }];')


def js_partitura(ordem_artigo: bool = False) -> str:
    src = (EST / "partitura.js").read_text("utf-8")
    if ordem_artigo:
        ancora = "function lanesOperacao() {\n    "          # só a raia Atendimento de lanesOperacao (há outra lista igual)
        if src.count(ancora + INJ_SEEDS) != 1:
            raise RuntimeError("ordem de injeção de lanesOperacao não encontrada em partitura.js")
        src = src.replace(ancora + INJ_SEEDS, ancora + INJ_ARTIGO)
    trocas = [
        ("export default function (component)", "window.__monta = function (component)"),
        ("return { render, relatorio, relStatus, gerarRelatorio };",
         "return { render, relatorio, relStatus, gerarRelatorio, __x: { lanesOperacao, svgPdf, K, lab, M } };"),
        ('a.push(`font-size="${parseFloat(cs.fontSize) || 11}"`, ',
         'a.push(`font-size="${parseFloat(cs.fontSize) || 11}"`, `font-family="${xe(cs.fontFamily).replace(/&quot;/g, "\'")}"`, '),
    ]
    for a, b in trocas:
        if src.count(a) != 1:
            raise RuntimeError(f"trecho não encontrado uma única vez em partitura.js: {a[:60]}")
        src = src.replace(a, b)
    return (EST / "trama.js").read_text("utf-8") + "\n" + src


def pagina(frame: dict, ordem_artigo: bool = False) -> str:
    fontes = FONTES.read_text("utf-8").replace("url(fonts_seeds/", f"url(file://{FONTES.parent}/fonts_seeds/")
    dados = json.dumps(frame, ensure_ascii=False, allow_nan=False).replace("</", "<\\/")
    return ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>html,body{margin:0;background:#f4f4f2}'
            + fontes + (EST / "trama.css").read_text("utf-8") + "</style></head><body><div id=\"raiz\" style=\"width:1400px\"></div>"
            f"<script>window.__F = {dados};</script><script>{js_partitura(ordem_artigo)}\n"
            "localStorage.setItem('seeds2.partitura.tema','light');"
            "window.__monta({ data: { frame: window.__F }, parentElement: document.getElementById('raiz') });</script></body></html>")


def hachuras(svg: str) -> str:
    """`svgPdf` registra a hachura como atributos (data-hatch*); aqui ela volta a ser um padrão SVG diagonal."""
    defs, ids = [], {}

    def troca(m):
        fill, cor, w, p = m.group(1), m.group(2), m.group(3), m.group(4)
        k = (fill, cor, w, p)
        if k not in ids:
            ids[k] = f"hx{len(ids)}"
            defs.append(f'<pattern id="{ids[k]}" width="{p}" height="{p}" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                        f'<rect width="{p}" height="{p}" fill="{fill}"/><rect width="{w}" height="{p}" fill="{cor}"/></pattern>')
        return f'fill="url(#{ids[k]})"'
    svg = re.sub(r'fill="(#[0-9a-f]{6})" data-hatch="(#[0-9a-f]{6})" data-hatch-w="([\d.]+)" data-hatch-p="([\d.]+)"', troca, svg)
    return svg.replace(">", "><defs>" + "".join(defs) + "</defs>", 1) if defs else svg


def main():
    marco, saida, W, H, opcoes = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    pag = saida.resolve().with_suffix(".bancada.html")
    pag.write_text(pagina(json.loads(marco.read_text("utf-8")), bool(json.loads(opcoes).get("ordem_artigo"))), encoding="utf-8")
    js = Path(__file__).with_name("extrair.js")
    out = subprocess.run(["node", str(js), str(pag), str(W), str(H), opcoes], capture_output=True, text=True, check=True)
    pag.unlink()
    r = json.loads(out.stdout)
    if r["erros"]:
        raise SystemExit("erros no navegador: " + "; ".join(r["erros"]))
    saida.write_text(hachuras(r["svg"]), encoding="utf-8")
    saida.with_suffix(".json").write_text(json.dumps(r["meta"], ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok", saida, r["meta"]["W"], "×", r["meta"]["H"], [L["title"][:40] for L in r["meta"]["lanes"]])


if __name__ == "__main__":
    main()
