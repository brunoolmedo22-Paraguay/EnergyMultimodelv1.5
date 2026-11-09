"""Gera a evidência reproduzível do Piso 3C-1 (casos sintéticos do commitment dinâmico resolvidos com Pyomo + HiGHS).

Uso: python -m ems_v2.milp.evidencia_3c1 [saida.md] [repeticoes]   (a partir da raiz do repositório)

Registra versões, hardware, configuração, classificação, objetivo, eventos, garantia de permanência, tamanho, tempos
(mediana e máximo de ``repeticoes`` execuções — amostra PEQUENA, sem caráter estatístico) e aceitação de cada caso —
inclusive inviáveis. Sintético/algébrico: não é validação física.
"""
from __future__ import annotations

import dataclasses
import os
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import fixtures_3c1 as Y
from .ambiente import verificar_ambiente
from .config import CONFIG_ANALITICA as C
from .solver_3c1 import resolver_3c1

RAIZ = Path(__file__).resolve().parents[2]

CASOS = [
    ("A transições", Y.caso_a, None, "u = [0,1,1,0]; y_1 = z_3 = 1; R$ 7 (eventos)"),
    ("B rampa", Y.caso_b, None, "p = [15,20,25,30]; R$ 2,5"),
    ("C T_on = 45", Y.caso_c, None, "u = [1,1,1,0]; R$ 5"),
    ("C T_on = 0", lambda: Y.caso_c(0.0), None, "u = [1,0,0,0]; R$ 0"),
    ("D T_off = 45", Y.caso_d, None, "u = [0,0,0,1]; R$ 3,5"),
    ("D T_off = 0", lambda: Y.caso_d(0.0), None, "u = [1,0,0,1]; R$ 1"),
    ("E obrigação OFF herdada", Y.caso_e, None, "u = [0,0,1,1]; R$ 10"),
    ("E obrigação ON herdada", lambda: Y.caso_e(ligado=True), None, "u = [1,1,0,0]; R$ 5"),
    ("F cumprir_na_janela", Y.caso_f, None, "u = [0,1,1,1]; R$ 5; garantia completa"),
    ("F residual vinculante", lambda: Y.caso_f("obrigacao_residual_vinculante"), None,
     "u = [0,0,0,1]; R$ 0; obrigação 1800 s"),
    ("G 2 unidades do bloco", Y.caso_g, None, "u#1 = 1111, u#2 = 0011; R$ 1"),
    ("H enumeração", Y.caso_h, None, "R$ 12,7 (= enumeração exaustiva 2⁸ × LP racional)"),
    ("I rampa inviável", Y.caso_i_rampa, None, "inviável"),
    ("I permanência inviável", Y.caso_i_permanencia, None, "inviável"),
    ("J contínuo N = 8", Y.caso_j, None, "aceito"),
    ("PEMFC instantânea (abstração)", Y.pemfc_instantanea, None, "R$ 0,33 (h·q + massas de evento)"),
    ("J N = 32 (escala)", lambda: Y.caso_j(N=32, L=[5, 25, 30, 35, 10, 5, 30, 30] * 4), None, "aceito (tempo)"),
    ("J N = 96 (escala)", lambda: Y.caso_j(N=96, L=[5, 25, 30, 35, 10, 5, 30, 30] * 12), None, "aceito (tempo)"),
]


def _f(x, nd=6):
    return "—" if x is None else (f"{x:.{nd}g}" if isinstance(x, float) else str(x))


def main(saida: str | None, rep: int = 5) -> None:
    amb = verificar_ambiente()
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    linhas = [
        "# Evidência executada — Piso 3C-1 (gerada por `python -m ems_v2.milp.evidencia_3c1`)", "",
        f"- Data (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')} · commit: `{sha}`",
        f"- Python {platform.python_version()} · {platform.platform()} · {os.cpu_count()} CPUs · "
        f"{platform.processor() or platform.machine()}",
        f"- Pyomo {amb['versoes'].get('pyomo')} · highspy {amb['versoes'].get('highspy')} · HiGHS {amb['versao_highs']} · "
        f"interface `{amb['interface']}` · divergências das versões fixadas: {amb['divergencias'] or 'nenhuma'}",
        f"- Configuração: `{dataclasses.asdict(C)}` (gaps nulos, 1 thread, semente 0)",
        f"- Tempos: mediana e máximo de {rep} execuções por caso nesta máquina (amostra pequena; SEM caráter estatístico).",
        "", "Sintético/algébrico — **não é validação física**.", "",
        "| Caso | Esperado (analítico/enumeração) | Classificação | Despacho | Objetivo (R$) | Eventos | Garantia | "
        "Var. / bin. / restr. | Construção med. (s) | Solver med./máx. (s) |",
        "|---|---|---|---|---|---|---|---|---|---|"]
    for nome, f, cp, esp in CASOS:
        rs = [resolver_3c1(f(), C, cp) for _ in range(rep)]
        r = rs[0]
        t = r.tamanho or {}
        cons = [x.tempos_s.get("construcao_s") or 0.0 for x in rs]
        sol = [x.tempos_s.get("solver_s") or 0.0 for x in rs]
        ev = "; ".join(f"{k}: {v['partidas']}↑/{v['paradas']}↓" for k, v in sorted(r.eventos.items())) or "—"
        linhas.append(
            f"| {nome} | {esp} | `{r.classificacao}` | `{r.estado_despacho}` | {_f(r.objetivo)} | {ev} | "
            f"{r.garantia_permanencia or '—'} | {t.get('variaveis', '—')} / {t.get('binarias_livres', '—')} / "
            f"{t.get('restricoes', '—')} | {statistics.median(cons):.3f} | {statistics.median(sol):.3f} / {max(sol):.3f} |")
    texto = "\n".join(linhas) + "\n"
    if saida:
        Path(saida).write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None, int(sys.argv[2]) if len(sys.argv) > 2 else 5)
