"""Única implementação matemática da plataforma.

Todas as páginas, gráficos, exportações, testes e scripts de calibração usam
esta classe. Não há modelo paralelo em app.py ou nos módulos de visualização.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from h2_pemfc.pemfc_config import DEFAULT_PARAMS, PEMFCParameters


class PEMFCModel:
    """Modelo semiempírico reconstruído de Altıntaş e Ertan (OTEKON 2024)."""

    def __init__(self, params: PEMFCParameters = DEFAULT_PARAMS) -> None:
        self.params = params

    @staticmethod
    def _array(value) -> np.ndarray:
        return np.asarray(value, dtype=float)

    def oxygen_partial_pressure(self, air_pressure_atm: float) -> float:
        return self.params.oxygen_fraction_air * float(air_pressure_atm)

    def nernst_voltage(self, temperature_K: float, air_pressure_atm: float) -> float:
        """Eq. (3): potencial reversível por célula."""
        p = self.params
        p_o2 = self.oxygen_partial_pressure(air_pressure_atm)
        numerator = p.p_h2 * np.sqrt(p_o2)
        denominator = p.p_h2o * np.sqrt(float(air_pressure_atm))
        return float(
            p.E0
            - 0.85e-3 * (temperature_K - p.T_ref)
            + (p.R * temperature_K) / (2.0 * p.F)
            * np.log(numerator / denominator)
        )

    def oxygen_concentration(self, temperature_K: float, air_pressure_atm: float) -> float:
        """Eq. (5): concentração de oxigênio na interface catalítica."""
        p_o2 = self.oxygen_partial_pressure(air_pressure_atm)
        return float(p_o2 / (5.08e6 * np.exp(-498.0 / temperature_K)))

    def activation_overpotential(
        self,
        current_density_A_cm2,
        temperature_K: float,
        air_pressure_atm: float,
    ) -> np.ndarray:
        """Eq. (4) e Eq. (6), com coeficientes efetivos identificados."""
        p = self.params
        j = self._array(current_density_A_cm2)
        j_safe = np.maximum(j, p.current_density_floor_A_cm2)
        i_mA_cm2 = 1000.0 * j_safe
        c_o2 = self.oxygen_concentration(temperature_K, air_pressure_atm)
        e_act = (
            p.xi1
            + p.xi2 * temperature_K
            + p.xi3 * temperature_K * np.log(i_mA_cm2)
            + p.xi4 * temperature_K * np.log(c_o2)
        )
        return np.maximum(-e_act, 0.0)

    def effective_proton_concentration(self, temperature_K: float) -> float:
        """Concentração efetiva que fecha a cadeia Eq. (10)-(12).

        A Eq. (11) não fornece alpha_H+ nem a escala dimensional do termo 1.
        A dependência térmica abaixo é a interpretação mais provável compatível
        com os resultados publicados e com o R_mem identificado.
        """
        p = self.params
        exponent = 1.0 - p.R_mem_temperature_exponent
        return float(
            p.proton_concentration_ref_mol_cm3
            * (temperature_K / p.T_ref) ** exponent
        )

    def membrane_conductivity(self, temperature_K: float) -> float:
        """Eq. (12): sigma = F² D_H C_H/(R T)."""
        p = self.params
        c_h = self.effective_proton_concentration(temperature_K)
        return float((p.F**2 / (p.R * temperature_K)) * p.D_H * c_h)

    def membrane_resistance(self, temperature_K: float) -> float:
        """Eq. (10): R_mem = t_m/sigma, em Ω.cm²."""
        return float(self.params.t_m / self.membrane_conductivity(temperature_K))

    def ohmic_overpotential(self, current_density_A_cm2, temperature_K: float) -> np.ndarray:
        """Eq. (9): V_ohm = j R_mem."""
        return self._array(current_density_A_cm2) * self.membrane_resistance(temperature_K)

    def concentration_coefficient(self, temperature_K: float) -> float:
        p = self.params
        return float(
            p.concentration_a_ref_V
            + p.concentration_a_temperature_V_K * (temperature_K - p.T_ref)
        )

    def concentration_overpotential(self, current_density_A_cm2, temperature_K: float) -> np.ndarray:
        """Eq. (13), com coeficientes efetivos inferidos."""
        p = self.params
        j = self._array(current_density_A_cm2)
        a = max(self.concentration_coefficient(temperature_K), 0.0)
        return a * np.exp(p.concentration_b_cm2_A * j)

    def losses(self, current_density_A_cm2, temperature_K: float, air_pressure_atm: float) -> dict[str, np.ndarray]:
        j = self._array(current_density_A_cm2)
        return {
            "V_act": self.activation_overpotential(j, temperature_K, air_pressure_atm),
            "V_ohm": self.ohmic_overpotential(j, temperature_K),
            "V_conc": self.concentration_overpotential(j, temperature_K),
        }

    def cell_voltage(self, current_density_A_cm2, temperature_K: float, air_pressure_atm: float) -> np.ndarray:
        """Eq. (2): V_cell = E - V_act - V_ohm - V_conc."""
        j = self._array(current_density_A_cm2)
        loss = self.losses(j, temperature_K, air_pressure_atm)
        voltage = (
            self.nernst_voltage(temperature_K, air_pressure_atm)
            - loss["V_act"]
            - loss["V_ohm"]
            - loss["V_conc"]
        )
        return np.maximum(voltage, 0.0)

    def stack_voltage(self, current_density_A_cm2, temperature_K: float, air_pressure_atm: float) -> np.ndarray:
        return self.params.N_cells * self.cell_voltage(current_density_A_cm2, temperature_K, air_pressure_atm)

    def total_current(self, current_density_A_cm2) -> np.ndarray:
        return self._array(current_density_A_cm2) * self.params.A_active_cm2

    def stack_power(self, current_density_A_cm2, temperature_K: float, air_pressure_atm: float) -> np.ndarray:
        """P_stack = N V_cell (j A_active)."""
        j = self._array(current_density_A_cm2)
        return self.stack_voltage(j, temperature_K, air_pressure_atm) * self.total_current(j)

    def efficiency_percent(self, current_density_A_cm2, temperature_K: float, air_pressure_atm: float) -> np.ndarray:
        """Definição inferida da Figura 3: eta = U_f V_cell/E0."""
        v = self.cell_voltage(current_density_A_cm2, temperature_K, air_pressure_atm)
        return 100.0 * self.params.fuel_utilization * v / self.params.E0

    def evaluate(self, current_density_A_cm2, temperature_K: float, air_pressure_atm: float) -> pd.DataFrame:
        j = self._array(current_density_A_cm2)
        loss = self.losses(j, temperature_K, air_pressure_atm)
        v_cell = self.cell_voltage(j, temperature_K, air_pressure_atm)
        return pd.DataFrame({
            "current_density_A_cm2": j,
            "current_A": self.total_current(j),
            "E_nernst_V": np.full_like(j, self.nernst_voltage(temperature_K, air_pressure_atm)),
            "V_act_V": loss["V_act"],
            "V_ohm_V": loss["V_ohm"],
            "V_conc_V": loss["V_conc"],
            "V_cell_V": v_cell,
            "V_stack_V": self.params.N_cells * v_cell,
            "P_stack_W": self.stack_power(j, temperature_K, air_pressure_atm),
            "efficiency_percent": self.efficiency_percent(j, temperature_K, air_pressure_atm),
            "temperature_K": np.full_like(j, temperature_K),
            "air_pressure_atm": np.full_like(j, air_pressure_atm),
        })

    def figure3_data(self, points: int = 240) -> dict[str, pd.DataFrame]:
        """Quatro conjuntos de dados necessários para reproduzir a Figura 3."""
        j = np.linspace(0.0, 1.0, points)
        low = self.evaluate(j, 298.15, 5.0)
        high = self.evaluate(j, 373.15, 5.0)
        p1 = self.evaluate(j, self.params.pressure_temperature_K, 1.0)
        p5 = self.evaluate(j, self.params.pressure_temperature_K, 5.0)
        return {"T_298": low, "T_373": high, "P_1": p1, "P_5": p5}
