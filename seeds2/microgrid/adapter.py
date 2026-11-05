"""Adaptador: inventário persistido → contrato agregado do orquestrador V1.6.

O runtime V1.6 (``orchestrator_runtime.build_exchange_package``) aceita UMA configuração
agregada por tecnologia. Este adaptador NÃO altera o EMS para "caber" mais equipamentos:

1. classifica cada equipamento instalado (representado / desabilitado / incompleto / incompatível);
2. agrega SOMENTE grupos fisicamente equivalentes no modelo existente (mesma referência e mesma
   configuração por unidade → soma linear da quantidade: strings FV em paralelo, aerogeradores,
   ramos Np de baterias idênticas, sistemas PEMFC idênticos);
3. nunca escolhe arbitrariamente entre equipamentos heterogêneos: todos os do grupo ficam
   "incompatíveis", com motivo explícito;
4. nunca omite silenciosamente: tudo o que não entra na rodada aparece em ``excluded`` e a UI
   exige confirmação explícita para executar sem esses equipamentos;
5. calcula impressões digitais (configuração e especificação) para rastrear a procedência.

As agregações são exatas porque, nos modelos existentes, a potência FV escala com
``n_series·n_parallel`` (``simulate_noct_efficiency_model``), a eólica com ``turbine_count``
(``run_wind_model``) e a bateria/PEMFC são caracterizadas por unidade e escaladas por Np/N_fc.
"""
from __future__ import annotations

import copy
import hashlib
import io
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from . import config as C
from .references import KIND_LABELS, battery_ref_parts

REPRESENTED, DISABLED, INCOMPLETE, INCOMPATIBLE = "representado", "desabilitado", "incompleto", "incompativel"
STATUS_LABELS = {REPRESENTED: "Representado no EMS", DISABLED: "Desabilitado", INCOMPLETE: "Configuração incompleta",
                 INCOMPATIBLE: "Não representável no EMS V1.6"}
TARGET = {"pv": "solar", "wind": "wind", "battery": "battery", "pemfc": "fc", "thermal": "thermal"}
# Faixas usadas pela interface V1.6 (não são limites físicos): fora delas apenas avisamos.
V16_UI_RANGES = {"N_fc": (1, 12), "battery_Ns": (1, 2000), "battery_Np": (1, 2000), "wind_count": (1, 100)}


@dataclass
class Mapping:
    id: str
    name: str
    kind: str
    status: str
    target: str | None = None
    reason: str = ""
    parent: str | None = None          # FV: id da usina à qual o arranjo pertence

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "kind_label": KIND_LABELS.get(self.kind, self.kind),
                "status": self.status, "status_label": STATUS_LABELS[self.status], "target": self.target,
                "reason": self.reason, "parent": self.parent}


@dataclass
class SimulationPlan:
    spec: dict
    mappings: list[Mapping]
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    load_descriptor: dict = field(default_factory=dict)
    climate_descriptor: dict = field(default_factory=dict)
    config_revision: int | None = None
    config_fingerprint: str | None = None
    run_conditions: dict = field(default_factory=dict)
    pv_installed_kWp: float = 0.0       # soma nominal registrada (calculada + declarada) das usinas habilitadas
    pv_represented_kWp: float = 0.0     # parte efetivamente representada na rodada (arranjos homogêneos aceitos)

    def for_equipment(self, eq_id: str) -> list[Mapping]:
        return [m for m in self.mappings if m.id == eq_id or m.parent == eq_id]

    @property
    def excluded(self) -> list[Mapping]:
        return [m for m in self.mappings if m.status in (INCOMPLETE, INCOMPATIBLE)]

    @property
    def represented(self) -> list[Mapping]:
        return [m for m in self.mappings if m.status == REPRESENTED]

    @property
    def runnable(self) -> bool:
        return not self.blockers

    @property
    def needs_ack(self) -> bool:
        return bool(self.excluded)

    @property
    def spec_fingerprint(self) -> str:
        payload = {"spec": self.spec, "load": self.load_descriptor, "climate": self.climate_descriptor,
                   "run_conditions": self.run_conditions}
        return hashlib.sha256(C.canonical_json(payload).encode("utf-8")).hexdigest()

    def provenance(self) -> dict:
        return {"origin": "microrrede", "config_revision": self.config_revision,
                "config_fingerprint": self.config_fingerprint, "spec_fingerprint": self.spec_fingerprint,
                "run_conditions": self.run_conditions,
                "represented": [m.as_dict() for m in self.represented],
                "excluded": [m.as_dict() for m in self.excluded]}


