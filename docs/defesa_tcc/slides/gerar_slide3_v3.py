"""Slide 3 (Contexto) — v3. Dados CONFERIDOS nos documentos originais (baixados em 25/11/2026):

[1] IRENA, Renewable Power Generation Costs in 2024, tabela de resumo (p. com «Solar PV 5 283 691 -87% … 0.417 0.043 -90%»):
    LCOE solar FV 0,417 → 0,043 USD/kWh (−90 %); eólica terrestre 0,113 → 0,034 USD/kWh (−70 %), 2010 → 2024.
[3] EPE, BEN 2026 — Relatório Síntese, ano base 2025:
    p. 50 «Geração MMGD total (GWh)», série solar 2016–2025. Rótulos impressos: 2020 4.764 · 2021 9.019 · 2022 17.378 ·
    2023 29.813 · 2024 41.006 · 2025 53.144 GWh. 2016–2019 sem rótulo no gráfico: lidos do desenho vetorial do próprio PDF
    (escala calibrada pelo rótulo de 2025; conferência: 2024 → 41.014, 2020 → 4.774): ≈ 48 · 161 · 533 · 1.648 GWh.
    p. 50: MMGD solar = 7,0 % da geração total e 60,3 % da geração solar em 2025.
    p. 52: capacidade de MMGD solar 35.892 MW (2024) → 44.742 MW (2025); capacidade solar total 64.793 MW (p. 51).
"""
import os
D = os.path.dirname(os.path.abspath(__file__))

SOLAR, WIND, PEM, BAT, REDE, NAVY, SLATE, TEAL = "#D9A21B", "#4C8DD6", "#1BA39C", "#7B6CF6", "#E0524F", "#14213D", "#4A5568", "#1F7A6D"
ANOS = list(range(2016, 2026))
MMGD = [48, 161, 533, 1648, 4764, 9019, 17378, 29813, 41006, 53144]   # GWh (2016–2019 lidos do gráfico vetorial)
ROTULADO = {2020, 2021, 2022, 2023, 2024, 2025}
# Geração eólica e solar (TWh) e participação na geração total (%) — OFICIAL: EPE, BEN Séries Históricas Completas,
# «Capítulo 5 (Balanço dos Centros de Transformação) – 1970 a 2025.xlsx», TABELA 5.3 (Centrais elétricas – total, serviço
# público + autoprodução), linhas «GERAÇÃO DE ELETRICIDADE GWh», «EÓLICA», «SOLAR» (solar inclui MMGD: 2025 = 88.140 GWh).
ANOS_ES = list(range(2007, 2026))
EOL_GWH = [662.8, 1183, 1238, 2177, 2704.5, 5050.0, 6578.4, 12240.3, 21625.7, 33488.9, 42373.3, 48475.1, 55985.6, 57050.7, 72286.0, 81631.6, 95800.7, 107654.0, 116488.3]
SOL_GWH = [0, 0, 0, 0, 0, 1.6, 4.8, 16.1, 58.9, 85.3, 831.8, 3461.4, 6654.6, 10748.3, 16752.3, 30126.5, 50632.9, 70664.7, 88140.5]
TOT_GWH = [445148.9, 463171.6, 466158.1, 515798.7, 531758.2, 557939.1, 577364.0, 596286.4, 586646.8, 584059.0, 595574.3, 607203.1, 633032.6, 628763.7, 656380.5, 677150.1, 708119.2, 751335.5, 775895.9]
EOL = [v / 1000 for v in EOL_GWH]
SOL = [v / 1000 for v in SOL_GWH]
ES = [e + s_ for e, s_ in zip(EOL, SOL)]
PART = [100 * (e + s_) / t for e, s_, t in zip(EOL_GWH, SOL_GWH, TOT_GWH)]
_k = ANOS_ES.index(2011)
ANOS_ES, EOL, SOL, ES, PART = ANOS_ES[_k:], EOL[_k:], SOL[_k:], ES[_k:], PART[_k:]   # gráfico a partir de 2011   # 2007 0,15 % · 2016 5,75 % · 2025 26,40 %

