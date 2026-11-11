"""Apoio dos testes do Piso 3D-A2-R (sem testes): microrredes do CATÁLOGO com FV, eólica, bateria e PCC.

Tudo aqui é dado de TESTE, sintético e rotulado (nenhuma instalação, tarifa, medição ou previsão meteorológica real).
Os equipamentos usam itens REAIS dos catálogos do SEEDS2 (módulo ``CS6K-275P`` de ``config/pv_database.py``;
aerogerador ``Vergnet GEV MP C 275 kW`` de ``config/wind_turbine_database.py``, situação ``restricted_domain``) e o
potencial é sempre derivado pelos modelos físicos do código (nunca por um perfil substituto). O clima é gerado pelo
gerador SINTÉTICO do Piso 2B (``clima_simples``) ou declarado ponto a ponto (``clima_tabela``), sempre rotulado.
"""
from __future__ import annotations

import copy

import numpy as np

from integracao_v2 import estrategia as E
from seeds2.microgrid import config as C
from seeds2.operation import forecast_sources as FS
from seeds2.operation import service as SV
from seeds2.operation import strategy as SG

from piso3da_util import FONTE, INICIO_LOCAL, bloco_h2, demanda_sintetica

MODULO = "CS6K-275P"
TURBINA = "Vergnet GEV MP C 275 kW"
TURBINA_ANALISE = "Bergey Excel 10"                     # curve_analysis_only: NÃO habilitada para energia
EMISSAO = "2025-12-31T12:00:00+00:00"


def config_hibrida(nome: str = "Microrrede 3D-A2-R (teste)", *, fv: bool = True, eolica: bool = True,
                   energia_kWh: float = 20.0, modo: str = "conectada", ns: int = 10, np_: int = 2, sujeira: float | None = 2.0,
                   turbina: str = TURBINA, n_turbinas: int = 1, perda_generica: bool = False, arranjos: int = 1,
                   modo_arranjo: str = "modulo") -> dict:
    cfg = C.new_config(nome)
    cfg["installation"].update(description="Fixture de teste automatizado (3D-A2-R)", nature="laboratorio",
                               operation_mode=modo)
    C.add_equipment(cfg, C.new_equipment("battery", "Banco 01", tag="BAT-01", params={
        "energy_kWh": energia_kWh, "soc_min_pct": 0.0, "soc_max_pct": 100.0, "soc_limits_source": "instalacao"}))
    if fv:
        eq = C.new_equipment("pv", "Usina FV 01", tag="FV-01")
        arrs = []
        for i in range(arranjos):
            kw = {"mode": modo_arranjo}
            if modo_arranjo == "modulo":
                kw.update(reference=MODULO, n_series=ns, n_parallel=np_)
                if sujeira is not None:
                    kw["soiling_pct"] = sujeira
            else:
                kw["declared_kWp"] = 5.0
            arrs.append(C.new_array(f"Arranjo {i + 1}", **kw))
        eq["arrays"] = arrs
        C.add_equipment(cfg, eq)
    if eolica:
        C.add_equipment(cfg, C.new_equipment("wind", "Aerogerador 01", tag="WT-01", params={
            "reference": turbina, "count": n_turbinas, "apply_grid_loss": perda_generica}))
    cfg["energy_balance"]["grid_connection"] = "conectada" if modo != "isolada" else "isolada"
    cfg["commissioning"].update(completed=True, step=5, completed_at=C.utc_now())
    return cfg


def ids(doc_ou_cfg: dict) -> dict:
    """{'bateria': eq-…, 'fv': eq-…, 'arranjos': [arr-…], 'eolica': eq-…} (os que existirem)."""
    eqs = doc_ou_cfg.get("equipment")
    if eqs is None:
        eqs = [dict(v, id=k) for k, v in (doc_ou_cfg["inventory_ref"]["equipment"]).items()]
    out = {"arranjos": []}
    for e in eqs:
        k = {"battery": "bateria", "pv": "fv", "wind": "eolica"}.get(e["kind"])
        if k:
            out[k] = e["id"]
    return out


def clima_simples(doc: dict, *, horas: int = 12, passo_s: int = 3600, ghi_pico: float = 1000.0, vento: float = 8.0,
                  vento_amp: float = 0.0, t_min: float = 20.0, t_max: float = 30.0, nascer: float = 6.0, por: float = 18.0,
                  pressao: float | None = None, umidade: float | None = None, fuso: str | None = "UTC", t0: str = INICIO_LOCAL):
    vs = ["ghi_W_m2", "temperature_C", "wind_speed_m_s"] + (["pressure_hPa"] if pressao is not None else []) + (
        ["humidity_pct"] if umidade is not None else [])
    p = {"t0": t0, "step_s": passo_s, "duration_s": horas * 3600, "variables": vs, "ghi_peak_W_m2": ghi_pico,
         "sunrise_h": nascer, "sunset_h": por, "t_min_C": t_min, "t_max_C": t_max, "wind_mean_m_s": vento,
         "wind_amp_m_s": vento_amp, "wind_period_h": 24.0}
    if pressao is not None:
        p["pressure_hPa"] = pressao
    if umidade is not None:
        p["humidity_pct"] = umidade
    cand = FS.synthetic_candidate("clima_simples", p, timezone=fuso, inventory_ref=doc["inventory_ref"])
    assert cand.ok, [f.message for f in cand.analysis.findings]
    return cand


