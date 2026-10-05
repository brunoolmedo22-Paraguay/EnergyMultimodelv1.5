"""Ponte plataforma → EMS.

Converte as saídas dos módulos da plataforma (DataFrames de ``simulate_profile``,
``simulate_tremblay`` etc.) no PACOTE DE TROCA lido pelo EMS: os mesmos
esquemas de CSV que ``montar_fontes.m`` consumia (termica.csv, eolica.csv,
fc.csv, bateria.csv) + carga.csv e pv.csv (``t_min,P_kW``) + ems_config.json.
Solar e eólica são não despacháveis: suas séries abatem a carga antes da otimização.
O pacote é o contrato auditável entre a plataforma e o otimizador: pode ser
exportado em zip e reexecutado depois.

Também gera os perfis de CARACTERIZAÇÃO. O EMS não recebe um modelo de FC ou de
bateria: ele deriva envelope, rampa, curva kg H2/kWh e eficiências a partir do
que OBSERVA no CSV. Por isso a série precisa (a) cobrir a missão inteira e (b)
varrer a faixa de operação — um perfil qualquer de 6 min, como o fc.csv
antigo, deixa a fonte indisponível no resto da missão.
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DADOS_DIR = Path(__file__).resolve().parent / "dados"

FC_COLUNAS = [
    "timestamp", "P_FC_requested_kW", "P_FC_delivered_kW", "P_deficit_kW", "state",
    "current_A", "V_stack_V", "P_stack_kW", "hydrogen_supplied_kg_h",
    "net_electrical_efficiency_LHV_percent", "P_aux_equivalent_kW", "P_dc_dc_loss_kW",
    "limitation_flag", "limitation_reason", "T_ambient_C", "T_coolant_in_C", "V_bus_V",
]

# valores de arquitetura_embarcacao.m / parametros_economicos.m do EMS original (defaults da UI)
ARCH_PADRAO = {
    "eta_dc": 0.97, "eta_dc1": 0.97, "eta_dc2": 0.96,
    "bat_Q_kWh": 200.0, "bat_SOC_min": 0.30, "bat_SOC_max": 0.80, "pv_P_rated_kWp": 50.0,
}
ECON_PADRAO = {
    "preco_H2_rs_kg": 25.0, "c_deg_bateria_rs_kWh": 0.08,
    "pen_deficit_rs_kWh": 50.0, "pen_excesso_rs_kWh": 0.5,
}


# ================================================================ CARGA
@dataclass
class PerfilCarga:
    t_min: np.ndarray
    P_kW: np.ndarray
    t0: pd.Timestamp
    descricao: str

    @property
    def duracao_min(self) -> float:
        return float(self.t_min[-1] - self.t_min[0])

    def df(self) -> pd.DataFrame:
        return pd.DataFrame({"t_min": self.t_min, "P_kW": self.P_kW})


def opcoes_walkforward() -> pd.DataFrame:
    d = pd.read_csv(DADOS_DIR / "ems_walkforward.csv", encoding="utf-8-sig",
                    usecols=["scenario", "profile", "start_hour"])
    return d.drop_duplicates().reset_index(drop=True)


def carga_walkforward(scenario: str, profile: str, start_hour: int) -> PerfilCarga:
    """Mesmo filtro de ``carregar_perfil_walkforward.m``."""
    d = pd.read_csv(DADOS_DIR / "ems_walkforward.csv", encoding="utf-8-sig")
    j = d[(d.scenario == scenario) & (d.profile == profile) & (d.start_hour == int(start_hour))].sort_values("t_min")
    if j.empty:
        raise ValueError(f"Sem janela walk-forward para {scenario} × {profile} às {start_hour}h.")
    t = j.t_min.to_numpy(float)
    return PerfilCarga(t - t[0], j.P_total_kw.to_numpy(float), pd.Timestamp(j.timestamp.iloc[0]),
                       f"Walk-forward · {scenario} × {profile} · {int(start_hour):02d}h")


def carga_copel(dia: str, data_ref: str = "2026-09-01") -> PerfilCarga:
    d = pd.read_csv(DADOS_DIR / f"carga_copel_b1_{dia}.csv")
    return PerfilCarga(d.t_min.to_numpy(float), d.P_kW.to_numpy(float), pd.Timestamp(data_ref),
                       f"COPEL B1 · {dia}")


def carga_de_dataframe(raw: pd.DataFrame, nome: str, t0: pd.Timestamp | None = None) -> PerfilCarga:
    """Aceita ``t_min,P_kW`` (como carregar_perfil_csv.m) ou ``timestamp,P_kW``."""
    cols = {c.lower().strip(): c for c in raw.columns}
    col_p = next((cols[c] for c in cols if any(k in c for k in ("p_kw", "potencia", "power", "load", "p_total"))), None)
    if col_p is None:
        raise ValueError("CSV de carga precisa de uma coluna de potência em kW (ex.: P_kW).")
    col_t = next((cols[c] for c in cols if any(k in c for k in ("t_min", "tempo", "time"))), None)
    if col_t is not None and "stamp" not in col_t.lower():
        t = pd.to_numeric(raw[col_t], errors="coerce").to_numpy(float)
        t0 = t0 or pd.Timestamp("2026-09-01 00:00")
    else:
        col_ts = next((cols[c] for c in cols if "stamp" in c or "data" in c), None)
        if col_ts is None:
            raise ValueError("CSV de carga precisa de t_min ou timestamp.")
        ts = pd.to_datetime(raw[col_ts])
        t0 = ts.iloc[0]
        t = ((ts - t0).dt.total_seconds() / 60).to_numpy(float)
    p = pd.to_numeric(raw[col_p], errors="coerce").to_numpy(float)
    ok = np.isfinite(t) & np.isfinite(p)
    t, p = t[ok], p[ok]
    grade = np.arange(t.min(), t.max() + 1e-9, 1.0)       # Ts_min = 1, como no config_cenario
    return PerfilCarga(grade - grade[0], np.interp(grade, t, p), t0, nome)


def recortar(perfil: PerfilCarga, inicio_min: float, duracao_min: float) -> PerfilCarga:
    m = (perfil.t_min >= inicio_min - 1e-9) & (perfil.t_min <= inicio_min + duracao_min + 1e-9)
    t = perfil.t_min[m]
    if t.size < 5:
        raise ValueError("Janela de carga muito curta.")
    return PerfilCarga(t - t[0], perfil.P_kW[m], perfil.t0 + pd.Timedelta(minutes=float(t[0])),
                       f"{perfil.descricao} · {inicio_min:.0f}–{inicio_min + duracao_min:.0f} min")


# ========================================================= CARACTERIZAÇÃO
def _grade(t0: pd.Timestamp, duracao_min: float) -> pd.DatetimeIndex:
    return pd.date_range(t0, periods=int(np.ceil(duracao_min)) + 2, freq="1min")


def caracterizar_fc(t0: pd.Timestamp, duracao_min: float, P_max_kW: float | None = None,
                    passo_s: float = 2.0, retencao_min: int = 2) -> pd.DataFrame:
    """Roda o modelo dinâmico PEMFC (1 stack) com uma escada que varre 10–100 %
    da potência líquida e inclui saltos grandes (20→100 %, 100→10 %) para que a
    rampa-limite do modelo apareça no CSV. Não passa do máximo físico — pedir
    acima leva o modelo a FAULT_LIMITED, que o EMS lê como indisponibilidade."""
    from h2_pemfc import Equivalent65kWHorizonDynamicModel
    from h2_pemfc.ems_input import prepare_ems_profile

    modelo = Equivalent65kWHorizonDynamicModel()
    pmax = min(float(P_max_kW or modelo._physical_max_power_kW), float(modelo._physical_max_power_kW))
    niveis = np.array([0.1, 0.3, 0.5, 0.7, 0.9, 1.0, 0.2, 1.0, 0.1, 0.6, 0.4, 0.8]) * pmax
    ts = _grade(t0, duracao_min)
    ref = np.resize(np.repeat(niveis, retencao_min), ts.size)
    raw = pd.DataFrame({"timestamp": ts, "P_FC_requested_kW": np.round(ref, 4)})
    prep = prepare_ems_profile(raw, dynamic_model=modelo)
    out = modelo.simulate_profile(prep.profile, internal_time_step_s=passo_s)
    return out[[c for c in FC_COLUNAS if c in out.columns]].copy()


def energia_banco_kWh(modelo: str, battery_key: str | None, Ns: int, Np: int) -> tuple[float, float]:
    """(E_nominal_kWh, Q_Ah da célula) — mesma conta da tela do módulo Bateria."""
    from models.battery_model import BATTERY_TREMBLAY, RC_CAPACITY_AH, RC_V_NOM_V, TREMBLAY_BATTERIES

    if modelo == BATTERY_TREMBLAY:
        b = TREMBLAY_BATTERIES[battery_key or "liion_3p3v_2p3ah"]
        return b.V_nom_V * b.Q_Ah * Ns * Np / 1000.0, b.Q_Ah
    return RC_V_NOM_V * RC_CAPACITY_AH * Ns * Np / 1000.0, RC_CAPACITY_AH


def caracterizar_bateria(t0: pd.Timestamp, duracao_min: float, modelo: str, battery_key: str | None,
                         Ns: int, Np: int, soc0: float, c_desc: float = 1.0, c_carga: float = 0.5,
                         passo_s: float = 10.0) -> tuple[pd.DataFrame, float]:
    """Escada de corrente ±(25, 50, 100 %) da taxa C escolhida, com carga e
    descarga (a calibração de Rint/eficiências em montar_fontes exige os dois
    sentidos e corrente variando). Durações compensadas para Ah líquido ≈ 0."""
    from models.battery_model import BATTERY_TREMBLAY, export_battery_dataframe, simulate_2rc, simulate_tremblay

    E_kWh, Q_Ah = energia_banco_kWh(modelo, battery_key, Ns, Np)
    I1C = Q_Ah * Np
    seg_d = 3.0
    seg_c = seg_d * c_desc / c_carga
    ciclo = [(+f * c_desc * I1C, seg_d) for f in (0.25, 0.5, 1.0)] + [(0.0, 1.0)] + \
            [(-f * c_carga * I1C, seg_c) for f in (0.25, 0.5, 1.0)] + [(0.0, 1.0)]
    t_s = np.arange(0.0, (duracao_min + 2) * 60.0 + 1e-9, passo_s)
    periodo = sum(d for _, d in ciclo) * 60.0
    limites = np.cumsum([d * 60.0 for _, d in ciclo])
    fase = np.searchsorted(limites, np.mod(t_s, periodo), side="right")
    corrente = np.array([ciclo[min(i, len(ciclo) - 1)][0] for i in fase])
    prof = pd.DataFrame({"timestamp": t0 + pd.to_timedelta(t_s, unit="s"), "current_A": corrente})
    if modelo == BATTERY_TREMBLAY:
        r = simulate_tremblay(prof, battery_key=battery_key or "liion_3p3v_2p3ah",
                              n_series=int(Ns), n_parallel=int(Np), initial_soc=float(soc0))
    else:
        r = simulate_2rc(prof, n_series=int(Ns), n_parallel=int(Np), initial_soc=float(soc0))
    return export_battery_dataframe(r), E_kWh


def disponibilidade_termica(t0: pd.Timestamp, duracao_min: float, cfg) -> pd.DataFrame:
    """Térmica pedida no Pmax em toda a missão → contractual_target = teto disponível."""
    from models.thermal_model import (ThermalInputMapping, evaluate_thermal_dispatch,
                                      export_thermal_dataframe, prepare_thermal_profile)

    ts = _grade(t0, duracao_min)
    raw = pd.DataFrame({"timestamp": ts, "power_requested_mw": float(cfg.pmax_mw)})
    prof = prepare_thermal_profile(raw, ThermalInputMapping("timestamp", "power_requested_mw", None))
    r, _ = evaluate_thermal_dispatch(prof, cfg)
    return export_thermal_dataframe(r)


def opcoes_termica(cfg) -> dict:
    """Parâmetros da ThermalConfig que o CSV não carrega e o EMS precisa."""
    d = {"termica_cvu_rs_kWh": float(cfg.cvu_rs_mwh) / 1000.0,
         "termica_Pmin_kW": float(cfg.pmin_technical_mw) * 1000.0}
    if cfg.ramp_up_mw_min:
        d["termica_ramp_kW_min"] = float(cfg.ramp_up_mw_min) * 1000.0
    return d


# ============================================================ ALINHAMENTO
def alinhar_horario(df: pd.DataFrame, t0: pd.Timestamp, duracao_min: float, col: str = "timestamp") -> tuple[pd.DataFrame, str]:
    """``montar_fontes.m`` alinha cada fonte ao SEU PRÓPRIO 1º instante. Para séries
    mais longas que a missão (térmica 24 h, eólica 41 h), isso usa a meia-noite
    quando a missão começa às 08h. Aqui cortamos a série no mesmo horário do dia
    de t0 ANTES de escrever o CSV — o MATLAB continua lendo relativo, sem mudança."""
    ts = pd.to_datetime(df[col])
    passo = (ts.iloc[1] - ts.iloc[0]) if len(ts) > 1 else pd.Timedelta(minutes=1)
    alvo = pd.Timestamp.combine(ts.iloc[0].date(), t0.time())
    if alvo < ts.iloc[0]:
        # Série que começa um passo depois da missão (ex.: 12:01 para missão às 12:00)
        # já está no horário certo; só vai para o dia seguinte se a diferença for maior.
        alvo = ts.iloc[0] if ts.iloc[0] - alvo <= passo else alvo + pd.Timedelta(days=1)
    if alvo > ts.iloc[-1]:
        return df, (f"a série ({ts.iloc[0]:%H:%M}–{ts.iloc[-1]:%H:%M}) não contém o horário da missão "
                    f"({t0:%H:%M}) — usada a partir do seu próprio início")
    i0 = int(np.searchsorted(ts.to_numpy(), np.datetime64(alvo), side="right") - 1)
    out = df.iloc[max(i0, 0):].reset_index(drop=True)
    cobre = (pd.to_datetime(out[col]).iloc[-1] - pd.to_datetime(out[col]).iloc[0]).total_seconds() / 60
    msg = f"cortado a partir de {pd.to_datetime(out[col]).iloc[0]:%d/%m %H:%M}"
    if cobre < duracao_min:
        msg += f" (cobre só {cobre:.0f} de {duracao_min:.0f} min)"
    return out, msg


def pv_de_solar(result: pd.DataFrame, t0: pd.Timestamp | None, duracao_min: float, alinhar: bool) -> tuple[pd.DataFrame, str]:
    """Resultado do módulo Solar (P_array em W, tempo no índice ou em ``timestamp``) → t_min,P_kW."""
    tempo = result["timestamp"] if "timestamp" in result.columns else result.index
    df = pd.DataFrame({"timestamp": pd.to_datetime(np.asarray(tempo)),
                       "P_kW": result["P_array"].to_numpy(float) / 1000.0})
    msg = "início próprio"
    if alinhar and t0 is not None:
        df, msg = alinhar_horario(df, t0, duracao_min)
    ts = pd.to_datetime(df.timestamp)
    return pd.DataFrame({"t_min": (ts - ts.iloc[0]).dt.total_seconds() / 60, "P_kW": df.P_kW}), msg


def eolica_de_modulo(result: pd.DataFrame, t0: pd.Timestamp | None, duracao_min: float,
                     alinhar: bool) -> tuple[pd.DataFrame, str]:
    """Resultado do módulo Eólica → CSV no esquema de ``export_wind_dataframe``."""
    from models.wind_model import export_wind_dataframe

    df = export_wind_dataframe(result)
    if alinhar and t0 is not None:
        return alinhar_horario(df, t0, duracao_min)
    return df, "início próprio"


# ================================================================ ESCRITA
def _para_csv(df: pd.DataFrame, path: Path) -> None:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_bool_dtype(out[c]):
            out[c] = out[c].astype(int)          # readtable do MATLAB: sem ambiguidade true/false
        elif pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d %H:%M:%S")
        elif out[c].dtype == object and c in ("limit_flag", "limitation_flag"):
            out[c] = out[c].map({True: 1, False: 0, "True": 1, "False": 0, "true": 1, "false": 0}).fillna(0).astype(int)
    if "timestamp" in out and not pd.api.types.is_string_dtype(out["timestamp"]):
        out["timestamp"] = pd.to_datetime(out["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    out.to_csv(path, index=False, float_format="%.8g")


def escrever_pacote(carga: PerfilCarga, tabelas: dict[str, pd.DataFrame], pv: pd.DataFrame | None,
                    config: dict, destino: Path | None = None, eolica: pd.DataFrame | None = None) -> Path:
    """``tabelas``: fontes DESPACHÁVEIS (termica, fc, bateria). ``pv`` e ``eolica``:
    renováveis não despacháveis, descontadas da carga antes da otimização."""
    if destino is None:
        destino = Path(tempfile.mkdtemp(prefix="ems_troca_"))
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    carga.df().to_csv(destino / "carga.csv", index=False, float_format="%.8g")
    for nome, df in tabelas.items():
        _para_csv(df, destino / f"{nome}.csv")
    if pv is not None:
        pv.to_csv(destino / "pv.csv", index=False, float_format="%.8g")
    if eolica is not None:
        _para_csv(eolica, destino / "eolica.csv")
    cfg = dict(config)
    cfg["exchange_dir"] = str(destino.resolve())
    cfg["usar_pv"] = pv is not None
    cfg["usar_eolica"] = eolica is not None
    cfg["t0"] = str(carga.t0)
    cfg["carga_descricao"] = carga.descricao
    cfg["opcoes_fontes"] = {k: v for k, v in cfg.get("opcoes_fontes", {}).items() if v is not None}
    cfg["opcoes_fontes"]["fontes"] = [n for n in ("termica", "fc", "bateria") if n in tabelas]
    cfg = {k: v for k, v in cfg.items() if v is not None}
    (destino / "ems_config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return destino
