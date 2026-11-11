"""ARQUIVO CIENTÍFICO (Piso 2D-A) — exportar, importar e consultar estudos científicos portáteis.

Dois pontos de entrada, o mesmo código:

* **Centro de Operação** da microrrede ativa (``view=operacao``, ``tab=arquivo``): exportar cenários desta microrrede
  (EXPORTAR CENÁRIO COMPLETO / ARQUIVAR NESTA INSTALAÇÃO), importar e consultar estudos;
* **Gestor de microrredes** (``view=arquivo``): importar e consultar estudos SEM abrir nem possuir microrrede alguma
  (instalação nova / diretório de dados vazio).

O estudo aberto (``tab=estudo``, ``?study=<archive_uid>``, rodada ``?srun=``) é uma CONSULTA HISTÓRICA: tudo vem dos
recursos gravados no Arquivo Científico (``seeds2.archive.view.StudyView``). Nada aqui chama ``run_optimizer`` nem
``build_exchange_package`` — não há rota de código da consulta até o motor. Estado de sessão: prefixo ``ar_`` (pequeno:
identificadores e o RELATÓRIO da inspeção; nunca o conteúdo dos pacotes).
"""
from __future__ import annotations

import uuid
from html import escape

import pandas as pd
import streamlit as st

from seeds2.archive import exporter
from seeds2.archive import format as FMT
from seeds2.archive import service as AS
from seeds2.archive.store import ACQUISITIONS, ArchiveError, StudyNotFound, StudyRejected
from seeds2.archive.view import StudyView
from seeds2.microgrid.references import KIND_LABELS
from seeds2.microgrid.store import StoreError
from seeds2.operation import contracts
from seeds2.operation import forecasts as F
from seeds2.operation import strategy as SG

from . import forecast_charts as CH
from . import forms, session, shell

TAB_LIST, TAB_STUDY = "arquivo", "estudo"
STATE_PREFIX = "ar_"
STATE_TONE = {"concluida": "ok", "falhou": "bad", "interrompida": "warn"}
SECTIONS = ("Procedência", "Configuração", "Previsões", "Rodadas e resultados", "Integridade")
AR_CSS = """
<style>
.ar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: .9rem; }
.ar-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .35rem .7rem; margin: .45rem 0; }
.ar-facts small { display: block; font-size: .63rem; font-weight: 750; letter-spacing: .09em; text-transform: uppercase; opacity: .6; }
.ar-facts span { font-size: .84rem; overflow-wrap: anywhere; }
.ar-ro { display: inline-flex; gap: .35rem; align-items: center; font-size: .72rem; font-weight: 750; letter-spacing: .06em;
  text-transform: uppercase; padding: .16rem .55rem; border-radius: 999px; color: #5B6B7C; background: rgba(91,107,124,.14); }
@media (max-width: 760px) { .ar-facts { grid-template-columns: 1fr 1fr; } }
</style>
"""


def _ss():
    return st.session_state


def clear_state() -> None:
    for k in [k for k in list(_ss().keys()) if str(k).startswith(STATE_PREFIX)]:
        _ss().pop(k, None)


def _pill(text: str, tone: str) -> str:
    return f'<span class="op-pill {escape(tone)}">{escape(text)}</span>'


def _size(n: int | None) -> str:
    if n is None:
        return "—"
    for unit, f in (("GiB", 2**30), ("MiB", 2**20), ("KiB", 2**10)):
        if n >= f:
            return f"{forms.fmt(n / f, 1)} {unit}"
    return f"{n} bytes"


def _table(rows: list[tuple[str, object]]) -> str:
    return '<table class="op-tbl">' + "".join(f"<tr><td>{escape(str(a))}</td><td>{escape(str(b))}</td></tr>"
                                              for a, b in rows) + "</table>"


def _states_text(by_state: dict) -> str:
    if not by_state:
        return "nenhuma"
    return ", ".join(f"{n} {contracts.RUN_STATE_LABELS.get(s, s).lower()}" for s, n in sorted(by_state.items()))


def _go_list(base_view: str) -> None:
    _ss().pop(shell.STUDY_KEY, None)
    _ss().pop("ar_run_uid", None)
    shell.go(base_view, TAB_LIST if base_view == "operacao" else None)


def open_study(archive_uid: str, base_view: str) -> None:
    _ss()[shell.STUDY_KEY] = archive_uid
    _ss().pop("ar_run_uid", None)
    _ss().pop("ar_section", None)
    _ss().pop("ar_version", None)
    shell.go(base_view, TAB_STUDY)


