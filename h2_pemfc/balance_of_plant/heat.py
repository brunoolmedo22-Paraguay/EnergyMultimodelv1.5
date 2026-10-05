"""Balanço térmico energético aproximado do sistema PEMFC."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import HeatConfig
from .dc_dc import _nonnegative_array


class HeatProductionModel:
    """Separa calor do stack e rejeito energético total equivalente."""

    def __init__(self, config: HeatConfig) -> None:
        config.validate()
        self.config = config

    def evaluate(
        self,
        *,
        chemical_power_kW,
        gross_stack_power_kW,
        dc_dc_loss_kW,
        auxiliary_power_kW,
        net_power_kW,
    ) -> pd.DataFrame:
        chemical = _nonnegative_array(chemical_power_kW, "chemical_power_kW")
        gross = _nonnegative_array(gross_stack_power_kW, "gross_stack_power_kW")
        dc_loss = _nonnegative_array(dc_dc_loss_kW, "dc_dc_loss_kW")
        auxiliary = _nonnegative_array(auxiliary_power_kW, "auxiliary_power_kW")
        net = _nonnegative_array(net_power_kW, "net_power_kW")
        sizes = {len(chemical), len(gross), len(dc_loss), len(auxiliary), len(net)}
        if len(sizes) != 1:
            raise ValueError("Todas as entradas térmicas devem ter o mesmo comprimento.")

        stack_reaction_heat = np.maximum(chemical - gross, 0.0)
        total_rejected = np.maximum(chemical - net, 0.0)
        explicitly_accounted = stack_reaction_heat + dc_loss + auxiliary
        unallocated = total_rejected - explicitly_accounted
        return pd.DataFrame(
            {
                "P_stack_reaction_heat_kW": stack_reaction_heat,
                "P_dc_dc_heat_kW": dc_loss,
                "P_auxiliary_equivalent_heat_kW": auxiliary,
                "P_total_rejected_equivalent_kW": total_rejected,
                "P_unallocated_balance_kW": unallocated,
                "stack_heat_within_manual_limit": (
                    stack_reaction_heat
                    <= self.config.maximum_stack_heat_dissipation_kW + 1e-12
                ),
                "stack_heat_limit_kW": np.full_like(
                    chemical, self.config.maximum_stack_heat_dissipation_kW
                ),
                "energy_balance_closure_kW": chemical - net - total_rejected,
            }
        )


__all__ = ["HeatProductionModel"]