def _inactive_spec() -> dict:
    from orchestrator_runtime import default_model_spec

    spec = default_model_spec()
    for key in ("solar", "wind", "fc", "battery", "thermal"):
        spec[key]["active"] = False
    return spec


def _group_key(kind: str, unit: dict, soc0: float | None = None) -> tuple:
    """Chave de equivalência física no modelo existente (mesma referência e mesma configuração por unidade)."""
    if kind == "pv":            # unit = arranjo
        return (unit["reference"], int(unit["n_series"]), float(unit["soiling_pct"]))
    p = unit["params"]
    if kind == "wind":
        return (p["reference"], bool(p.get("apply_grid_loss") or False))
    if kind == "battery":
        from .derived import battery_derived

        d = battery_derived(p)
        return (p["model_reference"], int(p["model_n_series"]), float(soc0), float(p["soc_min_pct"]),
                float(p["soc_max_pct"]), float(d["c_discharge"][0]), float(d["c_charge"][0]))
    if kind == "pemfc":
        return (p["reference"], p["power_basis"])
    return (unit["id"],)


def _describe_group(kind: str, key: tuple) -> str:
    if kind == "pv":
        return f"{key[0]} · {key[1]} em série · sujeira {key[2]:g}%"
    if kind == "wind":
        return f"{key[0]}{' · perda genérica' if key[1] else ''}"
    if kind == "battery":
        return f"{key[0]} · Ns={key[1]} · SOC {key[2]:g}/{key[3]:g}/{key[4]:g}% · {key[5]:.3g}C/{key[6]:.3g}C"
    if kind == "pemfc":
        return f"{key[0]} · base {key[1]}"
    return str(key)


