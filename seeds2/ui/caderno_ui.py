"""Caderno de Ensaios (Piso 3D-B2-C) — ``tab = caderno`` do Centro de Operação.

Todos os cenários e TODAS as rodadas desta microrrede (qualquer cenário, versão e motor — V1.6 e V2), com versão, motor,
estado, datas, revisão do inventário, resultado rotulado pelo motor e dados gravados; e os estudos do Arquivo Científico.
Somente leitura: lista o que está persistido, não altera cenários, rodadas nem estudos, e nunca chama o otimizador. Abrir
uma rodada, um cenário (Folha de Ensaio) ou um estudo usa os fluxos existentes. Nada de outra microrrede é listado.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from seeds2.microgrid.store import StoreError
from seeds2.operation import contracts

from . import session, shell

TAB = "caderno"
TOM = {"concluida": "ok", "falhou": "b", "interrompida": "w", "em_execucao": "i", "preparada": "i"}


def dados(store, *, ativo: str | None = None) -> dict:
    """Linhas do Caderno a partir do armazenamento da microrrede (e do Arquivo Científico, se existir)."""
    from . import execution_ui

    cenarios = store.list_scenarios()
    nomes = {s.scenario_uid: s.name for s in cenarios}
    rodadas = store.list_runs(limit=2000)
    por_cenario: dict[str, dict[str, int]] = {}
    linhas = []
    for r in rodadas:
        c = por_cenario.setdefault(r.scenario_uid, {})
        c[r.state] = c.get(r.state, 0) + 1
        linhas.append({"uid": r.run_uid, "cenario_uid": r.scenario_uid,
                       "cenario": ((r.manifest or {}).get("scenario") or {}).get("name") or nomes.get(r.scenario_uid) or "—",
                       "versao": r.scenario_version, "motor": "V2" if execution_ui._is_v2_run(r) else "V1.6",
                       "estado": r.state, "estado_rotulo": contracts.RUN_STATE_LABELS.get(r.state, r.state),
                       "tom": TOM.get(r.state, ""), "criada": shell.fmt_time(r.created_at),
                       "finalizada": shell.fmt_time(r.finished_at) or "—", "revisao": r.config_revision,
                       "resultado": execution_ui.run_cost_text(r), "dados": len(r.data or {}),
                       "cenario_existe": r.scenario_uid in nomes})
    cen = [{"uid": s.scenario_uid, "nome": s.name, "versao": s.version, "motor": "V2" if execution_ui._is_v2_doc(s.document) else "V1.6",
            "atualizado": shell.fmt_time(s.updated_at), "revisao": s.base_revision, "rodadas": por_cenario.get(s.scenario_uid, {}),
            "atual": s.scenario_uid == ativo} for s in reversed(cenarios)]
    return {"cenarios": cen, "rodadas": linhas, "estudos": _estudos(store), "rotulos": dict(contracts.RUN_STATE_LABELS)}


def _estudos(store) -> list[dict]:
    """Estudos do Arquivo Científico da instalação (somente leitura). O banco do Arquivo NÃO é criado por esta consulta."""
    from seeds2.microgrid.store import resolve_data_dir

    if not (Path(str(resolve_data_dir())) / "scientific_archive" / "archive.db").is_file():
        return []
    try:
        estudos = list(reversed(session.archive().list_studies()))
    except StoreError:
        return []
    mg = session.active_uid()
    return [{"uid": e.archive_uid, "nome": e.scenario_name, "origem": e.origin_microgrid_name or "—", "versoes": e.n_versions,
             "rodadas": e.n_runs, "verificado": bool((e.verification or {}).get("ok")), "content_id": e.content_id[:16],
             "desta": bool(mg and e.origin_microgrid_uid == mg), "importado": shell.fmt_time(e.imported_at)} for e in estudos]


def _on_action() -> None:
    a = shell.payload("seeds_caderno")
    if not a:
        return
    ss = st.session_state
    if a.get("type") == "abrir_rodada" and a.get("run"):
        from . import execution_ui

        execution_ui.open_run(str(a["run"]))
    elif a.get("type") == "abrir_cenario" and a.get("sc"):
        from . import operation_center as OC

        if ss.get(shell.SCENARIO_KEY) != a["sc"]:
            if OC.is_dirty():                               # uma edição pendente nunca é descartada em silêncio
                ss["op_flash"] = ("warn", "Há alterações não salvas no cenário aberto: salve-as ou descarte-as antes de "
                                          "abrir outro cenário.")
                return
            OC._clear_selection()
            ss[shell.SCENARIO_KEY] = str(a["sc"])
        shell.go("operacao", a.get("tab") or "inicializacao")
    elif a.get("type") == "abrir_estudo" and a.get("study"):
        from . import archive_ui

        archive_ui.open_study(str(a["study"]), "operacao")
    elif a.get("type") == "nav":
        shell.go(a.get("view") or "operacao", a.get("tab"))


def render(store, cur) -> None:
    from . import trama

    saved = session.saved()
    d = dados(store, ativo=cur.scenario_uid if cur is not None else None)
    d["microrrede"] = {"nome": (saved.config.get("installation") or {}).get("name") or "", "revisao": saved.revision}
    c1, _ = st.columns([1, 3])
    with c1:
        if st.button("← Centro de Operação", key="cd_back"):
            shell.go("operacao")
            st.rerun()
    st.html(f'<h1 class="sd-section" style="font-size:1.5rem;margin:.2rem 0 .1rem">Caderno de ensaios · {escape(d["microrrede"]["nome"])}</h1>'
            '<div class="sd-muted" style="margin-bottom:.5rem">Cenários, versões e rodadas desta microrrede (motores V1.6 e V2) e os '
            'estudos do Arquivo Científico. Somente leitura: abrir uma rodada não executa modelos nem o otimizador.</div>')
    trama.pagina("caderno", d, key="seeds_caderno", on_action=_on_action)


__all__ = ["TAB", "dados", "render"]
