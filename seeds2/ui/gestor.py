"""GESTOR DE MICRORREDES — página inicial do SEEDS2.

Lista as microrredes do catálogo (cada uma com armazenamento próprio) e permite: criar (comissionamento),
abrir, exportar ZIP, gerar relatório PDF, importar backups (nova / restaurar / cópia independente) e excluir
definitivamente (com confirmação por nome e proteção administrativa). Exportação e relatório consultam
DIRETAMENTE o armazenamento da microrrede escolhida, sem abri-la nesta sessão.
"""
from __future__ import annotations

import json
import os
from html import escape

import streamlit as st

from seeds2.microgrid import config as C
from seeds2.microgrid.admin import SECRET_KEY, deletion_policy
from seeds2.microgrid.references import KIND_LABELS
from seeds2.microgrid.registry import (EMS_LABELS, ORIGIN_LABELS, STATE_LABELS, MicrogridNotFound, RegistryError,
                                       card_summary)
from seeds2.microgrid.store import StoreError, backup_filename

from . import forms, session, shell

DLG = "gestor_dlg"
GESTOR_CSS = """
<style>
.gs-hero { position: relative; overflow: hidden; border-radius: 18px; padding: 1.5rem 1.6rem 1.35rem; margin: .4rem 0 1rem 0;
  border: 1px solid color-mix(in srgb, var(--primary-color, #0E7C86) 25%, rgba(128,128,128,.25));
  background: radial-gradient(120% 140% at 100% 0%, color-mix(in srgb, var(--primary-color, #0E7C86) 16%, transparent) 0%, transparent 55%),
              linear-gradient(120deg, color-mix(in srgb, var(--primary-color, #0E7C86) 8%, transparent), transparent 70%);
  animation: sdfade .25s ease both; }
.gs-hero::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--primary-color, #0E7C86); }
.gs-hero h1 { margin: .3rem 0 .25rem 0; font-size: clamp(1.6rem, 1.15rem + 1.6vw, 2.35rem); letter-spacing: .02em; font-weight: 800; line-height: 1.08; }
.gs-hero p { margin: 0; font-size: 1.04rem; opacity: .8; max-width: 760px; }
.gs-hero .facts { display: flex; flex-wrap: wrap; gap: .4rem .5rem; margin-top: .8rem; }
.st-key-gestor_actions button { min-height: 2.75rem; padding-left: 1.3rem; padding-right: 1.3rem; font-weight: 650; letter-spacing: .03em; }
.st-key-gestor_grid { display: grid !important; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 1rem !important; align-items: stretch; }
.st-key-gestor_grid > div { width: auto !important; min-width: 0; }
[class*="st-key-mgc_"] { border-radius: 16px !important; height: 100%; transition: box-shadow .18s, transform .18s; animation: sdfade .28s ease both;
  border-color: color-mix(in srgb, var(--primary-color, #0E7C86) 18%, rgba(128,128,128,.28)) !important; }
[class*="st-key-mgc_"]:hover { box-shadow: 0 10px 28px rgba(14,124,134,.10); transform: translateY(-1px); }
@media (prefers-reduced-motion: reduce) { [class*="st-key-mgc_"], .gs-hero { animation: none; transition: none; } }
.gc-top { display: flex; flex-wrap: wrap; gap: .35rem; align-items: center; margin-bottom: .45rem; }
.gc-chip { display: inline-flex; align-items: center; gap: .35rem; font-size: .7rem; font-weight: 750; letter-spacing: .06em; text-transform: uppercase;
  padding: .18rem .55rem; border-radius: 999px; border: 1px solid currentColor; }
.gc-chip::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.gc-chip.s-ativa { color: #2E8B57; } .gc-chip.s-configuracao { color: #2F6FED; } .gc-chip.s-atencao { color: #C77700; } .gc-chip.s-erro { color: #C2364A; }
.gc-chip.e-pronta { color: var(--primary-color, #0E7C86); } .gc-chip.e-parcial { color: #8A6D00; } .gc-chip.e-bloqueada { color: #5B6B7C; }
.gc-name { font-size: 1.22rem; font-weight: 760; letter-spacing: -.01em; line-height: 1.2; margin: .1rem 0 .1rem 0; overflow-wrap: anywhere; }
.gc-uid { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .74rem; opacity: .62; }
.gc-desc { font-size: .88rem; opacity: .8; margin: .45rem 0 .35rem 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.6em; }
.gc-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .4rem .7rem; margin: .5rem 0; }
.gc-facts small { display: block; font-size: .64rem; font-weight: 750; letter-spacing: .09em; text-transform: uppercase; opacity: .6; }
.gc-facts span { font-size: .84rem; overflow-wrap: anywhere; }
.gc-techs { display: flex; flex-wrap: wrap; gap: .3rem; margin: .45rem 0 .55rem 0; }
.gc-tech { font-size: .72rem; padding: .12rem .5rem; border-radius: .45rem; background: color-mix(in srgb, var(--primary-color, #0E7C86) 10%, transparent); }
.gc-kpis { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; margin: .3rem 0 .55rem 0; }
.gc-kpi { border: 1px solid rgba(128,128,128,.22); border-radius: 11px; padding: .5rem .6rem; background: color-mix(in srgb, var(--primary-color, #0E7C86) 6%, transparent); }
.gc-kpi small { display: block; font-size: .63rem; font-weight: 750; letter-spacing: .09em; text-transform: uppercase; opacity: .65; }
.gc-kpi b { display: block; font-size: 1.08rem; font-weight: 760; font-variant-numeric: tabular-nums; margin: .1rem 0 0 0; }
.gc-kpi span { font-size: .7rem; opacity: .68; }
.gc-foot { font-size: .76rem; opacity: .7; margin-top: .2rem; }
.gc-warn { font-size: .78rem; color: #A35F00; margin-top: .3rem; }
.gs-empty { text-align: center; padding: 2.4rem 1.2rem 2rem; border-radius: 18px; border: 1.5px dashed color-mix(in srgb, var(--primary-color, #0E7C86) 35%, transparent);
  background: color-mix(in srgb, var(--primary-color, #0E7C86) 4%, transparent); animation: sdfade .3s ease both; }
.gs-empty svg { width: 92px; height: 92px; color: var(--primary-color, #0E7C86); opacity: .9; }
.gs-empty h3 { margin: .7rem 0 .3rem 0; font-size: 1.25rem; }
.gs-empty p { margin: 0 auto; max-width: 560px; opacity: .78; }
.st-key-gd_do button { background: #C2364A !important; border-color: #C2364A !important; color: #fff !important; }
.st-key-gd_do button:disabled { opacity: .45; }
.gs-del { border-left: 3px solid #C2364A; background: color-mix(in srgb, #C2364A 7%, transparent); border-radius: 0 10px 10px 0; padding: .7rem .85rem; margin: .2rem 0 .7rem 0; }
.gs-del table { border-collapse: collapse; font-size: .88rem; } .gs-del td { padding: .1rem .9rem .1rem 0; vertical-align: top; }
.gs-sum { border: 1px solid rgba(128,128,128,.25); border-radius: 12px; padding: .7rem .85rem; margin: .3rem 0 .6rem 0; }
.gs-sum table { border-collapse: collapse; font-size: .86rem; } .gs-sum td { padding: .1rem .9rem .1rem 0; vertical-align: top; }
@media (max-width: 720px) { .gc-facts { grid-template-columns: 1fr 1fr; } .gs-hero { padding: 1.1rem 1.1rem 1rem; } }
</style>
"""
EMPTY_SVG = """<svg viewBox="0 0 96 96" aria-hidden="true"><rect x="8" y="14" width="80" height="68" rx="16" fill="currentColor" opacity=".08"/>
<path d="M22 58h52" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
<path d="M30 58V40M48 58V32M66 58V44" stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity=".7"/>
<circle cx="30" cy="37" r="4.5" fill="currentColor"/><circle cx="48" cy="29" r="4.5" fill="currentColor"/><circle cx="66" cy="41" r="4.5" fill="currentColor"/>
<path d="M48 66v9M43.5 70.5h9" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>"""
BASIS_LABELS = {"declarada": "declarada (datasheet)", "derivada": "estimada do datasheet", "modelo": "parametrização do modelo"}