ICON = {
 "sun": '<circle cx="20" cy="20" r="7" fill="none" stroke="currentColor" stroke-width="3"/><g stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 3v5M20 32v5M3 20h5M32 20h5M8 8l3.5 3.5M28.5 28.5L32 32M8 32l3.5-3.5M28.5 11.5L32 8"/></g>',
 "wind": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 18v19M20 18V4M20 18l12 7M20 18L8 25"/></g><circle cx="20" cy="18" r="3" fill="currentColor"/>',
 "bat": '<rect x="6" y="11" width="25" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="3"/><rect x="32" y="16" width="3" height="8" fill="currentColor"/><rect x="10" y="15" width="11" height="10" fill="currentColor"/>',
 "h2": '<text x="20" y="27" text-anchor="middle" font-family="Manrope,sans-serif" font-weight="800" font-size="19" fill="currentColor">H₂</text>',
 "grid": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M14 37L20 4l6 33M10 12h20M8 20h24M16 29h8"/></g>',
 "home": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><path d="M6 19L20 7l14 12v16H6z"/><path d="M17 35v-9h6v9"/></g>',
 "bld": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><rect x="9" y="5" width="22" height="31"/><path d="M15 11h3M22 11h3M15 18h3M22 18h3M15 25h3M22 25h3M18 36v-5h4v5"/></g>',
 "vil": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><path d="M3 22l9-8 9 8v13H3z"/><path d="M19 20l9-8 9 8v15H21"/></g>',
 "ship": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M4 24h32l-5 9H9z"/><path d="M11 24V15h14v9M17 15V9h6"/></g>',
}
COR = {"sun": SOLAR, "wind": WIND, "h2": PEM, "bat": BAT, "grid": REDE}
NOME = {"sun": "Solar", "wind": "Eólica", "h2": "Célula H₂", "bat": "Bateria", "grid": "Rede"}

# cargas de pequeno porte e as fontes que as alimentam (cada uma com a sua referência do artigo)
CARGAS = [
    ("home", "Residências e comércios", "[3]", ["sun", "grid"]),
    ("bld", "Edificações", "[4]", ["sun", "grid", "bat"]),
    ("vil", "Localidades isoladas", "[5]", ["wind", "sun", "h2", "bat"]),
    ("ship", "Embarcações", "[6]", ["h2", "bat"]),
]


def svgi(k, s, c):
    return f'<svg width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c};flex:none">{ICON[k]}</svg>'


def convergencia(W, H, fontes, carga, rf=22, rl=36):
    """Fontes à esquerda, empilhadas; linhas que convergem para a carga à direita (todas ao mesmo tempo)."""
    n = len(fontes)
    xl = W - rl - 4; yl = H / 2
    xf = rf + 4
    gap = min(2 * rf + 12, (H - 2 * rf - 4) / max(n - 1, 1))
    y0 = yl - gap * (n - 1) / 2
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    for i, k in enumerate(fontes):
        y = y0 + i * gap; c = COR[k]
        x1, x2 = xf + rf, xl - rl
        s.append(f'<path d="M{x1} {y} C{(x1+x2)/2} {y}, {(x1+x2)/2} {yl}, {x2-8} {yl}" fill="none" stroke="{c}" stroke-width="3" stroke-linecap="round"/>')
    s.append(f'<path d="M{xl-rl-14} {yl-8} L{xl-rl-1} {yl} L{xl-rl-14} {yl+8} Z" fill="{NAVY}"/>')
    for i, k in enumerate(fontes):
        y = y0 + i * gap; c = COR[k]
        s.append(f'<circle cx="{xf}" cy="{y}" r="{rf}" fill="#fff" stroke="{c}" stroke-width="2.5"/>'
                 f'<svg x="{xf-rf*.62}" y="{y-rf*.62}" width="{rf*1.24}" height="{rf*1.24}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>')
    s.append(f'<circle cx="{xl}" cy="{yl}" r="{rl}" fill="#fff" stroke="{NAVY}" stroke-width="3"/>'
             f'<svg x="{xl-rl*.6}" y="{yl-rl*.6}" width="{rl*1.2}" height="{rl*1.2}" viewBox="0 0 40 40" style="color:{NAVY}">{ICON[carga]}</svg>')
    s.append("</svg>")
    return "".join(s)


