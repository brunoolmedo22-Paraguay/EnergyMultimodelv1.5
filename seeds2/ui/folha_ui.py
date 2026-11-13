"""Folha de Ensaio (Piso 3D-B2-D; finalizada na missão de finalização da Partitura V2) — instrumento de preparação do ensaio.

Organização aprovada no protótipo, em TRÊS COLUNAS (no celular, empilhadas):

* **índice** (esquerda): identidade do cenário, as quatro seções com o estado de cada uma (os MESMOS estados do painel
  do Centro de Operação: ``S.readiness``, ``S.strategy_status``, ``execution_ui.stage_state``) e, na seção 03 com o
  motor V2, as SUBSEÇÕES navegáveis do formulário da estratégia (com as declarações ausentes de cada uma);
* **seção** (centro): a etapa existente, intacta — mesmos widgets, chaves, campos científicos, validações, preflight,
  barra de salvar e execução. A Folha só a envolve; o cartão de abertura da etapa vira o cabeçalho da seção (CSS);
* **prontidão** (direita): o acompanhamento do ensaio — versão salva × alterações não salvas, o estado de cada seção,
  o preflight da versão salva e se a execução está disponível, pelas MESMAS razões que habilitam o botão da seção 04
  (alterações não salvas, bloqueios do preflight, outra rodada em execução). Nenhum critério novo.

UI-FINISH-01: na seção 04 com o motor V2, o botão de executar (o MESMO, com as mesmas guardas) vive num cartão de rodada
desenhado na coluna do índice, logo abaixo da Folha. A etapa entrega o cartão por um «slot» de sessão (``CTA_SLOT``) — a
Folha não importa o pacote do motor.

O índice e a prontidão são desenhados DEPOIS da etapa, na mesma execução, para refletirem as edições feitas nela.
"""
from __future__ import annotations

from typing import Callable

import streamlit as st

from seeds2.operation import scenarios as S

from . import shell

SECOES = (("inicializacao", "01", "Estado inicial"), ("previsoes", "02", "Previsões"), ("estrategia", "03", "Motor e estratégia"),
          ("execucao", "04", "Missão e execução"))
TABS = tuple(s[0] for s in SECOES)
TOM = {"ok": "ok", "warn": "w", "bad": "b", "info": "i", "off": ""}
CTA_SLOT = "fl_cta_slot"            # = integracao_v2.ui.CTA_SLOT (cartão de rodada entregue pela etapa 04)

# Estilos da Folha na página (fora do componente): colunas, colunas laterais fixas ao rolar, cabeçalho compacto da etapa
# (o cartão de abertura vira título de seção; os mesmos textos continuam na página) e âncoras das subseções.
FOLHA_CSS = """<style>
[data-testid="stColumn"]:has(.st-key-fl_col_indice), [data-testid="stColumn"]:has(.st-key-fl_col_prontidao) { align-self: flex-start; }
@media (min-width: 1181px) {
  [data-testid="stColumn"]:has(.st-key-fl_col_indice), [data-testid="stColumn"]:has(.st-key-fl_col_prontidao) {
    position: sticky; top: 4.2rem; max-height: calc(100vh - 5rem); overflow-y: auto; scrollbar-width: thin; }
}
@media (min-width: 641px) and (max-width: 1180px) {
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-fl_col_indice) { flex-wrap: wrap; }
  [data-testid="stColumn"]:has(.st-key-fl_col_indice) { flex: 0 0 214px !important; width: 214px !important;
    position: sticky; top: 4.2rem; max-height: calc(100vh - 5rem); overflow-y: auto; }
  [data-testid="stColumn"]:has(.st-key-fl_col_secao) { flex: 1 1 0 !important; width: auto !important; min-width: 0; }
  [data-testid="stColumn"]:has(.st-key-fl_col_prontidao) { flex: 1 1 100% !important; width: 100% !important; }
}
.st-key-fl_col_secao .sd-hero { padding: .2rem 0 .55rem 0; border: 0; background: none; box-shadow: none; animation: none;
  border-bottom: 1px solid rgba(128,128,128,.22); border-radius: 0; margin-bottom: .2rem; }
.st-key-fl_col_secao .sd-hero::before { display: none; }
.st-key-fl_col_secao .sd-hero h1 { font-size: 1.45rem; margin: .15rem 0 .2rem 0; }
.st-key-fl_col_secao .sd-hero p { font-size: .9rem; }
.st-key-fl_col_secao .sd-hero .facts { display: none; }
.st-key-fl_col_secao [class*="st-key-op_back"] button { min-height: 0; padding: .1rem .55rem; border: 0; background: none;
  font-size: .82rem; opacity: .7; }
.st-key-fl_col_secao [class*="st-key-op_back"] button:hover { opacity: 1; text-decoration: underline; }
.fl-sub { display: flex; align-items: baseline; gap: .6rem; font-size: 1.02rem; font-weight: 720; letter-spacing: -.005em;
  margin: 1.1rem 0 .1rem 0; padding-top: .35rem; border-top: 1px solid rgba(128,128,128,.22); scroll-margin-top: 4.6rem; }
.fl-sub .fl-sub-n { font-size: .74rem; font-weight: 800; letter-spacing: .08em; opacity: .5; font-variant-numeric: tabular-nums; }
</style>"""


