"""Estratégia EMS e janela da missão de um cenário (Piso 2C).

Somente opções EXISTENTES e verificadas do motor V1.6 (``orchestrator_runtime`` / ``ems_integration``) são
expostas. Nada aqui altera a formulação do otimizador:

* **Função objetivo** — uma única: o custo econômico da operação já implementado em ``despacho.custo_lote``
  (H₂ pela curva kg/kWh × preço, degradação da bateria, CVU e partida da térmica, penalidades de déficit e de
  vertimento). É identificada explicitamente (``OBJECTIVE``); não há seletor multiobjetivo.
* **Algoritmo de resolução** — ``orchestrator_runtime.ALGORITMOS`` (GA, GWO, NGO ou só SQP), opção de
  metaheurística penalizada (``meta_penalizada``).
* **Parâmetros econômicos e conversores** — os mesmos campos e faixas do formulário do console V1.6.
* **Horizonte móvel N, semente e tolerância do SOC-alvo** — idem.
* **Validação** — validação dinâmica do H₂ no modelo PEMFC (``executor.validar_fc_dinamico``), a única opção de
  validação implementada.

Tolerâncias internas do motor (viabilidade 1e-6, SLSQP ``ftol`` 1e-9 e 200 iterações, passo de 60 s) são FIXAS
no V1.6 e apenas informadas (``ENGINE_FIXED``).

O bloco ``ems_strategy`` (antes reservado como ``None``) e o bloco ``mission`` (novo, opcional) fazem parte do
documento do cenário: a versão do cenário usada por uma execução guarda a configuração EXATA.
"""
from __future__ import annotations

import copy
import re
from typing import Any

import pandas as pd

FORMAT_VERSION = 1
OBJECTIVE = "custo_economico_v16"
OBJECTIVE_LABEL = "Custo econômico da operação (função objetivo do EMS V1.6)"
OBJECTIVE_TERMS = (
    "H₂ consumido pela PEMFC (curva empírica kg/kWh × preço do H₂)",
    "Degradação da bateria (R$/kWh processado)",
    "Custo variável (CVU) e custo de partida da térmica",
    "Penalidade de energia não atendida (déficit)",
    "Penalidade de vertimento (excesso despachável e renovável)",
)
# Mesmos códigos de orchestrator_runtime.ALGORITMOS (sem importar o runtime aqui: leitura leve do domínio).
ALGORITHMS = {2: "GWO · Grey Wolf Optimizer", 3: "NGO · Northern Goshawk Optimization", 1: "GA · Algoritmo genético",
              0: "Só SQP (sem metaheurística)"}
# Faixas aceitas pelo formulário do console V1.6 (orchestrator_app._optimizer_page) — não são limites científicos.
RANGES = {
    "N": (1, 15), "seed": (0, 10000), "soc_alvo_tol": (0.01, 0.50),
    "econ.preco_H2_rs_kg": (0.0, 500.0), "econ.c_deg_bateria_rs_kWh": (0.0, 10.0),
    "econ.pen_deficit_rs_kWh": (0.0, 1e4), "econ.pen_excesso_rs_kWh": (0.0, 1e3),
    "eta_conv.eta_dc1": (0.5, 1.0), "eta_conv.eta_dc2": (0.5, 1.0), "eta_conv.eta_dc": (0.5, 1.0),
}
LABELS = {
    "N": "Horizonte móvel N [passos de 1 min]", "seed": "Semente aleatória", "soc_alvo_tol": "Tolerância do SOC-alvo (±)",
    "econ.preco_H2_rs_kg": "Preço do H₂ [R$/kg]", "econ.c_deg_bateria_rs_kWh": "Degradação da bateria [R$/kWh]",
    "econ.pen_deficit_rs_kWh": "Penalidade de déficit [R$/kWh]", "econ.pen_excesso_rs_kWh": "Penalidade de vertimento [R$/kWh]",
    "eta_conv.eta_dc1": "η FC (somente base stack)", "eta_conv.eta_dc2": "η bateria ↔ barramento", "eta_conv.eta_dc": "η PV",
}
ENGINE_FIXED = {
    "Passo de tempo do despacho": "60 s (Ts_s fixo no runtime V1.6; grade de 1 min)",
    "Tolerância de viabilidade": "1e-6 (despacho.TOL_VIAVEL)",
    "Refino SLSQP": "ftol 1e-9, até 200 iterações",
    "Combinações inteiras por passo": "até 64 (vizinhança da configuração anterior)",
    "SOC-alvo final da bateria": "igual ao SOC inicial ± tolerância (restrição existente do EMS V1.6)",
}
STEP_S = 60                       # passo do motor V1.6 (orchestrator_runtime: "Ts_s": 60)
MIN_DURATION_MIN = 4              # ponte.recortar exige ≥ 5 pontos na janela da carga
LONG_DURATION_MIN = 1440
UNDECLARED_CLOCK = "mesmo_relogio"


def default_strategy() -> dict:
    """Valores iniciais = ``orchestrator_runtime.default_optimizer_config`` (padrão do console V1.6)."""
    return {"format_version": FORMAT_VERSION, "objective": OBJECTIVE, "algorithm": 2, "meta_penalizada": False,
            "N": 3, "seed": 0, "soc_alvo_tol": 0.05, "validar_h2": False,
            "econ": {"preco_H2_rs_kg": 25.0, "c_deg_bateria_rs_kWh": 0.08, "pen_deficit_rs_kWh": 50.0,
                     "pen_excesso_rs_kWh": 0.5},
            "eta_conv": {"eta_dc1": 0.97, "eta_dc2": 0.96, "eta_dc": 0.97}}


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _get(d: dict, path: str) -> Any:
    cur: Any = d
    for p in path.split("."):
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur


