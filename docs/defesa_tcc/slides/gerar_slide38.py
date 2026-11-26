"""Slide 38 (deck) — Agradecimentos. Pedido do responsável: sem nomes da banca; QR do aplicativo (o mesmo do slide 29); UNILA.
CNPq: texto do artigo («apoio financeiro ao projeto n.º 460014/2025-0»); sem logotipo (não há arquivo oficial no repositório)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, LIGHT, div
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
TEAL = "#1F7A6D"


def slide():
    s, h = "", ""
    h += div(110, 150, 1000, None, "Obrigado!", "", "font:700 120px/1.05 Gelasio,serif;color:#14213D")
    itens = [("À banca", "pela leitura e pelas contribuições."),
             ("Ao CNPq", "pelo apoio financeiro ao projeto n.º 460014/2025-0."),
             ("À UNILA", "e ao curso de Engenharia de Energia do ILATIT.")]
    for k, (t, d) in enumerate(itens):
        y = 360 + k * 112
        s += f'<rect x="110" y="{y}" width="8" height="80" rx="4" fill="{TEAL}"/>'
        h += div(142, y + 2, 880, None, f'<div style="font:700 32px Gelasio,serif;color:#14213D">{t}</div>'
                 f'<div style="font:500 26px/1.35 Manrope;color:#4A5568;margin-top:4px">{d}</div>', "")
    h += '<img src="../capa/assets/unila.png" style="position:absolute;left:110px;top:720px;height:150px">'
    # cartão do aplicativo (mesmo QR do slide 29)
    s += f'<rect x="1150" y="170" width="660" height="738" rx="30" fill="{LIGHT}"/>'
    h += '<img src="../capa/assets/seeds.png" style="position:absolute;left:1260px;top:204px;width:440px">'
    lado, m = 340, 340 / 29 * 4
    s += f'<rect x="{1480-lado/2-m}" y="{366}" width="{lado+2*m}" height="{lado+2*m}" rx="24" fill="#fff"/>'
    h += f'<img src="assets/qr_app.png" style="position:absolute;left:{1480-lado/2}px;top:{366+m}px;width:{lado}px;height:{lado}px;image-rendering:pixelated">'
    h += div(1150, 830, 660, None, "energymultimodelv15.streamlit.app", "", f"font:700 30px Manrope;color:{TEAL};text-align:center")
    body = (f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{s}</svg>' + h + rodape(38))
    open(os.path.join(D, "S38_agradecimentos.html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


if __name__ == "__main__":
    slide()
