"""Runner científico do Piso 2C — serviço de execução SEPARADO da camada Streamlit.

Fluxo de uma rodada (``submit``):

1. recebe a identidade e a versão IMUTÁVEL do cenário (``scenario_versions``);
2. executa o preflight (fase A) sobre essa versão — incompatível → nada é iniciado;
3. abre a rodada (``MicrogridStore.start_run``: manifesto de procedência imutável; idempotente pelo ``request_id``:
   uma recarga/duplo clique nunca executa duas vezes; uma única rodada ativa por microrrede);
4. em uma thread própria (não depende da sessão do navegador): monta a carga e o clima na grade da missão,
   executa os modelos físicos e monta o pacote de troca com ``orchestrator_runtime.build_exchange_package``;
5. fase B do preflight (contrato efetivo do motor) — incompatível → rodada 'falhou' SEM chamar o otimizador;
6. ``orchestrator_runtime.run_optimizer`` (progresso REAL: passo k/n do despacho, gravado no banco);
7. grava séries completas, resumo, relatório e pacote de troca na MESMA transação que conclui a rodada.

Qualquer exceção → 'falhou' (sem resultados). Processo encerrado no meio → a rodada fica 'em_execucao' com um dono
morto e é marcada 'interrompida' por ``recover`` (nunca 'concluida'). Execuções são serializadas no processo
(``_ENGINE_LOCK``): nenhuma chamada paralela aos modelos/otimizador. Nada aqui altera modelos ou o EMS.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import socket
import tempfile
import threading
import time
import traceback
import uuid
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from seeds2.microgrid.store import MicrogridDeletedError, MissingStoreError, RunStateError, StoreError

from . import contracts
from . import forecasts as F
from . import mission as M
from . import preflight as P
from . import strategy as SG

RUN_FORMAT = "seeds2-run"
RUN_FORMAT_VERSION = 1
STALE_S = 1800.0                      # dono em OUTRO host sem sinal por 30 min → interrompida
HEARTBEAT_EVERY_S = 0.5
_HOST = socket.gethostname()
_TOKEN = uuid.uuid4().hex             # identifica ESTE processo (reuso de PID não engana a recuperação)
OWNER = f"{_HOST}|{os.getpid()}|{_TOKEN}"
_ENGINE_LOCK = threading.Lock()
_LIVE: dict[str, threading.Thread | None] = {}       # rodadas deste processo (None = registrada, thread por iniciar)
_LIVE_LOCK = threading.Lock()
_SCIENCE_FP: dict | None = None
ROOT = Path(__file__).resolve().parents[2]
# Preparation/validation determines the actual engine inputs, too. Include it
# in provenance without importing unrelated experimental dispatch implementations.
SCIENCE_PATHS = ("models", "h2_pemfc", "simulation", "ems_integration", "config", "orchestrator_runtime.py",
                 "seeds2/operation", "seeds2/microgrid/adapter.py", "seeds2/microgrid/config.py",
                 "seeds2/microgrid/references.py")


class PreflightError(StoreError):
    """O cenário não é executável pelo motor atual (relatório em ``preflight``). Nada foi iniciado."""

    def __init__(self, pf: P.Preflight):
        errs = [i.message for i in pf.items if i.level == P.ERROR]
        super().__init__(f"{len(errs)} incompatibilidade(s): " + " | ".join(errs[:3]))
        self.preflight = pf


# ====================================================================== dono / recuperação
def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def owner_is_dead(run_uid: str, owner: str, heartbeat_at: str) -> bool:
    """O dono de uma rodada 'em_execucao' não pode mais concluí-la?"""
    try:
        host, pid_s, token = owner.split("|")
        pid = int(pid_s)
    except ValueError:
        return True
    if host == _HOST:
        if pid == os.getpid():
            if token != _TOKEN:
                return True                           # processo anterior com o mesmo PID (reinício)
            with _LIVE_LOCK:
                t = _LIVE.get(run_uid, False)
            return t is False or (t is not None and not t.is_alive())
        if not _pid_alive(pid):
            return True
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat_at)).total_seconds()
    except (TypeError, ValueError):
        return True
    return age > STALE_S


def recover(store) -> list[str]:
    """Marca como 'interrompida' as rodadas cujo processo terminou (reinício do servidor, encerramento inesperado)."""
    return store.recover_runs(owner_is_dead)


def is_running_here(run_uid: str) -> bool:
    with _LIVE_LOCK:
        t = _LIVE.get(run_uid)
    return t is not None and t.is_alive()


def wait(run_uid: str, timeout: float | None = None) -> bool:
    """Espera a thread da rodada terminar (testes/scripts). Verdadeiro se terminou."""
    with _LIVE_LOCK:
        t = _LIVE.get(run_uid)
    if t is None:
        return True
    t.join(timeout)
    return not t.is_alive()


# ====================================================================== procedência
def science_fingerprint() -> dict:
    """SHA-256 do código e dos dados científicos usados (modelos, EMS, bancos de equipamentos, runtime)."""
    global _SCIENCE_FP
    if _SCIENCE_FP is None:
        h = hashlib.sha256()
        files = []
        for rel in SCIENCE_PATHS:
            p = ROOT / rel
            items = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file() and "__pycache__" not in x.parts
                                                   and x.suffix in (".py", ".csv", ".json"))
            for f in items:
                h.update(str(f.relative_to(ROOT)).encode())
                h.update(f.read_bytes())
                files.append(f)
        _SCIENCE_FP = {"sha256": h.hexdigest(), "files": len(files), "paths": list(SCIENCE_PATHS)}
    return dict(_SCIENCE_FP)


def software_versions() -> dict:
    import scipy

    from seeds2 import APP_NAME, APP_VERSION

    return {"app": f"{APP_NAME} {APP_VERSION}", "runtime": "Energy MultiModel V1.6 (orchestrator_runtime + ems_integration)",
            "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
            "science": science_fingerprint()}


def _json_safe(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, np.ndarray):
        return _json_safe(v.tolist())
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return f if np.isfinite(f) else None
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, datetime)):
        return str(v)
    if isinstance(v, (str, int, bool)) or v is None:
        return v
    return str(v)


def build_manifest(pf: P.Preflight, run_uid: str, request_id: str) -> dict:
    stored = pf.scenario
    doc = stored.document
    fc = doc.get("forecasts") or {}
    keys = ("data", "blob", "source_type", "provenance", "label", "timezone", "timezone_source", "t0", "t_end", "step_s",
            "n_points", "variables", "transforms")
    return _json_safe({
        "format": RUN_FORMAT, "format_version": RUN_FORMAT_VERSION, "run_uid": run_uid, "request_id": request_id,
        "reference": asdict(contracts.run_reference(stored)),
        "scenario": {"name": doc.get("name"), "description": doc.get("description"), "version": stored.version,
                     "fingerprint": stored.fingerprint},
        "software": software_versions(),
        "objective": {"key": SG.OBJECTIVE, "label": SG.OBJECTIVE_LABEL, "terms": list(SG.OBJECTIVE_TERMS)},
        "strategy": doc.get("ems_strategy"), "engine_fixed": SG.ENGINE_FIXED,
        "mission": {**(doc.get("mission") or {}), **(pf.engine_inputs().get("grid") or {})},
        "forecasts": {slot: {k: e.get(k) for k in keys} for slot, e in fc.items()},
        "engine_inputs": pf.engine_inputs(),
        "preflight": pf.report(),
    })


# ====================================================================== execução
def prepare(store, scenario_uid: str, version: int | None = None) -> P.Preflight:
    return P.prepare(store, store.get_scenario(scenario_uid, version))


def submit(store, scenario_uid: str, version: int, request_id: str, *, background: bool = True):
    """Inicia a rodada da versão ``version`` (gravada) do cenário. Devolve a ``StoredRun`` (existente, se o mesmo
    ``request_id`` já foi submetido). ``PreflightError`` se incompatível; ``RunBusyError`` se outra rodada está ativa."""
    pf = prepare(store, scenario_uid, version)
    if not pf.ok:
        raise PreflightError(pf)
    run_uid = uuid.uuid4().hex
    with _LIVE_LOCK:
        _LIVE[run_uid] = None                         # registrada antes do INSERT: recuperação não a julga morta
    try:
        run, created = store.start_run(run_uid=run_uid, request_id=request_id, scenario_uid=scenario_uid,
                                       scenario_version=int(version), scenario_fingerprint=pf.scenario.fingerprint,
                                       manifest=build_manifest(pf, run_uid, request_id), owner=OWNER,
                                       is_dead=owner_is_dead)
    except BaseException:
        with _LIVE_LOCK:
            _LIVE.pop(run_uid, None)
        raise
    if not created:
        with _LIVE_LOCK:
            _LIVE.pop(run_uid, None)
        return run
    if background:
        t = threading.Thread(target=_execute, args=(store, run_uid, pf), name=f"seeds2-run-{run_uid[:8]}", daemon=True)
        with _LIVE_LOCK:
            _LIVE[run_uid] = t
        t.start()
    else:
        with _LIVE_LOCK:
            _LIVE[run_uid] = threading.current_thread()
        try:
            _execute(store, run_uid, pf)
        finally:
            with _LIVE_LOCK:
                _LIVE.pop(run_uid, None)
    return store.get_run(run_uid)


def _execute(store, run_uid: str, pf: P.Preflight) -> None:
    import orchestrator_runtime as RT
    from ems_integration import ponte

    state = {"last": 0.0}

    def beat(progress: dict, force: bool = False) -> None:
        now = time.monotonic()
        if force or now - state["last"] >= HEARTBEAT_EVERY_S:
            state["last"] = now
            if not store.heartbeat_run(run_uid, OWNER, progress):
                raise RunStateError("A rodada deixou de estar em execução por este processo.")

    outcome: dict = {"engine_check": None}
    try:
        beat({"phase": "fila"}, force=True)
        with _ENGINE_LOCK:
            t_start = time.perf_counter()
            beat({"phase": "modelos"}, force=True)
            w = pf.window
            spec = pf.plan.spec
            opt = pf.optimizer_cfg
            carga = ponte.PerfilCarga(np.arange(w.duration_min + 1, dtype=float), np.asarray(w.demand_kW, dtype=float),
                                      pd.Timestamp(w.start_wall),
                                      f"Cenário {pf.scenario.document.get('name')} v{pf.scenario.version}")
            climate_raw = M.climate_frame(w)
            with tempfile.TemporaryDirectory(prefix="seeds2_run_") as tmp:
                package, outputs = RT.build_exchange_package(carga, spec, opt, climate_raw=climate_raw,
                                                             destino=Path(tmp) / "pacote")
                beat({"phase": "verificacao"}, force=True)
                ok, checks, effective = P.engine_check(pf, package)
                outcome["engine_check"] = {"ok": ok, "items": checks, "effective_initial_state": effective}
                if not ok:
                    store.fail_run(run_uid, OWNER, {"kind": "incompatibilidade", "message": "O contrato efetivo do motor "
                                   "não representa o estado inicial declarado; o otimizador NÃO foi chamado.",
                                   "items": checks}, outcome=_json_safe(outcome))
                    return
                beat({"phase": "otimizador", "k": 0, "n": int(len(carga.t_min))}, force=True)
                r, val = RT.run_optimizer(package, opt, progress=lambda k, n: beat(
                    {"phase": "otimizador", "k": int(k), "n": int(n)}, force=(k == n)))
                beat({"phase": "gravando"}, force=True)
                data, summary, extra = _results(pf, w, carga, r, val, outputs, Path(package))
            outcome.update(extra)
            outcome["elapsed_s"] = time.perf_counter() - t_start
            store.finish_run(run_uid, OWNER, outcome=_json_safe(outcome), summary=_json_safe(summary), data=data)
    except (MicrogridDeletedError, MissingStoreError):
        return                                        # microrrede excluída durante a execução: nada a registrar
    except RunStateError:
        return
    except BaseException as exc:                      # noqa: BLE001 — registrar a falha sem resultados parciais
        try:
            store.fail_run(run_uid, OWNER, {"kind": "falha", "type": type(exc).__name__, "message": str(exc)[:2000],
                                            "traceback": traceback.format_exc()[-4000:]}, outcome=_json_safe(outcome))
        except Exception:                             # noqa: BLE001 — a recuperação marcará 'interrompida'
            pass
        if not isinstance(exc, Exception):
            raise


# ====================================================================== resultados
def _csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, lineterminator="\n").encode("utf-8")


def input_frame(w: M.Window) -> pd.DataFrame:
    df = pd.DataFrame({"passo": np.arange(len(w.grid_utc)), "t_min": np.arange(len(w.grid_utc), dtype=float),
                       "timestamp_utc": w.grid_utc.strftime("%Y-%m-%dT%H:%M:%SZ") if w.timezone else
                       w.grid_utc.strftime("%Y-%m-%dT%H:%M:%S"),
                       "timestamp_local": w.grid_wall.strftime("%Y-%m-%dT%H:%M:%S"),
                       "timestamp_runtime": w.runtime_times.strftime("%Y-%m-%dT%H:%M:%S"),
                       "demand_kW": w.demand_kW})
    for var, vals in w.climate.items():
        df[var] = vals
    return df


def output_frame(r: dict, val: dict | None, w: M.Window) -> pd.DataFrame:
    import orchestrator_runtime as RT

    kv = int(r["k_validos"])
    df = RT.series_dataframe(r)                       # ponto de partida V1.6 (nada removido)
    df.insert(0, "timestamp_local", w.grid_wall[:kv].strftime("%Y-%m-%dT%H:%M:%S"))
    df.insert(0, "timestamp_utc", input_frame(w)["timestamp_utc"].to_numpy()[:kv])
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%dT%H:%M:%S")
    df = df.rename(columns={"timestamp": "timestamp_runtime"})
    # Saídas do motor que series_dataframe não inclui:
    df["P_renovavel_disponivel_kW"] = np.asarray(r["P_renov_kW"])[:kv]
    df["custo_partida_rs"] = np.asarray(r["custo_partida_rs"])[:kv]
    df["violacao_refino"] = np.asarray(r["viol_ref"])[:kv]
    df["n_combinacoes"] = np.asarray(r["n_combos"])[:kv]
    for j, nome in enumerate(r["nomes"]):
        df[f"Pmax_unid_{nome}_kW"] = np.asarray(r["P_max_unid_kW"])[:kv, j]
    if val is not None and "h2_kg_passo" in val:
        df["h2_kg_validacao_dinamica"] = np.asarray(val["h2_kg_passo"])[:kv]
    return df


def summarize(r: dict, val: dict | None) -> dict:
    rel = r["rel"]
    kv = int(r["k_validos"])
    ts_h = float(r["Ts_s"]) / 3600.0
    e_load = float(np.sum(np.asarray(r["P_load_kW"])[:kv]) * ts_h)
    e_uns = float(rel["energia_nao_atendida_kWh"])
    names = list(r["nomes"])
    e_src = {n: float(x) for n, x in zip(names, rel["energia_por_fonte_kWh"])}
    e_pv = float(np.sum(r["eta_pv"] * np.asarray(r["P_pv_kW"])[:kv]) * ts_h)
    e_eol = float(np.sum(r["eta_eol"] * np.asarray(r["P_eol_kW"])[:kv]) * ts_h)
    h2 = (rel.get("consumo_fisico") or {}).get("fc", {}).get("valor")
    soc_f = {n: float(s) for n, s in zip(names, rel["SOC_final"]) if np.isfinite(s)}
    return {
        "algoritmo": r["algoritmo"], "N": int(r["N"]), "passos": kv, "Ts_s": float(r["Ts_s"]),
        "custo_total_rs": float(rel["custo_total_rs"]),
        "custo_por_fonte_rs": {n: float(x) for n, x in zip(names, rel["custo_por_fonte_rs"])},
        "energia_demanda_kWh": e_load, "energia_atendida_kWh": e_load - e_uns, "energia_nao_atendida_kWh": e_uns,
        "energia_excedente_kWh": float(rel["energia_vertida_kWh"]),
        "energia_excedente_despachavel_kWh": float(rel.get("energia_vertida_despachavel_kWh", 0.0)),
        "energia_excedente_renovavel_kWh": float(rel.get("energia_vertida_renovavel_kWh", 0.0)),
        "energia_solar_kWh": e_pv, "energia_eolica_kWh": e_eol, "energia_por_fonte_kWh": e_src,
        "h2_kg": float(h2) if h2 is not None else None,
        "h2_kg_validacao_dinamica": float(val["h2_kg"]) if val else None,
        "soc_final": soc_f, "partidas": {n: int(x) for n, x in zip(names, rel["partidas"])},
        "passos_inviaveis": int(r["n_inviaveis"]), "fontes": names, "avisos": list(r.get("avisos", [])),
        "tempo_otimizador_s": float(r["tempo_total_s"]),
    }


def _zip_dir(path: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(path.rglob("*")):
            if f.is_file():
                info = zipfile.ZipInfo(str(f.relative_to(path)), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, f.read_bytes())
    return buf.getvalue()


def _results(pf: P.Preflight, w: M.Window, carga, r: dict, val: dict | None, outputs: dict, package: Path):
    data: dict[str, tuple[bytes, str]] = {
        "entradas/missao.csv": (_csv(input_frame(w)), "text/csv"),
        "saidas/despacho_ems.csv": (_csv(output_frame(r, val, w)), "text/csv"),
        "pacote_troca.zip": (_zip_dir(package), "application/zip"),
    }
    for key, value in outputs.items():
        if isinstance(value, pd.DataFrame):
            df = value.reset_index() if not isinstance(value.index, pd.RangeIndex) else value
            data[f"modelos/{key}.csv"] = (_csv(df), "text/csv")
    report = {"rel": r["rel"], "log": r.get("log", []), "avisos": r.get("avisos", []), "fontes_meta": r.get("fontes_meta"),
              "bateria": r.get("bateria"), "config_pacote": r.get("config"), "S_base_kW": r.get("S_base_kW"),
              "eta": r.get("eta"), "n_unid_inst": r.get("n_unid_inst"), "t_meta_s": r.get("t_meta_s"),
              "t_ref_s": r.get("t_ref_s"), "validacao_dinamica": val, "notas_runtime": outputs.get("notes")}
    data["saidas/relatorio_ems.json"] = (json.dumps(_json_safe(report), ensure_ascii=False, indent=1).encode("utf-8"),
                                         "application/json")
    extra = {"effective_engine": {"nomes": list(r["nomes"]), "tipos": list(r["tipos"]),
                                  "n_unid_inst": r["n_unid_inst"], "bateria": r.get("bateria"), "algoritmo": r["algoritmo"],
                                  "N": int(r["N"]), "Ts_s": float(r["Ts_s"]), "S_base_kW": float(r["S_base_kW"])},
             "warnings": list(r.get("avisos", []))}
    return data, summarize(r, val), extra


# ====================================================================== leitura de resultados (sem recalcular)
def load_csv(store, run_uid: str, name: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(store.run_data(run_uid, name)))


def new_request_id() -> str:
    return uuid.uuid4().hex


__all__ = ["OWNER", "PreflightError", "build_manifest", "input_frame", "is_running_here", "load_csv", "new_request_id",
           "output_frame", "owner_is_dead", "prepare", "recover", "science_fingerprint", "software_versions", "submit",
           "summarize", "wait"]
