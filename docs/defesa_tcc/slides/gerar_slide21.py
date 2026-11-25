"""Slide 21 (deck) — Verificação e fluxo de execução: Fig. 5.3 do artigo IDÊNTICA (mesmos blocos, textos e cores), ampliada à largura do slide,
+ três pontos (Seção 5.4: valores ausentes nunca viram zero; versão imutável; verificação independente e auditoria; Python/Streamlit 1.66.1,
Pyomo 6.10.1 e HiGHS 1.15.1; consulta posterior refaz a auditoria sem resolver de novo)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, DEF2, HEAD, NAVY, SLATE, LINE, T, div
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
VD, VDF, VDB, VDC = "#25734B", "#EAF4EE", "#8CC3A0", "#D7EDDF"
ESC, CINB, CINF, LAR = "#363A45", "#BDBAB2", "#E6E5E1", "#C47A1E"
TIT = '<div class="tt">Verificação e fluxo de execução</div>'
REF = "Fig. 5.3 do artigo (Seção 5.4)"
DEF3 = DEF2.replace("</defs>",
    f'<marker id="ao" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="14" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0L10 5L0 10z" fill="{LAR}"/></marker>'
    f'<marker id="ak" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="14" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0L10 5L0 10z" fill="{ESC}"/></marker></defs>')

ETAPAS = [("0", "Criação da microrrede", "Recursos, parâmetros e conexão à rede", "Inventário<br>em revisão"),
          ("1", "Inicialização", "Estados iniciais e disponibilidade", "Cenário vinculado"),
          ("2", "Previsões", "Demanda e condições climáticas", "Séries temporais"),
          ("3", "Estratégia EMS", "Horizontes, objetivo e declarações", "Versão do cenário"),
          ("4", "Execução", "Verificação, simulação e resultados", "Rodada e<br>indicadores")]


def slide21():
    s, h = "", ""
    x0, w, gap, y0, hc = 110, 308, 40, 268, 380
    # chaves superiores
    xa = x0 + w
    s += f'<path d="M{x0} 236 V224 H{xa} V236" fill="none" stroke="{VD}" stroke-width="3"/>' + T((x0 + xa) / 2, 206, "Sistema físico", 26, 700, VD, "Gelasio", anchor="middle")
    xb, xe = x0 + w + gap, x0 + 5 * w + 4 * gap
    s += f'<path d="M{xb} 236 V224 H{xe} V236" fill="none" stroke="{ESC}" stroke-width="3"/>' + T((xb + xe) / 2, 206, "Cenário operativo / versão salva", 26, 700, ESC, "Gelasio", anchor="middle")
    for i, (n, t, sub, prod) in enumerate(ETAPAS):
        x = x0 + i * (w + gap)
        verde = i == 0
        fill, borda, circ = (VDF, VDB, VD) if verde else ("#fff", CINB, ESC)
        s += f'<rect x="{x}" y="{y0}" width="{w}" height="{hc}" rx="18" fill="{fill}" stroke="{borda}" stroke-width="2.5"/>'
        s += f'<circle cx="{x+w/2}" cy="{y0}" r="30" fill="{circ}" stroke="#fff" stroke-width="4"/>' + T(x + w / 2, y0 + 11, n, 30, 700, "#fff", "Gelasio", anchor="middle")
        h += div(x + 14, y0 + 40, w - 28, 196,
                 f'<div style="font:700 24px Gelasio,serif;color:{VD if verde else "#14213D"}">Etapa {n}</div>'
                 f'<div style="font:700 29px/1.15 Gelasio,serif;color:#14213D;margin-top:2px">{t}</div>'
                 f'<div style="font:500 22px/1.35 Gelasio,serif;color:#4A5568;margin-top:12px">{sub}</div>', "",
                 "display:flex;flex-direction:column;align-items:center;justify-content:flex-start;text-align:center")
        pf, pb, pc = (VDC, VDB, VD) if verde else (CINF, CINB, "#14213D")
        s += f'<rect x="{x+18}" y="{y0+hc-104}" width="{w-36}" height="84" rx="12" fill="{pf}" stroke="{pb}" stroke-width="2"/>'
        h += div(x + 18, y0 + hc - 104, w - 36, 84, prod, "", f"display:flex;align-items:center;justify-content:center;text-align:center;font:700 23px/1.2 Gelasio,serif;color:{pc}")
        if i < 4:
            s += f'<path d="M{x+w+6} {y0+hc/2} H{x+w+gap-6}" stroke="{ESC}" stroke-width="3" marker-end="url(#ak)"/>'
    # retorno de pendências (da etapa 4 às etapas 1–3)
    yb = y0 + hc + 46
    xs = [x0 + i * (w + gap) + w / 2 for i in range(1, 5)]
    s += f'<path d="M{xs[3]} {y0+hc} V{yb} H{xs[0]}" fill="none" stroke="{LAR}" stroke-width="3" stroke-dasharray="9 7"/>'
    for xx in xs[:3]:
        s += f'<path d="M{xx} {yb} V{y0+hc+6}" fill="none" stroke="{LAR}" stroke-width="3" stroke-dasharray="9 7" marker-end="url(#ao)"/>'
    s += T((xs[0] + xs[3]) / 2, yb + 36, "Pendências da verificação de compatibilidade retornam às Etapas 1 a 3", 22, 500, LAR, "Gelasio", anchor="middle", it=True)
    # legenda
    s += f'<path d="M{x0} {yb+6} H{x0+50}" stroke="{ESC}" stroke-width="3" marker-end="url(#ak)"/>' + T(x0 + 60, yb + 12, "Sequência das etapas", 18, 600, SLATE)
    s += f'<path d="M{x0} {yb+36} H{x0+50}" stroke="{LAR}" stroke-width="3" stroke-dasharray="9 7" marker-end="url(#ao)"/>' + T(x0 + 60, yb + 42, "Retorno de pendências", 18, 600, SLATE)
    # três pontos (Seção 5.4)
    pts = [("Nada é presumido", "Valores ausentes nunca viram zero; incoerências impedem salvar e pendências voltam às etapas 1 a 3."),
           ("Cada decisão é verificada", "Pyomo 6.10.1 e HiGHS 1.15.1 resolvem cada janela; uma verificação independente confere a solução e, ao fim, uma auditoria integral."),
           ("Cada estudo é reprodutível", "A rodada fica ligada a uma versão imutável do cenário; reabri-la refaz a auditoria sem otimizar de novo.")]
    w3, y3 = 540, 768
    for k, (t, d) in enumerate(pts):
        x = 110 + k * (w3 + 40)
        if k:
            s += f'<line x1="{x-20}" x2="{x-20}" y1="{y3}" y2="{y3+140}" stroke="{LINE}" stroke-width="2"/>'
        h += div(x, y3, w3, None, f'<div style="font:700 24px Gelasio,serif;color:#14213D;margin-bottom:6px">{t}</div>{d}', "p", "font-size:22px;line-height:1.38")
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEF3}{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(21))
    open(os.path.join(D, "S21_identico.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide21()