def _flash() -> None:
    f = _ss().pop("ar_flash", None)
    if f:
        {"ok": st.success, "warn": st.warning, "bad": st.error}.get(f[0], st.info)(f[1])


# ======================================================================= entrada
def render(store, *, base_view: str) -> None:
    """``store``: armazenamento da microrrede ativa comissionada (exportação disponível) ou ``None`` (Gestor)."""
    from .execution_ui import EX_CSS
    from .operation_center import OP_CSS

    if store is None:                                   # no Gestor o CSS comum do Centro (pílulas, tabelas) não foi aplicado
        st.html(OP_CSS + EX_CSS)
    st.html(AR_CSS)
    try:
        archive = session.archive()
    except StoreError as exc:
        st.error(f"Arquivo Científico indisponível: {shell.md(exc)}")
        return
    if shell.route().get("tab") == TAB_STUDY:
        _study(archive, store, base_view)
    else:
        _home(archive, store, base_view)


def _home(archive, store, base_view: str) -> None:
    if base_view == "operacao":
        if st.button("← Centro de Operação", key="ar_back_oc"):
            shell.go("operacao")
            st.rerun()
    shell.hero("Arquivo Científico", "Estudos científicos portáteis",
               "Exporte um cenário completo (versões, inventário de referência, previsões, rodadas e resultados), guarde-o "
               "fora do SEEDS2 e consulte-o em qualquer instalação — sem executar o EMS novamente.",
               [("Estudos arquivados nesta instalação", str(len(archive.list_studies()))),
                ("Formato", f"{FMT.FORMAT} v{FMT.FORMAT_VERSION}"), ("Extensão", FMT.SUFFIX)])
    _flash()
    shell.callout(shell.STUDY_SCOPE.replace("**", ""), "")
    if store is not None:
        _export_section(archive, store)
    _import_section(archive, store, base_view)
    _list_section(archive, store, base_view)


# ======================================================================= exportação
def _export_section(archive, store) -> None:
    st.markdown('<div class="sd-section">Exportar cenário completo</div>', unsafe_allow_html=True)
    items = store.list_scenarios()
    if not items:
        st.caption("Esta microrrede ainda não tem cenários operativos para exportar.")
        return
    by_uid = {s.scenario_uid: s for s in items}
    opts = [s.scenario_uid for s in items]
    pre = _ss().get(shell.SCENARIO_KEY)
    with st.container(border=True):
        uid = st.selectbox("Cenário desta microrrede", opts, index=opts.index(pre) if pre in opts else len(opts) - 1,
                           format_func=lambda u: f"{by_uid[u].name} · v{by_uid[u].version}", key="ar_exp_pick")
        sc = by_uid[uid]
        runs = store.list_runs(uid, limit=100_000)
        by_state: dict[str, int] = {}
        for r in runs:
            by_state[r.state] = by_state.get(r.state, 0) + 1
        busy = by_state.get("em_execucao", 0)
        st.html(_table([("Cenário", f"{sc.name} · ID {sc.scenario_uid}"),
                        ("Versões incluídas", f"1 a {sc.version} (todas)"),
                        ("Rodadas incluídas", _states_text({k: v for k, v in by_state.items() if k != "em_execucao"})),
                        ("Inventário de referência", "todas as revisões citadas pelas versões e rodadas")]))
        prev = archive.find_by_origin(uid)
        if prev:
            st.caption(f"Este cenário já tem {len(prev)} estudo(s) no Arquivo Científico desta instalação (exportações "
                       "anteriores ficam preservadas como estão).")
        if busy:
            st.warning(f"Há {busy} rodada(s) deste cenário em execução: aguarde a conclusão para exportar.")
        c1, c2 = st.columns(2)
        prepared = _ss().get("ar_export")
        if c1.button("PREPARAR EXPORTAÇÃO", key="ar_exp_prepare", type="primary", width="stretch", disabled=bool(busy),
                     help="Monta o pacote .seeds2study.zip a partir de um instantâneo do banco desta microrrede."):
            exporter.prune_exports()
            name = FMT.safe_filename(sc.name, uid)
            dest = exporter.export_dir() / f"{uuid.uuid4().hex[:8]}_{name}"
            try:
                res = exporter.export_to_file(store, uid, dest)
            except StoreError as exc:
                st.error(shell.md(exc))
                return
            prepared = {"scenario_uid": uid, "path": str(res.path), "filename": name, "size": res.size,
                        "sha256": res.package_sha256, "content_id": res.content_id,
                        "runs": len(res.manifest["study"]["runs"]), "versions": len(res.manifest["study"]["versions"])}
            _ss()["ar_export"] = prepared
        if c2.button("ARQUIVAR NESTA INSTALAÇÃO", key="ar_exp_local", width="stretch", disabled=bool(busy),
                     help="Guarda o estudo no Arquivo Científico desta instalação (mesma verificação da importação)."):
            inst = (session.saved().config.get("installation") or {}) if session.saved() else {}
            try:
                res = AS.archive_scenario(store, archive, uid, context={"microgrid_uid": inst.get("uid"),
                                                                         "incarnation": store.incarnation,
                                                                         "name": inst.get("name")})
            except StoreError as exc:
                st.error(shell.md(exc))
                return
            _ss()["ar_flash"] = ("ok" if res.created else "warn",
                                 f"Estudo “{res.study.scenario_name}” arquivado nesta instalação." if res.created else
                                 "Este conteúdo já estava no Arquivo Científico (nada foi duplicado).")
            st.rerun()
        if prepared and prepared.get("scenario_uid") == uid:
            from pathlib import Path

            path = Path(prepared["path"])
            if path.is_file():
                st.success(f"Pacote preparado: {prepared['versions']} versão(ões), {prepared['runs']} rodada(s), "
                           f"{_size(prepared['size'])} · SHA-256 {prepared['sha256'][:16]}…")
                st.download_button("⬇ EXPORTAR CENÁRIO COMPLETO", data=lambda p=path: p.read_bytes(),
                                   file_name=prepared["filename"], mime="application/zip", key="ar_exp_dl",
                                   type="primary", icon=":material/download:")
            else:
                _ss().pop("ar_export", None)
        st.caption("O arquivo científico preserva o experimento; não substitui o backup ZIP da microrrede (Gestão da "
                   "Microrrede).")


