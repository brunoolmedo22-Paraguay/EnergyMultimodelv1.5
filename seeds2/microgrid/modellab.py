"""Importação de dispositivos do PEMFC ModelLab (arquivo NÃO confiável).

Formatos reais do ModelLab v0.5 (repositório PEMFC-MODELAB, ``workspace/project_io.py`` e
``pemfc_core/schemas.py``):

* ``.pmldevice.zip`` / ``.pmlproj.zip`` — ``manifest.json`` (``schema = "pemfc-modellab/workspace"``,
  ``schema_version`` 1.x, ``records: {"tipo:id": sha256 canônico}``, ``blobs``), ``records/<tipo>/<id>.json``
  e ``blobs/<sha256>``. O SHA-256 de cada registro é calculado sobre o JSON canônico (chaves ordenadas,
  separadores compactos, UTF-8), exatamente como ``canonical_sha256`` do ModelLab.
* ``profile.json`` — perfil calibrado (``schema = "pemfc-modellab/profile"``, versão 1.x).

Importar NÃO torna o dispositivo simulável: um perfil V–I calibrado (estacionário, domínio restrito) não
descreve balanço de planta, consumo global, controle nem dinâmica. O dispositivo é registrado com sua
procedência e o estado de validação do perfil, e fica **pendente de integração científica** no EMS.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from typing import Any

WORKSPACE_SCHEMA = "pemfc-modellab/workspace"
PROFILE_SCHEMA = "pemfc-modellab/profile"
MAX_PACKAGE_BYTES = 25 * 1024 * 1024
MAX_ENTRY_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 80 * 1024 * 1024
MAX_ENTRIES = 2000
_CHUNK = 1024 * 1024
_RECORD_RE = re.compile(r"^records/(device|dataset|draft|calibration|export|experiment)/([A-Za-z0-9_.\-]{1,100})\.json$")
_BLOB_RE = re.compile(r"^blobs/[0-9a-f]{64}$")
_HEX64 = re.compile(r"[0-9a-f]{64}")

STATUS_LABELS = {
    "NO_CONVERGIDO": "Não convergido (não utilizável)",
    "AJUSTE_INSUFICIENTE": "Ajuste insuficiente (não utilizável)",
    "AJUSTADO_A_CURVA": "Ajustado às curvas de calibração — sem capacidade preditiva demonstrada",
    "VALIDADO_EXPERIMENTALMENTE": "Validado experimentalmente (somente nas condições validadas)",
}
VALIDATION_LABELS = {
    "SIN_VALIDACION_INDEPENDIENTE": "Sem validação independente",
    "VALIDACION_SUPERADA": "Validação independente superada",
    "VALIDACION_NO_SUPERADA": "Validação independente não superada",
    "VALIDACION_CON_DATOS_NO_EXPERIMENTALES": "Validação com dados não experimentais",
    "VALIDACION_SOLO_MISMA_CONDICION": "Validação apenas na mesma condição de calibração",
}
INTEGRATION_PENDING = ("Pendente de integração científica: o perfil V–I calibrado do ModelLab não substitui o modelo "
                       "PEMFC usado pelo EMS (balanço de planta, consumo auxiliar, controle e dinâmica não descritos).")
_PROFILE_TOP = {"schema": str, "schema_version": str, "profile_id": str, "created_utc": str, "status": dict,
                "engine": dict, "device": dict, "parameters": list, "datasets": list, "fit": dict, "validation": dict,
                "domain": dict, "provenance": dict}
_DEVICE_FIELDS = {"id": str, "name": str, "manufacturer": str, "model": str, "technology": str, "configuration": str,
                  "n_cells": (int,), "n_cells_origin": str, "active_area_cm2": (int, float), "active_area_origin": str,
                  "rated_power_W": (int, float), "nominal_voltage_V": (int, float), "nominal_current_A": (int, float),
                  "datasheet_reference": str, "provenance": str, "active_calibration_id": str, "notes": str}


class ImportRejected(ValueError):
    """Pacote rejeitado (mensagem apresentável)."""


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _clean_device(d: dict) -> dict:
    out = {}
    for k, typ in _DEVICE_FIELDS.items():
        v = d.get(k)
        if v is None:
            out[k] = None
            continue
        types = typ if isinstance(typ, tuple) else (typ,)
        if isinstance(v, bool) or not isinstance(v, types):
            raise ImportRejected(f"Campo do dispositivo {k!r} com tipo inválido.")
        out[k] = v[:500] if isinstance(v, str) else v
    return out


def _range(v: Any) -> list[float] | None:
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return [float(v[0]), float(v[1])]
    return None


def validate_profile(profile: Any) -> list[str]:
    """Validação estrutural compatível com ``validate_profile_dict`` do ModelLab (sem dependências)."""
    if not isinstance(profile, dict):
        return ["O perfil deve ser um objeto JSON."]
    errs = [f"Campo obrigatório {k!r} ausente ou com tipo inválido." for k, t in _PROFILE_TOP.items()
            if not isinstance(profile.get(k), t)]
    if errs:
        return errs
    if profile["schema"] != PROFILE_SCHEMA:
        errs.append(f"Esquema de perfil desconhecido: {profile['schema'][:60]!r}.")
    if str(profile["schema_version"]).split(".")[0] != "1":
        errs.append(f"Versão de perfil não suportada: {profile['schema_version'][:20]!r}.")
    if profile["status"].get("code") not in STATUS_LABELS:
        errs.append("Estado do perfil inválido.")
    cal = [d for d in profile["datasets"] if isinstance(d, dict) and d.get("role") == "calibración"]
    if not cal:
        errs.append("O perfil não contém curva de calibração (perfil sem curva V–I não é admissível).")
    return errs


def summarize_profile(profile: dict, *, calibration_id: str | None = None, origin: str = "", label: str = "",
                      created_utc: str | None = None) -> dict:
    st, val, dom = profile["status"], profile["validation"], (profile.get("domain") or {}).get("calibration") or {}
    fit = profile.get("fit") or {}
    eng = profile.get("engine") or {}
    rmse = (fit.get("metrics_calibration") or {}).get("rmse_V")
    return {
        "id": calibration_id, "profile_id": profile["profile_id"][:100], "label": str(label)[:200], "origin": str(origin)[:60],
        "created_utc": str(created_utc or profile["created_utc"])[:40],
        "status_code": st.get("code"), "status_label": STATUS_LABELS.get(st.get("code"), "—"),
        "usable_in_modellab": bool(st.get("usable_for_simulation", False)),
        "predictive_capability": str(st.get("predictive_capability") or "")[:80],
        "validation_status": str(val.get("status") or "")[:80],
        "validation_label": VALIDATION_LABELS.get(val.get("status"), str(val.get("status") or "—")[:80]),
        "rmse_V": float(rmse) if isinstance(rmse, (int, float)) and not isinstance(rmse, bool) else None,
        "model_id": str(eng.get("model_id") or "")[:100], "engine_app_version": str(eng.get("app_version") or "")[:20],
        "n_curves": len(profile.get("datasets") or []),
        "domain": {"j_A_cm2": _range(dom.get("j_A_cm2")), "temperature_K": _range(dom.get("temperature_K")),
                   "cathode_pressure_atm": _range(dom.get("cathode_pressure_atm"))},
    }


def _read_capped(zf: zipfile.ZipFile, info: zipfile.ZipInfo, budget: list[int]) -> bytes:
    out = bytearray()
    with zf.open(info) as fh:
        while chunk := fh.read(_CHUNK):
            out += chunk
            budget[0] -= len(chunk)
            if len(out) > MAX_ENTRY_BYTES or budget[0] < 0:
                raise ImportRejected("Conteúdo descomprimido excede os limites de importação.")
    return bytes(out)


def _parse_package(data: bytes) -> dict:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ImportRejected("O arquivo não é um ZIP válido do PEMFC ModelLab.") from None
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ImportRejected("Pacote com entradas demais.")
        names = [i.filename for i in infos]
        if len(set(names)) != len(names):
            raise ImportRejected("Pacote com entradas duplicadas.")
        for i in infos:
            n = i.filename
            if not (n == "manifest.json" or _RECORD_RE.match(n) or _BLOB_RE.match(n)):
                raise ImportRejected(f"Entrada inesperada no pacote: {n[:80]!r}.")
            if i.flag_bits & 0x1 or i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ImportRejected("Pacote criptografado ou com compressão não suportada.")
            if i.file_size > MAX_ENTRY_BYTES:
                raise ImportRejected("Entrada do pacote excede o tamanho permitido.")
        if "manifest.json" not in names:
            raise ImportRejected("Falta manifest.json: não é um pacote do PEMFC ModelLab.")
        if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
            raise ImportRejected("O conteúdo declarado do pacote excede o limite.")
        budget = [MAX_TOTAL_BYTES]
        content = {i.filename: _read_capped(zf, i, budget) for i in infos}
    try:
        man = json.loads(content["manifest.json"].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ImportRejected("manifest.json ilegível.") from None
    if not isinstance(man, dict) or man.get("schema") != WORKSPACE_SCHEMA:
        raise ImportRejected("Esquema desconhecido: não é um pacote de dispositivo do PEMFC ModelLab.")
    ver = man.get("schema_version")
    if not isinstance(ver, str) or ver.split(".")[0] != "1":
        raise ImportRejected("Versão do pacote ModelLab não suportada.")
    recs, blobs = man.get("records"), man.get("blobs", {})
    if not isinstance(recs, dict) or not isinstance(blobs, dict):
        raise ImportRejected("Manifesto com estrutura inválida.")
    for k in ("app_version", "created_utc"):
        if man.get(k) is not None and not isinstance(man.get(k), str):
            raise ImportRejected("Manifesto com tipos inválidos.")
    records: dict[str, dict] = {}
    for key, digest in recs.items():
        if not isinstance(key, str) or ":" not in key or not isinstance(digest, str) or not _HEX64.fullmatch(digest):
            raise ImportRejected("Manifesto com registros inválidos.")
        kind, rid = key.split(":", 1)
        path = f"records/{kind}/{rid}.json"
        if path not in content or not _RECORD_RE.match(path):
            raise ImportRejected(f"Falta o registro {key[:60]} declarado no manifesto.")
        try:
            val = json.loads(content[path].decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ImportRejected(f"Registro {key[:60]} ilegível.") from None
        if canonical_sha256(val) != digest:
            raise ImportRejected(f"O registro {key[:60]} não confere com sua impressão digital (arquivo alterado).")
        records[key] = val
    undeclared = [n for n in content if n.startswith("records/") and
                  f"{n.split('/')[1]}:{n.split('/')[2][:-5]}" not in recs]
    if undeclared:
        raise ImportRejected("Pacote contém registros não declarados no manifesto.")
    for sha, meta in blobs.items():
        if not isinstance(sha, str) or not _HEX64.fullmatch(sha) or not isinstance(meta, dict):
            raise ImportRejected("Manifesto com binários inválidos.")
        raw = content.get(f"blobs/{sha}")
        if raw is None or hashlib.sha256(raw).hexdigest() != sha:
            raise ImportRejected("Binário original ausente ou alterado no pacote.")
    devices = [v for k, v in records.items() if k.startswith("device:")]
    if len(devices) != 1 or not isinstance(devices[0], dict):
        raise ImportRejected(f"O pacote deve conter exatamente um dispositivo (contém {len(devices)}). "
                             "Exporte um único dispositivo no ModelLab (.pmldevice.zip).")
    device = _clean_device(devices[0])
    if not (device.get("name") or "").strip():
        raise ImportRejected("Dispositivo sem nome no pacote.")
    cals = []
    for k, v in records.items():
        if not k.startswith("calibration:") or not isinstance(v, dict) or v.get("device_id") != device["id"]:
            continue
        errs = validate_profile(v.get("profile"))
        if errs:
            raise ImportRejected(f"Calibração {k[12:60]} com perfil inválido: {errs[0]}")
        cals.append(summarize_profile(v["profile"], calibration_id=str(v.get("id"))[:100], origin=v.get("origin", ""),
                                      label=v.get("label", ""), created_utc=v.get("created_utc")))
    return {"format": "pmldevice", "source": {"schema": WORKSPACE_SCHEMA, "schema_version": ver,
                                               "app_version": str(man.get("app_version") or "")[:20],
                                               "created_utc": str(man.get("created_utc") or "")[:40]},
            "device": device, "calibrations": sorted(cals, key=lambda c: c["created_utc"]),
            "n_records": len(records), "n_blobs": len(blobs)}


def _parse_profile(data: bytes) -> dict:
    if len(data) > MAX_ENTRY_BYTES:
        raise ImportRejected("profile.json grande demais.")
    try:
        prof = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ImportRejected("Arquivo não é um JSON válido.") from None
    errs = validate_profile(prof)
    if errs:
        raise ImportRejected("Perfil do ModelLab inválido: " + errs[0])
    dev = prof["device"]
    device = _clean_device({k: v for k, v in dev.items() if k in _DEVICE_FIELDS})
    device["id"] = None
    if not (device.get("name") or "").strip():
        device["name"] = f"Perfil {prof['profile_id'][:40]}"
    return {"format": "profile", "source": {"schema": PROFILE_SCHEMA, "schema_version": prof["schema_version"][:20],
                                             "app_version": str((prof.get("engine") or {}).get("app_version") or "")[:20],
                                             "created_utc": prof["created_utc"][:40]},
            "device": device, "calibrations": [summarize_profile(prof, origin="profile.json")], "n_records": 1, "n_blobs": 0}


def parse_modellab_file(data: bytes, filename: str) -> dict:
    """Valida e resume um arquivo do ModelLab. Nunca levanta exceção não controlada: ``ImportRejected``."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ImportRejected("Arquivo vazio ou inválido.")
    if len(data) > MAX_PACKAGE_BYTES:
        raise ImportRejected(f"Arquivo maior que {MAX_PACKAGE_BYTES // (1024 * 1024)} MiB.")
    try:
        info = _parse_package(bytes(data)) if bytes(data[:2]) == b"PK" else _parse_profile(bytes(data))
    except ImportRejected:
        raise
    except Exception as exc:  # noqa: BLE001 — qualquer defeito do arquivo vira rejeição controlada
        raise ImportRejected(f"Arquivo do ModelLab malformado ({type(exc).__name__}).") from None
    info["filename"] = str(filename or "")[:200]
    info["sha256"] = hashlib.sha256(bytes(data)).hexdigest()
    active = info["device"].get("active_calibration_id")
    info["active_calibration_id"] = active if any(c["id"] == active for c in info["calibrations"]) else None
    info["integration_status"] = "pendente_integracao"
    info["integration_note"] = INTEGRATION_PENDING
    return info


def imported_record(info: dict, blob_sha: str, imported_at: str) -> dict:
    """Estrutura persistida no equipamento PEMFC (``imported``)."""
    return {"format": info["format"], "filename": info["filename"], "blob": blob_sha, "imported_at": imported_at,
            "source": info["source"], "device": info["device"], "calibrations": info["calibrations"],
            "active_calibration_id": info["active_calibration_id"], "integration_status": info["integration_status"],
            "integration_note": info["integration_note"]}
