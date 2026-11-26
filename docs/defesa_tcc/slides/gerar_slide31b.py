"""Slide 31 (deck) — Resultados: operação do armazenamento e coordenação (C4). Figura = Fig. 7.1/7.2 do artigo REDESENHADA pelo
motor gráfico do próprio SEEDS (Partitura/Trama) a partir da rodada 14d8e5b3 (C4), via `seeds_fig/extrair.py`:
raias Decisões do MPC · Atendimento (despacho) · Bateria (energia nas fronteiras) · Tarifa de decisão.
Cartões no estilo `.pt .card` da Partitura (fundo #f4f4f2 sobre #e6e6e4, filete de cor à esquerda, número em Archivo).
Números (Seção 7.1, conferidos no marco da rodada): 178,04 kWh às 18:00 (SOC 30 % → 89 %); 50 kW nos 12 intervalos de ponta;
20,15 kWh às 21:00; 1 kWh na ponta: R$ 0,490 (fora de ponta, rendimento 0,9025) × R$ 1,93894; C3: 62,50 kWh = 50,3 % da carga
decidida em janelas iniciadas entre 15:00 e 16:00, antes de a ponta (18:00) entrar no horizonte do MPC (a partir das 16:15).
Três propostas: A painel + cartões à direita · B figura larga + cartões embaixo · C a tela da Partitura (cabeçalho, lentes, barra de estado)."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(D, "assets")
TIT = "Resultados — operação do armazenamento"
REF = ("Fig. 7.1 e 7.2 e Seção 7.1 do artigo · figura desenhada pelo motor gráfico do SEEDS (Partitura) a partir da rodada 14d8e5b3 (C4)")
BG, SURF, INK, INK2, INK3 = "#e6e6e4", "#f4f4f2", "#171717", "#4d545b", "#7c848c"
FV, BAT, GRID, FUT = "#c98a00", "#7a63e0", "#d9534a", "#C0532F"
FD = "Archivo, 'Source Sans 3', sans-serif"
FT = "'Source Sans 3', sans-serif"
CSS_SEEDS = f"""
.sd{{position:absolute;font-family:{FT};color:{INK}}}
.card{{position:absolute;background:{SURF};border-radius:24px;box-sizing:border-box;padding:20px 26px 18px 30px;font-family:{FT}}}
.card::before{{content:"";position:absolute;left:0;top:22px;bottom:22px;width:4px;border-radius:4px;background:var(--acc)}}
.card h3{{margin:0;font:600 22px/1.2 {FT};color:{INK2}}}
.card .big{{font:700 44px/1.15 {FD};letter-spacing:-.02em;color:{INK};margin-top:4px;font-variant-numeric:tabular-nums}}
.card .big small{{font:600 22px {FD};color:{INK2};margin-left:6px;letter-spacing:0}}
.card .sub{{font:400 22px/1.3 {FT};color:{INK3};margin-top:4px}}
.leg{{display:inline-flex;align-items:center;gap:10px;margin-right:26px;font:400 22px {FT};color:{INK2};white-space:nowrap}}
.leg i{{display:inline-block;width:18px;height:18px;border-radius:5px}}
.leg i.ln{{height:4px;width:28px;border-radius:2px}}
.leg i.ht{{background:repeating-linear-gradient(45deg,{BAT} 0 3px,{SURF} 3px 7px)}}
"""

CARTOES = [
    (BAT, "Energia no início da ponta", "178,04", "kWh", "SOC de 30 % para 89 %, carregando fora de ponta"),
    (BAT, "Descarga na ponta", "50", "kW", "potência máxima do banco, de 18:00 a 21:00"),
    (GRID, "Custo de 1 kWh entregue na ponta", "R$ 0,49 × 1,94", "", "guardado fora de ponta × importado na ponta"),
    (FUT, "Decidido antes de ver a ponta", "50,3 %", "", "da carga de C3, por janelas que não viam a ponta"),
]


def cartao(x, y, w, h, acc, t, big, un, sub):
    u = f"<small>{un}</small>" if un else ""
    return (f'<div class="card" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;--acc:{acc}">'
            f'<h3>{t}</h3><div class="big">{big}{u}</div><div class="sub">{sub}</div></div>')


def figura(nome, x, y, s, marcas=True):
    """Insere o SVG do SEEDS (escala s) e devolve (svg, html); marca 16:15 (a ponta entra na janela do MPC, N = 8)."""
    meta = json.load(open(os.path.join(A, nome + ".json"), encoding="utf-8"))
    W, H, pl, pr, K = meta["W"], meta["H"], meta["padL"], meta["padR"], meta["K"]
    corpo = open(os.path.join(A, nome + ".svg"), encoding="utf-8").read()
    corpo = corpo[corpo.index(">") + 1: corpo.rindex("</svg>")]
    o = f'<svg x="{x}" y="{y}" width="{W*s}" height="{H*s}" viewBox="0 0 {W} {H}" overflow="visible">{corpo}'
    h = ""
    if marcas:
        cw = (W - pl - pr) / K
        X = lambda k: pl + k * cw
        y1 = meta["lanes"][0]["y"] + 6
        y2 = H - 20
        o += (f'<line x1="{X(65)}" x2="{X(65)}" y1="{y1}" y2="{y2}" stroke="{FUT}" stroke-width="1.4" stroke-dasharray="4 3"/>')
        yt = y + (meta["lanes"][1]["y"] - 11) * s - 27      # entre as decisões e o título do atendimento, à esquerda da marca
        h += (f'<div class="sd" style="left:{x + X(65)*s - 560}px;top:{yt}px;width:550px;text-align:right;font:600 20px/1.2 {FT};color:{FUT};white-space:nowrap">'
              f'<b>16:15</b> · a ponta entra na janela do MPC (N = 8)</div>')
    return o + "</svg>", h


def legenda(x, y, w):
    itens = [f'<span class="leg"><i style="background:{FV}"></i>Solar</span>', f'<span class="leg"><i style="background:{BAT}"></i>Bateria</span>',
             f'<span class="leg"><i style="background:{GRID}"></i>Rede</span>', f'<span class="leg"><i class="ln" style="background:{INK}"></i>Demanda</span>',
             '<span class="leg"><i class="ht"></i>carga da bateria</span>', f'<span class="leg"><i class="ln" style="background:{GRID}"></i>tarifa</span>']
    return f'<div class="sd" style="left:{x}px;top:{y}px;width:{w}px;display:flex;flex-wrap:wrap">{"".join(itens)}</div>'


def salvar(nome, s, h, titulo=True):
    body = ('<link rel="stylesheet" href="assets/fonts_seeds.css">' + (f'<div class="tt">{TIT}</div>' if titulo else "")
            + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(31))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM + CSS_SEEDS, body=body))


# ===================================================================== A · painel da Partitura + cartões à direita
def a():
    s = f'<rect x="110" y="166" width="1700" height="746" rx="30" fill="{BG}"/><rect x="124" y="180" width="1150" height="718" rx="24" fill="{SURF}"/>'
    h = legenda(150, 196, 1100)
    f_, fh = figura("seeds_c4_op_estreito", 140, 236, 1.6)
    s += f_; h += fh
    for i, c in enumerate(CARTOES):
        h += cartao(1288, 180 + i * 182, 508, 170, *c)
    salvar("S31b_A_painel", s, h)


# ===================================================================== B · figura larga + cartões embaixo
def b():
    s = f'<rect x="110" y="166" width="1700" height="546" rx="30" fill="{SURF}"/>'
    h = legenda(150, 180, 1640)
    f_, fh = figura("seeds_c4_op_largo", 200, 214, 1.47)
    s += f_; h += fh
    for i, c in enumerate(CARTOES):
        h += cartao(110 + i * 431, 726, 415, 188, *c)
    salvar("S31b_B_largo", s, h)


# ===================================================================== C · a tela da Partitura (cabeçalho, lentes, estado)
def c():
    s = f'<rect x="110" y="40" width="1700" height="884" rx="34" fill="{BG}"/>'
    h = (f'<div class="sd" style="left:142px;top:62px;font:700 40px/1.1 {FD};letter-spacing:-.01em">C4 — CT-046 · Solar + Bateria + Rede · 02-10-2026</div>'
         f'<div class="sd" style="left:142px;top:112px;width:1640px;font:400 22px {FT};color:{INK3};white-space:nowrap;overflow:hidden">rodada 14d8e5b3 · 96 intervalos de 15 min · N 8 · m 1 · H<sub>L</sub> 96 — '
         f'<b style="color:{INK2}">R$ 865,03</b> realizados · <b style="color:{INK2}">1.967 kWh</b> atendidos · déficit <b style="color:{INK2}">0,0 kWh</b> · valor futuro em <b style="color:{INK2}">96 de 96</b> decisões</div>')
    abas = ["Operação", "Decisão", "Economia", "Evidência", "Visão Geral"]
    s += f'<rect x="142" y="156" width="{len(abas)*168+12}" height="54" rx="14" fill="#dcdcd9"/>'
    for i, t in enumerate(abas):
        if i == 0:
            s += f'<rect x="{148+i*168}" y="162" width="160" height="42" rx="10" fill="{SURF}"/>'
        h += f'<div class="sd" style="left:{148+i*168}px;top:168px;width:160px;text-align:center;font:600 22px {FT};color:{INK if i == 0 else INK2}">{t}</div>'
    s += f'<rect x="126" y="226" width="1140" height="608" rx="24" fill="{SURF}"/>'
    h += legenda(150, 240, 1100)
    f_, fh = figura("seeds_c4_op_estreito", 140, 274, 1.33)
    s += f_; h += fh
    for i, cc in enumerate(CARTOES):
        h += cartao(1282, 226 + i * 154, 512, 142, *cc)
    s += f'<rect x="126" y="848" width="1668" height="62" rx="18" fill="{SURF}"/>'
    est = [("#1e7a50", "algébrico aprovado"), ("#1e7a50", "evidência verificada (20 de 20) sem solver"), ("#a56400", "dados sintéticos de ensaio")]
    h += (f'<div class="sd" style="left:150px;top:864px;width:1620px;display:flex;gap:30px;font:400 22px {FT};color:{INK2};white-space:nowrap">'
          f'<span><b style="color:{INK}">RODADA 14d8e5b3</b> · concluída · somente leitura</span>'
          + "".join(f'<span><i style="display:inline-block;width:11px;height:11px;border-radius:50%;background:{c_};margin-right:9px"></i>{t}</span>' for c_, t in est) + "</div>")
    salvar("S31b_C_tela", s, h, titulo=False)


if __name__ == "__main__":
    a()
    b()
    c()
