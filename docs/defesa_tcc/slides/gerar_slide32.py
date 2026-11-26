"""Slide 32 (deck) — Resultados: custos operacionais C1–C4, na mesma linguagem do slide 31 (contêiner do SEEDS, figura do motor
Trama em ~50 % da largura, cartões `.card` à direita).

Figura (P1): custo realizado POR INTERVALO das quatro rodadas (4f7da832, dbccd121, 7252f033, 14d8e5b3), desenhado pela API de raias
do próprio motor (`seeds_fig/extrair.py`, modo `custom`; séries `custo_realizado_intervalo_R` gravadas, escala COMUM 0–50 R$),
com a faixa da ponta. Entrada das séries: `seeds_fig/custos_c1c4.json`.
Números (Tabela 7.1, Seção 7.1, conferidos nos marcos): 1.274,25 / 1.100,97 / 1.038,31 / 865,03 R$; na ponta 523,54 / 521,08 /
232,70 / 230,24 R$ (= 41,1 / 47,3 / 22,4 / 26,6 % do custo); ponta = 13,7 % da energia; FV −173,28 (98,6 % fora de ponta);
bateria −235,94 (R$ 290,84 evitados na ponta − 54,90 a mais fora de ponta); C4 −409,22 = soma; objetivo do MILP na 1.ª decisão
de C4 R$ 865,02 (54,34 + 810,68) × realizado 865,03; banco termina com 20 kWh (60 no início): ciclo do dia R$ 217,31 em C3."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD
from gerar_slide8 import rodape
from gerar_slide31b import CSS_SEEDS, BG, SURF, INK, INK2, INK3, FV, BAT, GRID, FUT, FD, FT
from gerar_slide31c import CSS_31

D = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(D, "assets")
TIT = "Resultados — custos operacionais (C1–C4)"
REF = ("Tabela 7.1 e Seção 7.1 do artigo · rodadas 4f7da832 (C1), dbccd121 (C2), 7252f033 (C3) e 14d8e5b3 (C4) · custos realizados, "
       "sem o custo futuro estimado")
CSS_32 = f"""
.eq{{display:grid;grid-template-columns:150px 1fr auto;align-items:center;gap:14px;padding:9px 0;border-top:1.5px solid rgba(20,24,28,.10)}}
.eq:first-of-type{{border-top:0}}
.eq span{{font:400 22px/1.25 {FT};color:{INK2}}}
.eq b{{font:700 28px {FD};color:{INK};text-align:right;white-space:nowrap}}
.tag{{display:inline-flex;align-items:center;gap:8px;font:700 22px {FT};color:{INK}}}
.tag i{{width:16px;height:16px;border-radius:5px;display:inline-block}}
"""


def figura(nome, x, y, s):
    m = json.load(open(os.path.join(A, nome + ".json"), encoding="utf-8"))
    W, H, pl, pr = m["W"], m["H"], m["padL"], m["padR"]
    v0, v1 = m["view"]
    cw = (W - pl - pr) / (v1 - v0)
    X = lambda k: pl + (k - v0) * cw
    corpo = open(os.path.join(A, nome + ".svg"), encoding="utf-8").read()
    corpo = corpo[corpo.index(">") + 1: corpo.rindex("</svg>")]
    o = (f'<svg x="{x}" y="{y}" width="{W*s}" height="{H*s}" viewBox="0 0 {W} {H}" overflow="visible">'
         f'<rect x="{X(72)}" y="2" width="{X(84)-X(72)}" height="{H-22}" fill="{GRID}" opacity=".10"/>{corpo}</svg>')
    return o, m, (lambda k: x + X(k) * s)


NOTA = ("C3 e C4 terminam com 20&nbsp;kWh (começaram com 60): o ciclo do dia vale R$&nbsp;217,31 em C3. "
        "Em todas: sem déficit, exportação ou vertimento.")


def cartao(x, y, w, h, acc, titulo, corpo):
    return f'<div class="card" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;--acc:{acc}"><h3>{titulo}</h3>{corpo}</div>'


def cartoes_direita(xr, wr, com_ponta=True):
    h = ""
    y = 180
    if com_ponta:
        h += cartao(xr, y, wr, 172, GRID, "A ponta pesa menos",
                    f'<div style="display:flex;align-items:baseline;gap:16px;margin-top:4px"><div class="big">41,1&nbsp;% <span style="color:{INK3}">→</span> 26,6&nbsp;%</div></div>'
                    f'<div class="sub" style="color:{INK2}">do custo do dia ocorre na ponta (C1 → C4), que tem só 13,7&nbsp;% da energia</div>')
        y += 186
    hs = 334 if com_ponta else 330
    eqs = [(FV, "Solar", "reduz a importação fora de ponta", "−R$&nbsp;173,28"),
           (BAT, "Bateria", "leva energia barata para a ponta", "−R$&nbsp;235,94"),
           ("#1F7A6D", "C4", "as duas juntas, sem sinergia extra", "−R$&nbsp;409,22")]
    corpo = "".join(f'<div class="eq"><span class="tag"><i style="background:{c}"></i>{t}</span><span>{d}</span><b>{v}</b></div>' for c, t, d, v in eqs)
    h += cartao(xr, y, wr, hs, BAT, "Os efeitos se somam",
                f'<div style="margin-top:6px">{corpo}</div><div class="sub" style="margin-top:4px">−32,1&nbsp;% = 13,6&nbsp;% (solar) + 18,5&nbsp;% (bateria)</div>'
                + (f'<div class="sub" style="margin-top:10px;padding-top:10px;border-top:1.5px solid rgba(20,24,28,.10)">{NOTA}</div>' if com_ponta else ""))
    y += hs + 14
    h += cartao(xr, y, wr, 898 - y, FUT, "O plano se cumpre",
                f'<div style="display:flex;align-items:center;gap:22px;margin-top:4px"><div class="big" style="white-space:nowrap">R$&nbsp;865,02 <span style="color:{INK3}">×</span> 865,03</div></div>'
                f'<div class="sub" style="color:{INK2}">previsto na 1.ª decisão de C4 (operação + continuação) × realizado no fim do dia</div>')
    return h


def salvar(nome, s, h):
    body = ('<link rel="stylesheet" href="assets/fonts_seeds.css">' + f'<div class="tt">{TIT}</div>'
            + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(32))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM + CSS_SEEDS + CSS_31 + CSS_32, body=body))


# ===================================================================== P1 · custo por intervalo C1–C4 (motor do SEEDS) + cartões
def p1():
    s = f'<rect x="110" y="166" width="1700" height="746" rx="30" fill="{BG}"/><rect x="124" y="180" width="860" height="718" rx="24" fill="{SURF}"/>'
    h = (f'<div class="sd" style="left:150px;top:198px;font:600 22px {FT};color:{INK2}">Custo realizado por intervalo de 15 min [R$]</div>'
         f'<div class="sd" style="left:690px;top:198px;font:600 22px {FT};color:{INK2};white-space:nowrap">'
         f'<i style="display:inline-block;width:18px;height:18px;border-radius:5px;background:{GRID};vertical-align:-2px;margin-right:9px"></i>Rede</div>')
    f_, m, XS = figura("seeds_custos_c1c4", 136, 238, 1.53)
    s += f_
    h += (f'<div class="sd" style="left:{(XS(72)+XS(84))/2-90}px;top:236px;width:180px;text-align:center;white-space:nowrap;'
          f'font:700 22px {FT};color:{GRID}">Ponta</div>')
    h += cartoes_direita(1000, 796)
    salvar("S32_P1_intervalos", s, h)


# ===================================================================== P2 · matriz 2 × 2 em cartões do SEEDS + cartões
def p2():
    s = f'<rect x="110" y="166" width="1700" height="746" rx="30" fill="{BG}"/><rect x="124" y="180" width="860" height="718" rx="24" fill="{SURF}"/>'
    h = ""
    cfg = [("C1", "Rede", "1.274,25", "523,54", None), ("C2", "Rede + Solar", "1.100,97", "521,08", "−13,6&nbsp;%"),
           ("C3", "Rede + Bateria", "1.038,31", "232,70", "−18,5&nbsp;%"), ("C4", "Rede + Solar + Bateria", "865,03", "230,24", "−32,1&nbsp;%")]
    x0, y0, cw, ch, gx, gy = 252, 256, 300, 236, 76, 84
    h += (f'<div class="sd" style="left:{x0}px;top:202px;width:{cw}px;text-align:center;font:600 22px {FT};color:{INK2}">Sem solar</div>'
          f'<div class="sd" style="left:{x0+cw+gx}px;top:202px;width:{cw}px;text-align:center;font:600 22px {FT};color:{INK2}">Com solar</div>')
    for r, t in enumerate(("Sem<br>bateria", "Com<br>bateria")):
        h += f'<div class="sd" style="left:146px;top:{y0+r*(ch+gy)+ch/2-28}px;width:110px;font:600 22px/1.25 {FT};color:{INK2}">{t}</div>'
    for i, (c, comp, tot, pon, red) in enumerate(cfg):
        x, y = x0 + (i % 2) * (cw + gx), y0 + (i // 2) * (ch + gy)
        dest = c == "C4"
        fundo, tc = ("#1F7A6D", "#fff") if dest else ("#fff", INK)
        s += f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="22" fill="{fundo}" stroke="rgba(20,24,28,.10)" stroke-width="1.5"/>'
        h += (f'<div class="sd" style="left:{x+24}px;top:{y+18}px;width:{cw-48}px;display:flex;justify-content:space-between;align-items:baseline">'
              f'<span style="font:700 30px {FD};color:{tc}">{c}</span>'
              + (f'<span style="font:700 22px {FT};color:{"#fff" if dest else "#1F7A6D"}">{red}</span>' if red else "") + "</div>"
              f'<div class="sd" style="left:{x+24}px;top:{y+62}px;font:400 22px {FT};color:{"#DDEFEC" if dest else INK3}">{comp}</div>'
              f'<div class="sd" style="left:{x+24}px;top:{y+100}px;font:700 44px {FD};letter-spacing:-.02em;color:{tc}">R$&nbsp;{tot}</div>'
              f'<div class="sd" style="left:{x+24}px;top:{y+166}px;font:400 22px/1.3 {FT};color:{"#DDEFEC" if dest else INK2}">na ponta: R$&nbsp;{pon}</div>')
    # setas: solar (horizontal) e bateria (vertical), com os deltas
    for r in (0, 1):
        yy = y0 + r * (ch + gy) + ch / 2
        s += f'<line x1="{x0+cw+10}" x2="{x0+cw+gx-14}" y1="{yy+18}" y2="{yy+18}" stroke="{FV}" stroke-width="4"/><path d="M{x0+cw+gx-16} {yy+10} L{x0+cw+gx-4} {yy+18} L{x0+cw+gx-16} {yy+26}Z" fill="{FV}"/>'
        h += f'<div class="sd" style="left:{x0+cw}px;top:{yy-22}px;width:{gx}px;text-align:center;font:700 20px {FD};color:#A57A0E">−173</div>'
    for col in (0, 1):
        xx = x0 + col * (cw + gx) + cw / 2
        s += f'<line x1="{xx}" x2="{xx}" y1="{y0+ch+10}" y2="{y0+ch+gy-14}" stroke="{BAT}" stroke-width="4"/><path d="M{xx-8} {y0+ch+gy-16} L{xx} {y0+ch+gy-4} L{xx+8} {y0+ch+gy-16}Z" fill="{BAT}"/>'
        h += f'<div class="sd" style="left:{xx+14}px;top:{y0+ch+gy/2-14}px;font:700 20px {FD};color:{BAT}">−236</div>'
    h += f'<div class="sd" style="left:150px;top:{y0+2*ch+gy+22}px;width:810px;font:400 20px/1.3 {FT};color:{INK3}">R$ por dia · setas = redução ao acrescentar o recurso</div>'
    h += cartoes_direita(1000, 796)
    salvar("S32_P2_matriz", s, h)


if __name__ == "__main__":
    p1()
    p2()
