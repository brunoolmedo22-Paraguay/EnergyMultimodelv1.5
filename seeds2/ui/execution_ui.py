"""Centro de Operação · Estratégia EMS (etapa 03) e Execução (etapa 04) — Piso 2C.

* ``tab = "estrategia"`` — função objetivo (única, identificada), algoritmo, horizonte N, semente, tolerâncias,
  parâmetros econômicos e validação: SOMENTE opções existentes do motor V1.6. Gravada no cenário (SALVAR CENÁRIO).
* ``tab = "execucao"`` — janela da missão (gravada no cenário), relatório de compatibilidade (preflight) da versão
  SALVA, EXECUTAR (rodada em thread própria; progresso real do motor lido do banco), histórico de rodadas.
* ``tab = "rodada"`` — rodada imutável lida do armazenamento (``?run=<uid>``): estado, indicadores, curvas,
  procedência. Abrir uma rodada NUNCA chama o otimizador.

Distinção central na interface: **Cenário** (editável, versionado) × **Rodada** (execução imutável de UMA versão).
Estado de sessão: ``op_ex_*`` (cache do preflight, pedido de execução), ``op_run_uid`` (rodada aberta),
widgets ``opw_sg_*`` / ``opw_ex_*`` — limpos ao trocar de cenário/microrrede.
"""
from __future__ import annotations

import datetime as dt
from html import escape

import pandas as pd
import streamlit as st

from seeds2.microgrid.references import KIND_LABELS
from seeds2.microgrid.store import RunBusyError, RunNotFound, StoreError
from seeds2.operation import contracts
from seeds2.operation import forecasts as F
from seeds2.operation import initialization as I
from seeds2.operation import mission as M
from seeds2.operation import preflight as P
from seeds2.operation import runner
from seeds2.operation import scenarios as S
from seeds2.operation import strategy as SG

from . import forms, run_charts as RC, session, shell

TAB_STRATEGY, TAB_EXEC, TAB_RUN = "estrategia", "execucao", "rodada"
STATE_PREFIXES = ("op_ex_", "opw_sg_", "opw_ex_", "op_run_uid")
STATE_TONE = {"em_execucao": "info", "concluida": "ok", "falhou": "bad", "interrompida": "warn"}
LEVEL_TONE = {P.ERROR: "bad", P.WARNING: "warn", P.CHECK: "info", P.OK: "ok", P.INFO: "off"}
LEVEL_GLYPH = {P.ERROR: "✕", P.WARNING: "!", P.CHECK: "◷", P.OK: "✓", P.INFO: "i"}
PHASES = {"preparando": "Preparando a rodada", "fila": "Aguardando o motor (outra execução neste servidor)",
          "modelos": "Calculando os modelos físicos e o pacote de troca (o motor não informa progresso nesta fase)",
          "verificacao": "Verificando o contrato efetivo do motor (estado inicial)", "otimizador": "Despacho EMS",
          "gravando": "Gravando séries e resultados", "concluida": "Concluída"}
EX_CSS = """
<style>
.op-f i.ok { color: #1f7a4c; background: rgba(46,139,87,.14); }
.ex-dist { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; margin: .2rem 0 .8rem 0; }
.ex-dist > div { border: 1px solid rgba(128,128,128,.25); border-radius: .7rem; padding: .6rem .8rem; }
.ex-dist b { font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; }
@media (max-width: 760px) { .ex-dist { grid-template-columns: 1fr; } }
</style>
"""


def _ss():
    return st.session_state


def _oc():
    from . import operation_center as OC

    return OC


def clear_state() -> None:
    for k in [k for k in list(_ss().keys()) if str(k).startswith(STATE_PREFIXES)]:
        _ss().pop(k, None)


def _pill(text: str, tone: str) -> str:
    return f'<span class="op-pill {escape(tone)}">{escape(text)}</span>'


def _items_html(items: list[dict]) -> str:
    order = {P.ERROR: 0, P.CHECK: 1, P.WARNING: 2, P.OK: 3, P.INFO: 4}
    rows = []
    for it in sorted(items, key=lambda i: order.get(i["level"], 9)):
        lv = it["level"]
        rows.append(f'<div class="op-f"><i class="{LEVEL_TONE.get(lv, "off")}">{LEVEL_GLYPH.get(lv, "·")}</i><span>'
                    f'<b>{escape(P.AREA_LABELS.get(it.get("area"), it.get("area") or ""))}:</b> {escape(it["message"])}</span></div>')
    return "".join(rows)


