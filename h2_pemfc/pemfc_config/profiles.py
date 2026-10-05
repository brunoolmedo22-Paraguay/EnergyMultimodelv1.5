"""Registro de perfis parametrizados da plataforma PEMFC.

``OTEKON_REFERENCE`` preserva integralmente a reprodução original. O perfil
``EQUIVALENT_65KW_HORIZON_CONSTRAINED`` acrescenta a parametrização efetiva
da ETAPA 3 e a geometria aproximada de 220 células e 300 cm², sem conter ou
duplicar qualquer equação eletroquímica.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .parameters import (
    DEFAULT_PARAMS,
    ElectrochemicalParameters,
    PEMFCParameters,
    StackGeometry,
)


@dataclass(frozen=True)
class ModelProfileMetadata:
    """Identidade, escopo e estado científico de um perfil."""

    profile_id: str
    display_name: str
    version: str
    source_reference: str
    description: str
    model_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParameterMetadata:
    """Rastreabilidade individual de um parâmetro."""

    symbol: str
    unit: str
    origin: str
    category: str
    justification: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PEMFCProfile:
    """Perfil completo, sem conter equações eletroquímicas."""

    metadata: ModelProfileMetadata
    electrochemical: ElectrochemicalParameters
    geometry: StackGeometry
    parameter_metadata: Mapping[str, ParameterMetadata]
    flat_parameters: PEMFCParameters

    @property
    def profile_id(self) -> str:
        return self.metadata.profile_id

    @property
    def parameters(self) -> PEMFCParameters:
        return self.flat_parameters


OTEKON_REFERENCE_METADATA = ModelProfileMetadata(
    profile_id="OTEKON_REFERENCE",
    display_name="OTEKON 2024 — referência reconstruída",
    version="1.0",
    source_reference="Altıntaş e Ertan, OTEKON 2024, Figura 3",
    description=(
        "Perfil de referência obtido por engenharia reversa e identificação "
        "paramétrica das curvas publicadas na Figura 3."
    ),
    model_status="REPRODUÇÃO COMPUTACIONAL DE REFERÊNCIA",
)

OTEKON_REFERENCE_PARAMETER_METADATA: Mapping[str, ParameterMetadata] = MappingProxyType({
    "E0": ParameterMetadata("E0", "V", "ARTIGO", "CONSTANTE_ELETROQUÍMICA", "Tabela 1."),
    "R": ParameterMetadata("R", "J mol⁻¹ K⁻¹", "CONSTANTE FÍSICA", "CONSTANTE_FÍSICA", "Tabela 1 e constante universal."),
    "F": ParameterMetadata("F", "C mol⁻¹", "CONSTANTE FÍSICA", "CONSTANTE_FÍSICA", "Tabela 1 e constante de Faraday."),
    "T_ref": ParameterMetadata("T_ref", "K", "ARTIGO", "REFERÊNCIA_TERMODINÂMICA", "Temperatura de referência usada na formulação."),
    "t_m": ParameterMetadata("t_m", "cm", "ARTIGO", "MEMBRANA", "Tabela 1."),
    "D_H": ParameterMetadata("D_H+", "cm² s⁻¹", "ARTIGO", "MEMBRANA", "Tabela 1; unidade cm²/s exigida dimensionalmente pela Eq. (12)."),
    "tau_H": ParameterMetadata("τ_H+", "s", "ARTIGO", "DINÂMICA_ELETROQUÍMICA", "Tabela 1."),
    "C_dl_specific": ParameterMetadata("C_dl/A", "F cm⁻²", "DERIVADO", "DINÂMICA_ELETROQUÍMICA", "Decomposição de 0,035 × 232 F da Tabela 1."),
    "p_h2": ParameterMetadata("p_H2", "atm", "INFERIDO", "CONDIÇÃO_OPERACIONAL", "Legenda do painel de pressão e hipótese de H2 puro."),
    "p_h2o": ParameterMetadata("p_H2O", "atm", "HIPÓTESE", "CONDIÇÃO_OPERACIONAL", "Não informado; valor preservado porque seu efeito é correlacionado ao intercepto de ativação."),
    "oxygen_fraction_air": ParameterMetadata("y_O2", "-", "CONSTANTE FÍSICA", "CONDIÇÃO_OPERACIONAL", "Fração molar aproximada do oxigênio no ar seco."),
    "pressure_temperature_K": ParameterMetadata("T_p", "K", "INFERIDO", "CONDIÇÃO_FIGURA_3", "O painel de 5 atm coincide com a curva de 373,15 K da Figura 3."),
    "A_active_cm2": ParameterMetadata("A", "cm²", "INFERIDO", "GEOMETRIA_STACK", "O fator 232 aparece no produto da capacitância de dupla camada."),
    "N_cells": ParameterMetadata("N", "células", "INFERIDO", "GEOMETRIA_STACK", "Consistência entre V_cell, A e potência do stack na Figura 3; valor inteiro mais provável: 41."),
    "xi1": ParameterMetadata("ξ1,ef", "V", "INFERIDO", "ATIVAÇÃO", "Identificação conjunta contra as duas curvas de temperatura e as duas de pressão."),
    "xi2": ParameterMetadata("ξ2,ef", "V K⁻¹", "INFERIDO", "ATIVAÇÃO", "Coeficiente efetivo; o valor impresso não fecha simultaneamente as curvas publicadas."),
    "xi3": ParameterMetadata("ξ3,ef", "V K⁻¹", "INFERIDO", "ATIVAÇÃO", "Coeficiente efetivo da dependência logarítmica da corrente."),
    "xi4": ParameterMetadata("ξ4,ef", "V K⁻¹", "INFERIDO", "ATIVAÇÃO", "O valor efetivo é exigido pela pequena separação entre as curvas de 1 e 5 atm."),
    "R_mem_ref_ohm_cm2": ParameterMetadata("R_mem,ref", "Ω cm²", "INFERIDO", "ÔHMICO", "Inclinação ôhmica identificada na Figura 3 e usada na cadeia Eq. (10)-(12)."),
    "R_mem_temperature_exponent": ParameterMetadata("n_R", "-", "INFERIDO", "ÔHMICO", "Dependência térmica efetiva da hidratação/condutividade não explicitada no artigo."),
    "concentration_a_ref_V": ParameterMetadata("a_ref", "V", "INFERIDO", "CONCENTRAÇÃO", "Coeficiente efetivo da Eq. (13)."),
    "concentration_a_temperature_V_K": ParameterMetadata("a_T", "V K⁻¹", "INFERIDO", "CONCENTRAÇÃO", "Dependência térmica efetiva; evita o valor negativo da expressão impressa em 373,15 K."),
    "concentration_b_cm2_A": ParameterMetadata("b_eff", "cm² A⁻¹", "INFERIDO", "CONCENTRAÇÃO", "Interpretação de unidade compatível com a curvatura publicada."),
    "fuel_utilization": ParameterMetadata("U_f", "-", "INFERIDO", "EFICIÊNCIA", "A expressão de eficiência não é fornecida; inferido pela proporcionalidade η/V da Figura 3."),
    "current_density_floor_A_cm2": ParameterMetadata("j_floor", "A cm⁻²", "HIPÓTESE NUMÉRICA", "REGULARIZAÇÃO_NUMÉRICA", "Evita log(0) na correlação de ativação sem alterar a malha exibida."),
})

OTEKON_REFERENCE = PEMFCProfile(
    metadata=OTEKON_REFERENCE_METADATA,
    electrochemical=DEFAULT_PARAMS.electrochemical,
    geometry=DEFAULT_PARAMS.geometry,
    parameter_metadata=OTEKON_REFERENCE_PARAMETER_METADATA,
    flat_parameters=DEFAULT_PARAMS,
)


EQUIVALENT_65KW_HORIZON_CONSTRAINED_METADATA = ModelProfileMetadata(
    profile_id="EQUIVALENT_65KW_HORIZON_CONSTRAINED",
    display_name="Stack PEMFC equivalente de 65 kW restringido pelo ponto Horizon",
    version="1.0",
    source_reference=(
        "Calibração ETAPA 3: curva experimental equivalente de 65 kW + "
        "ponto nominal do Horizon VLIIPro50-22 V1.3"
    ),
    description=(
        "Perfil eletroquímico aproximado para estudos preliminares de um stack "
        "de 220 células e 300 cm². Os quatro coeficientes efetivos foram "
        "identificados na ETAPA 3; os demais permanecem ancorados no OTEKON."
    ),
    model_status="CURVA EQUIVALENTE RESTRITA — NÃO VALIDADA NO HORIZON",
)

_EQUIVALENT_65KW_FLAT_PARAMETERS = OTEKON_REFERENCE.parameters.copy_with(
    # Condições nominais usadas na calibração; a API estática pode substituí-las.
    p_h2=2.3816925734024177,
    pressure_temperature_K=353.15,
    # Geometria do stack aproximado.
    A_active_cm2=300.0,
    N_cells=220,
    # Quatro parâmetros efetivos identificados na ETAPA 3.
    xi1=-0.8617092428432912,
    R_mem_ref_ohm_cm2=0.016977693645129133,
    concentration_a_ref_V=0.0006012169244341891,
    concentration_b_cm2_A=1.9018750855225133,
)

_equivalent_metadata = dict(OTEKON_REFERENCE_PARAMETER_METADATA)
_equivalent_metadata.update({
    "p_h2": ParameterMetadata(
        "p_H2",
        "atm abs",
        "DERIVADO_DE_MANUAL_HORIZON",
        "CONDIÇÃO_OPERACIONAL",
        "Valor nominal absoluto derivado de 140 kPag e 101,325 kPa; substituível em tempo de avaliação.",
    ),
    "pressure_temperature_K": ParameterMetadata(
        "T_cal",
        "K",
        "HIPÓTESE_ETAPA3",
        "CONDIÇÃO_CALIBRAÇÃO",
        "Temperatura comum de 353,15 K adotada explicitamente na calibração equivalente.",
    ),
    "A_active_cm2": ParameterMetadata(
        "A",
        "cm²",
        "HIPÓTESE",
        "GEOMETRIA_STACK",
        "Área ativa inicial de 300 cm²; não é informada no manual Horizon e deve ser revista com dados reais.",
    ),
    "N_cells": ParameterMetadata(
        "N",
        "células",
        "MANUAL_HORIZON",
        "GEOMETRIA_STACK",
        "Número de células publicado para o VLSIIPro66-22 no manual V1.3.",
    ),
    "xi1": ParameterMetadata(
        "ξ1,ef",
        "V",
        "CALIBRAÇÃO_ETAPA3",
        "ATIVAÇÃO_EFETIVA",
        "Identificado contra quatro pontos equivalentes e o ponto nominal Horizon, com prior OTEKON.",
    ),
    "R_mem_ref_ohm_cm2": ParameterMetadata(
        "R_mem,ref",
        "Ω cm²",
        "CALIBRAÇÃO_ETAPA3",
        "ÔHMICO_EFETIVO",
        "Identificado como coeficiente efetivo conjunto; não representa medição direta da membrana Horizon.",
    ),
    "concentration_a_ref_V": ParameterMetadata(
        "a_ref",
        "V",
        "CALIBRAÇÃO_ETAPA3",
        "CONCENTRAÇÃO_EFETIVA",
        "Identificado como amplitude efetiva com regularização fraca em relação ao prior OTEKON.",
    ),
    "concentration_b_cm2_A": ParameterMetadata(
        "b_eff",
        "cm² A⁻¹",
        "CALIBRAÇÃO_ETAPA3",
        "CONCENTRAÇÃO_EFETIVA",
        "Identificado como crescimento efetivo; fortemente correlacionado aos demais parâmetros ajustados.",
    ),
})
EQUIVALENT_65KW_HORIZON_CONSTRAINED_PARAMETER_METADATA: Mapping[str, ParameterMetadata] = (
    MappingProxyType(_equivalent_metadata)
)

EQUIVALENT_65KW_HORIZON_CONSTRAINED = PEMFCProfile(
    metadata=EQUIVALENT_65KW_HORIZON_CONSTRAINED_METADATA,
    electrochemical=_EQUIVALENT_65KW_FLAT_PARAMETERS.electrochemical,
    geometry=_EQUIVALENT_65KW_FLAT_PARAMETERS.geometry,
    parameter_metadata=EQUIVALENT_65KW_HORIZON_CONSTRAINED_PARAMETER_METADATA,
    flat_parameters=_EQUIVALENT_65KW_FLAT_PARAMETERS,
)


MODEL_PROFILES: Mapping[str, PEMFCProfile] = MappingProxyType({
    OTEKON_REFERENCE.profile_id: OTEKON_REFERENCE,
    EQUIVALENT_65KW_HORIZON_CONSTRAINED.profile_id: EQUIVALENT_65KW_HORIZON_CONSTRAINED,
})


def get_profile(profile_id: str) -> PEMFCProfile:
    """Obtém um perfil registrado e falha explicitamente para nomes inválidos."""
    try:
        return MODEL_PROFILES[profile_id]
    except KeyError as exc:
        available = ", ".join(sorted(MODEL_PROFILES))
        raise KeyError(
            f"Perfil PEMFC desconhecido: {profile_id!r}. Disponíveis: {available}."
        ) from exc


# Compatibilidade com toda a aplicação existente.
PARAMETER_METADATA: dict[str, dict[str, str]] = {
    name: metadata.to_dict()
    for name, metadata in OTEKON_REFERENCE.parameter_metadata.items()
}
