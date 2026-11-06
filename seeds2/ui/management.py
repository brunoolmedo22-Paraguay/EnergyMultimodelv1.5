"""Gestão da Microrrede: manutenção da configuração da ÚNICA instalação (inventário, balanço energético, demanda,
identificação e localização, relatório técnico, histórico de revisões, rodadas registradas, backup e restauração).

As alterações ficam como **edição pendente** (cópia de trabalho) até "Salvar alterações", que grava uma
nova revisão imutável preservando a identidade da instalação. Nunca se cria outra microrrede.
"""
from __future__ import annotations


import pandas as pd
import streamlit as st

from seeds2.microgrid import config as C
from seeds2.microgrid.store import IdentityError, StoreError, backup_filename

from . import exports, forms, session, shell

TABS = {"inventario": "Inventário", "balanco": "Balanço energético", "demanda": "Demanda e dados",
        "instalacao": "Instalação", "historico": "Relatório, histórico e backups"}
TAB_ALIASES = {"topologia": "balanco"}       # links antigos continuam funcionando
ORIGIN_LABELS = {"commissioning": "comissionamento", "edit": "edição", "restore": "restauração", "revert": "reversão",
                 "migration": "migração", "run_conditions": "condições da rodada"}


def _identity(cfg: dict, saved) -> None:
    inst = cfg["installation"]
    shell.hero("Gestão da Microrrede", inst.get("name") or "Microrrede",
               inst.get("description") or "Inventário, balanço energético, parâmetros técnicos e manutenção da configuração desta instalação.",
               [("Natureza", C.NATURE_OPTIONS.get(inst.get("nature"), "não declarada")),
                ("Modo", C.OPERATION_MODE_OPTIONS.get(inst.get("operation_mode"), "não declarado")),
                ("Local", forms.location_text(inst.get("location"))),
                ("Revisão salva", str(saved.revision) if saved else "—"),
                ("Identidade", inst["uid"][:12] + "…")])


def _pending_bar() -> None:
    ss = st.session_state
    if ss.get("mg_notice"):
        st.info(ss.pop("mg_notice"))
    if ss.get("mg_conflict"):
        st.error(shell.md(ss["mg_conflict"]))
        c1, c2 = st.columns([3, 1.4])
        c1.caption("Outra sessão salvou uma revisão mais nova. Para não sobrescrevê-la, recarregue-a (sua edição local será "
                   "descartada) e reaplique as alterações.")
        if c2.button("Recarregar revisão salva", key="mg_reload", width="stretch"):
            session.discard()
            forms.bump()
            st.rerun()
    if ss.get("mg_error"):
        st.error(shell.md(ss["mg_error"]))
    if not session.is_dirty():
        return
    items = session.pending_changes()
    with st.container(border=True, key="mg_pending"):
        c1, c2, c3 = st.columns([3.2, 1, 1], vertical_alignment="center")
        c1.markdown(f"**Edição pendente — {len(items)} alteração(ões) ainda não salva(s)**  \n"
                    + "  \n".join(f"• {shell.md(i)}" for i in items[:12]))
        note = c1.text_input("Nota da revisão (opcional)", key=f"mg_note_{forms.token()}", placeholder="p. ex. substituição do banco de baterias")
        if c2.button("Salvar alterações", key="mg_save", type="primary", width="stretch"):
            if session.save(note=note or "; ".join(items)[:300], origin="edit"):
                forms.bump()
                st.toast("Configuração salva como nova revisão.")
            st.rerun()
        if c3.button("Descartar", key="mg_discard", width="stretch"):
            session.discard()
            forms.bump()
            st.rerun()


def render() -> None:
    saved = session.saved()
    cfg = session.work()
    _identity(cfg, saved)
    _pending_bar()
    r = shell.route()
    tab = TAB_ALIASES.get(r.get("tab"), r.get("tab"))
    tab = tab if tab in TABS else "inventario"
    miss = C.identification_missing(cfg)
    if miss and tab != "instalacao":
        c1, c2 = st.columns([4, 1.2], vertical_alignment="center")
        c1.warning("Identificação incompleta (configuração anterior a esta versão): " + shell.md(", ".join(miss)) +
                   ". O inventário existente é preservado.")
        if c2.button("Completar identificação", key="mg_complete_ident", width="stretch"):
            shell.go("gestao", "instalacao")
            st.rerun()
    sel = st.segmented_control("Seção", list(TABS), default=tab, format_func=TABS.get, key=f"mg_tab_{tab}",
                               label_visibility="collapsed")
    if sel and sel != tab:
        shell.go("gestao", sel)
        st.rerun()
    plan = session.plan(cfg)
    with st.container(key=f"mg_stage_{tab}"):
        st.html('<div class="sd-stage"></div>')
        {"inventario": _inventory, "balanco": _balance, "demanda": _demand, "instalacao": _installation,
         "historico": _history}[tab](cfg, plan)


