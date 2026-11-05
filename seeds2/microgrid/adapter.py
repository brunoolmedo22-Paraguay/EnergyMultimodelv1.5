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
from .references import KIND_LABELS, PEMFC_REF_KEY, battery_ref_parts

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

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "kind_label": KIND_LABELS.get(self.kind, self.kind),
                "status": self.status, "status_label": STATUS_LABELS[self.status], "target": self.target,
                "reason": self.reason}


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
        payload = {"spec": self.spec, "load": self.load_descriptor, "climate": self.climate_descriptor}
        return hashlib.sha256(C.canonical_json(payload).encode("utf-8")).hexdigest()

    def provenance(self) -> dict:
        return {"origin": "microrrede", "config_revision": self.config_revision,
                "config_fingerprint": self.config_fingerprint, "spec_fingerprint": self.spec_fingerprint,
                "represented": [m.as_dict() for m in self.represented],
                "excluded": [m.as_dict() for m in self.excluded]}


def _inactive_spec() -> dict:
    from orchestrator_runtime import default_model_spec

    spec = default_model_spec()
    for key in ("solar", "wind", "fc", "battery", "thermal"):
        spec[key]["active"] = False
    return spec


def _group_key(eq: dict) -> tuple:
    p = eq["params"]
    k = eq["kind"]
    if k == "pv":
        return (p["reference"], int(p["n_series"]), float(p["soiling_pct"]))
    if k == "wind":
        return (p["reference"], bool(p.get("apply_grid_loss") or False))
    if k == "battery":
        return (p["reference"], int(p["n_series"]), float(p["soc0_pct"]), float(p["soc_min_pct"]),
                float(p["soc_max_pct"]), float(p["c_discharge"]), float(p["c_charge"]))
    if k == "pemfc":
        return (p["reference"], p["power_basis"])
    return (eq["id"],)


def _describe_group(kind: str, key: tuple) -> str:
    if kind == "pv":
        return f"{key[0]} · {key[1]} em série · sujeira {key[2]:g}%"
    if kind == "wind":
        return f"{key[0]}{' · perda genérica' if key[1] else ''}"
    if kind == "battery":
        return f"{key[0]} · Ns={key[1]} · SOC {key[2]:g}/{key[3]:g}/{key[4]:g}% · {key[5]:g}C/{key[6]:g}C"
    if kind == "pemfc":
        return f"{key[0]} · base {key[1]}"
    return str(key)