def _ss():
    return st.session_state


def policy():
    def secret():
        return st.secrets.get(SECRET_KEY)
    return deletion_policy(os.environ, secret)


def _flash() -> None:
    f = _ss().pop("mg_flash", None)
    if f:
        tone, msg = f
        {"ok": st.success, "warn": st.warning, "bad": st.error}.get(tone, st.info)(shell.md(msg))


# --------------------------------------------------------------------------- tarjetas
def _pv_text(s: dict) -> tuple[str, str]:
    if s["pv_kWp"] is None:
        return "—", "sem FV registrada" if "Solar fotovoltaica" not in s["technologies"] else "sem potência calculável"
    comp, decl = s["pv_computed_kWp"], s["pv_declared_kWp"]
    if comp and decl:
        note = f"calculada {forms.fmt(comp, 2)} + declarada {forms.fmt(decl, 2)}"
    else:
        note = "calculada (datasheet, STC)" if comp else "declarada pela instalação"
    return forms.fmt(s["pv_kWp"], 2, "kWp"), note


def _card_html(entry, s: dict) -> str:
    state = s["state"]
    ems_key, ems_detail = s["ems"]
    step = s["commissioning_step"]
    pv_val, pv_note = _pv_text(s)
    wind = (forms.fmt(s["wind_kW"], 0, "kW"), "nominal do catálogo × quantidade") if s["wind_kW"] is not None else ("—", "sem eólica")
    storage = ((forms.fmt(s["storage_kWh"], 1, "kWh"), " + ".join(BASIS_LABELS[b] for b in s["storage_basis"]))
               if s["storage_kWh"] is not None else ("—", "sem armazenamento registrado"))
    techs = "".join(f'<span class="gc-tech">{escape(t)}</span>' for t in s["technologies"]) or \
        '<span class="gc-tech">nenhum equipamento</span>'
    facts = "".join(f"<div><small>{escape(k)}</small><span>{escape(v or 'não declarado')}</span></div>"
                    for k, v in (("Natureza", s["nature"]), ("Modo declarado", s["operation_mode"]), ("Localização", s["location"])))
    kpis = "".join(f'<div class="gc-kpi"><small>{escape(k)}</small><b>{escape(v)}</b><span>{escape(n)}</span></div>'
                   for k, v, n in (("FV instalada", pv_val, pv_note), ("Eólica instalada", *wind),
                                   ("Armazenamento", *storage),
                                   ("Equipamentos", str(s["n_equipment"]), f"{len(s['technologies'])} tecnologia(s)")))
    comm = "Comissionamento concluído" if s["commissioned"] else f"Comissionamento em andamento · etapa {step:02d} de 05"
    origin = ORIGIN_LABELS.get(entry.origin, entry.origin)
    copied = s.get("copied_from") or {}
    origin_txt = origin + (f" (origem {copied.get('uid', '')[:8]}…)" if copied else "")
    warn = "".join(f'<div class="gc-warn">! {escape(a)}</div>' for a in s["attention"])
    return (f'<div class="gc"><div class="gc-top"><span class="gc-chip s-{escape(state)}">{escape(STATE_LABELS[state])}</span>'
            f'<span class="gc-chip e-{escape(ems_key)}" title="{escape(ems_detail)}">{escape(EMS_LABELS[ems_key])}</span></div>'
            f'<div class="gc-name">{escape(s["name"] or "Sem nome")}</div>'
            f'<div class="gc-uid" title="Identificador interno imutável">ID {escape(entry.uid)}</div>'
            f'<div class="gc-desc">{escape(s["description"] or "Sem descrição.")}</div>'
            f'<div class="gc-facts">{facts}</div><div class="gc-techs">{techs}</div><div class="gc-kpis">{kpis}</div>'
            f'<div class="gc-foot">{escape(comm)} · alterada {escape(shell.fmt_time(s["saved_at"]))} · rev. {s["revision"]} · '
            f'{escape(origin_txt)}</div>'
            f'<div class="gc-foot">EMS: {escape(ems_detail if len(ems_detail) <= 150 else ems_detail[:149].rstrip() + "…")}</div>'
            f'{warn}</div>')


