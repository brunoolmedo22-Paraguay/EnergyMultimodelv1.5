"""Configuração rastreável do balance of plant preliminar da ETAPA 5.

Os coeficientes usados pelos modelos auxiliares ficam centralizados neste
módulo. Cada valor exportável recebe uma classificação científica explícita:
valor do manual, resultado derivado, parâmetro calibrado nesta etapa ou
hipótese de modelagem.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import numpy as np

from h2_pemfc.pemfc_data import horizon_specifications_as_dict


class ModelParameterClassification(str, Enum):
    """Classes de rastreabilidade específicas do modelo da ETAPA 5."""

    MANUAL_HORIZON = "MANUAL_HORIZON"
    DERIVADO = "DERIVADO"
    CALIBRADO_ETAPA5 = "CALIBRADO_ETAPA5"
    HIPOTESE = "HIPOTESE"


@dataclass(frozen=True)
class ParameterRecord:
    """Registro longo e auditável de um parâmetro de modelagem."""

    parameter_id: str
    display_name: str
    value: float
    unit: str
    classification: ModelParameterClassification
    source: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["classification"] = self.classification.value
        return payload


@dataclass(frozen=True)
class DCDCConfig:
    """Conversor DC/DC representado por eficiência constante preliminar."""

    efficiency: float = 0.97
    maximum_efficiency: float = 0.97

    def validate(self) -> None:
        if not np.isfinite(self.efficiency) or not np.isfinite(self.maximum_efficiency):
            raise ValueError("Eficiências do DC/DC devem ser finitas.")
        if not 0.0 < self.efficiency <= 1.0:
            raise ValueError("A eficiência operacional do DC/DC deve estar em (0, 1].")
        if not 0.0 < self.maximum_efficiency <= 1.0:
            raise ValueError("A eficiência máxima do DC/DC deve estar em (0, 1].")
        if self.efficiency > self.maximum_efficiency + 1e-12:
            raise ValueError("A eficiência operacional não pode superar a máxima publicada.")


@dataclass(frozen=True)
class AuxiliaryPowerConfig:
    """Parâmetros do consumo auxiliar agregado e equivalente.

    A lei usada é uma potência contínua da fração de carga bruta. O valor
    nominal é calibrado exclusivamente para fechar o balanço de 50 kW líquidos
    no ponto nominal calculado pelo stack da ETAPA 4.
    """

    reference_gross_power_kW: float
    nominal_auxiliary_power_kW: float
    load_exponent: float = 1.35
    target_net_power_kW: float = 50.0

    @classmethod
    def calibrated_from_nominal_balance(
        cls,
        *,
        reference_gross_power_kW: float,
        dc_dc_efficiency: float,
        target_net_power_kW: float,
        load_exponent: float = 1.35,
    ) -> "AuxiliaryPowerConfig":
        values = np.asarray(
            [reference_gross_power_kW, dc_dc_efficiency, target_net_power_kW, load_exponent],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ValueError("Dados da calibração auxiliar devem ser finitos.")
        nominal_auxiliary = dc_dc_efficiency * reference_gross_power_kW - target_net_power_kW
        config = cls(
            reference_gross_power_kW=float(reference_gross_power_kW),
            nominal_auxiliary_power_kW=float(nominal_auxiliary),
            load_exponent=float(load_exponent),
            target_net_power_kW=float(target_net_power_kW),
        )
        config.validate()
        return config

    def validate(self) -> None:
        values = np.asarray(
            [
                self.reference_gross_power_kW,
                self.nominal_auxiliary_power_kW,
                self.load_exponent,
                self.target_net_power_kW,
            ],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ValueError("Parâmetros auxiliares devem ser finitos.")
        if self.reference_gross_power_kW <= 0.0:
            raise ValueError("A potência bruta de referência deve ser positiva.")
        if self.nominal_auxiliary_power_kW < 0.0:
            raise ValueError("A potência auxiliar nominal não pode ser negativa.")
        if self.load_exponent < 1.0:
            raise ValueError(
                "O expoente auxiliar deve ser pelo menos 1 para manter a hipótese "
                "preliminar crescente sem penalização excessiva em baixa carga."
            )
        if self.target_net_power_kW <= 0.0:
            raise ValueError("A potência líquida alvo deve ser positiva.")


@dataclass(frozen=True)
class HydrogenConfig:
    """Constantes e limites usados no balanço de hidrogênio."""

    faraday_constant_C_mol: float = 96485.0
    hydrogen_molar_mass_kg_mol: float = 2.01588e-3
    utilization: float = 0.97
    utilization_manual_minimum: float = 0.97
    maximum_consumption_kg_h: float = 4.8
    lower_heating_value_kWh_kg: float = 33.33

    def validate(self) -> None:
        values = np.asarray(list(asdict(self).values()), dtype=float)
        if not np.isfinite(values).all() or (values <= 0.0).any():
            raise ValueError("Parâmetros de hidrogênio devem ser positivos e finitos.")
        if self.utilization > 1.0 or self.utilization_manual_minimum > 1.0:
            raise ValueError("Utilização de hidrogênio não pode superar 1.")
        if self.utilization < self.utilization_manual_minimum - 1e-12:
            raise ValueError("A utilização adotada não pode ser inferior ao limite do manual.")


@dataclass(frozen=True)
class AirConfig:
    """Parâmetros da estimativa estequiométrica de oxigênio e ar seco."""

    oxygen_molar_mass_kg_mol: float = 31.998e-3
    oxygen_mass_fraction_dry_air: float = 0.232
    lambda_air: float = 2.0
    maximum_air_flow_g_s: float = 80.0

    def validate(self) -> None:
        values = np.asarray(list(asdict(self).values()), dtype=float)
        if not np.isfinite(values).all() or (values <= 0.0).any():
            raise ValueError("Parâmetros do ar devem ser positivos e finitos.")
        if self.oxygen_mass_fraction_dry_air >= 1.0:
            raise ValueError("A fração mássica de oxigênio deve ser menor que 1.")
        if self.lambda_air < 1.0:
            raise ValueError("lambda_air deve ser pelo menos estequiométrico (>= 1).")


@dataclass(frozen=True)
class HeatConfig:
    """Parâmetros do balanço térmico energético preliminar."""

    maximum_stack_heat_dissipation_kW: float = 70.0

    def validate(self) -> None:
        if (
            not np.isfinite(self.maximum_stack_heat_dissipation_kW)
            or self.maximum_stack_heat_dissipation_kW <= 0.0
        ):
            raise ValueError("O limite de dissipação térmica deve ser positivo e finito.")


@dataclass(frozen=True)
class Stage5BaseConfiguration:
    """Configuração dos submodelos que não dependem da curva do stack."""

    dc_dc: DCDCConfig
    hydrogen: HydrogenConfig
    air: AirConfig
    heat: HeatConfig
    system_rated_power_kW: float
    stack_manual_rated_power_kW: float

    @classmethod
    def from_project_data(cls) -> "Stage5BaseConfiguration":
        values = horizon_specifications_as_dict()
        config = cls(
            dc_dc=DCDCConfig(
                efficiency=float(values["dc_dc_efficiency_max_percent"]) / 100.0,
                maximum_efficiency=float(values["dc_dc_efficiency_max_percent"]) / 100.0,
            ),
            hydrogen=HydrogenConfig(
                utilization=float(values["hydrogen_utilization_min_percent"]) / 100.0,
                utilization_manual_minimum=float(
                    values["hydrogen_utilization_min_percent"]
                )
                / 100.0,
                maximum_consumption_kg_h=float(
                    values["hydrogen_consumption_max_kg_h"]
                ),
            ),
            air=AirConfig(
                maximum_air_flow_g_s=float(values["air_consumption_max_g_s"]),
            ),
            heat=HeatConfig(
                maximum_stack_heat_dissipation_kW=float(
                    values["heat_dissipation_rated_max_kW"]
                )
            ),
            system_rated_power_kW=float(values["system_rated_power_kW"]),
            stack_manual_rated_power_kW=float(values["stack_rated_power_kW"]),
        )
        config.validate()
        return config

    def validate(self) -> None:
        self.dc_dc.validate()
        self.hydrogen.validate()
        self.air.validate()
        self.heat.validate()
        if (
            not np.isfinite(self.system_rated_power_kW)
            or self.system_rated_power_kW <= 0.0
        ):
            raise ValueError("A potência nominal do sistema deve ser positiva e finita.")
        if (
            not np.isfinite(self.stack_manual_rated_power_kW)
            or self.stack_manual_rated_power_kW <= 0.0
        ):
            raise ValueError("A potência nominal publicada do stack deve ser positiva e finita.")


DEFAULT_STAGE5_BASE_CONFIGURATION = Stage5BaseConfiguration.from_project_data()


def build_parameter_records(
    base: Stage5BaseConfiguration,
    auxiliary: AuxiliaryPowerConfig,
) -> tuple[ParameterRecord, ...]:
    """Produz a tabela auditável dos coeficientes efetivamente usados."""
    return (
        ParameterRecord(
            "system_rated_power_kW",
            "Potência nominal líquida do sistema",
            base.system_rated_power_kW,
            "kW",
            ModelParameterClassification.MANUAL_HORIZON,
            "Manual VLIIPro50-22 V1.3, Tabela 4.2",
            "Alvo usado para fechar o consumo auxiliar agregado no ponto nominal.",
        ),
        ParameterRecord(
            "stack_manual_rated_power_kW",
            "Potência nominal publicada do stack",
            base.stack_manual_rated_power_kW,
            "kW",
            ModelParameterClassification.MANUAL_HORIZON,
            "Manual VLIIPro50-22 V1.3, Tabela 4.2",
            "Referência documental; o modelo eletroquímico calcula 65,35 kW a 450 A.",
        ),
        ParameterRecord(
            "dc_dc_efficiency_maximum",
            "Eficiência máxima publicada do DC/DC",
            base.dc_dc.maximum_efficiency,
            "-",
            ModelParameterClassification.MANUAL_HORIZON,
            "Manual VLIIPro50-22 V1.3, seção 4.4.3",
            "Valor máximo declarado pelo fabricante.",
        ),
        ParameterRecord(
            "dc_dc_efficiency_constant",
            "Eficiência constante adotada do DC/DC",
            base.dc_dc.efficiency,
            "-",
            ModelParameterClassification.HIPOTESE,
            "Hipótese de modelagem — ETAPA 5",
            "A curva de eficiência em função da carga não está disponível.",
        ),
        ParameterRecord(
            "auxiliary_reference_gross_power_kW",
            "Potência bruta de referência do modelo auxiliar",
            auxiliary.reference_gross_power_kW,
            "kW",
            ModelParameterClassification.DERIVADO,
            "Modelo estático da ETAPA 4 avaliado em 450 A",
            "Valor calculado pela curva eletroquímica equivalente restringida.",
        ),
        ParameterRecord(
            "auxiliary_nominal_power_kW",
            "Consumo auxiliar equivalente no ponto nominal",
            auxiliary.nominal_auxiliary_power_kW,
            "kW",
            ModelParameterClassification.CALIBRADO_ETAPA5,
            "Fechamento P_net = eta_DCDC P_stack - P_aux",
            "Agregado equivalente; não decompõe compressor, bomba e controladores.",
        ),
        ParameterRecord(
            "auxiliary_load_exponent",
            "Expoente da curva de consumo auxiliar",
            auxiliary.load_exponent,
            "-",
            ModelParameterClassification.HIPOTESE,
            "Hipótese de modelagem — ETAPA 5",
            "Mantém a curva contínua, não negativa e crescente; requer dados reais futuros.",
        ),
        ParameterRecord(
            "hydrogen_utilization_manual_minimum",
            "Utilização mínima de H2 publicada",
            base.hydrogen.utilization_manual_minimum,
            "-",
            ModelParameterClassification.MANUAL_HORIZON,
            "Manual VLIIPro50-22 V1.3, Tabela 4.2",
            "O manual declara utilização superior a 97%.",
        ),
        ParameterRecord(
            "hydrogen_utilization_assumed",
            "Utilização de H2 adotada",
            base.hydrogen.utilization,
            "-",
            ModelParameterClassification.HIPOTESE,
            "Hipótese conservadora — ETAPA 5",
            "Usa o limite inferior publicado, até que existam medições do sistema.",
        ),
        ParameterRecord(
            "hydrogen_maximum_consumption_kg_h",
            "Consumo máximo de H2",
            base.hydrogen.maximum_consumption_kg_h,
            "kg/h",
            ModelParameterClassification.MANUAL_HORIZON,
            "Manual VLIIPro50-22 V1.3, Tabela 4.2",
            "Usado apenas como verificação de limite, não como ponto de calibração.",
        ),
        ParameterRecord(
            "hydrogen_lower_heating_value_kWh_kg",
            "PCI do hidrogênio adotado",
            base.hydrogen.lower_heating_value_kWh_kg,
            "kWh/kg",
            ModelParameterClassification.DERIVADO,
            "Constante energética de referência",
            "Usado para converter vazão mássica em potência química de entrada.",
        ),
        ParameterRecord(
            "lambda_air",
            "Razão estequiométrica de ar",
            base.air.lambda_air,
            "-",
            ModelParameterClassification.HIPOTESE,
            "Hipótese de modelagem — ETAPA 5",
            "Valor configurável; não foi publicado para o ponto nominal.",
        ),
        ParameterRecord(
            "air_maximum_flow_g_s",
            "Consumo máximo de ar",
            base.air.maximum_air_flow_g_s,
            "g/s",
            ModelParameterClassification.MANUAL_HORIZON,
            "Manual VLIIPro50-22 V1.3, Tabela 4.2",
            "Usado como verificação do fluxo calculado.",
        ),
        ParameterRecord(
            "stack_heat_dissipation_max_kW",
            "Dissipação térmica máxima publicada",
            base.heat.maximum_stack_heat_dissipation_kW,
            "kW",
            ModelParameterClassification.MANUAL_HORIZON,
            "Manual VLIIPro50-22 V1.3, Tabela 4.2",
            "Comparado ao calor de reação aproximado do stack, não ao rejeito total equivalente.",
        ),
    )


__all__ = [
    "AirConfig",
    "AuxiliaryPowerConfig",
    "DCDCConfig",
    "DEFAULT_STAGE5_BASE_CONFIGURATION",
    "HeatConfig",
    "HydrogenConfig",
    "ModelParameterClassification",
    "ParameterRecord",
    "Stage5BaseConfiguration",
    "build_parameter_records",
]