def build_plan(config: dict, *, revision: int | None = None, fingerprint: str | None = None) -> SimulationPlan:
    spec = _inactive_spec()
    mappings: list[Mapping] = []
    warnings: list[str] = []
    blockers: list[str] = []
    candidates: dict[str, list[dict]] = {k: [] for k in TARGET}

    for eq in config.get("equipment", []):
        base = dict(id=eq["id"], name=eq["name"], kind=eq["kind"])
        if not eq.get("enabled", True):
            mappings.append(Mapping(**base, status=DISABLED, reason="Desabilitado na Gestão da Microrrede; não entra na rodada."))
            continue
        issues = C.errors(C.equipment_issues(eq))
        missing = C.missing_required(eq)
        if issues or missing:
            why = "; ".join([i.message for i in issues] + ([f"faltam: {', '.join(missing)}"] if missing else []))
            mappings.append(Mapping(**base, status=INCOMPLETE, reason=why))
            continue
        candidates[eq["kind"]].append(eq)

    def ok(eq: dict, target: str, reason: str = "") -> None:
        mappings.append(Mapping(eq["id"], eq["name"], eq["kind"], REPRESENTED, target, reason))

    def bad(eq: dict, reason: str) -> None:
        mappings.append(Mapping(eq["id"], eq["name"], eq["kind"], INCOMPATIBLE, None, reason))

    # ---- grupos homogêneos (pv, wind, battery, pemfc)
    for kind in ("pv", "wind", "battery", "pemfc"):
        eqs = candidates[kind]
        if not eqs:
            continue
        groups: dict[tuple, list[dict]] = {}
        for eq in eqs:
            groups.setdefault(_group_key(eq), []).append(eq)
        if len(groups) > 1:
            desc = " | ".join(_describe_group(kind, k) for k in groups)
            for eq in eqs:
                bad(eq, f"{len(groups)} configurações distintas de {KIND_LABELS[kind]} habilitadas ({desc}). O EMS V1.6 "
                        "representa um único tipo por tecnologia; desabilite as que não devem entrar na rodada.")
            continue
        key, members = next(iter(groups.items()))
        target = TARGET[kind]
        agg = f"agregado com {len(members) - 1} equipamento(s) idêntico(s)" if len(members) > 1 else ""
        if kind == "pv":
            spec["solar"].update(active=True, module_key=key[0], n_series=key[1],
                                 n_parallel=sum(int(e["params"]["n_parallel"]) for e in members), soiling_losses_pct=key[2])
        elif kind == "wind":
            count = sum(int(e["params"]["count"]) for e in members)
            spec["wind"].update(active=True, turbine_key=key[0], turbine_count=count, apply_grid_loss=key[1])
            lo, hi = V16_UI_RANGES["wind_count"]
            if not lo <= count <= hi:
                warnings.append(f"Quantidade total de aerogeradores ({count}) fora da faixa usada na interface V1.6 ({lo}–{hi}).")
        elif kind == "battery":
            model, cell = battery_ref_parts(key[0])
            np_total = sum(int(e["params"]["n_parallel"]) for e in members)
            spec["battery"].update(active=True, model=model, key=cell, Ns=key[1], Np=np_total, soc0=key[2] / 100.0,
                                   soc_min=key[3] / 100.0, soc_max=key[4] / 100.0, c_desc=key[5], c_carga=key[6])
            for name, val in (("battery_Ns", key[1]), ("battery_Np", np_total)):
                lo, hi = V16_UI_RANGES[name]
                if not lo <= val <= hi:
                    warnings.append(f"{name} = {val} fora da faixa usada na interface V1.6 ({lo}–{hi}).")
        elif kind == "pemfc":
            if key[0] != PEMFC_REF_KEY:
                for eq in members:
                    bad(eq, "Perfil PEMFC não suportado pelo motor atual.")
                continue
            n = sum(int(e["params"]["quantity"]) for e in members)
            spec["fc"].update(active=True, N_fc=n, base=key[1])
            lo, hi = V16_UI_RANGES["N_fc"]
            if not lo <= n <= hi:
                warnings.append(f"N_fc = {n} fora da faixa usada na interface V1.6 ({lo}–{hi}).")
        for eq in members:
            ok(eq, target, agg)

    # ---- térmica: uma única pequena unidade geradora
    th = candidates["thermal"]
    plants = [e for e in th if e["params"]["dynamic"] != "local_generator"]
    for eq in plants:
        bad(eq, "Dinâmica 'Usina termelétrica de grande porte' não é suportada pelo runtime integrado V1.6 "
                "(que usa a pequena unidade geradora). Disponível apenas na bancada Térmica.")
    locals_ = [e for e in th if e["params"]["dynamic"] == "local_generator"]
    if len(locals_) > 1:
        for eq in locals_:
            bad(eq, f"{len(locals_)} unidades térmicas habilitadas; o EMS V1.6 representa uma única unidade térmica "
                    "(potências e rampas distintas não são agregáveis sem alterar a formulação).")
    elif len(locals_) == 1:
        p = locals_[0]["params"]
        spec["thermal"].update(active=True, pmax_kW=float(p["pmax_kW"]), pmin_kW=float(p["pmin_kW"]),
                               cvu=float(p["cvu_rs_MWh"]), ramp=float(p["ramp_kW_min"] or 0.0),
                               partida=float(p["startup_cost_rs"]))
        ok(locals_[0], "thermal", "" if p.get("ramp_kW_min") else "sem limite de rampa declarado")

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
    dem = config.get("demand") or {}
    load_descriptor = demand_descriptor(dem)
    if not load_descriptor:
        blockers.append("Demanda da microrrede não definida ou incompleta (Gestão → Demanda e dados).")

    order = {k: i for i, k in enumerate(("pv", "wind", "battery", "pemfc", "thermal"))}
    ids = [e["id"] for e in config.get("equipment", [])]
    mappings.sort(key=lambda m: (order.get(m.kind, 9), ids.index(m.id) if m.id in ids else 0))
    return SimulationPlan(spec=spec, mappings=mappings, blockers=blockers, warnings=warnings,
                          load_descriptor=load_descriptor, climate_descriptor=climate_descriptor,
                          config_revision=revision, config_fingerprint=fingerprint)


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
