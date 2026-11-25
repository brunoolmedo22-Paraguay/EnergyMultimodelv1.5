"""Slide 3 (Contexto) — v2: crescimento exponencial + escala dos pequenos sistemas; −90/−70 % só em texto.

ATENÇÃO — SÉRIE ANUAL PROVISÓRIA (maquete): só 2023, 2024 e 2025 da FV e 2025 da eólica foram conferidos em
fontes da EPE. Os demais anos são aproximações de boletins setoriais e DEVEM ser substituídos pela tabela
«Capacidade instalada de geração elétrica» do BEN 2026 (série 2016–2025, mesma referência [3] do artigo).
"""
import math
import os
D = os.path.dirname(os.path.abspath(__file__))

SOLAR, WIND, PEM, BAT, NAVY, SLATE, TEAL = "#D9A21B", "#4C8DD6", "#1BA39C", "#7B6CF6", "#14213D", "#4A5568", "#1F7A6D"
ANOS = list(range(2016, 2026))
FV = [0.08, 1.1, 2.4, 4.7, 7.9, 13.0, 24.0, 37.8, 48.5, 64.8]      # GW — PROVISÓRIO exceto 2023–2025
EOL = [10.7, 12.8, 14.7, 15.4, 17.7, 21.6, 25.6, 28.0, 29.5, 34.7]  # GW — PROVISÓRIO exceto 2025

ICON = {
 "sun": '<circle cx="20" cy="20" r="7" fill="none" stroke="currentColor" stroke-width="3"/><g stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 3v5M20 32v5M3 20h5M32 20h5M8 8l3.5 3.5M28.5 28.5L32 32M8 32l3.5-3.5M28.5 11.5L32 8"/></g>',
 "wind": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 18v19M20 18V4M20 18l12 7M20 18L8 25"/></g><circle cx="20" cy="18" r="3" fill="currentColor"/>',
 "bat": '<rect x="6" y="11" width="25" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="3"/><rect x="32" y="16" width="3" height="8" fill="currentColor"/><rect x="10" y="15" width="11" height="10" fill="currentColor"/>',
 "h2": '<text x="20" y="27" text-anchor="middle" font-family="Manrope,sans-serif" font-weight="800" font-size="19" fill="currentColor">H₂</text>',
 "grid": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M14 37L20 4l6 33M10 12h20M8 20h24M16 29h8"/></g>',
 "ship": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M4 24h32l-5 9H9z"/><path d="M11 24V15h14v9M17 15V9h6"/></g>',
 "bld": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><rect x="9" y="5" width="22" height="31"/><path d="M15 11h3M22 11h3M15 18h3M22 18h3M15 25h3M22 25h3M18 36v-5h4v5"/></g>',
 "vil": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><path d="M3 22l9-8 9 8v13H3z"/><path d="M19 20l9-8 9 8v15H21"/></g>',
 "fab": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><path d="M4 35V19l9 6v-6l9 6v-6l9 6V7h5v28z"/></g>',
 "br": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><path d="M9 8l9-3 8 4 7 1 3 7-4 5-1 7-6 5-5-1-3-5-5-3-1-6-4-4z"/></g>',
}
COR = {"sun": SOLAR, "wind": WIND, "h2": PEM, "bat": BAT, "grid": "#E0524F"}


def ic(k, s=40, c=NAVY):
    return f'<svg width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c};flex:none">{ICON[k]}</svg>'


def chips(recs, s=34):
    return "".join(f'<span class="chip" style="border-color:{COR[k]}">{ic(k, s-14, COR[k])}</span>' for k in recs)