def grafico_es(W, H, fs_lab=26):
    pl, pr, pt, pb = 8, 8, 34, 46
    ymax = 230
    y = lambda v: pt + (H - pt - pb) * (1 - v / ymax)
    n = len(ANOS_ES); gw = (W - pl - pr) / n; bw = gw * .64
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs><linearGradient id="ges" x1="0" y1="1" x2="0" y2="0">'
         f'<stop offset="0" stop-color="{WIND}"/><stop offset="1" stop-color="{SOLAR}"/></linearGradient></defs>']
    for g in (100, 200):
        s.append(f'<line x1="{pl}" x2="{W-pr}" y1="{y(g)}" y2="{y(g)}" stroke="#EEF1F1" stroke-width="1.5"/>'
                 f'<text x="{pl}" y="{y(g)-7}" font-family="Manrope" font-size="15" fill="#9AA5B1">{g} TWh</text>')
    s.append(f'<line x1="{pl}" x2="{W-pr}" y1="{y(0)}" y2="{y(0)}" stroke="#C9D3DD" stroke-width="1.5"/>')
    for i, (a, v, p) in enumerate(zip(ANOS_ES, ES, PART)):
        cx = pl + gw * (i + .5); bx = cx - bw / 2; h = max(y(0) - y(v), 2); r = min(5, h / 2)
        he = max(y(0) - y(EOL[i]), 0); hs = y(0) - y(SOL[i])
        if hs >= 1.5:   # solar em cima (cantos arredondados), eólica embaixo, 2 px de separação
            s.append(f'<rect x="{bx}" y="{y(0)-he}" width="{bw}" height="{he}" fill="{WIND}"/>')
            r2 = min(5, hs / 2)
            ys = y(0) - he - 2
            s.append(f'<path d="M{bx} {ys} V{ys-hs+r2} q0 -{r2} {r2} -{r2} h{bw-2*r2} q{r2} 0 {r2} {r2} V{ys} Z" fill="{SOLAR}"/>')
        else:
            s.append(f'<path d="M{bx} {y(0)} V{y(0)-h+r} q0 -{r} {r} -{r} h{bw-2*r} q{r} 0 {r} {r} V{y(0)} Z" fill="{WIND}"/>')
        if (a - 2011) % 3 == 0 or a == 2025:
            s.append(f'<text x="{cx}" y="{H-14}" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="17" fill="{SLATE}">{a}</text>')
        if a in (2011, 2018, 2025):
            pf = f"{p:.1f}".replace(".", ",") + " %"
            fs = fs_lab if a == 2025 else fs_lab * .75
            anc, xx = ("end", bx + bw) if a == 2025 else ("start", bx) if a == 2011 else ("middle", cx)
            s.append(f'<text x="{xx}" y="{y(v)-12}" text-anchor="{anc}" font-family="Gelasio" font-weight="700" font-size="{fs:.0f}" fill="{NAVY}">{pf}</text>')
    s.append("</svg>")
    return "".join(s)


