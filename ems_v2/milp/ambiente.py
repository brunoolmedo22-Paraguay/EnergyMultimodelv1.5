"""Verificação do ambiente do solver (versões fixadas e disponibilidade), sem falha não controlada."""
from __future__ import annotations

import importlib.metadata as md

VERSOES_FIXADAS = {"pyomo": "6.10.1", "highspy": "1.15.1"}
INTERFACE = "pyomo.contrib.solver:highs"
LICENCAS = {"pyomo": "BSD-3-Clause", "highspy": "MIT"}


def versao_instalada(pacote: str) -> str | None:
    try:
        return md.version(pacote)
    except md.PackageNotFoundError:
        return None


def verificar_ambiente() -> dict:
    """Devolve versões instaladas, divergências das fixadas e disponibilidade da interface ``highs``.
    ``disponivel`` só é True se Pyomo e highspy importam e a fábrica reconhece o solver."""
    inst = {p: versao_instalada(p) for p in VERSOES_FIXADAS}
    info = {"versoes": inst, "fixadas": dict(VERSOES_FIXADAS), "interface": INTERFACE,
            "divergencias": sorted(p for p, v in inst.items() if v != VERSOES_FIXADAS[p]),
            "disponivel": False, "versao_highs": None, "erro": None}
    if any(v is None for v in inst.values()):
        info["erro"] = "Pyomo e/ou highspy não instalados (pip install -r requirements-ems_v2.txt)."
        return info
    try:
        import pyomo.environ  # noqa: F401 — registra os plugins da fábrica de solvers
        from pyomo.contrib.solver.common.factory import SolverFactory

        opt = SolverFactory("highs")
        if opt is None or not opt.available():
            info["erro"] = "Interface 'highs' indisponível."
            return info
        v = opt.version()
        info["versao_highs"] = ".".join(str(x) for x in v) if isinstance(v, tuple) else str(v)
        info["disponivel"] = True
    except Exception as exc:  # noqa: BLE001 — diagnóstico, nunca falha não controlada
        info["erro"] = f"{type(exc).__name__}: {exc}"
    return info


__all__ = ["INTERFACE", "LICENCAS", "VERSOES_FIXADAS", "verificar_ambiente", "versao_instalada"]
