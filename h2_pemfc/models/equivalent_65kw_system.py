"""Sistema PEMFC aproximado com balance of plant preliminar da ETAPA 5.

O modelo compõe o stack eletroquímico da ETAPA 4 com submodelos separados de
DC/DC, consumo auxiliar equivalente, hidrogênio, ar e calor. Não implementa
inversão potência→corrente, solicitação de potência ou dinâmica temporal.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Iterable

import numpy as np
import pandas as pd

from h2_pemfc.balance_of_plant import (
    AirConsumptionModel,
    AuxiliaryPowerConfig,
    DCDCConverterModel,
    DEFAULT_STAGE5_BASE_CONFIGURATION,
    EquivalentAuxiliaryPowerModel,
    HeatProductionModel,
    HydrogenConsumptionModel,
    Stage5BaseConfiguration,
    build_parameter_records,
)
from h2_pemfc.models.equivalent_65kw_stack import Equivalent65kWHorizonStackModel


class Equivalent65kWHorizonSystemModel:
    """Modelo estático completo aproximado do VLIIPro50-22.

    A entrada continua sendo a corrente do stack. Esta classe acrescenta as
    potências do conversor e auxiliares, vazões e balanço térmico, mas não
    escolhe a corrente a partir de uma potência solicitada.
    """

    def __init__(
        self,
        stack_model: Equivalent65kWHorizonStackModel | None = None,
        base_configuration: Stage5BaseConfiguration = DEFAULT_STAGE5_BASE_CONFIGURATION,
        *,
        auxiliary_load_exponent: float = 1.35,
        auxiliary_configuration: AuxiliaryPowerConfig | None = None,
    ) -> None:
        base_configuration.validate()
        self.stack_model = stack_model or Equivalent65kWHorizonStackModel()
        self.base_configuration = base_configuration

        nominal_stack = self.stack_model.evaluate_point(
            self.stack_model.specification.current_max_A
        )
        self.nominal_model_gross_power_kW = float(nominal_stack["P_stack_kW"])
        if auxiliary_configuration is None:
            auxiliary_configuration = AuxiliaryPowerConfig.calibrated_from_nominal_balance(
                reference_gross_power_kW=self.nominal_model_gross_power_kW,
                dc_dc_efficiency=base_configuration.dc_dc.efficiency,
                target_net_power_kW=base_configuration.system_rated_power_kW,
                load_exponent=auxiliary_load_exponent,
            )
        auxiliary_configuration.validate()
        self.auxiliary_configuration = auxiliary_configuration

        cells = self.stack_model.specification.number_of_cells
        self.dc_dc_model = DCDCConverterModel(base_configuration.dc_dc)
        self.auxiliary_model = EquivalentAuxiliaryPowerModel(auxiliary_configuration)
        self.hydrogen_model = HydrogenConsumptionModel(
            cells, base_configuration.hydrogen
        )
        self.air_model = AirConsumptionModel(
            cells,
            base_configuration.hydrogen.faraday_constant_C_mol,
            base_configuration.air,
        )
        self.heat_model = HeatProductionModel(base_configuration.heat)
        self.parameter_records = build_parameter_records(
            base_configuration, auxiliary_configuration
        )

    def with_air_lambda(self, lambda_air: float) -> "Equivalent65kWHorizonSystemModel":
        """Cria uma cópia com outra hipótese de excesso de ar."""
        new_air = replace(self.base_configuration.air, lambda_air=float(lambda_air))
        new_base = replace(self.base_configuration, air=new_air)
        return type(self)(
            stack_model=self.stack_model,
            base_configuration=new_base,
            auxiliary_configuration=self.auxiliary_configuration,
        )

    def evaluate(
        self,
        current_A: Iterable[float] | float,
        temperature_K: float | None = None,
        anode_pressure_kPag: float | None = None,
        cathode_pressure_kPag: float | None = None,
        *,
        air_pressure_atm_abs: float | None = None,
        ambient_pressure_kPa: float | None = None,
    ) -> pd.DataFrame:
        """Avalia o sistema completo para uma corrente imposta."""
        stack = self.stack_model.evaluate(
            current_A=current_A,
            temperature_K=temperature_K,
            anode_pressure_kPag=anode_pressure_kPag,
            cathode_pressure_kPag=cathode_pressure_kPag,
            air_pressure_atm_abs=air_pressure_atm_abs,
            ambient_pressure_kPa=ambient_pressure_kPa,
        ).reset_index(drop=True)

        gross = stack["P_stack_kW"].to_numpy(dtype=float)
        current = stack["current_A"].to_numpy(dtype=float)
        dc_dc = self.dc_dc_model.evaluate(gross).reset_index(drop=True)
        auxiliary = self.auxiliary_model.evaluate(gross).reset_index(drop=True)

        net_power = (
            dc_dc["P_dc_dc_output_kW"].to_numpy(dtype=float)
            - auxiliary["P_aux_equivalent_kW"].to_numpy(dtype=float)
        )
        # Com o expoente >= 1 e a calibração nominal, a curva é não negativa
        # dentro do domínio previsto. Uma violação futura é tratada explicitamente.
        if (net_power < -1e-10).any():
            raise ValueError(
                "A hipótese auxiliar produziu potência líquida negativa; revise a configuração."
            )
        net_power = np.maximum(net_power, 0.0)

        hydrogen = self.hydrogen_model.evaluate(current).reset_index(drop=True)
        air = self.air_model.evaluate(current).reset_index(drop=True)
        chemical = hydrogen["hydrogen_chemical_power_LHV_kW"].to_numpy(dtype=float)
        gross_efficiency = np.divide(
            100.0 * gross,
            chemical,
            out=np.zeros_like(gross),
            where=chemical > 0.0,
        )
        net_efficiency = np.divide(
            100.0 * net_power,
            chemical,
            out=np.zeros_like(net_power),
            where=chemical > 0.0,
        )
        heat = self.heat_model.evaluate(
            chemical_power_kW=chemical,
            gross_stack_power_kW=gross,
            dc_dc_loss_kW=dc_dc["P_dc_dc_loss_kW"].to_numpy(dtype=float),
            auxiliary_power_kW=auxiliary["P_aux_equivalent_kW"].to_numpy(dtype=float),
            net_power_kW=net_power,
        ).reset_index(drop=True)

        result = pd.concat([stack, dc_dc, auxiliary, hydrogen, air, heat], axis=1)
        result["P_net_kW"] = net_power
        result["gross_electrical_efficiency_LHV_percent"] = gross_efficiency
        result["net_electrical_efficiency_LHV_percent"] = net_efficiency
        result["net_power_within_system_rated"] = (
            result["P_net_kW"]
            <= self.base_configuration.system_rated_power_kW + 1e-12
        )
        result["net_power_target_kW"] = self.base_configuration.system_rated_power_kW
        result["stage5_balance_closure_kW"] = (
            result["P_dc_dc_output_kW"]
            - result["P_aux_equivalent_kW"]
            - result["P_net_kW"]
        )
        result["system_model_id"] = "VLIIPro50_22_APPROX_BOP_STAGE5"
        result["scientific_status"] = (
            "MODELO APROXIMADO COM HIPOTESE DE BALANCE OF PLANT"
        )
        return result

    def evaluate_point(self, current_A: float, **kwargs: float) -> pd.Series:
        result = self.evaluate(current_A, **kwargs)
        if len(result) != 1:
            raise RuntimeError("evaluate_point deve produzir exatamente uma linha.")
        return result.iloc[0]

    def curve(self, points: int = 451, **kwargs: float) -> pd.DataFrame:
        if points < 2:
            raise ValueError("points deve ser pelo menos 2.")
        currents = np.linspace(
            self.stack_model.specification.current_min_A,
            self.stack_model.specification.current_max_A,
            int(points),
        )
        return self.evaluate(currents, **kwargs)

    def nominal_balance(self) -> pd.Series:
        """Balanço completo no limite nominal de corrente publicado."""
        return self.evaluate_point(self.stack_model.specification.current_max_A)

    def parameters_table(self) -> pd.DataFrame:
        return pd.DataFrame(record.to_dict() for record in self.parameter_records)


__all__ = ["Equivalent65kWHorizonSystemModel"]
