"""Espelho Python de ``contrato_fonte.m``.

O otimizador não conhece FC, bateria, térmica ou vento: conhece apenas objetos
que obedecem a este contrato. As validações replicam as do MATLAB para que um
pacote de troca inválido falhe da mesma forma nos dois backends.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TIPOS = ("geracao", "nao_despachavel", "armazenamento")


@dataclass
class CurvaEmpirica:
    """Curva (x, y) com *clamping* nas bordas — igual a ``interp_clamp`` do MATLAB.

    Usada pela FC: ``y`` = kg H2 / kWh em função da potência por stack ``x``.
    ``fator`` converte a quantidade física em R$ (preço do H2).
    """

    x: np.ndarray
    y: np.ndarray
    fator_custo: float = 1.0

    def __call__(self, p_por_unid: np.ndarray) -> np.ndarray:
        if self.x.size == 1:
            return np.full(np.shape(p_por_unid), float(self.y[0]))
        # np.interp já satura nas bordas (não extrapola), como interp_clamp.
        return np.interp(p_por_unid, self.x, self.y)


@dataclass
class Fonte:
    nome: str
    tipo: str
    P_max_unid_kW: np.ndarray
    P_min_unid_kW: np.ndarray
    eta: float = 1.0
    n_unid: int = 1
    n_ini: int | None = None
    dn_max: float = np.inf
    c_var_rs_kWh: np.ndarray | None = None      # (Nt, n_unid)
    curva: CurvaEmpirica | None = None          # substitui custo_fn/qtd_fisica_fn
    qtd_fisica_unidade: str = ""
    c_start_unid_rs: float = 0.0
    ramp_kW_min: float = np.inf
    E_kWh: float | None = None
    SOC_ini: float | None = None
    SOC_min: float = 0.0
    SOC_max: float = 1.0
    SOC_alvo: float | None = None
    eta_carga: float = 1.0
    eta_descarga: float = 1.0
    c_deg_rs_kWh: float = 0.0
    meta: dict = field(default_factory=dict)    # diagnósticos (não usados na otimização)

    def __post_init__(self) -> None:
        if not self.nome:
            raise ValueError('Campo "nome" obrigatório.')
        if self.tipo not in TIPOS:
            raise ValueError(f"Fonte {self.nome}: tipo inválido {self.tipo!r}.")
        self.P_max_unid_kW = np.asarray(self.P_max_unid_kW, dtype=float).ravel()
        nt = self.P_max_unid_kW.size
        if self.armazena:
            self.n_unid = 1
        pmin = np.zeros(nt) if self.P_min_unid_kW is None else np.asarray(self.P_min_unid_kW, dtype=float)
        if pmin.ndim == 0:
            pmin = np.full(nt, float(pmin))
        self.P_min_unid_kW = pmin.ravel()
        if self.n_ini is None:
            self.n_ini = self.n_unid
        if self.c_var_rs_kWh is None:
            self.c_var_rs_kWh = np.zeros((nt, self.n_unid))
        else:
            c = np.asarray(self.c_var_rs_kWh, dtype=float)
            if c.ndim == 0:
                c = np.full((nt, self.n_unid), float(c))
            elif c.ndim == 1:
                c = np.repeat(c.reshape(-1, 1), self.n_unid, axis=1)
            self.c_var_rs_kWh = c
        if self.c_var_rs_kWh.shape != (nt, self.n_unid):
            raise ValueError(f"Fonte {self.nome}: c_var_rs_kWh deve ser {nt}x{self.n_unid}.")
        if not (np.all(np.isfinite(self.P_max_unid_kW)) and np.all(np.isfinite(self.P_min_unid_kW))):
            raise ValueError(
                f"Fonte {self.nome}: envelope com NaN/Inf. Fora da janela coberta pelo modelo "
                "declare P_max_unid=0 (indisponível), nunca NaN."
            )
        if not self.armazena and np.any(self.P_min_unid_kW > self.P_max_unid_kW + 1e-9):
            raise ValueError(f"Fonte {self.nome}: piso > teto por unidade em alguns instantes.")
        if not 0 <= self.n_ini <= self.n_unid:
            raise ValueError(f"Fonte {self.nome}: n_ini={self.n_ini} fora de [0, {self.n_unid}].")
        if self.armazena and self.SOC_ini is not None and not (self.SOC_min <= self.SOC_ini <= self.SOC_max):
            raise ValueError(
                f"Fonte {self.nome}: SOC_ini={self.SOC_ini:.3f} fora de [{self.SOC_min:.3f}, {self.SOC_max:.3f}]."
            )

    @property
    def armazena(self) -> bool:
        return self.tipo == "armazenamento"

    @property
    def nt(self) -> int:
        return self.P_max_unid_kW.size

    # --- custo e quantidade física por kWh, vetorizados -----------------------
    def custo_por_kwh(self, P_kW: np.ndarray, n: int, h: np.ndarray) -> np.ndarray:
        """R$/kWh na potência testada (``custo_fn``) ou pela matriz ``c_var``."""
        if self.curva is not None:
            return self.curva(np.abs(P_kW) / np.maximum(n, 1)) * self.curva.fator_custo
        col = min(max(n, 1), self.c_var_rs_kWh.shape[1]) - 1
        return np.broadcast_to(self.c_var_rs_kWh[h, col], np.shape(P_kW))

    def qtd_por_kwh(self, P_kW: np.ndarray, n: int) -> np.ndarray | None:
        if self.curva is None:
            return None
        return self.curva(np.abs(P_kW) / np.maximum(n, 1))
