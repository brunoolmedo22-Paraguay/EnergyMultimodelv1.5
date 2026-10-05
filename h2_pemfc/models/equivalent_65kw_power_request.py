"""Inversão estática potência líquida → corrente para a ETAPA 6.

Este módulo compõe :class:`Equivalent65kWHorizonSystemModel` e resolve a
corrente necessária para uma potência líquida solicitada. Não reimplementa
nenhuma equação eletroquímica e não inclui rampas, estados ou dinâmica temporal.

O modelo continua sendo aproximado: a curva eletroquímica é a calibração
``EQUIVALENT_65KW_HORIZON_CONSTRAINED`` e o balance of plant é a hipótese
agregada da ETAPA 5.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from h2_pemfc.models.equivalent_65kw_system import Equivalent65kWHorizonSystemModel
from h2_pemfc.pemfc_data import horizon_specifications_as_dict


@dataclass(frozen=True)
class Stage6OperatingLimits:
    """Limites estáticos usados na inversão da potência solicitada."""

    system_rated_power_kW: float
    system_peak_power_kW: float
    recommended_min_power_kW: float
    recommended_max_power_kW: float
    branch_grid_points: int = 2001
    monotonic_power_tolerance_kW: float = 1e-10
    root_power_tolerance_kW: float = 1e-8
    root_current_tolerance_A: float = 1e-9

    @classmethod
    def from_project_data(cls) -> "Stage6OperatingLimits":
        values = horizon_specifications_as_dict()
        rated = float(values["system_rated_power_kW"])
        recommended_min = (
            rated * float(values["recommended_output_min_percent"]) / 100.0
        )
        recommended_max = (
            rated * float(values["recommended_output_max_percent"]) / 100.0
        )
        limits = cls(
            system_rated_power_kW=rated,
            system_peak_power_kW=float(values["system_peak_power_kW"]),
            recommended_min_power_kW=recommended_min,
            recommended_max_power_kW=recommended_max,
        )
        limits.validate()
        return limits

    def validate(self) -> None:
        numeric = np.asarray(
            [
                self.system_rated_power_kW,
                self.system_peak_power_kW,
                self.recommended_min_power_kW,
                self.recommended_max_power_kW,
                self.monotonic_power_tolerance_kW,
                self.root_power_tolerance_kW,
                self.root_current_tolerance_A,
            ],
            dtype=float,
        )
        if not np.isfinite(numeric).all():
            raise ValueError("Os limites operacionais da ETAPA 6 devem ser finitos.")
        if self.system_rated_power_kW <= 0.0:
            raise ValueError("A potência nominal deve ser positiva.")
        if self.system_peak_power_kW < self.system_rated_power_kW:
            raise ValueError("A potência de pico não pode ser inferior à nominal.")
        if not (
            0.0
            < self.recommended_min_power_kW
            < self.recommended_max_power_kW
            <= self.system_rated_power_kW
        ):
            raise ValueError("A faixa recomendada deve estar dentro da potência nominal.")
        if self.branch_grid_points < 101:
            raise ValueError("branch_grid_points deve ser pelo menos 101.")
        if (
            self.monotonic_power_tolerance_kW < 0.0
            or self.root_power_tolerance_kW <= 0.0
            or self.root_current_tolerance_A <= 0.0
        ):
            raise ValueError("As tolerâncias da ETAPA 6 devem ser positivas.")


DEFAULT_STAGE6_OPERATING_LIMITS = Stage6OperatingLimits.from_project_data()


@dataclass(frozen=True)
class OperationalBranchDiagnostics:
    """Diagnóstico da rama monotônica usada pelo solucionador."""

    current_min_A: float
    current_max_A: float
    net_power_min_kW: float
    net_power_max_kW: float
    full_curve_monotonic_increasing: bool
    branch_truncated_due_non_monotonicity: bool
    first_non_monotonic_current_A: float | None
    sampled_points_total: int
    sampled_points_branch: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class Equivalent65kWHorizonPowerRequestModel:
    """Modelo estático orientado a uma potência líquida solicitada.

    A corrente é encontrada com ``scipy.optimize.brentq`` exclusivamente na
    rama operacional monotônica identificada dentro de 0–450 A. Solicitações
    inviáveis são saturadas e informadas; correntes fora do domínio e NaN não
    são retornados silenciosamente.
    """

    def __init__(
        self,
        system_model: Equivalent65kWHorizonSystemModel | None = None,
        operating_limits: Stage6OperatingLimits = DEFAULT_STAGE6_OPERATING_LIMITS,
    ) -> None:
        operating_limits.validate()
        self.system_model = system_model or Equivalent65kWHorizonSystemModel()
        self.operating_limits = operating_limits

    @staticmethod
    def _requested_array(
        requested_power_kW: Iterable[float] | float,
    ) -> np.ndarray:
        requested = np.atleast_1d(np.asarray(requested_power_kW, dtype=float))
        if requested.ndim != 1 or requested.size == 0:
            raise ValueError(
                "requested_power_kW deve ser escalar ou vetor unidimensional não vazio."
            )
        if not np.isfinite(requested).all():
            raise ValueError("requested_power_kW deve conter somente valores finitos.")
        if (requested < 0.0).any():
            raise ValueError("requested_power_kW não pode conter valores negativos.")
        return requested

    @staticmethod
    def _validate_bus_voltage(bus_voltage_V: float | None) -> float | None:
        if bus_voltage_V is None:
            return None
        value = float(bus_voltage_V)
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError("bus_voltage_V deve ser positivo e finito quando informado.")
        return value

    def analyze_operational_branch(
        self,
        temperature_K: float | None = None,
        anode_pressure_kPag: float | None = None,
        cathode_pressure_kPag: float | None = None,
        *,
        air_pressure_atm_abs: float | None = None,
        ambient_pressure_kPa: float | None = None,
    ) -> tuple[pd.DataFrame, OperationalBranchDiagnostics]:
        """Amostra a curva e seleciona a rama crescente conectada a 0 A.

        Se a curva líquida deixar de crescer, a rama válida termina no ponto
        imediatamente anterior à primeira queda ou platô numérico. Essa escolha
        evita inverter uma função multivalorada.
        """
        limits = self.operating_limits
        curve = self.system_model.curve(
            points=limits.branch_grid_points,
            temperature_K=temperature_K,
            anode_pressure_kPag=anode_pressure_kPag,
            cathode_pressure_kPag=cathode_pressure_kPag,
            air_pressure_atm_abs=air_pressure_atm_abs,
            ambient_pressure_kPa=ambient_pressure_kPa,
        ).reset_index(drop=True)
        current = curve["current_A"].to_numpy(dtype=float)
        net_power = curve["P_net_kW"].to_numpy(dtype=float)
        if not np.isfinite(current).all() or not np.isfinite(net_power).all():
            raise RuntimeError("A curva estática contém valores não finitos.")
        if len(curve) < 2:
            raise RuntimeError("A curva estática não possui pontos suficientes.")

        delta_power = np.diff(net_power)
        non_increasing = np.flatnonzero(
            delta_power <= limits.monotonic_power_tolerance_kW
        )
        full_monotonic = non_increasing.size == 0
        if full_monotonic:
            branch_end_index = len(curve) - 1
            first_non_monotonic_current = None
        else:
            branch_end_index = int(non_increasing[0])
            first_non_monotonic_current = float(current[branch_end_index + 1])

        if branch_end_index < 1:
            raise RuntimeError(
                "Não foi encontrada uma rama operacional crescente com largura positiva."
            )
        branch = curve.iloc[: branch_end_index + 1].copy().reset_index(drop=True)
        branch_power = branch["P_net_kW"].to_numpy(dtype=float)
        if np.any(np.diff(branch_power) <= limits.monotonic_power_tolerance_kW):
            raise RuntimeError("A rama selecionada não é estritamente crescente.")

        diagnostics = OperationalBranchDiagnostics(
            current_min_A=float(branch["current_A"].iloc[0]),
            current_max_A=float(branch["current_A"].iloc[-1]),
            net_power_min_kW=float(branch["P_net_kW"].iloc[0]),
            net_power_max_kW=float(branch["P_net_kW"].iloc[-1]),
            full_curve_monotonic_increasing=full_monotonic,
            branch_truncated_due_non_monotonicity=not full_monotonic,
            first_non_monotonic_current_A=first_non_monotonic_current,
            sampled_points_total=len(curve),
            sampled_points_branch=len(branch),
        )
        return branch, diagnostics

    def _solve_current_for_target(
        self,
        target_power_kW: float,
        diagnostics: OperationalBranchDiagnostics,
        *,
        temperature_K: float | None,
        anode_pressure_kPag: float | None,
        cathode_pressure_kPag: float | None,
        air_pressure_atm_abs: float | None,
        ambient_pressure_kPa: float | None,
    ) -> tuple[float, str]:
        limits = self.operating_limits
        if target_power_kW <= diagnostics.net_power_min_kW + limits.root_power_tolerance_kW:
            return diagnostics.current_min_A, "BRANCH_LOWER_ENDPOINT"
        if target_power_kW >= diagnostics.net_power_max_kW - limits.root_power_tolerance_kW:
            return diagnostics.current_max_A, "BRANCH_UPPER_ENDPOINT"

        def residual(current_A: float) -> float:
            value = self.system_model.evaluate_point(
                current_A,
                temperature_K=temperature_K,
                anode_pressure_kPag=anode_pressure_kPag,
                cathode_pressure_kPag=cathode_pressure_kPag,
                air_pressure_atm_abs=air_pressure_atm_abs,
                ambient_pressure_kPa=ambient_pressure_kPa,
            )["P_net_kW"]
            value = float(value)
            if not np.isfinite(value):
                raise RuntimeError("O modelo produziu potência líquida não finita.")
            return value - target_power_kW

        lower = diagnostics.current_min_A
        upper = diagnostics.current_max_A
        f_lower = residual(lower)
        f_upper = residual(upper)
        if f_lower > limits.root_power_tolerance_kW or f_upper < -limits.root_power_tolerance_kW:
            raise RuntimeError("A potência alvo não está contida na rama operacional.")
        current = brentq(
            residual,
            lower,
            upper,
            xtol=limits.root_current_tolerance_A,
            rtol=4.0 * np.finfo(float).eps,
            maxiter=100,
        )
        if not np.isfinite(current):
            raise RuntimeError("O solucionador retornou corrente não finita.")
        if current < lower - 1e-9 or current > upper + 1e-9:
            raise RuntimeError("O solucionador retornou corrente fora da rama operacional.")
        return float(current), "BRENTQ_BOUNDED"

    def solve_requested_power(
        self,
        requested_power_kW: Iterable[float] | float,
        temperature_K: float | None = None,
        anode_pressure_kPag: float | None = None,
        cathode_pressure_kPag: float | None = None,
        *,
        air_pressure_atm_abs: float | None = None,
        ambient_pressure_kPa: float | None = None,
        bus_voltage_V: float | None = None,
    ) -> pd.DataFrame:
        """Resolve uma ou várias solicitações estáticas e independentes.

        ``bus_voltage_V`` é aceito e registrado para integração futura. Nesta
        etapa ele não modifica a eficiência constante do DC/DC da ETAPA 5.
        """
        requested = self._requested_array(requested_power_kW)
        bus_voltage = self._validate_bus_voltage(bus_voltage_V)
        _, diagnostics = self.analyze_operational_branch(
            temperature_K=temperature_K,
            anode_pressure_kPag=anode_pressure_kPag,
            cathode_pressure_kPag=cathode_pressure_kPag,
            air_pressure_atm_abs=air_pressure_atm_abs,
            ambient_pressure_kPa=ambient_pressure_kPa,
        )
        limits = self.operating_limits
        records: list[dict[str, object]] = []

        for request in requested:
            request_value = float(request)
            declared_target = min(request_value, limits.system_peak_power_kW)
            physical_target = min(declared_target, diagnostics.net_power_max_kW)

            current, solver_method = self._solve_current_for_target(
                physical_target,
                diagnostics,
                temperature_K=temperature_K,
                anode_pressure_kPag=anode_pressure_kPag,
                cathode_pressure_kPag=cathode_pressure_kPag,
                air_pressure_atm_abs=air_pressure_atm_abs,
                ambient_pressure_kPa=ambient_pressure_kPa,
            )
            system_point = self.system_model.evaluate_point(
                current,
                temperature_K=temperature_K,
                anode_pressure_kPag=anode_pressure_kPag,
                cathode_pressure_kPag=cathode_pressure_kPag,
                air_pressure_atm_abs=air_pressure_atm_abs,
                ambient_pressure_kPa=ambient_pressure_kPa,
            )
            delivered = float(system_point["P_net_kW"])
            if not np.isfinite(delivered):
                raise RuntimeError("A potência entregue calculada não é finita.")
            solver_residual = delivered - physical_target
            if abs(solver_residual) > 5.0 * limits.root_power_tolerance_kW:
                raise RuntimeError(
                    "O solucionador não fechou a potência alvo dentro da tolerância."
                )

            deficit = max(request_value - delivered, 0.0)
            excess = max(delivered - request_value, 0.0)
            limitation_reasons: list[str] = []
            if request_value > limits.system_peak_power_kW + limits.root_power_tolerance_kW:
                limitation_reasons.append("REQUEST_ABOVE_DECLARED_PEAK")
            if declared_target > diagnostics.net_power_max_kW + limits.root_power_tolerance_kW:
                limitation_reasons.append("PHYSICAL_OPERATIONAL_BRANCH_MAX_REACHED")
            if (
                diagnostics.branch_truncated_due_non_monotonicity
                and declared_target > diagnostics.net_power_max_kW
            ):
                limitation_reasons.append("NON_MONOTONIC_CURVE_BRANCH_LIMIT")

            warnings: list[str] = []
            if request_value == 0.0:
                warnings.append("ZERO_POWER_STATIC_POINT_WITHOUT_STATE_MODEL")
            elif delivered < limits.recommended_min_power_kW - limits.root_power_tolerance_kW:
                warnings.append("BELOW_RECOMMENDED_OUTPUT_RANGE")
            elif delivered > limits.recommended_max_power_kW + limits.root_power_tolerance_kW:
                warnings.append("ABOVE_RECOMMENDED_OUTPUT_RANGE")
            if delivered > limits.system_rated_power_kW + limits.root_power_tolerance_kW:
                warnings.append("ABOVE_NOMINAL_POWER")
            if diagnostics.branch_truncated_due_non_monotonicity:
                warnings.append("NON_MONOTONIC_NET_POWER_CURVE_VALID_BRANCH_ONLY")
            if bus_voltage is not None:
                warnings.append("BUS_VOLTAGE_INFORMATIONAL_ONLY_CONSTANT_DCDC_EFFICIENCY")

            within_recommended = (
                limits.recommended_min_power_kW - limits.root_power_tolerance_kW
                <= delivered
                <= limits.recommended_max_power_kW + limits.root_power_tolerance_kW
            )
            prefix: dict[str, object] = {
                "P_FC_requested_kW": request_value,
                "P_target_after_declared_peak_kW": declared_target,
                "P_target_after_physical_branch_kW": physical_target,
                "P_FC_delivered_kW": delivered,
                "P_deficit_kW": deficit,
                "P_excess_kW": excess,
                "limitation_flag": bool(limitation_reasons),
                "limitation_reason": (
                    "NONE" if not limitation_reasons else "|".join(limitation_reasons)
                ),
                "operational_warning_flag": bool(warnings),
                "operational_warning_reason": (
                    "NONE" if not warnings else "|".join(warnings)
                ),
                "within_recommended_output_range": bool(within_recommended),
                "recommended_output_min_kW": limits.recommended_min_power_kW,
                "recommended_output_max_kW": limits.recommended_max_power_kW,
                "system_rated_power_kW": limits.system_rated_power_kW,
                "system_peak_power_kW": limits.system_peak_power_kW,
                "bus_voltage_V": bus_voltage,
                "bus_voltage_used_in_static_solution": False,
                "solver_method": solver_method,
                "solver_residual_kW": solver_residual,
                "operational_branch_current_min_A": diagnostics.current_min_A,
                "operational_branch_current_max_A": diagnostics.current_max_A,
                "operational_branch_power_min_kW": diagnostics.net_power_min_kW,
                "operational_branch_power_max_kW": diagnostics.net_power_max_kW,
                "full_net_power_curve_monotonic_increasing": (
                    diagnostics.full_curve_monotonic_increasing
                ),
                "branch_truncated_due_non_monotonicity": (
                    diagnostics.branch_truncated_due_non_monotonicity
                ),
            }
            payload = prefix | system_point.to_dict()
            payload["power_request_model_id"] = "VLIIPro50_22_APPROX_POWER_REQUEST_STAGE6"
            payload["scientific_status_stage6"] = (
                "INVERSAO ESTATICA DE MODELO APROXIMADO; SEM DINAMICA OU VALIDACAO HORIZON"
            )
            records.append(payload)

        result = pd.DataFrame.from_records(records)
        numeric_required = [
            "P_FC_requested_kW",
            "P_FC_delivered_kW",
            "P_deficit_kW",
            "current_A",
            "current_density_A_cm2",
            "V_cell_V",
            "V_stack_V",
            "P_stack_kW",
            "P_aux_equivalent_kW",
            "P_dc_dc_loss_kW",
            "hydrogen_supplied_kg_h",
            "air_supplied_g_s",
            "net_electrical_efficiency_LHV_percent",
            "P_stack_reaction_heat_kW",
            "solver_residual_kW",
        ]
        if not np.isfinite(result[numeric_required].to_numpy(dtype=float)).all():
            raise RuntimeError("A saída da ETAPA 6 contém valores numéricos não finitos.")
        current_min = self.system_model.stack_model.specification.current_min_A
        current_max = self.system_model.stack_model.specification.current_max_A
        if (
            (result["current_A"] < current_min - 1e-9).any()
            or (result["current_A"] > current_max + 1e-9).any()
        ):
            raise RuntimeError("A saída da ETAPA 6 contém corrente fora de 0–450 A.")
        return result

    def solve_point(self, requested_power_kW: float, **kwargs: float) -> pd.Series:
        result = self.solve_requested_power(requested_power_kW, **kwargs)
        if len(result) != 1:
            raise RuntimeError("solve_point deve produzir exatamente uma linha.")
        return result.iloc[0]

    def operating_limits_table(self) -> pd.DataFrame:
        limits = self.operating_limits
        return pd.DataFrame(
            [
                {
                    "parameter_id": "system_rated_power_kW",
                    "value": limits.system_rated_power_kW,
                    "unit": "kW",
                    "classification": "MANUAL_HORIZON",
                },
                {
                    "parameter_id": "system_peak_power_kW",
                    "value": limits.system_peak_power_kW,
                    "unit": "kW",
                    "classification": "MANUAL_HORIZON",
                },
                {
                    "parameter_id": "recommended_output_min_kW",
                    "value": limits.recommended_min_power_kW,
                    "unit": "kW",
                    "classification": "DERIVADO",
                },
                {
                    "parameter_id": "recommended_output_max_kW",
                    "value": limits.recommended_max_power_kW,
                    "unit": "kW",
                    "classification": "DERIVADO",
                },
                {
                    "parameter_id": "branch_grid_points",
                    "value": float(limits.branch_grid_points),
                    "unit": "points",
                    "classification": "HIPOTESE_NUMERICA",
                },
            ]
        )


__all__ = [
    "DEFAULT_STAGE6_OPERATING_LIMITS",
    "Equivalent65kWHorizonPowerRequestModel",
    "OperationalBranchDiagnostics",
    "Stage6OperatingLimits",
]
