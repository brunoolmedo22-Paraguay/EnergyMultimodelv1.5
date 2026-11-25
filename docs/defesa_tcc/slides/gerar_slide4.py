"""Slide 4 — Decisões com consequências futuras. Três maquetes (A espelho+tempo, B linha do tempo, C janelas aninhadas).
Conteúdo da Introdução do artigo: cadeia CEPEL NEWAVE (médio/longo) → DECOMP (curto) → DESSEM (programação diária) [8–10];
custo futuro da água [11]; decisões intertemporais na microrrede [7, 14]; filosofias conectada × isolada."""
import os
D = os.path.dirname(os.path.abspath(__file__))

SOLAR, WIND, PEM, BAT, REDE, NAVY, SLATE, TEAL = "#D9A21B", "#4C8DD6", "#1BA39C", "#7B6CF6", "#E0524F", "#14213D", "#4A5568", "#1F7A6D"
AGUA, TERM = "#3B82C4", "#8A5A44"

ICON = {
 "bat": '<rect x="6" y="11" width="25" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="3"/><rect x="32" y="16" width="3" height="8" fill="currentColor"/><rect x="10" y="15" width="11" height="10" fill="currentColor"/>',
 "h2": '<text x="20" y="27" text-anchor="middle" font-family="Manrope,sans-serif" font-weight="800" font-size="19" fill="currentColor">H₂</text>',
 "grid": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M14 37L20 4l6 33M10 12h20M8 20h24M16 29h8"/></g>',
 "drop": '<path d="M20 4C14 13 9 19 9 25a11 11 0 0 0 22 0c0-6-5-12-11-21z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>',
 "fire": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M6 36V22l7 4v-4l7 4V10h6v26z"/><path d="M29 8c2-3 6-2 6 1"/><path d="M27 3c2-1 4 0 4 2"/></g>',
 "clock": '<circle cx="20" cy="20" r="15" fill="none" stroke="currentColor" stroke-width="3"/><path d="M20 11v10l7 4" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
 "peak": '<g fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><path d="M4 30h9V14h14v16h9"/></g>',
 "cloud": '<path d="M12 31h17a7 7 0 0 0 0-14 10 10 0 0 0-19 3 6 6 0 0 0 2 11z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>',
}


def ic(k, s, c):
    return f'<svg width="{s}" height="{s}" viewBox="0 0 40 40" style="color:{c};flex:none">{ICON[k]}</svg>'


def reservatorio(W, H, nivel=.62):
    """Vale com represa: água até `nivel` da altura útil."""
    yb = H - 8; yt = 18; yw = yb - (yb - yt) * nivel
    xl = W * .06; xr = W * .78
    vale = f"M{xl} {yt} L{W*.30} {yb} L{W*.62} {yb} L{xr} {yt}"
    # água: interseção do vale com y >= yw
    fx = lambda y, a, b: a + (b - a) * (y - yt) / (yb - yt)
    wl = fx(yw, xl, W * .30); wr = fx(yw, xr, W * .62)
    return (f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<path d="M{wl} {yw} L{W*.30} {yb} L{W*.62} {yb} L{wr} {yw} Z" fill="{AGUA}" opacity=".85"/>'
            f'<path d="M{wl} {yw} L{wr} {yw}" stroke="#fff" stroke-width="2" opacity=".7"/>'
            f'<path d="{vale}" fill="none" stroke="{SLATE}" stroke-width="3" stroke-linejoin="round"/>'
            f'<rect x="{xr-4}" y="{yt-4}" width="{W*.08}" height="{yb-yt+4}" rx="3" fill="#C9D3DD" stroke="{SLATE}" stroke-width="2.5"/>'
            f'<path d="M{xr+W*.08} {yb-14} q{W*.06} 0 {W*.12} 10" fill="none" stroke="{AGUA}" stroke-width="5" stroke-linecap="round"/>'
            f'</svg>')


