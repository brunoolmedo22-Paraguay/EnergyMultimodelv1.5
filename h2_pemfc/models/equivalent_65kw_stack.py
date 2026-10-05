"""Modelo estático do stack PEMFC equivalente restringido pelo Horizon.

Este módulo é uma camada de composição sobre :class:`models.pemfc_model.PEMFCModel`.
Ele converte corrente total em densidade de corrente, aplica as condições de
pressão e organiza os resultados do stack. Nenhuma equação eletroquímica é
reimplementada aqui.

O perfil representa uma curva equivalente de 65 kW restringida pelo ponto
nominal do Horizon VLIIPro50-22. Não é uma validação experimental do equipamento
Horizon e não inclui balance of plant, DC/DC, potência líquida ou dinâmica.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from h2_pemfc.models.pemfc_model import PEMFCModel
from h2_pemfc.pemfc_config import (
    EQUIVALENT_65KW_HORIZON_CONSTRAINED,
    PEMFCProfile,
)
from h2_pemfc.pemfc_data import horizon_specifications_as_dict


@dataclass(frozen=True)
class StaticStackSpecification:
    """Limites e referências publicados ou assumidos para a ETAPA 4."""

    number_of_cells: int
    active_area_cm2: float
    current_min_A: float
    current_max_A: float
    voltage_min_V: float
    voltage_max_V: float
    voltage_nominal_V: float
    rated_power_kW: float
    anode_pressure_nominal_kPag: float
    cathode_pressure_nominal_kPag: float
    calibration_temperature_K: float = 353.15
    ambient_pressure_reference_kPa: float = 101.325

    @classmethod
    def from_project_data(cls) -> "StaticStackSpecification":
        values = horizon_specifications_as_dict()
        return cls(
            number_of_cells=int(values["number_of_cells"]),
            active_area_cm2=float(values["active_area_cm2"]),
            current_min_A=0.0,
            current_max_A=float(values["stack_current_max_A"]),
            voltage_min_V=float(values["stack_voltage_min_V"]),
            voltage_max_V=float(values["stack_voltage_max_V"]),
            voltage_nominal_V=float(values["stack_voltage_nominal_V"]),
            rated_power_kW=float(values["stack_rated_power_kW"]),
            anode_pressure_nominal_kPag=float(values["anode_pressure_nominal_kPag"]),
            cathode_pressure_nominal_kPag=float(values["cathode_pressure_nominal_kPag"]),
        )

    def validate(self) -> None:
        numeric_values = {
            "active_area_cm2": self.active_area_cm2,
            "current_min_A": self.current_min_A,
            "current_max_A": self.current_max_A,
            "voltage_min_V": self.voltage_min_V,
            "voltage_max_V": self.voltage_max_V,
            "voltage_nominal_V": self.voltage_nominal_V,
            "rated_power_kW": self.rated_power_kW,
            "anode_pressure_nominal_kPag": self.anode_pressure_nominal_kPag,
            "cathode_pressure_nominal_kPag": self.cathode_pressure_nominal_kPag,
            "calibration_temperature_K": self.calibration_temperature_K,
            "ambient_pressure_reference_kPa": self.ambient_pressure_reference_kPa,
        }
        if self.number_of_cells <= 0:
            raise ValueError("number_of_cells deve ser positivo.")
        for name, value in numeric_values.items():
            if not np.isfinite(value):
                raise ValueError(f"{name} deve ser finito.")
        if self.active_area_cm2 <= 0.0:
            raise ValueError("active_area_cm2 deve ser positiva.")
        if self.current_min_A < 0.0 or self.current_max_A <= self.current_min_A:
            raise ValueError("Faixa de corrente inválida.")
        if self.voltage_min_V <= 0.0 or self.voltage_max_V <= self.voltage_min_V:
            raise ValueError("Faixa de tensão inválida.")
        if not self.voltage_min_V <= self.voltage_nominal_V <= self.voltage_max_V:
            raise ValueError("A tensão nominal deve estar dentro da faixa publicada.")
        if self.rated_power_kW <= 0.0:
            raise ValueError("rated_power_kW deve ser positiva.")
        if self.anode_pressure_nominal_kPag < 0.0 or self.cathode_pressure_nominal_kPag < 0.0:
            raise ValueError("Pressões manométricas nominais não podem ser negativas.")
        if self.calibration_temperature_K <= 0.0 or self.ambient_pressure_reference_kPa <= 0.0:
            raise ValueError("Temperatura absoluta e pressão ambiente devem ser positivas.")


DEFAULT_STATIC_STACK_SPECIFICATION = StaticStackSpecification.from_project_data()


class Equivalent65kWHorizonStackModel:
    """API estática para o stack aproximado VLSIIPro66-22.

    A classe contém um :class:`PEMFCModel` e delega a ele todas as equações da
    célula. Esta camada apenas resolve geometria, condições operacionais,
    grandezas derivadas e indicadores de limites estáticos.
    """

    def __init__(
        self,
        profile: PEMFCProfile = EQUIVALENT_65KW_HORIZON_CONSTRAINED,
        specification: StaticStackSpecification = DEFAULT_STATIC_STACK_SPECIFICATION,
    ) -> None:
        specification.validate()
        if profile.geometry.N_cells != specification.number_of_cells:
            raise ValueError("O número de células do perfil diverge da especificação da ETAPA 4.")
        if not np.isclose(profile.geometry.A_active_cm2, specification.active_area_cm2):
            raise ValueError("A área ativa do perfil diverge da especificação da ETAPA 4.")
        self.profile = profile
        self.specification = specification
        self.base_model = PEMFCModel(profile.parameters)

    @staticmethod
    def _current_array(current_A: Iterable[float] | float) -> np.ndarray:
        current = np.atleast_1d(np.asarray(current_A, dtype=float))
        if current.ndim != 1:
            raise ValueError("current_A deve ser escalar ou vetor unidimensional.")
        if current.size == 0:
            raise ValueError("current_A não pode ser vazio.")
        if not np.isfinite(current).all():
            raise ValueError("current_A deve conter somente valores finitos.")
        if (current < 0.0).any():
            raise ValueError("current_A não pode conter valores negativos.")
        return current

    def _resolve_conditions(
        self,
        temperature_K: float | None,
        anode_pressure_kPag: float | None,
        cathode_pressure_kPag: float | None,
        air_pressure_atm_abs: float | None,
        ambient_pressure_kPa: float | None,
    ) -> tuple[float, float, float, float, float, float]:
        spec = self.specification
        temperature = spec.calibration_temperature_K if temperature_K is None else float(temperature_K)
        ambient = (
            spec.ambient_pressure_reference_kPa
            if ambient_pressure_kPa is None
            else float(ambient_pressure_kPa)
        )
        anode_gauge = (
            spec.anode_pressure_nominal_kPag
            if anode_pressure_kPag is None
            else float(anode_pressure_kPag)
        )
        if air_pressure_atm_abs is not None and cathode_pressure_kPag is not None:
            raise ValueError(
                "Informe cathode_pressure_kPag ou air_pressure_atm_abs, não ambos."
            )
        if air_pressure_atm_abs is None:
            cathode_gauge = (
                spec.cathode_pressure_nominal_kPag
                if cathode_pressure_kPag is None
                else float(cathode_pressure_kPag)
            )
            air_abs = (ambient + cathode_gauge) / ambient
        else:
            air_abs = float(air_pressure_atm_abs)
            cathode_gauge = ambient * (air_abs - 1.0)

        values = {
            "temperature_K": temperature,
            "ambient_pressure_kPa": ambient,
            "anode_pressure_kPag": anode_gauge,
            "cathode_pressure_kPag": cathode_gauge,
            "air_pressure_atm_abs": air_abs,
        }
        for name, value in values.items():
            if not np.isfinite(value):
                raise ValueError(f"{name} deve ser finito.")
        if temperature <= 0.0 or ambient <= 0.0 or air_abs <= 0.0:
            raise ValueError("Temperatura absoluta e pressões absolutas devem ser positivas.")
        if anode_gauge < 0.0 or cathode_gauge < 0.0:
            raise ValueError("Pressões manométricas não podem ser negativas.")

        hydrogen_abs = (ambient + anode_gauge) / ambient
        return temperature, ambient, anode_gauge, cathode_gauge, air_abs, hydrogen_abs

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
        """Avalia um ou vários pontos estáticos do stack.

        Correntes acima de 450 A não são saturadas nesta etapa: são calculadas e
        marcadas pelos indicadores de limite. Correntes negativas são rejeitadas.
        """
        current = self._current_array(current_A)
        (
            temperature,
            ambient,
            anode_gauge,
            cathode_gauge,
            air_abs,
            hydrogen_abs,
        ) = self._resolve_conditions(
            temperature_K,
            anode_pressure_kPag,
            cathode_pressure_kPag,
            air_pressure_atm_abs,
            ambient_pressure_kPa,
        )

        # A pressão de H2 é uma condição operacional; todas as equações continuam
        # centralizadas em PEMFCModel.
        operating_parameters = self.profile.parameters.copy_with(p_h2=hydrogen_abs)
        electrochemical_model = PEMFCModel(operating_parameters)
        current_density = current / self.specification.active_area_cm2
        raw = electrochemical_model.evaluate(current_density, temperature, air_abs).copy()

        raw["P_stack_kW"] = raw["P_stack_W"] / 1000.0
        nernst = raw["E_nernst_V"].to_numpy(dtype=float)
        cell_voltage = raw["V_cell_V"].to_numpy(dtype=float)
        raw["electrochemical_efficiency_percent"] = np.divide(
            100.0 * cell_voltage,
            nernst,
            out=np.zeros_like(cell_voltage),
            where=nernst > 0.0,
        )
        raw.rename(
            columns={"efficiency_percent": "otekon_effective_efficiency_percent"},
            inplace=True,
        )

        spec = self.specification
        raw["current_within_range"] = raw["current_A"].between(
            spec.current_min_A, spec.current_max_A, inclusive="both"
        )
        raw["current_above_max"] = raw["current_A"] > spec.current_max_A
        raw["voltage_within_range"] = raw["V_stack_V"].between(
            spec.voltage_min_V, spec.voltage_max_V, inclusive="both"
        )
        raw["voltage_below_min"] = raw["V_stack_V"] < spec.voltage_min_V
        raw["voltage_above_max"] = raw["V_stack_V"] > spec.voltage_max_V
        raw["power_within_rated"] = raw["P_stack_kW"] <= spec.rated_power_kW
        raw["power_above_rated"] = raw["P_stack_kW"] > spec.rated_power_kW
        raw["within_all_static_limits"] = (
            raw["current_within_range"]
            & raw["voltage_within_range"]
            & raw["power_within_rated"]
        )
        raw["limit_status"] = raw.apply(self._limit_status, axis=1)

        raw["ambient_pressure_kPa"] = ambient
        raw["anode_pressure_kPag"] = anode_gauge
        raw["cathode_pressure_kPag"] = cathode_gauge
        raw["hydrogen_pressure_atm_abs"] = hydrogen_abs
        raw["air_pressure_atm_abs"] = air_abs
        raw["profile_id"] = self.profile.profile_id

        ordered_columns = [
            "current_A",
            "current_density_A_cm2",
            "E_nernst_V",
            "V_act_V",
            "V_ohm_V",
            "V_conc_V",
            "V_cell_V",
            "V_stack_V",
            "P_stack_W",
            "P_stack_kW",
            "electrochemical_efficiency_percent",
            "otekon_effective_efficiency_percent",
            "temperature_K",
            "ambient_pressure_kPa",
            "anode_pressure_kPag",
            "cathode_pressure_kPag",
            "hydrogen_pressure_atm_abs",
            "air_pressure_atm_abs",
            "current_within_range",
            "current_above_max",
            "voltage_within_range",
            "voltage_below_min",
            "voltage_above_max",
            "power_within_rated",
            "power_above_rated",
            "within_all_static_limits",
            "limit_status",
            "profile_id",
        ]
        return raw.loc[:, ordered_columns]

    @staticmethod
    def _limit_status(row: pd.Series) -> str:
        reasons: list[str] = []
        if bool(row["current_above_max"]):
            reasons.append("CURRENT_ABOVE_MAX")
        if bool(row["voltage_below_min"]):
            reasons.append("VOLTAGE_BELOW_MIN")
        if bool(row["voltage_above_max"]):
            reasons.append("VOLTAGE_ABOVE_MAX")
        if bool(row["power_above_rated"]):
            reasons.append("POWER_ABOVE_RATED")
        return "OK" if not reasons else "|".join(reasons)

    def evaluate_point(self, current_A: float, **kwargs: float) -> pd.Series:
        """Atalho escalar para integrações que não necessitam de DataFrame."""
        result = self.evaluate(current_A, **kwargs)
        if len(result) != 1:
            raise RuntimeError("evaluate_point deve produzir exatamente uma linha.")
        return result.iloc[0]

    def curve(self, points: int = 451, **kwargs: float) -> pd.DataFrame:
        """Gera a curva estática dentro da faixa Horizon de 0 a 450 A."""
        if points < 2:
            raise ValueError("points deve ser pelo menos 2.")
        current = np.linspace(
            self.specification.current_min_A,
            self.specification.current_max_A,
            int(points),
        )
        return self.evaluate(current, **kwargs)


__all__ = [
    "DEFAULT_STATIC_STACK_SPECIFICATION",
    "Equivalent65kWHorizonStackModel",
    "StaticStackSpecification",
]