def grafico_mmgd(W, H, fs_lab=26):
    pl, pr, pt, pb = 8, 8, 30, 46
    ymax = 58000
    y = lambda v: pt + (H - pt - pb) * (1 - v / ymax)
    n = len(ANOS); gw = (W - pl - pr) / n; bw = gw * .62
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    for g in (20000, 40000):
        s.append(f'<line x1="{pl}" x2="{W-pr}" y1="{y(g)}" y2="{y(g)}" stroke="#EEF1F1" stroke-width="1.5"/>'
                 f'<text x="{pl}" y="{y(g)-7}" font-family="Manrope" font-size="15" fill="#9AA5B1">{g//1000} TWh</text>')
    s.append(f'<line x1="{pl}" x2="{W-pr}" y1="{y(0)}" y2="{y(0)}" stroke="#C9D3DD" stroke-width="1.5"/>')
    for i, (a, v) in enumerate(zip(ANOS, MMGD)):
        cx = pl + gw * (i + .5); bx = cx - bw / 2; h = max(y(0) - y(v), 2); r = min(6, h / 2)
        s.append(f'<path d="M{bx} {y(0)} V{y(0)-h+r} q0 -{r} {r} -{r} h{bw-2*r} q{r} 0 {r} {r} V{y(0)} Z" fill="{SOLAR}"/>')
        s.append(f'<text x="{cx}" y="{H-14}" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="17" fill="{SLATE}">{a}</text>')
        if a in (2016, 2020, 2025):
            lab = f"{v/1000:.1f}".replace(".", ",") if v >= 1000 else f"{v/1000:.2f}".replace(".", ",")
            fs = fs_lab if a == 2025 else fs_lab * .72
            s.append(f'<text x="{cx}" y="{y(v)-12}" text-anchor="middle" font-family="Gelasio" font-weight="700" font-size="{fs:.0f}" fill="{NAVY}">{lab}</text>')
    s.append("</svg>")
    return "".join(s)


CSS = """
@import url("../capa/assets/fonts.css");
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:#fff}
.slide{position:relative;width:1920px;height:1080px;overflow:hidden;font-family:"Manrope",sans-serif;color:#14213D}
.tt{position:absolute;left:110px;top:70px;font:700 60px "Gelasio",Georgia,serif}
.hl{position:absolute;left:110px;right:110px;height:1.5px;background:#E6ECEB}
.ft{position:absolute;left:110px;right:110px;bottom:34px;height:60px;display:flex;align-items:center;gap:24px;font:500 17px "Manrope";color:#7B8794}
.ft img{height:56px}.ft .sep{width:1.5px;height:30px;background:#DCE3E2}.ft b{font-weight:600;color:#5B6675}
.pn{position:absolute;right:110px;bottom:42px;font:700 40px "Gelasio",serif;line-height:1;text-align:right}
.pn::before{content:"";display:block;width:44px;height:5px;border-radius:3px;margin:0 0 10px auto;background:linear-gradient(90deg,#6DB527,#1E8A72 55%,#0072BA)}
.ref{position:absolute;left:110px;bottom:124px;font:500 14px "Manrope";color:#9AA5B1}
.big{font:700 64px/1 "Gelasio",serif}
.bl{font:600 20px "Manrope";color:#4A5568}
.cap{font:500 18px "Manrope";color:#4A5568}
.h{font:700 28px "Gelasio",serif}
.card{background:#EEF3F2;border-radius:26px}
.row{display:flex;align-items:center;gap:18px}
.row .nm{font:700 23px "Gelasio",serif;line-height:1.15}
.row .ft2{font:500 16px "Manrope";color:#4A5568;margin-top:4px}
.row .rf{font:500 14px "Manrope";color:#9AA5B1}
.dest{display:flex;align-items:center;gap:22px;font:italic 400 36px "Gelasio",serif;color:#fff;background:#14213D;border-radius:22px;padding:22px 34px}
.dest b{font-style:normal;color:#C1FF72}
"""
RODAPE = ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
          '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
          '<div class="pn">3</div>')
REF = ('<div class="ref">[1] IRENA, Renewable Power Generation Costs in 2024 · [3] EPE, Balanço Energético Nacional 2026, ano base 2025 '
       '(MMGD: micro e minigeração distribuída) · [4] Yamashita et al., 2021 · [5] Morais et al., 2010 · [6] Kopka et al.</div>')


def cabeca():
    return (f'<div class="tt">Contexto</div>'
            f'<div style="position:absolute;left:110px;top:172px">'
            f'<div style="font:700 26px Gelasio,serif">Redução do custo da energia, 2010 → 2024 <span style="font:500 17px Manrope;color:#9AA5B1">[1]</span></div>'
            f'<div style="display:flex;gap:64px;margin-top:8px">'
            f'<div><div class="big" style="color:{SOLAR}">−90 %</div><div class="bl" style="margin-top:4px">solar fotovoltaica</div></div>'
            f'<div><div class="big" style="color:{WIND}">−70 %</div><div class="bl" style="margin-top:4px">eólica terrestre</div></div>'
            f'</div></div>')


