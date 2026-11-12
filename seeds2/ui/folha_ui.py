"""Folha de Ensaio (Piso 3D-B2-D) — a organização da Partitura V2 sobre as etapas existentes do cenário.

A Folha NÃO substitui os formulários: cada seção continua a ser a etapa que já existia (mesmos widgets, chaves, campos
científicos, validações, preflight e execução). Esta camada acrescenta, acima de cada etapa, o cabeçalho da folha: o cenário
e a versão, o índice das seções com o estado de cada uma (os MESMOS estados do painel do Centro de Operação), a prontidão e
o aviso de alterações não salvas — e permite ir de uma seção a outra sem voltar ao painel.
"""
from __future__ import annotations

import streamlit as st

from seeds2.operation import scenarios as S

from . import shell

SECOES = (("inicializacao", "01", "Estado inicial"), ("previsoes", "02", "Previsões"), ("estrategia", "03", "Motor e estratégia"),
          ("execucao", "04", "Missão e execução"))
TABS = tuple(s[0] for s in SECOES)
TOM = {"ok": "ok", "warn": "w", "bad": "b", "info": "i", "off": ""}


def dados(store, cur, doc: dict, tab: str, *, dirty: bool) -> dict:
    """Cabeçalho da folha a partir do documento de trabalho e dos MESMOS estados de etapa do painel."""
    from . import execution_ui

    fs = S.findings(doc)
    rd = S.readiness(doc, fs, None)
    est = dict(rd["stages"])
    est["estrategia"] = S.strategy_status(doc)
    try:
        est["execucao"] = execution_ui.stage_state(store, cur)
    except Exception as exc:  # noqa: BLE001 — o cabeçalho nunca impede o uso da etapa
        est["execucao"] = ("off", "Indisponível", str(exc)[:80])
    cont = rd["counts"]
    return {"cenario": {"uid": cur.scenario_uid, "nome": doc.get("name") or cur.name, "versao": cur.version,
                        "motor": "V2 · MILP–MPC hierárquico (experimental)" if execution_ui._is_v2_doc(doc) else "V1.6",
                        "revisao": (doc.get("inventory_ref") or {}).get("config_revision")},
            "secoes": [{"id": k, "n": n, "titulo": t, "tom": TOM.get(est[k][0], ""), "estado": est[k][1], "detalhe": est[k][2],
                        "atual": k == tab} for k, n, t in SECOES],
            "constatacoes": {str(k): int(v) for k, v in cont.items()}, "alterado": bool(dirty),
            "rodadas": len(store.list_runs(cur.scenario_uid, limit=2000))}


def _on_action() -> None:
    a = shell.payload("seeds_folha")
    if a and a.get("type") == "nav":
        shell.go(a.get("view") or "operacao", a.get("tab"))


def cabecalho(store, cur, doc: dict | None, tab: str, *, dirty: bool) -> None:
    """Desenha o cabeçalho da Folha acima de uma etapa. Sem cenário selecionado não desenha nada (a etapa diz o que falta)."""
    if cur is None or doc is None or tab not in TABS:
        return
    from . import trama

    trama.pagina("folha", dados(store, cur, doc, tab, dirty=dirty), key="seeds_folha", on_action=_on_action, wide=False)


__all__ = ["SECOES", "TABS", "cabecalho", "dados"]