def _v2():
    from . import execution_ui

    return execution_ui._v2()


def dados(store, cur, doc: dict, tab: str, *, dirty: bool) -> dict:
    """Índice da folha a partir do documento de trabalho e dos MESMOS estados de etapa do painel."""
    from . import execution_ui

    fs = S.findings(doc)
    rd = S.readiness(doc, fs, None)
    est = dict(rd["stages"])
    est["estrategia"] = S.strategy_status(doc)
    try:
        est["execucao"] = execution_ui.stage_state(store, cur)
    except Exception as exc:  # noqa: BLE001 — o índice nunca impede o uso da etapa
        est["execucao"] = ("off", "Indisponível", str(exc)[:80])
    cont = rd["counts"]
    v2 = execution_ui._is_v2_doc(doc)
    subs = []
    if v2 and tab == "estrategia":
        try:
            subs = _v2().subsecoes_estrategia(doc)
        except Exception:  # noqa: BLE001
            subs = []
    return {"cenario": {"uid": cur.scenario_uid, "nome": doc.get("name") or cur.name, "versao": cur.version,
                        "motor": "V2 · MILP–MPC hierárquico (experimental)" if v2 else "V1.6",
                        "revisao": (doc.get("inventory_ref") or {}).get("config_revision")},
            "secoes": [{"id": k, "n": n, "titulo": t, "tom": TOM.get(est[k][0], ""), "estado": est[k][1], "detalhe": est[k][2],
                        "atual": k == tab} for k, n, t in SECOES],
            "subsecoes": subs, "constatacoes": {str(k): int(v) for k, v in cont.items()}, "alterado": bool(dirty),
            "rodadas": len(store.list_runs(cur.scenario_uid, limit=2000))}