def bloco_grafico(x, y, W, H):
    return (f'<div style="position:absolute;left:{x}px;top:{y}px">'
            f'<div class="h" style="font-size:26px">Eólica + solar: de 0,5 % a 26,4 % da geração do Brasil</div>'
            f'<div class="cap" style="margin-top:4px"><span style="color:{WIND}">■</span> Eólica  <span style="color:{SOLAR}">■</span> Solar fotovoltaica — geração anual (TWh) e participação na geração total [3]</div>'
            f'<div style="margin-top:6px">{grafico_es(W, H)}</div>'
            f'<div class="cap" style="margin-top:2px">2025: <b style="color:#14213D">204,6 TWh</b> = eólica 116,5 + solar 88,1 — '
            f'<b style="color:#14213D">60 %</b> da geração solar já ocorre junto à carga (MMGD) [3]</div></div>')


P = {}

# ---------- V3a · gráfico à esquerda, cargas com fontes convergindo à direita, destaque em faixa
b = cabeca() + bloco_grafico(110, 352, 980, 340)
b += '<div class="card" style="position:absolute;left:1150px;top:176px;width:660px;height:612px;padding:26px 32px">'
b += '<div class="h" style="font-size:26px">Cargas pequenas, várias fontes</div>'
for k, nome, ref, fontes in CARGAS:
    b += (f'<div class="row" style="margin-top:8px">{convergencia(220, 130, fontes, k, rf=14, rl=30)}'
          f'<div><div class="nm">{nome} <span class="rf">{ref}</span></div><div class="ft2">{" + ".join(NOME[f] for f in fontes)}</div></div></div>')
b += '</div>'
b += ('<div class="dest" style="position:absolute;left:110px;right:110px;top:808px">'
      '<span>Várias fontes em um mesmo sistema <b>exigem coordenação.</b></span></div>')
P["S3v3_a"] = b + REF + RODAPE

# ---------- V3b · mesmo conteúdo, cargas em linha (4 colunas) e gráfico mais largo
b = cabeca()
b += f'<div style="position:absolute;left:110px;top:282px">{grafico_mmgd(860, 300, fs_lab=24)}</div>'
b += ('<div style="position:absolute;left:1010px;top:300px;width:800px">'
      '<div class="h" style="font-size:30px">Geração junto à carga cresceu mais de mil vezes</div>'
      '<div class="cap" style="margin-top:8px">Micro e minigeração distribuída solar no Brasil, 2016 → 2025 [3]</div>'
      '<div style="display:flex;gap:44px;margin-top:26px">'
      f'<div><div class="big" style="font-size:58px">53,1 <span style="font-size:30px">TWh</span></div><div class="cap">gerados em 2025</div></div>'
      f'<div><div class="big" style="font-size:58px">69 <span style="font-size:30px">%</span></div><div class="cap">da capacidade solar<br>está junto à carga</div></div></div></div>')
for i, (k, nome, ref, fontes) in enumerate(CARGAS):
    x = 110 + i * 432
    b += (f'<div class="card" style="position:absolute;left:{x}px;top:612px;width:408px;height:176px;padding:18px 22px;display:flex;align-items:center;gap:14px">'
          f'{convergencia(190, 140, fontes, k, rf=15, rl=30)}<div><div class="row"><div class="nm" style="font-size:21px">{nome} <span class="rf">{ref}</span></div></div>'
          f'<div class="ft2" style="font-size:15px">{" + ".join(NOME[f] for f in fontes)}</div></div></div>')
b += ('<div class="dest" style="position:absolute;left:110px;right:110px;top:812px">'
      '<span>Várias fontes em um mesmo sistema <b>exigem coordenação.</b></span></div>')
P["S3v3_b"] = b + REF + RODAPE

HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
for nome, body in P.items():
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))
print(list(P))