def open_run(run_uid: str) -> None:
    _ss()["op_run_uid"] = run_uid
    shell.go("operacao", TAB_RUN)                     # ?run=<uid> na URL (sobrevive à recarga)


def _back(key: str) -> None:
    if st.button("← Centro de Operação", key=key):
        shell.go("operacao")
        st.rerun()


# ======================================================================= preflight (cache por versão salva)
def preflight(store, cur) -> P.Preflight:
    """Preflight da versão SALVA ``cur`` (nunca da edição pendente). Recalculado quando a versão do cenário ou a revisão
    do inventário mudam."""
    saved = session.saved()
    key = (cur.scenario_uid, cur.version, cur.fingerprint, saved.revision if saved else None)
    c = _ss().get("op_ex_pf")
    if c is None or c[0] != key:
        pf = P.prepare(store, cur)
        _ss()["op_ex_pf"] = (key, pf)
        return pf
    return c[1]


def stage_state(store, cur) -> tuple[str, str, str]:
    """Estado da etapa 04 no painel (preflight da versão salva)."""
    try:
        pf = preflight(store, cur)
    except StoreError as exc:
        return "bad", "Indisponível", str(exc)[:80]
    n = pf.count(P.ERROR)
    runs = [r for r in store.list_runs(cur.scenario_uid, limit=50)]
    done = sum(1 for r in runs if r.state == "concluida")
    hist = f" · {done} rodada(s) concluída(s)" if done else ""
    if n:
        return "bad", "Não executável", f"{n} incompatibilidade(s) na versão salva v{cur.version}{hist}"
    return "ok", "Pronto para executar", f"versão salva v{cur.version}{hist}"


