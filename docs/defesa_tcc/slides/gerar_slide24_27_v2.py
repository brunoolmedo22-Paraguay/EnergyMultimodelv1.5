"""Slides 24–27, segunda rodada (o responsável escolheu E2 para as entradas e K1 para a configuração; «pode ser melhor ainda»).

Entradas (E2 refinado):
  E2b — fichas com o NÚMERO-CHAVE de cada entrada em destaque (energia, máximo, faixa, razão), procedência na mesma linha do nome.
  E2c — as mesmas informações num painel único à direita, em linhas separadas por filetes (lê como a legenda do gráfico).
Configuração (K1 refinado):
  K1b — cartões das configurações com o MESMO desenho nos dois casos (composição + bateria com o estado inicial); malha; ficha em três
        painéis claros.
  K1c — sem repetição: a malha (duração, intervalos, N, m, H_L) fica num cartão próprio e a ficha embaixo passa a duas colunas,
        Recursos e Gerenciamento (demanda crítica e realização igual à previsão entram no gerenciamento).
Dados e procedência: os mesmos de `gerar_slide24_27.py` (Tabelas 6.1–6.3; séries do cenário das rodadas de referência)."""
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_slide16 import NAVY, LIGHT, LINE, T, div, ic
from gerar_slide24_25 import bateria, COR, NOME, ficha_html
from gerar_slide24_27 import CASOS, entradas, malha, salvar, GHI, TEMP, PONTA

# ------------------------------------------------------------------ conteúdo adicional
DESTAQUE = {
    "ct": [("Demanda", "ANEEL [37]", NAVY, "1.967 kWh", "no dia · pico de 100 kW, mínimo de 58,24 kW"),
           ("Irradiância", "Sintética", GHI, "970 W/m²", "máxima · 7,125 kWh/m² no dia"),
           ("Temperatura", "Sintética", TEMP, "15,0 a 26,7 °C", "ambiente ao longo do dia"),
           ("Tarifa", "ANEEL, COPEL [38, 39]", PONTA, "4,4 ×", "1,94 na ponta × 0,44 R$/kWh fora dela")],
    "emb": [("Demanda", "Registro do projeto", NAVY, "68,21 kWh", "na missão · de 7,16 a 58,77 kW"),
            ("Irradiância", "Sintética", GHI, "931 a 970 W/m²", "meio-dia, série de 5 min"),
            ("Temperatura", "Sintética", TEMP, "23,4 a 24,5 °C", "ambiente durante a missão"),
            ("Hidrogênio", "Sintético", PONTA, "10 R$/kg", "preço sem cotação de mercado")],
}
# configuração: (nome, recursos, bateria inicial [fração, kWh] ou None, reserva final [fração, texto] ou None)
CFG = {
    "ct": [("C1", ["grid"], None, None), ("C2", ["grid", "sun"], None, None),
           ("C3", ["grid", "bat"], (.30, 60), None), ("C4", ["grid", "sun", "bat"], (.30, 60), None)],
    "emb": [("C5", ["sun", "bat", "h2"], (.50, 75), (.30, "Termina com ≥ 45 kWh")),
            ("C6", ["sun", "bat", "h2"], (.12, 18), (None, "Sem reserva final"))],
}
NOTA = {"ct": "Mesma demanda, tarifa, clima e estratégia em C1–C4; muda só a composição.",
        "emb": "Mesma composição e missão; mudam o estado inicial da bateria e a reserva final. PEMFC ligada a 30&nbsp;kW no início."}
GER = {
    "ct": [("Objetivo", "Custo de importação"), ("Condição final", "Nenhuma declarada"), ("Valor futuro", "PWL, 5 a 17 pontos, a cada janela"),
           ("Demanda", "Crítica: atendida sempre"), ("Realização", "Igual à previsão (ensaio)"), ("Aceitação", "Ótimo, sem gap, até 60 s")],
    "emb": [("Objetivo", "Consumo de hidrogênio"), ("Condição final", "C5: ≥ 45 kWh · C6: nenhuma"), ("Valor futuro", "PWL, 5 a 50 pontos, a cada janela"),
            ("Operação", "Isolada, demanda crítica"), ("Realização", "Igual à previsão (ensaio)"), ("Aceitação", "Ótimo, sem gap, até 60 s")],
}
RODAPE_CFG = {"ct": "Demanda <b>crítica</b> · realização <b>igual à previsão</b> (ensaio) · cada janela resolvida até o <b>ótimo, sem gap</b>, em até 60 s",
              "emb": "Operação <b>isolada</b> · demanda <b>crítica</b> · realização <b>igual à previsão</b> (ensaio) · cada janela até o <b>ótimo, sem gap</b>, em até 60 s"}
