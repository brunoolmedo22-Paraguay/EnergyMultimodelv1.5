"""Slide 31 (deck) — Resultados: operação do armazenamento (C4), segunda rodada sobre a proposta A (pedido do responsável):
gráfico em METADE da largura, ponta destacada, sem a raia «Decisões do MPC»; a outra metade com a informação relevante.

Figura: motor gráfico do SEEDS (Partitura/Trama) sobre a rodada 14d8e5b3, dia completo 00:00–24:00 (`seeds_fig/extrair.py`),
raias Atendimento · Bateria · Tarifa. Empilhamento na ordem da Fig. 7.1 (rede embaixo, solar, bateria por cima; `ordem_artigo`).
Sobreposições do slide: faixa da ponta (18:00–21:00) e os valores gravados da energia às 18:00 (178,04 kWh) e às 21:00 (20,15 kWh), posicionados pela escala
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
.row{{display:grid;grid-template-columns:170px 1fr auto;align-items:center;gap:16px;padding:9px 0;border-top:1.5px solid rgba(20,24,28,.10)}}
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
    """SVG do SEEDS (escala s) + sobreposições: faixa da ponta e valores gravados da bateria."""
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
    for k, e in ((72, 178.04), (84, 20.15)):
        o += f'<circle cx="{X(k)}" cy="{YE(e)}" r="3.2" fill="{BAT}" stroke="#fff" stroke-width="1.2"/>'
    o += "</svg>"
    P = lambda k, yy: (x + X(k) * s, y + yy * s)
    h = ""
    px, py = P(72, m["lanes"][0]["y"] + 22)
    cx = px + (X(84) - X(72)) * s / 2
    h += (f'<div class="sd" style="left:{cx-90}px;top:{py}px;width:180px;text-align:center;white-space:nowrap;font:700 22px/1.15 {FT};color:{GRID}">'
          f'Ponta<br><span style="font-weight:600;font-size:20px">18:00–21:00</span></div>')
    for k, e, txt, dy in ((72, 178.04, "178,04 kWh", -44), (84, 20.15, "20,15 kWh", -36)):
        px, py = P(k, YE(e))
        h += f'<div class="sd" style="left:{px+12}px;top:{py+dy}px;font:700 20px {FD};color:{BAT};white-space:nowrap">{txt}</div>'
    return o, h


def cartao(x, y, w, h, acc, titulo, corpo):
    return (f'<div class="card" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;--acc:{acc}">'
            f'<h3>{titulo}</h3>{corpo}</div>')


def slide():
    s = f'<rect x="110" y="166" width="1700" height="746" rx="30" fill="{BG}"/><rect x="124" y="180" width="860" height="718" rx="24" fill="{SURF}"/>'
    leg = legenda(150, 196, 830).replace("margin-right:26px", "margin-right:18px")
    it = leg.split('<span class="leg">')                     # ordem da legenda = ordem do empilhamento: Rede, Solar, Bateria
    h = it[0] + "".join('<span class="leg">' + it[i] for i in (3, 1, 2, 4, 5, 6))
    f_, fh = figura("seeds_c4_dia", 136, 238, 1.53)
    s += f_; h += fh
    xr, wr = 1000, 796
    # 1 · o que a bateria fez (trechos do dia, C4)
    linhas = [("", "até 12:45", "Preserva o estoque inicial", "60 kWh", "fora de ponta valeria só 0,44 R$/kWh"),
              ("", "12:45–18:00", "Carrega fora de ponta", "60 → 178 kWh", "SOC de 30 para 89 %"),
              ("p", "18:00–21:00", "Descarrega no limite do banco", "50 kW", "178 → 20 kWh")]
    corpo = "".join(f'<div class="row"><i class="chip {c}" style="font-style:normal">{t}</i><span>{a}</span><b>{v}<small>{sub}</small></b></div>'
                    for c, t, a, v, sub in linhas)
    h += cartao(xr, 180, wr, 280, BAT, "O que a bateria fez em C4", f'<div style="margin-top:8px">{corpo}</div>')
    # 2 · quanto vale a energia entregue na ponta
    y2 = 474
    conta = [("Comprados da rede na ponta, custariam", "R$ 290,84", INK2, 400), ("Carregar fora de ponta custou a mais", "− R$ 54,90", INK2, 400),
             ("Ganho líquido da bateria", "R$ 235,94", INK, 700)]
    linhas2 = "".join(f'<div class="row" style="grid-template-columns:1fr auto;padding:9px 0"><span style="color:{c};font-weight:{w}">{a}</span>'
                      f'<b style="font-size:{30 if w == 700 else 26}px">{v}</b></div>' for a, v, c, w in conta)
    h += cartao(xr, y2, wr, 256, GRID, "Energia entregue pela bateria na ponta",
                f'<div style="display:flex;align-items:baseline;gap:14px;margin-top:2px"><div class="big">150&nbsp;kWh</div>'
                f'<div class="sub" style="margin:0">de 18:00 a 21:00, a 1,94 R$/kWh</div></div><div style="margin-top:2px">{linhas2}</div>')
    # 3 · coordenação: decide antes de ver a ponta
    y3 = 744
    h += cartao(xr, y3, wr, 154, FUT, "Decide antes de ver a ponta",
                f'<div style="display:flex;gap:24px;align-items:center;margin-top:2px"><div class="big" style="font-size:52px;color:{FUT}">50,3&nbsp;%</div>'
                f'<div class="sub" style="color:{INK2};font-size:22px;line-height:1.32">da carga de C3 foi decidida antes de a ponta entrar no horizonte do MPC: '
                f'<b style="color:{INK}">só o valor futuro</b> indicava que guardar valia a pena.</div></div>')
    body = ('<link rel="stylesheet" href="assets/fonts_seeds.css">' + f'<div class="tt">{TIT}</div>'
            + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(31))
    open(os.path.join(D, "S31c_metade.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM + CSS_SEEDS + CSS_31, body=body))


if __name__ == "__main__":
    slide()
