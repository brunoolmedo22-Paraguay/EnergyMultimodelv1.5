"""Slides 24–27 (deck) — estudos de caso em DOIS slides cada (pedido do responsável, a partir da proposta B):
  · Dados de entrada: as entradas do cenário num gráfico com três eixos verticais (demanda, irradiância, temperatura) e, embaixo,
    o sinal econômico (tarifa A4 Verde na CT-046; preço do H₂ na embarcação). A potência FV NÃO aparece: é resultado do modelo.
  · Configuração no SEEDS: configurações (C1–C4 / C5–C6), malha temporal e janelas, recursos e estratégia do EMS.

Fontes: Tabelas 6.1–6.3 e Seções 6.2–6.3 do artigo. Séries = previsões gravadas no cenário da rodada de referência dos exemplos
persistentes (`seeds2/exemplos`, C4 e C5), em `dados/*.json`: demanda (CSV do cenário), clima (CSV original, procedência sintética)
e tarifa de decisão. Conferência: CT-046 1.967,15 kWh, 100 / 81,96 / 58,24 kW, GHI máx. 970 W/m², 7,125 kWh/m², 15,0–26,7 °C;
EMB 68,21 kWh, 7,16–58,77 kW, média 34,10 kW."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, SLATE, LIGHT, LINE, T, div
from gerar_slide8 import rodape
from gerar_slide24_25 import DEFS, CT, EMB, MUTED, PONTA, configs, ficha_html, SOLAR

D = os.path.dirname(os.path.abspath(__file__))
TEMP = "#B5478B"          # temperatura (cor própria, distinta dos recursos)
GHI = "#C99412"           # irradiância (família solar, mais escura para leitura)


def serie_clima(sr):
    c = sr["clima"]
    return c["ghi_W_m2"], c["temperatura_C"]


CASOS = {
    "ct": dict(
        n=(24, 25), nome="CT-046", serie=CT,
        tit_e="Dados de entrada da microrrede CT-046", tit_c="Configuração da CT-046 no SEEDS",
        dmax=120, dt=(0, 40, 80, 120),
        xt=[(0, "0 h"), (6, "6 h"), (12, "12 h"), (18, "18 h"), (24, "24 h")], h0=0, h1=24,
        ponta=(18, 21),
        eco=dict(nome="Tarifa", un="R$/kWh", vmax=2.0, ticks=(0, 1, 2), dec=0,
                 blocos=[(0, 18, 0.44234), (18, 21, 1.93894), (21, 24, 0.44234)],
                 rot=[(9, "0,44 fora de ponta"), (19.5, "1,94 na ponta")]),
        cards=[("Demanda", "ANEEL [37]", NAVY, "Curva CT-046 de dia útil, escalada a <b>100&nbsp;kW</b> de pico; <b>1.967&nbsp;kWh</b> no dia"),
               ("Irradiância", "Sintética", GHI, "Dia de céu claro, <b>máx. 970&nbsp;W/m²</b>; 7,125&nbsp;kWh/m² no dia"),
               ("Temperatura", "Sintética", TEMP, "Ambiente de <b>15,0 a 26,7&nbsp;°C</b>"),
               ("Tarifa", "ANEEL, COPEL [38, 39]", PONTA, "A4 Horária Verde: <b>1,94</b> na ponta e <b>0,44&nbsp;R$/kWh</b> fora dela (4,4&nbsp;×)")],
        nota="Foz do Iguaçu (PR) · 2/10/2026 · 96 intervalos de 15 min",
        ref_e="Tabela 6.1 do artigo · séries do cenário da rodada de referência C4 · ANEEL [37, 38], COPEL [39]",
        configs=[("C1", ["grid"], None), ("C2", ["grid", "sun"], None), ("C3", ["grid", "bat"], None), ("C4", ["grid", "sun", "bat"], None)],
        malha=dict(n=96, N=8, m=1, k=36, rot_n="96 intervalos de 15 min · 24 h", rot_N="N = 8 (2 h)", rot_HL="H<sub>L</sub> = 96 (24 h), encurta até o fim do dia",
                   ticks=[(0, "0 h"), (24, "6 h"), (48, "12 h"), (72, "18 h"), (96, "24 h")]),
        grupos=[("Recursos", [
                    ("Fotovoltaica", "58 kWp · 100 × CS7L-580MS", "Fabricante [40]"),
                    ("Bateria", "200 kWh · 50 kW · SOC 10–90 %", "Declarado"),
                    ("Rede (PCC)", "Só importação, até 200 kW", "Declarado")]),
                ("Execução", [
                    ("Duração", "24 h em 96 × 15 min", ""),
                    ("Demanda", "Crítica: atendida sempre", ""),
                    ("Realização", "Igual à previsão (ensaio)", "")]),
                ("Gerenciamento", [
                    ("Objetivo", "Custo de importação", ""),
                    ("Condição final", "Nenhuma declarada", ""),
                    ("Valor futuro", "PWL, 5 a 17 pontos", ""),
                    ("Aceitação", "Ótimo, sem gap, até 60 s", "")])],
        nota_cfg="Mesma demanda, tarifa, clima e estratégia em C1–C4; muda só a composição. A bateria inicia em 30&nbsp;% (60&nbsp;kWh).",
        ref_c="Tabelas 6.1 e 6.2 do artigo · Canadian Solar [40]"),
    "emb": dict(
        n=(26, 27), nome="EMB-H2-120", serie=EMB,
        tit_e="Dados de entrada da embarcação EMB-H2-120", tit_c="Configuração da EMB-H2-120 no SEEDS",
        dmax=60, dt=(0, 20, 40, 60),
        xt=[(12, "12:00"), (12.5, "12:30"), (13, "13:00"), (13.5, "13:30"), (14, "14:00")], h0=12, h1=14,
        ponta=None,
        eco=dict(nome="Hidrogênio", un="R$/kg", vmax=12, ticks=(0, 6, 12), dec=0,
                 blocos=[(12, 14, 10.0)], rot=[(13, "10 R$/kg (preço sintético)")]),
        cards=[("Demanda", "Registro do projeto", NAVY, "Propulsão em médias de 15 min, com <b>68,21&nbsp;kWh</b> na missão"),
               ("Irradiância", "Sintética", GHI, "Série de 5 min, <b>931 a 970&nbsp;W/m²</b> (meio-dia)"),
               ("Temperatura", "Sintética", TEMP, "Ambiente de <b>23,4 a 24,5&nbsp;°C</b>"),
               ("Hidrogênio", "Sintético", PONTA, "Preço de <b>10&nbsp;R$/kg</b>, sem cotação de mercado")],
        nota="Missão de 2/10/2026, 12:00–14:00 · 8 intervalos de 15 min",
        ref_e="Tabela 6.3 do artigo · séries do cenário da rodada de referência C5 · ciclo de propulsão de 37,85 min repetido; pico original 63,06 kW, reduzido pelas médias de 15 min",
        configs=[("C5", ["sun", "bat", "h2"], (.50, .30)), ("C6", ["sun", "bat", "h2"], (.12, None))],
        malha=dict(n=8, N=4, m=1, k=2, rot_n="8 intervalos de 15 min · 120 min", rot_N="N = 4 (1 h)", rot_HL="H<sub>L</sub> = 8 (120 min), encurta até o fim da missão",
                   ticks=[(0, "12:00"), (2, "12:30"), (4, "13:00"), (6, "13:30"), (8, "14:00")]),
        grupos=[("Recursos", [
                    ("Fotovoltaica", "3,48 kWp · 6 × CS7L-580MS", "Fabricante [40]"),
                    ("Bateria", "150 kWh · 75 kW · SOC 10–90 %", "Declarado"),
                    ("PEMFC", "≈ 50 kW, mín. 10 kW, sempre ligada", "Aprox. [41]")]),
                ("Execução", [
                    ("Duração", "120 min em 8 × 15 min", ""),
                    ("Operação", "Isolada, demanda crítica", ""),
                    ("Realização", "Igual à previsão (ensaio)", "")]),
                ("Gerenciamento", [
                    ("Objetivo", "Consumo de hidrogênio", ""),
                    ("Condição final", "C5: ≥ 45 kWh · C6: nenhuma", ""),
                    ("Valor futuro", "PWL, 5 a 50 pontos", ""),
                    ("Aceitação", "Ótimo, sem gap, até 60 s", "")])],
        nota_cfg="Mesma composição e missão; mudam o estado inicial da bateria e a reserva exigida ao final. PEMFC ligada a 30&nbsp;kW no início.",
        ref_c="Tabelas 6.2 e 6.3 do artigo · Canadian Solar [40] · Horizon VLIIPro50-22 [41] (parametrização aproximada, não calibração)"),
}


def fmt(v, dec=0):
    return f"{v:.{dec}f}".replace(".", ",")


# ------------------------------------------------------------------ gráfico de entradas: três eixos verticais + sinal econômico
def entradas(c, x, y, w, h):
    """Painel principal (demanda à esquerda; irradiância e temperatura à direita) e painel do sinal econômico, com o mesmo eixo do tempo."""
    sr = c["serie"]
    d = sr["demanda_kW"]
    ghi, tmp = serie_clima(sr)
    h0, h1 = c["h0"], c["h1"]
    xl, xr = x + 92, x + w - 222                 # área de desenho (eixos à direita em xr e xr + 96)
    he = 104                                     # painel do sinal econômico
    hp = h - he - 84
    yb = y + hp
    ye = yb + 40
    X = lambda t: xl + (xr - xl) * (t - h0) / (h1 - h0)
    Yd = lambda v: yb - hp * v / c["dmax"]
    Yg = lambda v: yb - hp * v / 1200
    Yt = lambda v: yb - hp * (v - 0) / 36
    s, ht = "", ""
    if c["ponta"]:
        a, b = c["ponta"]
        s += f'<rect x="{X(a)}" y="{y}" width="{X(b)-X(a)}" height="{ye+he-y}" fill="{PONTA}" opacity=".08"/>'
        s += T((X(a) + X(b)) / 2, y + 26, "Ponta", 22, 700, PONTA, anchor="middle")
    # grade e eixos (marcas alinhadas: 4 linhas)
    for i in range(4):
        yy = yb - hp * i / 3
        s += f'<line x1="{xl}" x2="{xr}" y1="{yy}" y2="{yy}" stroke="#E3E9E8" stroke-width="1.5"/>'
        s += T(xl - 12, yy + 8, fmt(c["dmax"] * i / 3), 22, 700, NAVY, anchor="end")
        s += T(xr + 12, yy + 8, fmt(1200 * i / 3), 22, 700, GHI)
        s += T(xr + 144, yy + 8, fmt(36 * i / 3), 22, 700, TEMP)
    for xx, cor in ((xl, NAVY), (xr, GHI), (xr + 132, TEMP)):
        s += f'<line x1="{xx}" x2="{xx}" y1="{y}" y2="{yb}" stroke="{cor}" stroke-width="2.5"/>'
    # títulos dos eixos (verticais)
    for xx, txt, cor in ((x + 14, "Demanda (kW)", NAVY), (xr + 96, "Irradiância (W/m²)", GHI), (xr + 210, "Temperatura (°C)", TEMP)):
        s += f'<text x="{xx}" y="{y+hp/2}" transform="rotate(-90 {xx} {y+hp/2})" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="22" fill="{cor}">{txt}</text>'

    def degraus(vs, t0, dt, Y):
        pts = []
        for i, v in enumerate(vs):
            pts += [(X(t0 + i * dt), Y(v)), (X(t0 + (i + 1) * dt), Y(v))]
        return "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts)
    dtd = (h1 - h0) / len(d)
    dtc = (h1 - h0) / len(ghi)
    ld = degraus(d, h0, dtd, Yd)
    s += f'<path d="{ld} L{X(h1):.1f} {yb} L{X(h0):.1f} {yb} Z" fill="url(#gd)"/><path d="{ld}" fill="none" stroke="{NAVY}" stroke-width="3.5" stroke-linejoin="round"/>'
    s += f'<path d="{degraus(ghi, h0, dtc, Yg)}" fill="none" stroke="{GHI}" stroke-width="3" stroke-linejoin="round"/>'
    s += f'<path d="{degraus(tmp, h0, dtc, Yt)}" fill="none" stroke="{TEMP}" stroke-width="3" stroke-linejoin="round" stroke-dasharray="10 6"/>'
    s += f'<line x1="{xl}" x2="{xr}" y1="{yb}" y2="{yb}" stroke="{NAVY}" stroke-width="2"/>'
    # sinal econômico
    e = c["eco"]
    Ye = lambda v: ye + he - he * v / e["vmax"]
    pts = []
    for a, b, v in e["blocos"]:
        pts += [(X(a), Ye(v)), (X(b), Ye(v))]
    le = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in pts)
    s += f'<path d="{le} L{X(h1)} {ye+he} L{X(h0)} {ye+he} Z" fill="{PONTA}" opacity=".12"/><path d="{le}" fill="none" stroke="{PONTA}" stroke-width="3.5"/>'
    s += f'<line x1="{xl}" x2="{xl}" y1="{ye}" y2="{ye+he}" stroke="{PONTA}" stroke-width="2.5"/>'
    for v in e["ticks"]:
        s += T(xl - 12, Ye(v) + 8, fmt(v), 22, 700, PONTA, anchor="end")
    s += f'<line x1="{xl}" x2="{xr}" y1="{ye+he}" y2="{ye+he}" stroke="{NAVY}" stroke-width="2"/>'
    s += f'<text x="{x+14}" y="{ye+he/2}" transform="rotate(-90 {x+14} {ye+he/2})" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="20" fill="{PONTA}">{e["un"]}</text>'
    for t, lab in e["rot"]:
        v = next(v for a, b, v in e["blocos"] if a <= t < b)
        s += T(X(t), Ye(v) - 12, lab, 22, 700, PONTA, anchor="middle")
    for t, lab in c["xt"]:
        s += f'<line x1="{X(t)}" x2="{X(t)}" y1="{ye+he}" y2="{ye+he+7}" stroke="{NAVY}" stroke-width="2"/>'
        s += T(X(t), ye + he + 34, lab, 22, 600, MUTED, anchor="middle")
    return s, ht


def cartoes(c, x, y, w, h, cols=4, gap=22):
    """Uma ficha por entrada: nome com a cor da curva, procedência e o essencial."""
    s, ht = "", ""
    k = len(c["cards"])
    linhas = -(-k // cols)
    cw = (w - gap * (cols - 1)) / cols
    ch = (h - gap * (linhas - 1)) / linhas
    for i, (nome, prov, cor, txt) in enumerate(c["cards"]):
        cx, cy = x + (i % cols) * (cw + gap), y + (i // cols) * (ch + gap)
        s += f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="20" fill="{LIGHT}"/>'
        traco = "stroke-dasharray:10 6;" if cor == TEMP else ""
        s += f'<line x1="{cx+24}" x2="{cx+64}" y1="{cy+38}" y2="{cy+38}" stroke="{cor}" stroke-width="5" stroke-linecap="round" style="{traco}"/>'
        ht += div(cx + 76, cy + 20, cw - 100, None, nome, "", "font:700 26px Gelasio,serif;color:#14213D")
        ht += div(cx + 24, cy + 62, cw - 48, None, prov, "p", "font-size:22px;color:#1F7A6D;font-weight:700")
        ht += div(cx + 24, cy + 96, cw - 48, None, txt, "p", "font-size:22px;line-height:1.4")
    return s, ht


def salvar(c, nome, tit, n, ref, s, h):
    body = (f'<div class="tt">{tit}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>'
            + h + f'<div class="ref">{ref}</div>' + rodape(n))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


# ===================================================================== Entradas · E1: gráfico em largura total, quatro fichas embaixo
def e1(k):
    c = CASOS[k]
    s, h = "", ""
    h += div(110, 160, 1700, None, c["nota"], "p", "font-size:24px;color:#4A5568")
    a, b = entradas(c, 110, 236, 1700, 470)
    s += a; h += b
    a, b = cartoes(c, 110, 728, 1700, 186)
    s += a; h += b
    salvar(c, f"S{c['n'][0]}_E1_entradas", c["tit_e"], c["n"][0], c["ref_e"], s, h)


# ===================================================================== Entradas · E2: gráfico à esquerda, fichas empilhadas à direita
def e2(k):
    c = CASOS[k]
    s, h = "", ""
    h += div(110, 160, 1200, None, c["nota"], "p", "font-size:24px;color:#4A5568")
    s += f'<rect x="110" y="212" width="1180" height="700" rx="26" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
    a, b = entradas(c, 130, 260, 1140, 620)
    s += a; h += b
    a, b = cartoes(c, 1320, 166, 490, 746, cols=1, gap=16)
    s += a; h += b
    salvar(c, f"S{c['n'][0]}_E2_entradas", c["tit_e"], c["n"][0], c["ref_e"], s, h)


# ------------------------------------------------------------------ malha temporal da missão (instância do slide 14)
def malha(c, x, y, w):
    m = c["malha"]
    n, N, k = m["n"], m["N"], m["k"]
    cw = w / n
    hc = 46
    s, ht = "", ""
    for i in range(n):
        if i < k:
            f = "#C9D3DD"
        elif i < k + m["m"]:
            f = "#1F7A6D"
        elif i < k + N:
            f = "#9ED3CB"
        else:
            f = "#E3E9E8"
        g = 1 if n > 20 else 4
        s += f'<rect x="{x+i*cw+g/2}" y="{y}" width="{cw-g}" height="{hc}" rx="{2 if n > 20 else 8}" fill="{f}"/>'
    # janela do MPC e horizonte longo
    xa, xb, xe = x + k * cw, x + (k + N) * cw, x + w
    s += f'<path d="M{xa} {y-12} V{y-24} H{xb} V{y-12}" fill="none" stroke="#1F7A6D" stroke-width="3"/>'
    ht += div(xa - 10, y - 66, 400, None, f'<b style="color:#1F7A6D">Janela do MPC: {m["rot_N"]}</b>', "p", "font-size:22px")
    s += f'<path d="M{xa} {y+hc+12} V{y+hc+24} H{xe} V{y+hc+12}" fill="none" stroke="#C0532F" stroke-width="3"/>'
    ht += div(xa, y + hc + 32, xe - xa, None, f'<span style="color:#C0532F;font-weight:800">Horizonte longo: {m["rot_HL"]}</span>', "p", "font-size:22px")
    s += T(xa + cw / 2, y + hc / 2 + 8, "m", 22, 800, "#fff", "Gelasio", anchor="middle", it=True) if cw > 30 else ""
    for i, lab in m["ticks"]:
        s += T(x + i * cw, y + hc + 90, lab, 22, 600, MUTED, anchor="middle")
    lx, ly = x, y + hc + 118
    for cor, lab in (("#C9D3DD", "Já aplicado"), ("#1F7A6D", "Aplicado agora (m = 1)"), ("#9ED3CB", "Previsto na janela"), ("#E3E9E8", "Além da janela")):
        wi = 66 + 12 * len(lab)
        if lx + wi - 30 > x + w:
            lx, ly = x, ly + 40
        s += f'<rect x="{lx}" y="{ly}" width="26" height="26" rx="5" fill="{cor}"/>'
        ht += div(lx + 36, ly - 2, 300, None, lab, "p", "font-size:22px")
        lx += wi
    return s, ht


# ===================================================================== Configuração · K1: configurações em cima | ficha em três colunas
def k1(k):
    c = CASOS[k]
    s, h = "", ""
    cfg = c["configs"]
    hc = 116 if len(cfg) == 4 else 140
    a, b = configs(c, 110, 172, 1700, hc)
    s += a; h += b
    h += div(110, 186 + hc, 1700, None, c["nota_cfg"], "p", "font-size:22px")
    a, b = malha(c, 150, 304 + hc, 1620)
    s += a; h += b
    cols = [(110, 540), (690, 540), (1270, 540)]
    for g, (cx, cw) in zip(c["grupos"], cols):
        h += div(cx, 668, cw, None, ficha_html(c, [g], cw))
    salvar(c, f"S{c['n'][1]}_K1_config", c["tit_c"], c["n"][1], c["ref_c"], s, h)


# ===================================================================== Configuração · K2: ficha à direita, configurações e malha à esquerda
def k2(k):
    c = CASOS[k]
    s, h = "", ""
    a, b = configs(c, 110, 172, 1040, 160 if len(c["configs"]) == 2 else 150)
    s += a; h += b
    h += div(110, 346, 1040, None, c["nota_cfg"], "p", "font-size:22px")
    s += f'<rect x="110" y="450" width="1040" height="460" rx="26" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
    h += div(140, 472, 900, None, "Malha temporal e janelas", "", "font:700 26px Gelasio,serif;color:#14213D")
    a, b = malha(c, 150, 610, 960)
    s += a; h += b
    s += f'<rect x="1190" y="166" width="620" height="744" rx="26" fill="{LIGHT}"/>'
    h += div(1222, 184, 560, None, ficha_html(c, c["grupos"], 560))
    salvar(c, f"S{c['n'][1]}_K2_config", c["tit_c"], c["n"][1], c["ref_c"], s, h)


if __name__ == "__main__":
    for kk in ("ct", "emb"):
        e1(kk)
        e2(kk)
        k1(kk)
        k2(kk)
