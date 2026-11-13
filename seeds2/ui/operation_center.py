"""Centro de Operação (Pisos 2A/2B) — espaço cotidiano da microrrede ativa.

* Painel (``tab`` vazio): cenário selecionado, inventário de referência, prontidão, etapas (Inicialização e
  Previsões disponíveis; Estratégia EMS e Execução identificadas como NÃO implementadas — sem botões fictícios),
  resumo da instalação física e acesso às ferramentas V1.6.
* Previsões (``tab = "previsoes"``, Piso 2B): ``forecasts_ui`` — demanda e clima (manual, CSV, sintético,
  referência) com pré-visualização gráfica, qualidade e cobertura; gravadas com o cenário (``op_blobs``).
* Inicialização (``tab = "inicializacao"``): estados iniciais por equipamento, construídos a partir do inventário
  de referência do cenário; validação explícita (erro de coerência / advertência / capacidade pendente).

Estado de sessão (prefixo ``op_``; limpo integralmente ao trocar de microrrede por ``session.reset_state``):
``op_scenario_uid`` (selecionado), ``op_work`` (cópia de trabalho do documento do cenário), ``op_base_version`` /
``op_base_fp`` (versão salva sobre a qual a edição foi iniciada), ``op_token`` (renova as chaves dos widgets ao
recarregar), ``op_conflict``/``op_error``/``op_flash`` (mensagens) e ``op_form`` (formulário aberto).
Nada aqui grava a configuração física permanente da microrrede.
"""
from __future__ import annotations

import copy
from html import escape

import streamlit as st

from seeds2.microgrid import config as C
from seeds2.microgrid.references import KIND_LABELS
from seeds2.microgrid.store import ScenarioConflictError, ScenarioNotFound, StoreError
from seeds2.operation import initialization as I
from seeds2.operation import scenarios as S
from seeds2.operation import service

from . import archive_ui, caderno_ui, execution_ui, folha_ui, forecasts_ui, forms, home, planta_ui, session, shell

SCN = shell.SCENARIO_KEY
TAB_INIT = "inicializacao"
TAB_FC = forecasts_ui.TAB
TAB_SG, TAB_EX, TAB_RUN = execution_ui.TAB_STRATEGY, execution_ui.TAB_EXEC, execution_ui.TAB_RUN
TAB_AR, TAB_STUDY = archive_ui.TAB_LIST, archive_ui.TAB_STUDY        # Piso 2D-A — Arquivo Científico
KIND_ORDER = ("battery", "pemfc", "thermal", "pv", "wind")
KIND_SECTION = {"battery": "Armazenamento — baterias", "pemfc": "H₂ / PEMFC", "thermal": "Térmica",
                "pv": "Solar fotovoltaica", "wind": "Eólica"}
TONE = {I.ERROR: "bad", I.WARNING: "warn", I.PENDING: "info", I.INCOMPLETE: "off"}
GLYPH = {I.ERROR: "✕", I.WARNING: "!", I.PENDING: "◷", I.INCOMPLETE: "–"}

OP_CSS = """
<style>
.op-k { font-size: .7rem; font-weight: 750; letter-spacing: .11em; text-transform: uppercase; opacity: .62; margin-bottom: .2rem; }
.op-t { font-size: 1.12rem; font-weight: 720; letter-spacing: -.01em; line-height: 1.25; margin: 0 0 .2rem 0; }
.op-d { font-size: .86rem; opacity: .78; line-height: 1.45; margin: 0 0 .35rem 0; }
.op-m { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .76rem; opacity: .7; }
.op-pill { display: inline-flex; align-items: center; gap: .35rem; font-size: .72rem; font-weight: 700; padding: .14rem .55rem;
  border-radius: 999px; white-space: nowrap; }
.op-pill.ok { color: #1f7a4c; background: rgba(46,139,87,.13); } .op-pill.warn { color: #a35c00; background: rgba(214,137,16,.15); }
.op-pill.bad { color: #b02a3e; background: rgba(194,54,74,.13); } .op-pill.off { color: #5B6B7C; background: rgba(91,107,124,.14); }
.op-pill.info { color: #2F5FCC; background: rgba(47,111,237,.12); }
.op-row { display: flex; align-items: center; justify-content: space-between; gap: .6rem; flex-wrap: wrap; }
.op-f { display: flex; gap: .5rem; align-items: flex-start; font-size: .84rem; line-height: 1.42; margin: .22rem 0; }
.op-f i { flex: none; font-style: normal; width: 1.2rem; height: 1.2rem; border-radius: 50%; display: grid; place-items: center;
  font-size: .7rem; font-weight: 800; margin-top: .05rem; }
.op-f i.bad { color: #C2364A; background: rgba(194,54,74,.14); } .op-f i.warn { color: #C77700; background: rgba(199,119,0,.14); }
.op-f i.info { color: #2F6FED; background: rgba(47,111,237,.13); } .op-f i.off { color: #5B6B7C; background: rgba(91,107,124,.14); }
.op-f b { font-weight: 650; }
.op-ref { font-size: .8rem; opacity: .75; margin: -.1rem 0 .45rem 0; }
.op-stage-n { font-size: .7rem; font-weight: 800; letter-spacing: .1em; opacity: .5; }
.op-tbl { border-collapse: collapse; font-size: .82rem; margin: .25rem 0 .5rem 0; width: 100%; }
.op-tbl td, .op-tbl th { padding: .22rem .5rem; border-bottom: 1px solid rgba(128,128,128,.18); text-align: left; vertical-align: top; }
.op-tbl th { font-size: .7rem; letter-spacing: .06em; text-transform: uppercase; opacity: .65; }
.op-tbl td:first-child { opacity: .75; white-space: nowrap; }
.op-legend { display: flex; flex-wrap: wrap; gap: .4rem 1.1rem; font-size: .8rem; opacity: .9; margin: .2rem 0 .6rem 0; }
</style>
"""


