"""Estimativa estequiométrica do consumo de oxigênio e ar."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import AirConfig
from .dc_dc import _nonnegative_array


class AirConsumptionModel:
    """Calcula o fluxo de ar seco a partir de O2 + 4e- -> 2O2-."""

    def __init__(
        self,
        number_of_cells: int,
        faraday_constant_C_mol: float,
        config: AirConfig,
    ) -> None:
        if int(number_of_cells) <= 0:
            raise ValueError("number_of_cells deve ser positivo.")
        if not np.isfinite(faraday_constant_C_mol) or faraday_constant_C_mol <= 0.0:
            raise ValueError("A constante de Faraday deve ser positiva e finita.")
        config.validate()
        self.number_of_cells = int(number_of_cells)
        self.faraday_constant_C_mol = float(faraday_constant_C_mol)
        self.config = config

    def evaluate(self, current_A) -> pd.DataFrame:
        current = _nonnegative_array(current_A, "current_A")
        cfg = self.config
        oxygen_mol_s = (
            self.number_of_cells * current
            / (4.0 * self.faraday_constant_C_mol)
        )
        oxygen_kg_s = oxygen_mol_s * cfg.oxygen_molar_mass_kg_mol
        stoichiometric_air_kg_s = oxygen_kg_s / cfg.oxygen_mass_fraction_dry_air
        supplied_air_g_s = 1000.0 * cfg.lambda_air * stoichiometric_air_kg_s
        return pd.DataFrame(
            {
                "oxygen_stoichiometric_mol_s": oxygen_mol_s,
                "oxygen_stoichiometric_g_s": oxygen_kg_s * 1000.0,
                "air_stoichiometric_g_s": stoichiometric_air_kg_s * 1000.0,
                "lambda_air": np.full_like(current, cfg.lambda_air),
                "air_supplied_g_s": supplied_air_g_s,
                "air_flow_within_manual_limit": (
                    supplied_air_g_s <= cfg.maximum_air_flow_g_s + 1e-12
                ),
                "air_flow_limit_g_s": np.full_like(
                    current, cfg.maximum_air_flow_g_s
                ),
            }
        )


__all__ = ["AirConsumptionModel"]
