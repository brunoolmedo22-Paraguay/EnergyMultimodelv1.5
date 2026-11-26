"""Slide 31 (deck) — Resultados: operação do armazenamento (C4), segunda rodada sobre a proposta A (pedido do responsável):
gráfico em METADE da largura, ponta destacada, sem a raia «Decisões do MPC»; a outra metade com a informação relevante.

Figura: motor gráfico do SEEDS (Partitura/Trama) sobre a rodada 14d8e5b3, 12:00–24:00 (`seeds_fig/extrair.py`, view [48, 96]),
raias Atendimento · Bateria · Tarifa. Sobreposições do slide: faixa da ponta (18:00–21:00), marca das 16:15 (a ponta entra na
janela do MPC, N = 8) e os valores gravados da energia às 18:00 (178,04 kWh) e às 21:00 (20,15 kWh), posicionados pela escala
lida dos rótulos do próprio eixo.
Números (Tabela 7.1, Seção 7.1, conferidos no marco): energia 60,00 → 178,04 kWh até 18:00 (SOC 30 → 89 %); 50 kW nos 12
intervalos de ponta; 20,15 kWh às 21:00; importação na ponta 270,01 (C1) → 118,74 kWh (C4), −56 %; 1 kWh na ponta: R$ 0,490
(0,44234 ÷ 0,9025) × R$ 1,93894; C3: 62,50 kWh = 50,3 % da carga decidida em janelas iniciadas entre 15:00 e 16:00."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD
from gerar_slide8 import rodape
from gerar_slide31b import CSS_SEEDS, BG, SURF, INK, INK2, INK3, FV, BAT, GRID, FUT, FD, FT, legenda

D = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(D, "assets")
TIT = "Resultados — operação do armazenamento"
REF = "Tabela 7.1, Fig. 7.1–7.2 e Seção 7.1 do artigo · figura desenhada pelo motor gráfico do SEEDS (Partitura) a partir da rodada 14d8e5b3 (C4)"
CSS_31 = f"""
.row{{display:grid;grid-template-columns:170px 1fr auto;align-items:center;gap:16px;padding:12px 0;border-top:1.5px solid rgba(20,24,28,.10)}}
.row:first-of-type{{border-top:0}}
.chip{{display:inline-flex;justify-content:center;align-items:center;height:38px;padding:0 14px;border-radius:999px;border:1.5px solid rgba(20,24,28,.22);
  font:600 20px {FT};color:{INK};background:#fff;white-space:nowrap}}
.chip.p{{border-color:{GRID};color:{GRID};background:#fdeceb}}
.row span{{font:400 22px/1.25 {FT};color:{INK2}}}
.row b{{font:700 28px {FD};color:{INK};font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}}
.row b small{{display:block;font:600 18px {FT};color:{INK3};letter-spacing:0}}
.barra{{position:absolute;height:44px;border-radius:10px}}
"""


def figura(nome, x, y, s):
    """SVG do SEEDS (escala s) + sobreposições: ponta, 16:15 e valores gravados da bateria."""
    m = json.load(open(os.path.join(A, nome + ".json"), encoding="utf-8"))
    W, H, pl, pr = m["W"], m["H"], m["padL"], m["padR"]
    v0, v1 = m["view"]
    cw = (W - pl - pr) / (v1 - v0)
    X = lambda k: pl + (k - v0) * cw
    corpo = open(os.path.join(A, nome + ".svg"), encoding="utf-8").read()
    corpo = corpo[corpo.index(">") + 1: corpo.rindex("</svg>")]
    yb_tit = m["lanes"][1]["y"]
    # escala da raia da bateria a partir dos rótulos «0» e «200» do próprio eixo (y do texto = linha + 3,5)
    tb = [r for r in m["rotulos"] if r["x"] == pl - 6 and yb_tit < r["y"] < m["lanes"][2]["y"]]
    y0 = next(r["y"] for r in tb if r["t"] == "0") - 3.5
    y200 = next(r["y"] for r in tb if r["t"] == "200") - 3.5
    YE = lambda e: y0 + (y200 - y0) * e / 200
    topo, base = 2, H - 20
    o = f'<svg x="{x}" y="{y}" width="{W*s}" height="{H*s}" viewBox="0 0 {W} {H}" overflow="visible">'
    o += f'<rect x="{X(72)}" y="{topo}" width="{X(84)-X(72)}" height="{base-topo}" fill="{GRID}" opacity=".10"/>'
    o += corpo
    o += f'<line x1="{X(65)}" x2="{X(65)}" y1="{topo+16}" y2="{base}" stroke="{FUT}" stroke-width="1.3" stroke-dasharray="4 3"/>'
    for k, e in ((72, 178.04), (84, 20.15)):
        o += f'<circle cx="{X(k)}" cy="{YE(e)}" r="3.2" fill="{BAT}" stroke="#fff" stroke-width="1.2"/>'
    o += "</svg>"
    P = lambda k, yy: (x + X(k) * s, y + yy * s)
    h = ""
    px, py = P(72, m["lanes"][0]["y"] + 22)
    h += (f'<div class="sd" style="left:{px}px;top:{py}px;width:{(X(84)-X(72))*s}px;text-align:center;font:700 22px/1.15 {FT};color:{GRID}">'
          f'Ponta<br><span style="font-weight:600;font-size:20px">18:00–21:00</span></div>')
    px, py = P(65, m["lanes"][2]["y"] + 6)            # raia da tarifa: espaço livre acima do patamar de 0,44 à esquerda da marca
    h += (f'<div class="sd" style="left:{px-282}px;top:{py}px;width:272px;text-align:right;font:600 20px/1.2 {FT};color:{FUT}">'
          f'<b>16:15</b> · a ponta entra<br>na janela do MPC</div>')
    for k, e, txt, dy in ((72, 178.04, "178,04 kWh", -44), (84, 20.15, "20,15 kWh", -36)):
        px, py = P(k, YE(e))
        h += f'<div class="sd" style="left:{px+12}px;top:{py+dy}px;font:700 20px {FD};color:{BAT};white-space:nowrap">{txt}</div>'
    return o, h


def cartao(x, y, w, h, acc, titulo, corpo):
    return (f'<div class="card" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;--acc:{acc}">'
            f'<h3>{titulo}</h3>{corpo}</div>')


def slide():
    s = f'<rect x="110" y="166" width="1700" height="746" rx="30" fill="{BG}"/><rect x="124" y="180" width="860" height="718" rx="24" fill="{SURF}"/>'
    h = legenda(150, 196, 830).replace("margin-right:26px", "margin-right:18px")
    f_, fh = figura("seeds_c4_tarde", 136, 238, 1.53)
    s += f_; h += fh
    xr, wr = 1000, 796
    # 1 · o que a bateria fez
    linhas = [("", "até 18:00", "Carrega fora de ponta", "60 → 178 kWh", "SOC de 30 para 89 %"),
              ("p", "18:00–21:00", "Descarrega no limite do banco", "50 kW", "178 → 20 kWh"),
              ("p", "na ponta", "Importação da rede, C1 → C4", "270 → 119 kWh", "−56 %")]
    corpo = "".join(f'<div class="row"><i class="chip {c}" style="font-style:normal">{t}</i><span>{a}</span><b>{v}<small>{sub}</small></b></div>'
                    for c, t, a, v, sub in linhas)
    h += cartao(xr, 180, wr, 300, BAT, "O que a bateria fez em C4", f'<div style="margin-top:8px">{corpo}</div>')
    # 2 · por que vale a pena: custo de 1 kWh na ponta
    L = 360
    y2 = 494
    h += cartao(xr, y2, wr, 224, GRID, "Custo de 1 kWh entregue na ponta", "")
    for i, (rot, v, cor, txt) in enumerate((("Guardado fora de ponta", 0.490, BAT, "R$ 0,49"), ("Importado na ponta", 1.93894, GRID, "R$ 1,94"))):
        yy = y2 + 62 + i * 60
        h += f'<div class="sd" style="left:{xr+30}px;top:{yy+8}px;width:230px;font:400 22px {FT};color:{INK2}">{rot}</div>'
        h += f'<div class="barra" style="left:{xr+290}px;top:{yy}px;width:{L*v/1.93894:.0f}px;background:{cor}"></div>'
        h += f'<div class="sd" style="left:{xr+304+L*v/1.93894:.0f}px;top:{yy+3}px;font:700 30px {FD};color:{INK};white-space:nowrap">{txt}</div>'
    h += f'<div class="sd" style="left:{xr+30}px;top:{y2+180}px;font:400 22px {FT};color:{INK3}">0,44 R$/kWh ÷ 0,9025 (rendimento de ida e volta)</div>'
    # 3 · coordenação: decide antes de ver a ponta
    y3 = 732
    h += cartao(xr, y3, wr, 166, FUT, "Decide antes de ver a ponta",
                f'<div style="display:flex;gap:24px;align-items:center;margin-top:6px"><div class="big" style="font-size:52px;color:{FUT}">50,3&nbsp;%</div>'
                f'<div class="sub" style="color:{INK2};font-size:22px;line-height:1.35">da carga de C3 (62,5&nbsp;kWh) foi decidida antes das 16:15, '
                f'quando a ponta ainda estava fora da janela do MPC: <b style="color:{INK}">só o valor futuro</b> indicava que guardar valia a pena.</div></div>')
    body = ('<link rel="stylesheet" href="assets/fonts_seeds.css">' + f'<div class="tt">{TIT}</div>'
            + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(31))
    open(os.path.join(D, "S31c_metade.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM + CSS_SEEDS + CSS_31, body=body))


if __name__ == "__main__":
    slide()