# ======================================================================= etapa 03 — Estratégia EMS
def render_strategy(store, cur) -> None:
    oc = _oc()
    _back("op_back_sg")
    if cur is None or oc.work() is None:
        st.info("Nenhum cenário selecionado. Crie ou selecione um cenário no Centro de Operação.")
        return
    doc = oc.work()
    tok = int(_ss().get("op_token") or 0)
    tone, label, detail = S.strategy_status(doc)
    shell.hero("Estratégia EMS", doc["name"],
               "Parâmetros do otimizador para as rodadas deste cenário — somente opções existentes e verificadas do motor "
               "V1.6. A configuração é gravada na versão do cenário e copiada para cada rodada.",
               [("Cenário", f"v{cur.version}" + (" · alterações não salvas" if oc.is_dirty() else "")),
                ("Estratégia", label + (f" · {detail}" if detail else "")),
                ("Inventário de referência", f"rev. {doc['inventory_ref']['config_revision']}")])
    with st.container(border=True):
        st.html(f'<div class="op-k">Função objetivo</div><div class="op-t">{escape(SG.OBJECTIVE_LABEL)}</div>'
                '<p class="op-d">Única função objetivo implementada no motor V1.6 (sem seletor multiobjetivo). Termos '
                'minimizados a cada passo do horizonte móvel:</p><ul class="op-d" style="margin:.1rem 0 .2rem 1.1rem;padding:0">'
                + "".join(f"<li>{escape(t)}</li>" for t in SG.OBJECTIVE_TERMS) + "</ul>")
    s = doc.get("ems_strategy")
    if s is None:
        shell.callout("<b>Estratégia ainda não definida.</b> Sem ela o cenário não é executável. Comece pelos valores "
                      "padrão do console V1.6 e ajuste o que for necessário.", "warn")
        if st.button("DEFINIR COM OS VALORES PADRÃO DO MOTOR V1.6", key="op_sg_default", type="primary"):
            doc["ems_strategy"] = SG.default_strategy()
            st.rerun()
        oc._save_bar(store, cur, I.summarize(S.findings(doc)))
        return
    k = f"opw_sg_{tok}"
    c1, c2 = st.columns(2, gap="large")
    with c1, st.container(border=True):
        st.html('<div class="op-k">Algoritmo de resolução</div>')
        algs = list(SG.ALGORITHMS)
        s["algorithm"] = st.radio("Algoritmo", algs, index=algs.index(s["algorithm"]) if s["algorithm"] in algs else 0,
                                  format_func=lambda a: SG.ALGORITHMS[a], key=f"{k}_alg",
                                  help="Metaheurística que gera o ponto inicial; o refino SLSQP é sempre aplicado.")
        s["meta_penalizada"] = st.toggle("Metaheurística com penalidade de restrições", value=bool(s["meta_penalizada"]),
                                         key=f"{k}_mp")
        st.html('<div class="op-k" style="margin-top:.6rem">Validação</div>')
        s["validar_h2"] = st.toggle("Validar o H₂ no modelo dinâmico PEMFC após o despacho", value=bool(s["validar_h2"]),
                                    key=f"{k}_val", help="executor.validar_fc_dinamico — única validação implementada.")
    with c2, st.container(border=True):
        st.html('<div class="op-k">Horizonte, semente e tolerância</div>')
        lo, hi = SG.RANGES["N"]
        s["N"] = int(st.number_input(SG.LABELS["N"], lo, hi, int(s["N"]), 1, key=f"{k}_N",
                                     help="Receding horizon: no fim da missão o horizonte encurta até 1 passo."))
        lo, hi = SG.RANGES["seed"]
        s["seed"] = int(st.number_input(SG.LABELS["seed"], lo, hi, int(s["seed"]), 1, key=f"{k}_seed"))
        lo, hi = SG.RANGES["soc_alvo_tol"]
        s["soc_alvo_tol"] = float(st.number_input(SG.LABELS["soc_alvo_tol"], lo, hi, float(s["soc_alvo_tol"]), 0.01,
                                                  key=f"{k}_tol", format="%.2f"))
    with st.container(border=True):
        st.html('<div class="op-k">Parâmetros econômicos e conversores</div>')
        cols = st.columns(4)
        for i, f in enumerate(("preco_H2_rs_kg", "c_deg_bateria_rs_kWh", "pen_deficit_rs_kWh", "pen_excesso_rs_kWh")):
            lo, hi = SG.RANGES[f"econ.{f}"]
            s["econ"][f] = float(cols[i].number_input(SG.LABELS[f"econ.{f}"], lo, hi, float(s["econ"][f]),
                                                      0.01 if hi <= 10 else 1.0, key=f"{k}_{f}"))
        cols = st.columns(3)
        for i, f in enumerate(("eta_dc1", "eta_dc2", "eta_dc")):
            lo, hi = SG.RANGES[f"eta_conv.{f}"]
            s["eta_conv"][f] = float(cols[i].number_input(SG.LABELS[f"eta_conv.{f}"], lo, hi, float(s["eta_conv"][f]),
                                                          0.01, key=f"{k}_{f}"))
        st.caption("Com a base PEMFC 'potência entregue', o EMS usa η FC = 1 no balanço (o valor acima só vale para a base "
                   "'stack').")
    with st.expander("Parâmetros fixos do motor V1.6 (informativos, não editáveis)"):
        st.html('<table class="op-tbl">' + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>"
                                                    for a, b in SG.ENGINE_FIXED.items()) + "</table>")
    errs = SG.strategy_errors(s)
    for e in errs:
        st.error(e)
    oc._save_bar(store, cur, I.summarize(S.findings(doc)))


# ======================================================================= etapa 04 — Execução
def _series_for_window(store, doc: dict) -> dict[str, M.Series]:
    from . import forecasts_ui

    get = forecasts_ui.get_blob_fn(store)
    out = {}
    for slot, entry in (doc.get("forecasts") or {}).items():
        if slot in F.EDITABLE_SLOTS and entry:
            try:
                out[slot] = M.load_series(slot, entry, get)
            except F.ForecastDataError:
                pass
    return out


def _climate_needed(doc: dict) -> bool:
    ref = doc["inventory_ref"]["equipment"]
    states = doc["initialization"]["equipment"]
    return any(r["kind"] in ("pv", "wind") and r.get("enabled", True)
               and (states.get(eid) or {}).get("availability") != "indisponivel" for eid, r in ref.items())