# ======================================================================= importação
def _upload_token() -> int:
    return int(_ss().get("ar_up_token") or 0)


def _import_section(archive, store, base_view: str) -> None:
    st.markdown('<div class="sd-section">Importar estudo científico</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.caption(f"Selecione um pacote {FMT.SUFFIX}. Ele é verificado antes de qualquer gravação; a importação cria um "
                   "estudo SOMENTE LEITURA, separado de todas as microrredes (nenhum inventário, cenário ou rodada é "
                   "alterado e nada é executado).")
        up = st.file_uploader("Pacote do Arquivo Científico", type=["zip"], key=f"ar_upload_{_upload_token()}")
        if up is None:
            _ss().pop("ar_insp", None)
            return
        cache = _ss().get("ar_insp")
        ident = (up.file_id, up.size)
        if cache is None or cache["ident"] != ident:
            rep = FMT.inspect(up)
            cache = {"ident": ident, "report": rep.as_report()}
            _ss()["ar_insp"] = cache
        rep = cache["report"]
        _inspection_report(rep)
        if not rep["ok"]:
            st.error("Pacote rejeitado: nada será importado. Corrija ou obtenha novamente o arquivo.")
            return
        dups = archive.find_by_content(rep["content_id"])
        related = [s for s in archive.find_by_origin(rep["summary"]["scenario_uid"]) if s.content_id != rep["content_id"]]
        mode = "recognize"
        if dups:
            d0 = dups[0]
            shell.callout(f"<b>Este estudo já está no Arquivo Científico</b> (mesmo conteúdo, importado em "
                          f"{escape(shell.fmt_time(d0.imported_at))}; ID local {escape(d0.archive_uid[:8])}…). Importar "
                          "de novo apenas reconhece o existente; para manter outra cópia identificável, marque a opção "
                          "abaixo.", "warn")
            if st.button("ABRIR ESTUDO EXISTENTE", key="ar_open_dup"):
                open_study(d0.archive_uid, base_view)
                st.rerun()
            if st.checkbox("Importar como OUTRA CÓPIA (novo identificador local; identidades de origem preservadas)",
                           key=f"ar_copy_{_upload_token()}"):
                mode = "copy"
        if related:
            st.info(f"Há {len(related)} estudo(s) do MESMO cenário de origem com outro conteúdo (exportações diferentes). "
                    "Nenhum é sobrescrito: cada um fica identificado pelo seu ID local e pela data de exportação.")
        ok = st.checkbox("Confirmo a importação deste estudo como registro somente leitura (não altera nenhuma microrrede "
                         "e não executa o EMS)", key=f"ar_confirm_{_upload_token()}")
        label = "IMPORTAR OUTRA CÓPIA" if mode == "copy" else ("RECONHECER ESTUDO EXISTENTE" if dups else "CONFIRMAR IMPORTAÇÃO")
        if st.button(label, key="ar_import", type="primary", disabled=not ok):
            ctx = None
            if store is not None and session.saved() is not None:
                inst = session.saved().config.get("installation") or {}
                ctx = {"microgrid_uid": inst.get("uid"), "incarnation": store.incarnation, "name": inst.get("name")}
            try:
                res = archive.import_package(up, on_duplicate=mode, context=ctx, expected_content_id=rep["content_id"])
            except StudyRejected as exc:
                st.error("Pacote rejeitado; nada foi importado: " + shell.md(" | ".join(exc.errors[:4])))
                return
            except StoreError as exc:
                st.error(shell.md(exc))
                return
            _ss()["ar_up_token"] = _upload_token() + 1
            _ss().pop("ar_insp", None)
            s = res.study
            _ss()["ar_flash"] = ("ok" if res.created else "warn",
                                 (f"Estudo “{s.scenario_name}” importado ({s.n_versions} versão(ões), {s.n_runs} rodada(s)); "
                                  f"ID local {s.archive_uid[:8]}…." if res.created else
                                  f"Estudo “{s.scenario_name}” já estava arquivado (ID local {s.archive_uid[:8]}…); nada foi "
                                  "duplicado."))
            st.rerun()


