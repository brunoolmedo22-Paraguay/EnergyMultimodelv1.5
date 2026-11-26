"""Slide 38 (deck) — Agradecimentos, fundo escuro (pedido do responsável: fundo diferenciado, que chame a atenção, letras maiores).
Fundo navy com o gradiente SEEDS na borda inferior, textos em branco, destaques em lima. Sem nomes da banca; CNPq com o texto do
artigo («apoio financeiro ao projeto n.º 460014/2025-0»); UNILA só no rodapé (logo branco); QR do aplicativo (o mesmo do slide 29)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, div
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
LIMA, NAVY2 = "#C1FF72", "#0E1830"
CSS38 = """
.slide{background:radial-gradient(120% 120% at 85% 10%, #22345E 0%, #14213D 45%, #0E1830 100%) !important}
.ft span{color:#AEB9CC !important}.ft b{color:#fff !important}.ft .sep{background:#3B4B6E !important}
.hl{background:#2B3B5E !important}.pn{color:#fff !important}
"""


def slide():
    s, h = "", ""
    # faixa com o gradiente SEEDS e brilhos discretos
    s += ('<defs><linearGradient id="g38" x1="0" x2="1"><stop offset="0" stop-color="#6DB527"/><stop offset=".55" stop-color="#1E8A72"/>'
          '<stop offset="1" stop-color="#0072BA"/></linearGradient><radialGradient id="bl" cx=".5" cy=".5" r=".5">'
          '<stop offset="0" stop-color="#1E8A72" stop-opacity=".35"/><stop offset="1" stop-color="#1E8A72" stop-opacity="0"/></radialGradient></defs>')
    s += '<circle cx="1480" cy="540" r="520" fill="url(#bl)"/>'
    s += '<rect x="110" y="300" width="160" height="8" rx="4" fill="url(#g38)"/>'
    h += div(110, 110, 1000, None, "Obrigado!", "", "font:700 150px/1.05 Gelasio,serif;color:#fff")
    itens = [("À banca", "pela leitura e pelas contribuições."),
             ("Ao CNPq", "pelo apoio financeiro ao projeto n.º&nbsp;460014/2025-0."),
             ("À UNILA", "e ao curso de Engenharia de Energia do ILATIT.")]
    for k, (t, d) in enumerate(itens):
        y = 352 + k * 140
        s += f'<rect x="110" y="{y+6}" width="8" height="100" rx="4" fill="{LIMA}"/>'
        h += div(148, y, 900, None, f'<div style="font:700 42px Gelasio,serif;color:#fff">{t}</div>'
                 f'<div style="font:500 32px/1.35 Manrope;color:#C9D4E6;margin-top:4px">{d}</div>', "")
    # cartão do aplicativo (mesmo QR do slide 29)
    lado = 380
    m = lado / 29 * 4
    xc = 1480
    s += f'<rect x="1150" y="150" width="660" height="760" rx="34" fill="#fff" fill-opacity=".06" stroke="#3B4B6E" stroke-width="2"/>'
    h += div(1150, 186, 660, None, "Acesse o SEEDS", "", f"font:700 40px Gelasio,serif;color:#fff;text-align:center")
    s += f'<rect x="{xc-lado/2-m}" y="262" width="{lado+2*m}" height="{lado+2*m}" rx="28" fill="#fff"/>'
    h += f'<img src="assets/qr_app.png" style="position:absolute;left:{xc-lado/2}px;top:{262+m}px;width:{lado}px;height:{lado}px;image-rendering:pixelated">'
    h += div(1150, 772, 660, None, "energymultimodelv15<br>.streamlit.app", "", f"font:700 34px/1.25 Manrope;color:{LIMA};text-align:center")
    rod = rodape(38).replace("../capa/assets/unila.png", "../capa/assets/unila_branco.png")
    body = (f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>' + h + rod)
    open(os.path.join(D, "S38_agradecimentos.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM + CSS38, body=body))


if __name__ == "__main__":
    slide()