def clima_tabela(doc: dict, valores: dict, *, passo_s: int = 3600, fuso: str = "UTC", t0: str = INICIO_LOCAL):
    """Clima declarado ponto a ponto (entrada manual sintética do Piso 2B)."""
    n = len(next(iter(valores.values())))
    tab = FS.regular_table(tuple(valores), t0, passo_s, n, {k: list(v) for k, v in valores.items()})
    cand = FS.manual_candidate(tab, "climate", timezone=fuso, inventory_ref=doc["inventory_ref"], provenance="sintetico")
    assert cand.ok, [f.message for f in cand.analysis.findings]
    return cand


def declarar_renovaveis(bloco: dict, doc: dict, *, eta: float = 1.0, densidade: str = "referencia_do_catalogo",
                        c_curt: float | None = None, semantica: str = "media_intervalo", emissao: str = EMISSAO) -> dict:
    b = E.atualizar_bloco(bloco, doc)
    b["clima"] = {"semantica": semantica, "emissao_utc": emissao}
    for eid, d in b["renovaveis"].items():
        d["procedencia"] = {"tipo": "sintetico", "fonte": FONTE}
        d["custo_curtailment_R_kWh"] = c_curt
        if d["tecnologia"] == "fv":
            d["eta_conversao_barramento"] = eta
        else:
            d["hipotese_densidade"] = densidade
    if c_curt is not None and "curtailment_operacional" not in b["objetivo"]["termos"]:
        b["objetivo"]["termos"] = list(b["objetivo"]["termos"]) + ["curtailment_operacional"]
    return b


def criar_cenario_hibrido(store, *, nome: str = "Cenário híbrido V2 de teste", soc0: float = 50.0, horas: int = 12,
                          demanda_kW: float = 10.0, clima=None, clima_kw: dict | None = None, mutar=None,
                          renov_kw: dict | None = None, **kw_bloco):
    """Cenário V2 COMPLETO (demanda + clima sintéticos rotulados, estratégia com renováveis declaradas) já SALVO."""
    sc = SV.create(store, name=nome)
    doc = copy.deepcopy(sc.document)
    for eid in E.baterias_do_cenario(doc):
        doc["initialization"]["equipment"][eid]["soc0_pct"] = float(soc0)
    dem = demanda_sintetica(doc, kW=demanda_kW, horas=horas)
    cl = clima if clima is not None else clima_simples(doc, horas=horas, **(clima_kw or {}))
    if callable(cl):
        cl = cl(doc)
    doc["forecasts"]["demand"] = dem.entry
    doc["forecasts"]["climate"] = cl.entry
    doc["mission"] = SG.default_mission(INICIO_LOCAL, "UTC", horas * 60)
    doc[E.CHAVE_MOTOR] = E.MOTOR_V2
    doc[E.CHAVE_BLOCO] = declarar_renovaveis(bloco_h2(doc, K=horas, **kw_bloco), doc, **(renov_kw or {}))
    if mutar is not None:
        mutar(doc)
    return SV.save(store, doc, sc.version, new_blobs={**dem.blobs, **cl.blobs})


def potencia_fv_independente(ghi, tamb, *, ns: int = 10, np_: int = 2, sujeira: float = 2.0, eta: float = 1.0) -> np.ndarray:
    """Oráculo INDEPENDENTE do modelo NOCT (equações escritas aqui a partir da ficha do catálogo, sem chamar o código):
    T_c = T_a + (NOCT − 20)/800 · G_eff; P = η_STC · (1 + γ (T_c − 25)) · G_eff · A · N [W] × η_barramento."""
    from config.pv_database import MODULE_DB
    st = MODULE_DB[MODULO]["stc"]
    area = st["length"] * st["width"]
    eff = st["p_nom"] / (1000.0 * area)
    g = np.asarray(ghi, float) * (1.0 - sujeira / 100.0)
    tc = np.asarray(tamb, float) + (st["noct"] - 20.0) / 800.0 * g
    fator = np.clip(1.0 + st["gamma_pmax_pct"] / 100.0 * (tc - 25.0), 0.0, None)
    return eta * eff * fator * g * area * ns * np_ / 1000.0


def potencia_eolica_independente(vento) -> np.ndarray:
    """Oráculo INDEPENDENTE da curva do Vergnet com ρ de referência: interpolação linear dos pontos do catálogo,
    zero abaixo do cut-in e a partir do cut-out (ρ = ρ_ref ⇒ v_eq = v)."""
    from config.wind_turbine_database import TURBINE_DB
    e = TURBINE_DB[TURBINA]
    pts = np.asarray(e["curve"]["points"], float)
    v = np.asarray(vento, float)
    p = np.interp(v, pts[:, 0], pts[:, 1])
    p[(v < e["spec"]["cut_in_mps"]) | (v >= e["spec"]["cut_out_mps"])] = 0.0
    return np.clip(p, 0.0, e["spec"]["operating_power_limit_kw"])


__all__ = ["EMISSAO", "MODULO", "TURBINA", "TURBINA_ANALISE", "clima_simples", "clima_tabela", "config_hibrida",
           "criar_cenario_hibrido", "declarar_renovaveis", "ids", "potencia_eolica_independente", "potencia_fv_independente"]
