"""Modelo preliminar do conversor DC/DC da ETAPA 5."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DCDCConfig


def _nonnegative_array(value, name: str) -> np.ndarray:
    array = np.atleast_1d(np.asarray(value, dtype=float))
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} deve ser escalar ou vetor unidimensional não vazio.")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} deve conter somente valores finitos.")
    if (array < 0.0).any():
        raise ValueError(f"{name} não pode conter valores negativos.")
    return array


class DCDCConverterModel:
    """Conversor de eficiência constante, sem dinâmica ou mapa de carga."""

    def __init__(self, config: DCDCConfig) -> None:
        config.validate()
        self.config = config

    def evaluate(self, input_power_kW) -> pd.DataFrame:
        power = _nonnegative_array(input_power_kW, "input_power_kW")
        output = self.config.efficiency * power
        loss = power - output
        return pd.DataFrame(
            {
                "P_dc_dc_input_kW": power,
                "dc_dc_efficiency": np.full_like(power, self.config.efficiency),
                "P_dc_dc_output_kW": output,
                "P_dc_dc_loss_kW": loss,
            }
        )


__all__ = ["DCDCConverterModel"]
