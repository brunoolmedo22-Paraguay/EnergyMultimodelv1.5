"""Slide 20 (deck) — Gerenciamento energético hierárquico no SEEDS: Fig. 5.2 do artigo IDÊNTICA (mesmos blocos, textos, setas e cores),
ajustada à largura do slide, + três pontos (Seção 5.3). Mesmo critério dos slides 16 e 18."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, DEF2, HEAD, NAVY, SLATE, LINE, T, div
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
AZ, AZH, AZB, AZS = "#EAF0F9", "#D9E4F3", "#9DB6DC", "#2F63B5"
ESC, CIN, LAR, CINA = "#363A45", "#E6E5E1", "#C47A1E", "#6B7280"
TIT = '<div class="tt">Gerenciamento energético hierárquico no SEEDS</div>'
REF = "Fig. 5.2 do artigo (Seção 5.3)"
DEF3 = DEF2.replace("</defs>",
    f'<marker id="ab" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="16" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0L10 5L0 10z" fill="{AZS}"/></marker>'
    f'<marker id="ao" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0L10 5L0 10z" fill="{LAR}"/></marker>'
    f'<marker id="ag" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0L10 5L0 10z" fill="{CINA}"/></marker>'
    f'<marker id="ak" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0L10 5L0 10z" fill="{ESC}"/></marker></defs>')


def caixa(x, y, w, h, tit, sub=None, forte=False, barra=True, fill="#fff", borda=AZB, tpx=19, spx=15.5, centro=False):
    bw = 4 if forte else 2
    bc = AZS if forte else borda
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{bc}" stroke-width="{bw}"/>'
    if barra:
        s += f'<rect x="{x+bw/2}" y="{y+bw/2}" width="6" height="{h-bw}" rx="2" fill="{AZS}"/>'
    t = f'<div style="font:700 {tpx}px/1.2 Gelasio,serif;color:#14213D">{tit}</div>'
    if sub:
        t += f'<div style="font:500 {spx}px/1.3 Manrope;color:#4A5568;margin-top:3px">{sub}</div>'
    al = "center" if centro else "left"
    return s + "", div(x + (16 if barra else 10), y, w - (24 if barra else 20), h, t, "", f"display:flex;flex-direction:column;justify-content:center;text-align:{al}")


def losango(cx, cy, w, h, txt, px=18):
    s = f'<path d="M{cx-w/2} {cy} L{cx} {cy-h/2} L{cx+w/2} {cy} L{cx} {cy+h/2} Z" fill="#fff" stroke="{AZS}" stroke-width="2.5"/>'
    return s, div(cx - w / 2 + 20, cy - h / 2, w - 40, h, txt, "", f"display:flex;align-items:center;justify-content:center;text-align:center;font:700 {px}px/1.15 Gelasio,serif;color:#14213D")


def lin(d, c=ESC, mk="ak", w=2.5, dash=""):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    m = f' marker-end="url(#{mk})"' if mk else ""
    return f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}"{da}{m}/>'


def it(x, y, t, c=SLATE, px=15, anchor="start", rot=None):
    tr = f' transform="rotate({rot} {x} {y})"' if rot is not None else ""
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Gelasio" font-style="italic" font-size="{px}" fill="{c}"{tr}>{t}</text>'


def slide20():
    s, h = "", ""

    def add(par):
        nonlocal s, h
        s += par[0]; h += par[1]

    # ---------------- nível de planejamento
    s += f'<rect x="110" y="168" width="500" height="582" rx="14" fill="{AZ}" stroke="{AZB}" stroke-width="2"/>'
    s += f'<path d="M110 182 a14 14 0 0 1 14 -14 h472 a14 14 0 0 1 14 14 v44 h-500 z" fill="{AZH}"/>'
    s += T(126, 194, "Nível de planejamento", 20, 700, AZS, "Gelasio")
    h += div(126, 198, 300, None, "Horizonte longo <i style='font-family:Gelasio'>H<sub>L</sub></i>", "", "font:500 16px Manrope;color:#2F63B5")
    add(losango(370, 270, 270, 70, "Replanejar<br>nesta janela?"))
    add(caixa(160, 320, 420, 58, "Plano longo a partir de <i>x<sub>k</sub></i>", "Trajetória de referência, não aplicada"))
    add(caixa(160, 392, 420, 92, "Reotimizações paramétricas", "Custo futuro × energia terminal, por modo das unidades despacháveis, e domínio viável"))
    add(caixa(160, 500, 420, 62, "Sinal de valor futuro", "Emitido por janela ou em lote", forte=True))
    add(caixa(160, 662, 420, 76, "Degradação declarada", "Sem valor futuro, energia mínima do plano longo ou interrupção"))
    s += lin("M370 305 V318") + it(378, 316, "Sim", px=14) + lin("M370 378 V390") + lin("M370 484 V498")
    s += lin("M235 270 H132 V531 H156", CINA, "ag", 2.2, "7 5") + it(146, 262, "Não", px=14)
    s += it(124, 470, "Sinal do lote vigente", CINA, 14, "middle", -90)
    # ---------------- topo
    add(caixa(650, 168, 400, 86, "Condições iniciais e horizonte",
              "Estado inicial <i>x</i><sub>0</sub> / discretização Δ<i>t</i><br>Horizontes <i>N</i>, <i>m</i> e <i>H<sub>L</sub></i> / duração <i>K</i>",
              barra=False, fill=CIN, borda=ESC, centro=True))
    s += s.count("") * "" + f'<rect x="650" y="168" width="400" height="86" rx="12" fill="none" stroke="{ESC}" stroke-width="3"/>'
    s += lin("M1052 210 H1094")
    add(caixa(1098, 168, 250, 86, "Instante de decisão <i>τ<sub>k</sub></i>", "Estado executado <i>x<sub>k</sub></i>", barra=False, borda="#B9BCC4", centro=True))
    add(caixa(1530, 168, 280, 86, "Auditoria integral<br>e registro", None, barra=False, fill=CIN, borda=ESC, tpx=20, centro=True))
    s += f'<rect x="1530" y="168" width="280" height="86" rx="12" fill="none" stroke="{ESC}" stroke-width="3"/>'
    # ---------------- nível operacional
    s += f'<rect x="650" y="290" width="1160" height="460" rx="14" fill="{AZ}" stroke="{AZB}" stroke-width="2"/>'
    s += f'<path d="M650 304 a14 14 0 0 1 14 -14 h1132 a14 14 0 0 1 14 14 v42 h-1160 z" fill="{AZH}"/>'
    h += div(666, 296, 600, None, "<b style='font-family:Gelasio;font-size:20px;color:#2F63B5'>Nível operacional</b> <b style='font-family:Gelasio;font-size:20px'>/</b> "
             "<b style='font-family:Gelasio;font-size:20px;color:#2F63B5'>MPC</b> &nbsp;<span style='font:500 16px Manrope;color:#2F63B5'>Janela <i>N</i>, aplicação <i>m</i></span>", "", "")
    add(caixa(680, 360, 420, 58, "Informações disponíveis até <i>τ<sub>k</sub></i>", "Registro vinculado à decisão"))
    add(caixa(680, 432, 420, 58, "Previsão da janela", "<i>N<sub>k</sub></i> intervalos a partir de <i>x<sub>k</sub></i>"))
    add(caixa(680, 510, 420, 58, "Verificação do sinal", "Janela, causalidade, domínio e modos"))
    add(losango(890, 614, 230, 56, "Sinal válido?"))
    add(caixa(680, 664, 420, 72, "MILP da janela", "Custo de operação + custo futuro terminal", forte=True))
    s += lin("M890 418 V430") + lin("M890 490 V508") + lin("M890 568 V584") + lin("M890 642 V662") + it(898, 658, "Sim", px=14)
    s += lin("M775 614 H370 V666", CINA, "ag", 2.2, "7 5") + it(760, 606, "Não", px=14, anchor="end")
    s += lin("M580 703 H676", CINA, "ag", 2.2, "7 5")
    s += lin("M580 531 H676", AZS, "ab", 5)
    # coluna direita
    add(caixa(1300, 672, 480, 64, "Verificação independente da solução"))
    add(caixa(1300, 584, 480, 72, "Aplicação dos <i>m</i> primeiros intervalos", "Simulação com os dados realizados"))
    add(caixa(1300, 498, 480, 70, "Atualização do estado executado", "Custo realizado, sem o custo futuro"))
    add(losango(1540, 430, 270, 62, "Fim da simulação?"))
    s += lin("M1100 700 H1296") + lin("M1540 672 V658") + lin("M1540 584 V570") + lin("M1540 498 V463")
    s += lin("M1540 399 V256") + it(1550, 340, "Sim", px=14)
    s += lin("M1405 430 H1250 V256", LAR, "ao", 2.2, "7 5") + it(1392, 422, "Não", LAR, 14, "end")
    s += it(1240, 340, "Próximo instante τ<tspan font-size=\"11\" dy=\"4\">k+m</tspan>", LAR, 14, "middle", -90)
    # instante → planejamento e operacional
    s += lin("M1180 254 V276 H507", ESC, "ak") + f'<circle cx="660" cy="276" r="4" fill="{ESC}"/>' + lin("M660 276 V389 H676")
    # legenda
    y = 772
    s += (lin(f"M110 {y} H160") + T(168, y + 6, "Sequência", 16, 600, SLATE)
          + lin(f"M330 {y} H380", AZS, "ab", 5) + T(388, y + 6, "Sinal de valor futuro", 16, 600, SLATE)
          + lin(f"M620 {y} H670", CINA, "ag", 2.2, "7 5") + T(678, y + 6, "Caminho alternativo", 16, 600, SLATE)
          + lin(f"M900 {y} H950", LAR, "ao", 2.2, "7 5") + T(958, y + 6, "Avanço do horizonte", 16, 600, SLATE))
    # três pontos (Seção 5.3)
    pts = [("Custo futuro calculado por pontos", "O trecho após a janela é resolvido várias vezes; uma função por modo das unidades."),
           ("Sinal verificado antes do uso", "Janela, causalidade, domínio e modos; se inválido, vale a degradação declarada."),
           ("Realizado ≠ futuro", "Só os m intervalos aplicados entram no custo; o custo futuro fica à parte.")]
    w3, y3 = 540, 808
    for k, (t, d) in enumerate(pts):
        x = 110 + k * (w3 + 40)
        if k:
            s += f'<line x1="{x-20}" x2="{x-20}" y1="{y3}" y2="{y3+104}" stroke="{LINE}" stroke-width="2"/>'
        h += div(x, y3, w3, None, f'<div style="font:700 23px Gelasio,serif;color:#14213D;margin-bottom:4px">{t}</div>{d}', "p", "font-size:21px;line-height:1.3")
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEF3}{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(20))
    open(os.path.join(D, "S20_identico.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide20()
