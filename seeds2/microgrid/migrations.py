"""Migrações explícitas e versionadas do DOCUMENTO de configuração.

v1 → v2 (refinamento do Piso 1). Princípios: nenhum valor conhecido é descartado; identidades são
preservadas; o que não pode ser reinterpretado sem ambiguidade é guardado em ``legacy`` e sinalizado.

* Localização: ``location`` (texto livre) → ``location.address``; latitude/longitude/fuso → ``location``.
* FV: equipamento plano (reference, n_series, n_parallel, soiling_pct) → usina com UM arranjo de mesmo
  significado (id determinístico ``arr-<id do equipamento>``). Sujeira ausente → 0 % marcada como padrão.
* Bateria: célula/Ns/Np → grupo "modelo"; taxas C → taxas máximas; limites de SOC preservados (origem
  "migrado"); **SOC inicial** → ``run_conditions`` (condição de rodada, não dado físico do banco).
* Topologia (barramento, tensão, acoplamentos) → ``legacy.topology_v1`` SEM reinterpretação como conexões
  verificadas; apenas o estado declarado de conexão à rede segue para ``energy_balance``.
* ``migrations`` registra a conversão (de/para, data, notas).
"""
from __future__ import annotations

import copy
from typing import Any

from .config import DOC_SCHEMA_VERSION, new_location, utc_now

SUPPORTED = (1, 2)


class MigrationError(ValueError):
    pass


def _pv_v1_to_v2(eq: dict, notes: list[str]) -> None:
    p = eq.get("params") or {}
    arr = {"id": f"arr-{str(eq.get('id', 'eq-'))[3:]}", "name": "Arranjo 01", "notes": "", "mode": "modulo",
           "reference": p.get("reference"), "n_series": p.get("n_series"), "n_parallel": p.get("n_parallel"),
           "soiling_pct": p.get("soiling_pct"), "soiling_default": False, "declared_kWp": None,
           "declared_source": None, "migrated_from": "v1:params"}
    if arr["soiling_pct"] is None:
        arr["soiling_pct"], arr["soiling_default"] = 0.0, True
        notes.append(f"{eq.get('name')}: perdas por sujeira não declaradas → 0 % (hipótese padrão, sinalizada).")
    eq["params"] = {}
    eq["arrays"] = [arr]


def _battery_v1_to_v2(eq: dict, soc0: dict, notes: list[str]) -> None:
    p = eq.get("params") or {}
    new = {"manufacturer": None, "model": None, "chemistry": None, "energy_kWh": None, "capacity_Ah": None,
           "voltage_V": None, "power_kW": None, "i_charge_max_A": None, "i_discharge_max_A": None,
           "c_charge_max": p.get("c_charge"), "c_discharge_max": p.get("c_discharge"),
           "soc_min_pct": p.get("soc_min_pct"), "soc_max_pct": p.get("soc_max_pct"),
           "soc_limits_source": "migrado" if (p.get("soc_min_pct") is not None or p.get("soc_max_pct") is not None) else "sugerido",
           "model_reference": p.get("reference"), "model_n_series": p.get("n_series"),
           "model_n_parallel": p.get("n_parallel")}
    if p.get("soc0_pct") is not None:
        soc0[eq["id"]] = p["soc0_pct"]
        notes.append(f"{eq.get('name')}: SOC inicial {p['soc0_pct']:g} % movido para as condições da rodada.")
    eq["params"] = new


def _v1_to_v2(doc: dict) -> dict:
    d = copy.deepcopy(doc)
    notes: list[str] = []
    inst = d.get("installation") or {}
    loc = new_location()
    loc["address"] = inst.pop("location", "") or ""
    loc["latitude"], loc["longitude"] = inst.pop("latitude", None), inst.pop("longitude", None)
    loc["timezone"] = inst.pop("timezone", "") or ""
    if loc["address"] or loc["latitude"] is not None or loc["timezone"]:
        loc["source"] = "migrado"
    inst["location"] = loc
    if inst.get("nature") is None or inst.get("operation_mode") is None:
        notes.append("Identificação: natureza da atividade e/ou modo de operação ainda não declarados.")
    soc0: dict[str, Any] = {}
    for section in ("equipment", "retired"):
        for eq in d.get(section) or []:
            if not isinstance(eq, dict):
                continue
            if eq.get("kind") == "pv":
                _pv_v1_to_v2(eq, notes if section == "equipment" else [])
            elif eq.get("kind") == "battery":
                _battery_v1_to_v2(eq, soc0 if section == "equipment" else {}, notes if section == "equipment" else [])
            elif eq.get("kind") == "pemfc":
                eq.setdefault("imported", None)
    topo = d.pop("topology", None) or {}
    d["energy_balance"] = {"grid_connection": topo.get("grid_connection", "nao_declarada")}
    if topo:
        d.setdefault("legacy", {})["topology_v1"] = topo
        d["legacy"]["topology_v1_note"] = ("Topologia declarativa do esquema v1 (barramento, tensão e acoplamentos) "
                                           "preservada apenas para rastreabilidade. Substituída pelo modelo lógico de "
                                           "balanço energético; NÃO representa conexões elétricas verificadas.")
        notes.append("Topologia elétrica v1 substituída pelo modelo lógico de balanço (dados preservados em legacy).")
    d["run_conditions"] = {"battery_soc0_pct": soc0}
    d["schema_version"] = 2
    d.setdefault("migrations", []).append({"from": 1, "to": 2, "at": utc_now(), "notes": notes})
    return d


def migrate_document(doc: Any) -> tuple[Any, list[dict]]:
    """Devolve (documento na versão atual, registros de migração aplicados nesta chamada)."""
    if not isinstance(doc, dict):
        raise MigrationError("Documento de configuração inválido.")
    ver = doc.get("schema_version")
    if ver == DOC_SCHEMA_VERSION:
        return doc, []
    if ver not in SUPPORTED:
        raise MigrationError(f"Versão de documento {ver!r} não suportada por esta versão do SEEDS2.")
    applied: list[dict] = []
    if ver == 1:
        try:
            doc = _v1_to_v2(doc)
        except (TypeError, AttributeError, KeyError, ValueError) as exc:
            raise MigrationError(f"Documento v1 com estrutura inesperada; migração não aplicada ({type(exc).__name__}).") from None
        applied.append(doc["migrations"][-1])
    return doc, applied


def needs_migration(doc: Any) -> bool:
    return isinstance(doc, dict) and doc.get("schema_version") in SUPPORTED and doc.get("schema_version") != DOC_SCHEMA_VERSION