def _summaries(reg) -> list[tuple]:
    out = []
    for e in reg.entries():
        try:
            stored = reg.open(e.uid).load()
            out.append((e, card_summary(stored), None))
        except (MicrogridNotFound, StoreError) as exc:
            out.append((e, None, str(exc)))
    out.sort(key=lambda t: (t[1] or {}).get("saved_at") or "", reverse=True)
    return out


def _prepare_zip(reg, uid: str) -> None:
    store = reg.open(uid)
    cur = store.load()
    _ss().setdefault("gestor_zip", {})[uid] = (cur.fingerprint, backup_filename(cur.config), store.export_backup())


def _prepare_pdf(reg, uid: str) -> None:
    from seeds2.report.pdf import build_report, report_filename

    store = reg.open(uid)
    cur = store.load()
    _ss().setdefault("gestor_pdf", {})[uid] = (cur.fingerprint, report_filename(cur.config), build_report(cur, store))


def _card(reg, entry, s: dict | None, error: str | None) -> None:
    uid = entry.uid
    with st.container(border=True, key=f"mgc_{uid}"):
        if s is None:
            st.html(f'<div class="gc"><div class="gc-top"><span class="gc-chip s-erro">Armazenamento indisponível</span></div>'
                    f'<div class="gc-uid">ID {escape(uid)}</div><div class="gc-desc">{escape(error or "")}</div></div>')
            if st.button("EXCLUIR MICRORREDE", key=f"g_del_{uid}", icon=":material/delete:", width="stretch"):
                _ss()[DLG] = {"type": "delete", "uid": uid, "incarnation": entry.incarnation}
                st.rerun()
            return
        st.html(_card_html(entry, s))
        if st.button("ABRIR MICRORREDE", key=f"g_open_{uid}", type="primary", width="stretch",
                     icon=":material/arrow_forward:"):
            try:
                commissioned = session.open_microgrid(uid)
            except MicrogridNotFound as exc:
                _ss()["mg_flash"] = ("warn", str(exc))
            else:
                shell.go("operacao" if commissioned else "comissionamento")
            st.rerun()
        c1, c2, c3 = st.columns(3)
        if c1.button("ZIP", key=f"g_zip_{uid}", icon=":material/download:", width="stretch",
                     help="EXPORTAR ZIP — backup .seeds2backup.zip desta microrrede (somente os dados dela; NÃO inclui "
                          "os cenários operativos do Piso 2A)"):
            try:
                with st.spinner("Preparando ZIP…"):
                    _prepare_zip(reg, uid)
            except StoreError as exc:
                st.error(shell.md(exc))
        if c2.button("PDF", key=f"g_pdf_{uid}", icon=":material/picture_as_pdf:", width="stretch",
                     help="GERAR RELATÓRIO PDF — relatório técnico da configuração salva (PRELIMINAR se não ativada)"):
            try:
                with st.spinner("Gerando relatório técnico…"):
                    _prepare_pdf(reg, uid)
            except StoreError as exc:
                st.error(shell.md(exc))
        if c3.button("Excluir", key=f"g_del_{uid}", icon=":material/delete:", width="stretch",
                     help="EXCLUIR MICRORREDE — exclusão definitiva com confirmação"):
            _ss()[DLG] = {"type": "delete", "uid": uid, "incarnation": entry.incarnation}   # H-02: vínculo
            st.rerun()
        for kind, label, mime in (("zip", "⬇ Baixar ZIP", "application/zip"), ("pdf", "⬇ Baixar relatório PDF", "application/pdf")):
            ready = _ss().get(f"gestor_{kind}", {}).get(uid)
            if ready and ready[0] == s["fingerprint"]:
                st.download_button(label, ready[2], file_name=ready[1], mime=mime, key=f"g_{kind}dl_{uid}",
                                   width="stretch", type="secondary")
                st.caption(f"{shell.md(ready[1])} · revisão {s['revision']}"
                           + (" · não inclui cenários operativos" if kind == "zip" else ""))


