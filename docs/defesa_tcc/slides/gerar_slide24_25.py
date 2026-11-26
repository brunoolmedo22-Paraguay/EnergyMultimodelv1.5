"""Slides 24 e 25 (deck) — os dois estudos de caso, com O MESMO desenho (pedido do responsável): o fundamental das Tabelas 6.1–6.3,
com a procedência de cada dado à vista, para transmitir segurança no que foi feito.

Dados: Tabelas 6.1, 6.2 e 6.3 e Seções 6.2–6.3 do artigo. Os perfis desenhados são as séries GRAVADAS nas rodadas de referência
dos exemplos persistentes do SEEDS (`seeds2/exemplos`, C4 e C5), extraídas para `dados/*.json` (demanda realizada = prevista,
potencial FV previsto por arranjo, tarifa de decisão). Conferência: CT-046 = 1.967,15 kWh/dia, 100 / 58,24 kW, 270,01 kWh na ponta;
EMB-H2-120 = 68,21 kWh, 7,16–58,77 kW, média 34,10 kW — iguais às tabelas.

Três propostas, cada uma desenhada igual nos dois slides:
  A  perfil + configurações à esquerda, ficha à direita
  B  perfil em largura total, ficha em três colunas embaixo
  C  ilustração do slide 23 + configurações à esquerda, perfil e ficha à direita"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import CSSM, DEF2, HEAD, NAVY, SLATE, LIGHT, LINE, BAT, PEM, T, div, ic, SOLAR, REDE
from gerar_slide8 import rodape

D = os.path.dirname(os.path.abspath(__file__))
MUTED = "#7B8794"
PONTA = "#E0524F"
DEFS = DEF2.replace("</defs>",
    '<filter id="sh" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#14213D" flood-opacity=".08"/></filter>'
    f'<linearGradient id="gd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{NAVY}" stop-opacity=".16"/><stop offset="1" stop-color="{NAVY}" stop-opacity=".03"/></linearGradient>'
    f'<linearGradient id="gs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{SOLAR}" stop-opacity=".55"/><stop offset="1" stop-color="{SOLAR}" stop-opacity=".18"/></linearGradient></defs>')


def carregar(nome):
    return json.load(open(os.path.join(D, "dados", nome), encoding="utf-8"))


CT = carregar("ct046_c4.json")
EMB = carregar("emb_c5.json")

# ------------------------------------------------------------------ conteúdo (Tabelas 6.1–6.3; procedência na 3.ª coluna)
CASOS = {
    "ct": dict(
        n=24, titulo="Microrrede industrial CT-046", img="assets/ilus_microrrede.png",
        lema="Conectada à rede · 24 h · minimiza o custo da energia importada",
        serie=CT, ymax=110, yt=(0, 50, 100), xt=[(0, "0 h"), (24, "6 h"), (48, "12 h"), (72, "18 h"), (96, "24 h")],
        faixa=(72, 84, "Ponta 18–21 h"), pico=None,
        sinal=("Tarifa de importação", [(0, 72, "0,44 R$/kWh fora de ponta"), (72, 84, "1,94"), (84, 96, "")]),
        configs=[("C1", ["grid"], None), ("C2", ["grid", "sun"], None), ("C3", ["grid", "bat"], None), ("C4", ["grid", "sun", "bat"], None)],
        nota_cfg="Mesma demanda, tarifa, clima e estratégia; muda só a composição. Bateria inicia em 30 % (60 kWh).",
        grupos=[
            ("Recursos", [
                ("Fotovoltaica", "58 kWp · 100 × CS7L-580MS", "Fabricante [40]"),
                ("Bateria", "200 kWh · 50 kW · SOC 10–90 %", "Declarado"),
                ("Rede (PCC)", "Só importação, até 200 kW", "Declarado")]),
            ("Dados de entrada", [
                ("Demanda", "Curva CT-046, pico de 100 kW", "ANEEL [37]"),
                ("Tarifa", "A4 Verde, ponta 4,4 vezes mais cara", "ANEEL, COPEL [38, 39]"),
                ("Clima", "Dia de sol, GHI máx. 970 W/m²", "Sintético")]),
            ("Gerenciamento", [
                ("Janela do MPC", "N = 8 (2 h), m = 1", ""),
                ("Horizonte longo", "H<sub>L</sub> = 96 (24 h)", ""),
                ("Valor futuro", "Recalculado a cada janela", ""),
                ("Condição final", "Nenhuma declarada", "")])],
        ref="Tabelas 6.1 e 6.2 do artigo · série gravada na rodada de referência C4 · ANEEL [37, 38], COPEL [39], Canadian Solar [40]",
        rodape_txt="Sistema hipotético em Foz do Iguaçu (PR), 2/10/2026, 96 × 15 min · demanda crítica · realização igual à previsão"),
    "emb": dict(
        n=25, titulo="Embarcação híbrida EMB-H2-120", img="assets/ilus_embarcacao.png",
        lema="Isolada · 120 min · minimiza o consumo de hidrogênio",
        serie=EMB, ymax=70, yt=(0, 30, 60), xt=[(0, "12:00"), (2, "12:30"), (4, "13:00"), (6, "13:30"), (8, "14:00")],
        faixa=None, pico=(63.06, "Pico do perfil original: 63,06 kW"),
        sinal=("Preço do H₂", [(0, 8, "10 R$/kg (sintético)")]),
        configs=[("C5", ["sun", "bat", "h2"], (.50, .30)), ("C6", ["sun", "bat", "h2"], (.12, None))],
        nota_cfg="Mesma composição e missão; mudam o estado inicial da bateria e a reserva exigida ao final.",
        grupos=[
            ("Recursos", [
                ("Fotovoltaica", "3,48 kWp · 6 × CS7L-580MS", "Fabricante [40]"),
                ("Bateria", "150 kWh · 75 kW · SOC 10–90 %", "Declarado"),
                ("PEMFC", "≈ 50 kW, mín. 10 kW, sempre ligada", "Aprox. [41]")]),
            ("Dados de entrada", [
                ("Demanda", "Propulsão, 68,21 kWh na missão", "Registro do projeto"),
                ("Hidrogênio", "10 R$/kg", "Sintético"),
                ("Clima", "Mesmo dia da CT-046", "Sintético")]),
            ("Gerenciamento", [
                ("Janela do MPC", "N = 4 (1 h), m = 1", ""),
                ("Horizonte longo", "H<sub>L</sub> = 8 (120 min)", ""),
                ("Valor futuro", "Recalculado a cada janela", ""),
                ("Condição final", "C5: ≥ 45 kWh · C6: nenhuma", "")])],
        ref="Tabelas 6.2 e 6.3 do artigo · série gravada na rodada de referência C5 · Canadian Solar [40], Horizon VLIIPro50-22 [41] (parametrização aproximada, não calibração)",
        rodape_txt="Sistema hipotético, 2/10/2026, 12:00–14:00, 8 × 15 min · demanda crítica · realização igual à previsão"),
}


# ------------------------------------------------------------------ peças
def perfil(c, x, y, w, h):
    """Perfil gravado (degraus de 15 min): demanda (navy) e potencial FV (solar); faixa da ponta; faixa do sinal econômico embaixo."""
    sr = c["serie"]
    d, pv = sr["demanda_kW"], sr["fv_disponivel_kW"]
    n = len(d)
    hs = 40                                   # faixa do sinal econômico
    hp = h - hs - 92                          # área do gráfico
    X = lambda i: x + 64 + (w - 84) * i / n
    Y = lambda v: y + hp - hp * v / c["ymax"]
    o = ""
    if c["faixa"]:
        a, b, lab = c["faixa"]
        o += f'<rect x="{X(a)}" y="{y}" width="{X(b)-X(a)}" height="{hp}" fill="{PONTA}" opacity=".10"/>'
        o += T((X(a) + X(b)) / 2, y - 12, lab, 22, 700, PONTA, anchor="middle")
    for v in c["yt"]:
        o += f'<line x1="{X(0)}" x2="{X(n)}" y1="{Y(v)}" y2="{Y(v)}" stroke="#E3E9E8" stroke-width="1.5"/>'
        o += T(X(0) - 14, Y(v) + 8, f"{v}", 22, 600, MUTED, anchor="end")
    o += T(X(0) - 14, Y(c["ymax"]) - 14, "kW", 22, 700, MUTED, anchor="end")

    def degraus(vs):
        pts = []
        for i, v in enumerate(vs):
            pts += [(X(i), Y(v)), (X(i + 1), Y(v))]
        return pts
    for vs, fill, cor, sw in ((pv, "url(#gs)", SOLAR, 2.5), (d, "url(#gd)", NAVY, 3.5)):
        p = degraus(vs)
        linha = "M" + " L".join(f"{a:.1f} {b:.1f}" for a, b in p)
        o += f'<path d="{linha} L{X(n):.1f} {Y(0):.1f} L{X(0):.1f} {Y(0):.1f} Z" fill="{fill}"/>'
        o += f'<path d="{linha}" fill="none" stroke="{cor}" stroke-width="{sw}" stroke-linejoin="round"/>'
    if c["pico"]:
        v, lab = c["pico"]
        o += f'<line x1="{X(0)}" x2="{X(n)}" y1="{Y(v)}" y2="{Y(v)}" stroke="{NAVY}" stroke-width="2" stroke-dasharray="7 6"/>'
        o += T(X(n), Y(v) - 10, lab, 22, 600, SLATE, anchor="end")
    o += f'<line x1="{X(0)}" x2="{X(n)}" y1="{Y(0)}" y2="{Y(0)}" stroke="{NAVY}" stroke-width="2"/>'
    for i, lab in c["xt"]:
        o += f'<line x1="{X(i)}" x2="{X(i)}" y1="{Y(0)}" y2="{Y(0)+7}" stroke="{NAVY}" stroke-width="2"/>'
        o += T(X(i), Y(0) + 32, lab, 22, 600, MUTED, anchor="middle")
    # faixa do sinal econômico (tarifa por posto / preço do H₂)
    ys = Y(0) + 52 + 34
    nome, blocos = c["sinal"]
    for a, b, lab in blocos:
        alto = bool(c["faixa"]) and a == c["faixa"][0]
        o += f'<rect x="{X(a)+1}" y="{ys}" width="{X(b)-X(a)-2}" height="{hs}" rx="6" fill="{PONTA if alto else "#D5DDE5"}"/>'
        if alto:
            o += T((X(a) + X(b)) / 2, ys + hs / 2 + 8, lab, 22, 800, "#fff", anchor="middle")
    o += T(X(0), ys - 12, f"{nome}: " + blocos[0][2], 22, 600, SLATE)
    return o, (X, Y, n)


def rotulos_html(c, geo):
    X, Y, n = geo
    d, pv = c["serie"]["demanda_kW"], c["serie"]["fv_disponivel_kW"]
    sol = "Solar disponível" + ("" if c["n"] == 24 else " (máx. " + f"{max(pv):.1f}".replace(".", ",") + " kW)")
    sw = lambda cor: f'<span style="display:inline-block;width:30px;height:4px;border-radius:2px;background:{cor};vertical-align:middle;margin:0 10px 3px 0"></span>'
    return div(X(0) + 30, Y(c["ymax"]) - 46, 620, None,
               f'{sw(NAVY)}<b>Demanda</b><span style="display:inline-block;width:34px"></span>{sw(SOLAR)}<span style="color:#A57A0E;font-weight:800">{sol}</span>',
               "p", "font-size:22px;white-space:nowrap")


def bateria(x, y, w, h, nivel, reserva=None):
    o = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="#fff" stroke="{BAT}" stroke-width="3"/>'
         f'<rect x="{x+w/2-11}" y="{y-7}" width="22" height="7" rx="2" fill="{BAT}"/>')
    lv = (h - 10) * nivel
    o += f'<rect x="{x+5}" y="{y+h-5-lv}" width="{w-10}" height="{lv}" rx="5" fill="{BAT}"/>'
    if reserva is not None:
        yr = y + h - 5 - (h - 10) * reserva
        o += f'<line x1="{x-10}" x2="{x+w+10}" y1="{yr}" y2="{yr}" stroke="{NAVY}" stroke-width="2.5" stroke-dasharray="6 5"/>'
    return o


COR = {"sun": SOLAR, "bat": BAT, "h2": PEM, "grid": REDE}
NOME = {"sun": "Solar", "bat": "Bateria", "h2": "PEMFC", "grid": "Rede"}


def cfg_card(c, item, x, y, w, h):
    """Cartão de uma configuração: nome e recursos no topo; embaixo, a composição (CT-046) ou a condição da bateria (embarcação)."""
    nome, recs, bat = item
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
    s += T(x + 22, y + 46, nome, 32, 700, NAVY, "Gelasio")
    r = 18
    for j, rk in enumerate(recs):
        px = x + w - 30 - (len(recs) - 1 - j) * 44
        s += f'<circle cx="{px}" cy="{y+34}" r="{r}" fill="#fff" stroke="{COR[rk]}" stroke-width="2.5"/>' + ic(rk, px - r * .62, y + 34 - r * .62, r * 1.24, COR[rk])
    if bat is None:
        ht = div(x + 22, y + 66, w - 44, h - 78, " + ".join(NOME[k] for k in recs), "p", "font-size:22px;font-weight:700;color:#14213D")
    else:
        ini, res = bat
        s += bateria(x + 24, y + 72, 40, h - 92, ini, res)
        t1 = f"Inicia em {round(ini*100)} % ({round(150*ini)} kWh)"
        t2 = "Termina com ≥ 45 kWh" if res else "Sem reserva final"
        ht = div(x + 86, y + 62, w - 100, h - 70, f"<span><b>{t1}</b><br>{t2}</span>", "p", "font-size:22px;line-height:1.45;display:flex;align-items:center")
    return s, ht


def configs(c, x, y, w, h, colunas=None, gap=18, hh=None):
    cfg = c["configs"]
    k = colunas or len(cfg)
    linhas = -(-len(cfg) // k)
    cw = (w - gap * (k - 1)) / k
    ch = hh or (h - gap * (linhas - 1)) / linhas
    s, ht = "", ""
    for i, item in enumerate(cfg):
        a, b = cfg_card(c, item, x + (i % k) * (cw + gap), y + (i // k) * (ch + gap), cw, ch)
        s += a; ht += b
    return s, ht


def ficha_html(c, grupos, w):
    """Ficha técnica: rótulo e procedência na 1.ª linha, valor na 2.ª (texto ≥ 22 px); grupo sem procedência em linha única."""
    import re
    nb = lambda v: re.sub(r"(\d|≥|≈|C\d:) ", lambda m: m.group(1) + "&nbsp;", v)   # número e unidade na mesma linha
    o = ""
    for g, linhas in grupos:
        linhas = [(lab, re.sub(r"(SOC&nbsp;\d+–\d+&nbsp;%)", r'<span style="white-space:nowrap">\1</span>', nb(val)), prov) for lab, val, prov in linhas]
        o += f'<div style="font:700 26px Gelasio,serif;color:#14213D;margin:0 0 6px">{g}</div>'
        for lab, val, prov in linhas:
            if prov or w < 450:
                o += (f'<div style="border-top:1.5px solid #DCE3E2;padding:4px 0 5px">'
                      f'<div style="display:flex;justify-content:space-between;font:600 22px/1.25 Manrope;color:#7B8794"><span>{lab}</span>'
                      f'<span style="color:#1F7A6D;font-weight:700">{prov}</span></div>'
                      f'<div style="font:700 24px/1.3 Gelasio,serif;color:#14213D">{val}</div></div>')
            else:
                o += (f'<div style="border-top:1.5px solid #DCE3E2;padding:5px 0;display:flex;gap:14px;align-items:baseline">'
                      f'<span style="font:600 22px/1.25 Manrope;color:#7B8794;flex:0 0 {min(184, w*.4):.0f}px">{lab}</span>'
                      f'<span style="font:700 24px/1.3 Gelasio,serif;color:#14213D">{val}</span></div>')
        o += '<div style="height:10px"></div>'
    return o


def ficha(c, x, y, w, cols=None):
    if cols is None:
        return "", div(x, y, w, None, ficha_html(c, c["grupos"], w))
    return "", "".join(div(cx, y, cw, None, ficha_html(c, [g], cw)) for g, (cx, cw) in zip(c["grupos"], cols))


def salvar(c, nome, s, h):
    tit = f'<div class="tt">{c["titulo"]}</div>'
    body = (tit + f'<svg width="1920" height="1080" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0">{DEFS}{s}</svg>'
            + h + f'<div class="ref">{c["ref"]}</div>' + rodape(c["n"]))
    open(os.path.join(D, nome + ".html"), "w", encoding="utf-8").write(HEAD.format(css=CSSM, body=body))


# ===================================================================== A · perfil + configurações | ficha
def pA(chave):
    c = CASOS[chave]
    s, h = "", ""
    h += div(110, 166, 1040, None, c["lema"], "p", "font-size:24px;color:#4A5568")
    s += f'<rect x="110" y="222" width="1040" height="464" rx="26" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
    a, geo = perfil(c, 150, 276, 980, 400)
    s += a; h += rotulos_html(c, geo)
    a, b = configs(c, 110, 708, 1040, 150)
    s += a; h += b
    h += div(110, 872, 1040, None, c["nota_cfg"], "p", "font-size:22px")
    s += f'<rect x="1190" y="166" width="620" height="744" rx="26" fill="{LIGHT}"/>'
    a, b = ficha(c, 1222, 184, 560)
    s += a; h += b
    salvar(c, f"S{c['n']}_A_perfil_ficha", s, h)


# ===================================================================== B · perfil + configurações em cima | ficha em três colunas embaixo
def pB(chave):
    c = CASOS[chave]
    s, h = "", ""
    h += div(110, 166, 1100, None, c["lema"], "p", "font-size:24px;color:#4A5568")
    s += f'<rect x="110" y="220" width="1130" height="400" rx="26" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
    a, geo = perfil(c, 150, 268, 1070, 340)
    s += a; h += rotulos_html(c, geo)
    s += f'<rect x="1270" y="220" width="540" height="400" rx="26" fill="{LIGHT}"/>'
    a, b = configs(c, 1290, 240, 500, 360, colunas=2 if len(c["configs"]) == 4 else 1)
    s += a; h += b
    a, b = ficha(c, 0, 652, 0, cols=[(110, 540), (690, 540), (1270, 540)])
    s += a; h += b
    salvar(c, f"S{c['n']}_B_largo", s, h)


# ===================================================================== C · ilustração do slide 23 + configurações | perfil + ficha
def pC(chave):
    c = CASOS[chave]
    s, h = "", ""
    s += f'<rect x="110" y="166" width="560" height="744" rx="26" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
    h += f'<img src="{c["img"]}" style="position:absolute;left:126px;top:182px;width:528px;height:246px;object-fit:cover">'
    h += div(140, 440, 500, None, c["lema"], "", "font:700 24px/1.35 Gelasio,serif;color:#14213D;text-align:center")
    a, b = configs(c, 134, 530, 512, 356, colunas=2 if len(c["configs"]) == 4 else 1)
    s += a; h += b
    a, geo = perfil(c, 720, 196, 1090, 330)
    s += a; h += rotulos_html(c, geo)
    a, b = ficha(c, 0, 556, 0, cols=[(710, 350), (1085, 350), (1460, 350)])
    s += a; h += b
    salvar(c, f"S{c['n']}_C_ilustracao", s, h)


if __name__ == "__main__":
    for k in ("ct", "emb"):
        pA(k)
        pB(k)
        pC(k)
