"""Planta da microrrede (Piso 3D-B2-B) — ``tab = planta`` do Centro de Operação.

O barramento equivalente desenhado como o modelo o enxerga: o que injeta acima, o que armazena ou consome abaixo, um nó por
equipamento do INVENTÁRIO SALVO (identidade por UID). Opcionalmente, uma rodada V2 concluída e verificada empresta aos nós
os valores GRAVADOS de cada intervalo (do marco de dados da Partitura): nada é recalculado e nenhum fluxo é desenhado nas
ligações — o modelo não calcula ramos. Abrir um nó leva ao painel desse equipamento (por UID) na Partitura da rodada.

Somente leitura: não altera o inventário, cenários nem rodadas; nunca chama o otimizador nem os modelos.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from seeds2.microgrid import config as C
from seeds2.microgrid.derived import battery_derived, pv_plant_summary

from . import forms, session, shell

TAB = "planta"
KEY_RUN = "pl_run_uid"
TIPOS = {"pv": "fv", "wind": "wt", "pemfc": "fc", "thermal": "term", "battery": "bat"}


def _txt(v, dec: int, un: str) -> str:
    return "não declarado" if v is None else forms.fmt(v, dec, un)


def _no(eq: dict) -> dict:
    """Um nó da planta a partir de UM equipamento do inventário (valores do inventário; nada inventado)."""
    kind, p = eq.get("kind"), eq.get("params") or {}
    nominal = C.installed_power_kW(eq) if kind != "battery" else None
    det: list[list[str]] = []
    uids = [eq["id"]]
    if kind == "pv":
        s = pv_plant_summary(eq)
        uids = [a["id"] for a in eq.get("arrays") or []]
        det = [["Arranjos", str(s["n_arrays"])], ["Módulos", str(s["n_modules"]) if s["n_modules"] else "não declarado"],
               ["Potência nominal (STC)", _txt(nominal, 2, "kWp")]]
        resumo = _txt(nominal, 1, "kWp")
    elif kind == "wind":
        det = [["Aerogerador", str(p.get("reference") or "não declarado")], ["Quantidade", str(p.get("count") or "não declarado")],
               ["Potência nominal", _txt(nominal, 0, "kW")]]
        resumo = _txt(nominal, 0, "kW")
    elif kind == "pemfc":
        det = [["Referência", str(p.get("reference") or "não declarado")], ["Unidades", str(p.get("quantity") or "não declarado")],
               ["Potência líquida máxima", _txt(nominal, 1, "kW")]]
        resumo = _txt(nominal, 0, "kW")
    elif kind == "battery":
        e, base, _ = battery_derived(p)["energy_kWh"]
        if e is None:
            e, base = C.battery_model_energy_kWh(eq), "parametrização do modelo"
        det = [["Energia", _txt(e, 1, "kWh") + (f" ({base})" if e is not None and base else "")],
               ["Limites de SOC", f"{forms.fmt(p.get('soc_min_pct'), 0)} – {forms.fmt(p.get('soc_max_pct'), 0)} %"
                if p.get("soc_min_pct") is not None and p.get("soc_max_pct") is not None else "não declarado"]]
        resumo = _txt(e, 0, "kWh")
    else:                                                   # térmica e demais: só o que o inventário registra
        det = [["Potência máxima", _txt(nominal, 0, "kW")]]
        resumo = _txt(nominal, 0, "kW")
    return {"uid": eq["id"], "tipo": TIPOS.get(kind, "outro"), "nome": eq.get("name") or "Sem nome", "tag": eq.get("tag") or "",
            "habilitado": bool(eq.get("enabled", True)), "configurado": bool(C.is_configured(eq)), "resumo": resumo,
            "detalhes": det, "uids": uids, "prefixo": eq["id"] + "#" if kind == "pemfc" else None}


def dados_do_inventario(saved) -> dict:
    cfg = saved.config
    inst = cfg.get("installation") or {}
    conectada = (cfg.get("energy_balance") or {}).get("grid_connection") == "conectada"
    return {"microrrede": {"uid": inst.get("uid"), "nome": inst.get("name") or "", "revisao": saved.revision,
                           "modo": C.OPERATION_MODE_OPTIONS.get(inst.get("operation_mode")) or "não declarado"},
            "nos": [_no(e) for e in cfg.get("equipment") or []],
            "demanda": {"origem": "Demanda agregada da microrrede (Gestão → Demanda e dados; nos cenários, a previsão)"},
            "pcc": {"conectada": conectada}}


def _rodadas_v2(store) -> list:
    from . import execution_ui

    return [r for r in store.list_runs(limit=200) if r.state == "concluida" and execution_ui._is_v2_run(r)]


def dados_da_rodada(store, run) -> dict | None:
    """Valores GRAVADOS da rodada por UID (seleção do marco da Partitura, feita na camada de integração; sem aritmética).
    ``None`` se a evidência não for verificada — a Planta mostra então só o inventário."""
    from . import execution_ui

    return execution_ui._v2().planta_rodada(store, run)        # acesso tardio à integração JÁ existente em execution_ui


def _on_action() -> None:
    a = shell.payload("seeds_planta")
    if not a:
        return
    ss = st.session_state
    if a.get("type") == "rodada":
        ss[KEY_RUN] = a.get("run") or ""
    elif a.get("type") == "abrir_rodada" and a.get("run"):
        from . import execution_ui

        execution_ui.open_run(str(a["run"]))
    elif a.get("type") == "nav":
        shell.go(a.get("view") or "operacao", a.get("tab"))


def render(store, cur) -> None:
    from . import trama

    saved = session.saved()
    dados = dados_do_inventario(saved)
    rodadas = _rodadas_v2(store)
    ss = st.session_state
    escolhida = ss.get(KEY_RUN)
    if escolhida is None and rodadas:
        escolhida = rodadas[0].run_uid                       # a mais recente concluída
    run = next((r for r in rodadas if r.run_uid == escolhida), None)
    cache = ss.setdefault("pl_cache", {})
    if run is not None and run.run_uid not in cache:
        if len(cache) > 3:
            cache.clear()
        with st.spinner("Lendo os dados gravados da rodada…"):
            cache[run.run_uid] = dados_da_rodada(store, run)
    dados["rodada"] = cache.get(run.run_uid) if run is not None else None
    dados["rodada_indisponivel"] = bool(run is not None and dados["rodada"] is None)
    dados["rodadas"] = [{"uid": r.run_uid, "rotulo": f"{(r.manifest.get('scenario') or {}).get('name') or 'cenário'} · v"
                                                      f"{r.scenario_version} · {shell.fmt_time(r.finished_at or r.created_at)}"}
                        for r in rodadas]
    dados["escolhida"] = run.run_uid if run is not None else ""
    c1, _ = st.columns([1, 3])
    with c1:
        if st.button("← Centro de Operação", key="pl_back"):
            shell.go("operacao")
            st.rerun()
    st.html(f'<h1 class="sd-section" style="font-size:1.5rem;margin:.2rem 0 .1rem">Planta · {escape(dados["microrrede"]["nome"])}</h1>'
            '<div class="sd-muted" style="margin-bottom:.5rem">Barramento equivalente da microrrede a partir do inventário salvo '
            f'(rev. {saved.revision}). Passe o mouse ou use Tab para destacar; clique ou Enter seleciona um equipamento.</div>')
    trama.pagina("planta", dados, key="seeds_planta", on_action=_on_action)
    if not dados["nos"]:
        st.info("O inventário desta microrrede ainda não tem equipamentos. Adicione-os em Gestão da Microrrede.")
        if st.button("Abrir a Gestão da Microrrede", key="pl_gestao"):
            shell.go("gestao")
            st.rerun()


__all__ = ["TAB", "dados_da_rodada", "dados_do_inventario", "render"]