# --------------------------------------------------------------------------- diálogos
def _close_dialog() -> None:
    _ss().pop(DLG, None)


@st.dialog("Excluir microrrede", width="large", on_dismiss=_close_dialog)
def _delete_dialog() -> None:
    reg = session.registry()
    uid = (_ss().get(DLG) or {}).get("uid")
    bound = (_ss().get(DLG) or {}).get("incarnation")         # incarnação que o usuário via ao pedir a exclusão
    current = reg.get(uid)
    if current is not None and bound is not None and current.incarnation != bound:
        st.warning("Esta microrrede foi substituída por outra com o mesmo identificador (excluída e reimportada em "
                   "outra sessão). Nada será excluído; feche e confira o Gestor.")
        if st.button("Fechar", key="gd_close_stale"):
            _close_dialog()
            st.rerun()
        return
    if not reg.exists(uid):
        st.info("Esta microrrede não existe mais no catálogo.")
        if st.button("Fechar", key="gd_close"):
            _close_dialog()
            st.rerun()
        return
    try:
        store = reg.open(uid)
        cur = store.load()
        n_rev, n_runs = len(store.history(limit=100_000)), len(store.runs(limit=100_000))
        n_scn = len(store.list_scenarios())
    except StoreError:
        store, cur, n_rev, n_runs, n_scn = None, None, 0, 0, 0
    name = (cur.config["installation"].get("name") if cur else "") or ""
    n_eq = len(cur.config.get("equipment", [])) if cur else 0
    st.html(f'<div class="gs-del"><b>Exclusão definitiva</b><table>'
            f'<tr><td>Microrrede</td><td><b>{escape(name or "(sem nome)")}</b></td></tr>'
            f'<tr><td>Identificador</td><td class="sd-mono">{escape(uid)}</td></tr>'
            f'<tr><td>Equipamentos</td><td>{n_eq}</td></tr><tr><td>Revisões no histórico</td><td>{n_rev}</td></tr>'
            f'<tr><td>Rodadas registradas</td><td>{n_runs}</td></tr>'
            f'<tr><td>Cenários operativos (Piso 2A)</td><td><b>{n_scn}</b></td></tr></table></div>')
    st.markdown("Serão excluídos **definitivamente** a configuração, o inventário, os dados importados (CSV e dispositivos "
                "PEMFC), o histórico de revisões, as rodadas e simulações registradas, os cenários operativos e as cópias "
                "internas desta microrrede. "
                "As demais microrredes, os modelos científicos e as referências técnicas não são afetados. **Esta ação não "
                "pode ser desfeita pela interface.**")
    if store is not None and cur is not None:
        if st.button("Preparar ZIP antes de excluir", key="gd_zip", icon=":material/download:"):
            _prepare_zip(reg, uid)
        ready = _ss().get("gestor_zip", {}).get(uid)
        if ready and ready[0] == cur.fingerprint:
            st.download_button("⬇ Baixar ZIP desta microrrede", ready[2], file_name=ready[1], mime="application/zip",
                               key="gd_zipdl")
        st.caption(shell.BACKUP_SCOPE)
    pol = policy()
    if not pol.allowed:
        st.warning(pol.describe())
        if st.button("CANCELAR", key="gd_cancel_off"):
            _close_dialog()
            st.rerun()
        return
    if pol.mode == "dev":
        st.caption(pol.describe())
    typed = st.text_input("Digite o nome exato da microrrede para confirmar", key=f"gd_name_{uid}",
                          placeholder=name or uid)
    cred = st.text_input("Credencial administrativa", type="password", key=f"gd_cred_{uid}") if pol.needs_credential else None
    expected = name.strip() or uid
    match = typed.strip() == expected
    # Consentimento ESPECÍFICO para os cenários (o ZIP atual não os contém): além da confirmação genérica por nome.
    scn_ok = True
    if n_scn:
        st.error(f"Esta microrrede tem **{n_scn} cenário(s) operativo(s)**. Eles serão excluídos definitivamente e **não "
                 "podem ser recuperados pelo ZIP atual** (o backup não inclui cenários).")
        scn_ok = st.checkbox(f"Entendo que os {n_scn} cenário(s) operativo(s) desta microrrede serão excluídos e que o ZIP "
                             "atual não permite recuperá-los", key=f"gd_scn_{uid}_{n_scn}")
    c1, c2 = st.columns(2)
    if c1.button("CANCELAR", key="gd_cancel", width="stretch"):
        _close_dialog()
        st.rerun()
    if c2.button("EXCLUIR DEFINITIVAMENTE", key="gd_do", type="primary", width="stretch",
                 disabled=not match or not scn_ok or (pol.needs_credential and not cred)):
        if not pol.check(cred):
            st.error("Credencial administrativa inválida. Nada foi excluído.")
            return
        try:                                            # recontagem no clique: cenários criados por outra sessão
            now_scn = len(reg.open(uid).list_scenarios())
        except StoreError:
            now_scn = n_scn
        if not scn_ok or now_scn > n_scn:
            st.error(f"A microrrede tem agora {now_scn} cenário(s) operativo(s) (outra sessão criou cenários). Confirme "
                     "novamente a exclusão dos cenários. Nada foi excluído.")
            return
        try:
            reg.delete(uid, expected_incarnation=bound)
        except (RegistryError, StoreError) as exc:
            st.error(shell.md(exc))
            return
        for k in ("gestor_zip", "gestor_pdf"):
            _ss().get(k, {}).pop(uid, None)
        _ss()["mg_flash"] = ("ok", f"Microrrede «{name or uid}» excluída definitivamente. As demais microrredes não foram alteradas.")
        _close_dialog()
        st.rerun()