def _mission_editor(store, doc: dict) -> None:
    series = _series_for_window(store, doc)
    used = [series[s] for s in ("demand", "climate") if s in series and (s == "demand" or _climate_needed(doc))]
    dem = (doc.get("forecasts") or {}).get("demand") or {}
    m = doc.get("mission")
    tz_default = m.get("timezone") if m else dem.get("timezone")
    hz = M.available_horizon(used, tz_default) if used else None
    with st.container(border=True):
        st.html('<div class="op-k">Janela da missão</div><p class="op-d">Horizonte disponível dos perfis ≠ janela da '
                'missão ≠ passo do motor ≠ horizonte móvel N. Todas as séries são convertidas para UTC antes de serem '
                'combinadas; nada é extrapolado nem preenchido com zero.</p>')
        if hz:
            st.html('<table class="op-tbl">'
                    f'<tr><td>Horizonte disponível (cobertura comum)</td><td>{escape(hz["start_text"])} → {escape(hz["end_text"])}'
                    f' · até {hz["max_duration_min"]} min</td></tr>'
                    f'<tr><td>Séries consideradas</td><td>{escape(", ".join(("Demanda" if s.slot == "demand" else "Clima") + " — " + M.tz_label(s.entry.get("timezone")) for s in used))}</td></tr>'
                    f'<tr><td>Passo da simulação</td><td>60 s (fixo no runtime V1.6)</td></tr>'
                    f'<tr><td>Horizonte móvel N</td><td>{escape(str((doc.get("ems_strategy") or {}).get("N", "— (etapa 03)")))}</td></tr>'
                    '</table>')
        elif used:
            st.warning("As previsões necessárias não têm período comum (ou têm fusos incompatíveis): não há horizonte "
                       "disponível para uma missão.")
        else:
            st.info("Defina a previsão de demanda (e o clima, se houver FV/eólica) na etapa 02 antes da janela.")
        if m is None:
            if st.button("DEFINIR JANELA DA MISSÃO", key="op_ex_mission_new", type="primary", disabled=not dem):
                start = hz["start_wall"] if hz else pd.Timestamp(dem["t0"]).ceil("min")
                dur = min(120, hz["max_duration_min"]) if hz and hz["max_duration_min"] >= SG.MIN_DURATION_MIN else 120
                doc["mission"] = SG.default_mission(start.strftime("%Y-%m-%dT%H:%M:00"), dem.get("timezone"), dur)
                st.rerun()
            return
        tok = int(_ss().get("op_token") or 0)
        k = f"opw_ex_{tok}"
        start = pd.Timestamp(m["start"])
        c1, c2, c3, c4 = st.columns([1.1, .9, 1, 1.4])
        d = c1.date_input("Data de início", value=start.date(), key=f"{k}_d", format="DD/MM/YYYY")
        t = c2.time_input("Hora de início", value=start.time(), key=f"{k}_t", step=60)
        dur = c3.number_input("Duração (min)", min_value=SG.MIN_DURATION_MIN, value=int(m["duration_min"]), step=1,
                              key=f"{k}_dur")
        tz_opts = []
        for tzv in (dem.get("timezone"), ((doc.get("forecasts") or {}).get("climate") or {}).get("timezone"), m.get("timezone"),
                    "UTC"):
            if tzv and tzv not in tz_opts:
                tz_opts.append(tzv)
        tz_opts.append(None)
        tz = c4.selectbox("Fuso horário da missão", tz_opts, index=tz_opts.index(m.get("timezone")),
                          format_func=lambda z: z or "não declarado (relógio das séries)", key=f"{k}_tz")
        new = {"format_version": SG.FORMAT_VERSION, "start": f"{d.isoformat()}T{t.strftime('%H:%M')}:00", "timezone": tz,
               "duration_min": int(dur), "undeclared_clock": m.get("undeclared_clock")}
        if tz is None and len(used) > 1 and all(not s.declared for s in used):
            same = st.checkbox("Declaro que demanda e clima, ambos sem fuso declarado, usam o MESMO relógio local "
                               "(declaração registrada na rodada)", value=m.get("undeclared_clock") == SG.UNDECLARED_CLOCK,
                               key=f"{k}_clock")
            new["undeclared_clock"] = SG.UNDECLARED_CLOCK if same else None
        elif tz is not None:
            new["undeclared_clock"] = None
        if new != m:
            doc["mission"] = new
            st.rerun()
        if hz and c1.button("Usar o início da cobertura comum", key=f"{k}_fit"):
            doc["mission"] = {**new, "start": hz["start_wall"].strftime("%Y-%m-%dT%H:%M:00")}
            _oc()._bump()                             # renova as chaves dos campos (mostram o novo início)
            st.rerun()


