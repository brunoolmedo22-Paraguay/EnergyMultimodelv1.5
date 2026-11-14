"""Confere os PDFs reais baixados pelo E2E do UI-RESULTADOS-02 contra os dados gravados do exemplo C4.

* PDF legível, paginado, com capa, sumário e as cinco seções da página de resultados; todas as fontes do explorador;
* custo realizado selado e identificador da rodada no documento; nenhum resíduo de interface («↗»);
* os dois caminhos (botão da Partitura e botão do painel) produzem documentos com o MESMO número de páginas e texto;
* a evidência da rodada não mudou (SHA-256 de cada dado gravado = os do início) e continua verificada sem solver.

Uso: python tools/e2e/check_ui_resultados02.py <dados> <seed.json> <saída do E2E>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ)]


def main(dados: str, seedf: str, saida: str) -> int:
    from pypdf import PdfReader

    from integracao_v2 import registro as RG
    from seeds2.microgrid.registry import MicrogridRegistry

    s = json.loads(Path(seedf).read_text("utf-8"))
    r = json.loads((Path(saida) / "e2e_ui_resultados02.json").read_text("utf-8"))
    falhas, n = [], 0

    def ok(c, msg):
        nonlocal n
        print(("ok — " if c else "FALHA — ") + msg)
        n += bool(c)
        if not c:
            falhas.append(msg)
    textos = {}
    for chave in ("pdf_partitura", "pdf_painel"):
        pag = [p.extract_text() or "" for p in PdfReader(r[chave]).pages]
        textos[chave] = pag
        tudo = "\n".join(pag)
        ok(len(pag) >= 30, f"{chave}: {len(pag)} páginas")
        ok("SEEDS2" in pag[0] and s["run"] in pag[0] and "Sumário" in pag[1], f"{chave}: capa com a rodada e sumário")
        for t in ("01 · Operação", "02 · Visão Geral", "03 · Decisão", "04 · Economia", "05 · Evidência", "Solar fotovoltaica", "Bateria",
                  "Rede / PCC", "Carga / Demanda", "Carga líquida", "Limitações científicas"):
            ok(t in tudo, f"{chave}: contém «{t}»")
        custo = f"{s['custo']:.2f}".replace(".", ",")
        ok(custo in tudo and "↗" not in tudo, f"{chave}: custo selado R$ {custo}; sem resíduos de interface")
        ok(re.search(rf"Página {len(pag)} de {len(pag)}", pag[-1]) is not None, f"{chave}: numeração «Página X de Y»")
    a, b = textos["pdf_partitura"], textos["pdf_painel"]
    gerado = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00 · SEEDS2")     # instante de GERAÇÃO (o resto deve ser idêntico)
    norm = lambda pg: [gerado.sub("", t) for t in pg]  # noqa: E731
    ok(len(a) == len(b) and norm(a) == norm(b), "os dois caminhos geram o mesmo documento (exceto o instante de geração)")
    st = MicrogridRegistry(dados).open(s["mg"])
    run = st.get_run(s["run"])
    ok({k: d["sha256"] for k, d in run.data.items()} == s["data"], "evidência da rodada intacta (SHA-256 de cada dado)")
    ok(RG.verificar(st, run).ok, "evidência continua verificada sem solver")
    print(f"{n} verificações; {len(falhas)} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:4]))
