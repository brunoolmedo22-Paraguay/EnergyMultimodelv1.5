"""Referências técnicas: visões SOMENTE LEITURA dos catálogos e modelos existentes.

Três conceitos são mantidos separados (ver docs/seeds2/ARQUITETURA_PISO1.md):

1. **Modelo científico** — equações (``models/``, ``h2_pemfc/``, ``simulation/``): não é tocado aqui.
2. **Referência técnica** — classe/modelo de equipamento com especificações documentadas
   (entradas de ``config/*_database.py``, células de bateria de ``models/battery_model.py``,
   perfil PEMFC equivalente). Este módulo apenas as LÊ e expõe procedência.
3. **Equipamento instalado** — unidade/agrupamento físico desta microrrede (``config.py``).

Nada aqui inventa fabricantes, preços ou validações: a procedência é copiada dos próprios
catálogos ou declarada como "não informada".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from config.pv_database import MODULE_DB, get_module
from config.thermal_database import (CVU_PRESETS, DYNAMIC_LABELS, LOCAL_GENERATOR, SOURCE_NOTE as THERMAL_SOURCE_NOTE,
                                     THERMAL_PLANT)
from config.wind_turbine_database import TURBINE_DB
from models.battery_model import (BATTERY_2RC, BATTERY_MODEL_LABELS, BATTERY_TREMBLAY, RC_CAPACITY_AH, RC_V_NOM_V,
                                  TREMBLAY_BATTERIES)

KINDS = ("pv", "wind", "battery", "pemfc", "thermal")
KIND_LABELS = {
    "pv": "Solar fotovoltaica",
    "wind": "Eólica",
    "battery": "Bateria",
    "pemfc": "H₂ / PEMFC",
    "thermal": "Térmica",
}
KIND_ROLE = {"pv": "geração renovável", "wind": "geração renovável", "battery": "armazenamento",
             "pemfc": "geração despachável", "thermal": "geração despachável"}

PEMFC_REF_KEY = "EQUIVALENT_65KW_HORIZON_CONSTRAINED"


@dataclass(frozen=True)
class Reference:
    key: str
    kind: str
    label: str
    manufacturer: str | None
    model: str | None
    summary: dict[str, Any] = field(default_factory=dict)       # magnitudes com unidade no nome
    provenance: str = "Procedência não informada no catálogo."
    category: str = ""                                          # p.ex. "datasheet", "célula de referência"
    notes: str = ""


# ------------------------------------------------------------------- Solar
@lru_cache(maxsize=1)
def pv_references() -> dict[str, Reference]:
    out = {}
    for key, entry in MODULE_DB.items():
        stc = entry["stc"]
        mod = get_module(key)
        out[key] = Reference(
            key=key, kind="pv", label=f"{stc['manufacturer']} {stc['model']}",
            manufacturer=stc["manufacturer"], model=stc["model"],
            summary={"P_STC [W]": float(stc["p_nom"]), "Tecnologia": stc.get("technology"),
                     "Células": stc.get("n_cells"), "NOCT [°C]": stc.get("noct"),
                     "γ_Pmax [%/°C]": stc.get("gamma_pmax_pct"), "Área [m²]": round(float(mod.stc.area), 4),
                     "η_STC [%]": round(100 * float(mod.stc.efficiency_stc), 2)},
            provenance="Datasheet público do fabricante (valores STC: 1000 W/m², AM1.5, 25 °C) — config/pv_database.py.",
            category="datasheet de fabricante",
            notes=str(stc.get("notes", "")),
        )
    return out


# ------------------------------------------------------------------- Eólica
@lru_cache(maxsize=1)
def wind_references() -> dict[str, Reference]:
    out = {}
    for key, entry in TURBINE_DB.items():
        spec = entry["spec"]
        src = entry.get("source") or {}
        prov = " · ".join(str(v) for v in (src.get("reference"), src.get("document")) if v) or "Procedência não informada."
        out[key] = Reference(
            key=key, kind="wind", label=key, manufacturer=spec.get("manufacturer"), model=spec.get("model"),
            summary={"P_nominal [kW]": float(spec["rated_power_kw"]), "Diâmetro do rotor [m]": spec.get("rotor_diameter_m"),
                     "Altura do cubo [m]": spec.get("hub_height_m"), "Classe IEC": spec.get("wind_class_iec"),
                     "Curva de potência": (entry.get("quality") or {}).get("power_curve")},
            provenance=f"{prov} — config/wind_turbine_database.py (curvas originais preservadas).",
            category=("arquivo técnico secundário · ensaio atribuído, verificação primária pendente"
                      if entry.get("integration_status") == "curve_analysis_only" else "documentação de fabricante"),
            notes=str(spec.get("notes", "")),
        )
        if entry.get("schema_version") == 2:
            out[key].summary.update({"P_máxima da curva [kW]": spec["curve_peak_power_kw"],
                                     "Base da potência de referência": spec["power_rating_basis"],
                                     "Domínio da curva [m/s]": entry["curve"]["curve_valid_wind_range_mps"],
                                     "Integração": entry["integration_status"],
                                     "Limitação": entry.get("integration_limitation")})
    return out


CURVE_SOURCE_LABELS = {
    "third_party_archive_table_v1": "Tabela de arquivo técnico secundário NREL/NatLabRockies (atribuição a ensaio; confirmação primária pendente)",
    "manufacturer_table": "Tabela de potência do fabricante (valores exatos do documento)",
    "datasheet_graph_digitized": "Curva digitalizada de gráfico do fabricante (aproximada; não é medição certificada)",
}


def wind_curve(key: str) -> dict | None:
    """Curva potência × vento ORIGINAL do catálogo (pontos inalterados), com procedência e qualidade."""
    entry = TURBINE_DB.get(key)
    if not entry:
        return None
    curve = entry.get("curve") or {}
    pts = curve.get("points") or []
    if not pts:
        return None
    src = entry.get("source") or {}
    stype = curve.get("source_type", "")
    return {"points": [(float(v), float(p)) for v, p in pts], "source_type": stype,
            "source_label": CURVE_SOURCE_LABELS.get(stype, f"Procedência da curva: {stype or 'não informada'}"),
            "digitized": stype != "manufacturer_table",  # legacy non-manufacturer flag
            "graph_digitized": stype == "datasheet_graph_digitized",
            "curve_valid_wind_range_mps": curve.get("curve_valid_wind_range_mps"),
            "integration_status": entry.get("integration_status", "legacy"),
            "integration_limitation": entry.get("integration_limitation"),
            "reference_density_kg_m3": curve.get("reference_density_kg_m3"),
            "quality": (entry.get("quality") or {}).get("power_curve"), "notes": str(curve.get("notes") or ""),
            "document": src.get("document"), "reference": src.get("reference"), "pages": src.get("pages")}


def wind_spec(key: str) -> dict:
    return dict((TURBINE_DB.get(key) or {}).get("spec") or {})


# ------------------------------------------------------------------- Bateria
@lru_cache(maxsize=1)
def battery_references() -> dict[str, Reference]:
    out = {}
    for key, b in TREMBLAY_BATTERIES.items():
        out[f"{BATTERY_TREMBLAY}:{key}"] = Reference(
            key=f"{BATTERY_TREMBLAY}:{key}", kind="battery", label=f"{b.name} · {BATTERY_MODEL_LABELS[BATTERY_TREMBLAY]}",
            manufacturer=None, model=None,
            summary={"V_nominal célula [V]": b.V_nom_V, "Q célula [Ah]": b.Q_Ah, "Química": b.chemistry},
            provenance="Parâmetros genéricos de célula do modelo Tremblay–Dessaint/Shepherd portados do protótipo "
                       "MATLAB do projeto — models/battery_model.py.",
            category="célula de referência (não é produto comercial validado)",
        )
    out[f"{BATTERY_2RC}:zhang2017_18650"] = Reference(
        key=f"{BATTERY_2RC}:zhang2017_18650", kind="battery",
        label=f"Li-ion 18650 · 2,35 Ah · {BATTERY_MODEL_LABELS[BATTERY_2RC]}", manufacturer=None, model=None,
        summary={"V_nominal célula [V]": RC_V_NOM_V, "Q célula [Ah]": RC_CAPACITY_AH, "Química": "li_ion"},
        provenance="Circuito equivalente 2 RC de Zhang et al. (2017) para célula Li-ion 18650 — models/battery_model.py.",
        category="célula de referência (não é produto comercial validado)",
    )
    return out


def battery_ref_parts(ref_key: str) -> tuple[str, str | None]:
    """'tremblay:liion_3p3v_2p3ah' → ('tremblay', 'liion_3p3v_2p3ah'); '2rc:…' → ('2rc', None)."""
    model, _, cell = ref_key.partition(":")
    return model, (cell if model == BATTERY_TREMBLAY else None)


def battery_cell(ref_key: str) -> tuple[float, float]:
    """(V_nom célula [V], Q célula [Ah]) da referência — mesma conta de ``ponte.energia_banco_kWh``."""
    model, cell = battery_ref_parts(ref_key)
    if model == BATTERY_TREMBLAY:
        b = TREMBLAY_BATTERIES[cell]
        return b.V_nom_V, b.Q_Ah
    return RC_V_NOM_V, RC_CAPACITY_AH


# ------------------------------------------------------------------- PEMFC
@lru_cache(maxsize=1)
def pemfc_max_net_power_kW() -> float:
    """Potência líquida máxima física de UM sistema, calculada pelo próprio modelo dinâmico."""
    from h2_pemfc import Equivalent65kWHorizonDynamicModel

    return float(Equivalent65kWHorizonDynamicModel()._physical_max_power_kW)


def pemfc_references() -> dict[str, Reference]:
    return {PEMFC_REF_KEY: Reference(
        key=PEMFC_REF_KEY, kind="pemfc",
        label="Sistema PEMFC equivalente · escala Horizon VLIIPro50-22 (aproximado)",
        manufacturer=None, model=None,
        summary={"Potência líquida máx. por sistema [kW]": "calculada pelo modelo (≈50)",
                 "Stack de referência": "210 células · 300 cm² (Chen et al., 2024)"},
        provenance="Perfil EQUIVALENT_65KW_HORIZON_CONSTRAINED — h2_pemfc/docs/MODEL_CARD_HORIZON_APPROX.md. "
                   "Modelo físico parametrizado aproximado; sem validação específica em equipamento instalado.",
        category="perfil de modelo aproximado",
        notes="Único perfil PEMFC suportado pelo motor atual. Perfis calibrados do PEMFC ModelLab ainda não são "
              "importáveis (ver docs/seeds2/ARQUITETURA_PISO1.md).",
    )}


# ------------------------------------------------------------------- Térmica
def thermal_dynamics() -> dict[str, str]:
    return dict(DYNAMIC_LABELS)


def thermal_fuel_presets() -> dict[str, dict]:
    return {k: dict(v) for k, v in CVU_PRESETS.items()}


THERMAL_PRESET_NOTE = THERMAL_SOURCE_NOTE
THERMAL_DYNAMIC_KEYS = (LOCAL_GENERATOR, THERMAL_PLANT)


def references_for(kind: str) -> dict[str, Reference]:
    if kind == "pv":
        return pv_references()
    if kind == "wind":
        return wind_references()
    if kind == "battery":
        return battery_references()
    if kind == "pemfc":
        return pemfc_references()
    return {}
