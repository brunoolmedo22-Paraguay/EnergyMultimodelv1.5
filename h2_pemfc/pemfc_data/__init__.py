"""Conjuntos de dados rastreáveis usados a partir da ETAPA 2."""

from .datasets import (
    DATA_ROOT,
    EQUIVALENT_65KW_CURVE_PATH,
    EQUIVALENT_65KW_METADATA_PATH,
    HORIZON_VLIIPRO50_22_METADATA_PATH,
    HORIZON_VLIIPRO50_22_SPECIFICATIONS_PATH,
    DataClassification,
    DatasetValidationError,
    derive_equivalent_65kw_table,
    horizon_specifications_as_dict,
    load_equivalent_65kw_curve,
    load_equivalent_65kw_metadata,
    load_horizon_vliipro50_22_metadata,
    load_horizon_vliipro50_22_specifications,
    validate_equivalent_65kw_curve,
    validate_horizon_vliipro50_22_specifications,
)

__all__ = [
    "DATA_ROOT",
    "EQUIVALENT_65KW_CURVE_PATH",
    "EQUIVALENT_65KW_METADATA_PATH",
    "HORIZON_VLIIPRO50_22_METADATA_PATH",
    "HORIZON_VLIIPRO50_22_SPECIFICATIONS_PATH",
    "DataClassification",
    "DatasetValidationError",
    "derive_equivalent_65kw_table",
    "horizon_specifications_as_dict",
    "load_equivalent_65kw_curve",
    "load_equivalent_65kw_metadata",
    "load_horizon_vliipro50_22_metadata",
    "load_horizon_vliipro50_22_specifications",
    "validate_equivalent_65kw_curve",
    "validate_horizon_vliipro50_22_specifications",
]
