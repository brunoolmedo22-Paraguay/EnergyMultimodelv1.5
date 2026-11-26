"""Slide 33 (deck) — Resultados: embarcação híbrida EMB-H2-120 (C5), no estilo aprovado do slide 32.

Figura (esquerda): a missão de 120 min desenhada a partir da rodada 055096cf (marco `seeds2-trama-frame`, valores gravados):
potência por recurso empilhada (PEMFC na base, solar, descarga da bateria) × demanda; carga da bateria hachurada abaixo de zero;
embaixo, energia da bateria nas fronteiras com a reserva final de 45 kWh.
Valores gravados: PEMFC 19,45 / 17,36 / 19,90 / 17,88 / 10,00 / 14,83 / 17,88 / 17,88 kW; bateria (descarga) 36,23 / 0 / 8,02 /
27,00 / 0 / 38,27 / 2,07 / 7,64 kW, carga 5,80 kW às 13:00; solar 3,09 ×4 e 2,96 ×4 kW; demanda 58,77 / 20,44 / 31,01 / 47,97 / 7,16 /
56,06 / 22,92 / 28,49 kW; energia 75,00 → … → 45,00 kWh.
Texto (Seção 7.2): 68,21 kWh = PEMFC 33,80 (49,6 %) + bateria líquida 28,36 (41,6 %) + solar 6,05 (8,9 %); PEMFC 10,00–19,90 kW;
correlação bateria × demanda 0,986; 62,3 % da energia pela bateria nos 3 intervalos de maior demanda; 79,9 % pela PEMFC nos 4 de
menor; consumo específico 0,0603 kg/kWh a 10 kW → 0,0768 kg/kWh na potência máxima; 2,156 kg de H₂ (R$ 21,56), modelo dinâmico
também 2,156 kg (subestimação máxima 0,0002 kg); missão termina com 45,00 kWh."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, LIGHT, T, div
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = "Resultados — embarcação híbrida (C5)"
REF = "Tabela 6.3, Fig. 7.3 e Seção 7.2 do artigo · valores gravados na rodada 055096cf (C5) · contexto de ensaio"
PEM, BAT, SOL, TEAL = "#1BA39C", "#7B6CF6", "#D9A21B", "#1F7A6D"
FC = [19.45, 17.36, 19.90, 17.88, 10.00, 14.83, 17.88, 17.88]
PD = [36.23, 0.0, 8.02, 27.00, 0.0, 38.27, 2.07, 7.64]
PC = [0, 0, 0, 0, 5.80, 0, 0, 0]
FV = [3.09, 3.09, 3.09, 3.09, 2.96, 2.96, 2.96, 2.96]
DEM = [58.77, 20.44, 31.01, 47.97, 7.16, 56.06, 22.92, 28.49]
E = [75.00, 65.47, 65.47, 63.36, 56.25, 57.63, 47.56, 47.01, 45.00]
HORAS = ["12:00", "12:15", "12:30", "12:45", "13:00", "13:15", "13:30", "13:45", "14:00"]
DEFS = (f'<defs><pattern id="hb" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        f'<rect width="8" height="8" fill="#fff"/><rect width="3.5" height="8" fill="{BAT}"/></pattern></defs>')


def nf(v, d=1):
    return f"{v:.{d}f}".replace(".", ",")


def figura():
    s, h = DEFS, ""
    px, pw = 196, 760
    cw = pw / 8
    X = lambda k: px + k * cw
    # legenda
    leg = [(PEM, "PEMFC", "q"), (SOL, "Solar", "q"), (BAT, "Bateria", "q"), (NAVY, "Demanda", "l"), (BAT, "Carga da bateria", "h")]
    xl = 110
    for cor, t, tipo in leg:
        if tipo == "q":
            s += f'<rect x="{xl}" y="182" width="22" height="22" rx="5" fill="{cor}"/>'
        elif tipo == "l":
            s += f'<rect x="{xl}" y="191" width="30" height="4" rx="2" fill="{cor}"/>'
        else:
            s += f'<rect x="{xl}" y="182" width="22" height="22" rx="5" fill="url(#hb)" stroke="{BAT}" stroke-width="1.5"/>'
        h += div(xl + (38 if tipo == "l" else 30), 178, 260, None, t, "p", "font-size:22px")
        xl += {"PEMFC": 134, "Solar": 118, "Bateria": 132, "Demanda": 158}.get(t, 220)
    # painel de potência
    top, base, vmax, vmin = 236, 492, 70.0, -10.0
    Y = lambda v: base - (base - top) * (v - vmin) / (vmax - vmin)
    h += div(110, 226, 80, None, "kW", "", "font:700 20px Manrope;color:#9AA5B1")
    for t in (0, 20, 40, 60):
        s += f'<line x1="{px}" x2="{px+pw}" y1="{Y(t)}" y2="{Y(t)}" stroke="{"#AEB8C2" if t == 0 else "#E8EDEC"}" stroke-width="1.5"/>'
        s += T(px - 12, Y(t) + 7, str(t), 20, 600, "#9AA5B1", anchor="end")
    for k in range(8):
        x0, bw = X(k) + 10, cw - 20
        acc = 0
        for v, cor in ((FC[k], PEM), (FV[k], SOL), (PD[k], BAT)):
            if v > 1e-6:
                s += f'<rect x="{x0}" y="{Y(acc+v)}" width="{bw}" height="{Y(acc)-Y(acc+v)}" fill="{cor}"/>'
            acc += v
        if FC[k] > 12:                                    # 13:00 (10 kW) já é nomeado na nota ao lado
            s += T(X(k) + cw / 2, Y(FC[k] / 2) + 7, nf(FC[k]), 20, 800, "#fff", anchor="middle")
        if PC[k] > 0:
            s += f'<rect x="{x0}" y="{Y(0)}" width="{bw}" height="{Y(-PC[k])-Y(0)}" fill="url(#hb)" stroke="{BAT}" stroke-width="1.5"/>'
    pts = []
    for k in range(8):
        pts += [(X(k), Y(DEM[k])), (X(k + 1), Y(DEM[k]))]
    d = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts)
    s += f'<path d="{d}" fill="none" stroke="{NAVY}" stroke-width="4" stroke-linejoin="round"/>'
    h += div(X(5) + 6, Y(0) + 4, 300, None, "← PEMFC no mínimo (10 kW)<br>&nbsp;&nbsp;&nbsp;&nbsp;carrega a bateria", "", f"font:600 20px/1.2 Manrope;color:{BAT}")
    # painel de energia da bateria
    t2, b2, e0, e1 = 566, 668, 40.0, 80.0
    YE = lambda v: b2 - (b2 - t2) * (v - e0) / (e1 - e0)
    h += div(110, 522, 600, None, "Energia na bateria [kWh]", "", "font:700 22px Manrope;color:#4A5568")
    for t in (40, 60, 80):
        s += f'<line x1="{px}" x2="{px+pw}" y1="{YE(t)}" y2="{YE(t)}" stroke="#E8EDEC" stroke-width="1.5"/>' + T(px - 12, YE(t) + 7, str(t), 20, 600, "#9AA5B1", anchor="end")
    s += f'<line x1="{px}" x2="{px+pw}" y1="{YE(45)}" y2="{YE(45)}" stroke="{NAVY}" stroke-width="2.5" stroke-dasharray="8 6"/>'
    h += div(px + 10, YE(45) - 30, 360, None, "reserva final exigida: 45 kWh", "", f"font:600 20px Manrope;color:{NAVY}")
    s += f'<polyline points="{" ".join(f"{X(k)},{YE(e)}" for k, e in enumerate(E))}" fill="none" stroke="{BAT}" stroke-width="4" stroke-linejoin="round"/>'
    for k, e in enumerate(E):
        s += f'<circle cx="{X(k)}" cy="{YE(e)}" r="6" fill="{BAT}" stroke="#fff" stroke-width="2"/>'
    s += T(X(0) + 12, YE(75) - 12, "75", 20, 800, BAT) + T(X(8) - 8, YE(45) - 16, "45,00", 22, 800, BAT, anchor="end")
    for k in range(0, 9, 2):
        s += T(X(k), b2 + 30, HORAS[k], 20, 600, "#9AA5B1", anchor="middle")
    return s, h


def cartao_direita(x, y, w, hc):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{hc}" rx="24" fill="{LIGHT}"/>'
    h = div(x + 30, y + 22, w - 60, None, "Quem supriu os 68,21 kWh da missão", "", "font:700 26px Gelasio,serif;color:#14213D")
    bx, bw, by = x + 30, w - 60, y + 76
    parts = [(PEM, .496, "PEMFC", "49,6&nbsp;%"), (BAT, .416, "Bateria", "41,6&nbsp;%"), (SOL, .089, "", "")]
    acc = 0
    for cor, f, nome, p in parts:
        s += f'<rect x="{bx+bw*acc:.1f}" y="{by}" width="{bw*f:.1f}" height="50" fill="{cor}"/>'
        if nome:
            h += div(bx + bw * acc + 14, by + 10, bw * f - 20, None, f"{nome} {p}", "", "font:700 22px Manrope;color:#fff;white-space:nowrap")
        acc += f
    h += div(bx + bw - 200, by + 58, 200, None, "Solar 8,9&nbsp;%", "", f"font:700 22px Manrope;color:#A57A0E;text-align:right")
    linhas = [(PEM, "PEMFC cobre a base", "Opera entre <b>10 e 19,9&nbsp;kW</b> (de até 50 kW) e supre 79,9&nbsp;% da energia nos intervalos de menor demanda."),
              (BAT, "Bateria cobre as variações", "Acompanha a demanda (correlação <b>0,986</b>) e entrega 62,3&nbsp;% da energia nos três picos."),
              (NAVY, "Por quê", "O H₂ rende menos em potência alta: <b>0,060 → 0,077&nbsp;kg/kWh</b>. Cobrir os picos com a PEMFC gastaria mais.")]
    yy = y + 172
    for cor, t, d in linhas:
        s += f'<rect x="{x+30}" y="{yy+6}" width="6" height="86" rx="3" fill="{cor}"/>'
        h += div(x + 52, yy, w - 82, None, f'<div style="font:700 23px Manrope;color:#14213D;margin-bottom:4px">{t}</div>{d}', "p", "font-size:22px;line-height:1.35")
        yy += 118
    return s, h


def cartoes_baixo(yc, hc):
    s = f'<rect x="110" y="{yc}" width="836" height="{hc}" rx="24" fill="{LIGHT}"/>'
    h = div(144, yc + 20, 780, None, "Reserva final cumprida", "", "font:700 26px Gelasio,serif;color:#14213D")
    h += div(144, yc + 64, 360, None, "45,00&nbsp;kWh", "", f"font:700 56px/1.1 Gelasio,serif;color:{BAT};white-space:nowrap")
    h += div(144, yc + 140, 340, None, "exigido: ≥ 45&nbsp;kWh (30&nbsp;%)", "p", "font-size:22px")
    h += div(520, yc + 62, 400, None, "Começou com 75&nbsp;kWh. O valor futuro levou ao MPC a reserva que está além da sua janela de 1&nbsp;h.",
             "p", "font-size:22px;line-height:1.35")
    s += f'<rect x="974" y="{yc}" width="836" height="{hc}" rx="24" fill="{TEAL}"/>'
    h += div(1008, yc + 20, 780, None, "Hidrogênio consumido", "", "font:700 26px Gelasio,serif;color:#fff")
    h += div(1008, yc + 64, 420, None, '2,156&nbsp;kg<span style="font:700 26px Manrope;margin-left:14px;color:#BFE3DC">R$&nbsp;21,56</span>', "",
             "font:700 56px/1.1 Gelasio,serif;color:#fff;white-space:nowrap")
    h += div(1008, yc + 140, 440, None, "0,0638&nbsp;kg/kWh em média", "", "font:500 22px Manrope;color:#DDEFEC")
    h += div(1490, yc + 64, 300, None, 'Modelo dinâmico:<br><b style="color:#fff">2,156&nbsp;kg</b><br>'
             '<span style="color:#BFE3DC">diferença máx. 0,0002&nbsp;kg</span>', "", "font:500 22px/1.38 Manrope;color:#DDEFEC")
    s += f'<line x1="1466" x2="1466" y1="{yc+66}" y2="{yc+170}" stroke="#5FA89C" stroke-width="2"/>'
    return s, h


def slide():
    s, h = "", ""
    for f in (figura, lambda: cartao_direita(1060, 166, 750, 530), lambda: cartoes_baixo(722, 186)):
        a, b = f(); s += a; h += b
    body = (f'<div class="tt">{TIT}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(33))
    open(os.path.join(D, "S33_c5.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide()
