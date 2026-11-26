"""Slide 36 (deck) — Conclusões. Fecha a pergunta do slide 7 (cartão escuro, mesmos destaques em lima) e marca os quatro objetivos
específicos com a evidência; à direita, a comparação dos dois estudos pedida pelo responsável («na microrrede industrial
observamos… / na embarcação observamos…»). Texto: Seção 8 e Seção 7 do artigo; números já apresentados nos slides 31–34.
Ressalva do artigo mantida: a separação física × estratégia «se sustenta dentro do conjunto de recursos que a formulação representa»."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, LIGHT, div, ic, SOLAR, REDE, BAT, PEM
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = "Conclusões"
REF = "Seções 7 e 8 do artigo"
TEAL, LIMA = "#1F7A6D", "#C1FF72"
PERG = (f'<span style="color:{LIMA}">Um mesmo gerenciamento energético</span> consegue operar '
        f'<span style="color:{LIMA}">microrredes de composições diferentes</span>, considerando '
        f'<span style="color:{LIMA}">o valor futuro da energia armazenada</span>?')
OBJ = [("Representação energética comum", "modelos físicos em 9 composições, sem inconsistências"),
       ("EMS hierárquico MILP–MPC com sinal de valor futuro", "valor futuro em todas as decisões; 168 janelas ótimas"),
       ("Avaliação em dois sistemas distintos", "microrrede industrial e embarcação híbrida"),
       ("Expansibilidade e desempenho computacional", "7 → 217 variáveis; até 5 s por decisão")]
CHECK = '<path d="M11 21 L17 27 L29 14" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'


def estudo(x, y, w, hc, cor, icones, titulo, pontos):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{hc}" rx="24" fill="{LIGHT}"/><rect x="{x}" y="{y+24}" width="6" height="{hc-48}" rx="3" fill="{cor}"/>'
    for k, (kk, c) in enumerate(icones):
        cx = x + w - 44 - (len(icones) - 1 - k) * 50
        s += f'<circle cx="{cx}" cy="{y+40}" r="19" fill="#fff" stroke="{c}" stroke-width="2.5"/>' + ic(kk, cx - 12, y + 28, 24, c)
    h = div(x + 34, y + 20, w - 260, None, titulo, "", "font:700 30px Gelasio,serif;color:#14213D")
    lis = "".join(f'<li style="margin:0 0 12px 0">{p}</li>' for p in pontos)
    h += div(x + 34, y + 76, w - 68, None, f'<ul style="margin:0;padding-left:24px">{lis}</ul>', "p", "font-size:28px;line-height:1.34")
    return s, h


def slide():
    s, h = "", ""
    # pergunta e resposta
    s += f'<rect x="110" y="166" width="700" height="330" rx="26" fill="{NAVY}"/>'
    h += div(146, 194, 630, None, PERG, "", "font:600 28px/1.4 Manrope;color:#fff")
    h += div(146, 362, 630, None, '<span style="font:700 56px Gelasio,serif;color:#fff">Sim,</span>'
             '<span style="font:500 26px/1.35 Manrope;color:#DCE3EE"> dentro do conjunto de recursos que a formulação representa.</span>', "",
             "line-height:1.2")
    # objetivos marcados
    h += div(110, 520, 700, None, "Objetivos específicos", "", "font:700 28px Gelasio,serif;color:#14213D")
    for k, (o, ev) in enumerate(OBJ):
        y = 570 + k * 86
        s += f'<circle cx="132" cy="{y+22}" r="20" fill="{TEAL}"/><g transform="translate({112} {y+2})">{CHECK}</g>'
        h += div(168, y, 640, None, f'<div style="font:700 24px/1.25 Manrope;color:#14213D">{o}</div>'
                 f'<div style="font:500 24px/1.3 Manrope;color:#1F7A6D">{ev}</div>', "")
    # os dois estudos
    a, b = estudo(850, 166, 960, 360, REDE, [("sun", SOLAR), ("bat", BAT), ("grid", REDE)], "Na microrrede industrial, observamos que",
                  ["A bateria começou a carregar <b>antes de a ponta entrar no horizonte do MPC</b>: o valor futuro indicou que guardar valia a pena.",
                   "A economia de <b>32,1&nbsp;%</b> foi a soma dos efeitos da solar e da bateria, sem sinergia adicional.",
                   "O plano da primeira decisão coincidiu com o custo realizado no fim do dia (<b>R$&nbsp;0,01</b> de diferença)."])
    s += a; h += b
    a, b = estudo(850, 546, 960, 362, PEM, [("sun", SOLAR), ("bat", BAT), ("h2", PEM)], "Na embarcação, observamos que",
                  ["A demanda foi atendida em todos os intervalos, sem conexão com a rede.",
                   "Com a bateria carregada, a PEMFC ficou na base (10–20&nbsp;kW) e a bateria absorveu as variações, cumprindo a reserva final.",
                   "Com pouca bateria, a PEMFC supriu <b>88&nbsp;%</b> da energia e o consumo de H₂ quase dobrou (<b>1,93&nbsp;×</b>)."])
    s += a; h += b
    body = (f'<div class="tt">{TIT}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(36))
    open(os.path.join(D, "S36_conclusoes.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide()