NB = lambda v: re.sub(r"(\d|≥|≈|C\d:) ", lambda m: m.group(1) + "&nbsp;", v)


def traco(cor):
    d = "stroke-dasharray:10 6;" if cor == TEMP else ""
    return d


# ===================================================================== Entradas · E2b: fichas com número-chave
def fichas_destaque(k, x, y, w, h, gap=16):
    s, ht = "", ""
    itens = DESTAQUE[k]
    ch = (h - gap * (len(itens) - 1)) / len(itens)
    for i, (nome, prov, cor, num, sub) in enumerate(itens):
        cy = y + i * (ch + gap)
        s += f'<rect x="{x}" y="{cy}" width="{w}" height="{ch}" rx="20" fill="{LIGHT}"/>'
        s += f'<line x1="{x+24}" x2="{x+60}" y1="{cy+37}" y2="{cy+37}" stroke="{cor}" stroke-width="5" stroke-linecap="round" style="{traco(cor)}"/>'
        ht += div(x + 72, cy + 20, 260, None, nome, "", "font:700 25px Gelasio,serif;color:#14213D")
        ht += div(x + w - 344, cy + 22, 320, None, prov, "p", "font-size:22px;color:#1F7A6D;font-weight:700;text-align:right")
        ht += div(x + 24, cy + 62, w - 48, None, NB(num), "", f"font:700 40px/1.1 Gelasio,serif;color:#14213D")
        ht += div(x + 24, cy + 112, w - 48, None, NB(sub), "p", "font-size:22px")
    return s, ht


def e2b(k):
    c = CASOS[k]
    s, h = "", ""
    h += div(110, 160, 1200, None, c["nota"], "p", "font-size:24px;color:#4A5568")
    s += f'<rect x="110" y="212" width="1180" height="700" rx="26" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
    a, b = entradas(c, 130, 260, 1140, 620)
    s += a; h += b
    a, b = fichas_destaque(k, 1320, 166, 490, 746)
    s += a; h += b
    salvar(c, f"S{c['n'][0]}_E2b_entradas", c["tit_e"], c["n"][0], c["ref_e"], s, h)


# ===================================================================== Entradas · E2c: painel único, linhas com filete
def e2c(k):
    c = CASOS[k]
    s, h = "", ""
    h += div(110, 160, 1200, None, c["nota"], "p", "font-size:24px;color:#4A5568")
    s += f'<rect x="110" y="212" width="1700" height="700" rx="26" fill="#fff" stroke="{LINE}" stroke-width="2" filter="url(#sh)"/>'
    a, b = entradas(c, 130, 260, 1150, 620)
    s += a; h += b
    x, w, y0, rh = 1330, 450, 236, 168
    for i, (nome, prov, cor, num, sub) in enumerate(DESTAQUE[k]):
        y = y0 + i * rh
        if i:
            s += f'<line x1="{x}" x2="{x+w}" y1="{y}" y2="{y}" stroke="#E3E9E8" stroke-width="2"/>'
        s += f'<line x1="{x}" x2="{x+36}" y1="{y+34}" y2="{y+34}" stroke="{cor}" stroke-width="5" stroke-linecap="round" style="{traco(cor)}"/>'
        h += div(x + 48, y + 17, 220, None, nome, "", "font:700 25px Gelasio,serif;color:#14213D")
        h += div(x + w - 220, y + 19, 220, None, prov, "p", "font-size:22px;color:#1F7A6D;font-weight:700;text-align:right")
        h += div(x, y + 56, w, None, NB(num), "", "font:700 38px/1.1 Gelasio,serif;color:#14213D")
        h += div(x, y + 104, w, None, NB(sub), "p", "font-size:22px")
    s += f'<line x1="{x-28}" x2="{x-28}" y1="240" y2="884" stroke="#E3E9E8" stroke-width="2"/>'
    salvar(c, f"S{c['n'][0]}_E2c_entradas", c["tit_e"], c["n"][0], c["ref_e"], s, h)