def _report(pf: P.Preflight, cur) -> None:
    rep = pf.report()
    c = rep["counts"]
    st.markdown(f'<div class="sd-section">Resumo de preparação · versão salva v{cur.version}</div>', unsafe_allow_html=True)
    shell.kpis([("Incompatibilidades", str(c[P.ERROR]), "bloqueiam a execução"),
                ("Advertências", str(c[P.WARNING]), "não bloqueiam"),
                ("Verificações no motor", str(c[P.CHECK]), "antes do otimizador"),
                ("Equipamentos excluídos", str(len(rep["excluded"])), "somente desta rodada")])
    if not pf.ok:
        shell.callout("<b>Este cenário NÃO pode ser executado pelo motor atual</b> sem ignorar condições que você declarou. "
                      "Corrija as incompatibilidades abaixo (o cenário continua válido e gravável).", "bad")
    st.html(_items_html(rep["items"]))
    if rep["excluded"]:
        st.html("<div class='op-k' style='margin-top:.5rem'>Excluídos desta rodada (inventário inalterado)</div>"
                '<table class="op-tbl">' + "".join(
                    f"<tr><td>{escape(e['name'])}</td><td>{escape(KIND_LABELS.get(e.get('kind'), e.get('kind') or ''))}</td>"
                    f"<td>{escape(e['reason'])}</td></tr>" for e in rep["excluded"]) + "</table>")
    if pf.plan is not None:
        with st.expander("Parâmetros que efetivamente chegarão ao motor"):
            ei = pf.engine_inputs()
            spec = ei["model_spec"]
            rows = []
            for key, label in (("solar", "Solar FV"), ("wind", "Eólica"), ("battery", "Bateria"), ("fc", "H₂ / PEMFC"),
                               ("thermal", "Térmica")):
                sp = spec.get(key) or {}
                if sp.get("active"):
                    params = ", ".join(f"{a} = {b}" for a, b in sp.items() if a != "active")
                    rows.append(f"<tr><td>{escape(label)}</td><td>{escape(params)}</td></tr>")
            st.html('<table class="op-tbl"><tr><th>Modelo</th><th>Especificação (runtime V1.6)</th></tr>' + "".join(rows)
                    + "</table>")
            st.json({"optimizer_cfg": ei["optimizer_cfg"], "grade": ei["grid"], "estado_inicial_declarado":
                     ei["declared_initial_state"], "regra_do_motor": ei["engine_initial_state_rule"],
                     "conversao_temporal": ei["resampling"]}, expanded=False)
    if pf.window is not None and pf.window.ok:
        with st.expander("Entradas da missão na grade do motor (pré-visualização da versão salva)"):
            inp = runner.input_frame(pf.window)
            st.plotly_chart(RC.inputs_figure(inp, subtitle=f"{len(inp)} instantes · fuso {M.tz_label(pf.window.timezone)}"),
                            config=RC.CONFIG, key="op_ex_inputs_fig", width="stretch")


@st.fragment(run_every=1.0)
def _live(store, run_uid: str) -> None:
    try:
        run = store.get_run(run_uid)
    except StoreError:
        return
    if run.final:
        _ss()["op_flash"] = ({"concluida": "ok"}.get(run.state, "warn"),
                             f"Rodada {run.run_uid[:8]}… {contracts.RUN_STATE_LABELS[run.state].lower()}.")
        open_run(run.run_uid)
        st.rerun(scope="app")
    p = run.progress or {}
    phase = p.get("phase", "preparando")
    with st.container(border=True):
        st.html(f'<div class="op-row"><div class="op-t">Execução em andamento · rodada {escape(run.run_uid[:8])}…</div>'
                f'{_pill("Em execução", "info")}</div><p class="op-d">Cenário v{run.scenario_version} · iniciada '
                f'{escape(shell.fmt_time(run.created_at))}. A execução continua no servidor mesmo que esta página seja '
                'recarregada ou fechada.</p>')
        if phase == "otimizador" and p.get("n"):
            k, n = int(p.get("k", 0)), int(p["n"])
            st.progress(min(k / n, 1.0), text=f"{PHASES['otimizador']} · passo {k} de {n}")
        else:
            st.caption("⏳ " + PHASES.get(phase, phase))


def _active_run(store):
    runs = store.list_runs(limit=20)
    active = [r for r in runs if r.state == "em_execucao"]
    if any(not runner.is_running_here(r.run_uid) for r in active):
        runner.recover(store)
        active = [r for r in store.list_runs(limit=20) if r.state == "em_execucao"]
    return active[0] if active else None


