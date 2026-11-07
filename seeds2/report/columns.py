"""Dicionário das colunas persistidas pelo Piso 2C (unidade e significado), usado pelo Excel e pelo PDF.

As descrições documentam o que o runner (``seeds2.operation.runner``) e o runtime V1.6 GRAVAM — não redefinem as
grandezas. Coluna desconhecida: preservada integralmente e marcada "não catalogada" (nunca omitida); unidade
desconhecida fica "não declarada" (nunca presumida).
"""
from __future__ import annotations

import re

from seeds2.operation import forecasts as F

UNKNOWN_UNIT = "não declarada"
TIME_UTC, TIME_LOCAL, TIME_RUNTIME = "utc", "local", "runtime"

_FIXED: dict[str, tuple[str, str]] = {
    # entradas/missao.csv
    "passo": ("—", "Índice do instante na grade de 1 min da missão (0 = início)."),
    "t_min": ("min", "Minutos desde o início da missão."),
    "timestamp_utc": ("instante", "Instante real em UTC (ISO 8601 com 'Z'); sem fuso declarado, relógio não declarado."),
    "timestamp_local": ("instante", "Relógio de parede no fuso declarado da missão (pode ser não uniforme na mudança de horário)."),
    "timestamp_runtime": ("instante", "Grade UNIFORME entregue ao runtime V1.6 (início local + k min)."),
    # saidas/despacho_ems.csv
    "P_carga_kW": ("kW", "Demanda elétrica (potência) na grade do motor."),
    "P_solar_kW": ("kW", "Potência FV calculada pelo modelo físico e entregue ao EMS (o balanço aplica η PV — "
                         "ver relatorio_ems.json 'eta'). Potência disponível, não despachada."),
    "P_eolica_kW": ("kW", "Potência eólica calculada pelo modelo físico e entregue ao EMS (disponível, não despachada)."),
    "P_renovavel_vertida_kW": ("kW", "Potência renovável vertida (não aproveitada)."),
    "P_carga_liquida_kW": ("kW", "Demanda líquida após o abatimento das renováveis."),
    "deficit_kW": ("kW", "Potência não atendida (déficit)."),
    "excesso_despachavel_kW": ("kW", "Excesso despachável (vertimento das fontes despacháveis)."),
    "h2_kg": ("kg (por passo)", "H₂ consumido no passo — estimativa do EMS (curva empírica kg/kWh)."),
    "h2_kg_validacao_dinamica": ("kg (por passo)", "H₂ no passo pela validação dinâmica PEMFC (metodologia distinta da "
                                                   "estimativa do EMS)."),
    "custo_rs": ("R$ (por passo)", "Custo do passo (função objetivo do EMS V1.6)."),
    "J_meta_rs": ("R$", "Valor da função objetivo no passo — solução da metaheurística (antes do refino)."),
    "J_refino_rs": ("R$", "Valor da função objetivo no passo — após o refino SLSQP."),
    "violacao_meta": ("—", "Violação de restrições da solução da metaheurística."),
    "violacao_refino": ("—", "Violação de restrições após o refino."),
    "P_renovavel_disponivel_kW": ("kW", "Potência renovável disponível considerada pelo EMS."),
    "custo_partida_rs": ("R$ (por passo)", "Custo de partida no passo."),
    "n_combinacoes": ("—", "Combinações inteiras avaliadas no passo."),
    # séries normalizadas das previsões
    "timestamp": ("instante", "Instante da observação (relógio de parede do fuso declarado da previsão / runtime)."),
}


def describe(column: str) -> tuple[str, str, bool]:
    """(unidade, descrição, catalogada?)."""
    if column in _FIXED:
        u, d = _FIXED[column]
        return u, d, True
    if column in F.VARIABLES:
        v = F.VARIABLES[column]
        return v.unit, v.label + ".", True
    m = re.fullmatch(r"P_(\w+?)_meta_kW", column)
    if m:
        return "kW", f"Potência da fonte '{m.group(1)}' na solução da metaheurística (antes do refino).", True
    m = re.fullmatch(r"Pmax_unid_(\w+)_kW", column)
    if m:
        return "kW", f"Potência máxima por unidade da fonte '{m.group(1)}' no passo.", True
    m = re.fullmatch(r"P_(\w+)_kW", column)
    if m:
        extra = " (+ descarga / − carga)" if m.group(1) == "bateria" else ""
        return "kW", f"Potência DESPACHADA pelo EMS para a fonte '{m.group(1)}'{extra}.", True
    m = re.fullmatch(r"SOC_(\w+)", column)
    if m:
        return "fração (0–1)", f"Estado de carga de '{m.group(1)}' (fração; multiplique por 100 para %).", True
    m = re.fullmatch(r"n_(\w+)", column)
    if m:
        return "unidades", f"Unidades em operação da fonte '{m.group(1)}'.", True
    return UNKNOWN_UNIT, "Coluna preservada do arquivo original (não catalogada neste dicionário).", False


def time_reference(column: str, timezone: str | None, *, model: bool = False) -> str | None:
    """Referência temporal de uma coluna de instante (None se não for coluna de tempo)."""
    if column == "timestamp_utc":
        return "UTC" if timezone else "relógio não declarado (sem fuso)"
    if column == "timestamp_local":
        return f"relógio de parede · {timezone}" if timezone else "relógio não declarado (sem fuso)"
    if column == "timestamp_runtime" or (model and column == "timestamp"):
        return ("grade uniforme do runtime (início no relógio local" + (f" · {timezone})" if timezone else ")"))
    return None


__all__ = ["UNKNOWN_UNIT", "describe", "time_reference"]