def strategy_errors(s: Any) -> list[str]:
    """Validação estrutural e de faixas da estratégia (``None`` = ainda não definida, válido)."""
    if s is None:
        return []
    if not isinstance(s, dict):
        return ["Estratégia EMS ilegível."]
    errs: list[str] = []
    if s.get("format_version") != FORMAT_VERSION:
        errs.append("Estratégia EMS: formato não reconhecido.")
    if s.get("objective") != OBJECTIVE:
        errs.append("Estratégia EMS: função objetivo desconhecida (o motor V1.6 implementa apenas o custo econômico).")
    allowed = {"format_version", "objective", "algorithm", "meta_penalizada", "N", "seed", "soc_alvo_tol", "validar_h2",
               "econ", "eta_conv"}
    if set(s) - allowed:
        errs.append(f"Estratégia EMS com campos desconhecidos: {sorted(set(s) - allowed)}.")
    if s.get("algorithm") not in ALGORITHMS or isinstance(s.get("algorithm"), bool):
        errs.append("Estratégia EMS: algoritmo inexistente no motor V1.6.")
    for k in ("meta_penalizada", "validar_h2"):
        if not isinstance(s.get(k), bool):
            errs.append(f"Estratégia EMS: '{k}' deve ser verdadeiro/falso.")
    for k in ("econ", "eta_conv"):
        if not isinstance(s.get(k), dict) or set(s[k]) != {p.split(".")[1] for p in RANGES if p.startswith(k + ".")}:
            errs.append(f"Estratégia EMS: bloco '{k}' incompleto ou com campos desconhecidos.")
    for path, (lo, hi) in RANGES.items():
        v = _get(s, path)
        if path in ("N", "seed"):
            if not isinstance(v, int) or isinstance(v, bool):
                errs.append(f"{LABELS[path]}: inteiro obrigatório.")
                continue
        if _num(v) is None:
            errs.append(f"{LABELS[path]}: valor numérico obrigatório.")
        elif not lo <= float(v) <= hi:
            errs.append(f"{LABELS[path]}: {v:g} fora da faixa aceita pelo motor V1.6 [{lo:g}, {hi:g}].")
    return errs


def optimizer_config(s: dict) -> dict:
    """Estratégia → ``optimizer_cfg`` no formato EXATO do console V1.6 (orchestrator_app._optimizer_page)."""
    return {"algoritmo": int(s["algorithm"]), "N": int(s["N"]), "seed": int(s["seed"]),
            "meta_penalizada": bool(s["meta_penalizada"]), "validar": bool(s["validar_h2"]),
            "soc_alvo_tol": float(s["soc_alvo_tol"]),
            "econ": {k: float(v) for k, v in s["econ"].items()}, "eta_conv": {k: float(v) for k, v in s["eta_conv"].items()}}


# ------------------------------------------------------------------ janela da missão
def default_mission(start: str, timezone: str | None, duration_min: int) -> dict:
    return {"format_version": FORMAT_VERSION, "start": start, "timezone": timezone, "duration_min": int(duration_min),
            "undeclared_clock": None}


def mission_errors(m: Any) -> list[str]:
    """``mission``: ``start`` (relógio de parede ISO, minuto inteiro) no fuso ``timezone`` (``None`` = não declarado),
    ``duration_min`` (≥ 4) e ``undeclared_clock`` (declaração explícita para séries sem fuso)."""
    if m is None:
        return []
    if not isinstance(m, dict):
        return ["Janela da missão ilegível."]
    errs: list[str] = []
    if m.get("format_version") != FORMAT_VERSION:
        errs.append("Janela da missão: formato não reconhecido.")
    if set(m) - {"format_version", "start", "timezone", "duration_min", "undeclared_clock"}:
        errs.append("Janela da missão com campos desconhecidos.")
    try:
        t = pd.Timestamp(str(m.get("start")))
        if t.tzinfo is not None:
            errs.append("Início da missão: informe o relógio de parede sem fuso (o fuso é declarado à parte).")
        elif t.second or t.microsecond or t.nanosecond:
            errs.append("Início da missão deve cair em um minuto inteiro (grade de 1 min do motor).")
    except (ValueError, TypeError):
        errs.append("Início da missão inválido.")
    tz = m.get("timezone")
    if tz is not None:
        from .forecasts import valid_timezone

        if not isinstance(tz, str) or not valid_timezone(tz):
            errs.append("Fuso horário da missão inválido.")
    d = m.get("duration_min")
    if not isinstance(d, int) or isinstance(d, bool) or d < MIN_DURATION_MIN:
        errs.append(f"Duração da missão: inteiro ≥ {MIN_DURATION_MIN} min (o motor exige ao menos 5 instantes).")
    if m.get("undeclared_clock") not in (None, UNDECLARED_CLOCK):
        errs.append("Declaração de relógio inválida.")
    return errs


def mission_key(m: dict) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", str(m.get("start")))


def copy_strategy(s: dict | None) -> dict:
    return copy.deepcopy(s) if s is not None else default_strategy()


__all__ = ["ALGORITHMS", "ENGINE_FIXED", "FORMAT_VERSION", "LABELS", "LONG_DURATION_MIN", "MIN_DURATION_MIN", "OBJECTIVE",
           "OBJECTIVE_LABEL", "OBJECTIVE_TERMS", "RANGES", "STEP_S", "UNDECLARED_CLOCK", "default_mission",
           "default_strategy", "mission_errors", "optimizer_config", "strategy_errors"]