def _history(store, cur, *, all_scenarios: bool) -> None:
    runs = store.list_runs(None if all_scenarios else cur.scenario_uid, limit=30)
    if not runs:
        st.caption("Nenhuma rodada registrada" + (" nesta microrrede." if all_scenarios else " para este cenário."))
        return
    names = {s.scenario_uid: s.name for s in store.list_scenarios()} if all_scenarios else {}
    for r in runs:
        s = r.summary or {}
        c1, c2 = st.columns([5, 1.1], vertical_alignment="center")
        cost = f"R$ {forms.fmt(s.get('custo_total_rs'), 2)}" if r.state == "concluida" else ""
        uns = f" · não atendida {forms.fmt(s.get('energia_nao_atendida_kWh'), 2, 'kWh')}" if r.state == "concluida" else ""
        who = f"{escape(names.get(r.scenario_uid, ''))} " if all_scenarios else ""
        c1.html(f'<div class="op-row" style="justify-content:flex-start;gap:.6rem">'
                f'{_pill(contracts.RUN_STATE_LABELS[r.state], STATE_TONE[r.state])}'
                f'<span class="op-m">{escape(r.run_uid[:8])}…</span><span>{who}v{r.scenario_version} · '
                f'{escape(shell.fmt_time(r.created_at))}</span><span class="op-m">{escape(cost)}{escape(uns)}</span></div>')
        if c2.button("Abrir", key=f"op_ex_open_{r.run_uid}", width="stretch"):
            open_run(r.run_uid)
            st.rerun()


def render_execution(store, cur) -> None:
    oc = _oc()
    st.html(EX_CSS)
    _back("op_back_ex")
    if cur is None or oc.work() is None:
        st.info("Nenhum cenário selecionado. Crie ou selecione um cenário no Centro de Operação.")
        return
    doc = oc.work()
    dirty = oc.is_dirty()
    shell.hero("Execução do cenário", doc["name"],
               "Seleção da janela, verificação científica de compatibilidade e rodada EMS (modelos físicos → contrato → "
               "otimizador V1.6). Cada rodada é imutável e fica gravada nesta microrrede.",
               [("Cenário (editável)", f"v{cur.version}" + (" · alterações não salvas" if dirty else "")),
                ("Inventário de referência", f"rev. {doc['inventory_ref']['config_revision']}"),
                ("Rodadas deste cenário", str(len(store.list_runs(cur.scenario_uid, limit=1000))))])
    st.html('<div class="ex-dist"><div><b>Cenário — editável</b><p class="op-d">Condições experimentais versionadas: '
            'estados iniciais, previsões, estratégia e janela. Editar cria uma nova versão.</p></div><div><b>Rodada — '
            'imutável</b><p class="op-d">Execução de UMA versão salva do cenário, com procedência, séries completas e '
            'resultados. Nunca é alterada; para mudar algo, edite o cenário e execute outra rodada.</p></div></div>')
    _mission_editor(store, doc)
    if dirty:
        shell.callout(f"Há <b>alterações não salvas</b> neste cenário. A verificação e a execução usam sempre a versão "
                      f"<b>salva</b> v{cur.version}: salve para incluir as alterações.", "warn")
    oc._save_bar(store, cur, I.summarize(S.findings(doc)))
    try:
        pf = preflight(store, cur)
    except StoreError as exc:
        st.error(shell.md(exc))
        return
    _report(pf, cur)
    active = _active_run(store)
    st.markdown('<div class="sd-section">Executar</div>', unsafe_allow_html=True)
    if active is not None:
        _live(store, active.run_uid)
    req_key = f"op_ex_req_{cur.scenario_uid}_{cur.version}"
    req = _ss().setdefault(req_key, runner.new_request_id())
    reason = ("há alterações não salvas" if dirty else "o cenário tem incompatibilidades" if not pf.ok else
              "outra rodada está em execução nesta microrrede" if active is not None else "")
    if st.button(f"▶ EXECUTAR CENÁRIO · VERSÃO {cur.version}", key="op_ex_run", type="primary", disabled=bool(reason),
                 help=f"Indisponível: {reason}." if reason else "Executa modelos físicos e otimizador sobre a versão salva."):
        try:
            run = runner.submit(store, cur.scenario_uid, cur.version, req, background=True)
        except runner.PreflightError as exc:
            st.error(shell.md(exc))
            return
        except (RunBusyError, StoreError) as exc:
            st.error(shell.md(exc))
            return
        _ss().pop(req_key, None)                      # pedido consumido: o mesmo clique nunca executa duas vezes
        _ss()["op_flash"] = ("info", f"Rodada {run.run_uid[:8]}… iniciada sobre a versão {cur.version}.")
        st.rerun()
    if reason:
        st.caption(f"Execução indisponível: {reason}.")
    st.markdown('<div class="sd-section">Rodadas registradas</div>', unsafe_allow_html=True)
    every = st.toggle("Mostrar rodadas de todos os cenários desta microrrede", key="op_ex_all")
    _history(store, cur, all_scenarios=every)


