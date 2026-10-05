"""Consumo auxiliar agregado do sistema PEMFC aproximado."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import AuxiliaryPowerConfig
from .dc_dc import _nonnegative_array


class EquivalentAuxiliaryPowerModel:
    """Hipótese contínua e crescente para o balance of plant elétrico.

    P_aux = P_aux,nom * (P_stack / P_stack,ref) ** exponent

    O modelo é equivalente: não atribui parcelas individuais ao compressor,
    bomba, ventiladores ou controladores sem dados experimentais.
    """

    def __init__(self, config: AuxiliaryPowerConfig) -> None:
        config.validate()
        self.config = config

    def evaluate(self, gross_stack_power_kW) -> pd.DataFrame:
        gross = _nonnegative_array(gross_stack_power_kW, "gross_stack_power_kW")
        load_fraction = gross / self.config.reference_gross_power_kW
        auxiliary = self.config.nominal_auxiliary_power_kW * np.power(
            load_fraction,
            self.config.load_exponent,
        )
        return pd.DataFrame(
            {
                "auxiliary_load_fraction": load_fraction,
                "P_aux_equivalent_kW": auxiliary,
                "auxiliary_load_exponent": np.full_like(
                    gross, self.config.load_exponent
                ),
            }
        )


__all__ = ["EquivalentAuxiliaryPowerModel"]