def _summary_table(cfg: dict, rep) -> str:
    m = rep.manifest
    eqs = cfg.get("equipment", [])
    counts = {}
    for e in eqs:
        counts[KIND_LABELS.get(e.get("kind"), e.get("kind"))] = counts.get(KIND_LABELS.get(e.get("kind"), e.get("kind")), 0) + 1
    inst = cfg["installation"]
    rows = [("Microrrede", inst.get("name") or "(sem nome)"), ("Identificador", inst["uid"]),
            ("Natureza", C.NATURE_OPTIONS.get(inst.get("nature"), "não declarada")),
            ("Inventário", ", ".join(f"{k}: {v}" for k, v in counts.items()) or "nenhum equipamento"),
            ("Arranjos FV", str(sum(len(e.get("arrays") or []) for e in eqs if e.get("kind") == "pv"))),
            ("Dados de entrada", f"{len(rep.blobs)} arquivo(s) (CSV / dispositivos PEMFC)"),
            ("Revisão de origem", f"{m.get('revision')} · {str(m.get('fingerprint'))[:16]}…"),
            ("Formato", f"backup v{m.get('format_version')} · documento v{m.get('doc_schema_version')} · SEEDS2 {m.get('app_version')}"),
            ("Gerado em", shell.fmt_time(m.get("created_at"))),
            ("Comissionamento", "concluído" if cfg.get("commissioning", {}).get("completed") else "em andamento")]
    body = "".join(f"<tr><td>{escape(k)}</td><td><b>{escape(str(v))}</b></td></tr>" for k, v in rows)
    return f'<div class="gs-sum"><table>{body}</table></div>'


