"""Resposta temporal do sistema PEMFC aproximado — ETAPA 7.

Este módulo compõe o solucionador estático da ETAPA 6 e acrescenta somente:

- uma máquina de estados operacional;
- partida e desligamento temporizados;
- limites de rampa de subida e descida;
- retenção de ordem zero dos comandos do EMS;
- geração de uma malha temporal interna configurável.

Não modifica nem replica as equações eletroquímicas. A resposta estática em cada
instante continua sendo calculada por
:class:`Equivalent65kWHorizonPowerRequestModel`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable

import numpy as np
import pandas as pd

from h2_pemfc.models.equivalent_65kw_power_request import (
    Equivalent65kWHorizonPowerRequestModel,
)
from h2_pemfc.pemfc_data import horizon_specifications_as_dict


class FuelCellOperatingState(str, Enum):
    """Estados discretos do sistema na ETAPA 7."""

    OFF = "OFF"
    STARTUP = "STARTUP"
    IDLE = "IDLE"
    RUN = "RUN"
    SHUTDOWN = "SHUTDOWN"
    FAULT_LIMITED = "FAULT_LIMITED"


class ReferencePolicy(str, Enum):
    """Política aplicada entre timestamps fornecidos pelo EMS."""

    ZERO_ORDER_HOLD = "ZERO_ORDER_HOLD"


@dataclass(frozen=True)
class Stage7DynamicConfiguration:
    """Parâmetros explícitos da resposta temporal preliminar.

    Os limites de rampa são valores do manual. O valor de 10 kW usado como
    referência de ``IDLE`` corresponde ao limite superior publicado (≤10 kW) e,
    portanto, é mantido como hipótese operacional conservadora até que exista
    uma calibração do controlador real.
    """

    internal_time_step_s: float
    ramp_up_kW_s: float
    ramp_down_kW_s: float
    idle_power_kW: float
    warm_startup_time_s: float = 30.0
    cold_startup_time_s: float = 600.0
    cold_temperature_threshold_C: float = 5.0
    normal_shutdown_time_s: float = 60.0
    cold_shutdown_time_s: float = 180.0
    default_ambient_temperature_C: float = 25.0
    default_coolant_inlet_temperature_C: float = 60.0
    default_bus_voltage_V: float = 600.0
    power_tolerance_kW: float = 1e-8
    reference_policy: ReferencePolicy = ReferencePolicy.ZERO_ORDER_HOLD

    @classmethod
    def from_project_data(cls) -> "Stage7DynamicConfiguration":
        values = horizon_specifications_as_dict()
        rated_power = float(values["system_rated_power_kW"])
        config = cls(
            internal_time_step_s=1.0,
            ramp_up_kW_s=float(values["ramp_up_kW_s"]),
            ramp_down_kW_s=float(values["ramp_down_kW_s"]),
            idle_power_kW=0.20 * rated_power,
        )
        config.validate()
        return config

    def validate(self) -> None:
        numeric = np.asarray(
            [
                self.internal_time_step_s,
                self.ramp_up_kW_s,
                self.ramp_down_kW_s,
                self.idle_power_kW,
                self.warm_startup_time_s,
                self.cold_startup_time_s,
                self.cold_temperature_threshold_C,
                self.normal_shutdown_time_s,
                self.cold_shutdown_time_s,
                self.default_ambient_temperature_C,
                self.default_coolant_inlet_temperature_C,
                self.default_bus_voltage_V,
                self.power_tolerance_kW,
            ],
            dtype=float,
        )
        if not np.isfinite(numeric).all():
            raise ValueError("A configuração dinâmica deve conter valores finitos.")
        if self.internal_time_step_s <= 0.0:
            raise ValueError("internal_time_step_s deve ser positivo.")
        if self.ramp_up_kW_s <= 0.0 or self.ramp_down_kW_s <= 0.0:
            raise ValueError("Os limites de rampa devem ser positivos.")
        if self.idle_power_kW <= 0.0:
            raise ValueError("A potência de IDLE deve ser positiva.")
        if self.warm_startup_time_s <= 0.0 or self.cold_startup_time_s <= 0.0:
            raise ValueError("Os tempos de partida devem ser positivos.")
        if self.cold_startup_time_s < self.warm_startup_time_s:
            raise ValueError("A partida fria não pode ser menor que a partida normal.")
        if self.normal_shutdown_time_s <= 0.0 or self.cold_shutdown_time_s <= 0.0:
            raise ValueError("Os tempos de desligamento devem ser positivos.")
        if self.cold_shutdown_time_s < self.normal_shutdown_time_s:
            raise ValueError("O desligamento frio não pode ser menor que o normal.")
        if self.default_bus_voltage_V <= 0.0:
            raise ValueError("A tensão padrão do barramento deve ser positiva.")
        if self.power_tolerance_kW <= 0.0:
            raise ValueError("A tolerância de potência deve ser positiva.")
        if self.reference_policy is not ReferencePolicy.ZERO_ORDER_HOLD:
            raise ValueError("A ETAPA 7 implementa somente retenção de ordem zero.")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reference_policy"] = self.reference_policy.value
        return payload


DEFAULT_STAGE7_DYNAMIC_CONFIGURATION = Stage7DynamicConfiguration.from_project_data()


class Equivalent65kWHorizonDynamicModel:
    """Planta virtual temporal orientada a comandos de potência do EMS.

    A entrada é um perfil temporal com ``timestamp``, ``P_FC_requested_kW`` e
    ``FC_enable``. Colunas ambientais opcionais são mantidas por retenção de
    ordem zero. A temperatura ambiente escolhe o tempo de partida/desligamento;
    a temperatura do refrigerante e a tensão do barramento são registradas, mas
    ainda não alteram o núcleo eletroquímico ou a eficiência constante do DC/DC.
    """

    REQUIRED_COLUMNS = ("timestamp", "P_FC_requested_kW", "FC_enable")
    OPTIONAL_COLUMNS = ("T_ambient_C", "T_coolant_in_C", "V_bus_V")

    def __init__(
        self,
        static_model: Equivalent65kWHorizonPowerRequestModel | None = None,
        configuration: Stage7DynamicConfiguration = DEFAULT_STAGE7_DYNAMIC_CONFIGURATION,
    ) -> None:
        configuration.validate()
        self.static_model = static_model or Equivalent65kWHorizonPowerRequestModel()
        self.configuration = configuration
        _, self._nominal_branch_diagnostics = self.static_model.analyze_operational_branch()
        self._physical_max_power_kW = float(
            self._nominal_branch_diagnostics.net_power_max_kW
        )
        self._declared_peak_power_kW = float(
            self.static_model.operating_limits.system_peak_power_kW
        )
        self._recommended_min_power_kW = float(
            self.static_model.operating_limits.recommended_min_power_kW
        )
        self._recommended_max_power_kW = float(
            self.static_model.operating_limits.recommended_max_power_kW
        )
        if self.configuration.idle_power_kW > self._physical_max_power_kW:
            raise ValueError("A potência de IDLE não pode exceder o máximo físico.")

    @staticmethod
    def _coerce_enable(series: pd.Series) -> pd.Series:
        if series.dtype == bool:
            return series.astype(bool)
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.isna().any() or (~numeric.isin([0, 1])).any():
            raise ValueError("FC_enable deve conter somente 0/1 ou booleanos.")
        return numeric.astype(int).astype(bool)

    def validate_profile(self, profile: pd.DataFrame) -> pd.DataFrame:
        """Valida e normaliza um perfil do EMS sem reordená-lo silenciosamente."""
        if not isinstance(profile, pd.DataFrame):
            raise TypeError("O perfil temporal deve ser um pandas.DataFrame.")
        missing = [column for column in self.REQUIRED_COLUMNS if column not in profile]
        if missing:
            raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(missing)}")
        if profile.empty:
            raise ValueError("O perfil temporal não pode ser vazio.")

        allowed = set(self.REQUIRED_COLUMNS) | set(self.OPTIONAL_COLUMNS)
        unknown = [column for column in profile.columns if column not in allowed]
        if unknown:
            raise ValueError(
                "Colunas não reconhecidas na ETAPA 7: " + ", ".join(unknown)
            )

        normalized = profile.copy()
        normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], errors="coerce", format="mixed")
        if normalized["timestamp"].isna().any():
            raise ValueError("timestamp contém valores inválidos.")
        if normalized["timestamp"].duplicated().any():
            raise ValueError("timestamp não pode conter duplicatas.")
        if not normalized["timestamp"].is_monotonic_increasing:
            raise ValueError("timestamp deve estar em ordem estritamente crescente.")

        requested = pd.to_numeric(normalized["P_FC_requested_kW"], errors="coerce")
        if requested.isna().any() or not np.isfinite(requested.to_numpy(dtype=float)).all():
            raise ValueError("P_FC_requested_kW deve conter valores finitos.")
        if (requested < 0.0).any():
            raise ValueError("P_FC_requested_kW não pode conter valores negativos.")
        normalized["P_FC_requested_kW"] = requested.astype(float)
        normalized["FC_enable"] = self._coerce_enable(normalized["FC_enable"])

        defaults = {
            "T_ambient_C": self.configuration.default_ambient_temperature_C,
            "T_coolant_in_C": self.configuration.default_coolant_inlet_temperature_C,
            "V_bus_V": self.configuration.default_bus_voltage_V,
        }
        for column, default in defaults.items():
            if column not in normalized:
                normalized[column] = float(default)
            else:
                values = pd.to_numeric(normalized[column], errors="coerce")
                values = values.ffill().fillna(float(default))
                if not np.isfinite(values.to_numpy(dtype=float)).all():
                    raise ValueError(f"{column} deve conter valores finitos.")
                normalized[column] = values.astype(float)

        if (normalized["V_bus_V"] <= 0.0).any():
            raise ValueError("V_bus_V deve ser positivo.")
        return normalized.reset_index(drop=True)

    def _build_internal_timeline(
        self, profile: pd.DataFrame, internal_time_step_s: float
    ) -> pd.DataFrame:
        step = float(internal_time_step_s)
        if not np.isfinite(step) or step <= 0.0:
            raise ValueError("internal_time_step_s deve ser positivo e finito.")

        start = profile["timestamp"].iloc[0]
        end = profile["timestamp"].iloc[-1]
        if start == end:
            timeline = pd.DatetimeIndex([start])
        else:
            regular = pd.date_range(
                start=start,
                end=end,
                freq=pd.to_timedelta(step, unit="s"),
            )
            # A união garante que mudanças em timestamps irregulares sejam aplicadas
            # exatamente no instante fornecido, sem criar intervalos maiores que o passo.
            timeline = regular.union(pd.DatetimeIndex(profile["timestamp"])).sort_values()

        commands = pd.DataFrame({"timestamp": timeline})
        mapped = pd.merge_asof(
            commands,
            profile,
            on="timestamp",
            direction="backward",
            allow_exact_matches=True,
        )
        if mapped[list(self.REQUIRED_COLUMNS[1:])].isna().any().any():
            raise RuntimeError("Falha ao aplicar retenção de ordem zero ao perfil.")
        mapped["source_timestamp"] = pd.merge_asof(
            commands,
            profile[["timestamp"]].rename(columns={"timestamp": "source_timestamp"}),
            left_on="timestamp",
            right_on="source_timestamp",
            direction="backward",
            allow_exact_matches=True,
        )["source_timestamp"]
        return mapped

    def _startup_duration_s(self, ambient_temperature_C: float) -> float:
        if ambient_temperature_C > self.configuration.cold_temperature_threshold_C:
            return self.configuration.warm_startup_time_s
        return self.configuration.cold_startup_time_s

    def _shutdown_duration_s(self, ambient_temperature_C: float) -> float:
        if ambient_temperature_C >= self.configuration.cold_temperature_threshold_C:
            return self.configuration.normal_shutdown_time_s
        return self.configuration.cold_shutdown_time_s

    def _apply_ramp(
        self,
        previous_power_kW: float,
        desired_power_kW: float,
        elapsed_s: float,
    ) -> tuple[float, bool, str]:
        if elapsed_s <= 0.0:
            return float(previous_power_kW), (
                abs(desired_power_kW - previous_power_kW)
                > self.configuration.power_tolerance_kW
            ), "INITIAL_CONDITION" if desired_power_kW != previous_power_kW else "NONE"
        delta = desired_power_kW - previous_power_kW
        maximum_up = self.configuration.ramp_up_kW_s * elapsed_s
        maximum_down = self.configuration.ramp_down_kW_s * elapsed_s
        if delta > maximum_up + self.configuration.power_tolerance_kW:
            return previous_power_kW + maximum_up, True, "RAMP_UP_LIMIT"
        if delta < -maximum_down - self.configuration.power_tolerance_kW:
            return max(previous_power_kW - maximum_down, 0.0), True, "RAMP_DOWN_LIMIT"
        return float(desired_power_kW), False, "NONE"

    @staticmethod
    def _join_reasons(reasons: Iterable[str]) -> str:
        filtered = [reason for reason in reasons if reason and reason != "NONE"]
        return "NONE" if not filtered else "|".join(dict.fromkeys(filtered))

    def _simulate_states(self, commands: pd.DataFrame) -> pd.DataFrame:
        cfg = self.configuration
        state = FuelCellOperatingState.OFF
        previous_power = 0.0
        startup_elapsed_s = 0.0
        shutdown_elapsed_s = 0.0
        active_startup_duration_s = cfg.warm_startup_time_s
        active_shutdown_duration_s = cfg.normal_shutdown_time_s
        records: list[dict[str, object]] = []
        previous_timestamp: pd.Timestamp | None = None

        for row in commands.itertuples(index=False):
            timestamp = pd.Timestamp(row.timestamp)
            elapsed_s = (
                0.0
                if previous_timestamp is None
                else float((timestamp - previous_timestamp).total_seconds())
            )
            if elapsed_s < 0.0:
                raise RuntimeError("A malha interna ficou fora de ordem.")

            request = float(row.P_FC_requested_kW)
            enabled = bool(row.FC_enable)
            ambient = float(row.T_ambient_C)
            saturation_reasons: list[str] = []
            state_reasons: list[str] = []

            request_after_declared_peak = min(request, self._declared_peak_power_kW)
            request_after_physical_limit = min(
                request_after_declared_peak, self._physical_max_power_kW
            )
            if request > self._declared_peak_power_kW + cfg.power_tolerance_kW:
                saturation_reasons.append("REQUEST_ABOVE_DECLARED_PEAK")
            if request_after_declared_peak > self._physical_max_power_kW + cfg.power_tolerance_kW:
                saturation_reasons.append("PHYSICAL_OPERATIONAL_BRANCH_MAX_REACHED")

            # Uma sequência de desligamento iniciada não é interrompida na ETAPA 7.
            if state is FuelCellOperatingState.SHUTDOWN:
                shutdown_elapsed_s += elapsed_s
                desired_reference = 0.0
                state_reasons.append("SHUTDOWN_SEQUENCE")
                if (
                    shutdown_elapsed_s >= active_shutdown_duration_s
                    and previous_power <= cfg.power_tolerance_kW
                ):
                    state = FuelCellOperatingState.OFF
                    desired_reference = 0.0
                    shutdown_elapsed_s = active_shutdown_duration_s
            elif not enabled:
                if state is FuelCellOperatingState.OFF:
                    desired_reference = 0.0
                else:
                    state = FuelCellOperatingState.SHUTDOWN
                    shutdown_elapsed_s = 0.0
                    active_shutdown_duration_s = self._shutdown_duration_s(ambient)
                    desired_reference = 0.0
                    state_reasons.append("SHUTDOWN_SEQUENCE")
            elif state is FuelCellOperatingState.OFF:
                state = FuelCellOperatingState.STARTUP
                startup_elapsed_s = 0.0
                active_startup_duration_s = self._startup_duration_s(ambient)
                desired_reference = 0.0
                state_reasons.append("STARTUP_SEQUENCE")
            elif state is FuelCellOperatingState.STARTUP:
                startup_elapsed_s += elapsed_s
                if startup_elapsed_s >= active_startup_duration_s:
                    startup_elapsed_s = active_startup_duration_s
                    if request <= cfg.idle_power_kW + cfg.power_tolerance_kW:
                        state = FuelCellOperatingState.IDLE
                        desired_reference = cfg.idle_power_kW
                    elif saturation_reasons:
                        state = FuelCellOperatingState.FAULT_LIMITED
                        desired_reference = request_after_physical_limit
                    else:
                        state = FuelCellOperatingState.RUN
                        desired_reference = request_after_physical_limit
                else:
                    desired_reference = cfg.idle_power_kW * (
                        startup_elapsed_s / active_startup_duration_s
                    )
                    state_reasons.append("STARTUP_SEQUENCE")
            else:
                if request <= cfg.idle_power_kW + cfg.power_tolerance_kW:
                    state = FuelCellOperatingState.IDLE
                    desired_reference = cfg.idle_power_kW
                    if request < cfg.idle_power_kW - cfg.power_tolerance_kW:
                        state_reasons.append("IDLE_MINIMUM_ENFORCED")
                elif saturation_reasons:
                    state = FuelCellOperatingState.FAULT_LIMITED
                    desired_reference = request_after_physical_limit
                else:
                    state = FuelCellOperatingState.RUN
                    desired_reference = request_after_physical_limit

            dynamic_target, ramp_flag, ramp_reason = self._apply_ramp(
                previous_power,
                desired_reference,
                elapsed_s,
            )
            if state is FuelCellOperatingState.OFF:
                dynamic_target = 0.0
                ramp_flag = False
                ramp_reason = "NONE"
            dynamic_target = min(max(dynamic_target, 0.0), self._physical_max_power_kW)

            within_recommended = (
                self._recommended_min_power_kW - cfg.power_tolerance_kW
                <= dynamic_target
                <= self._recommended_max_power_kW + cfg.power_tolerance_kW
            )
            limitation_reasons = saturation_reasons + state_reasons
            if ramp_flag:
                limitation_reasons.append(ramp_reason)

            records.append(
                {
                    "timestamp": timestamp,
                    "source_timestamp": row.source_timestamp,
                    "P_FC_requested_kW": request,
                    "P_reference_after_limits_kW": float(desired_reference),
                    "P_dynamic_target_kW": float(dynamic_target),
                    "FC_enable": enabled,
                    "T_ambient_C": ambient,
                    "T_coolant_in_C": float(row.T_coolant_in_C),
                    "V_bus_V": float(row.V_bus_V),
                    "state": state.value,
                    "startup_flag": state is FuelCellOperatingState.STARTUP,
                    "ramp_limitation_flag": bool(ramp_flag),
                    "ramp_limitation_reason": ramp_reason,
                    "saturation_flag": bool(saturation_reasons),
                    "saturation_reason": self._join_reasons(saturation_reasons),
                    "recommended_region_flag": bool(within_recommended),
                    "limitation_flag": bool(limitation_reasons),
                    "limitation_reason": self._join_reasons(limitation_reasons),
                    "startup_elapsed_s": float(startup_elapsed_s),
                    "startup_duration_s": float(active_startup_duration_s),
                    "shutdown_elapsed_s": float(shutdown_elapsed_s),
                    "shutdown_duration_s": float(active_shutdown_duration_s),
                    "internal_elapsed_s": elapsed_s,
                }
            )
            previous_power = float(dynamic_target)
            previous_timestamp = timestamp

        return pd.DataFrame.from_records(records)

    def simulate_profile(
        self,
        profile: pd.DataFrame,
        *,
        internal_time_step_s: float | None = None,
    ) -> pd.DataFrame:
        """Simula um perfil do EMS em malha interna de até ``time_step`` segundos.

        A referência é mantida por retenção de ordem zero entre timestamps. Os
        timestamps originais são sempre incluídos na malha, mesmo quando não são
        múltiplos inteiros do passo escolhido.
        """
        normalized = self.validate_profile(profile)
        step = (
            self.configuration.internal_time_step_s
            if internal_time_step_s is None
            else float(internal_time_step_s)
        )
        commands = self._build_internal_timeline(normalized, step)
        dynamic = self._simulate_states(commands)

        targets = dynamic["P_dynamic_target_kW"].to_numpy(dtype=float)
        rounded_targets = np.round(targets, decimals=12)
        unique_targets, inverse = np.unique(rounded_targets, return_inverse=True)
        static_unique = self.static_model.solve_requested_power(unique_targets)
        static_response = static_unique.iloc[inverse].reset_index(drop=True)

        result = dynamic.copy()
        result["P_FC_delivered_kW"] = static_response[
            "P_FC_delivered_kW"
        ].to_numpy(dtype=float)
        result["P_deficit_kW"] = np.maximum(
            result["P_FC_requested_kW"].to_numpy(dtype=float)
            - result["P_FC_delivered_kW"].to_numpy(dtype=float),
            0.0,
        )
        result["P_excess_kW"] = np.maximum(
            result["P_FC_delivered_kW"].to_numpy(dtype=float)
            - result["P_FC_requested_kW"].to_numpy(dtype=float),
            0.0,
        )

        passthrough_columns = [
            "current_A",
            "current_density_A_cm2",
            "V_cell_V",
            "V_stack_V",
            "P_stack_kW",
            "P_aux_equivalent_kW",
            "P_dc_dc_loss_kW",
            "hydrogen_supplied_kg_h",
            "air_supplied_g_s",
            "gross_electrical_efficiency_LHV_percent",
            "net_electrical_efficiency_LHV_percent",
            "P_stack_reaction_heat_kW",
            "P_total_rejected_equivalent_kW",
        ]
        for column in passthrough_columns:
            result[column] = static_response[column].to_numpy()

        result["static_solver_limitation_flag"] = static_response[
            "limitation_flag"
        ].to_numpy(dtype=bool)
        result["static_solver_limitation_reason"] = static_response[
            "limitation_reason"
        ].astype(str).to_numpy()
        result["reference_policy"] = self.configuration.reference_policy.value
        result["internal_time_step_configured_s"] = step
        result["dynamic_model_id"] = "VLIIPro50_22_APPROX_DYNAMIC_STAGE7"
        result["scientific_status_stage7"] = (
            "DINAMICA OPERACIONAL PRELIMINAR SOBRE MODELO APROXIMADO; "
            "SEM VALIDACAO TEMPORAL DO HORIZON"
        )

        numeric_required = [
            "P_FC_requested_kW",
            "P_reference_after_limits_kW",
            "P_dynamic_target_kW",
            "P_FC_delivered_kW",
            "P_deficit_kW",
            "current_A",
            "V_stack_V",
            "hydrogen_supplied_kg_h",
        ]
        if not np.isfinite(result[numeric_required].to_numpy(dtype=float)).all():
            raise RuntimeError("A resposta temporal contém valores não finitos.")
        if (result["current_A"] < -1e-9).any() or (result["current_A"] > 450.0 + 1e-9).any():
            raise RuntimeError("A resposta temporal contém corrente fora de 0–450 A.")
        return result

    def dynamic_parameters_table(self) -> pd.DataFrame:
        """Tabela auditável dos valores temporais e sua classificação."""
        cfg = self.configuration
        rows = [
            ("ramp_up_kW_s", cfg.ramp_up_kW_s, "kW/s", "MANUAL_HORIZON", "Tabela 4.2"),
            ("ramp_down_kW_s", cfg.ramp_down_kW_s, "kW/s", "MANUAL_HORIZON", "Tabela 4.2"),
            ("warm_startup_time_s", cfg.warm_startup_time_s, "s", "MANUAL_HORIZON", "Partida até IDLE, T ambiente > 5 °C"),
            ("cold_startup_time_s", cfg.cold_startup_time_s, "s", "MANUAL_HORIZON", "Partida a -30 °C; usado como limite configurável"),
            ("normal_shutdown_time_s", cfg.normal_shutdown_time_s, "s", "MANUAL_HORIZON", "Desligamento em temperatura normal"),
            ("cold_shutdown_time_s", cfg.cold_shutdown_time_s, "s", "MANUAL_HORIZON", "Desligamento em baixa temperatura"),
            ("idle_power_kW", cfg.idle_power_kW, "kW", "HIPOTESE", "Adota o limite superior publicado de ≤10 kW"),
            ("internal_time_step_s", cfg.internal_time_step_s, "s", "HIPOTESE_NUMERICA", "Passo interno padrão"),
            ("reference_policy", cfg.reference_policy.value, "-", "HIPOTESE_NUMERICA", "Retenção de ordem zero"),
            ("default_ambient_temperature_C", cfg.default_ambient_temperature_C, "°C", "MANUAL_HORIZON", "Condição padrão do manual"),
            ("default_coolant_inlet_temperature_C", cfg.default_coolant_inlet_temperature_C, "°C", "HIPOTESE", "Somente registrada na ETAPA 7"),
            ("default_bus_voltage_V", cfg.default_bus_voltage_V, "V", "HIPOTESE", "Uma das plataformas nominais publicadas; informativa"),
        ]
        return pd.DataFrame(
            rows,
            columns=["parameter_id", "value", "unit", "classification", "notes"],
        )


__all__ = [
    "DEFAULT_STAGE7_DYNAMIC_CONFIGURATION",
    "Equivalent65kWHorizonDynamicModel",
    "FuelCellOperatingState",
    "ReferencePolicy",
    "Stage7DynamicConfiguration",
]