def crescimento(W, H, legenda=True, rot_fs=30):
    """Barras empilhadas lado a lado (FV e eólica) 2016–2025, escala linear para evidenciar a curva."""
    pl, pr, pt, pb = 10, 10, 54, 46
    ymax = 70
    y = lambda v: pt + (H - pt - pb) * (1 - v / ymax)
    n = len(ANOS); gw = (W - pl - pr) / n; bw = gw * .34
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    for g in (20, 40, 60):
        s.append(f'<line x1="{pl}" x2="{W-pr}" y1="{y(g)}" y2="{y(g)}" stroke="#EEF1F1" stroke-width="1.5"/>'
                 f'<text x="{pl}" y="{y(g)-7}" font-family="Manrope" font-size="15" fill="#9AA5B1">{g} GW</text>')
    s.append(f'<line x1="{pl}" x2="{W-pr}" y1="{y(0)}" y2="{y(0)}" stroke="#C9D3DD" stroke-width="1.5"/>')
    pts = []
    for i, a in enumerate(ANOS):
        cx = pl + gw * (i + .5)
        for j, (v, c) in enumerate(((EOL[i], WIND), (FV[i], SOLAR))):
            bx = cx - bw - 2 + j * (bw + 4); h = max(y(0) - y(v), 2); r = min(5, h / 2)
            s.append(f'<path d="M{bx} {y(0)} V{y(0)-h+r} q0 -{r} {r} -{r} h{bw-2*r} q{r} 0 {r} {r} V{y(0)} Z" fill="{c}"/>')
        pts.append((cx + 2 + bw / 2, y(FV[i])))
        s.append(f'<text x="{cx}" y="{H-16}" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="17" fill="{SLATE}">{a}</text>')
    # curva de tendência da FV
    dpath = "M" + " L".join(f"{x:.1f} {yy:.1f}" for x, yy in pts)
    s.append(f'<path d="{dpath}" fill="none" stroke="{SOLAR}" stroke-width="2.5" stroke-dasharray="2 6" stroke-linecap="round" opacity=".9"/>')
    x25, y25 = pts[-1]; xe = pl + gw * 9.5 - bw / 2 - 2
    s.append(f'<text x="{x25-4}" y="{y25-14}" text-anchor="end" font-family="Gelasio" font-weight="700" font-size="{rot_fs}" fill="{NAVY}">64,8</text>'
             f'<text x="{xe-8}" y="{y(EOL[-1])-12}" text-anchor="end" font-family="Gelasio" font-weight="700" font-size="{rot_fs*.75:.0f}" fill="{NAVY}">34,7</text>')
    if legenda:
        s.append(f'<text x="{pl}" y="22" font-family="Manrope" font-weight="600" font-size="18" fill="{SLATE}">'
                 f'<tspan fill="{SOLAR}">■</tspan> Solar fotovoltaica   <tspan fill="{WIND}">■</tspan> Eólica   — capacidade instalada no Brasil (GW) [3]</text>')
    s.append(f'<text x="{W/2}" y="{H/2}" text-anchor="middle" font-family="Manrope" font-weight="800" font-size="30" fill="#E0524F" opacity=".22" transform="rotate(-12 {W/2} {H/2})">SÉRIE PROVISÓRIA — CONFERIR NO BEN 2026</text>')
    s.append("</svg>")
    return "".join(s)


# --------- escala: régua logarítmica de potência (kW)
ESC = [  # nome, valor em kW, ícone, recursos, rótulo do valor, fonte
    ("Embarcação EMB-H2-120", 60, "ship", ["h2", "bat", "sun"], "≈ 60 kW de pico", "caso C5–C6"),
    ("Microrrede CT-046", 100, "fab", ["sun", "bat", "grid"], "100 kW de pico", "casos C1–C4"),
    ("Sistema Interligado Nacional", 261e6, "br", [], "261 GW instalados", "[3]"),
]


