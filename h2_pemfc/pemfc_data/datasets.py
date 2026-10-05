"""Carga, derivação e validação dos conjuntos de dados da ETAPA 2.

Este módulo contém somente infraestrutura de dados. Ele não implementa equações
PEMFC, não instancia perfis de modelo e não executa identificação paramétrica.
"""
from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd


class DataClassification(str, Enum):
    """Classificações de rastreabilidade permitidas no projeto."""

    MANUAL_HORIZON = "MANUAL_HORIZON"
    EXPERIMENTAL_EQUIVALENTE = "EXPERIMENTAL_EQUIVALENTE"
    DERIVADO = "DERIVADO"
    HIPOTESE = "HIPOTESE"


class DatasetValidationError(ValueError):
    """Erro explícito de estrutura, unidade ou domínio de um dataset."""


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"

EQUIVALENT_65KW_ROOT = DATA_ROOT / "equivalent_65kw"
EQUIVALENT_65KW_CURVE_PATH = EQUIVALENT_65KW_ROOT / "curve_raw.csv"
EQUIVALENT_65KW_METADATA_PATH = EQUIVALENT_65KW_ROOT / "metadata.json"

HORIZON_VLIIPRO50_22_ROOT = DATA_ROOT / "horizon_vliipro50_22"
HORIZON_VLIIPRO50_22_SPECIFICATIONS_PATH = (
    HORIZON_VLIIPRO50_22_ROOT / "specifications.csv"
)
HORIZON_VLIIPRO50_22_METADATA_PATH = HORIZON_VLIIPRO50_22_ROOT / "metadata.json"

EQUIVALENT_RAW_COLUMNS = ("current_A", "stack_voltage_V")
EQUIVALENT_DERIVED_COLUMNS = (
    "current_density_A_cm2",
    "cell_voltage_V",
    "stack_power_kW",
    "power_density_W_cm2",
)

HORIZON_SPECIFICATION_COLUMNS = (
    "parameter_id",
    "display_name",
    "value",
    "unit",
    "classification",
    "source_location",
    "notes",
)

HORIZON_REQUIRED_PARAMETER_IDS = frozenset({
    "number_of_cells",
    "active_area_cm2",
    "stack_current_max_A",
    "stack_voltage_nominal_V",
    "stack_voltage_min_V",
    "stack_voltage_max_V",
    "stack_rated_power_kW",
    "system_rated_power_kW",
    "system_peak_power_kW",
    "recommended_output_min_percent",
    "recommended_output_max_percent",
    "ramp_up_kW_s",
    "ramp_down_kW_s",
    "anode_pressure_nominal_kPag",
    "cathode_pressure_nominal_kPag",
    "hydrogen_utilization_min_percent",
    "hydrogen_consumption_max_kg_h",
    "dc_dc_efficiency_max_percent",
    "air_consumption_max_g_s",
    "heat_dissipation_rated_max_kW",
})


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo de metadados não encontrado: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise DatasetValidationError(f"Metadados devem ser um objeto JSON: {path}")
    return payload


def _classification_values() -> set[str]:
    return {item.value for item in DataClassification}


def _require_positive_finite(series: pd.Series, name: str) -> None:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise DatasetValidationError(f"A coluna {name!r} contém valor não numérico ou não finito.")
    if (numeric <= 0.0).any():
        raise DatasetValidationError(f"A coluna {name!r} deve conter somente valores positivos.")


def _validate_field_classifications(metadata: Mapping[str, Any]) -> None:
    fields = metadata.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        raise DatasetValidationError("Metadados não contêm o mapa obrigatório 'fields'.")
    allowed = _classification_values()
    for field_name, field_metadata in fields.items():
        if not isinstance(field_metadata, Mapping):
            raise DatasetValidationError(
                f"Metadados do campo {field_name!r} devem ser um objeto."
            )
        classification = field_metadata.get("classification")
        if classification not in allowed:
            raise DatasetValidationError(
                f"Classificação inválida no campo {field_name!r}: {classification!r}."
            )


def load_equivalent_65kw_metadata(
    path: str | Path = EQUIVALENT_65KW_METADATA_PATH,
) -> dict[str, Any]:
    """Carrega e valida a rastreabilidade do stack experimental equivalente."""
    metadata = _load_json(Path(path))
    if metadata.get("dataset_id") != "EQUIVALENT_65KW_EXPERIMENTAL":
        raise DatasetValidationError("dataset_id inesperado para o stack equivalente de 65 kW.")
    if metadata.get("is_horizon_test") is not False:
        raise DatasetValidationError(
            "O dataset equivalente deve declarar explicitamente que não é ensaio Horizon."
        )
    _validate_field_classifications(metadata)

    stack = metadata.get("stack")
    if not isinstance(stack, Mapping):
        raise DatasetValidationError("Metadados do stack equivalente ausentes.")
    for key in ("number_of_cells", "active_area_cm2"):
        record = stack.get(key)
        if not isinstance(record, Mapping):
            raise DatasetValidationError(f"Metadado obrigatório ausente: stack.{key}")
        value = record.get("value")
        if not isinstance(value, (int, float)) or not np.isfinite(float(value)) or value <= 0:
            raise DatasetValidationError(f"Valor inválido em stack.{key}: {value!r}")
        if record.get("classification") != DataClassification.EXPERIMENTAL_EQUIVALENTE.value:
            raise DatasetValidationError(
                f"stack.{key} deve ser classificado como EXPERIMENTAL_EQUIVALENTE."
            )
    return metadata