def _inspection_report(rep: dict) -> None:
    s = rep.get("summary") or {}
    if rep["ok"]:
        st.html(shell.check("<b>Verificação concluída</b> — formato reconhecido, versão compatível, todos os recursos com "
                            "SHA-256 e tamanho conferidos, relações entre cenário, versões, inventário, previsões e rodadas "
                            "íntegras.", "ok"))
    for e in rep.get("errors") or []:
        st.html(shell.check(escape(e), "bad"))
    for w in rep.get("warnings") or []:
        st.html(shell.check(escape(w), "warn"))
    if not s:
        return
    rows = [("Cenário de origem", f"{s.get('scenario_name')} · {s.get('scenario_uid')}"),
            ("Microrrede de origem", f"{s.get('microgrid_name')} · {s.get('microgrid_uid')}"),
            ("Versões do cenário", s.get("versions")),
            ("Rodadas", f"{s.get('runs')} ({_states_text(s.get('runs_by_state') or {})})"),
            ("Revisões do inventário", ", ".join(map(str, s.get("inventory_revisions") or []))),
            ("Experimento (rodadas)", f"{shell.fmt_time(s.get('first_run_at')) or '—'} → {shell.fmt_time(s.get('last_run_at')) or '—'}"),
            ("Exportado em", shell.fmt_time(s.get("exported_at"))),
            ("Versão do SEEDS2 que exportou", s.get("exporter_version")),
            ("Formato", f"{FMT.FORMAT} v{s.get('format_version')}"),
            ("Tamanho", f"{_size(s.get('package_bytes'))} compactado · {_size(s.get('uncompressed_bytes'))} de conteúdo · "
                        f"{s.get('resources')} recursos"),
            ("SHA-256 do pacote", rep.get("package_sha256")),
            ("Identidade do conteúdo", rep.get("content_id"))]
    st.html(_table(rows))
    st.caption(FMT.INTEGRITY_NOTE)