def regua(W, H, x0=40, x1=None):
    x1 = x1 or W - 40
    lo, hi = 1, 1e9   # 1 kW … 1 TW
    X = lambda v: x0 + (x1 - x0) * (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
    yb = H * .55
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs><linearGradient id="gr" x1="0" x2="1"><stop offset="0" stop-color="#6DB527"/><stop offset=".55" stop-color="#1E8A72"/><stop offset="1" stop-color="#0072BA"/></linearGradient></defs>',
         f'<rect x="{x0}" y="{yb-5}" width="{x1-x0}" height="10" rx="5" fill="url(#gr)"/>']
    for v, t in ((1, "1 kW"), (1e3, "1 MW"), (1e6, "1 GW"), (1e9, "1 TW")):
        s.append(f'<line x1="{X(v)}" x2="{X(v)}" y1="{yb+8}" y2="{yb+20}" stroke="#9AA5B1" stroke-width="2"/>'
                 f'<text x="{X(v)}" y="{yb+42}" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="16" fill="#7B8794">{t}</text>')
    for k in range(10):
        v = 10 ** k
        if v not in (1, 1e3, 1e6, 1e9):
            s.append(f'<line x1="{X(v)}" x2="{X(v)}" y1="{yb+8}" y2="{yb+14}" stroke="#C9D3DD" stroke-width="1.5"/>')
    # faixa "pequeno porte"
    a, b2 = X(100), X(261e6)
    s.append(f'<path d="M{a} {yb-20} Q{(a+b2)/2} {yb-95} {b2} {yb-20}" fill="none" stroke="{TEAL}" stroke-width="2" stroke-dasharray="3 7"/>'
             f'<text x="{(a+b2)/2}" y="{yb-70}" text-anchor="middle" font-family="Gelasio" font-style="italic" font-size="24" fill="{TEAL}">≈ 10⁶ vezes menor</text>')
    s.append("</svg>")
    return "".join(s), X, yb


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
.dest{font:italic 400 32px "Gelasio",serif;color:#1F7A6D}
.cap{font:500 18px "Manrope";color:#4A5568}
.big{font:700 84px/1 "Gelasio",serif}
.bl{font:600 20px "Manrope";color:#4A5568;margin-top:6px}
.chip{display:inline-flex;width:34px;height:34px;border-radius:50%;border:2.5px solid;align-items:center;justify-content:center;background:#fff;margin-right:6px}
.card{background:#EEF3F2;border-radius:24px}
.mk{position:absolute;display:flex;flex-direction:column;align-items:center;text-align:center}
.mk .n{font:700 22px "Gelasio",serif;line-height:1.15;margin-top:8px}
.mk .v{font:600 17px "Manrope";color:#4A5568}
.mk .f{font:500 14px "Manrope";color:#9AA5B1}
.pin{position:absolute;width:3px}
"""
RODAPE = ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
          '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
          '<div class="pn">3</div>')
REF = '<div class="ref">[1] IRENA, Renewable Power Generation Costs in 2024 · [3] EPE, Balanço Energético Nacional 2026, ano base 2025 · [4] Yamashita et al. · [5] Morais et al. · [6] Kopka et al.</div>'
NUMS = (f'<div style="display:flex;gap:64px;align-items:flex-end">'
        f'<div><div class="big" style="color:{SOLAR}">−90 %</div><div class="bl">custo da energia solar</div></div>'
        f'<div><div class="big" style="color:{WIND}">−70 %</div><div class="bl">custo da eólica terrestre</div></div></div>'
        f'<div class="cap" style="margin-top:10px">2010 → 2024 [1]</div>')


def marcadores(X, yb, left, top, escala=1.0, show_rec=True):
    out = ""
    for nome, v, k, rec, val, fonte in ESC:
        x = left + X(v)
        acima = v < 1e3
        h = 150 if acima else 120
        if acima:
            yy = top + yb - 26 - 170 if nome.startswith("Micro") else top + yb + 46
        out += ""
    return out


P = {}

# ===================== V1 · Números + crescimento | escala (régua) embaixo
b = '<div class="tt">Contexto</div>'
b += f'<div style="position:absolute;left:110px;top:200px">{NUMS}</div>'
b += f'<div style="position:absolute;left:840px;top:170px">{crescimento(970, 390)}</div>'
svg, X, yb = regua(1700, 200, x0=40, x1=1660)
b += f'<div style="position:absolute;left:110px;top:650px">{svg}</div>'
# marcadores na régua
mk = [("Embarcação", 60, "ship", ["h2", "bat", "sun"], "≈ 60 kW", "C5–C6", "up"),
      ("Microrrede industrial", 100, "fab", ["sun", "bat", "grid"], "100 kW", "C1–C4", "down"),
      ("Sistema Interligado Nacional", 261e6, "br", [], "261 GW", "[3]", "up")]
for nome, v, k, rec, val, fonte, lado in mk:
    x = 110 + X(v); y0 = 650 + yb
    if lado == "up":
        b += f'<div class="pin" style="left:{x-1.5}px;top:{y0-34}px;height:30px;background:{NAVY}"></div>'
        al = "right:" + str(1920 - x + 14) + "px" if v > 1e6 else "left:" + str(x - 24) + "px"
        b += (f'<div class="mk" style="{al};top:{y0-150};top:{y0-148}px;flex-direction:row;gap:12px;align-items:center;text-align:left">{ic(k, 46)}'
              f'<div><div class="n" style="margin-top:0">{nome}</div><div class="v">{val} <span class="f">· {fonte}</span></div><div style="margin-top:4px">{chips(rec, 30)}</div></div></div>')
    else:
        b += f'<div class="pin" style="left:{x-1.5}px;top:{y0+6}px;height:58px;background:{NAVY}"></div>'
        b += (f'<div class="mk" style="left:{x-24}px;top:{y0+66}px;width:300px;align-items:flex-start;text-align:left;flex-direction:row;gap:12px">{ic(k, 46)}'
              f'<div><div class="n" style="margin-top:0">{nome}</div><div class="v">{val} <span class="f">· {fonte}</span> {chips(rec, 30)}</div></div></div>')
b += '<div class="dest" style="position:absolute;left:110px;top:470px;width:640px">Várias fontes, agora também em sistemas de pequeno porte.</div>'
P["S3v2_1_regua"] = b + REF + RODAPE

# ===================== V2 · Gráfico protagonista + coluna de pequenos sistemas (cartões com potência)
b = '<div class="tt">Contexto</div>'
b += f'<div style="position:absolute;left:110px;top:190px;display:flex;gap:48px">' \
     f'<div><span class="big" style="font-size:64px;color:{SOLAR}">−90 %</span><span class="bl" style="margin-left:12px">solar</span></div>' \
     f'<div><span class="big" style="font-size:64px;color:{WIND}">−70 %</span><span class="bl" style="margin-left:12px">eólica</span></div>' \
     f'<div class="cap" style="align-self:flex-end;margin-bottom:10px">custo da energia, 2010 → 2024 [1]</div></div>'
b += f'<div style="position:absolute;left:110px;top:300px">{crescimento(1080, 520, rot_fs=34)}</div>'
b += '<div class="card" style="position:absolute;left:1260px;top:190px;width:550px;height:630px;padding:34px 36px">'
b += '<div style="font:700 28px Gelasio,serif">Pequeno porte, várias fontes</div>'
sist = [("bld", "Edificações", "[4]", ["bat", "h2"], None), ("vil", "Localidades isoladas", "[5]", ["wind", "sun", "h2", "bat"], None),
        ("ship", "Embarcações", "[6]", ["h2", "bat"], None)]
for k, nome, ref, rec, _ in sist:
    b += (f'<div style="display:flex;align-items:center;gap:18px;margin-top:30px">{ic(k, 54)}<div><div style="font:700 24px Gelasio,serif">{nome} '
          f'<span style="font:500 15px Manrope;color:#9AA5B1">{ref}</span></div><div style="margin-top:8px">{chips(rec)}</div></div></div>')
b += ('<div style="margin-top:34px;border-top:1px dashed #C9D3DD;padding-top:22px;display:flex;align-items:baseline;gap:14px">'
      '<span class="big" style="font-size:56px">10⁶×</span><span class="cap">menores que o SIN:<br>60–100 kW nos estudos de caso × 261 GW [3]</span></div></div>')
b += '<div class="dest" style="position:absolute;left:110px;top:850px">Várias fontes em um mesmo sistema exigem coordenação.</div>'
P["S3v2_2_grafico"] = b + REF.replace("bottom:124px", "bottom:124px") + RODAPE

# ===================== V3 · Zoom: do SIN ao pequeno sistema (círculos encaixados)
b = '<div class="tt">Contexto</div>'
b += f'<div style="position:absolute;left:110px;top:200px">{NUMS}</div>'
b += f'<div style="position:absolute;left:110px;top:440px">{crescimento(760, 380, rot_fs=28)}</div>'
zx, zy = 960, 190
z = [f'<svg width="860" height="660" viewBox="0 0 860 660" style="position:absolute;left:{zx}px;top:{zy}px">']
# círculo grande: SIN
z.append('<circle cx="250" cy="330" r="230" fill="#EEF3F2"/><circle cx="250" cy="330" r="230" fill="none" stroke="#C9D3DD" stroke-width="2"/>')
z.append(f'<text x="250" y="200" text-anchor="middle" font-family="Gelasio" font-weight="700" font-size="30" fill="{NAVY}">SIN</text>'
         f'<text x="250" y="232" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="20" fill="{SLATE}">261 GW [3]</text>')
# ponto minúsculo e lupa
z.append(f'<circle cx="300" cy="400" r="4" fill="{TEAL}"/><circle cx="300" cy="400" r="16" fill="none" stroke="{TEAL}" stroke-width="2.5"/>')
z.append(f'<path d="M310 388 L628 173 M310 412 L628 547" stroke="{TEAL}" stroke-width="2" stroke-dasharray="3 7" fill="none"/>')
z.append(f'<circle cx="660" cy="360" r="190" fill="#fff" stroke="{TEAL}" stroke-width="3"/>')
z.append(f'<text x="660" y="232" text-anchor="middle" font-family="Gelasio" font-style="italic" font-size="22" fill="{TEAL}">≈ 10⁶ vezes menor</text>')
z.append("</svg>")
b += "".join(z)
# conteúdo dentro do círculo de zoom
b += f'<div style="position:absolute;left:{zx+660-150}px;top:{zy+260}px;width:300px;display:flex;flex-direction:column;gap:16px">'
for k, nome, rec in (("bld", "Edificações [4]", ["bat", "h2"]), ("vil", "Localidades isoladas [5]", ["wind", "sun", "h2", "bat"]), ("ship", "Embarcações [6]", ["h2", "bat"])):
    b += f'<div style="display:flex;align-items:center;gap:12px">{ic(k, 36)}<div><div style="font:700 19px Gelasio,serif">{nome}</div><div style="margin-top:4px">{chips(rec, 28)}</div></div></div>'
b += '</div>'
b += f'<div class="cap" style="position:absolute;left:{zx+470}px;top:{zy+570}px;width:380px;text-align:center">potências da ordem de kW</div>'
b += '<div class="dest" style="position:absolute;left:960px;top:870px">Várias fontes em um mesmo sistema exigem coordenação.</div>'
P["S3v2_3_zoom"] = b + REF + RODAPE

HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
for nome, body in P.items():
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))
print(list(P))
