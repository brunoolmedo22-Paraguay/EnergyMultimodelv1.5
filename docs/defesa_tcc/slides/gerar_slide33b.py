"""Slide 33 (deck) — Resultados: embarcação híbrida, C5 × C6 lado a lado (pedido do responsável: comparar bateria alta × baixa).

Despachos desenhados pelo MOTOR GRÁFICO DO SEEDS (Partitura/Trama, `seeds_fig/extrair.py`, ordem da Fig. 7.3) a partir de:
  · C5 — rodada 055096cf dos exemplos persistentes (SOC inicial 50 %, reserva final ≥ 45 kWh);
  · C6 — rodada REPRODUZIDA com o próprio SEEDS (`seeds_fig/rodar_c6.py`: cenário de C5 com SOC inicial 12 % e sem termo terminal,
    MILP–MPC Pyomo 6.10.1 + HiGHS 1.15.1, diretório temporário). Conferida com o artigo: PEMFC 60,00 kWh (88,0 %), 19,96–44,28 kW,
    4,163 kg de H₂ (R$ 41,63), 24,58 kW às 13:00 levando o banco de 15,00 a 19,84 kWh, 18,39 kW da bateria às 13:15, fim em 15,00 kWh.
Comparação (Seção 7.2): H₂ 2,156 × 4,163 kg (1,93 ×); PEMFC 49,6 % (10,00–19,90 kW) × 88,0 % (19,96–44,28 kW); bateria cobre as
variações (correlação 0,986) × ciclos curtos recarregada pela própria PEMFC."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, LIGHT, div
from gerar_slide8 import rodape
from gerar_slide31b import BG, SURF, INK, INK2, INK3, FT, FD

D = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(D, "assets")
TIT = "Resultados — embarcação híbrida (C5 × C6)"
REF = ("Fig. 7.3–7.4 e Seção 7.2 do artigo · despachos desenhados pelo motor gráfico do SEEDS: rodada 055096cf (C5) e rodada de C6 "
       "reproduzida no SEEDS (SOC inicial 12 %, sem condição final), idêntica ao artigo")
C5, C6 = "#2C6FB0", "#C0532F"
PEM, BAT, SOL = "#1f9e8f", "#7a63e0", "#c98a00"


def figura(nome, x, y, s, notas):
    m = json.load(open(os.path.join(A, nome + ".json"), encoding="utf-8"))
    W, H = m["W"], m["H"]
    corpo = open(os.path.join(A, nome + ".svg"), encoding="utf-8").read()
    corpo = corpo[corpo.index(">") + 1: corpo.rindex("</svg>")]
    o = f'<svg x="{x}" y="{y}" width="{W*s}" height="{H*s}" viewBox="0 0 {W} {H}" overflow="visible">{corpo}</svg>'
    # escala da raia da bateria a partir dos rótulos «0» e «150» do próprio eixo
    yb = m["lanes"][1]["y"]
    tb = [r for r in m["rotulos"] if r["y"] > yb and r["x"] < m["padL"]]
    y0 = next(r["y"] for r in tb if r["t"] == "0") - 3.5
    y150 = next(r["y"] for r in tb if r["t"] == "150") - 3.5
    YE = lambda e: y + (y0 + (y150 - y0) * e / 150) * s
    h = ""
    for e, txt, dx in notas:
        h += (f'<div class="sd" style="left:{x + (m["padL"] + 6) * s + dx}px;top:{YE(e) - 34}px;font:700 20px {FD};color:{BAT};white-space:nowrap">{txt}</div>')
    return o, h


def painel(x, y, w, hp, cor, c, cond, nome, notas):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{hp}" rx="26" fill="{BG}"/><rect x="{x+12}" y="{y+12}" width="{w-24}" height="{hp-24}" rx="20" fill="{SURF}"/>'
    h = (f'<div class="sd" style="left:{x+36}px;top:{y+24}px;width:{w-72}px;display:flex;align-items:baseline;gap:16px;white-space:nowrap">'
         f'<span style="font:700 34px {FD};color:{cor}">{c}</span><span style="font:600 22px {FT};color:{INK2}">{cond}</span></div>')
    a, b = figura(nome, x + 30, y + 72, 1.38, notas)
    return s + a, h + b


def legenda(y):
    it = [(PEM, "PEMFC", "q"), (SOL, "Solar", "q"), (BAT, "Bateria", "q"), (INK, "Demanda", "l"), (BAT, "carga da bateria", "h")]
    o = ""
    for cor, t, tipo in it:
        if tipo == "q":
            i = f'<i style="display:inline-block;width:18px;height:18px;border-radius:5px;background:{cor}"></i>'
        elif tipo == "l":
            i = f'<i style="display:inline-block;width:28px;height:4px;border-radius:2px;background:{cor}"></i>'
        else:
            i = f'<i style="display:inline-block;width:18px;height:18px;border-radius:5px;background:repeating-linear-gradient(45deg,{cor} 0 3px,{SURF} 3px 7px)"></i>'
        o += f'<span style="display:inline-flex;align-items:center;gap:10px;margin:0 18px">{i}{t}</span>'
    return f'<div class="sd" style="left:110px;top:{y}px;width:1700px;display:flex;justify-content:center;font:400 22px {FT};color:{INK2}">{o}</div>'


def tile(x, y, w, hc, titulo, a, b, chip=None, destaque=False):
    """destaque = fundo violeta (cor da bateria): o cartão principal do slide."""
    tc, sc = ("#fff", "#ECE9FF") if destaque else ("#14213D", "#4A5568")
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{hc}" rx="24" fill="{"#5B4BC4" if destaque else LIGHT}"/>'
    h = div(x + 28, y + 18, w - 56, None, titulo, "", f"font:700 24px Gelasio,serif;color:{tc}")
    for k, (c, cor, big, sub) in enumerate((("C5", C5) + a, ("C6", C6) + b)):
        xx = x + 28 + k * (w - 56) / 2
        h += div(xx, y + 60, (w - 56) / 2 - 12, None,
                 f'<div style="font:700 22px Manrope;color:{"#D9D3FF" if destaque else cor}">{c}</div><div style="font:700 38px/1.15 Gelasio,serif;color:{tc};white-space:nowrap">{big}</div>'
                 f'<div style="font:500 22px/1.3 Manrope;color:{sc};margin-top:2px">{sub}</div>', "")
    if chip:
        h += div(x + w - 140, y + 16, 112, 38, chip, "", "display:flex;align-items:center;justify-content:center;border-radius:19px;background:#FBE4DC;"
                 f"font:700 22px Manrope;color:{C6}")
    return s, h


def slide():
    s, h = "", ""
    for x, cor, c, cond, nome, notas in (
            (110, C5, "C5", "bateria a 50 % · reserva final ≥ 45 kWh", "seeds_c5_op", [(75, "75 → 45 kWh", 4)]),
            (974, C6, "C6", "bateria a 12 % · sem reserva final", "seeds_c6_op", [(18, "18 → 15 kWh (limite de 10 %)", 4)])):
        a, b = painel(x, 166, 836, 482, cor, c, cond, nome, notas); s += a; h += b
    h += legenda(656)
    for i, (t, a, b, chip) in enumerate((
            ("Hidrogênio consumido", ("2,156&nbsp;kg", "R$&nbsp;21,56"), ("4,163&nbsp;kg", "R$&nbsp;41,63"), "1,93&nbsp;×"),
            ("Energia suprida pela PEMFC", ("49,6&nbsp;%", "entre 10 e 19,9&nbsp;kW"), ("88,0&nbsp;%", "entre 20 e 44,3&nbsp;kW"), None),
            ("Papel da bateria", ("Variações", "acompanha a demanda"), ("Picos", "recarregada pela PEMFC"), None))):
        a_, b_ = tile(110 + i * 576, 700, 548, 208, t, a, b, chip, destaque=(i == 2)); s += a_; h += b_
    body = ('<link rel="stylesheet" href="assets/fonts_seeds.css">' + f'<div class="tt">{TIT}</div>'
            + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(33))
    open(os.path.join(D, "S33b_c5c6.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM + ".sd{position:absolute}", body=body))


if __name__ == "__main__":
    slide()