# ======================================================================= lista
def _list_section(archive, store, base_view: str) -> None:
    st.markdown('<div class="sd-section">Estudos arquivados nesta instalação</div>', unsafe_allow_html=True)
    studies = list(reversed(archive.list_studies()))
    if not studies:
        st.caption("Nenhum estudo arquivado. Importe um pacote .seeds2study.zip ou arquive um cenário de uma microrrede.")
        return
    active = session.active_uid()
    for s in studies:
        with st.container(border=True, key=f"ar_card_{s.archive_uid}"):
            acq = _pill("Importado" if s.acquisition == "importado" else "Arquivado localmente", "info")
            here = _pill("Origem: esta microrrede", "ok") if active and s.origin_microgrid_uid == active else ""
            copy = _pill("Cópia", "off") if s.copy_of else ""
            ver = _pill("Verificado na importação", "ok") if (s.verification or {}).get("ok") else _pill("Não verificado", "bad")
            st.html(f'<div class="op-row"><div class="op-t">{escape(s.scenario_name)}</div><span class="ar-ro">Somente '
                    f'leitura</span></div><div class="op-row" style="justify-content:flex-start;gap:.4rem">{acq}{ver}{here}'
                    f'{copy}</div><div class="ar-facts">'
                    f'<div><small>Microrrede de origem</small><span>{escape(s.origin_microgrid_name or "—")} · '
                    f'{escape(s.origin_microgrid_uid[:8])}…</span></div>'
                    f'<div><small>Cenário de origem</small><span class="op-m">{escape(s.origin_scenario_uid[:12])}…</span></div>'
                    f'<div><small>Versões · rodadas</small><span>{s.n_versions} · {s.n_runs} ({escape(_states_text(s.runs_by_state))})</span></div>'
                    f'<div><small>Experimento</small><span>{escape(shell.fmt_time(s.last_run_at) or "sem rodadas")}</span></div>'
                    f'<div><small>SEEDS2 (exportação)</small><span>{escape(s.exporter_version)} · {escape(shell.fmt_time(s.exported_at))}</span></div>'
                    f'<div><small>ID local</small><span class="op-m">{escape(s.archive_uid[:8])}… · {escape(shell.fmt_time(s.imported_at))}</span></div>'
                    '</div>')
            if st.button("ABRIR ESTUDO", key=f"ar_open_{s.archive_uid}", width="stretch"):
                open_study(s.archive_uid, base_view)
                st.rerun()


# ======================================================================= estudo (consulta histórica)
def _study(archive, store, base_view: str) -> None:
    ss = _ss()
    if st.button("← Arquivo Científico", key="ar_back_list"):
        _go_list(base_view)
        st.rerun()
    uid = ss.get(shell.STUDY_KEY) or st.query_params.get("study")
    if not uid:
        st.info("Nenhum estudo selecionado.")
        return
    try:
        view = StudyView(archive, uid)
    except StudyNotFound:
        st.error("Este estudo não existe no Arquivo Científico desta instalação.")
        return
    ss[shell.STUDY_KEY] = view.uid
    s, o = view.study, view.origin
    shell.hero("Estudo arquivado · somente leitura", s.scenario_name,
               f"Consulta histórica de um experimento da microrrede «{o.get('microgrid_name') or '—'}». Os resultados são os "
               "ORIGINAIS da rodada gravada na origem — abrir este estudo não executa modelos nem o otimizador, e nada "
               "aqui é atribuído a uma microrrede desta instalação.",
               [("Microrrede de origem", f"{o.get('microgrid_name')} · {s.origin_microgrid_uid[:8]}…"),
                ("Versões", str(s.n_versions)), ("Rodadas", f"{s.n_runs} ({_states_text(s.runs_by_state)})"),
                ("Exportado", f"{shell.fmt_time(s.exported_at)} · SEEDS2 {s.exporter_version}"),
                ("ID local", s.archive_uid)])
    _flash()
    # Recarga da página com ?srun=<rodada>: a seção de rodadas é a inicial (a rodada consultada sobrevive à recarga).
    start = SECTIONS.index("Rodadas e resultados") if (ss.get("ar_run_uid") or st.query_params.get("srun")) else 0
    sec = st.radio("Seção do estudo", SECTIONS, index=start, horizontal=True, key="ar_section",
                   label_visibility="collapsed")
    try:
        if sec == "Procedência":
            _provenance(view)
        elif sec == "Configuração":
            _configuration(view)
        elif sec == "Previsões":
            _forecasts(view)
        elif sec == "Rodadas e resultados":
            _runs(view, base_view)
        else:
            _integrity(view)
    except (ArchiveError, StoreError) as exc:
        st.error(f"Não foi possível ler este estudo: {shell.md(exc)} Nada foi alterado; verifique a integridade.")