def validate_equivalent_65kw_curve(
    raw_curve: pd.DataFrame,
    metadata: Mapping[str, Any],
) -> None:
    """Valida somente os pontos medidos e a geometria usada nas conversões."""
    missing = set(EQUIVALENT_RAW_COLUMNS) - set(raw_curve.columns)
    if missing:
        raise DatasetValidationError(
            "Colunas ausentes no dataset equivalente: " + ", ".join(sorted(missing))
        )
    unexpected = set(raw_curve.columns) - set(EQUIVALENT_RAW_COLUMNS)
    if unexpected:
        raise DatasetValidationError(
            "O CSV bruto deve conter apenas dados medidos; colunas inesperadas: "
            + ", ".join(sorted(unexpected))
        )
    if raw_curve.empty:
        raise DatasetValidationError("O dataset equivalente não pode estar vazio.")

    _require_positive_finite(raw_curve["current_A"], "current_A")
    _require_positive_finite(raw_curve["stack_voltage_V"], "stack_voltage_V")

    current = pd.to_numeric(raw_curve["current_A"], errors="raise")
    if current.duplicated().any():
        raise DatasetValidationError("A corrente deve ser única em cada ponto experimental.")
    if not current.is_monotonic_increasing:
        raise DatasetValidationError("Os pontos experimentais devem estar ordenados por corrente.")

    _validate_field_classifications(metadata)
    stack = metadata["stack"]
    if float(stack["number_of_cells"]["value"]) <= 0:
        raise DatasetValidationError("number_of_cells deve ser positivo.")
    if float(stack["active_area_cm2"]["value"]) <= 0:
        raise DatasetValidationError("active_area_cm2 deve ser positiva.")


def derive_equivalent_65kw_table(
    raw_curve: pd.DataFrame,
    metadata: Mapping[str, Any],
) -> pd.DataFrame:
    """Calcula as grandezas normalizadas sem gravá-las como dados experimentais."""
    validate_equivalent_65kw_curve(raw_curve, metadata)
    number_of_cells = float(metadata["stack"]["number_of_cells"]["value"])
    active_area_cm2 = float(metadata["stack"]["active_area_cm2"]["value"])

    derived = raw_curve.loc[:, EQUIVALENT_RAW_COLUMNS].astype(float).copy()
    derived["current_density_A_cm2"] = derived["current_A"] / active_area_cm2
    derived["cell_voltage_V"] = derived["stack_voltage_V"] / number_of_cells
    derived["stack_power_kW"] = (
        derived["current_A"] * derived["stack_voltage_V"] / 1000.0
    )
    derived["power_density_W_cm2"] = (
        derived["stack_power_kW"] * 1000.0
        / (number_of_cells * active_area_cm2)
    )
    return derived


def load_equivalent_65kw_curve(
    curve_path: str | Path = EQUIVALENT_65KW_CURVE_PATH,
    metadata_path: str | Path = EQUIVALENT_65KW_METADATA_PATH,
) -> pd.DataFrame:
    """Carrega os pontos medidos e devolve a tabela com derivações determinísticas."""
    curve_path = Path(curve_path)
    if not curve_path.is_file():
        raise FileNotFoundError(f"CSV experimental não encontrado: {curve_path}")
    raw_curve = pd.read_csv(curve_path)
    metadata = load_equivalent_65kw_metadata(metadata_path)
    return derive_equivalent_65kw_table(raw_curve, metadata)


def load_horizon_vliipro50_22_metadata(
    path: str | Path = HORIZON_VLIIPRO50_22_METADATA_PATH,
) -> dict[str, Any]:
    """Carrega os metadados do manual e da hipótese de área ativa."""
    metadata = _load_json(Path(path))
    if metadata.get("dataset_id") != "HORIZON_VLIIPRO50_22_V1_3_SPECIFICATIONS":
        raise DatasetValidationError("dataset_id inesperado para o VLIIPro50-22.")
    area = metadata.get("active_area_assumption")
    if not isinstance(area, Mapping):
        raise DatasetValidationError("Metadado obrigatório active_area_assumption ausente.")
    if area.get("classification") != DataClassification.HIPOTESE.value:
        raise DatasetValidationError("A área ativa de 300 cm2 deve ser classificada como HIPOTESE.")
    if float(area.get("value", 0.0)) != 300.0:
        raise DatasetValidationError("A hipótese inicial de área ativa deve ser 300 cm2 nesta etapa.")
    return metadata


