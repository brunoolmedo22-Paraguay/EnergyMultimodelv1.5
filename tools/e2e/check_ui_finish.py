"""Confere os ARQUIVOS reais produzidos pelo E2E do UI-FINISH-01 (``e2e_ui_finish.js``) contra os dados gravados.

* imagens de gráfico: PNG com pHYs = 300 ppp e metadados; SVG autocontido (sem CSS externo, variáveis, classes ou scripts),
  com <title>/<metadata>, tema claro × escuro distintos;
* ZIP de figuras: manifest.json com SHA-256 de cada arquivo e das fontes = índice da rodada; arquivos não vazios; só figuras;
* Excel: folhas esperadas; tabela de intervalos IGUAL, valor a valor, ao texto do CSV gravado (leitura exata); ausente =
  célula vazia; o do estudo arquivado = o da rodada local;
* PDF: texto do início, meio e fim (rodada, resultados, limitações, rótulo sintético, custo selado);
* modal: nitidez do fundo constante em todos os quadros (o desfoque nunca some), inclusive nos quadros «stale»;
* banco: o E2E criou exatamente UMA rodada (interrompida, cancelada pelo usuário), sem dados.

Uso: python tools/e2e/check_ui_finish.py <SEEDS2_DATA_DIR> <seed_ui_finish.json> <pasta de saída do E2E>   (python com o projeto)
"""
from __future__ import annotations

import csv
import glob
import hashlib
import io
import json
import os
import struct
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ)]