def bateria(W, H, nivel=.62):
    pad = 6; cw = W - 18
    lv = (H - 2 * pad - 8) * nivel
    return (f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<rect x="3" y="3" width="{cw}" height="{H-6}" rx="16" fill="#fff" stroke="{BAT}" stroke-width="4"/>'
            f'<rect x="{cw+3}" y="{H/2-16}" width="12" height="32" rx="4" fill="{BAT}"/>'
            f'<rect x="{3+pad+4}" y="{H-3-pad-4-lv}" width="{cw-2*pad-8}" height="{lv}" rx="10" fill="{BAT}" opacity=".85"/>'
            f'</svg>')


def tarifa(W, H, lbl=True):
    y0, y1 = H - 22, 14
    xa, xb = W * .66, W * .82
    d = f"M0 {y0-18} H{xa} V{y1} H{xb} V{y0-18} H{W}"
    out = (f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
           f'<rect x="{xa}" y="4" width="{xb-xa}" height="{H-26}" fill="{REDE}" opacity=".10"/>'
           f'<path d="{d}" fill="none" stroke="{REDE}" stroke-width="3.5" stroke-linejoin="round"/>')
    if lbl:
        out += (f'<text x="{(xa+xb)/2}" y="{H-4}" text-anchor="middle" font-family="Manrope" font-weight="700" font-size="15" fill="{REDE}">ponta</text>'
                f'<text x="0" y="{H-4}" font-family="Manrope" font-size="14" fill="#9AA5B1">tarifa</text>')
    return out + "</svg>"


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
.card{position:absolute;background:#EEF3F2;border-radius:26px}
.h{font:700 30px "Gelasio",serif}
.k{font:600 17px "Manrope";color:#4A5568}
.cap{font:500 18px "Manrope";color:#4A5568}
.hz{display:flex;align-items:center;height:44px;border-radius:12px;color:#fff;font:700 19px "Manrope";padding:0 16px;justify-content:space-between}
.hz span{font:500 15px "Manrope";opacity:.9;white-space:nowrap}
.ev{display:flex;align-items:center;gap:12px;background:#fff;border-radius:16px;padding:12px 16px;font:600 18px "Manrope";line-height:1.25}
.ev small{display:block;font:500 14px "Manrope";color:#7B8794}
.arw{flex:none}
.eq{position:absolute;width:86px;height:86px;border-radius:50%;background:#14213D;color:#C1FF72;display:flex;flex-direction:column;align-items:center;justify-content:center;font:700 34px "Gelasio",serif;line-height:1}
.eq small{font:600 11px "Manrope";color:#fff;margin-top:4px;text-align:center;line-height:1.1}
.chip{display:inline-flex;align-items:center;gap:12px;background:#fff;border:2px solid #DCE3E2;border-radius:40px;padding:10px 22px;font:600 19px "Manrope"}
.chip b{font:700 19px "Gelasio",serif}
.dest{display:flex;align-items:center;gap:22px;font:italic 400 36px "Gelasio",serif;color:#fff;background:#14213D;border-radius:22px;padding:22px 34px}
.dest b{font-style:normal;color:#C1FF72}
.lane{position:absolute;display:flex;align-items:center}
.tag{font:700 14px "Manrope";letter-spacing:.04em;color:#7B8794}
"""
RODAPE = ('<div class="hl" style="bottom:112px"></div><div class="ft"><img src="../capa/assets/unila.png"><div class="sep"></div>'
          '<span>Engenharia de Energia · ILATIT</span><div class="sep"></div><span><b>Defesa de TCC</b> · Bruno Manuel Olmedo Chávez</span></div>'
          '<div class="pn">4</div>')
REF = '<div class="ref">[8–11] CEPEL: NEWAVE, DECOMP e DESSEM; custo futuro da água · [7, 14] decisões intertemporais em microrredes</div>'
TIT = '<div class="tt">Decisões com consequências futuras</div>'
DEST = '<div class="dest" style="position:absolute;left:110px;right:110px;top:{top}px"><span>O que se decide agora <b>define o que será possível depois.</b></span></div>'


def seta(W=60, c=NAVY):
    return (f'<svg class="arw" width="{W}" height="24" viewBox="0 0 {W} 24"><path d="M2 12 H{W-12}" stroke="{c}" stroke-width="3" stroke-dasharray="2 6" stroke-linecap="round"/>'
            f'<path d="M{W-14} 4 L{W-2} 12 L{W-14} 20" fill="none" stroke="{c}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def evento(k, c, txt, sub):
    return f'<div class="ev">{ic(k, 34, c)}<div>{txt}<small>{sub}</small></div></div>'


def filosofias():
    return ('<div style="display:flex;gap:16px;align-items:center">'
            f'<span class="k" style="margin-right:4px">Filosofia de gestão:</span>'
            f'<span class="chip">{ic("grid", 26, REDE)}<b>Conectada</b> → reduzir o custo</span>'
            f'<span class="chip">{ic("bat", 26, BAT)}<b>Isolada</b> → garantir o atendimento</span></div>')


P = {}

# ===================== A · Espelho SIN ≡ microrrede + consequências no tempo
b = TIT
L, Wc, T, Hc = 110, 820, 170, 560
b += f'<div class="card" style="left:{L}px;top:{T}px;width:{Wc}px;height:{Hc}px"></div>'
b += f'<div class="card" style="left:{1920-110-Wc}px;top:{T}px;width:{Wc}px;height:{Hc}px"></div>'
b += f'<div class="eq" style="left:{960-43}px;top:{T+352}px">≡<small>mesmo<br>princípio</small></div>'
# SIN
x = L + 36
b += f'<div style="position:absolute;left:{x}px;top:{T+28}px"><div class="tag">SISTEMA INTERLIGADO NACIONAL</div><div class="h" style="margin-top:4px">Água armazenada</div></div>'
b += f'<div style="position:absolute;left:{x}px;top:{T+110}px">{reservatorio(330, 190)}</div>'
hz = [("NEWAVE", "médio e longo prazo", 370, "#0E4F86"), ("DECOMP", "curto prazo", 320, "#2C6FB0"), ("DESSEM", "programação diária", 270, AGUA)]
for i, (n, s, w, c) in enumerate(hz):
    b += f'<div class="hz" style="position:absolute;left:{x+350 + (370-w)}px;top:{T+108+i*62}px;width:{w}px;background:{c}">{n}<span>{s}</span></div>'
b += f'<div class="k" style="position:absolute;left:{x+350}px;top:{T+300}px;width:370px;text-align:right;font-size:15px">horizontes maiores orientam os menores [8–10]</div>'
b += (f'<div style="position:absolute;left:{x}px;top:{T+352}px;width:{Wc-72}px">'
      f'<div class="tag" style="margin-bottom:8px">AGORA → DEPOIS</div>'
      f'<div style="display:flex;align-items:center;gap:10px">{evento("drop", AGUA, "Turbinar a água", "hoje")}{seta(70)}{evento("fire", TERM, "Térmica mais cara", "amanhã")}</div>'
      f'<div class="cap" style="margin-top:12px">Cada decisão presente tem um <b style="color:#14213D">custo futuro</b> [11].</div></div>')
# Microrrede
x = 1920 - 110 - Wc + 36 + 50
b += f'<div style="position:absolute;left:{x}px;top:{T+28}px"><div class="tag">MICRORREDE</div><div class="h" style="margin-top:4px">Energia armazenada e estados</div></div>'
b += f'<div style="position:absolute;left:{x}px;top:{T+122}px">{bateria(250, 150)}</div>'
b += f'<div style="position:absolute;left:{x+300}px;top:{T+120}px">{tarifa(380, 120)}</div>'
b += (f'<div style="position:absolute;left:{x+300}px;top:{T+262}px;display:flex;align-items:center;gap:10px" class="k">'
      f'{ic("h2", 30, PEM)} PEMFC ligada: tempo mínimo  {ic("cloud", 28, SLATE)} previsões</div>')
b += (f'<div style="position:absolute;left:{x}px;top:{T+352}px;width:{Wc-120}px">'
      f'<div class="tag" style="margin-bottom:8px">AGORA → DEPOIS</div>'
      f'<div style="display:flex;align-items:center;gap:10px">{evento("bat", BAT, "Descarregar a bateria", "tarifa baixa")}{seta(56)}{evento("peak", REDE, "Falta na ponta", "tarifa alta")}</div>'
      f'<div style="display:flex;align-items:center;gap:10px;margin-top:10px">{evento("h2", PEM, "Ligar a PEMFC", "agora")}{seta(56)}{evento("clock", PEM, "Permanência obrigatória", "depois")}</div></div>')
b += f'<div style="position:absolute;left:110px;top:752px">{filosofias()}</div>'
b += DEST.format(top=816)
P["S4_A_espelho"] = b + REF + RODAPE

# ===================== B · Linha do tempo «agora → depois» protagonista
b = TIT
x0, x1, yax = 470, 1790, 210
b += (f'<svg width="1920" height="1080" style="position:absolute;left:0;top:0"><defs><linearGradient id="gt" x1="0" x2="1">'
      f'<stop offset="0" stop-color="#6DB527"/><stop offset=".55" stop-color="#1E8A72"/><stop offset="1" stop-color="#0072BA"/></linearGradient></defs>'
      f'<rect x="{x0}" y="{yax-6}" width="{x1-x0-30}" height="12" rx="6" fill="url(#gt)"/>'
      f'<path d="M{x1-40} {yax-22} L{x1} {yax} L{x1-40} {yax+22} Z" fill="#0072BA"/>'
      f'<line x1="{x0+150}" x2="{x0+150}" y1="{yax+12}" y2="770" stroke="#C9D3DD" stroke-width="2" stroke-dasharray="4 8"/>'
      f'<line x1="{x1-260}" x2="{x1-260}" y1="{yax+12}" y2="770" stroke="#C9D3DD" stroke-width="2" stroke-dasharray="4 8"/></svg>')
b += f'<div style="position:absolute;left:{x0+90}px;top:{yax-58}px;font:700 28px Gelasio,serif">agora</div>'
b += f'<div style="position:absolute;left:{x1-310}px;top:{yax-58}px;font:700 28px Gelasio,serif">depois</div>'
lanes = [
    ("SIN", "Água armazenada", reservatorio(150, 92), ("drop", AGUA, "Turbinar a água"), ("fire", TERM, "Térmica mais cara"), "custo futuro da água [11]"),
    ("MICRORREDE", "Bateria", bateria(120, 76), ("bat", BAT, "Descarregar fora da ponta"), ("peak", REDE, "Falta energia na ponta"), "tarifa baixa → tarifa alta"),
    ("MICRORREDE", "PEMFC", f'<div style="width:120px;height:76px;display:flex;align-items:center;justify-content:center">{ic("h2", 64, PEM)}</div>', ("h2", PEM, "Ligar a célula"), ("clock", PEM, "Permanência obrigatória"), "tempo mínimo em operação"),
    ("MICRORREDE", "Previsões", f'<div style="width:120px;height:76px;display:flex;align-items:center;justify-content:center">{ic("cloud", 64, SLATE)}</div>', ("cloud", SLATE, "Decidir com previsão"), ("clock", SLATE, "Rever a decisão"), "nova informação chega"),
]
for i, (tag, nome, viz, ag, dp, nota) in enumerate(lanes):
    y = 262 + i * 122
    b += (f'<div class="lane" style="left:110px;top:{y}px;width:340px;gap:16px">{viz}<div><div class="tag">{tag}</div>'
          f'<div style="font:700 22px Gelasio,serif">{nome}</div></div></div>')
    b += f'<div style="position:absolute;left:{x0+20}px;top:{y+10}px">{evento(ag[0], ag[1], ag[2], "agora")}</div>'
    b += f'<div style="position:absolute;left:{x1-400}px;top:{y+10}px">{evento(dp[0], dp[1], dp[2], "depois")}</div>'
    b += (f'<svg width="560" height="60" style="position:absolute;left:{x0+390}px;top:{y+14}px"><path d="M4 30 C180 -6, 380 -6, 540 30" fill="none" stroke="{ag[1]}" stroke-width="3" stroke-dasharray="2 7" stroke-linecap="round"/>'
          f'<path d="M526 18 L544 31 L524 40" fill="none" stroke="{ag[1]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>'
          f'<div class="k" style="position:absolute;left:{x0+390}px;top:{y+60}px;width:560px;text-align:center;font-size:15px;color:#7B8794">{nota}</div>')
    if i == 0:
        b += f'<div style="position:absolute;left:110px;right:110px;top:{y+108}px;border-top:1px dashed #C9D3DD"></div>'
b += f'<div style="position:absolute;left:110px;top:752px">{filosofias()}</div>'
b += DEST.format(top=816)
P["S4_B_tempo"] = b + REF + RODAPE

# ===================== C · Janelas aninhadas (horizontes)
b = TIT


def ninho(x, y, W, cores, nomes, subs, icone, titulo, tag):
    out = f'<div style="position:absolute;left:{x}px;top:{y}px;width:330px;display:flex;gap:16px;align-items:center">{icone}<div><div class="tag">{tag}</div><div class="h" style="font-size:26px">{titulo}</div></div></div>'
    xx, ww, hh, yy = x + 380, W, 200, y - 20
    for i, (c, n, s) in enumerate(zip(cores, nomes, subs)):
        out += (f'<div style="position:absolute;left:{xx}px;top:{yy}px;width:{ww}px;height:{hh}px;border:3px solid {c};border-radius:22px;background:{c}{"14" if i else "0d"}">'
                f'<div style="position:absolute;right:18px;top:12px;text-align:right"><div style="font:700 21px Manrope;color:{c}">{n}</div><div class="k" style="font-size:14px">{s}</div></div></div>')
        xx += 24; yy += 24; hh -= 48; ww = ww * .58
    return out


b += ninho(110, 210, 1300, ["#0E4F86", "#2C6FB0", AGUA], ["NEWAVE", "DECOMP", "DESSEM"], ["médio e longo prazo", "curto prazo", "programação diária"],
           reservatorio(140, 90), "Água armazenada", "SIN")
b += ninho(110, 470, 1300, [TEAL, "#2A9A5C", "#6DB527"], ["Planejamento longo", "Decisão de curto prazo", "Aplicação"], ["horizonte ampliado", "janela da operação", "o agora"],
           bateria(120, 76), "Energia armazenada", "MICRORREDE")
b += (f'<svg width="60" height="90" style="position:absolute;left:520px;top:368px"><path d="M30 4 V70" stroke="{NAVY}" stroke-width="3" stroke-dasharray="2 7" stroke-linecap="round"/>'
      f'<path d="M18 60 L30 76 L42 60" fill="none" stroke="{NAVY}" stroke-width="3" stroke-linecap="round"/></svg>'
      f'<div style="position:absolute;left:590px;top:394px;font:italic 400 24px Gelasio,serif;color:{TEAL}">o maior orienta o menor — o mesmo princípio em escala menor</div>')
b += f'<div style="position:absolute;left:110px;top:752px">{filosofias()}</div>'
b += DEST.format(top=816)
P["S4_C_janelas"] = b + REF + RODAPE

HEAD = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="slide">{body}</div></body></html>'
for nome, body in P.items():
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSS, body=body))
print(list(P))
