"""Variações da capa B (barramento)."""
import os
D = os.path.dirname(os.path.abspath(__file__))

TIT = "SEEDS: Desenvolvimento e Avaliação de um Simulador Modular Expansível com Gerenciamento Energético Hierárquico Baseado em MILP–MPC"
AUT = "Bruno Manuel Olmedo Chávez"
ORI = "Prof. Dr. Jorge Javier Gimenez Ledesma"
COO = "Me. Daniel Firmo Kazay"
CUR = "Engenharia de Energia · ILATIT"
DAT = "Foz do Iguaçu, 9 de dezembro de 2026"

ICON = {
 "sun": '<circle cx="20" cy="20" r="7" fill="none" stroke="currentColor" stroke-width="3"/><g stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 3v5M20 32v5M3 20h5M32 20h5M8 8l3.5 3.5M28.5 28.5L32 32M8 32l3.5-3.5M28.5 11.5L32 8"/></g>',
 "wind": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 18v19M20 18V4M20 18l12 7M20 18L8 25"/></g><circle cx="20" cy="18" r="3" fill="currentColor"/>',
 "bat": '<rect x="6" y="11" width="25" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="3"/><rect x="32" y="16" width="3" height="8" fill="currentColor"/><rect x="10" y="15" width="11" height="10" fill="currentColor"/>',
 "h2": '<text x="20" y="27" text-anchor="middle" font-family="Manrope,sans-serif" font-weight="800" font-size="20" fill="currentColor">H₂</text>',
 "grid": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M14 37L20 4l6 33M10 12h20M8 20h24M16 29h8"/></g>',
 "load": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"><path d="M6 19L20 7l14 12v16H6z"/><path d="M17 35v-9h6v9"/></g>',
}
COR = {"sun": "#D9A21B", "wind": "#4C8DD6", "h2": "#1BA39C", "bat": "#7B6CF6", "grid": "#E0524F", "load": "#14213D"}
NOME = {"sun": "Solar", "wind": "Eólica", "h2": "PEMFC", "bat": "Bateria", "grid": "Rede", "load": "Demanda"}
# sentido: in = injeta no barramento, out = consome, bi = bidirecional
SENT = {"sun": "in", "wind": "in", "h2": "in", "bat": "bi", "grid": "bi", "load": "out"}

GRAD = '<linearGradient id="{id}" x1="0" y1="0" x2="{x2}" y2="{y2}"><stop offset="0" stop-color="#6DB527"/><stop offset=".55" stop-color="#1E8A72"/><stop offset="1" stop-color="#0072BA"/></linearGradient>'


def seta(x, y, ang, c):
    return f'<path d="M-7 -6 L7 0 L-7 6 Z" fill="{c}" transform="translate({x} {y}) rotate({ang})"/>'


def no(k, cx, cy, r=36, rot=None, dark=False):
    c = COR[k] if not (dark and k == "load") else "#FFFFFF"
    fill = "#FFFFFF" if not dark else "#1B2B4D"
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{c}" stroke-width="3"/>'
            f'<svg x="{cx-20}" y="{cy-20}" width="40" height="40" viewBox="0 0 40 40" style="color:{c}">{ICON[k]}</svg>')


def bus_h(W, H, ybus, cima, baixo, dark=False, lbl="#4A5568", x0=30, x1=None, stub=110):
    """Barramento horizontal: `cima` acima (fontes), `baixo` abaixo."""
    x1 = x1 or W - 30
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"><defs>{GRAD.format(id="gh", x2=1, y2=0)}</defs>']
    s.append(f'<rect x="{x0}" y="{ybus-6}" width="{x1-x0}" height="12" rx="6" fill="url(#gh)"/>')
    def lado(lista, up):
        n = len(lista)
        for i, k in enumerate(lista):
            cx = x0 + (x1 - x0) * (i + 1) / (n + 1)
            cy = ybus - stub if up else ybus + stub
            c = COR[k] if not (dark and k == "load") else "#FFFFFF"
            a, b = (cy + 36, ybus - 6) if up else (ybus + 6, cy - 36)
            s.append(f'<line x1="{cx}" y1="{a}" x2="{cx}" y2="{b}" stroke="{c}" stroke-width="3"/>')
            m = (a + b) / 2
            sen = SENT[k]
            if sen == "in":
                s.append(seta(cx, m, 90 if up else -90, c))
            elif sen == "out":
                s.append(seta(cx, m, -90 if up else 90, c))
            else:
                s.append(seta(cx, m - 9, -90, c)); s.append(seta(cx, m + 9, 90, c))
            s.append(f'<circle cx="{cx}" cy="{ybus}" r="7" fill="{"#fff" if not dark else "#14213D"}" stroke="{c}" stroke-width="3"/>')
            s.append(no(k, cx, cy, dark=dark))
            ty = cy - 52 if up else cy + 66
            s.append(f'<text x="{cx}" y="{ty}" text-anchor="middle" font-family="Manrope,sans-serif" font-weight="600" font-size="19" letter-spacing=".5" fill="{lbl}">{NOME[k]}</text>')
    lado(cima, True); lado(baixo, False)
    s.append('</svg>')
    return "".join(s)


