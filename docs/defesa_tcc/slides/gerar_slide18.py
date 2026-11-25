"""Slide 18 (deck) — Arquitetura do SEEDS: Fig. 5.1 do artigo IDÊNTICA (mesmos blocos, textos, setas e cores), em disposição horizontal,
com três pontos principais (Seção 5.1). Mesmo critério do slide 16 (Fig. 4.1)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, DEF2, HEAD, NAVY, SLATE, LINE, T, div
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
VER, VERB = "#EAF4EE", "#8CC3A0"          # modularidade
CIN, CINB = "#F1F0EC", "#BDBAB2"          # integração / caixas neutras
AZ, AZB, AZS = "#EAF0F9", "#8FA9D4", "#2F63B5"   # EMS hierárquico · sinal de coordenação
ESC = "#363A45"                           # cabeçalho escuro da representação comum
LAR = "#C47A1E"                           # retorno ou vínculo (laranja tracejado)
TIT = '<div class="tt">Arquitetura do SEEDS</div>'
REF = "Fig. 5.1 do artigo (Seção 5.1), em disposição horizontal"
DEF3 = DEF2.replace("</defs>",
    f'<marker id="ab" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="20" markerHeight="20" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0L10 5L0 10z" fill="{AZS}"/></marker>'
    f'<marker id="ao" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="{LAR}"/></marker>'
    f'<marker id="ak" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="{ESC}"/></marker></defs>')


def caixa(x, y, w, h, tit, sub, fill="#fff", borda=CINB, tpx=22, spx=18, centro=False):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{borda}" stroke-width="2"/>'
    al = "center" if centro else "left"
    t = f'<div style="font:700 {tpx}px/1.2 Gelasio,serif;color:#14213D">{tit}</div>'
    if sub:
        t += f'<div style="font:500 {spx}px/1.32 Manrope;color:#4A5568;margin-top:4px">{sub}</div>'
    return s, div(x + 18, y, w - 36, h, t, "", f"display:flex;flex-direction:column;justify-content:center;text-align:{al}")


def seta(x1, y1, x2, y2, c=ESC, mk="ak", w=2.5, dash=""):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="M{x1} {y1} L{x2} {y2}" fill="none" stroke="{c}" stroke-width="{w}"{da} marker-end="url(#{mk})"/>'


def rot(x, y, txt, c=SLATE, anchor="start", px=17):
    return T(x, y, txt, px, 500, c, "Gelasio", anchor=anchor, it=True)


def slide18():
    s, h = "", ""
    # ---------- grupo 1 · Modularidade
    s += f'<rect x="110" y="172" width="490" height="500" rx="18" fill="{VER}" stroke="{VERB}" stroke-width="2"/>'
    s += T(132, 204, "Modularidade", 22, 700, "#2E8A57", "Gelasio")
    for y, t, sub in ((222, "Modelos físicos e catálogos", "Fotovoltaica, eólica, bateria, PEMFC e conexão à rede (PCC)"),
                      (384, "Configuração da microrrede", "Composição, arranjo e parâmetros; conectada ou isolada; revisões"),
                      (546, "Cenário operativo", "Estados iniciais, disponibilidade, previsões e estratégia EMS")):
        a, b = caixa(130, y, 450, 110, t, sub); s += a; h += b
    s += seta(260, 332, 260, 380) + rot(276, 362, "Seleção de equipamentos")
    s += seta(260, 494, 260, 542) + rot(276, 524, "Revisão referenciada")
    # ---------- grupo 2 · Integração
    s += f'<rect x="680" y="172" width="480" height="500" rx="18" fill="{CIN}" stroke="{CINB}" stroke-width="2"/>'
    s += T(702, 204, "Integração", 22, 700, "#5A5750", "Gelasio")
    s += (f'<rect x="700" y="222" width="440" height="290" rx="14" fill="#fff" stroke="{ESC}" stroke-width="3"/>'
          f'<path d="M700 236 a14 14 0 0 1 14 -14 h412 a14 14 0 0 1 14 14 v66 h-440 z" fill="{ESC}"/>')
    h += div(700, 222, 440, 80, "Representação energética<br>comum por recurso", "",
             "display:flex;align-items:center;justify-content:center;text-align:center;font:700 22px/1.2 Gelasio,serif;color:#fff")
    h += div(712, 312, 416, 196, "<div>Barramento equivalente em kW líquidos<br>Potência renovável disponível<br>Curva H<sub>2</sub>–potência linear por partes"
             "<br>Limites e estados por recurso<br>Intercâmbio e tarifas no PCC</div>", "",
             "display:flex;align-items:center;justify-content:center;text-align:center;font:500 18px/1.6 Gelasio,serif;color:#14213D")
    s += seta(920, 514, 920, 556)
    a, b = caixa(700, 560, 440, 96, "Verificação de compatibilidade", "Representável, excluído ou impeditivo", centro=True); s += a; h += b
    # setas modularidade → representação
    s += seta(582, 262, 696, 262) + rot(640, 252, "Modelos", anchor="middle", px=16)
    s += f'<path d="M582 438 H620 V600 H582" fill="none" stroke="{ESC}" stroke-width="2.5"/>' + seta(620, 440, 696, 440)
    s += rot(658, 412, "Inventário", anchor="middle", px=15) + rot(658, 430, "e cenário", anchor="middle", px=15)
    # ---------- grupo 3 · EMS hierárquico + simulação + resultados
    s += f'<rect x="1250" y="172" width="560" height="296" rx="18" fill="{AZ}" stroke="{AZB}" stroke-width="2"/>'
    s += T(1272, 204, "EMS hierárquico", 22, 700, AZS, "Gelasio")
    a, b = caixa(1270, 222, 470, 84, "Planejamento de horizonte longo", "Custo futuro × energia terminal", tpx=21, spx=17); s += a; h += b
    s += f'<path d="M1400 306 V364" stroke="{AZS}" stroke-width="5" marker-end="url(#ab)"/>' + T(1414, 342, "Sinal de valor futuro", 17, 700, AZS)
    a, b = caixa(1270, 368, 470, 84, "MPC em janelas sucessivas", "Despacho com termo terminal", tpx=21, spx=17); s += a; h += b
    s += seta(1400, 454, 1400, 494) + rot(1414, 480, "Decisões aplicadas")
    a, b = caixa(1270, 498, 470, 62, "Simulação em malha fechada", None, tpx=21, centro=True); s += a; h += b
    s += seta(1505, 562, 1505, 584)
    a, b = caixa(1270, 588, 470, 118, "Resultados e evidência",
                 "Séries por recurso, indicadores operacionais e econômicos, auditoria independente e registros verificáveis sem nova otimização",
                 fill=CIN, tpx=21, spx=16, centro=True); s += a; h += b
    # integração → EMS
    s += f'<path d="M1142 608 H1200 V410 H1266" fill="none" stroke="{ESC}" stroke-width="2.5" marker-end="url(#ak)"/>'
    s += rot(1172, 634, "Problema", px=15) + rot(1172, 652, "de despacho", px=15)
    # estado executado (simulação → MPC e planejamento)
    s += f'<path d="M1742 529 H1782 V264 H1746" fill="none" stroke="{LAR}" stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#ao)"/>'
    s += f'<path d="M1782 410 H1746" fill="none" stroke="{LAR}" stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#ao)"/>'
    s += f'<text x="1806" y="400" font-family="Gelasio" font-style="italic" font-size="16" fill="{LAR}" transform="rotate(-90 1806 400)" text-anchor="middle">Estado executado</text>'
    # pendências (verificação → cenário) e vínculo (resultados → configuração)
    s += f'<path d="M880 658 V700 H126 V601 H126" fill="none" stroke="{LAR}" stroke-width="2.5" stroke-dasharray="7 6"/>' + seta(126, 601, 128, 601, LAR, "ao")
    s += rot(520, 694, "Pendências", LAR, "middle", 16)
    s += f'<path d="M1268 690 H1232 V724 H116 V439 H126" fill="none" stroke="{LAR}" stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#ao)"/>'
    s += rot(700, 744, "Vínculo à revisão do inventário e à versão do cenário", LAR, "middle", 16)
    # legenda
    s += (seta(1270, 744, 1316, 744) + T(1324, 750, "Fluxo de informação", 16, 600, SLATE)
          + f'<path d="M1500 744 H1546" stroke="{AZS}" stroke-width="5" marker-end="url(#ab)"/>' + T(1554, 750, "Sinal de coordenação", 16, 600, SLATE)
          + f'<path d="M1270 772 H1316" stroke="{LAR}" stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#ao)"/>' + T(1324, 778, "Retorno ou vínculo", 16, 600, SLATE))
    # três pontos (Seção 5.1)
    pts = [("Físico separado da estratégia", "Trocar um equipamento muda a instância do problema, não a formulação do EMS."),
           ("Uma representação comum", "Cada recurso entra no mesmo barramento; antes de executar, tudo é verificado, sem aproximar nem omitir recursos."),
           ("Resultados rastreáveis", "Cada rodada fica ligada à revisão do inventário e à versão do cenário que a originaram.")]
    w3, y3 = 540, 800
    for k, (t, d) in enumerate(pts):
        x = 110 + k * (w3 + 40)
        if k:
            s += f'<line x1="{x-20}" x2="{x-20}" y1="{y3}" y2="{y3+120}" stroke="{LINE}" stroke-width="2"/>'
        h += div(x, y3, w3, None, f'<div style="font:700 24px Gelasio,serif;color:#14213D;margin-bottom:6px">{t}</div>{d}', "p", "font-size:21px;line-height:1.32")
    body = (TIT + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEF3}{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(18))
    open(os.path.join(D, "S18_identico.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide18()
