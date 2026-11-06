"""Fontes de dados das previsões (Piso 2B): CSV, perfil manual, perfil sintético e perfis de referência.

Todas as fontes produzem o mesmo objeto (``forecasts.Candidate``) a partir de uma série normalizada; nenhuma
aplica os modelos científicos (FV/eólica/EMS). Reutilização da V1.6, sem duplicar algoritmos:

* leitura de CSV: decodificação de ``simulation.mix_engine._decode_bytes`` (UTF-8/latin-1) com separador explícito
  (``read_table``); conversão numérica com vírgula decimal: ``mix_engine._numeric``; detecção de colunas climáticas:
  ``mix_engine.detect_climate_columns`` (aliases do MIX) e de demanda: ``OPERATION_ALIASES`` + as palavras-chave
  de ``ems_integration.ponte.carga_de_dataframe``;
* perfis de referência de demanda: ``ponte.carga_walkforward`` e ``ponte.carga_copel`` (mesmas funções usadas pelas
  rodadas V1.6) e os CSVs de exemplo em ``Dados_exemplo/``;
* clima sintético de demonstração: ``orchestrator_runtime.synthetic_climate`` (o mesmo perfil do console V1.6).

``rederive(entry, get_blob)`` reconstrói a série normalizada a partir da origem registrada (arquivo + mapeamento,
gerador + parâmetros + semente, ou conjunto de referência + parâmetros) e confere o SHA-256.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np
import pandas as pd

from . import forecasts as F
from .initialization import ERROR

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "Dados_exemplo"
MAX_CSV_BYTES = 20 * 1024 * 1024
MAX_POINTS = 600_000                  # ~1 ano a 1 min: proteção da interface (não é limite científico)
PROVENANCE_BY_SOURCE = {
    # Procedências admitidas por tipo de origem (regra 7 do CLAUDE.md: sintético/referência nunca "medido").
    "manual": ("nao_declarado", "medido", "sintetico"),
    "csv": ("nao_declarado", "medido", "sintetico"),
    "sintetico": ("sintetico",),
    "referencia": ("referencia", "sintetico"),
}


# ====================================================================== CSV
_TIME_ABS = ("timestamp", "datetime", "data_hora", "datahora", "fecha_hora", "date_time", "data", "date", "hora", "time",
             "tempo", "instante")
_TIME_REL = {"t_min": "min", "tempo_min": "min", "minuto": "min", "minutos": "min", "min": "min", "t_s": "s",
             "tempo_s": "s", "segundos": "s", "seconds": "s", "t_h": "h", "horas": "h", "hours": "h"}
_DEMAND_WORDS = ("p_kw", "p_mw", "p_w", "potencia", "power", "load", "p_total", "demanda", "demand", "carga", "consumo")


@dataclass
class CsvInspection:
    data: bytes
    filename: str
    raw: pd.DataFrame | None = None
    errors: list[str] = field(default_factory=list)
    suggestion: dict = field(default_factory=dict)
    detected_units: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.raw is not None and not self.errors

    @property
    def columns(self) -> list[str]:
        return [str(c) for c in self.raw.columns] if self.raw is not None else []


SEPARATORS = (";", ",", "\t", "|")


def read_table(data: bytes) -> pd.DataFrame:
    """Leitura das previsões: decodificação da V1.6 (``mix_engine._decode_bytes``: UTF-8 com/sem BOM, latin-1) e
    separador ESCOLHIDO entre ``SEPARATORS`` pela linha de cabeçalho — o farejador automático de
    ``mix_engine.read_csv_auto`` pode adotar uma letra como separador em arquivos de uma coluna. Todas as células são
    lidas como TEXTO (sem conversões implícitas); números e instantes são interpretados depois, explicitamente."""
    from simulation.mix_engine import _decode_bytes

    text = _decode_bytes(data)
    header = next((ln for ln in text.splitlines() if ln.strip()), "")
    counts = {sep: header.count(sep) for sep in SEPARATORS}
    sep = max(counts, key=lambda k: counts[k])
    if counts[sep] == 0:
        raise ValueError("uma única coluna no cabeçalho (separador não reconhecido)")
    names = [h.strip().strip('"').strip() for h in header.split(sep)]
    if len(set(names)) != len(names):
        raise ValueError("cabeçalho com nomes de coluna repetidos")
    return pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False, skip_blank_lines=True,
                       on_bad_lines="error", engine="python")


def inspect_csv(data: bytes, filename: str, slot: str) -> CsvInspection:
    """Lê o arquivo e propõe um mapeamento (que o usuário confirma ou corrige). Nunca levanta exceção para
    arquivos malformados: os problemas voltam em ``errors``."""
    from simulation.mix_engine import detect_climate_columns

    rep = CsvInspection(bytes(data or b""), str(filename or "arquivo.csv"))
    if not rep.data.strip():
        rep.errors.append("Arquivo vazio.")
        return rep
    if len(rep.data) > MAX_CSV_BYTES:
        rep.errors.append(f"Arquivo maior que {MAX_CSV_BYTES // (1024 * 1024)} MB.")
        return rep
    if b"\x00" in rep.data[:4096]:
        rep.errors.append("O arquivo não parece ser texto CSV (conteúdo binário).")
        return rep
    try:
        raw = read_table(rep.data)
    except Exception as exc:                                    # noqa: BLE001 — qualquer falha do leitor é apresentável
        rep.errors.append(f"Não foi possível interpretar o CSV: {str(exc)[:200]}")
        return rep
    raw.columns = [str(c).strip() for c in raw.columns]
    if raw.shape[1] < 2:
        rep.errors.append("O CSV precisa de ao menos duas colunas (tempo e valores). Verifique o separador "
                          "(vírgula, ponto e vírgula ou tabulação).")
        return rep
    if len(set(raw.columns)) != len(raw.columns):
        rep.errors.append("Cabeçalho com nomes de coluna repetidos.")
        return rep
    if len(raw) == 0:
        rep.errors.append("O CSV não contém linhas de dados.")
        return rep
    if len(raw) > MAX_POINTS:
        rep.errors.append(f"O CSV tem {len(raw)} linhas (máximo nesta interface: {MAX_POINTS}).")
        return rep
    rep.raw = raw
    norm = {F.normalize_name(c): c for c in raw.columns}
    # tempo
    time_col, mode, unit = None, "absoluto", None
    for alias, u in _TIME_REL.items():
        if alias in norm:
            time_col, mode, unit = norm[alias], "relativo", u
            break
    if time_col is None:
        time_col = next((norm[a] for a in _TIME_ABS if a in norm), None)
    if time_col is None:
        time_col = next((c for n, c in norm.items() if any(w in n for w in ("stamp", "data", "date", "hora", "time", "fecha"))), None)
    if time_col is None:
        time_col = raw.columns[0]
    cols: dict[str, dict] = {}
    if slot == "demand":
        from simulation.mix_engine import OPERATION_ALIASES

        c = next((norm[F.normalize_name(a)] for a in OPERATION_ALIASES["demand_total_kw"] if F.normalize_name(a) in norm), None)
        if c is None:
            c = next((orig for n, orig in norm.items() if orig != time_col and any(w in n for w in _DEMAND_WORDS)), None)
        if c is not None:
            cols["demand_kW"] = {"column": c, "unit": F.detect_unit("demand_kW", c)}
    else:
        det = detect_climate_columns(raw.columns)
        semantic = {"ghi": "ghi_W_m2", "temperature": "temperature_C", "wind_speed": "wind_speed_m_s",
                    "wind_direction": "wind_direction_deg", "pressure": "pressure_hPa", "humidity": "humidity_pct"}
        for sem, var in semantic.items():
            c = det.get(sem)
            if c is None:          # cabeçalho já no formato canônico do SEEDS2 (p. ex. ghi_W_m2)
                c = norm.get(F.normalize_name(var))
            if c is not None and c != time_col:
                cols[var] = {"column": c, "unit": F.detect_unit(var, c)}
    rep.detected_units = {k: v["unit"] for k, v in cols.items()}
    rep.suggestion = {"time_mode": mode, "time_column": time_col, "date_order": "auto", "relative_unit": unit or "min",
                      "t0": None, "timezone": None, "duplicates": "recusar", "columns": cols}
    return rep


def normalize_csv(raw: pd.DataFrame, mapping: Mapping) -> F.Normalized:
    """Aplica um mapeamento (confirmado pelo usuário) a um CSV lido. Unidade não confirmada → erro."""
    findings: list[F.Finding] = []
    tcol = mapping.get("time_column")
    if tcol not in raw.columns:
        findings.append(F.Finding(ERROR, None, "sem_tempo", "Selecione a coluna de tempo."))
        return F.Normalized(None, mapping.get("timezone"), "nao_declarado", findings, [])
    tz = mapping.get("timezone") or None
    if not F.valid_timezone(tz):
        findings.append(F.Finding(ERROR, None, "fuso_invalido", f"Fuso horário desconhecido: {str(tz)[:40]!r}."))
        return F.Normalized(None, None, "nao_declarado", findings, [])
    if mapping.get("time_mode") == "relativo":
        parsed = F.parse_relative(raw[tcol], unit=mapping.get("relative_unit") or "min", t0=mapping.get("t0"), timezone=tz)
    else:
        parsed = F.parse_absolute(raw[tcol], date_order=mapping.get("date_order") or "auto", timezone=tz)
    columns, conversions = {}, {}
    used = {tcol}
    for var, m in (mapping.get("columns") or {}).items():
        if var not in F.VARIABLES or not m or not m.get("column"):
            continue
        col, unit = m["column"], m.get("unit")
        if col not in raw.columns:
            findings.append(F.Finding(ERROR, var, "coluna_inexistente", f"Coluna {col!r} inexistente no arquivo."))
            continue
        if col in used:
            findings.append(F.Finding(ERROR, var, "coluna_repetida", f"A coluna {col!r} foi mapeada mais de uma vez."))
            continue
        used.add(col)
        if unit not in F.UNITS[var]:
            findings.append(F.Finding(ERROR, var, "unidade_nao_confirmada",
                                      f"{F.VARIABLES[var].label}: confirme a unidade da coluna {col!r} (não indicada "
                                      "de forma inequívoca no cabeçalho)."))
            continue
        columns[var] = F.convert(var, F.numeric(raw[col]).to_numpy(dtype=float), unit)
        conversions[var] = unit
    parsed.findings = findings + parsed.findings
    if not columns and not any(f.level == ERROR for f in parsed.findings):
        parsed.findings.append(F.Finding(ERROR, None, "sem_variaveis", "Mapeie ao menos uma coluna de valores."))
    if any(f.level == ERROR for f in parsed.findings) and parsed.ts is not None and not columns:
        parsed.ts = None
    return F.assemble(parsed, columns, duplicates=mapping.get("duplicates") or "recusar", conversions=conversions)


def csv_candidate(insp: CsvInspection, slot: str, mapping: Mapping, *, inventory_ref: Mapping, provenance: str,
                  notes: str = "") -> F.Candidate:
    if not insp.ok:
        return F.Candidate(slot, None, None, F.Analysis([F.Finding(ERROR, None, "csv", e) for e in insp.errors]))
    norm = normalize_csv(insp.raw, mapping)
    clean = _clean_mapping(mapping)
    params = {"filename": insp.filename[:200], "size": len(insp.data), "sha256": sha256(insp.data).hexdigest(),
              "rows": int(len(insp.raw)), "columns": insp.columns[:200]}
    return F.build(slot, norm, source_type="csv", provenance=provenance, label=f"CSV · {insp.filename}"[:300],
                   inventory_ref=inventory_ref, params=params, mapping=clean,
                   original=(insp.data, {"name": insp.filename, "media_type": "text/csv"}), notes=notes)


def _clean_mapping(m: Mapping) -> dict:
    return {"time_mode": m.get("time_mode") or "absoluto", "time_column": m.get("time_column"),
            "date_order": m.get("date_order") or "auto", "relative_unit": m.get("relative_unit") or "min",
            "t0": m.get("t0") or None, "timezone": m.get("timezone") or None,
            "duplicates": m.get("duplicates") or "recusar",
            "columns": {k: {"column": v.get("column"), "unit": v.get("unit")}
                        for k, v in (m.get("columns") or {}).items() if v and v.get("column")}}


# ====================================================================== perfil manual
def regular_table(variables: tuple[str, ...], start: str, step_s: int, n: int, values: Mapping[str, list] | None = None) -> pd.DataFrame:
    """Tabela editável com instantes regulares (construção por intervalos). Valores não informados ficam vazios."""
    n = int(max(0, min(n, MAX_POINTS)))
    ts = pd.Timestamp(start) + pd.to_timedelta(np.arange(n) * int(step_s), unit="s")
    df = pd.DataFrame({"timestamp": ts})
    for k in variables:
        col = list((values or {}).get(k) or [])[:n]
        df[k] = pd.array(col + [None] * (n - len(col)), dtype="Float64")
    return df


def parse_pasted(text: str) -> tuple[list[float | None], list[str]]:
    """Valores colados (uma coluna): separadores = quebra de linha, ';', tabulação ou espaço; a vírgula é sempre
    DECIMAL (``12,5`` = 12.5). Célula vazia/``-`` → ausente."""
    out: list[float | None] = []
    bad: list[str] = []
    import re

    for tok in [t for t in re.split(r"[\n;\t ]+", str(text or "").strip()) if t != ""]:
        if tok in ("-", "NA", "na", "NaN", "nan"):
            out.append(None)
            continue
        try:
            out.append(float(tok.replace(",", ".")))
        except ValueError:
            bad.append(tok[:20])
            out.append(None)
    return out, bad


def manual_candidate(table: pd.DataFrame, slot: str, *, timezone: str | None, inventory_ref: Mapping, provenance: str,
                     construction: Mapping | None = None, notes: str = "") -> F.Candidate:
    variables = [k for k in F.SLOT_VARIABLES[slot] if k in table.columns]
    t = table.copy()
    keep = t["timestamp"].notna() | t[variables].notna().any(axis=1) if variables else t["timestamp"].notna()
    t = t[keep].reset_index(drop=True)                            # linhas totalmente vazias da tabela são ignoradas
    findings: list[F.Finding] = []
    if not F.valid_timezone(timezone):
        findings.append(F.Finding(ERROR, None, "fuso_invalido", "Fuso horário inválido."))
    ts = pd.to_datetime(t["timestamp"], errors="coerce")
    bad = ts.isna().to_numpy()
    parsed = F.ParsedTime(ts=None if bad.any() else ts, timezone=timezone,
                          timezone_source="usuario" if timezone else "nao_declarado", findings=findings)
    if bad.any():
        parsed.findings.append(F.Finding(ERROR, None, "timestamp_invalido",
                                         f"{int(bad.sum())} linha(s) sem instante válido (linhas {', '.join(str(i + 1) for i in np.flatnonzero(bad)[:4])})."))
    cols = {k: pd.to_numeric(t[k], errors="coerce").to_numpy(dtype=float) for k in variables}
    norm = F.assemble(parsed, cols, duplicates="recusar")
    return F.build(slot, norm, source_type="manual", provenance=provenance, label="Perfil manual (tabela)",
                   inventory_ref=inventory_ref, params={"construction": dict(construction or {})}, notes=notes)


# ====================================================================== perfis sintéticos (reprodutíveis)
GENERATOR_VERSION = 1


def _grid(p: Mapping) -> pd.DatetimeIndex:
    step, dur = int(p["step_s"]), int(p["duration_s"])
    if step <= 0 or dur <= 0:
        raise ValueError("Passo e duração devem ser positivos.")
    n = dur // step + 1
    if n > MAX_POINTS:
        raise ValueError(f"Perfil com {n} pontos (máximo {MAX_POINTS}).")
    return pd.Timestamp(p["t0"]) + pd.to_timedelta(np.arange(n) * step, unit="s")


def _hours(ts: pd.DatetimeIndex) -> np.ndarray:
    return ts.hour.to_numpy(float) + ts.minute.to_numpy(float) / 60 + ts.second.to_numpy(float) / 3600


def _noise(p: Mapping, n: int, stream: int = 0) -> np.ndarray:
    pct = float(p.get("noise_pct") or 0.0)
    if pct <= 0:
        return np.zeros(n)
    rng = np.random.default_rng([int(p["seed"]), stream])          # semente registrada → reprodução exata
    return rng.normal(0.0, pct / 100.0, n)


def _gen_demand_constant(p: Mapping) -> pd.DataFrame:
    ts = _grid(p)
    v = float(p["value_kW"]) * (1.0 + _noise(p, len(ts)))
    return pd.DataFrame({"timestamp": ts, "demand_kW": np.maximum(v, 0.0)})


def _gen_demand_blocks(p: Mapping) -> pd.DataFrame:
    """Tramos horários: lista [(hora_inicial, kW)] ordenada; cada valor vale até o tramo seguinte (ciclo de 24 h)."""
    ts = _grid(p)
    blocks = sorted((float(h), float(v)) for h, v in p["blocks"])
    if not blocks:
        raise ValueError("Defina ao menos um tramo horário.")
    h = _hours(ts)
    starts = np.array([b[0] for b in blocks])
    vals = np.array([b[1] for b in blocks])
    idx = np.searchsorted(starts, h, side="right") - 1          # antes do 1º tramo → último tramo (ciclo diário)
    v = vals[idx] * (1.0 + _noise(p, len(ts)))
    return pd.DataFrame({"timestamp": ts, "demand_kW": np.maximum(v, 0.0)})


def _gen_demand_daily(p: Mapping) -> pd.DataFrame:
    """Padrão diário: base + até dois picos gaussianos (hora e largura configuráveis), periódico em 24 h."""
    ts = _grid(p)
    h = _hours(ts)
    v = np.full(len(ts), float(p["base_kW"]))
    for peak in p.get("peaks") or []:
        hp, width, amp = float(peak["hour"]), float(peak["width_h"]), float(peak["kW"])
        dh = (h - hp + 12.0) % 24.0 - 12.0
        v += amp * np.exp(-0.5 * (dh / max(width, 1e-6)) ** 2)
    v = v * (1.0 + _noise(p, len(ts)))
    return pd.DataFrame({"timestamp": ts, "demand_kW": np.maximum(v, 0.0)})


def _gen_climate(p: Mapping) -> pd.DataFrame:
    """Clima sintético SIMPLES e explicitamente hipotético (não é previsão meteorológica). Cada variável é
    gerada só se pedida: GHI em sino diurno (mesma forma do clima sintético V1.6: sen^1,25 entre nascer e pôr do sol),
    temperatura senoidal diária, vento = média + oscilação + ruído com semente, direção/pressão/umidade constantes."""
    ts = _grid(p)
    h = _hours(ts)
    n = len(ts)
    out = {"timestamp": ts}
    vs = p["variables"]
    if "ghi_W_m2" in vs:
        rise, sset = float(p["sunrise_h"]), float(p["sunset_h"])
        if sset <= rise:
            raise ValueError("O pôr do sol deve ser posterior ao nascer do sol.")
        x = np.clip((h - rise) / (sset - rise), 0.0, 1.0)
        ghi = float(p["ghi_peak_W_m2"]) * np.clip(np.sin(np.pi * x), 0.0, None) ** 1.25
        ghi[(h <= rise) | (h >= sset)] = 0.0
        out["ghi_W_m2"] = ghi * np.clip(1.0 + _noise(p, n, 1), 0.0, None)
    if "temperature_C" in vs:
        tmin, tmax, hmax = float(p["t_min_C"]), float(p["t_max_C"]), float(p.get("t_max_hour", 15.0))
        out["temperature_C"] = (tmin + tmax) / 2 + (tmax - tmin) / 2 * np.cos(2 * np.pi * (h - hmax) / 24.0)
    if "wind_speed_m_s" in vs:
        mean, amp, per = float(p["wind_mean_m_s"]), float(p.get("wind_amp_m_s", 0.0)), float(p.get("wind_period_h", 24.0))
        w = mean + amp * np.sin(2 * np.pi * h / max(per, 1e-6)) + mean * _noise(p, n, 2)
        out["wind_speed_m_s"] = np.maximum(w, 0.0)
    if "wind_direction_deg" in vs:
        out["wind_direction_deg"] = np.full(n, float(p["wind_dir_deg"]) % 360.0)
    if "pressure_hPa" in vs:
        out["pressure_hPa"] = np.full(n, float(p["pressure_hPa"]))
    if "humidity_pct" in vs:
        out["humidity_pct"] = np.full(n, float(p["humidity_pct"]))
    return pd.DataFrame(out)


GENERATORS: dict[str, dict] = {
    "demanda_constante": {"slot": "demand", "label": "Demanda constante", "fn": _gen_demand_constant},
    "demanda_tramos": {"slot": "demand", "label": "Demanda por tramos horários", "fn": _gen_demand_blocks},
    "demanda_diaria": {"slot": "demand", "label": "Padrão diário (base + picos)", "fn": _gen_demand_daily},
    "clima_simples": {"slot": "climate", "label": "Clima sintético simples (dia típico hipotético)", "fn": _gen_climate},
}


def generate(name: str, params: Mapping) -> pd.DataFrame:
    return GENERATORS[name]["fn"](params)


def synthetic_candidate(name: str, params: Mapping, *, timezone: str | None, inventory_ref: Mapping,
                        notes: str = "") -> F.Candidate:
    g = GENERATORS[name]
    p = dict(params)
    p.setdefault("seed", None)
    if float(p.get("noise_pct") or 0) > 0 and p.get("seed") is None:
        p["seed"] = 0
    try:
        df = generate(name, p)
    except (KeyError, ValueError, TypeError) as exc:
        return F.Candidate(g["slot"], None, None, F.Analysis([F.Finding(ERROR, None, "gerador", f"Parâmetros inválidos: {exc}")]))
    parsed = F.ParsedTime(ts=df["timestamp"], timezone=timezone, timezone_source="usuario" if timezone else "nao_declarado")
    norm = F.assemble(parsed, {k: df[k].to_numpy(float) for k in df.columns if k != "timestamp"})
    norm.transforms.append(f"Gerado por '{name}' (versão {GENERATOR_VERSION}) — perfil SINTÉTICO hipotético.")
    params_out = {"generator": name, "generator_version": GENERATOR_VERSION, "seed": p.get("seed"),
                  "params": {k: v for k, v in p.items() if k != "seed"}}
    return F.build(g["slot"], norm, source_type="sintetico", provenance="sintetico",
                   label=f"Sintético · {g['label']}", inventory_ref=inventory_ref, params=params_out, notes=notes)


# ====================================================================== perfis de referência (V1.6)
def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def walkforward_options() -> list[tuple[str, str, int]]:
    from ems_integration import ponte

    d = ponte.opcoes_walkforward()
    return [(str(r.scenario), str(r.profile), int(r.start_hour)) for r in d.itertuples()]


def _ref_walkforward(p: Mapping) -> pd.DataFrame:
    from ems_integration import ponte

    c = ponte.carga_walkforward(p["scenario"], p["profile"], int(p["start_hour"]))
    return pd.DataFrame({"timestamp": c.t0 + pd.to_timedelta(c.t_min, unit="min"), "demand_kW": c.P_kW})


def _ref_copel(p: Mapping) -> pd.DataFrame:
    from ems_integration import ponte

    c = ponte.carga_copel(p["day"], str(p["date"]))
    return pd.DataFrame({"timestamp": c.t0 + pd.to_timedelta(c.t_min, unit="min"), "demand_kW": c.P_kW})


def _ref_climate_v16(p: Mapping) -> pd.DataFrame:
    import orchestrator_runtime as RT
    from ems_integration import ponte

    n = int(p["duration_min"]) + 1
    carga = ponte.PerfilCarga(np.arange(n, dtype=float), np.zeros(n), pd.Timestamp(p["t0"]), "grade do clima")
    c = RT.synthetic_climate(carga)                      # MESMO perfil do console V1.6 (sem reimplementação)
    return pd.DataFrame({"timestamp": pd.to_datetime(c["timestamp"]), "ghi_W_m2": c["GHI_W_m2"],
                         "temperature_C": c["temperature_C"], "wind_speed_m_s": c["wind_speed_mps"],
                         "wind_direction_deg": c["wind_direction_deg"], "pressure_hPa": c["pressure_hPa"],
                         "humidity_pct": c["humidity_pct"]})


def _ref_file(fname: str, mapping: dict) -> Callable[[Mapping], pd.DataFrame]:
    def load(_p: Mapping) -> pd.DataFrame:
        raw = read_table((EXAMPLES / fname).read_bytes())
        raw.columns = [str(c).strip() for c in raw.columns]
        norm = normalize_csv(raw, mapping)
        if norm.df is None or any(f.level == ERROR for f in norm.findings):
            raise ValueError(f"Conjunto de referência {fname} ilegível.")
        return norm.df
    return load


def _abs(cols: dict) -> dict:
    return {"time_mode": "absoluto", "time_column": "timestamp", "date_order": "auto", "timezone": None,
            "duplicates": "recusar", "columns": {k: {"column": c, "unit": F.VARIABLES[k].unit} for k, c in cols.items()}}


_SOLAR_FILES = {f"previsao_solar_{h}": f"PREVISAO_SOLAR_120min_{h}.csv" for h in ("06", "12", "16", "18")}
REFERENCES: dict[str, dict] = {
    "walkforward": {"slot": "demand", "label": "Walk-forward de referência (embarcação, janelas de 2 h)",
                    "provenance": "referencia", "fn": _ref_walkforward, "file": "ems_integration/dados/ems_walkforward.csv",
                    "note": "Mesma função das rodadas V1.6 (ponte.carga_walkforward). Instantes do próprio conjunto; "
                            "fuso não declarado."},
    "copel_b1": {"slot": "demand", "label": "Curva típica COPEL B1 (24 h, 1 min)", "provenance": "referencia",
                 "fn": _ref_copel, "file": None,
                 "note": "Perfil típico SEM data própria: a data é escolhida aqui (convenção explícita). Mesma função "
                         "das rodadas V1.6 (ponte.carga_copel)."},
    "exemplo_mix_operacao": {"slot": "demand", "label": "Exemplo MIX — demanda total (Dados_exemplo)",
                             "provenance": "referencia",
                             "fn": _ref_file("mix_operacao_exemplo.csv", _abs({"demand_kW": "P_demanda_total_kW"})),
                             "file": "Dados_exemplo/mix_operacao_exemplo.csv", "note": "Arquivo de exemplo do MIX V1.6."},
    "clima_sintetico_v16": {"slot": "climate", "label": "Clima sintético de demonstração V1.6",
                            "provenance": "sintetico", "fn": _ref_climate_v16, "file": None,
                            "note": "orchestrator_runtime.synthetic_climate — o mesmo perfil do console V1.6 "
                                    "('Sintético diário'). Sintético, nunca medido."},
    **{k: {"slot": "climate", "label": f"Exemplo solar 120 min ({f[-6:-4]} h) — GHI e Tamb", "provenance": "referencia",
           "fn": _ref_file(f, _abs({"ghi_W_m2": "GHI", "temperature_C": "Tamb"})), "file": f"Dados_exemplo/{f}",
           "note": "Arquivo de exemplo da bancada solar V1.6 (unidades usadas pela V1.6: W/m², °C). Não é medição desta "
                   "instalação."} for k, f in _SOLAR_FILES.items()},
    "exemplo_mix_clima": {"slot": "climate", "label": "Exemplo MIX — clima completo (10 min)", "provenance": "referencia",
                          "fn": _ref_file("mix_clima_exemplo.csv", _abs({
                              "ghi_W_m2": "GHI", "temperature_C": "temperatura_C", "wind_speed_m_s": "wind_speed",
                              "wind_direction_deg": "wind_direction", "pressure_hPa": "pressure_hPa",
                              "humidity_pct": "humidity_pct"})),
                          "file": "Dados_exemplo/mix_clima_exemplo.csv", "note": "Arquivo de exemplo do MIX V1.6."},
    "eolico_ceara_1sem": {"slot": "climate", "label": "Eólico sintético Ceará — 1 semana (10 min)",
                          "provenance": "sintetico",
                          "fn": _ref_file("perfil_eolico_sintetico_ceara_1_semana_10min.csv", _abs({
                              "wind_speed_m_s": "wind_speed", "wind_direction_deg": "wind_direction",
                              "temperature_C": "temperature", "pressure_hPa": "pressure", "humidity_pct": "humidity"})),
                          "file": "Dados_exemplo/perfil_eolico_sintetico_ceara_1_semana_10min.csv",
                          "note": "Arquivo de exemplo da bancada eólica V1.6 (sintético segundo o próprio nome)."},
}


def reference_candidate(key: str, params: Mapping, *, inventory_ref: Mapping, notes: str = "") -> F.Candidate:
    r = REFERENCES[key]
    p = dict(params)
    try:
        df = r["fn"](p)
    except (KeyError, ValueError, TypeError, FileNotFoundError) as exc:
        return F.Candidate(r["slot"], None, None, F.Analysis([F.Finding(ERROR, None, "referencia", f"Conjunto indisponível: {exc}")]))
    parsed = F.ParsedTime(ts=pd.to_datetime(df["timestamp"]), timezone=None, timezone_source="nao_declarado")
    norm = F.assemble(parsed, {k: df[k].to_numpy(float) for k in df.columns if k != "timestamp"})
    norm.transforms.append(f"Conjunto de referência do software: {r['label']}.")
    params_out = {"dataset": key, "params": p}
    if r.get("file"):
        params_out["file"] = r["file"]
        params_out["file_sha256"] = _file_sha(ROOT / r["file"])
    return F.build(r["slot"], norm, source_type="referencia", provenance=r["provenance"], label=f"Referência · {r['label']}",
                   inventory_ref=inventory_ref, params=params_out, notes=notes)


# ====================================================================== reprodutibilidade
def rederive(entry: Mapping, get_blob: Callable[[str], bytes]) -> tuple[bool, str]:
    """Reconstrói a série normalizada a partir da origem registrada e compara o SHA-256 com ``entry['data']``."""
    st = entry.get("source_type")
    try:
        F.load(entry, get_blob)                         # integridade da série ARMAZENADA (SHA-256, formato, tamanho)
    except F.ForecastDataError as exc:
        return False, str(exc)
    try:
        if st == "manual":
            return True, "Perfil manual: a série gravada é a própria origem (integridade do SHA-256 verificada)."
        if st == "csv":
            data = get_blob(entry["blob"])
            if sha256(data).hexdigest() != entry["blob"]:
                return False, "Arquivo original corrompido (hash divergente)."
            raw = read_table(data)
            raw.columns = [str(c).strip() for c in raw.columns]
            norm = normalize_csv(raw, entry["mapping"])
        elif st == "sintetico":
            p = entry["params"]
            if p.get("generator_version") != GENERATOR_VERSION:
                return False, f"Gerador na versão {p.get('generator_version')}; este software implementa a versão {GENERATOR_VERSION}."
            df = generate(p["generator"], {**p["params"], "seed": p.get("seed")})
            norm = F.assemble(F.ParsedTime(ts=df["timestamp"]), {k: df[k].to_numpy(float) for k in df.columns if k != "timestamp"})
        elif st == "referencia":
            p = entry["params"]
            r = REFERENCES[p["dataset"]]
            if p.get("file") and _file_sha(ROOT / p["file"]) != p.get("file_sha256"):
                return False, "O arquivo de referência do software mudou desde a gravação (SHA-256 diferente)."
            df = r["fn"](p.get("params") or {})
            norm = F.assemble(F.ParsedTime(ts=pd.to_datetime(df["timestamp"])),
                              {k: df[k].to_numpy(float) for k in df.columns if k != "timestamp"})
        else:
            return False, "Tipo de origem desconhecido."
    except Exception as exc:                                    # noqa: BLE001 — relatório apresentável
        return False, f"Falha ao reconstruir: {str(exc)[:200]}"
    if norm.df is None:
        return False, "A origem registrada não produz mais uma série válida."
    h = F.digest(F.to_csv_bytes(norm.df))
    if h != entry.get("data"):
        return False, f"A reconstrução produz outra série (SHA-256 {h[:12]}… ≠ {str(entry.get('data'))[:12]}…)."
    return True, "Série reconstruída a partir da origem registrada com o mesmo SHA-256."


__all__ = ["CsvInspection", "GENERATORS", "GENERATOR_VERSION", "MAX_POINTS", "PROVENANCE_BY_SOURCE", "REFERENCES",
           "csv_candidate", "generate", "inspect_csv", "read_table", "manual_candidate", "normalize_csv", "parse_pasted",
           "reference_candidate", "regular_table", "rederive", "synthetic_candidate", "walkforward_options"]