def main(dados: str, seedf: str, saida: str) -> int:
    from openpyxl import load_workbook
    from PIL import Image, ImageFilter, ImageStat
    from pypdf import PdfReader

    from seeds2.microgrid.registry import MicrogridRegistry

    s = json.loads(Path(seedf).read_text("utf-8"))
    st = MicrogridRegistry(dados).open(s["lab"])
    run = st.get_run(s["run"])
    bx = Path(saida) / "baixados"
    falhas, n = [], 0

    def ok(c, msg):
        nonlocal n
        print(("ok — " if c else "FALHA — ") + msg)
        if c:
            n += 1
        else:
            falhas.append(msg)

    # ---- imagens de gráfico
    pngs = sorted(glob.glob(str(bx / "*.png")))
    svgs = sorted(glob.glob(str(bx / "*.svg")))
    ok(len(pngs) == 3 and len(svgs) == 3, f"{len(pngs)} PNG e {len(svgs)} SVG de gráficos")
    for f in pngs:
        b = Path(f).read_bytes()
        i = b.find(b"pHYs")
        ppm = struct.unpack(">I", b[i + 4:i + 8])[0] if i > 0 else 0
        im = Image.open(f)
        ok(round(ppm * 0.0254) == 300 and b"tEXt" in b and im.size[0] > 2000, f"{Path(f).name}: {im.size[0]}×{im.size[1]} px, 300 ppp declarados, metadados")
    for f in svgs:
        t = Path(f).read_text("utf-8")
        ok(t.startswith("<?xml") and "<title>" in t and "<metadata>" in t and "var(--" not in t and "class=" not in t
           and "<script" not in t and "<link" not in t and "http://" not in t.replace("http://www.w3.org/2000/svg", ""),
           f"{Path(f).name}: SVG autocontido (sem CSS externo, variáveis, classes ou scripts)")
    claro = [f for f in svgs if f.endswith("_claro.svg") and "bateria_" not in Path(f).name]
    escuro = [f for f in svgs if f.endswith("_escuro.svg") and "bateria_" not in Path(f).name]
    if claro and escuro:
        a, b2 = Path(claro[0]).read_text("utf-8"), Path(escuro[0]).read_text("utf-8")
        ok(a != b2 and '"tema":"light"' in a and '"tema":"dark"' in b2, "SVG claro × escuro: mesmos dados, temas distintos")
        import re
        num = lambda x: re.findall(r">(-?\d+(?:,\d+)?)</text>", x)  # noqa: E731
        ok(num(a) == num(b2), "SVG claro × escuro: os mesmos rótulos numéricos (nenhum valor muda com o tema)")
    # ---- ZIP de figuras
    z = zipfile.ZipFile(glob.glob(str(bx / "seeds2_figuras_*.zip"))[0])
    man = json.loads(z.read("manifest.json"))
    ok(all(hashlib.sha256(z.read(e["file"])).hexdigest() == e["sha256"] and len(z.read(e["file"])) > 0 for e in man["figures"]),
       f"ZIP: {len(man['figures'])} arquivos com SHA-256 do manifesto conferido e não vazios")
    ok(all(src["sha256"] == run.data[src["name"]]["sha256"] for e in man["figures"] for src in e["data_sources"]),
       "ZIP: SHA-256 dos dados de origem = índice da rodada gravada")
    ok(set(z.namelist()) <= {"manifest.json", "LEIA-ME.txt"} | {e["file"] for e in man["figures"]}, "ZIP: nenhum arquivo fora do escopo (só figuras)")
    # ---- Excel
    xl = [f for f in glob.glob(str(bx / "seeds2_dados_*.xlsx")) if not Path(f).name.startswith("estudo_")][0]
    wb = load_workbook(xl, read_only=True)
    ok({"02 Indicadores", "06 Intervalos", "07 Fronteiras", "10 Procedência", "11 Dicionário de dados"} <= set(wb.sheetnames), f"Excel: folhas {wb.sheetnames}")
    linhas = list(wb["06 Intervalos"].iter_rows(values_only=True))
    texto = list(csv.reader(io.StringIO(st.run_data(run.run_uid, "v2/intervalos.csv").decode("utf-8"))))
    ok(list(linhas[0]) == texto[0] and len(linhas) == len(texto), f"Excel: {len(linhas) - 1} linhas × {len(texto[0])} colunas = CSV gravado")
    dif, vazios = 0, 0
    for r, t in zip(linhas[1:], texto[1:]):
        for v, c in zip(r, t):
            if c == "":
                vazios += v is None
                dif += v is not None
                continue
            try:
                f = float(c)
            except ValueError:
                continue
            if not isinstance(v, (int, float)) or float(v) != f:
                dif += 1
    ok(dif == 0, f"Excel: todos os números iguais ao texto do CSV (double exato); {vazios} ausente(s) = célula vazia")
    xe = glob.glob(str(bx / "estudo_*.xlsx"))[0]
    ok(list(load_workbook(xe, read_only=True)["06 Intervalos"].iter_rows(values_only=True)) == linhas, "Excel do estudo arquivado = Excel da rodada local")
    # ---- PDF
    pdf = PdfReader(glob.glob(str(bx / "seeds2_relatorio_*.pdf"))[0])
    txt = [p.extract_text() for p in pdf.pages]
    custo = f"{run.summary['mission']['custo_realizado_total_R']:.2f}".replace(".", ",")
    ok(len(txt) >= 6 and run.run_uid in "".join(txt) and "Resultados" in "".join(txt[1:-1]) and "Limitações" in txt[-1],
       f"PDF: {len(txt)} páginas; início (rodada), meio (Resultados), fim (Limitações)")
    ok("SINTÉTICOS" in "".join(txt) and custo in "".join(txt), f"PDF: rótulo de dados sintéticos e custo selado R$ {custo}")
    # ---- modal
    q = json.loads((Path(saida) / "modal_quadros.json").read_text("utf-8"))
    nit = []
    for x in q:
        im = Image.open(x["arq"]).convert("L")
        w, h = im.size
        nit.append(ImageStat.Stat(im.crop((int(.82 * w), int(.35 * h), int(.97 * w), int(.7 * h))).filter(ImageFilter.FIND_EDGES)).mean[0])
    ok(max(nit) - min(nit) < 1.0, f"modal: nitidez do fundo constante em {len(nit)} quadros ({min(nit):.2f}–{max(nit):.2f}; "
                                   f"{sum(1 for x in q if x['stale'])} durante a atualização do fragmento)")
    # ---- banco
    rs = [r for r in st.list_runs(limit=100) if r.scenario_uid == s["longa"]]
    novas = [r for r in rs if r.run_uid != s["falha"]]
    ok(len(novas) == 1 and novas[0].state == "interrompida" and (novas[0].error or {}).get("kind") == "cancelada_pelo_usuario" and not novas[0].data,
       "banco: exatamente UMA rodada nova (cancelada pelo usuário, sem dados)")
    print(f"{'CONCLUÍDO' if not falhas else 'FALHAS'} — {n} verificações" + ("" if not falhas else ": " + "; ".join(falhas)))
    return 1 if falhas else 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    raise SystemExit(main(*sys.argv[1:]))