def build_plan(config: dict, *, revision: int | None = None, fingerprint: str | None = None) -> SimulationPlan:
    from .derived import battery_derived, pv_array_kWp

    spec = _inactive_spec()
    mappings: list[Mapping] = []
    warnings: list[str] = []
    blockers: list[str] = []
    candidates: dict[str, list[dict]] = {k: [] for k in TARGET}
    soc0_map = dict(((config.get("run_conditions") or {}).get("battery_soc0_pct") or {}))
    run_conditions: dict = {"battery_soc0_pct": {}}
    pv_installed = 0.0

    def ok(uid, name, kind, target, reason="", parent=None):
        mappings.append(Mapping(uid, name, kind, REPRESENTED, target, reason, parent))

    def bad(uid, name, kind, reason, parent=None, status=INCOMPATIBLE):
        mappings.append(Mapping(uid, name, kind, status, None, reason, parent))

    for eq in config.get("equipment", []):
        kind = eq["kind"]
        if not eq.get("enabled", True):
            bad(eq["id"], eq["name"], kind, "Desabilitado na Gestão da Microrrede; não entra na rodada.", status=DISABLED)
            continue
        issues = C.errors(C.equipment_issues(eq))
        if issues:
            bad(eq["id"], eq["name"], kind, "; ".join(i.message for i in issues), status=INCOMPLETE)
            continue
        if kind == "pv":
            arrays = eq.get("arrays") or []
            if not arrays:
                bad(eq["id"], eq["name"], kind, "Usina sem arranjos cadastrados.", status=INCOMPLETE)
            for a in arrays:
                label = f"{eq['name']} · {a['name']}"
                kwp, _ = pv_array_kWp(a)
                pv_installed += kwp or 0.0
                if a.get("mode") == "declarado":
                    bad(a["id"], label, kind, "Arranjo com potência nominal declarada, sem módulo identificado: o modelo "
                        "fotovoltaico existente exige o datasheet do módulo e Ns/Np. Potência registrada, não simulada.",
                        parent=eq["id"])
                    continue
                missing = C.array_missing(a)
                if missing:
                    bad(a["id"], label, kind, "faltam: " + ", ".join(missing), parent=eq["id"], status=INCOMPLETE)
                    continue
                candidates["pv"].append({"unit": a, "eq": eq, "label": label})
            continue
        missing = C.missing_required(eq)
        if missing:
            bad(eq["id"], eq["name"], kind, "faltam: " + ", ".join(missing), status=INCOMPLETE)
            continue
        if kind == "battery":
            s0 = soc0_map.get(eq["id"])
            p = eq["params"]
            if s0 is None:
                bad(eq["id"], eq["name"], kind, "SOC inicial da rodada não definido (Simulação → Condições da rodada).",
                    status=INCOMPLETE)
                continue
            if not float(p["soc_min_pct"]) <= float(s0) <= float(p["soc_max_pct"]):
                bad(eq["id"], eq["name"], kind, f"SOC inicial da rodada ({s0:g} %) fora dos limites operacionais "
                    f"[{p['soc_min_pct']:g}, {p['soc_max_pct']:g}] %.", status=INCOMPLETE)
                continue
            for w in battery_derived(p, C.battery_model_energy_kWh(eq))["warnings"]:
                warnings.append(f"{eq['name']}: {w}")
            candidates["battery"].append({"unit": eq, "eq": eq, "label": eq["name"], "soc0": float(s0)})
            continue
        if kind == "pemfc" and eq["params"]["reference"] == C.PEMFC_IMPORT_REF:
            from .modellab import INTEGRATION_PENDING
            bad(eq["id"], eq["name"], kind, INTEGRATION_PENDING)
            continue
        candidates[kind].append({"unit": eq, "eq": eq, "label": eq["name"]})

    # ---- grupos homogêneos (FV por arranjo; eólica, bateria e PEMFC por equipamento)
    for kind in ("pv", "wind", "battery", "pemfc"):
        items = candidates[kind]
        if not items:
            continue
        groups: dict[tuple, list[dict]] = {}
        for it in items:
            groups.setdefault(_group_key(kind, it["unit"], it.get("soc0")), []).append(it)
        parent = (lambda it: it["eq"]["id"]) if kind == "pv" else (lambda it: None)
        if len(groups) > 1:
            desc = " | ".join(_describe_group(kind, k) for k in groups)
            unit_word = "arranjos" if kind == "pv" else "configurações"
            for it in items:
                bad(it["unit"]["id"], it["label"], kind,
                    f"{len(groups)} {unit_word} distintas de {KIND_LABELS[kind]} habilitadas ({desc}). O EMS V1.6 representa "
                    "um único tipo por tecnologia (sem médias entre módulos/configurações diferentes); desabilite ou "
                    "ajuste os que não devem entrar na rodada.", parent=parent(it))
            continue
        key, members = next(iter(groups.items()))
        target = TARGET[kind]
        agg = f"agregado com {len(members) - 1} unidade(s) idêntica(s)" if len(members) > 1 else ""
        if kind == "pv":
            n_par = sum(int(it["unit"]["n_parallel"]) for it in members)
            spec["solar"].update(active=True, module_key=key[0], n_series=key[1], n_parallel=n_par, soiling_losses_pct=key[2])
        elif kind == "wind":
            count = sum(int(it["unit"]["params"]["count"]) for it in members)
            spec["wind"].update(active=True, turbine_key=key[0], turbine_count=count, apply_grid_loss=key[1])
            lo, hi = V16_UI_RANGES["wind_count"]
            if not lo <= count <= hi:
                warnings.append(f"Quantidade total de aerogeradores ({count}) fora da faixa usada na interface V1.6 ({lo}–{hi}).")
        elif kind == "battery":
            model, cell = battery_ref_parts(key[0])
            np_total = sum(int(it["unit"]["params"]["model_n_parallel"]) for it in members)
            spec["battery"].update(active=True, model=model, key=cell, Ns=key[1], Np=np_total, soc0=key[2] / 100.0,
                                   soc_min=key[3] / 100.0, soc_max=key[4] / 100.0, c_desc=key[5], c_carga=key[6])
            run_conditions["battery_soc0_pct"] = {it["unit"]["id"]: it["soc0"] for it in members}
            for name, val in (("battery_Ns", key[1]), ("battery_Np", np_total)):
                lo, hi = V16_UI_RANGES[name]
                if not lo <= val <= hi:
                    warnings.append(f"{name} = {val} fora da faixa usada na interface V1.6 ({lo}–{hi}).")
        elif kind == "pemfc":
            n = sum(int(it["unit"]["params"]["quantity"]) for it in members)
            spec["fc"].update(active=True, N_fc=n, base=key[1])
            lo, hi = V16_UI_RANGES["N_fc"]
            if not lo <= n <= hi:
                warnings.append(f"N_fc = {n} fora da faixa usada na interface V1.6 ({lo}–{hi}).")
        for it in members:
            ok(it["unit"]["id"], it["label"], kind, target, agg, parent=parent(it))

    # ---- térmica: uma única pequena unidade geradora
    th = [it["unit"] for it in candidates["thermal"]]
    for eq in [e for e in th if e["params"]["dynamic"] != "local_generator"]:
        bad(eq["id"], eq["name"], "thermal", "Dinâmica 'Usina termelétrica de grande porte' não é suportada pelo runtime "
            "integrado V1.6 (que usa a pequena unidade geradora). Disponível apenas na bancada Térmica.")
    locals_ = [e for e in th if e["params"]["dynamic"] == "local_generator"]
    if len(locals_) > 1:
        for eq in locals_:
            bad(eq["id"], eq["name"], "thermal", f"{len(locals_)} unidades térmicas habilitadas; o EMS V1.6 representa uma "
                "única unidade térmica (potências e rampas distintas não são agregáveis sem alterar a formulação).")
    elif len(locals_) == 1:
        p = locals_[0]["params"]
        spec["thermal"].update(active=True, pmax_kW=float(p["pmax_kW"]), pmin_kW=float(p["pmin_kW"]),
                               cvu=float(p["cvu_rs_MWh"]), ramp=float(p["ramp_kW_min"] or 0.0),
                               partida=float(p["startup_cost_rs"]))
        ok(locals_[0]["id"], locals_[0]["name"], "thermal", "thermal", "" if p.get("ramp_kW_min") else "sem limite de rampa declarado")

    # ---- clima, demanda e bloqueios
    clim = config.get("climate") or {}
    climate_descriptor: dict = {}
    if spec["solar"]["active"] or spec["wind"]["active"]:
        if clim.get("source") == "csv":
            spec["climate"]["source"] = "CSV climático"
            climate_descriptor = {"source": "csv", "blob": (clim.get("csv") or {}).get("blob")}
        else:
            spec["climate"]["source"] = "Sintético diário"
            climate_descriptor = {"source": "sintetico"}
            warnings.append("Solar/eólica usarão o clima SINTÉTICO diário (demonstração), não medições da instalação.")
    if not any(spec[k]["active"] for k in ("fc", "battery", "thermal")):
        blockers.append("Nenhuma fonte despachável representável (H₂/PEMFC, bateria ou térmica): o EMS exige ao menos uma.")
    load_descriptor = demand_descriptor(config.get("demand") or {})
    if not load_descriptor:
        blockers.append("Demanda da microrrede não definida ou incompleta (Gestão → Demanda e dados).")
    pv_repr = 0.0
    if spec["solar"]["active"]:
        from .derived import pv_module_stc
        pv_repr = pv_module_stc(spec["solar"]["module_key"])["P_W"] * spec["solar"]["n_series"] * spec["solar"]["n_parallel"] / 1000.0

    order = {k: i for i, k in enumerate(("pv", "wind", "battery", "pemfc", "thermal"))}
    pos = {e["id"]: i for i, e in enumerate(config.get("equipment", []))}
    mappings.sort(key=lambda m: (order.get(m.kind, 9), pos.get(m.parent or m.id, 0)))
    return SimulationPlan(spec=spec, mappings=mappings, blockers=blockers, warnings=warnings,
                          load_descriptor=load_descriptor, climate_descriptor=climate_descriptor,
                          config_revision=revision, config_fingerprint=fingerprint, run_conditions=run_conditions,
                          pv_installed_kWp=pv_installed, pv_represented_kWp=pv_repr)