# ======================================================================= rodada (resultados persistidos)
def _kpis(s: dict) -> None:
    items = [("Custo total", f"R$ {forms.fmt(s.get('custo_total_rs'), 2)}", "função objetivo V1.6"),
             ("Energia atendida", forms.fmt(s.get("energia_atendida_kWh"), 2, "kWh"),
              f"de {forms.fmt(s.get('energia_demanda_kWh'), 2, 'kWh')} demandados"),
             ("Não atendida", forms.fmt(s.get("energia_nao_atendida_kWh"), 3, "kWh"), "déficit"),
             ("Excedente", forms.fmt(s.get("energia_excedente_kWh"), 2, "kWh"),
              f"renovável {forms.fmt(s.get('energia_excedente_renovavel_kWh'), 2, 'kWh')}")]
    if s.get("h2_kg") is not None:
        items.append(("H₂ consumido", forms.fmt(s["h2_kg"], 3, "kg"), "estimativa do EMS"
                      + (f" · dinâmico {forms.fmt(s['h2_kg_validacao_dinamica'], 3, 'kg')}" if s.get("h2_kg_validacao_dinamica") else "")))
    shell.kpis(items)


def render_run(store, cur) -> None:
    st.html(EX_CSS)
    ss = _ss()
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("← Execução do cenário", key="op_back_run"):
            ss.pop("op_run_uid", None)
            shell.go("operacao", TAB_EXEC)
            st.rerun()
    uid = ss.get("op_run_uid") or st.query_params.get("run")
    if not uid:
        st.info("Nenhuma rodada selecionada.")
        return
    try:
        run = store.get_run(uid)
    except RunNotFound:
        st.error("Esta rodada não existe nesta microrrede.")
        return
    ss["op_run_uid"] = run.run_uid
    m = run.manifest
    scn = m.get("scenario") or {}
    eng = (run.outcome or {}).get("effective_engine") or {}
    shell.hero("Rodada · imutável", f"{scn.get('name')} · versão {run.scenario_version}",
               "Resultados lidos do armazenamento local desta microrrede. Abrir esta página NÃO executa modelos nem o "
               "otimizador.",
               [("Estado", contracts.RUN_STATE_LABELS[run.state]), ("Rodada", run.run_uid),
                ("Iniciada", shell.fmt_time(run.created_at)), ("Finalizada", shell.fmt_time(run.finished_at) or "—"),
                ("Inventário", f"rev. {run.config_revision} · {run.config_fingerprint[:10]}…"),
                ("Algoritmo", f"{eng.get('algoritmo', (m.get('strategy') or {}).get('algorithm'))} · N = "
                              f"{(m.get('strategy') or {}).get('N')}")])
    if cur is not None and cur.scenario_uid == run.scenario_uid and cur.version != run.scenario_version:
        st.caption(f"O cenário está agora na versão {cur.version}; esta rodada permanece vinculada à versão "
                   f"{run.scenario_version} (imutável).")
    if run.state == "em_execucao":
        _live(store, run.run_uid)
        return
    run_results(store, run, key="op_run")


