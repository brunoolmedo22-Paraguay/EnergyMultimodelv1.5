"""Slide 29 (deck) — Demonstração do SEEDS: só o link do aplicativo, o QR code e o logo (pedido do responsável).
QR gerado localmente (segno, correção M, versão 3) em `slides/assets/qr_app.png`; conferido por decodificação (zxing-cpp):
https://energymultimodelv15.streamlit.app/ . Zona de silêncio ≥ 4 módulos garantida pelo cartão branco."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, HEAD, NAVY, LIGHT, LINE, div
from gerar_slide8 import rodape
from gerar_slide24_25 import DEFS

D = os.path.dirname(os.path.abspath(__file__))
URL = "energymultimodelv15.streamlit.app"
LOGO = "../capa/assets/seeds.png"          # 994 × 309
QR = "assets/qr_app.png"                    # 29 módulos


def img(src, x, y, w, h=None, st=""):
    hh = f"height:{h}px;" if h else ""
    return f'<img src="{src}" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;{hh}{st}">'


def qr(x, y, lado, sombra=True):
    """QR num cartão branco; margem de 4 módulos (zona de silêncio)."""
    m = lado / 29 * 4
    s = (f'<rect x="{x}" y="{y}" width="{lado+2*m}" height="{lado+2*m}" rx="28" fill="#fff" stroke="{LINE}" stroke-width="2"'
         + (' filter="url(#sh)"' if sombra else "") + "/>")
    return s, img(QR, x + m, y + m, lado, lado, "image-rendering:pixelated")


def salvar(nome, tit, s, h):
    body = ((f'<div class="tt">{tit}</div>' if tit else "")
            + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>'
            + h + rodape(29))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


LINK = f'<span style="font:700 40px Manrope;color:#1F7A6D;letter-spacing:.2px">{URL}</span>'


# ===================================================================== A · centrado: logo, QR, link
def a():
    s, h = "", ""
    h += img(LOGO, 960 - 300, 120, 600)
    a_, b_ = qr(960 - 245, 340, 380)
    s += a_; h += b_
    h += div(110, 856, 1700, None, LINK, "", "text-align:center")
    salvar("S29_A_centro", "", s, h)


# ===================================================================== B · duas metades: logo e link à esquerda, QR à direita
def b():
    s, h = "", ""
    h += img(LOGO, 110, 300, 820)
    s += f'<line x1="110" x2="930" y1="610" y2="610" stroke="{LINE}" stroke-width="2"/>'
    h += div(110, 640, 900, None, "Acesse o aplicativo", "", "font:600 26px Manrope;color:#4A5568")
    h += div(110, 684, 900, None, LINK, "")
    a_, b_ = qr(1180, 220, 540)
    s += a_; h += b_
    salvar("S29_B_metades", "Demonstração do SEEDS", s, h)


# ===================================================================== C · faixa clara: QR grande no centro do cartão, logo e link ao lado
def c():
    s, h = "", ""
    s += f'<rect x="110" y="180" width="1700" height="720" rx="32" fill="{LIGHT}"/>'
    a_, b_ = qr(220, 250, 500, sombra=False)
    s += a_; h += b_
    h += img(LOGO, 960, 360, 760)
    h += div(960, 640, 820, None, LINK, "")
    salvar("S29_C_faixa", "Demonstração do SEEDS", s, h)


if __name__ == "__main__":
    a()
    b()
    c()