def bus_v(W, H, xbus, esq, dir_, y0=30, y1=None, stub=120, lbl="#4A5568"):
    y1 = y1 or H - 30
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"><defs>{GRAD.format(id="gv", x2=0, y2=1)}</defs>']
    s.append(f'<rect x="{xbus-6}" y="{y0}" width="12" height="{y1-y0}" rx="6" fill="url(#gv)"/>')
    def lado(lista, left):
        n = len(lista)
        for i, k in enumerate(lista):
            cy = y0 + (y1 - y0) * (i + 1) / (n + 1)
            cx = xbus - stub if left else xbus + stub
            c = COR[k]
            a, b = (cx + 36, xbus - 6) if left else (xbus + 6, cx - 36)
            s.append(f'<line x1="{a}" y1="{cy}" x2="{b}" y2="{cy}" stroke="{c}" stroke-width="3"/>')
            m = (a + b) / 2; sen = SENT[k]
            if sen == "in": s.append(seta(m, cy, 0 if left else 180, c))
            elif sen == "out": s.append(seta(m, cy, 180 if left else 0, c))
            else: s.append(seta(m - 9, cy, 180, c)); s.append(seta(m + 9, cy, 0, c))
            s.append(f'<circle cx="{xbus}" cy="{cy}" r="7" fill="#fff" stroke="{c}" stroke-width="3"/>')
            s.append(no(k, cx, cy))
            tx, anc = (cx - 52, "end") if left else (cx + 52, "start")
            s.append(f'<text x="{tx}" y="{cy+7}" text-anchor="{anc}" font-family="Manrope,sans-serif" font-weight="600" font-size="19" fill="{lbl}">{NOME[k]}</text>')
    lado(esq, True); lado(dir_, False)
    s.append('</svg>')
    return "".join(s)


HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"><style>{css}</style></head><body><div class="slide">{body}<div class="tag">{tag}</div></div></body></html>'

COMUM = """
h1{font-weight:700;color:var(--navy);line-height:1.15}
.nm .a{font-weight:700;font-size:38px;color:var(--navy)}
.nm .o{font-size:25px;line-height:1.6;margin-top:12px;color:#2b3648}
.nm .o b{font-weight:600}
.cm{font:600 21px var(--sans);color:var(--slate);letter-spacing:.02em;line-height:1.6}
"""

def nomes():
    return f'<div class="nm"><div class="a">{AUT}</div><div class="o"><b>Orientador:</b> {ORI}<br><b>Coorientador:</b> {COO}</div></div>'

V = {}

# ------------------------------------------------ B1 · Controlador
V["B1_controlador"] = dict(tag="B1 · Controlador", css=COMUM + """
.def{position:absolute;left:110px;top:92px;font:italic 400 44px var(--serif);color:var(--teal)}
.def::after{content:"";display:inline-block;width:120px;height:3px;background:var(--rust);vertical-align:middle;margin-left:28px}
h1{position:absolute;left:110px;top:165px;width:1700px;font-size:60px}
.nm{position:absolute;left:110px;top:620px}
.un{position:absolute;left:110px;bottom:60px;display:flex;align-items:center;gap:34px}
.un img{height:160px}.un .cm{border-left:2px solid var(--line);padding-left:30px}
.logo{position:absolute;left:1190px;top:500px;width:480px}
.ems{position:absolute;left:1425px;top:662px;width:2px;height:78px;background-image:linear-gradient(var(--teal) 50%,transparent 0);background-size:2px 10px}
.bus{position:absolute;left:990px;top:730px}
""", body=f"""<div class="def">Defesa de Trabalho de Conclusão de Curso</div>
<h1>{TIT}</h1>{nomes()}
<div class="un"><img src="assets/unila.png"><div class="cm">{CUR}<br>{DAT}</div></div>
<img class="logo" src="assets/seeds.png"><div class="ems"></div>
<div class="bus">{bus_h(880, 300, 22, [], ["sun","wind","h2","bat","grid","load"], stub=115)}</div>""")