# ======================================================================= estado do cenário na sessão
def _ss():
    return st.session_state


def _flash(tone: str, text: str) -> None:
    _ss()["op_flash"] = (tone, text)


def _bump() -> None:
    _ss()["op_token"] = int(_ss().get("op_token") or 0) + 1


def _adopt(stored) -> None:
    ss = _ss()
    ss[SCN] = stored.scenario_uid
    ss["op_work"] = copy.deepcopy(stored.document)
    ss["op_work_uid"] = stored.scenario_uid
    ss["op_base_version"] = stored.version
    ss["op_base_fp"] = _fp_edicao(stored.document)
    for k in ("op_conflict", "op_error", "op_stale", "op_blobs"):
        ss.pop(k, None)                     # op_blobs: dados de previsão pendentes (gravados ou descartados)
    _bump()


def _clear_selection() -> None:
    ss = _ss()
    for k in (SCN, "op_work", "op_work_uid", "op_base_version", "op_base_fp", "op_conflict", "op_error", "op_stale"):
        ss.pop(k, None)
    forecasts_ui.clear_state()
    execution_ui.clear_state()


def work() -> dict | None:
    return _ss().get("op_work")


def _canon_num(x):
    """Forma canônica SÓ para a comparação de edição: inteiro e real de mesmo valor são o mesmo número (os campos
    numéricos devolvem ``float`` para um valor gravado como ``int``, p. ex. 0 → 0.0). O documento NÃO é alterado."""
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, int):
        return float(x)
    if isinstance(x, dict):
        return {k: _canon_num(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_canon_num(v) for v in x]
    return x


def _fp_edicao(doc: dict) -> str:
    """Impressão da cópia de trabalho para «alterações não salvas»: abrir e percorrer as etapas (que apresentam os
    números do documento em campos reais) não cria alteração; qualquer mudança de valor, texto, opção ou estrutura cria."""
    return C.fingerprint(_canon_num(doc))


def is_dirty() -> bool:
    w = work()
    return w is not None and _fp_edicao(w) != _ss().get("op_base_fp")


def sync(store) -> tuple[list, object | None]:
    """Lista os cenários DESTA microrrede e sincroniza a cópia de trabalho do selecionado. Uma edição pendente
    nunca é substituída em silêncio: se outra sessão salvou uma versão nova, ela é apenas sinalizada
    (``op_stale``) e o salvamento acusará conflito."""
    ss = _ss()
    items = store.list_scenarios()
    uids = {s.scenario_uid for s in items}
    sel = ss.get(SCN)
    if sel is None and "op_url_checked" not in ss:      # recarga da página: ?sc=<uid> (apenas se for DESTA microrrede)
        ss["op_url_checked"] = True
        q = st.query_params.get("sc")
        if q in uids:
            sel = q
    if sel is not None and sel not in uids:
        if ss.get("op_work_uid") == sel:
            ss["op_error"] = "O cenário selecionado não existe nesta microrrede."
        _clear_selection()
        sel = None
    if sel is None and items:
        sel = items[-1].scenario_uid                     # o mais recente
    if sel is None:
        return items, None
    try:
        cur = store.get_scenario(sel)
    except ScenarioNotFound:
        _clear_selection()
        return items, None
    if ss.get("op_work_uid") != sel or work() is None:
        _adopt(cur)
    elif cur.version != ss.get("op_base_version"):
        if is_dirty():
            ss["op_stale"] = cur.version
        else:
            _adopt(cur)
            _flash("info", f"Cenário atualizado para a versão {cur.version} (salva em outra sessão).")
    else:
        ss.pop("op_stale", None)
    ss[SCN] = sel
    return items, cur


# ======================================================================= apresentação auxiliar
def _pill(text: str, tone: str) -> str:
    return f'<span class="op-pill {escape(tone)}">{escape(text)}</span>'


def _findings_html(fs: list[I.Finding]) -> str:
    order = {I.ERROR: 0, I.INCOMPLETE: 1, I.WARNING: 2, I.PENDING: 3}
    rows = []
    for f in sorted(fs, key=lambda f: order[f.level]):
        rows.append(f'<div class="op-f"><i class="{TONE[f.level]}">{GLYPH[f.level]}</i><span>'
                    f'<b>{escape(I.LEVEL_LABELS[f.level])}:</b> {escape(f.message)}</span></div>')
    return "".join(rows)


def _ref_line(ref: dict) -> str:
    k = ref["kind"]
    parts = []
    if k == "battery":
        parts.append(f"Energia nominal {forms.fmt(ref.get('energy_kWh'), 1, 'kWh')}")
        if ref.get("soc_min_pct") is not None and ref.get("soc_max_pct") is not None:
            src = ref.get("soc_limits_source") or "sugerido"
            kind = "intervalo recomendado" if src not in I.SOC_OPERATIONAL_SOURCES else "restrição operacional"
            parts.append(f"{kind} de SOC {ref['soc_min_pct']:g}–{ref['soc_max_pct']:g} % "
                         f"({C.SOC_LIMIT_SOURCES.get(src, src).lower()})")
        parts.append("limite físico 0–100 %")
    elif k == "pemfc":
        parts.append(f"{ref.get('quantity') or '?'} unidade(s) instalada(s)")
        parts.append(f"máx. {forms.fmt(ref.get('unit_max_kW'), 1, 'kW')} por unidade" if ref.get("unit_max_kW")
                     else "potência por unidade não conhecida")
    elif k == "thermal":
        parts.append(f"Pmín técnica {forms.fmt(ref.get('pmin_kW'), 1, 'kW')} · Pmáx {forms.fmt(ref.get('pmax_kW'), 1, 'kW')}")
    elif k == "wind":
        parts.append(f"{ref.get('count') or '?'} aerogerador(es) · {forms.fmt(ref.get('nominal_kW'), 1, 'kW')} nominal")
    elif k == "pv":
        parts.append(f"{ref.get('arrays', 0)} arranjo(s) · {forms.fmt(ref.get('nominal_kW'), 2, 'kWp')} registrados")
    return " · ".join(parts)


def _drift(store, doc: dict):
    saved = session.saved()
    return S.drift(doc, saved.config, saved.revision), saved


# ======================================================================= formulários (novo / duplicar / dados)
def _form(store, items, cur) -> None:
    ss = _ss()
    kind = ss.get("op_form")
    if kind not in ("new", "dup", "meta") or (kind != "new" and cur is None):
        ss.pop("op_form", None)
        return
    titles = {"new": "Novo cenário", "dup": f"Duplicar “{cur.name}”" if cur else "", "meta": "Nome e descrição do cenário"}
    with st.container(border=True):
        st.markdown(f'<div class="op-t">{escape(titles[kind])}</div>', unsafe_allow_html=True)
        if kind == "new":
            st.caption(f"O cenário é definido sobre a revisão salva {session.saved().revision} do inventário. Ele não "
                       "altera a configuração física da microrrede.")
        elif kind == "dup":
            st.caption(f"Cópia independente da versão salva {cur.version} (alterações não salvas desta sessão não são "
                       "copiadas). Mesma referência de inventário e mesmas condições.")
        default_name = {"new": "", "dup": f"Cópia de {cur.name}"[:S.NAME_MAX] if cur else "",
                        "meta": cur.name if cur else ""}[kind]
        default_desc = {"new": "", "dup": cur.document.get("description", "") if cur else "",
                        "meta": cur.document.get("description", "") if cur else ""}[kind]
        with st.form(f"op_form_{kind}", border=False):
            name = st.text_input("Nome do cenário *", value=default_name, max_chars=S.NAME_MAX)
            desc = st.text_area("Descrição", value=default_desc, max_chars=S.DESCRIPTION_MAX, height=90,
                                placeholder="Objetivo do experimento, hipóteses, condições...")
            c1, c2 = st.columns(2)
            ok = c1.form_submit_button({"new": "Criar cenário", "dup": "Duplicar cenário", "meta": "Salvar nome e descrição"}[kind],
                                       type="primary", width="stretch")
            cancel = c2.form_submit_button("Cancelar", width="stretch")
        if cancel:
            ss.pop("op_form", None)
            st.rerun()
        if not ok:
            return
        if not name.strip():
            st.error("Informe o nome do cenário.")
            return
        try:
            if kind == "new":
                res = service.create(store, name=name, description=desc)
                _flash("ok", f"Cenário “{res.name}” criado (versão 1, inventário rev. {res.base_revision}).")
            elif kind == "dup":
                res = service.duplicate(store, cur.scenario_uid, name=name, description=desc)
                _flash("ok", f"Cenário “{res.name}” criado como cópia independente de “{cur.name}” (v{cur.version}).")
            else:
                if is_dirty():
                    st.error("Há alterações não salvas na Inicialização deste cenário: salve-as ou descarte-as antes de "
                             "renomear (nada foi gravado).")
                    return
                doc = copy.deepcopy(cur.document)
                doc["name"], doc["description"] = " ".join(name.split()), desc.strip()
                res = service.save(store, doc, cur.version, note="Nome/descrição do cenário")
                _flash("ok", f"Dados do cenário salvos (versão {res.version}).")
        except ScenarioConflictError as exc:
            st.error(str(exc))
            return
        except (S.ScenarioValidationError, StoreError) as exc:
            st.error(shell.md(exc))
            return
        ss.pop("op_form", None)
        _adopt(res)
        shell.go("operacao")
        st.rerun()


# ======================================================================= painel
def _scenario_bar(store, items, cur) -> None:
    ss = _ss()
    if not items:
        shell.callout("<b>Nenhum cenário nesta microrrede.</b> Um cenário reúne condições experimentais editáveis "
                      "(estados iniciais e previsões; futuramente estratégia EMS) sem alterar a configuração física.", "")
        if ss.get("op_form") is None and st.button("＋ NOVO CENÁRIO", key="op_new_empty", type="primary"):
            ss["op_form"] = "new"
            st.rerun()
        return
    by_uid = {s.scenario_uid: s for s in items}
    c1, c2, c3, c4 = st.columns([3.2, 1.1, 1.1, 1.3], vertical_alignment="bottom")
    opts = [s.scenario_uid for s in items]
    idx = opts.index(cur.scenario_uid) if cur is not None and cur.scenario_uid in opts else len(opts) - 1
    choice = c1.selectbox("Cenário selecionado", opts, index=idx, key=f"op_pick_{ss.get('op_token', 0)}",
                          format_func=lambda u: f"{by_uid[u].name} · v{by_uid[u].version}")
    if cur is not None and choice != cur.scenario_uid:
        if is_dirty():
            c1.error("Há alterações não salvas neste cenário: salve-as ou descarte-as antes de trocar de cenário.")
        else:
            _clear_selection()
            ss[SCN] = choice
            shell.go("operacao")
            st.rerun()
    if c2.button("＋ Novo", key="op_new", width="stretch", help="Criar um novo cenário"):
        ss["op_form"] = "new"
        st.rerun()
    if c3.button("Duplicar", key="op_dup", width="stretch", help="Cópia independente do cenário selecionado"):
        ss["op_form"] = "dup"
        st.rerun()
    if c4.button("Nome e descrição", key="op_meta", width="stretch"):
        ss["op_form"] = "meta"
        st.rerun()


def _cards(store, cur) -> None:
    doc = work()
    d, saved = _drift(store, doc)
    fs = S.findings(doc)
    rd = S.readiness(doc, fs, d)
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1, st.container(border=True, height="stretch"):
        lin = (doc.get("lineage") or {}).get("duplicated_from")
        status = _pill("Alterações não salvas", "warn") if is_dirty() else _pill(f"Salvo · v{cur.version}", "ok")
        st.html(f'<div class="op-k">Cenário</div><div class="op-row"><div class="op-t">{escape(doc["name"])}</div>{status}</div>'
                f'<p class="op-d">{escape(doc.get("description") or "Sem descrição.")}</p>'
                f'<div class="op-m">versão {cur.version} · atualizado {escape(shell.fmt_time(cur.updated_at))}'
                f'{" · cópia de “" + escape(lin["name"]) + "” v" + str(lin["version"]) if lin else ""}</div>'
                f'<div class="op-m">ID {escape(cur.scenario_uid)}</div>')
    with c2, st.container(border=True, height="stretch"):
        ref = doc["inventory_ref"]
        if d.stale:
            tone, label = "warn", "Inventário mudou"
        elif not d.same_revision:
            tone, label = "ok", "Equivalente ao atual"
        else:
            tone, label = "ok", "Revisão atual"
        changes = d.describe(doc, saved.config) if d.stale else []
        body = "".join(f"<li>{escape(x)}</li>" for x in changes[:6])
        st.html(f'<div class="op-k">Inventário de referência</div><div class="op-row"><div class="op-t">Revisão '
                f'{ref["config_revision"]}</div>{_pill(label, tone)}</div>'
                f'<p class="op-d">{len(ref["equipment"])} equipamento(s) no instantâneo do cenário. Revisão salva atual da '
                f'microrrede: {saved.revision}.</p>'
                + (f'<ul class="op-d" style="margin:.1rem 0 .3rem 1rem;padding:0">{body}</ul>' if body else "")
                + f'<div class="op-m">configuração {escape(ref["config_fingerprint"][:12])}… · inventário '
                  f'{escape(ref["inventory_fingerprint"][:12])}…</div>')
        if not d.same_revision:
            if st.button(f"Atualizar referência para a revisão {saved.revision}", key="op_rebase_panel", width="stretch",
                         disabled=is_dirty(), help="Salve ou descarte alterações pendentes antes." if is_dirty() else
                         "Cria nova versão do cenário vinculada à revisão atual; estados de equipamentos retirados "
                         "são preservados."):
                _rebase(store, cur)
    with c3, st.container(border=True, height="stretch"):
        rows = []
        for key, title, sub in S.STAGES:
            tone, label, detail = rd["stages"][key]
            rows.append(shell.check(f"<b>{escape(title)}</b> — {escape(label)}"
                                    f"{' · ' + escape(detail) if detail else ''}", {"info": "warn"}.get(tone, tone)))
        ex_tone, ex_label, _ = execution_ui.stage_state(store, cur)
        st.html('<div class="op-k">Preparação do cenário</div><div class="op-row"><div class="op-t">'
                f'{"Inicialização definida" if rd["stages"]["inicializacao"][0] == "ok" else "Em preparação"}</div>'
                f'{_pill(ex_label + f" (v{cur.version})", ex_tone)}</div>' + "".join(rows))


def _archive_card(store, cur) -> None:
    """Piso 2D-A: acesso ao ARQUIVO CIENTÍFICO (exportar/importar/consultar estudos) sem alterar as etapas 01–04."""
    try:
        n = len(session.archive().list_studies())
    except StoreError:
        n = None
    with st.container(border=True, key="op_archive_card"):
        c1, c2 = st.columns([3.2, 1.3], vertical_alignment="center")
        c1.html('<div class="op-k">Arquivo Científico</div><div class="op-t">Exportar, importar e consultar estudos</div>'
                '<p class="op-d">EXPORTAR CENÁRIO COMPLETO (todas as versões, previsões, rodadas e resultados) em um pacote '
                '.seeds2study.zip portátil; estudos importados ficam somente leitura e separados desta microrrede.'
                + (f" {n} estudo(s) arquivado(s) nesta instalação." if n is not None else "") + '</p>')
        if c2.button("ABRIR ARQUIVO CIENTÍFICO", key="op_open_ar", type="primary", width="stretch"):
            shell.go("operacao", TAB_AR)
            st.rerun()


def _rebase(store, cur) -> None:
    try:
        res = service.rebase(store, cur.scenario_uid, cur.version)
    except ScenarioConflictError as exc:
        _ss()["op_conflict"] = str(exc)
        st.rerun()
    except (S.ScenarioValidationError, StoreError) as exc:
        _ss()["op_error"] = str(exc)
        st.rerun()
    _adopt(res)
    _flash("ok", f"Referência atualizada para a revisão {res.base_revision} do inventário (versão {res.version} do "
                 "cenário). Revise os estados iniciais.")
    st.rerun()


def _stages(store, cur) -> None:
    st.markdown('<div class="sd-section">Etapas do experimento</div>', unsafe_allow_html=True)
    doc = work()
    fs = S.findings(doc) if doc else []
    cols = st.columns(4, gap="small")
    for i, (col, (key, title, sub)) in enumerate(zip(cols, S.STAGES)):
        with col, st.container(border=True, height="stretch"):
            if key == "inicializacao":
                rd = S.readiness(doc, fs, None) if doc else None
                tone, label, _ = rd["stages"][key] if rd else ("off", "Sem cenário", "")
                st.html(f'<div class="op-row"><span class="op-stage-n">0{i + 1}</span>{_pill(label, tone)}</div>'
                        f'<div class="op-t">{escape(title)}</div><p class="op-d">{escape(sub)}. Disponível nesta versão.</p>')
                if st.button("ABRIR INICIALIZAÇÃO", key="op_open_init", type="primary", width="stretch", disabled=cur is None):
                    shell.go("operacao", TAB_INIT)
                    st.rerun()
            elif key == "previsoes":
                rd = S.readiness(doc, fs, None) if doc else None
                tone, label, _ = rd["stages"][key] if rd else ("off", "Sem cenário", "")
                st.html(f'<div class="op-row"><span class="op-stage-n">0{i + 1}</span>{_pill(label, tone)}</div>'
                        f'<div class="op-t">{escape(title)}</div><p class="op-d">{escape(sub)}. Disponível nesta versão.</p>')
                if st.button("ABRIR PREVISÕES", key="op_open_fc", type="primary", width="stretch", disabled=cur is None):
                    shell.go("operacao", TAB_FC)
                    st.rerun()
            elif key == "estrategia":
                tone, label, _ = S.strategy_status(doc) if doc else ("off", "Sem cenário", "")
                st.html(f'<div class="op-row"><span class="op-stage-n">0{i + 1}</span>{_pill(label, tone)}</div>'
                        f'<div class="op-t">{escape(title)}</div><p class="op-d">{escape(sub)}.</p>')
                if st.button("ABRIR ESTRATÉGIA EMS", key="op_open_sg", type="primary", width="stretch", disabled=cur is None):
                    shell.go("operacao", TAB_SG)
                    st.rerun()
            else:
                tone, label, _ = execution_ui.stage_state(store, cur) if cur is not None else ("off", "Sem cenário", "")
                st.html(f'<div class="op-row"><span class="op-stage-n">0{i + 1}</span>{_pill(label, tone)}</div>'
                        f'<div class="op-t">{escape(title)}</div><p class="op-d">{escape(sub)}.</p>')
                if st.button("ABRIR EXECUÇÃO", key="op_open_ex", type="primary", width="stretch", disabled=cur is None):
                    shell.go("operacao", TAB_EX)
                    st.rerun()


def _panel(store, items, cur) -> None:
    saved = session.saved()
    inst = saved.config["installation"]
    shell.hero("Centro de Operação", inst["name"],
               "Espaço de trabalho cotidiano da microrrede ativa: selecione um cenário, defina as condições iniciais e "
               "prepare experimentos. Operação manual e experimental — sem telemetria, SCADA nem controle físico.",
               [("Inventário", f"rev. {saved.revision} · {saved.fingerprint[:10]}…"), ("Identidade", inst["uid"]),
                ("Cenários", str(len(items)))] + home.installation_facts(saved))
    home.identification_notice()
    _scenario_bar(store, items, cur)
    _form(store, items, cur)
    if cur is not None and work() is not None:
        _cards(store, cur)
    _stages(store, cur)
    shell.callout("<b>Execução de cenário (etapa 04)</b>: usa as condições DESTE cenário — estados iniciais, previsões, "
                  "estratégia e janela — sobre a revisão do inventário que ele referencia, e grava cada rodada (imutável) "
                  "nesta microrrede. A <b>Simulação</b> (console V1.6) continua independente: usa a configuração salva da "
                  "microrrede, suas condições da rodada e a demanda/clima do inventário.", "")
    _archive_card(store, cur)
    with st.expander("Instalação física (inventário salvo) e prontidão do console V1.6"):
        home.installation_summary()
    with st.expander("Ferramentas V1.6 — bancadas individuais dos modelos"):
        home.benches()


# ======================================================================= inicialização
def _availability(prefix: str, state: dict, disabled: bool = False) -> None:
    keys = list(I.AVAILABILITY)
    val = st.radio("Disponibilidade técnica", keys, index=keys.index(state.get("availability", "disponivel")),
                   format_func=lambda k: {"disponivel": "Disponível", "indisponivel": "Indisponível"}[k],
                   horizontal=True, key=f"{prefix}_av", disabled=disabled,
                   help="Disponibilidade técnica do equipamento no cenário (manutenção, falha...). Distinta do estado "
                        "operativo e da produção prevista.")
    state["availability"] = val


def _state_select(prefix: str, state: dict, labels: dict) -> None:
    opts = [None, *labels]
    cur = state.get("state")
    val = st.selectbox("Estado operativo inicial", opts, index=opts.index(cur) if cur in opts else 0,
                       format_func=lambda k: "— não definido —" if k is None else labels[k], key=f"{prefix}_st")
    state["state"] = val


def _number(label: str, prefix: str, field: str, state: dict, *, integer: bool = False, **kw) -> None:
    v = state.get(field)
    if integer:
        val = st.number_input(label, value=int(v) if isinstance(v, int) else None, step=1, min_value=0,
                              key=f"{prefix}_{field}", placeholder="não definido", **kw)
        state[field] = int(val) if val is not None else None
    else:
        val = st.number_input(label, value=float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None,
                              step=1.0, min_value=0.0, key=f"{prefix}_{field}", placeholder="não definido",
                              format="%.2f", **kw)
        state[field] = float(val) if val is not None else None


def _equipment_card(eq_id: str, ref: dict, state: dict, token: int) -> None:
    prefix = f"op_{eq_id}_{token}"
    k = ref["kind"]
    with st.container(border=True):
        tag = f" · {ref['tag']}" if ref.get("tag") else ""
        st.html(f'<div class="op-row"><div class="op-t">{escape(ref["name"])}</div>'
                f'<span class="op-m">{escape(KIND_LABELS[k])}{escape(tag)}</span></div>'
                f'<div class="op-ref">{escape(_ref_line(ref))}</div>')
        _availability(prefix, state)
        if k == "battery":
            _number("SOC inicial (%)", prefix, "soc0_pct", state, max_value=100.0,
                    help="Estado de carga no instante inicial do cenário. Limite físico 0–100 %; fora do intervalo "
                         "recomendado/operacional gera advertência, não bloqueio.")
        elif k == "pemfc":
            _state_select(prefix, state, I.DISPATCH_STATES)
            a, b = st.columns(2)
            with a:
                _number("Unidades em operação", prefix, "units_on", state, integer=True,
                        help=f"Sistemas/stacks em operação (instalados: {ref.get('quantity') or '?'}).")
            with b:
                _number("Potência inicial (kW)", prefix, "power_kW", state, help="Potência líquida entregue no instante inicial.")
        elif k == "thermal":
            _state_select(prefix, state, I.THERMAL_STATES)
            _number("Potência inicial (kW)", prefix, "power_kW", state)
        else:
            st.caption("Fonte não despachável: a produção depende das condições ambientais (Previsões, Piso 2B). "
                       "Aqui registra-se apenas a disponibilidade técnica.")
        fs = I.validate_state(eq_id, k, state, ref)
        if fs:
            st.html(_findings_html(fs))


def _initialization(store, cur) -> None:
    ss = _ss()
    if st.button("← Centro de Operação", key="op_back"):
        shell.go("operacao")
        st.rerun()
    if cur is None or work() is None:
        st.info("Nenhum cenário selecionado. Crie ou selecione um cenário no Centro de Operação.")
        return
    doc = work()
    saved = session.saved()
    d = S.drift(doc, saved.config, saved.revision)
    shell.hero("Inicialização · estados iniciais", doc["name"],
               "Condições do instante inicial do experimento, por equipamento do inventário de referência. Não altera a "
               "configuração física permanente da microrrede.",
               [("Cenário", f"v{cur.version}" + (" · alterações não salvas" if is_dirty() else "")),
                ("Inventário de referência", f"rev. {doc['inventory_ref']['config_revision']}"),
                ("Microrrede", saved.config["installation"]["name"])])
    if d.stale:
        changes = "; ".join(d.describe(doc, saved.config)[:6])
        shell.callout(f"<b>O inventário mudou</b> desde a revisão {d.base_revision} usada por este cenário (atual: "
                      f"{d.current_revision}): {escape(changes)}. Os controles abaixo refletem a revisão de referência; "
                      "atualize a referência no Centro de Operação para incluir as mudanças.", "warn")
    st.html('<div class="op-legend">'
            '<span><b style="color:#C2364A">✕ Erro de coerência</b> — dados contraditórios; impede salvar</span>'
            '<span><b style="color:#C77700">! Advertência técnica</b> — permitido</span>'
            '<span><b style="color:#2F6FED">◷ Capacidade científica pendente</b> — registrado, ainda não interpretado pelo EMS V1.6</span>'
            '</div>')
    refs = doc["inventory_ref"]["equipment"]
    states = doc["initialization"]["equipment"]
    token = int(ss.get("op_token") or 0)
    enabled = sorted(((eid, r) for eid, r in refs.items() if r.get("enabled", True)),
                     key=lambda it: (it[1].get("position", 1 << 30), it[1].get("name", "")))
    if not enabled:
        st.info("O inventário de referência não tem equipamentos habilitados.")
    for kind in KIND_ORDER:
        group = [(eid, r) for eid, r in enabled if r["kind"] == kind]
        if not group:
            continue
        st.markdown(f'<div class="sd-section">{escape(KIND_SECTION[kind])}</div>', unsafe_allow_html=True)
        cols = st.columns(2, gap="medium")
        for i, (eid, r) in enumerate(group):
            states.setdefault(eid, I.default_state(kind))
            with cols[i % 2]:
                _equipment_card(eid, r, states[eid], token)
    disabled = [r["name"] for r in refs.values() if not r.get("enabled", True)]
    if disabled:
        st.caption("Desabilitados no inventário (não entram na operação; sem estado inicial): " + shell.md(", ".join(disabled)))
    orphans = doc["initialization"].get("orphaned") or {}
    if orphans:
        with st.expander(f"Estados preservados de equipamentos retirados ({len(orphans)})"):
            for eid, o in orphans.items():
                nm = (o.get("reference") or {}).get("name") or eid
                st.markdown(f"- **{shell.md(nm)}** — retirado na revisão {o.get('orphaned_at_revision')}; estado preservado, "
                            "não aplicado.")
    fs = S.findings(doc)
    glob = [f for f in fs if f.eq_id is None]
    if glob:
        st.html(_findings_html(glob))
    s = I.summarize(fs)
    shell.kpis([("Erros de coerência", str(s[I.ERROR]), "impedem salvar"),
                ("Advertências", str(s[I.WARNING]), "permitidas"),
                ("Pendências do EMS", str(s[I.PENDING]), "registradas, não interpretadas"),
                ("Não definidos", str(s[I.INCOMPLETE]), "prontidão do cenário")])
    _save_bar(store, cur, s)


def _save_bar(store, cur, counts: dict) -> None:
    ss = _ss()
    if ss.get("op_stale"):
        shell.callout(f"Outra sessão salvou a versão {ss['op_stale']} deste cenário. Salvar acusará conflito: recarregue "
                      "a versão salva (suas alterações desta sessão serão descartadas) ou copie seus valores antes.", "warn")
    c1, c2, c3 = st.columns([1.4, 1.4, 3], vertical_alignment="center")
    dirty = is_dirty()
    if c1.button("SALVAR CENÁRIO", key="op_save", type="primary", width="stretch", disabled=not dirty):
        try:
            res = service.save(store, work(), int(ss["op_base_version"]), new_blobs=ss.get("op_blobs"))
        except ScenarioConflictError as exc:
            ss["op_conflict"] = str(exc)
            st.rerun()
        except S.ScenarioValidationError as exc:
            ss["op_error"] = "Nada foi gravado. " + str(exc)
            st.rerun()
        except StoreError as exc:
            ss["op_error"] = str(exc)
            st.rerun()
        _adopt(res)
        _flash("ok", f"Cenário salvo (versão {res.version}).")
        st.rerun()
    if c2.button("DESCARTAR ALTERAÇÕES", key="op_discard", width="stretch", disabled=not dirty and not ss.get("op_conflict")):
        _adopt(store.get_scenario(cur.scenario_uid))
        _flash("info", "Alterações descartadas; versão salva recarregada.")
        st.rerun()
    if counts[I.ERROR]:
        c3.caption("Há erros de coerência: corrija-os para poder salvar.")
    elif dirty:
        c3.caption("Alterações não salvas neste cenário (apenas nesta sessão).")
    else:
        c3.caption(f"Sem alterações pendentes · versão salva {cur.version}.")


# ======================================================================= entrada
def render() -> None:
    ss = _ss()
    store = session.store()
    st.html(OP_CSS)
    items, cur = sync(store)
    flash = ss.pop("op_flash", None)
    if flash:
        {"ok": st.success, "info": st.info, "warn": st.warning}.get(flash[0], st.info)(flash[1])
    if ss.get("op_conflict"):
        st.error(ss["op_conflict"])
        if st.button("Recarregar versão salva (descarta as alterações desta sessão)", key="op_reload"):
            _adopt(store.get_scenario(ss[SCN]))
            st.rerun()
    if ss.get("op_error"):
        st.error(shell.md(ss.pop("op_error")))
    tab = shell.route().get("tab")
    etapas = {TAB_INIT: _initialization, TAB_FC: forecasts_ui.render, TAB_SG: execution_ui.render_strategy,
              TAB_EX: execution_ui.render_execution}
    if tab in etapas:                                   # Piso 3D-B2-D: Folha de Ensaio em três colunas em volta da etapa
        folha_ui.render(store, cur, work, tab, is_dirty=is_dirty, corpo=lambda: etapas[tab](store, cur))
    elif tab == TAB_RUN:
        execution_ui.render_run(store, cur)
    elif tab in (TAB_AR, TAB_STUDY):
        archive_ui.render(store, base_view="operacao")
    elif tab == planta_ui.TAB:                          # Piso 3D-B2-B: Planta (barramento equivalente)
        planta_ui.render(store, cur)
    elif tab == caderno_ui.TAB:                         # Piso 3D-B2-C: Caderno de Ensaios (cenários, rodadas, estudos)
        caderno_ui.render(store, cur)
    else:
        _panel(store, items, cur)


__all__ = ["render", "sync", "work", "is_dirty"]
