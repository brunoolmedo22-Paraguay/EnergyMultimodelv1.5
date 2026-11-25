"""Slide 3 (Contexto) — três propostas visuais. Dados das MESMAS referências do artigo:
[1] IRENA, Renewable Power Generation Costs in 2024 (LCOE global médio ponderado, USD 2024/kWh);
[3] EPE, Balanço Energético Nacional 2026, ano base 2025 (capacidade e participação na geração).
Série solar 2016/2023/2024: EPE, Anuário Estatístico de Energia Elétrica (mesma instituição de [3]).
Valores marcados VERIFICAR devem ser conferidos no PDF original antes da versão final."""
import os
D = os.path.dirname(os.path.abspath(__file__))

SOLAR, WIND, PEM, BAT, REDE, NAVY = "#D9A21B", "#4C8DD6", "#1BA39C", "#7B6CF6", "#E0524F", "#14213D"
LCOE = {"FV": (0.417, 0.043, SOLAR), "Eólica terrestre": (0.113, 0.034, WIND)}   # 2010 FV: VERIFICAR
CAP_FV = [(2016, 0.081), (2023, 37.843), (2024, 48.468), (2025, 64.793)]           # GW
CAP_EOL = [(2024, 29.55), (2025, 34.707)]                                           # 2024: VERIFICAR (≈ 34,707/1,175)
PART = (23.7, 26.4)                                                                 # % da geração (2024, 2025)

ICON = {
 "sun": '<circle cx="20" cy="20" r="7" fill="none" stroke="currentColor" stroke-width="3"/><g stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 3v5M20 32v5M3 20h5M32 20h5M8 8l3.5 3.5M28.5 28.5L32 32M8 32l3.5-3.5M28.5 11.5L32 8"/></g>',
 "wind": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 18v19M20 18V4M20 18l12 7M20 18L8 25"/></g><circle cx="20" cy="18" r="3" fill="currentColor"/>',
 "bat": '<rect x="6" y="11" width="25" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="3"/><rect x="32" y="16" width="3" height="8" fill="currentColor"/><rect x="10" y="15" width="11" height="10" fill="currentColor"/>',
 "h2": '<text x="20" y="27" text-anchor="middle" font-family="Manrope,sans-serif" font-weight="800" font-size="19" fill="currentColor">H₂</text>',
 "load": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><path d="M6 19L20 7l14 12v16H6z"/><path d="M17 35v-9h6v9"/></g>',
 "ship": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M4 24h32l-5 9H9z"/><path d="M11 24V15h14v9M17 15V9h6"/></g>',
 "bld": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><rect x="9" y="5" width="22" height="31"/><path d="M15 11h3M22 11h3M15 18h3M22 18h3M15 25h3M22 25h3M18 36v-5h4v5"/></g>',
 "vil": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><path d="M3 22l9-8 9 8v13H3z"/><path d="M19 20l9-8 9 8v15H21"/></g>',
}
COR = {"sun": SOLAR, "wind": WIND, "h2": PEM, "bat": BAT, "load": NAVY}
NOME = {"sun": "Solar", "wind": "Eólica", "h2": "H₂", "bat": "Bateria", "load": "Demanda"}
GRAD = '<linearGradient id="{id}" x1="0" x2="1"><stop offset="0" stop-color="#6DB527"/><stop offset=".55" stop-color="#1E8A72"/><stop offset="1" stop-color="#0072BA"/></linearGradient>'

SISTEMAS = [  # [4], [5], [6] do artigo
    ("bld", "Edificações", "[4]", ["bat", "h2", "load"]),
    ("vil", "Localidades isoladas", "[5]", ["wind", "sun", "h2", "bat", "load"]),
    ("ship", "Embarcações", "[6]", ["h2", "bat", "load"]),
]


def svg_icone(k, x, y, s, c):
    return f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>'