def _inventory(cfg, plan) -> None:
    forms.inventory(cfg, plan, autosave=False, key="mg_inv")
    st.caption("Alterações no inventário entram como edição pendente; use **Salvar alterações** para gravar uma nova revisão.")


def _balance(cfg, plan) -> None:
    st.caption("Esquema lógico do balanço energético agregado usado pelo EMS. Não é um esquema unifilar: barramentos, "
               "tensões e acoplamentos físicos não são modelados nesta versão.")
    forms.balance_view(cfg, plan, key="mg_bal")
    if forms.grid_form(cfg, key="mg_bal"):
        forms.bump()
        st.rerun()
    forms.grid_notice(cfg)
    legacy = (cfg.get("legacy") or {}).get("topology_v1")
    if legacy:
        with st.expander("Topologia declarada na versão anterior (somente rastreabilidade)"):
            st.caption((cfg.get("legacy") or {}).get("topology_v1_note", ""))
            st.json(legacy, expanded=False)


def _demand(cfg, plan) -> None:
    st.markdown('<div class="sd-section">Demanda de referência da instalação</div>', unsafe_allow_html=True)
    if forms.demand_editor(cfg, key="mg_dem", submit="Aplicar demanda à edição"):
        forms.bump()
        st.rerun()
    st.markdown('<div class="sd-section">Clima para solar/eólica</div>', unsafe_allow_html=True)
    if forms.climate_editor(cfg, key="mg_clim", submit="Aplicar clima à edição"):
        forms.bump()
        st.rerun()


def _installation(cfg, plan) -> None:
    inst = cfg["installation"]
    st.caption(f"Identidade estável da instalação: `{inst['uid']}` · criada {shell.fmt_time(inst.get('created_at'))} · "
               f"comissionada {shell.fmt_time(cfg['commissioning'].get('completed_at'))}. Alterar o nome ou a descrição "
               "não cria outra microrrede.")
    forms.identification_cards(cfg, key="mg_inst")
    _, c2 = st.columns([2, 1])
    if c2.button("Aplicar à edição", key="mg_inst_apply", type="primary", width="stretch"):
        errs = forms.apply_identification(cfg, key="mg_inst")
        if errs:
            for e in errs:
                st.error(shell.md(e))
        else:
            forms.bump()
            st.rerun()
    st.markdown('<div class="sd-section">Armazenamento e acesso</div>', unsafe_allow_html=True)
    s = session.store()
    st.markdown(f"- Banco desta microrrede: `{s.path}` (esquema v{s.db_version()}); catálogo em "
                f"`{session.registry().path}`; diretório-base definido por `SEEDS2_DATA_DIR`.\n"
                "- **Sem autenticação nem perfis de acesso** neste piso: qualquer pessoa com acesso à aplicação pode alterar "
                "a configuração. Para implantação corporativa, restrinja o acesso pela rede/servidor (ver documentação).")