def run_results(source, run, *, key: str) -> None:
    """Resultados de uma rodada FINALIZADA lidos de ``source`` (``MicrogridStore`` da microrrede ou, no Piso 2D-A, um
    estudo arquivado — mesmo contrato ``run_data``). Nunca chama modelos nem o otimizador. ``key`` prefixa os widgets."""
    m = run.manifest
    if run.state != "concluida":
        err = run.error or {}
        shell.callout(f"<b>Rodada {escape(contracts.RUN_STATE_LABELS.get(run.state, run.state).lower())}</b> — "
                      f"{escape(err.get('message') or '')} Nenhum resultado foi gravado como concluído.", "bad")
        chk = ((run.outcome or {}).get("engine_check") or {}).get("items") or err.get("items") or []
        if chk:
            st.html(_items_html(chk))
        _provenance(run)
        return
    s = run.summary or {}
    _kpis(s)
    try:
        out = runner.load_csv(source, run.run_uid, "saidas/despacho_ems.csv")
        inp = runner.load_csv(source, run.run_uid, "entradas/missao.csv")
    except StoreError as exc:
        st.error(shell.md(exc))
        return
    sub = f"{len(out)} passos de 60 s · fuso {M.tz_label((m.get('mission') or {}).get('timezone'))}"
    st.plotly_chart(RC.power_figure(out, subtitle=sub), config=RC.CONFIG, key=f"{key}_power", width="stretch")
    bat = ((m.get("engine_inputs") or {}).get("declared_initial_state") or {}).get("battery") or {}
    fig = RC.soc_figure(out, soc_min=bat.get("soc_min_pct"), soc_max=bat.get("soc_max_pct"), subtitle=sub)
    if fig is not None:
        st.plotly_chart(fig, config=RC.CONFIG, key=f"{key}_soc", width="stretch")
    fig = RC.h2_figure(out, subtitle=sub)
    if fig is not None:
        st.plotly_chart(fig, config=RC.CONFIG, key=f"{key}_h2", width="stretch")
    with st.expander("Entradas da missão gravadas (grade do motor)"):
        st.plotly_chart(RC.inputs_figure(inp, subtitle=sub), config=RC.CONFIG, key=f"{key}_inputs", width="stretch")
    if s.get("avisos"):
        st.markdown('<div class="sd-section">Avisos do motor</div>', unsafe_allow_html=True)
        st.html("".join(shell.check(escape(a), "warn") for a in s["avisos"]))
    chk = ((run.outcome or {}).get("engine_check") or {}).get("items") or []
    if chk:
        st.markdown('<div class="sd-section">Contrato efetivo do motor (verificado antes do otimizador)</div>',
                    unsafe_allow_html=True)
        st.html(_items_html(chk))
    _provenance(run)


def _provenance(run) -> None:
    m = run.manifest
    with st.expander("Procedência da rodada (manifesto imutável)"):
        ref = m.get("reference") or {}
        sw = m.get("software") or {}
        rows = [("Microrrede", f"{ref.get('microgrid_uid')} · incarnação {ref.get('microgrid_incarnation')}"),
                ("Cenário", f"{ref.get('scenario_uid')} · v{ref.get('scenario_version')} · {str(ref.get('scenario_fingerprint'))[:16]}…"),
                ("Inventário", f"revisão {ref.get('config_revision')} · {str(ref.get('config_fingerprint'))[:16]}…"),
                ("Software", f"{sw.get('app')} · Python {sw.get('python')} · numpy {sw.get('numpy')} · scipy {sw.get('scipy')}"),
                ("Código científico", f"SHA-256 {str((sw.get('science') or {}).get('sha256'))[:16]}… "
                                      f"({(sw.get('science') or {}).get('files')} arquivos)"),
                ("Função objetivo", (m.get("objective") or {}).get("label", "")),
                ("Janela", f"{(m.get('mission') or {}).get('start_wall')} ({(m.get('mission') or {}).get('timezone') or 'não declarado'})"
                           f" · {(m.get('mission') or {}).get('duration_min')} min · UTC {(m.get('mission') or {}).get('start_utc')}")]
        for slot, e in (m.get("forecasts") or {}).items():
            rows.append((f"Previsão {slot}", f"{e.get('label')} · série {str(e.get('data'))[:12]}… · fuso "
                                             f"{e.get('timezone') or 'não declarado'}"))
        st.html('<table class="op-tbl">' + "".join(f"<tr><td>{escape(a)}</td><td>{escape(str(b))}</td></tr>" for a, b in rows)
                + "</table>")
        if run.data:
            st.html("<div class='op-k'>Dados gravados (SHA-256 do conteúdo)</div><table class='op-tbl'>" + "".join(
                f"<tr><td>{escape(n)}</td><td class='op-m'>{escape(d['sha256'][:16])}… · {d['size']:,} bytes</td></tr>"
                for n, d in run.data.items()) + "</table>")
        st.json(m, expanded=False)


__all__ = ["TAB_EXEC", "TAB_RUN", "TAB_STRATEGY", "clear_state", "open_run", "preflight", "render_execution", "render_run",
           "render_strategy", "run_results", "stage_state"]
