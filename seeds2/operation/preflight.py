"""Preflight científico (Piso 2C): o cenário só é executado se as condições declaradas puderem ser representadas
CORRETAMENTE pelo motor atual (runtime + EMS V1.6, inalterados). Regra central: nunca executar em silêncio um cenário
diferente do configurado.

Duas fases:

* **Fase A** (``prepare``) — estática, sem modelos: estrutura, revisão do inventário de referência, estados iniciais,
  disponibilidade (exclusão SOMENTE da rodada, sem tocar no inventário), classificação do adaptador, previsões (hash
  verificado) e janela temporal (UTC, cobertura, conversão para a grade). Produz o relatório legível e os parâmetros
  que chegarão ao motor.
* **Fase B** (``engine_check``) — depois dos modelos físicos e ANTES do otimizador: lê o pacote de troca com a própria
  função do EMS (``ems_integration.fontes.montar_fontes``, apenas leitura) e confere que o estado inicial efetivo do
  motor (SOC_ini, n_ini, P_prev = 0, rampas, envelopes) é equivalente ao declarado. Se a equivalência não puder ser
  demonstrada, a execução é recusada sem chamar o otimizador.

Representação dos estados iniciais no EMS V1.6 (código, não suposição):

* Bateria — ``SOC_ini`` = primeiro SOC da caracterização (= SOC declarado); ``SOC_min/SOC_max`` do inventário são
  restrição EFETIVA do despacho; SOC-alvo final = SOC inicial ± tolerância. SOC fora de [SOC_min, SOC_max] ou bancos
  agregados com SOC distintos → NÃO representável (bloqueio; o cenário continua gravável).
* PEMFC — ``n_ini = N_fc`` (todas as unidades em operação), ``P_prev = 0``. Representável: "em operação" com TODAS as
  unidades; potência inicial 0 é exatamente o contrato do motor; potência > 0 só se (1) for admissível no envelope
  caracterizado do 1º passo para as unidades em operação e (2) a rampa do 1º passo for comprovadamente inativa
  (fase B; C-02.2). Desligada, em partida ou com parte das unidades → bloqueio.
* Térmica — ``n_ini = int(Pmín > 0)``, ``P_prev = 0``. Representável: "desligada" quando Pmín = 0; "em operação"
  quando Pmín > 0 com as mesmas condições (1) e (2) da fase B. Demais → bloqueio. Sem física de partida.
* Indisponível — equipamento excluído SOMENTE da rodada (cópia do inventário com o equipamento desabilitado; o
  adaptador agrega apenas o que é fisicamente equivalente). A exclusão é listada no relatório e gravada na rodada. Seu
  estado inicial não é exigido (o motor não o usa — C-02.1), mas valores declarados continuam validados (p. ex.
  indisponível e em operação = erro de coerência).
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from seeds2.microgrid import adapter as A
from seeds2.microgrid.references import KIND_LABELS

from . import forecasts as F
from . import initialization as I
from . import mission as M
from . import scenarios as S
from . import strategy as SG

OK, INFO, WARNING, ERROR, CHECK = "ok", "info", "aviso", "erro", "verificacao"
LEVEL_LABELS = {OK: "Representável", INFO: "Informação", WARNING: "Advertência (não bloqueia)",
                ERROR: "Incompatibilidade (bloqueia)", CHECK: "Verificação no motor (antes do otimizador)"}
AREAS = ("cenario", "inventario", "inicializacao", "disponibilidade", "previsoes", "janela", "estrategia", "motor")
AREA_LABELS = {"cenario": "Cenário", "inventario": "Inventário de referência", "inicializacao": "Estados iniciais",
               "disponibilidade": "Disponibilidade", "previsoes": "Previsões", "janela": "Janela temporal",
               "estrategia": "Estratégia EMS", "motor": "Contrato do motor"}
SOC_TOL = 1e-6


@dataclass(frozen=True)
class Item:
    level: str
    area: str
    message: str
    eq_id: str | None = None

    def as_dict(self) -> dict:
        return {"level": self.level, "area": self.area, "message": self.message, "eq_id": self.eq_id}


@dataclass
class Preflight:
    items: list[Item] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)
    represented: list[dict] = field(default_factory=list)
    plan: A.SimulationPlan | None = None
    optimizer_cfg: dict | None = None
    window: M.Window | None = None
    declared: dict = field(default_factory=dict)          # estados declarados por grupo do motor
    checks: list[dict] = field(default_factory=list)      # verificações da fase B
    scenario: Any = None                                  # StoredScenario
    config_revision: int | None = None
    config_fingerprint: str | None = None
    drift: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.level == ERROR for i in self.items)

    def add(self, level: str, area: str, message: str, eq_id: str | None = None) -> None:
        self.items.append(Item(level, area, message, eq_id))

    def count(self, level: str) -> int:
        return sum(1 for i in self.items if i.level == level)

    def engine_inputs(self) -> dict:
        """Parâmetros que efetivamente chegam ao motor (exibidos antes e gravados na rodada)."""
        spec = self.plan.spec if self.plan else {}
        w = self.window
        return {"model_spec": copy.deepcopy(spec), "optimizer_cfg": copy.deepcopy(self.optimizer_cfg),
                "declared_initial_state": copy.deepcopy(self.declared),
                "engine_initial_state_rule": {"battery": "SOC_ini = SOC declarado; SOC-alvo final = SOC_ini ± tolerância",
                                              "fc": "n_ini = N_fc (todas em operação); P_prev = 0",
                                              "thermal": "n_ini = int(Pmín > 0); P_prev = 0"},
                "grid": None if w is None or w.grid_utc is None else {
                    "step_s": SG.STEP_S, "n_steps": int(len(w.grid_utc)), "duration_min": int(w.duration_min),
                    "timezone": w.timezone, "start_wall": str(w.start_wall), "start_utc": str(w.start_utc),
                    "end_utc": str(w.grid_utc[-1])},
                "resampling": copy.deepcopy(w.resampling) if w else {}}

    def report(self) -> dict:
        return {"ok": self.ok, "items": [i.as_dict() for i in self.items], "excluded": copy.deepcopy(self.excluded),
                "represented": copy.deepcopy(self.represented), "checks": copy.deepcopy(self.checks),
                "drift": list(self.drift), "counts": {lv: self.count(lv) for lv in (OK, INFO, WARNING, ERROR, CHECK)}}


def _states(doc: dict) -> dict:
    return (doc.get("initialization") or {}).get("equipment") or {}


def _refs(doc: dict) -> dict:
    return (doc.get("inventory_ref") or {}).get("equipment") or {}


# ====================================================================== fase A
def prepare(store, stored) -> Preflight:
    """Fase A sobre uma versão GRAVADA (``StoredScenario``) do cenário."""
    pf = Preflight(scenario=stored)
    doc = stored.document
    # ---- estrutura e integridade do documento
    errs = S.structural_errors(doc)
    for slot, entry in (doc.get("forecasts") or {}).items() if not errs else ():
        errs += F.entry_errors(slot, entry)
    for e in errs:
        pf.add(ERROR, "cenario", e)
    if errs:
        return pf
    mg = doc.get("microgrid") or {}
    if store.incarnation is not None and mg.get("incarnation") not in (None, store.incarnation):
        pf.add(ERROR, "cenario", "O cenário foi definido para outra incarnação desta microrrede.")
        return pf
    # ---- Piso 3D-A: um cenário que seleciona o motor V2 NUNCA é executado pelo motor V1.6 (sem recaída silenciosa)
    if S.engine(doc) != "legacy_v16":
        pf.add(ERROR, "estrategia", f"Este cenário seleciona o motor '{S.engine(doc)}' (EMS V2 experimental MILP–MPC): a "
               "execução pelo motor V1.6 é recusada. Use a execução do motor V2 (etapa 04) ou selecione o motor V1.6 e "
               "salve uma nova versão do cenário.")
        return pf
    # ---- revisão do inventário de referência (imutável)
    ref = doc["inventory_ref"]
    try:
        rev = store.get_revision(int(ref["config_revision"]))
    except Exception as exc:                                     # noqa: BLE001 — mensagem apresentável
        pf.add(ERROR, "inventario", f"Revisão {ref['config_revision']} do inventário indisponível: {exc}")
        return pf
    if rev.fingerprint != ref["config_fingerprint"]:
        pf.add(ERROR, "inventario", "A revisão do inventário referenciada não corresponde à impressão digital do cenário.")
        return pf
    pf.config_revision, pf.config_fingerprint = rev.revision, rev.fingerprint
    saved = store.load()
    if saved is not None:
        d = S.drift(doc, saved.config, saved.revision)
        if d.stale:
            pf.drift = d.describe(doc, saved.config)
            pf.add(WARNING, "inventario", f"O inventário atual (revisão {saved.revision}) mudou desde a revisão "
                   f"{rev.revision} de referência deste cenário ({'; '.join(pf.drift[:4])}). A execução usa a revisão "
                   f"{rev.revision} (a do cenário); atualize a referência no Centro de Operação para usar o inventário atual.")
        else:
            pf.add(OK, "inventario", f"Inventário de referência: revisão {rev.revision} "
                   + ("(atual)." if d.same_revision else f"(equivalente à revisão atual {saved.revision})."))
    # ---- estados iniciais (regras do Piso 2A)
    # C-02.1: equipamento DECLARADO indisponível (e habilitado na revisão de referência) é excluído desta rodada; o
    # motor não usará seu estado inicial, que portanto não é exigido ("não definido" vira informação). Erros de
    # coerência de valores efetivamente declarados (p. ex. indisponível e em operação) continuam bloqueando.
    enabled_ref = {e["id"] for e in rev.config.get("equipment", []) if e.get("enabled", True)}
    unavailable_ids = {eq_id for eq_id, st in _states(doc).items()
                       if eq_id in enabled_ref and (st or {}).get("availability") == "indisponivel"}
    not_required: set[str] = set()
    findings = S.findings(doc)
    for f in findings:
        name = (_refs(doc).get(f.eq_id) or {}).get("name") if f.eq_id else None
        prefix = f"{name}: " if name else ""
        if f.level == I.ERROR:
            pf.add(ERROR, "inicializacao", prefix + f.message, f.eq_id)
        elif f.level == I.INCOMPLETE and f.eq_id in unavailable_ids:
            not_required.add(f.eq_id)
        elif f.level == I.INCOMPLETE:
            pf.add(ERROR, "inicializacao", prefix + "não definido — " + f.message, f.eq_id)
        elif f.level == I.WARNING:
            pf.add(WARNING, "inicializacao", prefix + f.message, f.eq_id)
        # PENDING: reinterpretado abaixo pelas regras de compatibilidade com o motor (nada é ignorado em silêncio).
    for eq_id in sorted(not_required, key=lambda e: (_refs(doc).get(e) or {}).get("position", 0)):
        r = _refs(doc).get(eq_id) or {}
        pf.add(INFO, "inicializacao", f"{r.get('name', eq_id)}: estado inicial não definido e NÃO requerido — o "
               "equipamento está declarado indisponível e é excluído do despacho desta rodada (o motor não o utiliza).",
               eq_id)
    # ---- estratégia
    strat = doc.get("ems_strategy")
    if strat is None:
        pf.add(ERROR, "estrategia", "Estratégia EMS não definida (etapa 03): escolha e salve os parâmetros do otimizador.")
    else:
        for e in SG.strategy_errors(strat):
            pf.add(ERROR, "estrategia", e)
        if not SG.strategy_errors(strat):
            pf.optimizer_cfg = SG.optimizer_config(strat)
            pf.add(OK, "estrategia", f"{SG.OBJECTIVE_LABEL} · {SG.ALGORITHMS[strat['algorithm']]} · N = {strat['N']} · "
                   f"semente {strat['seed']} · tolerância do SOC-alvo ±{strat['soc_alvo_tol']:g}.")
    # ---- configuração efetiva DA RODADA: disponibilidade e SOC do cenário (inventário permanente intocado)
    eff = copy.deepcopy(rev.config)
    states, refs = _states(doc), _refs(doc)
    by_id = {e["id"]: e for e in eff.get("equipment", [])}
    unavailable = set()
    for eq_id, st in states.items():
        if eq_id in unavailable_ids and eq_id in by_id:
            unavailable.add(eq_id)
            by_id[eq_id]["enabled"] = False
            r = refs.get(eq_id) or {}
            pf.excluded.append({"id": eq_id, "name": r.get("name", eq_id), "kind": r.get("kind"),
                                "reason": "Indisponível no cenário: excluído somente desta rodada (inventário inalterado)."})
            pf.add(INFO, "disponibilidade", f"{r.get('name', eq_id)} ({KIND_LABELS.get(r.get('kind'), r.get('kind'))}) "
                   "declarado indisponível: excluído somente desta rodada; o inventário permanente não é alterado.", eq_id)
    eff.setdefault("run_conditions", {})["battery_soc0_pct"] = {
        eq_id: float(st["soc0_pct"]) for eq_id, st in states.items()
        if (refs.get(eq_id) or {}).get("kind") == "battery" and eq_id not in unavailable
        and isinstance((st or {}).get("soc0_pct"), (int, float))}
    plan = A.build_plan(eff, revision=rev.revision, fingerprint=rev.fingerprint, external_inputs=True)
    pf.plan = plan
    _classify(pf, plan, doc, unavailable)
    for b in plan.blockers:
        pf.add(ERROR, "motor", b)
    for w in plan.warnings:
        pf.add(WARNING, "motor", w)
    if pf.optimizer_cfg and pf.optimizer_cfg.get("validar") and not plan.spec["fc"]["active"]:
        pf.add(WARNING, "estrategia", "Validação dinâmica do H₂ selecionada, mas não há PEMFC na rodada: sem efeito.")
    # ---- previsões e janela
    _forecasts_and_window(pf, store, doc, plan)
    return pf


def _classify(pf: Preflight, plan: A.SimulationPlan, doc: dict, unavailable: set[str]) -> None:
    states, refs = _states(doc), _refs(doc)
    for m in plan.mappings:
        eq_id = m.parent or m.id
        if m.status == A.REPRESENTED:
            pf.represented.append(m.as_dict())
            continue
        if m.status == A.DISABLED:
            if eq_id not in unavailable:
                pf.add(INFO, "inventario", f"{m.name}: desabilitado no inventário (não faz parte da operação).", eq_id)
            continue
        # incompleto / não representável e DISPONÍVEL no cenário: nunca omitido em silêncio
        if m.kind == "battery":
            ref, soc = refs.get(eq_id) or {}, (states.get(eq_id) or {}).get("soc0_pct")
            if soc is None:
                continue                              # já relatado como "não definido" (estados iniciais)
            lo, hi = ref.get("soc_min_pct"), ref.get("soc_max_pct")
            if soc is not None and lo is not None and hi is not None and not lo - 1e-9 <= float(soc) <= hi + 1e-9:
                pf.add(ERROR, "inicializacao", f"{m.name}: SOC inicial {float(soc):g} % fora dos limites [{lo:g}, {hi:g}] % "
                       "que o EMS V1.6 usa como restrição EFETIVA do despacho. O motor atual não pode representar esse "
                       "estado: execução bloqueada até existir suporte científico (piso do otimizador). O cenário continua "
                       "válido e gravável.", eq_id)
                continue
            if "distintas" in m.reason:
                pf.add(ERROR, "inicializacao", f"{m.name}: bancos com SOC iniciais ou configurações diferentes. O EMS V1.6 "
                       "agrega bancos idênticos com UM único SOC inicial: estados distintos não são representáveis "
                       "(execução bloqueada; valores preservados no cenário).", eq_id)
                continue
        pf.add(ERROR, "motor", f"{m.name} ({KIND_LABELS.get(m.kind, m.kind)}): {A.STATUS_LABELS[m.status].lower()} — "
               f"{m.reason} Um equipamento disponível no cenário não pode ser omitido da rodada: ajuste o inventário ou "
               "declare-o indisponível no cenário.", eq_id)
    spec = plan.spec
    # ---- bateria
    if spec["battery"]["active"]:
        ids = [m["id"] for m in pf.represented if m["kind"] == "battery"]
        soc = spec["battery"]["soc0"] * 100.0
        pf.declared["battery"] = {"equipment": ids, "soc0_pct": soc, "soc_min_pct": spec["battery"]["soc_min"] * 100,
                                  "soc_max_pct": spec["battery"]["soc_max"] * 100}
        pf.add(OK, "inicializacao", f"Bateria ({len(ids)} banco(s) agregado(s)): SOC inicial {soc:g} % aplicado como SOC_ini "
               f"do EMS; limites efetivos {spec['battery']['soc_min'] * 100:g}–{spec['battery']['soc_max'] * 100:g} %; "
               "SOC-alvo final = SOC inicial ± tolerância (restrição existente do EMS V1.6).")
        pf.checks.append({"kind": "battery_soc", "soc0": spec["battery"]["soc0"]})
    # ---- PEMFC
    if spec["fc"]["active"]:
        ids = [m["id"] for m in pf.represented if m["kind"] == "pemfc"]
        bad, p0, units = [], 0.0, 0
        for eq_id in ids:
            st, ref = states.get(eq_id) or {}, refs.get(eq_id) or {}
            q = ref.get("quantity")
            units += int(st.get("units_on") or 0)
            p0 += float(st.get("power_kW") or 0.0)
            if st.get("state") != "em_operacao":
                bad.append(f"{ref.get('name', eq_id)} declarada '{I.DISPATCH_STATES.get(st.get('state'), '?').lower()}'")
            elif q is not None and st.get("units_on") != q:
                bad.append(f"{ref.get('name', eq_id)} com {st.get('units_on')} de {q} unidade(s) em operação")
        n_fc = int(spec["fc"]["N_fc"])
        pf.declared["fc"] = {"equipment": ids, "units_on": units, "N_fc": n_fc, "power_kW": p0}
        if bad:
            pf.add(ERROR, "inicializacao", "PEMFC: " + "; ".join(bad) + f". O EMS V1.6 inicia com TODAS as {n_fc} unidades "
                   "em operação (n_ini = N_fc) e sem potência anterior (P_prev = 0); estados desligado, em partida ou com "
                   "parte das unidades não são representáveis (não há física de partida). Execução bloqueada; o estado "
                   "continua preservado no cenário.")
        elif p0 <= 1e-9:
            pf.add(OK, "inicializacao", f"PEMFC: {n_fc} unidade(s) em operação com potência inicial 0 — exatamente o estado "
                   "inicial do EMS V1.6 (n_ini = N_fc, P_prev = 0).")
        elif spec["fc"]["base"] != "entregue":
            pf.add(ERROR, "inicializacao", "PEMFC com potência inicial > 0 e base de potência 'stack': a equivalência com o "
                   "motor não pode ser demonstrada (o estado declarado é potência líquida entregue).")
        else:
            pf.add(CHECK, "inicializacao", f"PEMFC: {n_fc} unidade(s) em operação com {p0:g} kW. O EMS V1.6 começa com "
                   "P_prev = 0 (sem restrição de rampa no 1º passo); antes do otimizador será verificado, com o contrato "
                   "caracterizado, (1) que a potência declarada é admissível no envelope do 1º passo para as unidades em "
                   "operação e (2) que a rampa do 1º passo não seria ativa a partir dela. Caso contrário a execução é "
                   "recusada.")
            pf.checks.append({"kind": "ramp", "source": "fc", "p0_kW": p0})
    # ---- térmica
    if spec["thermal"]["active"]:
        ids = [m["id"] for m in pf.represented if m["kind"] == "thermal"]
        eq_id = ids[0] if ids else None
        st = states.get(eq_id) or {}
        pmin = float(spec["thermal"]["pmin_kW"])
        n_ini = 1 if pmin > 0 else 0
        p0 = float(st.get("power_kW") or 0.0)
        pf.declared["thermal"] = {"equipment": ids, "state": st.get("state"), "power_kW": p0, "expected_n_ini": n_ini}
        state = st.get("state")
        if state == "desligada" and n_ini == 0:
            pf.add(OK, "inicializacao", "Térmica desligada com Pmín = 0 — exatamente o estado inicial do EMS V1.6 "
                   "(n_ini = 0, P_prev = 0; custo de partida cobrado se ligar).")
            pf.checks.append({"kind": "n_ini", "source": "termica", "expected": 0})
        elif state == "em_operacao" and n_ini == 1:
            pf.add(CHECK, "inicializacao", f"Térmica em operação com {p0:g} kW (Pmín = {pmin:g} kW → o EMS V1.6 inicia com "
                   "n_ini = 1 e P_prev = 0). Antes do otimizador será verificado que a potência declarada é admissível no "
                   "envelope caracterizado do 1º passo e que a rampa do 1º passo não seria ativa a partir dela; caso "
                   "contrário a execução é recusada.")
            pf.checks += [{"kind": "n_ini", "source": "termica", "expected": 1},
                          {"kind": "ramp", "source": "termica", "p0_kW": p0}]
        else:
            why = ("o EMS V1.6 deriva n_ini = 1 (ligada) de Pmín > 0" if n_ini == 1 else
                   "o EMS V1.6 deriva n_ini = 0 (desligada) de Pmín = 0")
            pf.add(ERROR, "inicializacao", f"Térmica declarada '{I.THERMAL_STATES.get(state, '?').lower()}': {why}, sem "
                   "física de partida. O estado declarado não é representável; execução bloqueada.", eq_id)
    for k, label in (("pv", "Solar FV"), ("wind", "Eólica")):
        ids = [m for m in pf.represented if m["kind"] == k]
        if ids:
            pf.add(OK, "disponibilidade", f"{label}: {len(ids)} unidade(s)/arranjo(s) disponível(is) representado(s) "
                   "(fonte não despachável: produção abatida da demanda).")


def _forecasts_and_window(pf: Preflight, store, doc: dict, plan: A.SimulationPlan) -> None:
    fc = doc.get("forecasts") or {}
    spec = plan.spec
    needs: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {"demand": (("demand_kW",), ())}
    solar, wind = spec["solar"]["active"], spec["wind"]["active"]
    if solar or wind:
        req: list[str] = []
        if solar:
            req += ["ghi_W_m2", "temperature_C"]
        if wind:
            req.append("wind_speed_m_s")
        present = list((fc.get("climate") or {}).get("variables") or [])
        opt = [v for v in ("wind_direction_deg", "temperature_C", "pressure_hPa", "humidity_pct")
               if wind and v in present and v not in req]
        missing = [v for v in req if fc.get("climate") and v not in present]
        for v in missing:
            pf.add(ERROR, "previsoes", f"{F.VARIABLES[v].label} ausente na previsão climática (obrigatória para "
                   f"{'FV' if v != 'wind_speed_m_s' else 'eólica'} nesta rodada).")
        needs["climate"] = (tuple(v for v in req if v in present or not fc.get("climate")), tuple(opt))
        if wind:
            absent = [F.VARIABLES[v].short for v in ("wind_direction_deg", "pressure_hPa", "humidity_pct") if v not in present]
            if absent:
                pf.add(INFO, "previsoes", "Eólica: " + ", ".join(absent) + " ausente(s) no perfil — o modelo eólico V1.6 "
                       "usa a densidade do ar de referência para o que não é informado (comportamento existente).")
        unused = [F.VARIABLES[v].short for v in present if v not in req and v not in opt]
        if unused:
            pf.add(INFO, "previsoes", "Variáveis do clima não usadas pelos modelos desta rodada: " + ", ".join(unused) + ".")
    elif fc.get("climate"):
        pf.add(INFO, "previsoes", "Nenhuma fonte FV/eólica na rodada: a previsão climática não é usada.")
    series: dict[str, M.Series] = {}
    for slot in needs:
        entry = fc.get(slot)
        if not entry:
            continue
        try:
            series[slot] = M.load_series(slot, entry, store.get_blob)
        except F.ForecastDataError as exc:
            pf.add(ERROR, "previsoes", f"{'Demanda' if slot == 'demand' else 'Clima'}: {exc}")
            continue
        pf.add(OK, "previsoes", f"{'Demanda' if slot == 'demand' else 'Clima'}: {entry.get('label') or entry.get('source_type')} "
               f"· SHA-256 {entry['data'][:12]}… verificado · {M.tz_label(entry.get('timezone'))}.")
    if any(i.level == ERROR and i.area == "previsoes" for i in pf.items):
        return
    w = M.build_window(doc.get("mission"), series, needs)
    pf.window = w
    for n in w.notes:
        pf.add({M.ERROR: ERROR, M.WARNING: WARNING, M.INFO: INFO}[n.level], "janela", n.message)
    if w.ok:
        pf.add(OK, "janela", f"Missão de {w.duration_min} min ({len(w.grid_utc)} instantes, passo de 60 s do motor) a partir "
               f"de {w.start_wall:%d/%m/%Y %H:%M} ({M.tz_label(w.timezone)}); UTC {w.start_utc:%d/%m/%Y %H:%M}.")
        for var, r in w.resampling.items():
            pf.add(INFO, "janela", f"{F.VARIABLES[var].label}: {r['method']}.")


# ====================================================================== fase B
def _engine_sources(package_dir: Path):
    """Lê o pacote de troca exatamente como ``executor.executar_pacote`` (mesmos dicionários ``arch``/``econ`` e a
    própria ``montar_fontes``). Somente leitura: devolve as fontes que o otimizador receberá."""
    from ems_integration.fontes import Log, montar_fontes
    from ems_integration.ponte import ARCH_PADRAO, ECON_PADRAO

    pasta = Path(package_dir)
    C = json.loads((pasta / "ems_config.json").read_text(encoding="utf-8"))
    t_min = pd.read_csv(pasta / "carga.csv").t_min.to_numpy(float)
    arch = dict(ARCH_PADRAO)
    arch.update(C.get("eta_conv", {}))
    arch["N_fc"] = int(C.get("N_fc", 1))
    if C.get("pv_P_rated_kWp") is not None:
        arch["pv_P_rated_kWp"] = float(C["pv_P_rated_kWp"])
    econ = dict(ECON_PADRAO)
    econ.update(C.get("econ", {}))
    return montar_fontes(pasta, t_min, arch, econ, C.get("opcoes_fontes", {}), Log()), float(C.get("Ts_s", 60))


def initial_power_admissible(f, p0: float) -> tuple[bool, str]:
    """C-02.2: a potência inicial declarada ``p0`` > 0 é uma condição ADMISSÍVEL do contrato caracterizado, no estado
    discreto que o motor realmente representa no instante inicial (``n_ini`` unidades em operação)? Exige
    ``n_ini ≥ 1`` e ``n_ini·P_min_unid_kW[0] ≤ p0 ≤ n_ini·P_max_unid_kW[0]`` (envelope do 1º passo). Independe da
    rampa: uma rampa ilimitada não elimina os limites físicos de potência."""
    n = int(f.n_ini)
    pmin, pmax = float(f.P_min_unid_kW[0]), float(f.P_max_unid_kW[0])
    if n < 1:
        return False, f"o motor representa {n} unidade(s) em operação no instante inicial; potência {p0:g} kW > 0 é inadmissível"
    lo, hi = n * pmin, n * pmax
    ok = lo - 1e-9 <= p0 <= hi + 1e-9
    return ok, (f"declarada {p0:g} kW; intervalo efetivo [{lo:.4g}, {hi:.4g}] kW = {n} unidade(s) em operação × envelope "
                f"caracterizado do 1º passo [{pmin:.4g}, {pmax:.4g}] kW por unidade")


def ramp_inactive(f, p0: float, ts_s: float) -> tuple[bool, str]:
    """A restrição de rampa do 1º passo que o EMS aplicaria com ``P_prev = p0`` (``despacho.restricoes_lineares``) é
    inativa em TODA a caixa viável de cada configuração candidata? Então o problema com ``P_prev = 0`` (contrato do
    motor) é o mesmo problema que o estado declarado definiria. Trata SOMENTE da rampa: a admissibilidade de ``p0``
    no envelope é verificada antes, por ``initial_power_admissible`` (C-02.2)."""
    from ems_integration.despacho import _n_prev_de

    if not np.isfinite(f.ramp_kW_min):
        return True, "rampa ilimitada no motor"
    lo = max(0, int(f.n_ini - f.dn_max)) if np.isfinite(f.dn_max) else 0
    hi = min(int(f.n_unid), int(f.n_ini + f.dn_max)) if np.isfinite(f.dn_max) else int(f.n_unid)
    applies = _n_prev_de(f, p0)
    parts = []
    for n1 in range(lo, hi + 1):
        if n1 == 0 or n1 != applies:
            continue                                  # o EMS não aplica a rampa (configuração muda ou desligada)
        dmax = n1 * f.ramp_kW_min * ts_s / 60.0
        need = max(n1 * float(f.P_max_unid_kW[0]) - p0, p0 - n1 * float(f.P_min_unid_kW[0]))
        parts.append(f"n = {n1}: rampa {dmax:.4g} kW/passo vs. desvio máximo {need:.4g} kW")
        if need > dmax + 1e-9:
            return False, "; ".join(parts)
    return True, "; ".join(parts) or "a rampa não se aplica a nenhuma configuração candidata do 1º passo"


def engine_check(pf: Preflight, package_dir: Path) -> tuple[bool, list[dict], dict]:
    """Fase B: confere o estado inicial efetivo do motor contra o declarado. Devolve (ok, constatações, estado efetivo)."""
    fontes, ts_s = _engine_sources(package_dir)
    by = {f.nome: f for f in fontes}
    eff = {f.nome: {"n_unid": int(f.n_unid), "n_ini": int(f.n_ini), "P_prev_kW": 0.0,
                    "P_max_unid_kW_t0": float(f.P_max_unid_kW[0]), "P_min_unid_kW_t0": float(f.P_min_unid_kW[0]),
                    "ramp_kW_min": float(f.ramp_kW_min) if np.isfinite(f.ramp_kW_min) else None,
                    **({"SOC_ini": float(f.SOC_ini), "SOC_min": float(f.SOC_min), "SOC_max": float(f.SOC_max),
                        "E_kWh": float(f.E_kWh)} if f.armazena else {})} for f in fontes}
    out: list[dict] = []
    ok = True

    def res(good: bool, msg: str) -> None:
        nonlocal ok
        ok = ok and good
        out.append({"level": OK if good else ERROR, "area": "motor", "message": msg})

    for c in pf.checks:
        if c["kind"] == "battery_soc":
            f = by.get("bateria")
            if f is None:
                res(False, "Bateria ausente do contrato do motor.")
            else:
                good = abs(float(f.SOC_ini) - float(c["soc0"])) <= SOC_TOL
                res(good, f"Bateria: SOC_ini efetivo do motor {f.SOC_ini * 100:.6g} % "
                          f"{'=' if good else '≠'} SOC declarado {c['soc0'] * 100:.6g} %.")
        elif c["kind"] == "n_ini":
            f = by.get(c["source"])
            good = f is not None and int(f.n_ini) == int(c["expected"])
            res(good, f"Térmica: n_ini efetivo do motor = {getattr(f, 'n_ini', '?')} (esperado {c['expected']} pelo estado "
                      "declarado).")
        elif c["kind"] == "ramp":
            f = by.get(c["source"])
            if f is None:
                res(False, f"Fonte {c['source']} ausente do contrato do motor.")
                continue
            label = {"fc": "PEMFC", "termica": "Térmica"}[c["source"]]
            p0 = float(c["p0_kW"])
            # 1) limites físicos do contrato caracterizado (sempre; mesmo com rampa ilimitada)
            adm, adetail = initial_power_admissible(f, p0)
            res(adm, f"{label}: potência inicial " + ("admissível no envelope efetivo do motor " if adm else
                "FORA do envelope efetivo do motor — estado declarado não representável; execução recusada antes do "
                "otimizador ") + f"({adetail}).")
            if not adm:
                continue
            # 2) só então, a rampa do 1º passo
            good, detail = ramp_inactive(f, p0, ts_s)
            res(good, f"{label}: potência inicial declarada {p0:g} kW — " + (
                "restrição de rampa do 1º passo comprovadamente inativa; P_prev = 0 do motor é equivalente "
                if good else "a rampa do 1º passo PODERIA restringir o despacho; o motor (P_prev = 0) não representa o "
                "estado declarado — execução recusada antes do otimizador ") + f"({detail}).")
    if "fc" in by and pf.declared.get("fc"):
        good = int(by["fc"].n_ini) == int(pf.declared["fc"]["N_fc"])
        res(good, f"PEMFC: n_ini efetivo do motor = {by['fc'].n_ini} (todas as {pf.declared['fc']['N_fc']} unidades).")
    return ok, out, eff


__all__ = ["AREAS", "AREA_LABELS", "CHECK", "ERROR", "INFO", "Item", "LEVEL_LABELS", "OK", "Preflight", "WARNING",
           "engine_check", "initial_power_admissible", "prepare", "ramp_inactive"]
