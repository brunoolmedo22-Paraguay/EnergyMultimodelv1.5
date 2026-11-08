"""Gera a evidência reproduzível do Piso 3B-P (casos sintéticos resolvidos com Pyomo + HiGHS).

Uso: python -m ems_v2.milp.evidencia [saida.md]   (a partir da raiz do repositório)
Registra versões, hardware, configuração, classificação, terminação, objetivo, limite, gap, tamanho, tempos e
aceitação de cada caso — inclusive inviáveis e terminações incompletas. Sintético/algébrico: não é validação física.
"""
from __future__ import annotations

import dataclasses
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import fixtures_3b as X
from .ambiente import verificar_ambiente
from .config import CONFIG_ANALITICA as C
from .solver import resolver

RAIZ = Path(__file__).resolve().parents[2]

CASOS = [
    ("A01", X.a01, C, "60 kW × 60 × 1 min; 60 kWh"),
    ("A02", X.a02, C, "10 kW × 1 min; 1/6 kWh"),
    ("A03 (1×60 min)", X.a03, C, "e_N = 50 kWh"),
    ("A03 (60×1 min)", lambda: X.a03(1, 60), C, "e_N = 50 kWh"),
    ("A04", X.a04, C, "P_c = 10 kW; e_1 = 69 kWh"),
    ("B01A", X.b01a, C, "E_indisp = 100 kWh; custo R$ 0"),
    ("B01B", X.b01b, C, "C_oper = 20 kW; custo R$ 10"),
    ("A05-FEAS", X.a05_feas, C, "objetivo nulo declarado; carregar e verter factíveis"),
    ("A05-OPT", X.a05_opt, C, "P_c = 10 kW; C_oper = 0; e_1 = 59 kWh; R$ 0"),
    ("A06", lambda: X.a06(preco_h2=10.0), C, "q = 0,9 kg/h; 0,015 kg/min; R$ 0,15 (c_H = 10 R$/kg)"),
    ("A06 ON a 5 kW", lambda: X.a06(carga=5.0, p_ant=10.0), C, "inviável (5 kW ∉ domínio ON)"),
    ("PWL não convexa + BESS", X.pwl_com_bateria, C, "p = 16 kW; q = 1,05 kg/h; R$ 12,5 (enumeração)"),
    ("A07", X.a07, C, "inviável (P_min 20 kW, demanda 5 kW, sem sumidouro)"),
    ("A08 duro", lambda: X.a08(False), C, "inviável"),
    ("A08 degradado", lambda: X.a08(True), C, "ℓ = 5 kW; ENS = 5 kWh; R$ 10 (V = 2 R$/kWh)"),
    ("2 BESS heterogêneos", X.duas_baterias, C, "P_c = 8,75 / 6,25 kW; R$ 1,1875"),
    ("Exclusividade", X.exclusividade, C, "P_c = 1/0,9 kW; R$ 18,888…"),
    ("Vários UIDs", X.multi_uid, C, "auditoria aceita"),
    ("Maior N=16 (completo)", X.instancia_maior, C, "ótimo"),
    ("Maior N=16 mip_max_improving_sols=1", X.instancia_maior,
     dataclasses.replace(C, opcoes_highs={"mip_max_improving_sols": 1}), "incumbente NÃO ótimo, auditado"),
    ("Maior N=16 time_limit=0", X.instancia_maior, dataclasses.replace(C, time_limit_s=0.0), "sem incumbente"),
    ("Maior N=48 time_limit=0,05 s (não determinístico)", lambda: X.instancia_maior(48),
     dataclasses.replace(C, time_limit_s=0.05), "limite de TEMPO; incumbente depende da máquina"),
]


def _f(x, nd=6):
    return "—" if x is None else (f"{x:.{nd}g}" if isinstance(x, float) else str(x))


def main(saida: str | None) -> None:
    amb = verificar_ambiente()
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    linhas = [
        "# Evidência executada — Piso 3B-P (gerada por `python -m ems_v2.milp.evidencia`)", "",
        f"- Data (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')} · commit: `{sha}`",
        f"- Python {platform.python_version()} · {platform.platform()} · {os.cpu_count()} CPUs · "
        f"{platform.processor() or platform.machine()}",
        f"- Pyomo {amb['versoes'].get('pyomo')} · highspy {amb['versoes'].get('highspy')} · HiGHS {amb['versao_highs']} · "
        f"interface `{amb['interface']}` · divergências das versões fixadas: {amb['divergencias'] or 'nenhuma'}",
        f"- Configuração base: `{dataclasses.asdict(C)}` (gaps nulos, 1 thread, semente 0)", "",
        "Sintético/algébrico — **não é validação física**. Tempos de parede nesta máquina (indicativos).", "",
        "| Caso | Esperado (analítico) | Classificação | Terminação / status | Objetivo (R$) | Limite | gap rel. | "
        "Var. / bin. / restr. | Construção (s) | Solver (s) | Despacho |",
        "|---|---|---|---|---|---|---|---|---|---|---|"]
    for nome, f, cfg, esp in CASOS:
        e, cp = f()
        r = resolver(e, cfg, cp)
        t = r.tamanho or {}
        linhas.append(
            f"| {nome} | {esp} | `{r.classificacao}` | {r.terminacao} / {r.status_solucao} | {_f(r.objetivo)} | "
            f"{_f(r.limite_dual)} | {_f(r.gap_rel, 3)} | {t.get('variaveis', '—')} / {t.get('binarias_livres', '—')} / "
            f"{t.get('restricoes', '—')} | {_f(r.tempos_s.get('construcao_s'), 2)} | {_f(r.tempos_s.get('solver_s'), 2)} | "
            f"`{r.estado_despacho}` |")
    texto = "\n".join(linhas) + "\n"
    if saida:
        Path(saida).write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
