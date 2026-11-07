"""Confere os arquivos BAIXADOS pelo E2E do Piso 2D-B (``e2e_piso2db_relatorios.js``) contra a origem.

* PDF (local, arquivado, após reinício): identificadores e indicadores persistidos presentes; páginas renderizadas em
  PNG (``<saida>/paginas/``) para inspeção visual.
* Excel (local × arquivado × após reinício): folhas, colunas e TODAS as séries numéricas iguais bit a bit entre si e
  iguais aos indicadores persistidos da origem (``e2e_origem.json``).
* ZIP de figuras: manifesto, SHA-256 de cada arquivo, PNG/SVG válidos.
* Registro do motor sabotado (opcional): deve estar ausente/vazio.

Uso:  python tools/e2e/check_piso2db_downloads.py <pasta_saida> <e2e_origem.json> [registro_do_motor]
"""
from __future__ import annotations

import glob
import io
import json
import os
import sys
import zipfile
from hashlib import sha256
from xml.etree import ElementTree as ET

import pandas as pd
from PIL import Image
from pypdf import PdfReader

ok = 0


def check(cond, msg):
    global ok
    if not cond:
        raise SystemExit("FALHA: " + msg)
    ok += 1
    print("ok —", msg)


def one(pattern):
    files = sorted(glob.glob(pattern))
    check(len(files) == 1, f"um arquivo para {os.path.basename(pattern)} ({len(files)})")
    return files[0]


def main(out: str, origin_path: str, engine_log: str | None = None) -> None:
    o = json.load(open(origin_path, encoding="utf-8"))
    dl = os.path.join(out, "downloads")
    pages_dir = os.path.join(out, "paginas")
    os.makedirs(pages_dir, exist_ok=True)
    s = o["summary"]
    cost = f"{s['custo_total_rs']:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    for tag in ("local", "arquivo", "reinicio"):
        f = one(os.path.join(dl, f"{tag}_seeds2_relatorio_*.pdf"))
        rd = PdfReader(f)
        txt = "\n".join(p.extract_text() or "" for p in rd.pages)
        for t in (o["run_uid"], o["microgrid_uid"], o["scenario_uid"], o["scenario_fingerprint"], o["config_fingerprint"],
                  o["incarnation"], f"R$ {cost}", "Industrial A — E2E 2D-B", "Alta demanda E2E",
                  "Potência (kW)", "Estado de carga (%)", *o["data"].values()):
            check(t in txt, f"PDF {tag}: contém {t[:40]}")
        check(("Estudo arquivado" in txt) == (tag != "local"), f"PDF {tag}: origem dos dados identificada")
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(f)
        for i in range(len(doc)):
            doc[i].render(scale=1.6).to_pil().save(os.path.join(pages_dir, f"{tag}_p{i + 1:02d}.png"))
        check(len(doc) >= 8, f"PDF {tag}: {len(doc)} páginas renderizadas para inspeção")
    dg = one(os.path.join(dl, "local_falha_seeds2_diagnostico_*.pdf"))
    txt = "\n".join(p.extract_text() or "" for p in PdfReader(dg).pages)
    check("otimizador indisponível" in txt and "Resultados energéticos" not in txt, "diagnóstico: erro original, sem resultados")
    books = {tag: one(os.path.join(dl, f"{tag}_seeds2_dados_*.xlsx")) for tag in ("local", "arquivo", "reinicio")}
    sheets = {tag: pd.read_excel(f, sheet_name=None) for tag, f in books.items()}
    check(list(sheets["local"]) == list(sheets["arquivo"]) == list(sheets["reinicio"]), "Excel: mesmas folhas nas 3 origens")
    for name in sheets["local"]:
        if name.startswith(("06", "07", "08", "09", "02", "03", "04")):
            pd.testing.assert_frame_equal(sheets["local"][name], sheets["arquivo"][name], check_exact=True)
            pd.testing.assert_frame_equal(sheets["local"][name], sheets["reinicio"][name], check_exact=True)
            check(True, f"Excel: folha '{name}' idêntica (local × arquivo × reinício)")
    ind = sheets["arquivo"]["02 Indicadores"]
    val = dict(zip(ind["chave"], ind["valor"]))
    for k in ("custo_total_rs", "energia_demanda_kWh", "energia_atendida_kWh", "energia_nao_atendida_kWh", "h2_kg"):
        check(float(val[k]).hex() == float(s[k]).hex(), f"Excel: {k} = valor persistido na origem (bit a bit)")
    check(len(sheets["arquivo"]["07 Despacho EMS"]) == s["passos"], f"Excel: {s['passos']} passos no despacho")
    for tag in ("local", "arquivo"):
        z = zipfile.ZipFile(one(os.path.join(dl, f"{tag}_seeds2_figuras_*.zip")))
        man = json.loads(z.read("manifest.json"))
        check(man["experiment"]["run_uid"] == o["run_uid"], f"figuras {tag}: manifesto identifica a rodada")
        for e in man["figures"]:
            b = z.read(e["file"])
            check(sha256(b).hexdigest() == e["sha256"], f"figuras {tag}: SHA-256 de {e['file']}")
            if e["format"] == "png":
                im = Image.open(io.BytesIO(b))
                check(im.size[0] >= 1900, f"figuras {tag}: {e['file']} {im.size[0]}×{im.size[1]} px")
            else:
                check(ET.fromstring(b).tag.endswith("svg"), f"figuras {tag}: {e['file']} é SVG válido")
    za, zb = (zipfile.ZipFile(one(os.path.join(dl, f"{t}_seeds2_figuras_*.zip"))) for t in ("local", "arquivo"))
    same = [n for n in za.namelist() if n.startswith("figuras/") and za.read(n) == zb.read(n)]
    check(len(same) == len([n for n in za.namelist() if n.startswith("figuras/")]),
          "figuras idênticas byte a byte entre a rodada local e a arquivada")
    if engine_log:
        check(not os.path.exists(engine_log) or os.path.getsize(engine_log) == 0, "motor sabotado NUNCA chamado no destino")
    print(f"CONCLUÍDO — {ok} verificações")


if __name__ == "__main__":
    main(*sys.argv[1:4])