# ------------------------------------------------ B2 · Linha contínua
V["B2_linha"] = dict(tag="", css=COMUM + """
h1{position:absolute;left:110px;top:240px;width:1700px;font-size:60px}
.un{position:absolute;left:110px;top:60px;height:150px}
.cmt{position:absolute;right:110px;top:118px;text-align:right}
.def{position:absolute;left:110px;top:560px;font:700 46px var(--serif);color:var(--teal)}
.def small{display:block;font:italic 400 24px var(--serif);color:var(--slate);margin-top:6px}
.nm{position:absolute;left:110px;top:720px}
.line{position:absolute;left:110px;top:695px;width:860px;height:3px;background:linear-gradient(90deg,var(--line),#6DB527)}
.bus{position:absolute;left:960px;top:505px}
.logo{position:absolute;right:110px;bottom:60px;width:360px}
""", body=f"""<img class="un" src="assets/unila.png"><div class="cmt cm">{DAT}</div>
<h1>{TIT}</h1>
<div class="def">Defesa de TCC<small>Engenharia de Energia · ILATIT</small></div><div class="line"></div>{nomes()}
<div class="bus">{bus_h(860, 380, 190, ["sun","wind","h2"], ["bat","grid","load"], x0=0, x1=850, stub=100)}</div>
<img class="logo" src="assets/seeds.png">""")

# ------------------------------------------------ B3 · Vertical
V["B3_vertical"] = dict(tag="B3 · Vertical", css=COMUM + """
.def{position:absolute;left:110px;top:96px;font:700 52px var(--serif);color:var(--teal)}
.def i{font-weight:400;color:var(--slate);font-size:30px;margin-left:16px}
h1{position:absolute;left:110px;top:190px;width:1080px;font-size:56px}
.nm{position:absolute;left:110px;top:690px}
.un{position:absolute;left:110px;bottom:60px;display:flex;align-items:center;gap:34px}
.un img{height:140px}.un .cm{border-left:2px solid var(--line);padding-left:30px}
.side{position:absolute;right:0;top:0;width:640px;height:1080px;background:var(--light)}
.logo{position:absolute;right:100px;top:70px;width:440px}
.bus{position:absolute;right:20px;top:250px}
""", body=f"""<div class="side"></div>
<div class="def">Defesa de TCC <i>· 2026</i></div><h1>{TIT}</h1>{nomes()}
<div class="un"><img src="assets/unila.png"><div class="cm">{CUR}<br>{DAT}</div></div>
<img class="logo" src="assets/seeds.png">
<div class="bus">{bus_v(600, 780, 300, ["sun","wind","h2"], ["bat","grid","load"], y0=10, y1=770, stub=130)}</div>""")

# ------------------------------------------------ B4 · Painel planta
V["B4_planta"] = dict(tag="B4 · Planta", css=COMUM + """
.def{position:absolute;left:110px;top:86px;font:700 84px var(--serif);color:var(--teal);letter-spacing:-.01em}
h1{position:absolute;left:110px;top:215px;width:1020px;font-size:50px;line-height:1.18}
.nm{position:absolute;left:110px;top:690px}
.un{position:absolute;left:110px;bottom:60px;display:flex;align-items:center;gap:34px}
.un img{height:140px}.un .cm{border-left:2px solid var(--line);padding-left:30px}
.card{position:absolute;right:90px;top:90px;width:640px;height:900px;border-radius:36px;background:var(--light)}
.card .logo{position:absolute;left:50%;transform:translateX(-50%);top:70px;width:470px}
.card .bus{position:absolute;left:20px;top:330px}
.card .gr{position:absolute;left:0;right:0;bottom:0;height:12px;border-radius:0 0 36px 36px;background:linear-gradient(90deg,#6DB527,#1E8A72 55%,#0072BA)}
""", body=f"""<div class="def">Defesa de TCC</div><h1>{TIT}</h1>{nomes()}
<div class="un"><img src="assets/unila.png"><div class="cm">{CUR}<br>{DAT}</div></div>
<div class="card"><img class="logo" src="assets/seeds.png"><div class="bus">{bus_h(600, 520, 260, ["sun","wind","h2"], ["bat","grid","load"], x0=20, x1=580, stub=125)}</div><div class="gr"></div></div>""")