# ------------------------------------------------------------------ cartões das configurações com o mesmo desenho nos dois casos
def cartao(item, x, y, w, h):
    nome, recs, ini, res = item
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#fff" stroke="{LINE}" stroke-width="2"/>'
    s += T(x + 22, y + 46, nome, 32, 700, NAVY, "Gelasio")
    r = 18
    for j, rk in enumerate(recs):
        px = x + w - 30 - (len(recs) - 1 - j) * 44
        s += f'<circle cx="{px}" cy="{y+34}" r="{r}" fill="#fff" stroke="{COR[rk]}" stroke-width="2.5"/>' + ic(rk, px - r * .62, y + 34 - r * .62, r * 1.24, COR[rk])
    ht = div(x + 22, y + 66, w - 44, None, " + ".join(NOME[k] for k in recs), "p", "font-size:22px;font-weight:700;color:#14213D")
    if ini:
        f, e = ini
        s += bateria(x + 26, y + 102, 32, h - 116, f, res[0] if res else None)
        txt = f"Bateria inicia em {round(f*100)}&nbsp;% ({e}&nbsp;kWh)" + (f"<br>{NB(res[1])}" if res else "")
        ht += div(x + 74, y + 106, w - 92, h - 116, f"<span>{txt}</span>", "p", "font-size:22px;line-height:1.4;display:flex;align-items:center")
    else:
        ht += div(x + 22, y + 108, w - 44, None, "Sem armazenamento", "p", "font-size:22px;color:#7B8794")
    return s, ht


def cartoes_cfg(k, x, y, w, h, gap=18):
    itens = CFG[k]
    cw = (w - gap * (len(itens) - 1)) / len(itens)
    s, ht = "", ""
    for i, it in enumerate(itens):
        a, b = cartao(it, x + i * (cw + gap), y, cw, h)
        s += a; ht += b
    return s, ht


# ===================================================================== Configuração · K1b: cartões unificados, malha, ficha em painéis
def k1b(k):
    c = CASOS[k]
    s, h = "", ""
    a, b = cartoes_cfg(k, 110, 168, 1700, 170)
    s += a; h += b
    h += div(110, 350, 1700, None, NOTA[k], "p", "font-size:22px")
    a, b = malha(c, 150, 470, 1620, legenda="cima", k=24 if k == "ct" else 2)
    s += a; h += b
    for g, cx in zip(c["grupos"], (110, 690, 1270)):
        s += f'<rect x="{cx}" y="650" width="540" height="264" rx="20" fill="{LIGHT}"/>'
        h += div(cx + 22, 662, 496, None, ficha_html(c, [g], 496).replace("font:700 26px Gelasio", "font:700 24px Gelasio"))
    salvar(c, f"S{c['n'][1]}_K1b_config", c["tit_c"], c["n"][1], c["ref_c"], s, h)


# ===================================================================== Configuração · K1c: malha em cartão + ficha em duas colunas, sem repetição
def linhas(rot_val, w, lab=196):
    o = ""
    for i, (l, v, *p) in enumerate(rot_val):
        prov = p[0] if p else ""
        o += (f'<div style="border-top:1.5px solid #DCE3E2;padding:7px 0;display:flex;align-items:baseline;gap:14px">'
              f'<span style="font:600 22px/1.25 Manrope;color:#7B8794;flex:0 0 {lab}px">{l}</span>'
              f'<span style="font:700 24px/1.3 Gelasio,serif;color:#14213D;flex:1">{NB(v)}</span>'
              + (f'<span style="font:700 22px/1.25 Manrope;color:#1F7A6D">{prov}</span>' if prov else "") + '</div>')
    return o


def k1c(k):
    c = CASOS[k]
    s, h = "", ""
    a, b = cartoes_cfg(k, 110, 168, 1700, 170)
    s += a; h += b
    h += div(110, 350, 1700, None, NOTA[k], "p", "font-size:22px")
    a, b = malha(c, 150, 470, 1620, legenda="cima", k=24 if k == "ct" else 2)
    s += a; h += b
    rec = [(l, v, p) for l, v, p in c["grupos"][0][1]]
    h += div(110, 652, 820, None, '<div style="font:700 26px Gelasio,serif;color:#14213D;margin-bottom:6px">Recursos</div>' + linhas(rec, 820, 170))
    h += div(990, 652, 820, None, '<div style="font:700 26px Gelasio,serif;color:#14213D;margin-bottom:6px">Gerenciamento</div>' + linhas(GER[k][:3], 820, 180))
    h += div(110, 862, 1700, None, RODAPE_CFG[k], "p", "font-size:22px")
    salvar(c, f"S{c['n'][1]}_K1c_config", c["tit_c"], c["n"][1], c["ref_c"], s, h)


if __name__ == "__main__":
    for kk in ("ct", "emb"):
        e2b(kk)
        e2c(kk)
        k1b(kk)
        k1c(kk)
