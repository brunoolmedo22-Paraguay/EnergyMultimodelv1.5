"""Documento de configuração da ÚNICA microrrede desta instalação (esquema v2).

Separação de domínio (Piso 1 — refinamento):

* **Inventário físico permanente** — ``equipment`` (dados de placa/datasheet, quantidades, limites);
* **Referências técnicas** — catálogos lidos em ``references.py`` (somente leitura);
* **Parametrização do modelo científico** — grupo "modelo" da bateria (célula, Ns/Np), separado do datasheet;
* **Condições de simulação** — ``run_conditions`` (p. ex. SOC inicial da rodada), fora do inventário;
* **Modelo lógico de balanço** — ``energy_balance`` (sem barramentos, tensões ou acoplamentos fictícios).

Não há aqui nenhuma equação dos modelos. Valores ausentes são PERMITIDOS (o usuário não é obrigado a inventar
dados): apenas impedem que o equipamento seja "tecnicamente configurado" para a simulação.
Migração de documentos antigos: ``migrations.py``.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .references import (KINDS, PEMFC_REF_KEY, THERMAL_DYNAMIC_KEYS, battery_references, pv_references,
                         thermal_fuel_presets, wind_references)

DOC_SCHEMA_VERSION = 2
EQUIPMENT_ID_RE = re.compile(r"^eq-[0-9a-f]{12}$")
ARRAY_ID_RE = re.compile(r"^arr-[0-9a-f]{12}$")
PEMFC_IMPORT_REF = "modellab_import"

NATURE_OPTIONS = {
    "industrial": "Industrial",
    "laboratorio": "Laboratório / pesquisa",
    "comercial": "Comercial / serviços",
    "rural": "Rural / agroindustrial",
    "transporte": "Embarcação / transporte",
    "comunitaria": "Comunitária / residencial",
    "outra": "Outra",
}
OPERATION_MODE_OPTIONS = {
    "isolada": "Isolada (off-grid)",
    "conectada": "Conectada à rede",
    "conectada_ilhamento": "Conectada, com capacidade declarada de ilhamento",
    "nao_definido": "Ainda não definido",
}
GRID_CONNECTION_OPTIONS = {"isolada": "Sem conexão com a rede", "conectada": "Conectada à rede de distribuição",
                           "nao_declarada": "Não declarada"}
LOCATION_SOURCES = {"manual": "Informada manualmente", "navegador": "Geolocalização do navegador (confirmada)",
                    "migrado": "Migrada da configuração anterior"}
DEMAND_SOURCES = {
    "nao_definida": "Ainda não definida",
    "walkforward": "Perfil de referência walk-forward (embarcação, 2 h)",
    "copel": "Curva típica COPEL B1",
    "csv": "CSV importado pela instalação",
}
PROVENANCE_KINDS = {
    "medido": "Medido na instalação",
    "sintetico": "Sintético / gerado",
    "referencia": "Conjunto de referência incluído no software (não medido nesta instalação)",
    "nao_declarado": "Procedência não declarada",
}
CLIMATE_SOURCES = {"sintetico": "Sintético diário (explícito, para demonstração)", "csv": "CSV climático importado"}
PEMFC_POWER_BASIS = {"entregue": "Potência entregue (líquida)", "stack": "Potência do stack (legado)"}
PV_ARRAY_MODES = {"modulo": "Módulos identificados (datasheet)", "declarado": "Potência nominal declarada"}
BATTERY_CHEMISTRIES = {
    "li_lfp": "Íon-lítio LFP", "li_nmc": "Íon-lítio NMC", "li_outro": "Íon-lítio (outra química)",
    "chumbo_acido": "Chumbo-ácido", "nicd": "Níquel-cádmio (NiCd)", "nimh": "Níquel-hidreto metálico (NiMH)",
    "outra": "Outra",
}
SOC_LIMIT_SOURCES = {"sugerido": "Valor inicial sugerido pelo SEEDS2 (não é limite do fabricante)",
                     "fabricante": "Documentado pelo fabricante", "instalacao": "Definido pela instalação",
                     "migrado": "Migrado da configuração anterior"}
SOC_MIN_DEFAULT, SOC_MAX_DEFAULT = 20.0, 80.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ======================================================== especificação de parâmetros
@dataclass(frozen=True)
class ParamSpec:
    name: str
    label: str
    unit: str
    type: str                       # "int" | "float" | "choice" | "bool" | "text"
    required: bool = True           # obrigatório para SIMULAR (não para registrar)
    min: float | None = None
    max: float | None = None
    min_exclusive: bool = False
    max_exclusive: bool = False
    help: str = ""
    default: Any = None             # opções de modelagem e valores iniciais explicitamente pedidos (SOC 20/80, sujeira 0)
    group: str = "principal"        # "principal" (datasheet/inventário) | "modelo" (parametrização científica)


def _choices(kind: str, name: str) -> dict[str, str]:
    if kind in ("pv", "pv_array") and name == "reference":
        return {k: r.label for k, r in pv_references().items()}
    if kind == "pv_array" and name == "mode":
        return dict(PV_ARRAY_MODES)
    if kind == "wind" and name == "reference":
        return {k: r.label for k, r in wind_references().items()}
    if kind == "battery" and name == "model_reference":
        return {k: r.label for k, r in battery_references().items()}
    if kind == "battery" and name == "chemistry":
        return dict(BATTERY_CHEMISTRIES)
    if kind == "battery" and name == "soc_limits_source":
        return dict(SOC_LIMIT_SOURCES)
    if kind == "pemfc" and name == "reference":
        return {PEMFC_REF_KEY: "Sistema PEMFC equivalente · Horizon VLIIPro50-22 (aproximado)",
                PEMFC_IMPORT_REF: "Dispositivo importado do PEMFC ModelLab"}
    if kind == "pemfc" and name == "power_basis":
        return dict(PEMFC_POWER_BASIS)
    if kind == "thermal" and name == "dynamic":
        from .references import thermal_dynamics
        return thermal_dynamics()
    if kind == "thermal" and name == "fuel_preset":
        return {k: k for k in thermal_fuel_presets()}
    return {}


def choices(kind: str, name: str) -> dict[str, str]:
    return _choices(kind, name)


PARAM_SPECS: dict[str, tuple[ParamSpec, ...]] = {
    # A usina FV não tem parâmetros próprios: é composta por arranjos (ARRAY_SPECS).
    "pv": (),
    "wind": (
        ParamSpec("reference", "Aerogerador (referência)", "", "choice", help="Curva original de config/wind_turbine_database.py."),
        ParamSpec("count", "Quantidade de aerogeradores", "unidades", "int", min=1),
        ParamSpec("apply_grid_loss", "Aplicar perda genérica gerador→rede do módulo eólico", "", "bool", default=False,
                  help="Opção do modelo eólico existente (perda genérica fixa)."),
    ),
    "battery": (
        ParamSpec("manufacturer", "Fabricante", "", "text", required=False),
        ParamSpec("model", "Modelo", "", "text", required=False),
        ParamSpec("chemistry", "Tecnologia / química", "", "choice", required=False),
        ParamSpec("energy_kWh", "Energia nominal", "kWh", "float", required=False, min=0, min_exclusive=True),
        ParamSpec("capacity_Ah", "Capacidade nominal", "Ah", "float", required=False, min=0, min_exclusive=True),
        ParamSpec("voltage_V", "Tensão nominal", "V", "float", required=False, min=0, min_exclusive=True),
        ParamSpec("power_kW", "Potência nominal", "kW", "float", required=False, min=0, min_exclusive=True),
        ParamSpec("i_charge_max_A", "Corrente máx. contínua de carga", "A", "float", required=False, min=0, min_exclusive=True),
        ParamSpec("i_discharge_max_A", "Corrente máx. contínua de descarga", "A", "float", required=False, min=0, min_exclusive=True),
        ParamSpec("c_charge_max", "Taxa máxima de carga", "C", "float", required=False, min=0, min_exclusive=True),
        ParamSpec("c_discharge_max", "Taxa máxima de descarga", "C", "float", required=False, min=0, min_exclusive=True),
        ParamSpec("soc_min_pct", "SOC mínimo operacional", "%", "float", min=0, max=100, default=SOC_MIN_DEFAULT),
        ParamSpec("soc_max_pct", "SOC máximo operacional", "%", "float", min=0, max=100, default=SOC_MAX_DEFAULT),
        ParamSpec("soc_limits_source", "Origem dos limites de SOC", "", "choice", required=False, default="sugerido"),
        ParamSpec("model_reference", "Modelo e célula de referência", "", "choice", group="modelo",
                  help="Tremblay–Dessaint ou circuito 2 RC (models/battery_model.py)."),
        ParamSpec("model_n_series", "Células em série (Ns)", "células", "int", min=1, group="modelo"),
        ParamSpec("model_n_parallel", "Ramos em paralelo (Np)", "ramos", "int", min=1, group="modelo"),
    ),
    "pemfc": (
        ParamSpec("reference", "Perfil / dispositivo PEMFC", "", "choice", default=PEMFC_REF_KEY),
        ParamSpec("quantity", "Sistemas/stacks instalados", "unidades", "int", min=1),
        ParamSpec("power_basis", "Base do envelope de potência no EMS", "", "choice", default="entregue",
                  help="Convenção do EMS V1.6: 'entregue' já é potência líquida (ηFC=1 no balanço)."),
    ),
    "thermal": (
        ParamSpec("dynamic", "Dinâmica operacional", "", "choice"),
        ParamSpec("fuel_preset", "Combustível (preset acadêmico de CVU)", "", "choice", required=False,
                  help="Apenas rótulo/origem do CVU sugerido; não representa usina real."),
        ParamSpec("pmax_kW", "Potência máxima", "kW", "float", min=0, min_exclusive=True),
        ParamSpec("pmin_kW", "Potência mínima técnica", "kW", "float", min=0),
        ParamSpec("cvu_rs_MWh", "CVU", "R$/MWh", "float", min=0),
        ParamSpec("ramp_kW_min", "Rampa máxima", "kW/min", "float", required=False, min=0, min_exclusive=True,
                  help="Vazio = sem limite de rampa declarado."),
        ParamSpec("startup_cost_rs", "Custo de partida", "R$", "float", min=0),
    ),
}
PARAM_INDEX = {kind: {p.name: p for p in specs} for kind, specs in PARAM_SPECS.items()}

ARRAY_SPECS: tuple[ParamSpec, ...] = (
    ParamSpec("mode", "Forma de cadastro", "", "choice", default="modulo"),
    ParamSpec("reference", "Módulo FV (referência)", "", "choice", help="Módulo do catálogo config/pv_database.py."),
    ParamSpec("n_series", "Módulos em série por string", "módulos", "int", min=1),
    ParamSpec("n_parallel", "Strings em paralelo", "strings", "int", min=1),
    ParamSpec("soiling_pct", "Perdas por sujeira", "%", "float", min=0, max=100, max_exclusive=True, default=0.0,
              help="0 % = hipótese de perdas por sujeira NÃO consideradas (não é uma medição de limpeza)."),
    ParamSpec("declared_kWp", "Potência nominal declarada", "kWp", "float", min=0, min_exclusive=True),
    ParamSpec("declared_source", "Procedência da potência declarada", "", "text", required=False),
)
ARRAY_INDEX = {p.name: p for p in ARRAY_SPECS}
ARRAY_FIELDS = set(ARRAY_INDEX) | {"id", "name", "notes", "soiling_default", "migrated_from"}
# Parâmetros obrigatórios para o arranjo ser "tecnicamente configurado", conforme a forma de cadastro.
ARRAY_REQUIRED = {"modulo": ("reference", "n_series", "n_parallel", "soiling_pct"), "declarado": ("declared_kWp",)}


# ======================================================== construção
def new_equipment_id() -> str:
    return f"eq-{uuid.uuid4().hex[:12]}"


def new_array_id() -> str:
    return f"arr-{uuid.uuid4().hex[:12]}"


def new_array(name: str = "", **values: Any) -> dict:
    arr = {"id": values.pop("id", None) or new_array_id(), "name": str(name).strip(), "notes": values.pop("notes", "") or ""}
    arr.update({p.name: p.default for p in ARRAY_SPECS})
    arr["soiling_default"] = True               # 0 % aplicado como hipótese padrão até o usuário declarar
    if "soiling_pct" in values:
        arr["soiling_default"] = False
    arr.update(values)
    unknown = set(arr) - ARRAY_FIELDS
    if unknown:
        raise ValueError(f"Campos desconhecidos para arranjo: {sorted(unknown)}")
    return arr


def new_equipment(kind: str, name: str, **fields: Any) -> dict:
    if kind not in KINDS:
        raise ValueError(f"Tipo de equipamento desconhecido: {kind!r}")
    now = utc_now()
    params = {p.name: p.default for p in PARAM_SPECS[kind]}
    params.update(fields.pop("params", {}) or {})
    eq = {
        "id": fields.pop("id", None) or new_equipment_id(),
        "kind": kind,
        "name": str(name).strip(),
        "tag": fields.pop("tag", "") or "",
        "serial": fields.pop("serial", "") or "",
        "enabled": bool(fields.pop("enabled", True)),
        "params": params,
        "notes": fields.pop("notes", "") or "",
        "created_at": now,
        "updated_at": now,
    }
    if kind == "pv":
        eq["arrays"] = list(fields.pop("arrays", []) or [])
    if kind == "pemfc":
        eq["imported"] = fields.pop("imported", None)
    if fields:
        raise ValueError(f"Campos desconhecidos para equipamento: {sorted(fields)}")
    return eq


def new_location() -> dict:
    return {"country": "", "region": "", "city": "", "address": "", "latitude": None, "longitude": None,
            "timezone": "", "source": "manual", "accuracy_m": None, "captured_at": None, "timezone_suggested": ""}


def new_config(name: str = "") -> dict:
    now = utc_now()
    return {
        "schema_version": DOC_SCHEMA_VERSION,
        "installation": {
            "uid": uuid.uuid4().hex,
            "name": str(name).strip(),
            "description": "",
            "nature": None,
            "operation_mode": None,
            "location": new_location(),
            "created_at": now,
        },
        "commissioning": {"completed": False, "step": 1, "completed_at": None},
        "equipment": [],
        "retired": [],
        "energy_balance": {"grid_connection": "nao_declarada"},
        "demand": {
            "source": "nao_definida",
            "walkforward": {"scenario": None, "profile": None, "start_hour": None},
            "copel": {"day": None, "start_h": None, "duration_min": None},
            # {"blob": sha256, "filename", "start_min", "duration_min", "rows", "columns", "t0"}
            "csv": None,
            "provenance": "nao_declarado",
            "timezone": "",
            "notes": "",
        },
        "climate": {"source": "sintetico", "csv": None, "provenance": "sintetico", "notes": ""},
        "run_conditions": {"battery_soc0_pct": {}},
        "migrations": [],
    }


def find_equipment(config: dict, eq_id: str) -> dict | None:
    return next((e for e in config.get("equipment", []) if e.get("id") == eq_id), None)


def add_equipment(config: dict, eq: dict) -> dict:
    if find_equipment(config, eq["id"]) is not None:
        raise ValueError(f"Identificador duplicado: {eq['id']}")
    config.setdefault("equipment", []).append(eq)
    return eq


EDITABLE_FIELDS = ("name", "tag", "serial", "enabled", "notes", "arrays", "imported")


def update_equipment(config: dict, eq_id: str, **changes: Any) -> dict:
    eq = find_equipment(config, eq_id)
    if eq is None:
        raise KeyError(f"Equipamento inexistente: {eq_id}")
    if "id" in changes or "kind" in changes:
        raise ValueError("Identificador e tipo de um equipamento são imutáveis.")
    params = changes.pop("params", None)
    for k, v in changes.items():
        if k not in EDITABLE_FIELDS or (k == "arrays" and eq["kind"] != "pv") or (k == "imported" and eq["kind"] != "pemfc"):
            raise ValueError(f"Campo não editável: {k}")
        eq[k] = v.strip() if isinstance(v, str) else copy.deepcopy(v)
    if params is not None:
        unknown = set(params) - set(PARAM_INDEX[eq["kind"]])
        if unknown:
            raise ValueError(f"Parâmetros desconhecidos para {eq['kind']}: {sorted(unknown)}")
        eq["params"].update(params)
    eq["updated_at"] = utc_now()
    return eq


def retire_equipment(config: dict, eq_id: str, reason: str = "") -> dict:
    """Retira o equipamento do inventário ativo; o registro fica em ``retired`` (auditoria)."""
    eq = find_equipment(config, eq_id)
    if eq is None:
        raise KeyError(f"Equipamento inexistente: {eq_id}")
    config["equipment"] = [e for e in config["equipment"] if e["id"] != eq_id]
    (config.get("run_conditions") or {}).get("battery_soc0_pct", {}).pop(eq_id, None)
    rec = copy.deepcopy(eq)
    rec["retired_at"] = utc_now()
    rec["retired_reason"] = str(reason or "")
    config.setdefault("retired", []).append(rec)
    return rec


# ======================================================== validação
@dataclass(frozen=True)
class Issue:
    level: str          # "error" bloqueia o salvamento; "warning" apenas informa
    path: str
    message: str


def _num_ok(spec: ParamSpec, v: Any) -> str | None:
    if spec.type == "int":
        if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, float) and v.is_integer())):
            return "deve ser um número inteiro"
    elif spec.type == "float":
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return "deve ser numérico"
        if v != v or v in (float("inf"), float("-inf")):
            return "deve ser finito"
    if spec.min is not None and (v < spec.min or (spec.min_exclusive and v == spec.min)):
        return f"deve ser {'>' if spec.min_exclusive else '≥'} {spec.min:g}{(' ' + spec.unit) if spec.unit else ''}"
    if spec.max is not None and (v > spec.max or (spec.max_exclusive and v == spec.max)):
        return f"deve ser {'<' if spec.max_exclusive else '≤'} {spec.max:g}{(' ' + spec.unit) if spec.unit else ''}"
    return None


def _check_value(kind: str, spec: ParamSpec, value: Any) -> str | None:
    if value is None:
        return None
    if spec.type == "choice":
        opts = _choices(kind, spec.name)
        if not isinstance(value, str):
            return "deve ser um identificador de referência (texto)"
        return None if value in opts else f"valor {value[:80]!r} não pertence às referências disponíveis"
    if spec.type == "bool":
        return None if isinstance(value, bool) else "deve ser verdadeiro/falso"
    if spec.type == "text":
        return None if isinstance(value, str) and len(value) <= 500 else "deve ser texto (até 500 caracteres)"
    return _num_ok(spec, value)


def validate_param(kind: str, name: str, value: Any) -> str | None:
    return _check_value(kind, PARAM_INDEX[kind][name], value)


def array_issues(arr: Any, prefix: str) -> list[Issue]:
    if not isinstance(arr, dict):
        return [Issue("error", prefix, "Arranjo inválido.")]
    out: list[Issue] = []
    if not ARRAY_ID_RE.match(str(arr.get("id", ""))):
        out.append(Issue("error", f"{prefix}.id", "Identificador de arranjo inválido."))
    if not isinstance(arr.get("name"), str) or not arr["name"].strip():
        out.append(Issue("error", f"{prefix}.name", "Nome do arranjo é obrigatório."))
    for k in ("notes",):
        if not isinstance(arr.get(k, ""), str):
            out.append(Issue("error", f"{prefix}.{k}", "Deve ser texto."))
    if not isinstance(arr.get("soiling_default", False), bool):
        out.append(Issue("error", f"{prefix}.soiling_default", "Estrutura inválida."))
    for u in sorted(set(arr) - ARRAY_FIELDS):
        out.append(Issue("error", f"{prefix}.{u}", "Campo desconhecido para arranjo."))
    if arr.get("mode") not in PV_ARRAY_MODES:
        out.append(Issue("error", f"{prefix}.mode", "Forma de cadastro do arranjo inválida."))
    for spec in ARRAY_SPECS:
        if spec.name == "mode":
            continue
        msg = _check_value("pv_array", spec, arr.get(spec.name))
        if msg:
            out.append(Issue("error", f"{prefix}.{spec.name}", f"{spec.label}: {msg}."))
    return out


def array_missing(arr: dict) -> list[str]:
    req = ARRAY_REQUIRED.get(arr.get("mode"), ())
    return [ARRAY_INDEX[k].label for k in req if arr.get(k) is None]


def _imported_issues(imp: Any, prefix: str) -> list[Issue]:
    if imp is None:
        return []
    if not isinstance(imp, dict):
        return [Issue("error", prefix, "Dados de importação inválidos.")]
    out = []
    if not re.fullmatch(r"[0-9a-f]{64}", str(imp.get("blob", ""))):
        out.append(Issue("error", f"{prefix}.blob", "Pacote original do dispositivo importado ausente."))
    if not isinstance(imp.get("device"), dict) or not isinstance(imp.get("calibrations"), list):
        out.append(Issue("error", prefix, "Metadados do dispositivo importado incompletos."))
    return out


def equipment_issues(eq: dict, prefix: str = "") -> list[Issue]:
    p = prefix or f"equipment[{eq.get('id')}]"
    out: list[Issue] = []
    kind = eq.get("kind")
    if kind not in KINDS:
        return [Issue("error", f"{p}.kind", f"Tipo desconhecido: {kind!r}")]
    if not EQUIPMENT_ID_RE.match(str(eq.get("id", ""))):
        out.append(Issue("error", f"{p}.id", "Identificador inválido (formato esperado eq-xxxxxxxxxxxx)."))
    if not str(eq.get("name", "")).strip():
        out.append(Issue("error", f"{p}.name", "Nome do equipamento é obrigatório."))
    for k in ("tag", "serial", "notes"):
        if not isinstance(eq.get(k, ""), str):
            out.append(Issue("error", f"{p}.{k}", "Deve ser texto."))
    if not isinstance(eq.get("enabled"), bool):
        out.append(Issue("error", f"{p}.enabled", "Estado habilitado deve ser verdadeiro/falso."))
    params = eq.get("params")
    if not isinstance(params, dict):
        return out + [Issue("error", f"{p}.params", "Parâmetros ausentes.")]
    for u in sorted(set(params) - set(PARAM_INDEX[kind])):
        out.append(Issue("error", f"{p}.params.{u}", "Parâmetro desconhecido para este tipo."))
    for name, value in params.items():
        if name in PARAM_INDEX[kind]:
            msg = validate_param(kind, name, value)
            if msg:
                out.append(Issue("error", f"{p}.params.{name}", f"{PARAM_INDEX[kind][name].label}: {msg}."))
    g = params.get
    if kind == "pv":
        arrays = eq.get("arrays")
        if not isinstance(arrays, list):
            out.append(Issue("error", f"{p}.arrays", "Lista de arranjos ausente ou inválida."))
        else:
            seen = set()
            for i, a in enumerate(arrays):
                out.extend(array_issues(a, f"{p}.arrays[{i}]"))
                if isinstance(a, dict):
                    if a.get("id") in seen:
                        out.append(Issue("error", f"{p}.arrays[{i}].id", "Identificador de arranjo duplicado."))
                    seen.add(a.get("id"))
    if kind == "battery":
        lo, hi = g("soc_min_pct"), g("soc_max_pct")
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo >= hi:
            out.append(Issue("error", f"{p}.params.soc_min_pct", "SOC mínimo deve ser menor que o SOC máximo."))
    if kind == "pemfc":
        out.extend(_imported_issues(eq.get("imported"), f"{p}.imported"))
        if g("reference") == PEMFC_IMPORT_REF and not eq.get("imported"):
            out.append(Issue("error", f"{p}.imported", "Referência 'importado do ModelLab' sem dispositivo importado."))
    if kind == "thermal":
        if g("pmin_kW") is not None and g("pmax_kW") is not None and g("pmin_kW") > g("pmax_kW"):
            out.append(Issue("error", f"{p}.params.pmin_kW", "Potência mínima técnica não pode superar a potência máxima."))
    return out


def missing_required(eq: dict) -> list[str]:
    """O que ainda falta para o equipamento ser tecnicamente configurado PARA A SIMULAÇÃO (rótulos)."""
    kind = eq.get("kind")
    params = eq.get("params") or {}
    if kind == "pv":
        arrays = eq.get("arrays") or []
        if not arrays:
            return ["ao menos um arranjo"]
        out = []
        for a in arrays:
            out += [f"{a.get('name') or 'arranjo'}: {m}" for m in array_missing(a)]
        return out
    if kind not in PARAM_SPECS:
        return []
    out = [s.label for s in PARAM_SPECS[kind] if s.required and params.get(s.name) is None]
    if kind == "wind":
        ref = wind_references().get(params.get("reference"))
        if ref and ref.summary.get("Integração") == "curve_analysis_only":
            out.append(ref.summary["Limitação"])
    if kind == "battery":
        from .derived import battery_derived
        d = battery_derived(params)
        for side, label in (("c_charge", "Taxa máxima de carga (ou corrente máx. + capacidade)"),
                            ("c_discharge", "Taxa máxima de descarga (ou corrente máx. + capacidade)")):
            if d[side][0] is None:
                out.append(label)
    return out


def is_configured(eq: dict) -> bool:
    return not missing_required(eq) and not [i for i in equipment_issues(eq) if i.level == "error"]


def battery_physically_registered(eq: dict) -> bool:
    """Banco descrito por ao menos uma grandeza nominal de datasheet (energia, capacidade ou tensão)."""
    p = eq.get("params") or {}
    return any(p.get(k) is not None for k in ("energy_kWh", "capacity_Ah", "voltage_V"))


def battery_model_parametrized(eq: dict) -> bool:
    p = eq.get("params") or {}
    return all(p.get(k) is not None for k in ("model_reference", "model_n_series", "model_n_parallel"))


def _str_field(obj: dict, key: str, path: str, out: list[Issue], required: bool = False, maxlen: int = 2000) -> None:
    v = obj.get(key)
    if v is None and not required:
        return
    if not isinstance(v, str) or len(v) > maxlen:
        out.append(Issue("error", f"{path}.{key}", "Deve ser texto."))
    elif required and not v.strip():
        out.append(Issue("error", f"{path}.{key}", "Campo obrigatório."))


def validate_location(loc: Any, path: str = "installation.location") -> list[Issue]:
    if not isinstance(loc, dict):
        return [Issue("error", path, "Estrutura inválida.")]
    out: list[Issue] = []
    for k in ("country", "region", "city", "address", "timezone", "timezone_suggested"):
        _str_field(loc, k, path, out, maxlen=300)
    for k, lim in (("latitude", 90.0), ("longitude", 180.0)):
        v = loc.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not -lim <= v <= lim):
            out.append(Issue("error", f"{path}.{k}", f"Deve estar entre −{lim:g}° e {lim:g}°."))
    if (loc.get("latitude") is None) != (loc.get("longitude") is None):
        out.append(Issue("error", f"{path}.latitude", "Informe latitude e longitude juntas (ou nenhuma)."))
    acc = loc.get("accuracy_m")
    if acc is not None and (isinstance(acc, bool) or not isinstance(acc, (int, float)) or acc < 0):
        out.append(Issue("error", f"{path}.accuracy_m", "Precisão estimada inválida."))
    if loc.get("source") not in LOCATION_SOURCES:
        out.append(Issue("error", f"{path}.source", "Origem da localização inválida."))
    if loc.get("captured_at") is not None and not isinstance(loc.get("captured_at"), str):
        out.append(Issue("error", f"{path}.captured_at", "Deve ser texto."))
    tz = loc.get("timezone") or ""
    if tz:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(tz)
        except Exception:
            out.append(Issue("error", f"{path}.timezone", f"Fuso horário IANA desconhecido: {tz[:60]!r}."))
    return out


def identification_missing(config: dict) -> list[str]:
    """Campos obrigatórios da identificação ainda vazios (configurações antigas podem não tê-los)."""
    inst = config.get("installation") or {}
    out = []
    if not str(inst.get("name") or "").strip():
        out.append("Nome da instalação")
    if inst.get("nature") is None:
        out.append("Natureza da atividade")
    if inst.get("operation_mode") is None:
        out.append("Modo de operação previsto")
    return out


def validate(config: dict) -> list[Issue]:
    """Validação completa do documento. Erros impedem salvar; avisos são informativos.

    Nunca levanta exceção: documentos com estrutura inesperada (p. ex. vindos de um backup adulterado)
    resultam em erro de validação."""
    try:
        return _validate(config)
    except (TypeError, AttributeError, ValueError, KeyError, IndexError) as exc:
        return [Issue("error", "$", f"Estrutura do documento inválida ({type(exc).__name__}).")]


def _validate(config: dict) -> list[Issue]:
    out: list[Issue] = []
    if not isinstance(config, dict):
        return [Issue("error", "$", "Configuração deve ser um objeto.")]
    if config.get("schema_version") != DOC_SCHEMA_VERSION:
        out.append(Issue("error", "schema_version",
                         f"Versão de documento {config.get('schema_version')!r} não suportada (esperado {DOC_SCHEMA_VERSION})."))
    for section in ("installation", "commissioning", "energy_balance", "demand", "climate", "run_conditions"):
        if not isinstance(config.get(section), dict):
            out.append(Issue("error", section, "Seção ausente ou inválida."))
    if not isinstance(config.get("equipment"), list) or not isinstance(config.get("retired", []), list):
        out.append(Issue("error", "equipment", "Inventário ausente ou inválido."))
    if not isinstance(config.get("migrations", []), list):
        out.append(Issue("error", "migrations", "Histórico de migrações inválido."))
    if "legacy" in config and not isinstance(config["legacy"], dict):
        out.append(Issue("error", "legacy", "Estrutura inválida."))
    if any(i.level == "error" for i in out):
        return out
    typed = [("commissioning.completed", config["commissioning"].get("completed"), bool),
             ("demand.walkforward", config["demand"].get("walkforward"), dict),
             ("demand.copel", config["demand"].get("copel"), dict),
             ("run_conditions.battery_soc0_pct", config["run_conditions"].get("battery_soc0_pct"), dict)]
    for path, val, typ in typed:
        if not isinstance(val, typ):
            out.append(Issue("error", path, "Estrutura inválida."))
    st = config["commissioning"].get("step")
    if isinstance(st, bool) or not isinstance(st, int) or not 1 <= st <= 5:
        out.append(Issue("error", "commissioning.step", "Etapa de comissionamento inválida."))
    for path, val in (("demand.csv", config["demand"].get("csv")), ("climate.csv", config["climate"].get("csv"))):
        if val is not None and not isinstance(val, dict):
            out.append(Issue("error", path, "Estrutura inválida."))
    for k in ("timezone", "notes"):
        if not isinstance(config["demand"].get(k, ""), str):
            out.append(Issue("error", f"demand.{k}", "Deve ser texto."))
    if any(i.level == "error" for i in out):
        return out

    inst = config["installation"]
    if not re.fullmatch(r"[0-9a-f]{32}", str(inst.get("uid", ""))):
        out.append(Issue("error", "installation.uid", "Identidade da instalação inválida."))
    _str_field(inst, "name", "installation", out, required=True, maxlen=300)
    _str_field(inst, "description", "installation", out)
    if inst.get("nature") is not None and inst["nature"] not in NATURE_OPTIONS:
        out.append(Issue("error", "installation.nature", "Natureza da instalação inválida."))
    if inst.get("operation_mode") is not None and inst["operation_mode"] not in OPERATION_MODE_OPTIONS:
        out.append(Issue("error", "installation.operation_mode", "Modo operativo inválido."))
    out.extend(validate_location(inst.get("location")))
    src = inst.get("copied_from")
    if src is not None:                    # procedência de uma cópia independente (importação como cópia)
        if not isinstance(src, dict) or not re.fullmatch(r"[0-9a-f]{32}", str(src.get("uid", ""))) or \
                src.get("uid") == inst.get("uid") or \
                not all(isinstance(src.get(k), str) for k in ("name", "copied_at")) or \
                not (src.get("fingerprint") is None or re.fullmatch(r"[0-9a-f]{64}", str(src.get("fingerprint")))):
            out.append(Issue("error", "installation.copied_from", "Procedência de cópia inválida."))

    ids: set[str] = set()
    for eq in config["equipment"]:
        if not isinstance(eq, dict):
            out.append(Issue("error", "equipment", "Equipamento inválido."))
            continue
        if eq.get("id") in ids:
            out.append(Issue("error", f"equipment[{eq.get('id')}].id", "Identificador duplicado."))
        ids.add(eq.get("id"))
        out.extend(equipment_issues(eq))
    names = [str(e.get("name", "")).strip().lower() for e in config["equipment"] if isinstance(e, dict)]
    for n in sorted({n for n in names if n and names.count(n) > 1}):
        out.append(Issue("warning", "equipment", f"Nome repetido no inventário: {n!r} (use o TAG para diferenciar)."))
    for r in config.get("retired", []):
        if isinstance(r, dict) and r.get("id") in ids:
            out.append(Issue("error", f"retired[{r.get('id')}]", "Equipamento retirado com identificador ainda ativo."))

    bal = config["energy_balance"]
    if bal.get("grid_connection") not in GRID_CONNECTION_OPTIONS:
        out.append(Issue("error", "energy_balance.grid_connection", "Estado de conexão à rede inválido."))
    if inst.get("operation_mode") == "isolada" and bal.get("grid_connection") == "conectada":
        out.append(Issue("warning", "energy_balance.grid_connection",
                         "Modo operativo 'isolada' declarado, mas a instalação está declarada como conectada à rede."))

    batt = {e["id"] for e in config["equipment"] if isinstance(e, dict) and e.get("kind") == "battery"}
    for eid, v in config["run_conditions"]["battery_soc0_pct"].items():
        if eid not in batt:
            out.append(Issue("error", f"run_conditions.battery_soc0_pct.{eid}", "SOC inicial para banco inexistente."))
        elif isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100:
            out.append(Issue("error", f"run_conditions.battery_soc0_pct.{eid}", "SOC inicial deve estar entre 0 e 100 %."))

    dem = config["demand"]
    if dem.get("source") not in DEMAND_SOURCES:
        out.append(Issue("error", "demand.source", "Fonte de demanda inválida."))
    if dem.get("provenance") not in PROVENANCE_KINDS:
        out.append(Issue("error", "demand.provenance", "Procedência da demanda inválida."))
    if dem.get("source") == "csv":
        csv = dem.get("csv") or {}
        if not re.fullmatch(r"[0-9a-f]{64}", str(csv.get("blob", ""))):
            out.append(Issue("error", "demand.csv", "Perfil CSV sem conteúdo armazenado (hash ausente)."))
    if dem.get("source") in ("walkforward", "copel") and dem.get("provenance") == "medido":
        out.append(Issue("error", "demand.provenance",
                         "Perfis de referência incluídos no software não podem ser declarados como medidos."))
    clim = config["climate"]
    if clim.get("source") not in CLIMATE_SOURCES:
        out.append(Issue("error", "climate.source", "Fonte climática inválida."))
    if clim.get("source") == "sintetico" and clim.get("provenance") == "medido":
        out.append(Issue("error", "climate.provenance", "Clima sintético não pode ser declarado como medido."))
    if clim.get("source") == "csv" and not re.fullmatch(r"[0-9a-f]{64}", str((clim.get("csv") or {}).get("blob", ""))):
        out.append(Issue("error", "climate.csv", "CSV climático sem conteúdo armazenado (hash ausente)."))
    return out


def errors(issues: Iterable[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "error"]


# ======================================================== identidade de conteúdo
def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def fingerprint(config: dict) -> str:
    """SHA-256 do conteúdo canônico da configuração (identifica a versão usada por uma rodada)."""
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()


# ======================================================== grandezas nominais (resumos de inventário)
def installed_power_kW(eq: dict) -> float | None:
    """Potência nominal registrada. FV: soma dos arranjos com potência calculável ou declarada."""
    p = eq.get("params") or {}
    try:
        if eq["kind"] == "pv":
            from .derived import pv_plant_summary
            s = pv_plant_summary(eq)
            return s["total_kWp"] if (s["n_computed"] or s["n_declared"]) else None
        if eq["kind"] == "wind" and p.get("reference") and p.get("count"):
            return wind_references()[p["reference"]].summary["P_nominal [kW]"] * p["count"]
        if eq["kind"] == "thermal" and p.get("pmax_kW"):
            return float(p["pmax_kW"])
        if eq["kind"] == "pemfc" and p.get("quantity") and p.get("reference") == PEMFC_REF_KEY:
            from .references import pemfc_max_net_power_kW
            return pemfc_max_net_power_kW() * p["quantity"]
        if eq["kind"] == "pemfc" and p.get("quantity") and p.get("reference") == PEMFC_IMPORT_REF:
            w = ((eq.get("imported") or {}).get("device") or {}).get("rated_power_W")
            return float(w) * p["quantity"] / 1000.0 if isinstance(w, (int, float)) and not isinstance(w, bool) else None
    except KeyError:
        return None
    return None


def battery_model_energy_kWh(eq: dict) -> float | None:
    """Energia da PARAMETRIZAÇÃO do modelo científico (V·Q da célula × Ns × Np), não do datasheet."""
    p = eq.get("params") or {}
    if eq.get("kind") != "battery" or not battery_model_parametrized(eq):
        return None
    from .references import battery_cell
    try:
        v, q = battery_cell(p["model_reference"])
    except KeyError:
        return None
    return v * q * p["model_n_series"] * p["model_n_parallel"] / 1000.0


def battery_energy_kWh(eq: dict) -> float | None:
    """Energia nominal do banco: declarada/derivada do datasheet; senão, a da parametrização do modelo."""
    if eq.get("kind") != "battery":
        return None
    from .derived import battery_derived
    e = battery_derived(eq.get("params") or {})["energy_kWh"][0]
    return e if e is not None else battery_model_energy_kWh(eq)


THERMAL_DYNAMICS = THERMAL_DYNAMIC_KEYS