def validate_horizon_vliipro50_22_specifications(
    specifications: pd.DataFrame,
    metadata: Mapping[str, Any],
) -> None:
    """Valida esquema, classificação e coerência básica das especificações."""
    missing_columns = set(HORIZON_SPECIFICATION_COLUMNS) - set(specifications.columns)
    if missing_columns:
        raise DatasetValidationError(
            "Colunas ausentes nas especificações Horizon: "
            + ", ".join(sorted(missing_columns))
        )
    unexpected = set(specifications.columns) - set(HORIZON_SPECIFICATION_COLUMNS)
    if unexpected:
        raise DatasetValidationError(
            "Colunas inesperadas nas especificações Horizon: "
            + ", ".join(sorted(unexpected))
        )
    if specifications.empty:
        raise DatasetValidationError("As especificações Horizon não podem estar vazias.")
    if specifications["parameter_id"].isna().any() or specifications["parameter_id"].duplicated().any():
        raise DatasetValidationError("parameter_id deve ser preenchido e único.")

    parameter_ids = set(specifications["parameter_id"].astype(str))
    missing_parameters = HORIZON_REQUIRED_PARAMETER_IDS - parameter_ids
    if missing_parameters:
        raise DatasetValidationError(
            "Parâmetros Horizon obrigatórios ausentes: "
            + ", ".join(sorted(missing_parameters))
        )

    _require_positive_finite(specifications["value"], "value")
    allowed = _classification_values()
    invalid_classifications = set(specifications["classification"]) - allowed
    if invalid_classifications:
        raise DatasetValidationError(
            "Classificações inválidas: " + ", ".join(sorted(invalid_classifications))
        )

    indexed = specifications.set_index("parameter_id")
    area = indexed.loc["active_area_cm2"]
    if area["classification"] != DataClassification.HIPOTESE.value:
        raise DatasetValidationError("active_area_cm2 deve ser classificada como HIPOTESE.")
    if float(area["value"]) != float(metadata["active_area_assumption"]["value"]):
        raise DatasetValidationError("A área ativa do CSV diverge dos metadados.")

    manual_rows = specifications.drop(index=specifications.index[specifications["parameter_id"] == "active_area_cm2"])
    if not (manual_rows["classification"] == DataClassification.MANUAL_HORIZON.value).all():
        raise DatasetValidationError(
            "Nesta etapa, todas as especificações exceto a área ativa devem ser MANUAL_HORIZON."
        )

    if float(indexed.loc["stack_voltage_min_V", "value"]) >= float(
        indexed.loc["stack_voltage_max_V", "value"]
    ):
        raise DatasetValidationError("A faixa de tensão Horizon está invertida ou degenerada.")
    if float(indexed.loc["recommended_output_min_percent", "value"]) >= float(
        indexed.loc["recommended_output_max_percent", "value"]
    ):
        raise DatasetValidationError("A faixa recomendada de potência está invertida.")
    if float(indexed.loc["system_rated_power_kW", "value"]) > float(
        indexed.loc["stack_rated_power_kW", "value"]
    ):
        raise DatasetValidationError(
            "A potência nominal do sistema não pode superar a potência bruta do stack."
        )


def load_horizon_vliipro50_22_specifications(
    specifications_path: str | Path = HORIZON_VLIIPRO50_22_SPECIFICATIONS_PATH,
    metadata_path: str | Path = HORIZON_VLIIPRO50_22_METADATA_PATH,
) -> pd.DataFrame:
    """Carrega e valida a tabela longa de especificações do VLIIPro50-22."""
    specifications_path = Path(specifications_path)
    if not specifications_path.is_file():
        raise FileNotFoundError(
            f"CSV de especificações Horizon não encontrado: {specifications_path}"
        )
    specifications = pd.read_csv(specifications_path)
    metadata = load_horizon_vliipro50_22_metadata(metadata_path)
    validate_horizon_vliipro50_22_specifications(specifications, metadata)
    return specifications


def horizon_specifications_as_dict(
    specifications: pd.DataFrame | None = None,
) -> dict[str, float]:
    """Converte a tabela validada em mapa numérico sem criar perfil de modelo."""
    if specifications is None:
        specifications = load_horizon_vliipro50_22_specifications()
    else:
        metadata = load_horizon_vliipro50_22_metadata()
        validate_horizon_vliipro50_22_specifications(specifications, metadata)
    return {
        str(row.parameter_id): float(row.value)
        for row in specifications.itertuples(index=False)
    }