@st.dialog("Importar microrrede (ZIP)", width="large", on_dismiss=_close_dialog)
def _import_dialog() -> None:
    reg = session.registry()
    st.caption("Selecione um backup .seeds2backup.zip exportado pelo SEEDS2 (formatos 1 e 2). O arquivo é verificado "
               "(estrutura, hashes SHA-256, versões) antes de qualquer gravação.")
    st.caption(shell.RESTORE_SCOPE)
    up = st.file_uploader("Backup .seeds2backup.zip", type=["zip"], key="gi_up")
    if up is None:
        if st.button("Cancelar", key="gi_cancel0"):
            _close_dialog()
            st.rerun()
        return
    data = up.getvalue()
    rep, existing = reg.inspect(data)
    for e in rep.errors:
        st.error(shell.md(e))
    if not rep.ok:
        if st.button("Fechar", key="gi_close_err"):
            _close_dialog()
            st.rerun()
        return
    cfg = rep.config
    st.success("Backup íntegro e compatível.")
    st.html(_summary_table(cfg, rep))
    for w in rep.warnings:
        st.warning(shell.md(w))

    def done(msg: str) -> None:
        _ss()["mg_flash"] = ("ok", msg)
        _close_dialog()
        st.rerun()

    if existing is None:
        st.info("Esta microrrede não existe no catálogo: será incluída com a MESMA identidade do backup.")
        c1, c2 = st.columns(2)
        if c1.button("Cancelar", key="gi_cancel1", width="stretch"):
            _close_dialog()
            st.rerun()
        if c2.button("IMPORTAR COMO NOVA MICRORREDE", key="gi_new", type="primary", width="stretch"):
            try:
                reg.import_new(data)
            except (RegistryError, StoreError) as exc:
                st.error(shell.md(exc))
            else:
                done(f"Microrrede «{cfg['installation'].get('name')}» importada no catálogo.")
        return
    cur = reg.open(existing.uid).load()
    st.warning(f"Já existe no catálogo uma microrrede com esta identidade: «{shell.md(cur.config['installation'].get('name'))}» "
               f"(revisão atual {cur.revision}). Nada será sobrescrito sem uma escolha explícita.")
    choice = st.radio("Como deseja importar?", ["restaurar", "copia", "cancelar"], key="gi_choice", index=None,
                      format_func={"restaurar": "Restaurar na microrrede existente",
                                   "copia": "Importar como cópia independente",
                                   "cancelar": "Cancelar"}.get)
    if choice == "restaurar":
        st.caption("O conteúdo do backup vira uma NOVA revisão da microrrede existente; o histórico é preservado e é "
                   "possível reverter em Gestão → Relatório, histórico e backups.")
        ok = st.checkbox("Confirmo substituir a configuração atual desta microrrede pelo conteúdo do backup", key="gi_ok")
        if st.button("RESTAURAR", key="gi_restore", type="primary", disabled=not ok):
            try:
                reg.restore_into(existing.uid, data, cur.revision)
            except (RegistryError, StoreError) as exc:
                st.error(shell.md(exc))
            else:
                done(f"Backup restaurado como nova revisão de «{cur.config['installation'].get('name')}».")
    elif choice == "copia":
        st.caption("Cria uma NOVA microrrede com nova identidade interna; o UID e a impressão digital de origem ficam "
                   "registrados. A cópia não representa a mesma instalação física.")
        if st.button("IMPORTAR CÓPIA", key="gi_copy", type="primary"):
            try:
                new_uid, _ = reg.import_copy(data)
            except (RegistryError, StoreError) as exc:
                st.error(shell.md(exc))
            else:
                done(f"Cópia independente criada (ID {new_uid[:8]}…).")
    elif choice == "cancelar":
        _close_dialog()
        st.rerun()