def mini_bus(W, recursos, gid, r=26, lbl=True):
    """Barramento em miniatura (mesma linguagem da capa): recursos pendurados abaixo."""
    H = 135 if lbl else 100
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs>{GRAD.format(id=gid)}</defs>',
         f'<rect x="0" y="8" width="{W}" height="8" rx="4" fill="url(#{gid})"/>']
    n = len(recursos)
    for i, k in enumerate(recursos):
        cx = W * (i + .5) / n; c = COR[k]; cy = 72
        s.append(f'<line x1="{cx}" y1="12" x2="{cx}" y2="{cy-r}" stroke="{c}" stroke-width="3"/>'
                 f'<circle cx="{cx}" cy="12" r="5" fill="#fff" stroke="{c}" stroke-width="2.5"/>'
                 f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="{c}" stroke-width="3"/>' + svg_icone(k, cx - 15, cy - 15, 30, c))
        if lbl:
            s.append(f'<text x="{cx}" y="{cy+r+26}" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="17" fill="#4A5568">{NOME[k]}</text>')
    s.append("</svg>")
    return "".join(s)


def slope(W, H, big=False):
    """LCOE 2010 → 2024 (dois pontos por fonte; IRENA só publica a série completa no relatório)."""
    pl, pr, pt, pb = 70, 40, 30, 50
    y = lambda v: pt + (H - pt - pb) * (1 - v / 0.45)
    x0, x1 = pl, W - pr
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    for g in (0, .1, .2, .3, .4):
        s.append(f'<line x1="{pl}" x2="{x1}" y1="{y(g)}" y2="{y(g)}" stroke="#E6ECEB" stroke-width="1"/>'
                 f'<text x="{pl-12}" y="{y(g)+6}" text-anchor="end" font-family="Manrope" font-size="16" fill="#7B8794">{g:.1f}</text>')
    for xx, t in ((x0, "2010"), (x1, "2024")):
        s.append(f'<text x="{xx}" y="{H-14}" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="18" fill="#4A5568">{t}</text>')
    for nome, (a, b, c) in LCOE.items():
        pct = round((1 - b / a) * 100)
        s.append(f'<line x1="{x0}" y1="{y(a)}" x2="{x1}" y2="{y(b)}" stroke="{c}" stroke-width="5" stroke-linecap="round"/>'
                 f'<circle cx="{x0}" cy="{y(a)}" r="8" fill="{c}" stroke="#fff" stroke-width="2"/><circle cx="{x1}" cy="{y(b)}" r="8" fill="{c}" stroke="#fff" stroke-width="2"/>')
    fs = 40 if big else 34
    xm = x0 + (x1 - x0) * .52
    yf = y(.417 + (.043 - .417) * .52); yw = y(.113 + (.034 - .113) * .52)
    s.append(f'<text x="{xm+44}" y="{yf-40}" font-family="Gelasio" font-weight="700" font-size="{fs}" fill="{NAVY}">−90 %</text>'
             f'<text x="{xm+44}" y="{yf-14}" font-family="Manrope" font-weight="600" font-size="17" fill="#4A5568"><tspan fill="{SOLAR}">●</tspan> Solar FV</text>'
             f'<text x="{xm-40}" y="{yw+46}" font-family="Gelasio" font-weight="700" font-size="{fs}" fill="{NAVY}">−70 %</text>'
             f'<text x="{xm-40}" y="{yw+72}" font-family="Manrope" font-weight="600" font-size="17" fill="#4A5568"><tspan fill="{WIND}">●</tspan> Eólica terrestre</text>')
    s.append(f'<text x="{pl-60}" y="{pt-8}" font-family="Manrope" font-size="15" fill="#7B8794">USD/kWh</text>')
    s.append("</svg>")
    return "".join(s)


def barras_br(W, H, bw=52):
    """Capacidade instalada no Brasil (GW): FV 2016, 2023, 2024, 2025; eólica 2024, 2025."""
    pl, pt, pb = 20, 40, 50
    ymax = 70
    y = lambda v: pt + (H - pt - pb) * (1 - v / ymax)
    grupos = [("2016", [(0.081, SOLAR)]), ("2023", [(37.843, SOLAR)]), ("2024", [(48.468, SOLAR), (29.55, WIND)]), ("2025", [(64.793, SOLAR), (34.707, WIND)])]
    gw = (W - pl) / len(grupos)
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<line x1="{pl}" x2="{W}" y1="{y(0)}" y2="{y(0)}" stroke="#C9D3DD" stroke-width="1.5"/>']
    for i, (ano, bars) in enumerate(grupos):
        cx = pl + gw * (i + .5)
        tot = len(bars) * bw + (len(bars) - 1) * 6
        for j, (v, c) in enumerate(bars):
            bx = cx - tot / 2 + j * (bw + 6); top = y(v); h = max(y(0) - top, 3)
            s.append(f'<path d="M{bx} {y(0)} V{y(0)-h+6} q0 -6 6 -6 h{bw-12} q6 0 6 6 V{y(0)} Z" fill="{c}"/>')
            if ano in ("2016", "2025") or (ano == "2024" and c == WIND and False):
                lab = "81 MW" if v < 1 else f"{v:.1f}".replace(".", ",")
                s.append(f'<text x="{bx+bw/2}" y="{top-12}" text-anchor="middle" font-family="Gelasio" font-weight="700" font-size="{24 if v>1 else 17}" fill="{NAVY}">{lab}</text>')
        s.append(f'<text x="{cx}" y="{H-14}" text-anchor="middle" font-family="Manrope" font-weight="600" font-size="18" fill="#4A5568">{ano}</text>')
    s.append(f'<text x="{pl}" y="{pt-16}" font-family="Manrope" font-size="15" fill="#7B8794">GW instalados no Brasil</text>')
    s.append("</svg>")
    return "".join(s)


def donut(D_, val, sub, cor_txt=NAVY):
    r = D_ / 2 - 14; c = 2 * 3.14159265 * r
    a = c * val / 100
    return (f'<svg width="{D_}" height="{D_}" viewBox="0 0 {D_} {D_}"><defs>{GRAD.format(id="gd")}</defs>'
            f'<circle cx="{D_/2}" cy="{D_/2}" r="{r}" fill="none" stroke="#EEF3F2" stroke-width="22"/>'
            f'<circle cx="{D_/2}" cy="{D_/2}" r="{r}" fill="none" stroke="url(#gd)" stroke-width="22" stroke-dasharray="{a} {c}" transform="rotate(-90 {D_/2} {D_/2})" stroke-linecap="butt"/>'
            f'<text x="{D_/2}" y="{D_/2+10}" text-anchor="middle" font-family="Gelasio" font-weight="700" font-size="{D_*.2:.0f}" fill="{cor_txt}">{str(val).replace(".", ",")}<tspan font-size="{D_*.11:.0f}"> %</tspan></text>'
            + f'<text x="{D_/2}" y="{D_/2+40}" text-anchor="middle" font-family="Manrope" font-size="15" fill="#4A5568">{sub}</text></svg>')


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
.dest{font:italic 400 34px "Gelasio",serif;color:#1F7A6D}
.h{font:700 30px "Gelasio",serif;color:#14213D}
.cap{font:500 18px "Manrope";color:#4A5568}
.card{background:#EEF3F2;border-radius:24px;padding:26px 30px}
.chev{position:absolute;height:64px;display:flex;align-items:center;padding-left:46px;color:#fff;font:700 26px "Gelasio",serif}
.big{font:700 92px/1 "Gelasio",serif}
.sys{display:flex;align-items:center;gap:14px;font:700 24px "Gelasio",serif}
.sys svg{flex:none}
.tag{font:500 15px "Manrope";color:#7B8794;margin-left:6px}
"""

RODAPE = ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
          '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
          '<div class="pn">3</div>')
REF = '<div class="ref">[1] IRENA, Renewable Power Generation Costs in 2024 (LCOE global, USD/kWh de 2024) · [3] EPE, Balanço Energético Nacional 2026, ano base 2025 · [4] Yamashita et al. · [5] Morais et al. · [6] Kopka et al.</div>'


def chev(x, w, txt, c, first=False):
    cp = "polygon(0 0,calc(100% - 26px) 0,100% 50%,calc(100% - 26px) 100%,0 100%" + (")" if first else ",26px 50%)")
    return f'<div class="chev" style="left:{x}px;top:180px;width:{w}px;background:{c};clip-path:{cp}">{txt}</div>'


def sistema(k, nome, ref, rec, W, gid, lbl=True):
    return (f'<div><div class="sys">{svg_icone_html(k)}<span>{nome}<span class="tag">{ref}</span></span></div>'
            f'<div style="margin-top:10px">{mini_bus(W, rec, gid, r=24 if not lbl else 26, lbl=lbl)}</div></div>')


def svg_icone_html(k, s=44, c=NAVY):
    return f'<svg width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>'


P = {}

# ---------------- A · Três atos em chevrons
cols = [(110, 560), (690, 560), (1270, 540)]
body = '<div class="tt">Contexto</div>'
body += chev(110, 580, "Ficaram baratas", "#6DB527", True) + chev(690, 580, "Cresceram no Brasil", "#2A9A5C") + chev(1270, 540, "Chegaram aos pequenos sistemas", "#0F7E8E")
body += f'<div style="position:absolute;left:110px;top:270px">{slope(560, 430)}<div class="cap" style="margin-top:6px">Custo nivelado da energia, 2010 → 2024 [1]</div></div>'
body += (f'<div style="position:absolute;left:700px;top:270px">{barras_br(395, 430, bw=34)}</div>'
         f'<div style="position:absolute;left:1128px;top:262px;text-align:center">{donut(140, 26.4, "da geração")}<div class="cap" style="margin-top:8px;width:140px">solar + eólica<br>em 2025 [3]</div></div>'
         f'<div class="cap" style="position:absolute;left:700px;top:706px"><span style="color:{SOLAR}">●</span> Solar FV · <span style="color:{WIND}">●</span> Eólica — capacidade instalada [3]</div>')
y0 = 270
for i, (k, nome, ref, rec) in enumerate(SISTEMAS):
    body += f'<div style="position:absolute;left:1290px;top:{y0 + i*165}px">{sistema(k, nome, ref, rec, 500, f"gA{i}", lbl=False)}</div>'
body += '<div class="dest" style="position:absolute;left:110px;top:790px">Várias fontes em um mesmo sistema exigem coordenação.</div>'
P["S3_A_tres_atos"] = body + REF + RODAPE

# ---------------- B · Números grandes
body = '<div class="tt">Contexto</div>'
body += ('<div style="position:absolute;left:110px;top:200px;width:1000px">'
         '<div class="cap" style="font-size:20px;margin-bottom:18px">Custo nivelado da energia, 2010 → 2024 [1]</div>'
         f'<div style="display:flex;gap:70px"><div><div class="big" style="color:{SOLAR}">−90 %</div><div class="h" style="font-size:26px;margin-top:8px">solar fotovoltaica</div></div>'
         f'<div><div class="big" style="color:{WIND}">−70 %</div><div class="h" style="font-size:26px;margin-top:8px">eólica terrestre</div></div></div>'
         '<div class="cap" style="font-size:20px;margin:56px 0 18px">Brasil, 2025 [3]</div>'
         f'<div style="display:flex;gap:56px;align-items:center"><div><div class="big" style="font-size:76px">64,8 <span style="font-size:40px">GW</span></div><div class="cap" style="font-size:20px">solar · +33,7 % no ano</div></div>'
         f'<div><div class="big" style="font-size:76px">34,7 <span style="font-size:40px">GW</span></div><div class="cap" style="font-size:20px">eólica · +17,5 % no ano</div></div>'
         f'<div style="text-align:center">{donut(190, 26.4, "da geração")}</div></div></div>')
body += '<div class="card" style="position:absolute;left:1180px;top:190px;width:630px;height:640px;padding:34px 40px">'
body += '<div class="h" style="font-size:28px;margin-bottom:22px">Pequenos sistemas, várias fontes</div>'
for i, (k, nome, ref, rec) in enumerate(SISTEMAS):
    body += f'<div style="margin-bottom:18px">{sistema(k, nome, ref, rec, 540, f"gB{i}", lbl=False)}</div>'
body += '</div><div class="dest" style="position:absolute;left:110px;top:840px">Várias fontes em um mesmo sistema exigem coordenação.</div>'
P["S3_B_numeros"] = body + REF + RODAPE

# ---------------- C · Do nacional ao pequeno (gráficos em cima, sistemas embaixo como protagonistas)
body = '<div class="tt">Contexto</div>'
body += (f'<div style="position:absolute;left:110px;top:180px">{slope(600, 330, big=True)}<div class="cap">Custo nivelado da energia, 2010 → 2024 [1]</div></div>'
         f'<div style="position:absolute;left:830px;top:180px">{barras_br(520, 330)}<div class="cap"><span style="color:{SOLAR}">●</span> Solar FV · <span style="color:{WIND}">●</span> Eólica — GW instalados [3]</div></div>'
         f'<div style="position:absolute;left:1470px;top:200px;text-align:center">{donut(250, 26.4, "da geração em 2025")}<div class="cap" style="margin-top:8px">solar + eólica (23,7 % em 2024) [3]</div></div>')
body += '<div style="position:absolute;left:110px;right:110px;top:578px;height:2px;background-image:linear-gradient(90deg,#1F7A6D 55%,transparent 0);background-size:14px 2px"></div>'
for i, (k, nome, ref, rec) in enumerate(SISTEMAS):
    body += f'<div class="card" style="position:absolute;left:{110 + i*575}px;top:620px;width:550px;height:265px">{sistema(k, nome, ref, rec, 490, f"gC{i}")}</div>'
P["S3_C_nacional_pequeno"] = body + REF.replace("bottom:124px", "bottom:124px") + RODAPE

HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
for nome, b in P.items():
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=b))
print(list(P))
