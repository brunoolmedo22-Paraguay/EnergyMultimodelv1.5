"""Objetos de parâmetros usados pelo núcleo eletroquímico PEMFC.

A classe :class:`PEMFCParameters` mantém a interface plana histórica usada pela
aplicação, pelos scripts de identificação e pelos testes. A arquitetura de
perfis, definida em :mod:`pemfc_config.profiles`, separa esses valores em dois
blocos explícitos: parâmetros eletroquímicos e geometria do stack.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from typing import Any


@dataclass(frozen=True)
class ElectrochemicalParameters:
    """Parâmetros físicos, operacionais e semiempíricos de uma célula PEMFC."""

    # Constantes e valores explicitamente publicados
    E0: float = 1.229                    # V
    R: float = 8.314                     # J/(mol.K)
    F: float = 96485.0                   # C/mol
    T_ref: float = 298.15                # K
    t_m: float = 0.005                   # cm
    D_H: float = 0.85e-6                 # cm²/s
    tau_H: float = 12.78                 # s
    C_dl_specific: float = 0.035         # F/cm²

    # Condições reconstruídas da Figura 3
    p_h2: float = 1.0                    # atm
    p_h2o: float = 0.50                  # atm
    oxygen_fraction_air: float = 0.21    # -
    pressure_temperature_K: float = 373.15

    # Coeficientes efetivos de ativação
    xi1: float = -0.674591776167
    xi2: float = 0.00177858729827
    xi3: float = -7.38573038384e-05
    xi4: float = 1.19623548544e-05

    # Cadeia ôhmica Eq. (10)-(12)
    R_mem_ref_ohm_cm2: float = 0.225432192680
    R_mem_temperature_exponent: float = -0.776511316144

    # Perdas por concentração Eq. (13)
    concentration_a_ref_V: float = 0.00658205964880
    concentration_a_temperature_V_K: float = 1.50924914732e-05
    concentration_b_cm2_A: float = 2.92419192535

    # Eficiência reconstruída da Figura 3
    fuel_utilization: float = 0.696146096313

    # Regularização numérica no ponto I=0
    current_density_floor_A_cm2: float = 0.010

    def copy_with(self, **kwargs: Any) -> "ElectrochemicalParameters":
        return replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StackGeometry:
    """Geometria elétrica e ativa do stack."""

    A_active_cm2: float = 232.0
    N_cells: int = 41

    def copy_with(self, **kwargs: Any) -> "StackGeometry":
        return replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ELECTROCHEMICAL_FIELD_NAMES = frozenset(
    field.name for field in fields(ElectrochemicalParameters)
)
_GEOMETRY_FIELD_NAMES = frozenset(field.name for field in fields(StackGeometry))


@dataclass(frozen=True)
class PEMFCParameters:
    """Visão plana compatível dos parâmetros consumidos por ``PEMFCModel``.

    Esta classe permanece deliberadamente plana para não quebrar a API
    existente. Perfis novos devem ser montados a partir de
    :class:`ElectrochemicalParameters` e :class:`StackGeometry` mediante
    :meth:`from_components`.
    """

    # Constantes e valores explicitamente publicados
    E0: float = 1.229
    R: float = 8.314
    F: float = 96485.0
    T_ref: float = 298.15
    t_m: float = 0.005
    D_H: float = 0.85e-6
    tau_H: float = 12.78
    C_dl_specific: float = 0.035

    # Condições reconstruídas da Figura 3
    p_h2: float = 1.0
    p_h2o: float = 0.50
    oxygen_fraction_air: float = 0.21
    pressure_temperature_K: float = 373.15

    # Geometria e stack
    A_active_cm2: float = 232.0
    N_cells: int = 41

    # Coeficientes efetivos de ativação
    xi1: float = -0.674591776167
    xi2: float = 0.00177858729827
    xi3: float = -7.38573038384e-05
    xi4: float = 1.19623548544e-05

    # Cadeia ôhmica Eq. (10)-(12)
    R_mem_ref_ohm_cm2: float = 0.225432192680
    R_mem_temperature_exponent: float = -0.776511316144

    # Perdas por concentração Eq. (13)
    concentration_a_ref_V: float = 0.00658205964880
    concentration_a_temperature_V_K: float = 1.50924914732e-05
    concentration_b_cm2_A: float = 2.92419192535

    # Eficiência reconstruída da Figura 3
    fuel_utilization: float = 0.696146096313

    # Regularização numérica no ponto I=0
    current_density_floor_A_cm2: float = 0.010

    @classmethod
    def from_components(
        cls,
        electrochemical: ElectrochemicalParameters,
        geometry: StackGeometry,
    ) -> "PEMFCParameters":
        """Monta a visão plana sem duplicar lógica matemática."""
        return cls(**electrochemical.to_dict(), **geometry.to_dict())

    @property
    def electrochemical(self) -> ElectrochemicalParameters:
        return ElectrochemicalParameters(
            **{name: getattr(self, name) for name in _ELECTROCHEMICAL_FIELD_NAMES}
        )

    @property
    def geometry(self) -> StackGeometry:
        return StackGeometry(
            **{name: getattr(self, name) for name in _GEOMETRY_FIELD_NAMES}
        )

    def copy_with(self, **kwargs: Any) -> "PEMFCParameters":
        unknown = set(kwargs) - (_ELECTROCHEMICAL_FIELD_NAMES | _GEOMETRY_FIELD_NAMES)
        if unknown:
            unknown_text = ", ".join(sorted(unknown))
            raise TypeError(f"Parâmetros desconhecidos: {unknown_text}")
        return replace(self, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def C_dl_total_F(self) -> float:
        return self.C_dl_specific * self.A_active_cm2

    @property
    def sigma_ref_S_cm(self) -> float:
        return self.t_m / self.R_mem_ref_ohm_cm2

    @property
    def proton_concentration_ref_mol_cm3(self) -> float:
        """Concentração efetiva derivada de Eq. (10)-(12) em T_ref."""
        return (
            self.sigma_ref_S_cm * self.R * self.T_ref
            / (self.F**2 * self.D_H)
        )


# Alias histórico preservado no módulo original. O perfil OTEKON_REFERENCE
# referencia exatamente esta instância.
DEFAULT_PARAMS = PEMFCParameters()


def __getattr__(name: str):
    """Compatibilidade tardia para o antigo import de PARAMETER_METADATA."""
    if name == "PARAMETER_METADATA":
        from .profiles import PARAMETER_METADATA

        return PARAMETER_METADATA
    raise AttributeError(name)