def prontidao(store, cur, doc: dict, d: dict, *, dirty: bool) -> dict:
    """Coluna de prontidão: reúne estados JÁ calculados (``d``) e as razões que habilitam o botão da seção 04."""
    from . import execution_ui

    sec = {s["id"]: s for s in d["secoes"]}
    # Rodada em execução: só LEITURA (a recuperação de rodadas de processos mortos continua sendo feita pela seção 04).
    ativa = next((r for r in store.list_runs(limit=20) if r.state == "em_execucao"), None)
    ok04 = sec["execucao"]["tom"] == "ok"
    motivo = ("há alterações não salvas" if dirty else
              ("o preflight V2 tem bloqueios" if execution_ui._is_v2_doc(cur.document) else "o cenário tem incompatibilidades")
              if not ok04 else "outra rodada está em execução nesta microrrede" if ativa is not None else "")
    pend = []
    if execution_ui._is_v2_doc(doc) and isinstance(doc.get("milp_mpc"), dict):
        try:
            subs = d.get("subsecoes") or _v2().subsecoes_estrategia(doc)
            pend = [{"id": s["id"], "n": s["n"], "titulo": s["titulo"], "pend": s["pend"]} for s in subs if s.get("pend")]
        except Exception:  # noqa: BLE001
            pend = []
    runs = store.list_runs(cur.scenario_uid, limit=1)
    ult = None
    if runs:
        r = runs[0]
        ult = {"uid": r.run_uid, "estado": r.state, "versao": r.scenario_version,
               "quando": str(getattr(r, "finished_at", None) or getattr(r, "created_at", "") or "")[:16].replace("T", " ")}
    return {"parte": "prontidao", "tab": next((s["id"] for s in d["secoes"] if s["atual"]), None),
            "cta_lateral": bool(execution_ui._is_v2_doc(cur.document)),
            "versao": cur.version, "alterado": bool(dirty), "secoes": d["secoes"], "constatacoes": d["constatacoes"],
            "pendencias": pend, "executavel": not motivo, "motivo": motivo,
            "ativa": ativa.run_uid if ativa is not None else None, "ultima": ult, "rodadas": d["rodadas"]}


def _acao(a) -> None:
    if not a:
        return
    if a.get("type") == "nav":
        shell.go(a.get("view") or "operacao", a.get("tab"))
    elif a.get("type") == "abrir_rodada" and a.get("run"):
        from . import execution_ui

        execution_ui.open_run(str(a["run"]))


def _on_action() -> None:
    _acao(shell.payload("seeds_folha"))


def _on_action_pr() -> None:
    _acao(shell.payload("seeds_folha_pr"))


def cabecalho(store, cur, doc: dict | None, tab: str, *, dirty: bool) -> None:
    """Índice da Folha sozinho (compatibilidade: usado quando não há colunas)."""
    if cur is None or doc is None or tab not in TABS:
        return
    from . import trama

    trama.pagina("folha", dados(store, cur, doc, tab, dirty=dirty), key="seeds_folha", on_action=_on_action, wide=False)


def render(store, cur, work: Callable[[], dict | None], tab: str, *, is_dirty: Callable[[], bool],
           corpo: Callable[[], None]) -> None:
    """Folha em três colunas em volta da etapa ``corpo`` (a etapa existente, chamada sem alteração)."""
    if cur is None or work() is None or tab not in TABS:
        corpo()                                         # sem cenário: a etapa diz o que falta (comportamento anterior)
        return
    from . import trama

    st.html(trama.WIDE_CSS)
    st.html(FOLHA_CSS)
    with st.container(key="fl_folha"):
        ci, cc, cr = st.columns([1.25, 3.6, 1.35], gap="medium")
        st.session_state[CTA_SLOT] = []                  # a etapa 04 V2 deposita aqui o cartão de rodada
        try:
            with cc, st.container(key="fl_col_secao"):
                corpo()
        finally:
            ctas = st.session_state.pop(CTA_SLOT, None) or []
        doc, dirty = work(), is_dirty()                  # depois da etapa: reflete as edições desta execução
        if doc is None:
            return
        d = dados(store, cur, doc, tab, dirty=dirty)
        with ci, st.container(key="fl_col_indice"):
            trama.pagina("folha", d, key="seeds_folha", on_action=_on_action, wide=False)
            for cta in ctas:                             # UI-FINISH-01: cartão de rodada logo abaixo da Folha
                cta()
        with cr, st.container(key="fl_col_prontidao"):
            trama.pagina("folha", prontidao(store, cur, doc, d, dirty=dirty), key="seeds_folha_pr", on_action=_on_action_pr,
                         wide=False)


__all__ = ["CTA_SLOT", "FOLHA_CSS", "SECOES", "TABS", "cabecalho", "dados", "prontidao", "render"]
