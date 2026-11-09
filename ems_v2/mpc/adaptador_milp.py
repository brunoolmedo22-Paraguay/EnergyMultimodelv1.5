"""Adaptador EXPLÍCITO do MPC para o solver 3C-1 (``ems_v2.milp.solver_3c1.resolver_3c1``).

Este módulo não importa Pyomo/HiGHS nem ``ems_v2.milp`` em tempo de importação: o import acontece dentro de
``resolver``. O núcleo MPC conhece só o protocolo ``ResolvedorJanela`` (duck typing): ``resolver(e3, compromisso)``
devolvendo um resultado com os campos de ``ResultadoResolucao3C1``. ``_executor`` (privado, só ensaios) é repassado ao
``resolver_3c1`` para simular terminações/adulterações, exatamente como nos testes 3C-1.
"""
from __future__ import annotations

import dataclasses
from typing import Protocol


class ResolvedorJanela(Protocol):
    identificador: str
    natureza: str

    def resolver(self, entrada, compromisso_parcial: dict | None = None): ...

    def configuracao_registro(self) -> dict: ...


class ResolvedorMILP3C1:
    natureza = "milp_3c1_pyomo_highs"

    def __init__(self, configuracao, *, tolerancias=None, identificador: str = "resolver_3c1", _executor=None):
        self.configuracao, self.tolerancias, self.identificador = configuracao, tolerancias, identificador
        self._executor = _executor

    def resolver(self, entrada, compromisso_parcial: dict | None = None):
        from ..audit import Tolerancias
        from ..milp.solver_3c1 import resolver_3c1
        return resolver_3c1(entrada, self.configuracao, compromisso_parcial,
                            tolerancias=self.tolerancias or Tolerancias(), _executor=self._executor)

    def configuracao_registro(self) -> dict:
        c = self.configuracao
        reg = dataclasses.asdict(c) if dataclasses.is_dataclass(c) else {"tipo_recebido": type(c).__name__}
        return {"resolvedor": self.identificador, "natureza": self.natureza, "configuracao": reg,
                "executor_substituido": self._executor is not None}


__all__ = ["ResolvedorJanela", "ResolvedorMILP3C1"]