def _provenance(view: StudyView) -> None:
    s, o, m = view.study, view.origin, view.manifest
    ex = m.get("exporter") or {}
    sw = ex.get("software") or {}
    st.markdown('<div class="sd-section">Identidade de origem (preservada)</div>', unsafe_allow_html=True)
    st.html(_table([("Microrrede", f"{o.get('microgrid_name')} · {o.get('microgrid_uid')}"),
                    ("Incarnação da microrrede", o.get("microgrid_incarnation") or "não registrada"),
                    ("Cenário", f"{o.get('scenario_name')} · {o.get('scenario_uid')}"),
                    ("Cenário criado / atualizado", f"{o.get('scenario_created_at')} / {o.get('scenario_updated_at')}"),
                    ("Versão atual na exportação", o.get("current_version"))]))
    st.markdown('<div class="sd-section">Exportação e armazenamento local</div>', unsafe_allow_html=True)
    st.html(_table([("Formato", f"{m.get('format')} v{m.get('format_version')}"),
                    ("Exportado em", m.get("created_at")),
                    ("SEEDS2 exportador", f"{ex.get('app')} {ex.get('app_version')} · banco v{ex.get('db_schema_version')}"),
                    ("Software", f"Python {sw.get('python')} · numpy {sw.get('numpy')} · pandas {sw.get('pandas')} · "
                                 f"scipy {sw.get('scipy')}"),
                    ("Código científico (exportador)", f"SHA-256 {str((sw.get('science') or {}).get('sha256'))[:16]}…"),
                    ("ID local (esta instalação)", s.archive_uid),
                    ("Aquisição", ACQUISITIONS.get(s.acquisition, s.acquisition) + (f" · contexto: {s.context_name}" if s.context_name else "")),
                    ("Cópia de", s.copy_of or "—"),
                    ("Importado em", s.imported_at),
                    ("SHA-256 do pacote", s.package_sha256), ("Identidade do conteúdo", s.content_id)]))
    st.caption(FMT.INTEGRITY_NOTE)
    st.markdown('<div class="sd-section">Versões do cenário</div>', unsafe_allow_html=True)
    rows = []
    for v in view.version_numbers():
        mv = view.version_meta(v)
        rows.append({"versão": v, "gravada em": mv.get("saved_at"), "origem": mv.get("origin"), "nota": mv.get("note"),
                     "inventário (rev.)": mv.get("base_revision"), "impressão digital": str(mv.get("fingerprint"))[:16] + "…"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown('<div class="sd-section">Revisões do inventário incluídas</div>', unsafe_allow_html=True)
    rows = []
    for r in view.revision_numbers():
        mr = view.revision_meta(r)
        rows.append({"revisão": r, "gravada em": mr.get("saved_at"), "origem": mr.get("origin"), "nota": mr.get("note"),
                     "impressão digital": str(mr.get("fingerprint"))[:16] + "…"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    with st.expander("Manifesto do pacote (como recebido)"):
        st.json({k: v for k, v in m.items() if k != "resources"}, expanded=False)


def _version_pick(view: StudyView, label: str = "Versão do cenário") -> int:
    vs = view.version_numbers()
    cur = _ss().get("ar_version")
    idx = vs.index(cur) if cur in vs else len(vs) - 1
    v = st.selectbox(label, vs, index=idx, format_func=lambda x: f"v{x}" + (" (última)" if x == vs[-1] else ""),
                     key="ar_version_pick")
    _ss()["ar_version"] = v
    return v


def _configuration(view: StudyView) -> None:
    from .operation_center import _ref_line

    v = _version_pick(view)
    doc = view.version_document(v)
    ref = doc.get("inventory_ref") or {}
    rev = ref.get("config_revision")
    st.markdown(f'<div class="sd-section">Inventário de referência · revisão {escape(str(rev))}</div>', unsafe_allow_html=True)
    try:
        inv = view.revision_document(int(rev))
    except (ArchiveError, TypeError, ValueError):
        inv = {}
    inst = inv.get("installation") or {}
    st.caption(f"Microrrede «{inst.get('name', '—')}» como estava na revisão {rev} (documento original incluído no pacote; "
               "impressão digital conferida na importação).")
    eqs = ref.get("equipment") or {}
    rows = []
    for eid, r in sorted(eqs.items(), key=lambda it: (it[1].get("position", 1 << 30), it[1].get("name", ""))):
        try:
            line = _ref_line(r)
        except Exception:  # noqa: BLE001 — referência de versão antiga: mostrar o que existe
            line = ""
        rows.append({"equipamento": r.get("name"), "tipo": KIND_LABELS.get(r.get("kind"), r.get("kind")),
                     "tag": r.get("tag") or "", "habilitado": "sim" if r.get("enabled", True) else "não",
                     "referência física": line})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown('<div class="sd-section">Estados iniciais</div>', unsafe_allow_html=True)
    states = (doc.get("initialization") or {}).get("equipment") or {}
    rows = []
    for eid, stt in states.items():
        r = eqs.get(eid) or {}
        rows.append({"equipamento": r.get("name") or eid, "disponibilidade": stt.get("availability"),
                     "SOC inicial (%)": stt.get("soc0_pct"), "estado": stt.get("state"),
                     "unidades em operação": stt.get("units_on"), "potência inicial (kW)": stt.get("power_kW")})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.caption("Sem estados iniciais nesta versão.")
    st.markdown('<div class="sd-section">Estratégia EMS</div>', unsafe_allow_html=True)
    if doc.get("engine") is not None or doc.get("milp_mpc") is not None:      # Piso 3D-A: motor V2 experimental
        from integracao_v2 import ui as V2UI

        V2UI.estrategia_arquivada(doc)
    sg = doc.get("ems_strategy")
    if not sg:
        st.caption("Estratégia não definida nesta versão.")
    else:
        econ, eta = sg.get("econ") or {}, sg.get("eta_conv") or {}
        st.html(_table([("Função objetivo", SG.OBJECTIVE_LABEL if sg.get("objective") == SG.OBJECTIVE else sg.get("objective")),
                        ("Algoritmo", SG.ALGORITHMS.get(sg.get("algorithm"), str(sg.get("algorithm")))),
                        ("Horizonte N", sg.get("N")), ("Semente", sg.get("seed")),
                        ("Tolerância do SOC-alvo", sg.get("soc_alvo_tol")),
                        ("Metaheurística penalizada", sg.get("meta_penalizada")),
                        ("Validação dinâmica do H₂", sg.get("validar_h2"))]
                       + [(SG.LABELS.get(f"econ.{k}", k), val) for k, val in econ.items()]
                       + [(SG.LABELS.get(f"eta_conv.{k}", k), val) for k, val in eta.items()]))
    st.markdown('<div class="sd-section">Janela temporal da missão</div>', unsafe_allow_html=True)
    mi = doc.get("mission")
    if not mi:
        st.caption("Janela não definida nesta versão.")
    else:
        st.html(_table([("Início (relógio de parede)", mi.get("start")), ("Fuso", mi.get("timezone") or "não declarado"),
                        ("Duração", f"{mi.get('duration_min')} min · passo 60 s"),
                        ("Declaração de relógio (séries sem fuso)", mi.get("undeclared_clock") or "—")]))
    with st.expander("Documento completo desta versão (JSON original)"):
        st.json(doc, expanded=False)


def _forecasts(view: StudyView) -> None:
    v = _version_pick(view)
    doc = view.version_document(v)
    fc = doc.get("forecasts") or {}
    if not fc:
        st.caption("Esta versão do cenário não tem previsões.")
        return
    titles = {"demand": "Demanda elétrica", "climate": "Clima"}
    order = {"demand": 0, "climate": 1}
    for slot, entry in sorted(fc.items(), key=lambda it: order.get(it[0], 9)):     # demanda antes do clima (como no 2B)
        st.markdown(f'<div class="sd-section">{escape(titles.get(slot, slot))}</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.html(_table([("Origem", f"{entry.get('label')} · "
                                       f"{contracts.FORECAST_SOURCE_TYPES.get(entry.get('source_type'), entry.get('source_type'))}"),
                            ("Procedência", entry.get("provenance")),
                            ("Fuso", f"{entry.get('timezone') or 'não declarado'} ({entry.get('timezone_source')})"),
                            ("Base temporal original", f"{entry.get('t0')} → {entry.get('t_end')} · passo "
                                                       f"{entry.get('step_s')} s · {entry.get('n_points')} pontos"),
                            ("Variáveis", ", ".join(entry.get("variables") or [])),
                            ("Transformações", "; ".join(entry.get("transforms") or []) or "nenhuma"),
                            ("Série normalizada (SHA-256)", entry.get("data")),
                            ("Arquivo original (SHA-256)", entry.get("blob") or "—")]))
            try:
                df = F.load(entry, view.get_blob)
            except F.ForecastDataError as exc:
                st.error(f"Série indisponível neste estudo: {shell.md(exc)}")
                continue
            if slot in ("demand", "climate"):
                fig = CH.figure(slot, df, title=f"{titles[slot]} — perfil do cenário (v{v}, arquivado)",
                                subtitle=f"{entry.get('label', '')} · dados originais do estudo")
                st.plotly_chart(fig, config=CH.CONFIG, key=f"ar_fc_{slot}_{v}", width="stretch")
            c1, c2 = st.columns(2)
            c1.download_button("Série normalizada (CSV)", data=lambda h=entry["data"]: view.get_blob(h),
                               file_name=f"previsao_{slot}_v{v}_normalizada.csv", mime="text/csv",
                               key=f"ar_fc_dl_{slot}_{v}", width="stretch")
            if entry.get("blob"):
                meta = view.blob_meta(entry["blob"])
                c2.download_button("Arquivo original importado", data=lambda h=entry["blob"]: view.get_blob(h),
                                   file_name=f"original_{slot}_v{v}.csv", mime=meta.get("media_type") or "text/csv",
                                   key=f"ar_fc_dlo_{slot}_{v}", width="stretch")
            with st.expander("Parâmetros de origem e mapeamento"):
                st.json({k: entry.get(k) for k in ("source_type", "provenance", "params", "mapping", "timezone",
                                                     "timezone_source", "format_version", "created_at", "quality", "stats")},
                        expanded=False)


def _runs(view: StudyView, base_view: str) -> None:
    from .execution_ui import run_results

    runs = view.list_runs()
    if not runs:
        st.caption("Este estudo não contém rodadas (o cenário foi exportado sem execuções).")
        return
    ss = _ss()
    sel = ss.get("ar_run_uid") or st.query_params.get("srun")
    if sel not in {r.run_uid for r in runs}:
        sel = None
    for r in runs:
        c1, c2 = st.columns([5, 1.1], vertical_alignment="center")
        from .execution_ui import run_cost_text

        cost = run_cost_text(r)
        c1.html(f'<div class="op-row" style="justify-content:flex-start;gap:.6rem">'
                f'{_pill(contracts.RUN_STATE_LABELS.get(r.state, r.state), STATE_TONE.get(r.state, "off"))}'
                f'<span class="op-m">{escape(r.run_uid[:8])}…</span><span>v{r.scenario_version} · '
                f'{escape(shell.fmt_time(r.created_at))}</span><span class="op-m">{escape(cost)}</span></div>')
        if c2.button("Consultar", key=f"ar_run_{r.run_uid}", width="stretch",
                     type="primary" if r.run_uid == sel else "secondary"):
            ss["ar_run_uid"] = r.run_uid
            shell.go(base_view, TAB_STUDY)
            st.rerun()
    if sel is None:
        st.caption("Selecione uma rodada para consultar indicadores, gráficos e procedência originais.")
        return
    run = view.get_run(sel)
    ss["ar_run_uid"] = run.run_uid
    st.markdown(f'<div class="sd-section">Rodada {escape(run.run_uid[:8])}… · versão {run.scenario_version} · '
                f'{escape(contracts.RUN_STATE_LABELS.get(run.state, run.state))}</div>', unsafe_allow_html=True)
    st.caption(f"Executada na origem em {run.created_at} (microrrede {run.microgrid_uid[:8]}…); finalizada "
               f"{run.finished_at or '—'}. Valores lidos do estudo arquivado — não recalculados.")
    run_results(view, run, key=f"ar_run_{run.run_uid[:8]}")


def _integrity(view: StudyView) -> None:
    s = view.study
    rep = s.verification or {}
    st.html(shell.check(f"<b>Verificação na importação:</b> {'aprovada' if rep.get('ok') else 'NÃO aprovada'} "
                        f"({escape(shell.fmt_time(s.imported_at))}).", "ok" if rep.get("ok") else "bad"))
    if st.button("VERIFICAR INTEGRIDADE AGORA", key="ar_verify", type="primary",
                 help="Relê todos os recursos gravados e confere SHA-256 e tamanho contra o manifesto do pacote."):
        ok, problems = view.archive.verify(view.uid)
        _ss()["ar_verify_result"] = (view.uid, ok, problems[:20])
    res = _ss().get("ar_verify_result")
    if res and res[0] == view.uid:
        if res[1]:
            st.success(f"Integridade confirmada: {s.n_resources} recursos com SHA-256 e tamanho conferidos.")
        else:
            st.error("Integridade VIOLADA: " + shell.md(" | ".join(res[2])))
    st.caption(FMT.INTEGRITY_NOTE)
    rows = [{"recurso": r["path"], "papel": ((view.manifest.get("resources") or {}).get(r["path"]) or {}).get("role"),
             "tamanho (bytes)": r["size"], "tipo": r["media_type"], "SHA-256": r["sha256"]}
            for r in view.archive.resources(view.uid)]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=360)
    deps = view.manifest.get("dependencies")
    if deps:
        with st.expander("Índice de dependências (versões → inventário/previsões; rodadas → versão/inventário/dados)"):
            st.json(deps, expanded=False)


__all__ = ["TAB_LIST", "TAB_STUDY", "clear_state", "open_study", "render"]
