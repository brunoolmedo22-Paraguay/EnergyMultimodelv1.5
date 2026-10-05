"""Balanço de hidrogênio pela lei de Faraday."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import HydrogenConfig
from .dc_dc import _nonnegative_array


class HydrogenConsumptionModel:
    """Calcula consumo eletroquímico e suprimento incluindo utilização."""

    def __init__(self, number_of_cells: int, config: HydrogenConfig) -> None:
        if int(number_of_cells) <= 0:
            raise ValueError("number_of_cells deve ser positivo.")
        config.validate()
        self.number_of_cells = int(number_of_cells)
        self.config = config

    def evaluate(self, current_A) -> pd.DataFrame:
        current = _nonnegative_array(current_A, "current_A")
        cfg = self.config
        molar_flow_stoich = (
            self.number_of_cells * current / (2.0 * cfg.faraday_constant_C_mol)
        )
        consumed_kg_s = molar_flow_stoich * cfg.hydrogen_molar_mass_kg_mol
        supplied_kg_s = consumed_kg_s / cfg.utilization
        supplied_kg_h = supplied_kg_s * 3600.0
        chemical_power_kW = supplied_kg_h * cfg.lower_heating_value_kWh_kg
        return pd.DataFrame(
            {
                "hydrogen_stoichiometric_mol_s": molar_flow_stoich,
                "hydrogen_consumed_kg_s": consumed_kg_s,
                "hydrogen_consumed_kg_h": consumed_kg_s * 3600.0,
                "hydrogen_utilization": np.full_like(current, cfg.utilization),
                "hydrogen_supplied_kg_s": supplied_kg_s,
                "hydrogen_supplied_kg_h": supplied_kg_h,
                "hydrogen_chemical_power_LHV_kW": chemical_power_kW,
                "hydrogen_consumption_within_manual_limit": (
                    supplied_kg_h <= cfg.maximum_consumption_kg_h + 1e-12
                ),
                "hydrogen_consumption_limit_kg_h": np.full_like(
                    current, cfg.maximum_consumption_kg_h
                ),
            }
        )


__all__ = ["HydrogenConsumptionModel"]