# --------------------------------------------------------------------------- página
def render() -> None:
    st.html(GESTOR_CSS)
    reg = session.registry()
    items = _summaries(reg)
    n = len(items)
    facts = [("Microrredes", str(n)), ("Armazenamento", str(reg.root))]
    f = "".join(f'<span class="sd-fact"><b>{escape(k)}</b> {escape(v)}</span>' for k, v in facts)
    st.html(f'<div class="gs-hero"><div class="sd-chip-h"><span class="sd-dot"></span>SEEDS2 · catálogo de instalações</div>'
            f'<h1>GESTOR DE MICRORREDES</h1><p>Selecione, registre e gerencie suas instalações energéticas.</p>'
            f'<div class="facts">{f}</div></div>')
    _flash()
    with st.container(horizontal=True, gap="small", key="gestor_actions"):
        if st.button("＋ NOVA MICRORREDE", key="g_new", type="primary", width="content"):
            session.begin_new("")
            shell.go("comissionamento")
            st.rerun()
        if st.button("IMPORTAR MICRORREDE (ZIP)", key="g_import", icon=":material/upload:", width="content"):
            _ss()[DLG] = {"type": "import"}
            st.rerun()
    st.write("")
    if not items:
        st.html(f'<div class="gs-empty">{EMPTY_SVG}<h3>Nenhuma microrrede registrada</h3><p>Crie a primeira microrrede '
                '(o comissionamento guia a identificação, o inventário, o balanço energético e a demanda) ou importe um '
                'backup <b>.seeds2backup.zip</b>. Nada é criado automaticamente.</p></div>')
    else:
        with st.container(key="gestor_grid"):
            for entry, s, err in items:
                _card(reg, entry, s, err)
    legacy = reg.meta("legacy_adoption")
    if legacy:
        try:
            info = json.loads(legacy)
        except ValueError:
            info = {}
        if info.get("state") == "done":
            st.caption(f"Armazenamento anterior ao Gestor ({shell.md(info.get('source', ''))}) adotado em "
                       f"{shell.md(shell.fmt_time(info.get('at')))} como a microrrede {shell.md(str(info.get('uid', ''))[:8])}…; "
                       "o arquivo original foi mantido intacto e pode ser removido manualmente após conferência.")
    st.caption(policy().describe())
    dlg = _ss().get(DLG) or {}
    if dlg.get("type") == "delete":
        _delete_dialog()
    elif dlg.get("type") == "import":
        _import_dialog()
