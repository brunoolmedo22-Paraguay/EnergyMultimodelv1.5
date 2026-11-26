"""Slide 37 (deck) — Perspectivas, tom construtivo («a plataforma está pronta para avançar em…»). Cinco perspectivas do artigo
(Seção 7.4/8): térmica no EMS (custos de combustível e restrições operacionais); malha temporal e discretização automáticas; custo
futuro para múltiplos bancos; previsões × condições realizadas (robustez); comparação com dados experimentais. A linha «Hoje» descreve
o estado atual verificado no código (CLAUDE.md): térmica bloqueada no EMS V2 (M19/CVU não implementado); Δ, N e H_L declarados no
cenário; dois bancos por envoltória convexa verificada; realização igual à previsão (ensaio); modelos parametrizados, não calibrados."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, LIGHT, div, ic
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TIT = "Perspectivas"
REF = "Seções 7.4 e 8 do artigo"
TEAL = "#1F7A6D"
P = [("fire", "#C0532F", "Geração térmica no EMS", "Custos de combustível e restrições operacionais na formulação.",
      "Modelo físico na bancada, ainda fora do EMS."),
     ("clock", "#2C6FB0", "Malha temporal automática", "Definir o passo e os horizontes a partir dos dados e dos recursos.",
      "Passo, N e H<sub>L</sub> declarados no cenário."),
     ("bat", "#7B6CF6", "Custo futuro com vários bancos", "Aproximação mais fiel quando há mais de um armazenamento.",
      "Até dois bancos, por envoltória convexa."),
     ("cloud", "#4C8DD6", "Previsão × realidade", "Avaliar a robustez com erros de previsão de demanda e clima.",
      "Realização igual à previsão (ensaio)."),
     ("check", TEAL, "Dados experimentais", "Comparar com medições para validar a representatividade dos modelos.",
      "Modelos parametrizados, não calibrados.")]


def slide():
    s, h = "", ""
    h += div(110, 168, 1700, None, "A plataforma está pronta para avançar em:", "", "font:600 30px Manrope;color:#4A5568")
    w, g, y0, hc = (1700 - 4 * 22) / 5, 22, 240, 650
    for k, (icn, cor, t, d, hoje) in enumerate(P):
        x = 110 + k * (w + g)
        s += f'<rect x="{x}" y="{y0}" width="{w}" height="{hc}" rx="26" fill="{LIGHT}"/>'
        s += f'<circle cx="{x+62}" cy="{y0+70}" r="38" fill="#fff" stroke="{cor}" stroke-width="3"/>' + ic(icn, x + 62 - 24, y0 + 46, 48, cor)
        h += div(x + 28, y0 + 136, w - 56, None, t, "", "font:700 30px/1.2 Gelasio,serif;color:#14213D")
        h += div(x + 28, y0 + 254, w - 56, None, d, "p", "font-size:25px;line-height:1.4")
        s += f'<line x1="{x+28}" x2="{x+w-28}" y1="{y0+hc-178}" y2="{y0+hc-178}" stroke="#D5DDDC" stroke-width="2"/>'
        h += div(x + 28, y0 + hc - 160, w - 56, None, f'<div style="font:700 22px Manrope;color:{cor};margin-bottom:4px">Hoje</div>{hoje}',
                 "p", "font-size:23px;line-height:1.35")
    body = (f'<div class="tt">{TIT}</div><svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>'
            + h + f'<div class="ref">{REF}</div>' + rodape(37))
    open(os.path.join(D, "S37_perspectivas.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide()
