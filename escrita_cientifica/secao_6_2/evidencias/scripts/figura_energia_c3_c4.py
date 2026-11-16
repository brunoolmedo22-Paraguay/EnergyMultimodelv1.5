"""Figura derivada (Seção 6.2.2): energia armazenada nas fronteiras de C3 e C4 (rodadas 7252f033 e 14d8e5b3).

Dados: evidencias/dados/C3_fronteiras.csv e C4_fronteiras.csv, reconstruídos dos SVG vetoriais
02_bateria_eq-e21ff4bbc46d.svg dos ZIP de figuras das rodadas (ver evidencias/LEIA-ME.md). Entre fronteiras a
potência é constante, logo a energia varia linearmente: ligar as fronteiras por segmentos retos é exato.
Elementos de referência calculados SOMENTE dos parâmetros declarados (Seção 5.2.1): limites de SOC 10 % e 90 %
(20 e 180 kWh), ponta 18h–21h, energia necessária às 18h para descarregar 50 kW em toda a ponta
(20 + 150/0,95 kWh) e a trajetória mais tardia que a atinge carregando a 50 kW (0,95 × 12,5 kWh por intervalo).
Uso: python -I figura_energia_c3_c4.py <pasta_dados> <pasta_saida>
"""
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

dados, saida = Path(sys.argv[1]), Path(sys.argv[2])
saida.mkdir(parents=True, exist_ok=True)


def fronteiras(caso):
    linhas = list(csv.DictReader(open(dados / f"{caso}_fronteiras.csv", encoding="utf-8")))
    assert len(linhas) == 97
    return [0.25 * int(x["fronteira"]) for x in linhas], [float(x["E_kWh"]) for x in linhas]


t3, e3 = fronteiras("C3")
t4, e4 = fronteiras("C4")
E_REQ = 20.0 + 150.0 / 0.95          # 177,89 kWh às 18h
PASSO = 0.95 * 50.0 * 0.25            # 11,875 kWh internos por intervalo a 50 kW
t_ini = 18.0 - (E_REQ - 60.0) / PASSO * 0.25

TINTA, TINTA2, GRADE, SUP = "#0b0b0b", "#52514e", "#d9d8d4", "#ffffff"
AZUL, LARANJA, REF = "#2a78d6", "#eb6834", "#6f6e69"
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 8, "axes.edgecolor": TINTA2,
                     "axes.labelcolor": TINTA, "xtick.color": TINTA2, "ytick.color": TINTA2,
                     "svg.fonttype": "none", "pdf.fonttype": 42})

fig, ax = plt.subplots(figsize=(16 / 2.54, 7.2 / 2.54), dpi=300)
fig.patch.set_facecolor(SUP)
ax.set_facecolor(SUP)
ax.axvspan(18, 21, color="#efeeea", lw=0, zorder=0)
ax.text(19.5, 196, "ponta", ha="center", va="top", color=TINTA2, fontsize=8)
for y, rot in ((180, "SOC 90 %"), (20, "SOC 10 %")):
    ax.axhline(y, color=REF, lw=0.6, ls=(0, (1, 2)), zorder=1)
    ax.text(0.15, y + 3, rot, color=TINTA2, fontsize=7, va="bottom")
ax.axvline(16.25, color=REF, lw=0.6, ls=(0, (4, 2)), zorder=1)
ax.text(16.15, 150, "a partir de 16h15, o horizonte\nde 2 h do MPC alcança a ponta", ha="right", va="center",
        color=TINTA2, fontsize=7)
ax.plot([t_ini, 18.0], [60.0, E_REQ], color=REF, lw=1.0, ls=(0, (5, 2)), zorder=2)
ax.annotate("carga mais tardia compatível\ncom 50 kW em toda a ponta", xy=(15.95, 81), xytext=(15.2, 96),
            ha="right", va="center", color=TINTA2, fontsize=7,
            arrowprops={"arrowstyle": "-", "color": TINTA2, "lw": 0.6})
ax.plot(t3, e3, color=AZUL, lw=2.0, solid_capstyle="round", zorder=3, label="C3 · bateria e rede")
ax.plot(t4, e4, color=LARANJA, lw=1.6, ls=(0, (4, 2.5)), zorder=4, label="C4 · FV, bateria e rede")
ax.text(14.1, 75.5, "C4", color=TINTA, fontsize=8, ha="center", va="bottom")
ax.text(14.1, 56.5, "C3", color=TINTA, fontsize=8, ha="center", va="top")
ax.annotate("178,0 kWh às 18h", xy=(18.0, max(e3)), xytext=(19.0, 172), fontsize=7, color=TINTA,
            arrowprops={"arrowstyle": "-", "color": TINTA2, "lw": 0.6}, va="center")
ax.annotate("carga às 12h45 (C4)", xy=(12.875, 63), xytext=(12.875, 38), fontsize=7, color=TINTA,
            arrowprops={"arrowstyle": "-", "color": TINTA2, "lw": 0.6}, ha="center", va="top")
ax.set_xlim(0, 24)
ax.set_ylim(0, 200)
ax.set_xticks(range(0, 25, 3), [f"{h}h" for h in range(0, 25, 3)])
ax.set_yticks(range(0, 201, 50))
ax.set_xlabel("Hora local (America/Sao_Paulo), 2 de outubro de 2026")
ax.set_ylabel("Energia armazenada [kWh]")
ax.grid(axis="y", color=GRADE, lw=0.5, zorder=0)
for lado in ("top", "right"):
    ax.spines[lado].set_visible(False)
ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), frameon=False, fontsize=7, handlelength=2.8)
fig.tight_layout(pad=0.4)
for ext in ("png", "svg", "pdf"):
    fig.savefig(saida / f"figura_6_4_energia_armazenada_C3_C4.{ext}", facecolor=SUP,
                **({"dpi": 300} if ext == "png" else {}))
print("t_ini %.3f h, E_req %.3f kWh, max C3 %.3f, max C4 %.3f" % (t_ini, E_REQ, max(e3), max(e4)))