# ------------------------------------------------------------------ demanda e clima
def demand_descriptor(dem: dict) -> dict:
    """Descritor mínimo e suficiente para reconstruir a carga; vazio se incompleto."""
    src = dem.get("source")
    if src == "walkforward":
        w = dem.get("walkforward") or {}
        if all(w.get(k) is not None for k in ("scenario", "profile", "start_hour")):
            return {"source": "walkforward", **{k: w[k] for k in ("scenario", "profile", "start_hour")}}
    elif src == "copel":
        c = dem.get("copel") or {}
        if all(c.get(k) is not None for k in ("day", "start_h", "duration_min")):
            return {"source": "copel", **{k: c[k] for k in ("day", "start_h", "duration_min")}}
    elif src == "csv":
        c = dem.get("csv") or {}
        if c.get("blob") and c.get("start_min") is not None and c.get("duration_min"):
            return {"source": "csv", **{k: c[k] for k in ("blob", "filename", "start_min", "duration_min")}}
    return {}


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    """Mesma leitura da V1.6 (``pd.read_csv(sep=None, engine='python')``)."""
    return pd.read_csv(io.BytesIO(data), sep=None, engine="python")


def build_load(descriptor: dict, get_blob=None):
    """Reconstrói o ``PerfilCarga`` exatamente pelas funções da V1.6 (``ems_integration.ponte``)."""
    from ems_integration import ponte

    src = descriptor.get("source")
    if src == "walkforward":
        return ponte.carga_walkforward(descriptor["scenario"], descriptor["profile"], int(descriptor["start_hour"]))
    if src == "copel":
        start = int(descriptor["start_h"])
        return ponte.recortar(ponte.carga_copel(descriptor["day"]), start * 60,
                              min(int(descriptor["duration_min"]), 1439 - start * 60))
    if src == "csv":
        if get_blob is None:
            raise ValueError("Leitor de dados armazenados ausente.")
        raw = read_csv_bytes(get_blob(descriptor["blob"]))
        base = ponte.carga_de_dataframe(raw, descriptor.get("filename") or "CSV da instalação")
        return ponte.recortar(base, float(descriptor["start_min"]), float(descriptor["duration_min"]))
    raise ValueError("Demanda não definida.")


def build_climate_raw(descriptor: dict, get_blob=None) -> pd.DataFrame | None:
    if descriptor.get("source") == "csv":
        if get_blob is None:
            raise ValueError("Leitor de dados armazenados ausente.")
        return read_csv_bytes(get_blob(descriptor["blob"]))
    return None


def spec_copy(plan: SimulationPlan) -> dict:
    return copy.deepcopy(plan.spec)


__all__: list[Any] = ["DISABLED", "INCOMPATIBLE", "INCOMPLETE", "REPRESENTED", "STATUS_LABELS", "Mapping",
                      "SimulationPlan", "build_climate_raw", "build_load", "build_plan", "demand_descriptor"]