# ------------------------------------------------ B5 · Noturno (B2 escuro)
V["B5_escuro"] = dict(tag="B5 · Escuro", css=COMUM + """
.slide{background:var(--navy)}
h1{position:absolute;left:110px;top:240px;width:1700px;font-size:60px;color:#fff}
.un{position:absolute;left:110px;top:60px;height:150px}
.cmt{position:absolute;right:110px;top:100px;text-align:right;color:#B8C4D6}
.def{position:absolute;left:110px;top:560px;font:700 46px var(--serif);color:var(--lime)}
.def small{display:block;font:italic 400 24px var(--serif);color:#B8C4D6;margin-top:6px}
.nm{position:absolute;left:110px;top:720px}.nm .a{color:#fff}.nm .o{color:#C9D3E3}
.line{position:absolute;left:110px;top:695px;width:860px;height:3px;background:linear-gradient(90deg,rgba(255,255,255,.15),#6DB527)}
.bus{position:absolute;left:960px;top:505px}
.logo{position:absolute;right:110px;bottom:60px;width:360px}
""", body=f"""<img class="un" src="assets/unila_branco.png"><div class="cmt cm">{CUR}<br>{DAT}</div>
<h1>{TIT}</h1>
<div class="def">Defesa de TCC<small>Trabalho de Conclusão de Curso</small></div><div class="line"></div>{nomes()}
<div class="bus">{bus_h(860, 380, 190, ["sun","wind","h2"], ["bat","grid","load"], x0=0, x1=850, stub=100, dark=True, lbl="#C9D3E3")}</div>
<img class="logo" src="assets/seeds_dark.png">""")

# ------------------------------------------------ B6 · Faixa
V["B6_faixa"] = dict(tag="B6 · Faixa", css=COMUM + """
.un{position:absolute;left:110px;top:60px;height:150px}
.cmt{position:absolute;right:110px;top:100px;text-align:right}
h1{position:absolute;left:110px;top:260px;width:1700px;font-size:60px}
.band{position:absolute;left:0;right:0;bottom:0;height:460px;background:var(--light)}
.band .gr{position:absolute;left:0;right:0;top:0;height:8px;background:linear-gradient(90deg,#6DB527,#1E8A72 55%,#0072BA)}
.def{position:absolute;left:110px;top:665px;font:700 44px var(--serif);color:var(--teal)}
.nm{position:absolute;left:110px;top:760px}
.vr{position:absolute;left:900px;top:680px;width:2px;height:330px;background:var(--line)}
.logo{position:absolute;right:110px;top:790px;width:330px}
.bus{position:absolute;left:960px;top:630px}
""", body=f"""<img class="un" src="assets/unila.png"><div class="cmt cm">{CUR}<br>{DAT}</div>
<h1>{TIT}</h1><div class="band"><div class="gr"></div></div>
<div class="def">Defesa de TCC</div>{nomes()}<div class="vr"></div>
<img class="logo" src="assets/seeds.png">
<div class="bus">{bus_h(540, 420, 210, ["sun","wind","h2"], ["bat","grid","load"], x0=0, x1=520, stub=95)}</div>""")


# ------------------------------------------------ B7 · Oficial (B2 + barramento do B1)
V["B7_oficial"] = dict(tag="", css=COMUM + """
.un{position:absolute;left:110px;top:60px;height:150px}
.cmt{position:absolute;right:110px;top:118px;text-align:right}
h1{position:absolute;left:110px;top:255px;width:1700px;font-size:62px}
.def{position:absolute;left:110px;top:615px;font:700 46px var(--serif);color:var(--teal)}
.def small{display:block;font:italic 400 24px var(--serif);color:var(--slate);margin-top:6px}
.nm{position:absolute;left:110px;top:775px}
.dash{position:absolute;background-image:linear-gradient(90deg,var(--teal) 55%,transparent 0);background-size:14px 2px;height:2px}
.dv{position:absolute;width:2px;background-image:linear-gradient(var(--teal) 55%,transparent 0);background-size:2px 14px}
.logo{position:absolute;left:1160px;top:548px;width:460px}
.bus{position:absolute;left:960px;top:728px}
""", body=f"""<img class="un" src="assets/unila.png"><div class="cmt cm">{DAT}</div>
<h1>{TIT}</h1>
<div class="def">Defesa de TCC<small>Engenharia de Energia · ILATIT</small></div>
<div class="dash" style="left:110px;top:749px;width:846px"></div>{nomes()}
<img class="logo" src="assets/seeds.png"><div class="dv" style="left:1384px;top:700px;height:40px"></div>
<div class="bus">{bus_h(860, 330, 22, [], ["sun","wind","h2","bat","grid","load"], x0=0, x1=850, stub=115)}</div>""")

for nome, p in V.items():
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(**p))
print(list(V))
