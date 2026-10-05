"""Validação e preparação dos arquivos CSV do EMS para a ETAPA 8.

O CSV mínimo da interface contém somente ``timestamp`` e
``P_FC_requested_kW``. A máquina dinâmica da ETAPA 7 exige também
``FC_enable``; por isso, esta camada de integração acrescenta a coluna com o
valor padrão ``True`` quando ela não está presente e registra explicitamente
todos os padrões empregados.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from h2_pemfc.models.equivalent_65kw_dynamic import Equivalent65kWHorizonDynamicModel


@dataclass(frozen=True)
class EMSInputPreparation:
    """Resultado auditável da preparação de um perfil do EMS."""

    profile: pd.DataFrame
    defaults_used: dict[str, object]

    @property
    def defaults_message(self) -> str:
        if not self.defaults_used:
            return "Nenhum valor padrão foi necessário."
        parts = [f"{key}={value}" for key, value in self.defaults_used.items()]
        return "Valores padrão aplicados: " + ", ".join(parts) + "."


def prepare_ems_profile(
    raw: pd.DataFrame,
    dynamic_model: Equivalent65kWHorizonDynamicModel | None = None,
) -> EMSInputPreparation:
    """Valida o CSV mínimo e o converte no contrato da ETAPA 7.

    Não reordena timestamps, não elimina duplicatas e não renomeia colunas de
    forma silenciosa. Os nomes das colunas são o contrato explícito de unidade:
    ``P_FC_requested_kW`` em kW, temperaturas em °C e ``V_bus_V`` em volts.
    """
    if not isinstance(raw, pd.DataFrame):
        raise TypeError("O arquivo do EMS deve ser lido como pandas.DataFrame.")
    if raw.empty:
        raise ValueError("O arquivo CSV do EMS não pode estar vazio.")

    required_minimum = {"timestamp", "P_FC_requested_kW"}
    missing = sorted(required_minimum - set(raw.columns))
    if missing:
        raise ValueError(
            "Colunas mínimas ausentes: " + ", ".join(missing) + "."
        )

    allowed = {
        "timestamp",
        "P_FC_requested_kW",
        "FC_enable",
        "T_ambient_C",
        "T_coolant_in_C",
        "V_bus_V",
    }
    unknown = [column for column in raw.columns if column not in allowed]
    if unknown:
        raise ValueError(
            "Colunas não reconhecidas: " + ", ".join(unknown) + ". "
            "Use exatamente os nomes e unidades documentados."
        )

    model = dynamic_model or Equivalent65kWHorizonDynamicModel()
    cfg = model.configuration
    prepared = raw.copy()
    defaults: dict[str, object] = {}

    if "FC_enable" not in prepared:
        prepared["FC_enable"] = True
        defaults["FC_enable"] = True

    optional_defaults = {
        "T_ambient_C": cfg.default_ambient_temperature_C,
        "T_coolant_in_C": cfg.default_coolant_inlet_temperature_C,
        "V_bus_V": cfg.default_bus_voltage_V,
    }
    for column, default in optional_defaults.items():
        if column not in prepared:
            prepared[column] = float(default)
            defaults[column] = float(default)
            continue
        numeric = pd.to_numeric(prepared[column], errors="coerce")
        invalid_nonempty = prepared[column].notna() & numeric.isna()
        if invalid_nonempty.any():
            raise ValueError(f"{column} contém valores não numéricos.")
        if numeric.isna().any():
            missing_count = int(numeric.isna().sum())
            defaults[f"{column}_missing_values"] = (
                f"{missing_count} valor(es) preenchido(s) por retenção do último valor "
                f"válido; padrão inicial {float(default)}"
            )
        prepared[column] = numeric

    normalized = model.validate_profile(prepared)
    return EMSInputPreparation(profile=normalized, defaults_used=defaults)


def build_example_ems_profile() -> pd.DataFrame:
    """Exemplo mínimo, com variação suficiente para exercitar rampas e limites."""
    timestamps = pd.date_range("2026-08-03 13:00:00", periods=7, freq="1min")
    power = np.array([0.0, 10.0, 20.0, 35.0, 50.0, 55.0, 15.0])
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "P_FC_requested_kW": power,
        }
    )


__all__ = [
    "EMSInputPreparation",
    "build_example_ems_profile",
    "prepare_ems_profile",
]