def _history(cfg, plan) -> None:
    s = session.store()
    saved = session.saved()
    st.markdown('<div class="sd-section">Documentação da configuração</div>', unsafe_allow_html=True)
    exports.export_actions(key="mg_exp")
    st.markdown('<div class="sd-section">Revisões da configuração</div>', unsafe_allow_html=True)
    hist = s.history(limit=200)
    if hist:
        st.dataframe(pd.DataFrame([{"Revisão": h["revision"], "Salva em": shell.fmt_time(h["saved_at"]),
                                    "Origem": ORIGIN_LABELS.get(h["origin"], h["origin"]), "Nota": h["note"],
                                    "Impressão digital": h["fingerprint"][:16] + "…"} for h in hist]),
                     hide_index=True, width="stretch", height=min(320, 40 + 35 * len(hist)))
        older = [h["revision"] for h in hist if h["revision"] != saved.revision]
        if older:
            with st.expander("Reverter para o conteúdo de uma revisão anterior"):
                st.caption("Cria uma NOVA revisão com o conteúdo escolhido; o histórico é preservado.")
                c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
                rv = c1.selectbox("Revisão", older, key="mg_rev_sel")
                ok = st.checkbox(f"Confirmo reverter a configuração para o conteúdo da revisão {rv}", key="mg_rev_ok")
                if c2.button("Reverter", key="mg_rev_do", disabled=not ok or session.is_dirty(), width="stretch"):
                    try:
                        s.revert_to(int(rv), saved.revision)
                    except StoreError as exc:
                        st.error(shell.md(exc))
                    else:
                        session.discard()
                        forms.bump()
                        st.rerun()
                if session.is_dirty():
                    st.caption("Salve ou descarte a edição pendente antes de reverter.")
    runs = s.runs(limit=50)
    st.markdown('<div class="sd-section">Rodadas registradas (procedência)</div>', unsafe_allow_html=True)
    if runs:
        st.dataframe(pd.DataFrame([{"Rodada": r["run_id"], "Quando": shell.fmt_time(r["created_at"]),
                                    "Origem": r["spec_origin"], "Revisão": r["config_revision"],
                                    "Config.": (r["config_fingerprint"] or "")[:12], "Excluídos": len(r["excluded"]),
                                    "Custo [R$]": r["summary"].get("custo_total_rs"),
                                    "Não atendida [kWh]": r["summary"].get("energia_nao_atendida_kWh")} for r in runs]),
                     hide_index=True, width="stretch")
    else:
        st.caption("Nenhuma rodada registrada ainda.")
    st.markdown('<div class="sd-section">Backup e restauração</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            st.markdown("**Exportar backup**")
            st.caption("ZIP autossuficiente: configuração, dados de entrada importados (CSV), histórico de revisões e manifesto "
                       "com hashes SHA-256. Não contém credenciais. Guarde-o em local seguro da instalação.")
            st.warning(shell.BACKUP_SCOPE)
            if st.button("Preparar backup da revisão salva", key="mg_bk_prep", width="stretch", disabled=saved is None):
                st.session_state["mg_bk"] = (backup_filename(saved.config), s.export_backup())
            if st.session_state.get("mg_bk"):
                name, data = st.session_state["mg_bk"]
                st.download_button("⬇ Baixar backup", data, file_name=name, mime="application/zip", key="mg_bk_dl",
                                   type="primary", width="stretch")
    with c2:
        with st.container(border=True):
            st.markdown("**Restaurar backup**")
            st.caption(shell.RESTORE_SCOPE)
            up = st.file_uploader("Backup .seeds2backup.zip", type=["zip"], key="mg_bk_up", label_visibility="collapsed")
            if up is not None:
                data = up.getvalue()
                rep = s.inspect_backup(data)
                m = rep.manifest
                if m:
                    st.caption(f"Instalação: **{shell.md(m.get('installation_name', '?'))}** · revisão "
                               f"{shell.md(m.get('revision'))} · gerado em {shell.md(shell.fmt_time(m.get('created_at')))} · "
                               f"SEEDS2 {shell.md(m.get('app_version', '?'))}")
                for e in rep.errors:                     # mensagens podem conter conteúdo do arquivo
                    st.error(shell.md(e))
                for w in rep.warnings:
                    st.warning(shell.md(w))
                if rep.ok and rep.same_installation is False:
                    st.error("Este backup pertence a OUTRA microrrede (identidade "
                             f"{shell.md(rep.config['installation']['uid'])}). Uma microrrede nunca troca de identidade: "
                             "use IMPORTAR MICRORREDE (ZIP) no Gestor de microrredes para incluí-la no catálogo.")
                elif rep.ok:
                    st.success("Backup íntegro e compatível.")
                    ok = st.checkbox("Confirmo substituir a configuração atual pelo conteúdo deste backup (uma nova revisão "
                                     "será criada; o histórico atual é preservado)", key="mg_bk_ok")
                    if st.button("Restaurar", key="mg_bk_do", type="primary", disabled=not ok or session.is_dirty(),
                                 width="stretch"):
                        try:
                            s.restore_backup(data, saved.revision if saved else 0, confirm=True)
                        except (StoreError, IdentityError) as exc:
                            st.error(shell.md(exc))
                        else:
                            session.discard()
                            forms.bump()
                            st.session_state.pop("mg_bk", None)
                            st.toast("Backup restaurado como nova revisão.")
                            st.rerun()
                    if session.is_dirty():
                        st.caption("Salve ou descarte a edição pendente antes de restaurar.")
