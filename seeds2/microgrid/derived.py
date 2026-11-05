"""Grandezas nominais DERIVADAS de dados de datasheet (sem simulação).

Funções auxiliares verificáveis, com unidades, base de cálculo e hipóteses explícitas. Não substituem nem
duplicam os modelos científicos: são produtos/quocientes nominais de catálogo, usados para descrever o
inventário (interface e relatório) e para detectar contradições entre dados declarados.
"""
from __future__ import annotations

from typing import Any

from config.pv_database import MODULE_DB

PV_STC_ASSUMPTIONS = ("Estimativa nominal em STC (1000 W/m², AM1,5, 25 °C) para módulos idênticos ao datasheet: "
                      "P = P_mód·Ns·Np; Voc = Voc_mód·Ns; Isc = Isc_mód·Np; Vmp = Vmp_mód·Ns; Imp = Imp_mód·Np. "
                      "Não considera perdas, mismatch, sujeira, inversor, limites de MPPT nem temperatura diferente de 25 °C.")
CONSISTENCY_TOL = 0.05          # 5 %: tolerância para apontar contradições entre valores declarados


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _pos_int(v: Any) -> int | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 1 or float(v) != int(v):
        return None
    return int(v)


# ------------------------------------------------------------------ fotovoltaica
def pv_module_stc(reference: str | None) -> dict | None:
    entry = MODULE_DB.get(reference or "")
    if not entry:
        return None
    s = entry["stc"]
    return {"P_W": float(s["p_nom"]), "Voc_V": float(s["v_oc"]), "Isc_A": float(s["i_sc"]),
            "Vmp_V": float(s["v_mp"]), "Imp_A": float(s["i_mp"]), "manufacturer": s["manufacturer"], "model": s["model"]}


def pv_array_nominal(arr: dict) -> dict | None:
    """Valores teóricos STC de UM arranjo homogêneo (mesmo módulo, Ns×Np definidos). None se insuficiente."""
    if arr.get("mode") != "modulo":
        return None
    mod = pv_module_stc(arr.get("reference"))
    ns, np_ = _pos_int(arr.get("n_series")), _pos_int(arr.get("n_parallel"))
    if mod is None or ns is None or np_ is None:
        return None
    return {"n_modules": ns * np_, "P_STC_kW": mod["P_W"] * ns * np_ / 1000.0,
            "Voc_V": mod["Voc_V"] * ns, "Isc_A": mod["Isc_A"] * np_,
            "Vmp_V": mod["Vmp_V"] * ns, "Imp_A": mod["Imp_A"] * np_,
            "module": f"{mod['manufacturer']} {mod['model']}", "assumptions": PV_STC_ASSUMPTIONS}


def pv_array_kWp(arr: dict) -> tuple[float | None, str | None]:
    """(potência nominal do arranjo [kWp], base) — base 'calculada' (datasheet) ou 'declarada'."""
    if arr.get("mode") == "declarado":
        v = _num(arr.get("declared_kWp"))
        return (v, "declarada") if v is not None and v > 0 else (None, None)
    nom = pv_array_nominal(arr)
    return (nom["P_STC_kW"], "calculada") if nom else (None, None)


def pv_plant_summary(eq: dict) -> dict:
    """Soma SOMENTE grandezas agregáveis (potência nominal). Tensões e correntes são por arranjo."""
    arrays = eq.get("arrays") or []
    calc = decl = 0.0
    n_calc = n_decl = 0
    unknown: list[str] = []
    for a in arrays:
        v, basis = pv_array_kWp(a)
        if basis == "calculada":
            calc += v
            n_calc += 1
        elif basis == "declarada":
            decl += v
            n_decl += 1
        else:
            unknown.append(str(a.get("name") or a.get("id")))
    return {"n_arrays": len(arrays), "computed_kWp": calc, "declared_kWp": decl, "total_kWp": calc + decl,
            "n_computed": n_calc, "n_declared": n_decl, "unknown_arrays": unknown,
            "n_modules": sum((pv_array_nominal(a) or {}).get("n_modules", 0) for a in arrays)}


# ------------------------------------------------------------------ bateria
def _rel_diff(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def battery_derived(params: dict, model_energy_kWh: float | None = None) -> dict:
    """Estimativas a partir do datasheet do banco + verificação de contradições.

    Cada valor vem com a base: 'declarada' (informada), 'derivada' (relação física com dados declarados) ou
    ausente. Nenhuma taxa C é inferida só a partir da energia nominal.
    """
    g = lambda k: _num(params.get(k))  # noqa: E731
    E, Q, V, P = g("energy_kWh"), g("capacity_Ah"), g("voltage_V"), g("power_kW")
    out: dict[str, Any] = {"warnings": []}

    def put(key, declared, derived, how):
        if declared is not None:
            out[key] = (declared, "declarada", "")
        elif derived is not None:
            out[key] = (derived, "derivada", how)
        else:
            out[key] = (None, None, "")

    put("energy_kWh", E, (V * Q / 1000.0) if V and Q else None, "E = V·Q/1000")
    put("capacity_Ah", Q, (E * 1000.0 / V) if E and V else None, "Q = E·1000/V")
    put("voltage_V", V, (E * 1000.0 / Q) if E and Q else None, "V = E·1000/Q")
    for side, i_key, c_key in (("charge", "i_charge_max_A", "c_charge_max"), ("discharge", "i_discharge_max_A", "c_discharge_max")):
        i, c = g(i_key), g(c_key)
        put(f"c_{side}", c, (i / Q) if i and Q else None, "C = I_máx/Q")
        put(f"i_{side}_A", i, (c * Q) if c and Q else None, "I = C·Q")
        if i and c and Q and _rel_diff(c, i / Q) > CONSISTENCY_TOL:
            out["warnings"].append(f"Taxa C de {'carga' if side == 'charge' else 'descarga'} declarada ({c:g} C) difere de "
                                   f"I_máx/Q ({i / Q:.3g} C).")
    if E and V and Q and _rel_diff(E, V * Q / 1000.0) > CONSISTENCY_TOL:
        out["warnings"].append(f"Energia declarada ({E:g} kWh) difere de V·Q ({V * Q / 1000.0:.4g} kWh).")
    e_eff = out["energy_kWh"][0]
    c_d = out["c_discharge"][0]
    if P and e_eff and c_d and P > c_d * e_eff * (1 + CONSISTENCY_TOL):
        out["warnings"].append(f"Potência nominal declarada ({P:g} kW) excede taxa de descarga × energia "
                               f"({c_d * e_eff:.4g} kW).")
    if model_energy_kWh is not None and e_eff and _rel_diff(e_eff, model_energy_kWh) > CONSISTENCY_TOL:
        out["warnings"].append(f"A parametrização do modelo científico ({model_energy_kWh:.4g} kWh) difere da energia "
                               f"do banco ({e_eff:.4g} kWh, {out['energy_kWh'][1]}).")
    return out
