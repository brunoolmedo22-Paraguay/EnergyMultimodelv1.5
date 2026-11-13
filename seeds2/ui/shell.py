"""Camada de apresentação comum: componentes v2 locais, CSS global, roteamento e barra superior."""
from __future__ import annotations

import os
import re
from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st

from seeds2 import APP_VERSION

STATIC = Path(__file__).resolve().parent / "static"
_KIT = (STATIC / "kit.css").read_text(encoding="utf-8")
VIEWS = ("gestor", "operacao", "gestao", "simulacao", "resultados", "alcance", "comissionamento", "arquivo")
VIEW_ALIASES = {"inicio": "operacao"}      # Piso 2A: o antigo "Início" foi substituído pelo Centro de Operação
# Navegação da microrrede ativa, agrupada: operação (cotidiano) · gestão física · resultados. A microrrede NÃO é
# um item do menu: é o contexto (identidade + TROCAR MICRORREDE na barra superior). "Alcance" é documentação
# (link secundário, fora da navegação principal).
NAV_ACTIVE = [("operacao", "Centro de Operação", "operacao"), ("simulacao", "Simulação", "operacao"),
              ("gestao", "Gestão da Microrrede", "fisica"), ("resultados", "Resultados", "resultados")]
NAV_COMMISSIONING = [("comissionamento", "Comissionamento", "fisica")]
NAV_GESTOR = [("gestor", "Gestor de microrredes", "gestor"), ("arquivo", "Arquivo Científico", "gestor")]
NAV_DOCS = [("alcance", "Alcance")]
SWITCH_KEY = "seeds_switch_requested"
ROUTE_KEY = "seeds_route"
SCENARIO_KEY = "op_scenario_uid"          # cenário selecionado no Centro de Operação (sobrevive à recarga: ?sc=)
STUDY_KEY = "ar_study_uid"                # Piso 2D-A: estudo arquivado aberto (sobrevive à recarga: ?study=)
# Alcance do backup ZIP (formato 2, inalterado nos Pisos 2A/2B/2C): exibido em TODA exportação/restauração/exclusão.
BACKUP_SCOPE = ("O backup ZIP atual contém a configuração da microrrede e os dados compatíveis do Piso 1 (inventário, "
                "dados de entrada importados, histórico de revisões). **Não inclui os cenários operativos do Centro de "
                "Operação (Piso 2A)**, as previsões associadas a eles (Piso 2B) **nem as rodadas científicas executadas e "
                "seus resultados (Piso 2C: séries completas, procedência e indicadores)**: nada disso pode ser recuperado a "
                "partir deste arquivo. Para preservar cenários, versões, previsões e rodadas use **EXPORTAR CENÁRIO COMPLETO** no "
                "**Arquivo Científico** (pacote .seeds2study.zip, Piso 2D-A) — que, por sua vez, guarda experimentos e não "
                "substitui este backup da configuração da microrrede.")
# Arquivo Científico (Piso 2D-A): alcance exibido em toda exportação/importação de estudos.
STUDY_SCOPE = ("O **Arquivo Científico** (.seeds2study.zip) preserva UM cenário completo — todas as versões, as revisões do "
               "inventário que elas referenciam, previsões (séries normalizadas e arquivos originais), estratégia, janela e "
               "todas as rodadas finalizadas com manifesto, resultados e séries — para consulta em qualquer instalação do "
               "SEEDS2, sem executar o EMS de novo. **Não substitui o backup da microrrede** (.seeds2backup.zip): não "
               "restaura a microrrede, o catálogo nem outros cenários.")
RESTORE_SCOPE = ("Restaurar um backup ZIP cria uma nova revisão da configuração; **nenhum cenário operativo nem rodada "
                 "científica é restaurado** (o arquivo não os contém). Os cenários já existentes nesta microrrede são mantidos e passam a indicar "
                 "que o inventário mudou.")


_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~$:&])")


def md(text: object) -> str:
    """Texto do usuário/arquivo como TEXTO LITERAL em contextos Markdown do Streamlit (captions, rótulos,
    st.error...): escapa sintaxe Markdown/HTML (links, imagens, ênfase, diretivas ``:cor[...]``, LaTeX) e
    reduz quebras de linha. Para HTML construído (st.html), use ``html.escape``."""
    return _MD_SPECIAL.sub(r"\\\1", " ".join(str(text).split()))


def _asset(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def component(name: str):
    """Componente v2 local (JS + CSS do kit). Registrar a cada execução é inócuo."""
    return st.components.v2.component(f"seeds_{name}", js=_asset(f"{name}.js"), css=_KIT + _asset(f"{name}.css"))


def payload(key: str, field: str = "action"):
    val = st.session_state.get(key)
    if val is None:
        return None
    try:
        return val.get(field) if hasattr(val, "get") else getattr(val, field, None)
    except Exception:  # noqa: BLE001
        return None


GLOBAL_CSS = """
<style>
/* Piso 3D-B2-A: os acentos das páginas SEEDS2 seguem a tinta do tema (paleta neutra da Partitura), não mais o verde fixo. */
.stApp { --primary-color: var(--st-primary-color, currentColor); }
.block-container { padding-top: calc(3.75rem + 0.6rem) !important; padding-bottom: 5rem !important; max-width: 1360px; }
h1, h2, h3 { letter-spacing: -0.012em; }
[data-testid="stHeader"] { background: transparent; pointer-events: none; }
[data-testid="stHeader"] [data-testid="stToolbar"], [data-testid="stHeader"] button, [data-testid="stHeader"] a,
[data-testid="stHeader"] [role="button"] { pointer-events: auto; }
.sd-hero { position: relative; display: flex; align-items: center; justify-content: space-between; gap: 1.5rem;
  padding: 1.15rem 1.4rem; margin: .35rem 0 .9rem 0; border-radius: 16px; overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--primary-color, #0E7C86) 22%, rgba(128,128,128,.25));
  background: linear-gradient(120deg, color-mix(in srgb, var(--primary-color, #0E7C86) 9%, transparent) 0%, transparent 62%);
  animation: sdfade .25s ease both; }
.sd-hero::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--primary-color, #0E7C86); }
.sd-hero .txt { min-width: 0; }
.sd-chip-h { display: inline-flex; align-items: center; gap: .45rem; font-size: .7rem; font-weight: 750; letter-spacing: .13em;
  color: var(--primary-color, #0E7C86); text-transform: uppercase; }
.sd-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 4px color-mix(in srgb, currentColor 18%, transparent); }
.sd-hero h1 { font-size: clamp(1.45rem, 1.1rem + 1.4vw, 2.05rem); margin: .35rem 0 .3rem 0; line-height: 1.12; letter-spacing: -.02em; }
.sd-hero p { margin: 0; max-width: 820px; opacity: .8; font-size: 1rem; line-height: 1.5; }
.sd-hero .facts { display: flex; flex-wrap: wrap; gap: .4rem .5rem; margin-top: .65rem; }
.sd-fact { font-size: .78rem; padding: .14rem .55rem; border-radius: .45rem; border: 1px solid rgba(128,128,128,.28); opacity: .92; }
.sd-fact b { font-weight: 650; }
.sd-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .8rem; }
.sd-eyebrow { text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; font-weight: 700; color: var(--primary-color, #0E7C86); }
.sd-section { font-size: 1.08rem; font-weight: 700; margin: .3rem 0 .15rem 0; }
.sd-muted { opacity: .72; font-size: .9rem; }
.sd-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .75rem; margin: .4rem 0 .8rem 0; }
.sd-kpi { border: 1px solid rgba(128,128,128,.25); border-radius: 12px; padding: .7rem .85rem; background: color-mix(in srgb, var(--secondary-background-color, #E9EEF3) 35%, transparent);
  animation: sdfade .3s ease both; }
.sd-kpi small { display: block; font-size: .68rem; font-weight: 750; letter-spacing: .09em; text-transform: uppercase; opacity: .7; }
.sd-kpi b { display: block; font-size: 1.35rem; font-weight: 750; letter-spacing: -.01em; margin: .15rem 0 .05rem 0; font-variant-numeric: tabular-nums; }
.sd-kpi span { font-size: .75rem; opacity: .7; }
.sd-stage { animation: sdfade .22s ease both; }
@keyframes sdfade { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .sd-stage, .sd-hero, .sd-kpi { animation: none; } }
@media (max-width: 720px) { .sd-hero { padding: 1rem 1.1rem; } }
</style>
"""


# Avisos e listas de verificação: usados também sobre o console V1.6 (que não recebe GLOBAL_CSS).
CALLOUT_CSS = """
<style>
.sd-callout { border-left: 3px solid var(--primary-color, #0E7C86); background: color-mix(in srgb, var(--primary-color, #0E7C86) 7%, transparent);
  border-radius: 0 10px 10px 0; padding: .6rem .8rem; font-size: .88rem; line-height: 1.5; margin: .35rem 0 .7rem 0; }
.sd-callout.warn { border-left-color: #C77700; background: color-mix(in srgb, #C77700 8%, transparent); }
.sd-callout.bad { border-left-color: #C2364A; background: color-mix(in srgb, #C2364A 8%, transparent); }
.sd-callout.ok { border-left-color: #2E8B57; background: color-mix(in srgb, #2E8B57 8%, transparent); }
.sd-check { display: flex; gap: .55rem; align-items: flex-start; font-size: .9rem; line-height: 1.45; margin: .2rem 0; }
.sd-check i { flex: none; font-style: normal; width: 1.3rem; height: 1.3rem; border-radius: 50%; display: grid; place-items: center; font-size: .75rem; font-weight: 800; }
.sd-check i.ok { color: #2E8B57; background: rgba(46,139,87,.14); } .sd-check i.warn { color: #C77700; background: rgba(199,119,0,.14); }
.sd-check i.bad { color: #C2364A; background: rgba(194,54,74,.14); } .sd-check i.off { color: #5B6B7C; background: rgba(91,107,124,.14); }
</style>
"""


def global_css() -> None:
    st.html(GLOBAL_CSS + CALLOUT_CSS)


def callout_css() -> None:
    st.html(CALLOUT_CSS)


def hero(chip: str, title: str, text: str, facts: list[tuple[str, str]] | None = None) -> None:
    f = "".join(f'<span class="sd-fact"><b>{escape(k)}</b> {escape(v)}</span>' for k, v in (facts or []) if v)
    st.html(f'<div class="sd-hero"><div class="txt"><div class="sd-chip-h"><span class="sd-dot"></span>{escape(chip)}</div>'
            f'<h1>{escape(title)}</h1><p>{escape(text)}</p>{f"<div class=facts>{f}</div>" if f else ""}</div></div>')


def kpis(items: list[tuple[str, str, str]]) -> None:
    body = "".join(f'<div class="sd-kpi" style="animation-delay:{i * 40}ms"><small>{escape(a)}</small><b>{escape(b)}</b>'
                   f'<span>{escape(c)}</span></div>' for i, (a, b, c) in enumerate(items))
    st.html(f'<div class="sd-kpis">{body}</div>')


def callout(text: str, tone: str = "") -> None:
    st.html(f'<div class="sd-callout {escape(tone)}">{text}</div>')


def check(text: str, tone: str) -> str:
    glyph = {"ok": "✓", "warn": "!", "bad": "✕", "off": "–"}[tone]
    return f'<div class="sd-check"><i class="{tone}">{glyph}</i><span>{text}</span></div>'


# --------------------------------------------------------------------------- roteamento (sobrevive a recargas)
def route() -> dict:
    ss = st.session_state
    if ROUTE_KEY not in ss:
        qp = st.query_params
        view = VIEW_ALIASES.get(qp.get("view", "gestor"), qp.get("view", "gestor"))
        ss[ROUTE_KEY] = {"view": view if view in VIEWS else "gestor", "tab": qp.get("tab")}
    r = ss[ROUTE_KEY]
    if r.get("view") in VIEW_ALIASES:
        r["view"] = VIEW_ALIASES[r["view"]]
    return r


def go(view: str, tab: str | None = None) -> None:
    r = route()
    view = VIEW_ALIASES.get(view, view)
    r["view"] = view if view in VIEWS else "gestor"
    r["tab"] = tab
    mg = st.session_state.get("mg_active_uid")          # a microrrede ativa DESTA aba sobrevive à recarga
    sc = st.session_state.get(SCENARIO_KEY) if mg else None
    # Piso 2C: a rodada aberta (?run=<uid>) sobrevive à recarga enquanto a vista for a da rodada.
    run = (st.session_state.get("op_run_uid") or st.query_params.get("run")) if mg and tab == "rodada" else None
    # Piso 2D-A: o estudo arquivado aberto (?study=<uid>) e a rodada consultada nele (?srun=) sobrevivem à recarga.
    study = (st.session_state.get(STUDY_KEY) or st.query_params.get("study")) if tab == "estudo" else None
    srun = (st.session_state.get("ar_run_uid") or st.query_params.get("srun")) if study else None
    st.query_params.clear()
    st.query_params.update({"view": r["view"], **({"tab": tab} if tab else {}), **({"mg": mg} if mg else {}),
                            **({"sc": sc} if sc else {}), **({"run": run} if run else {}),
                            **({"study": study} if study else {}), **({"srun": srun} if srun else {})})


def _on_topbar() -> None:
    a = payload("seeds_topbar")
    if a and a.get("type") == "nav":
        go(a["view"])
    elif a and a.get("type") == "switch":               # TROCAR MICRORREDE (tratado no início da próxima execução)
        st.session_state[SWITCH_KEY] = True


def nav_classica() -> bool:
    """Navegação CLÁSSICA (links na barra superior, como antes do Piso 3D-B2) pedida pela instalação com
    ``SEEDS2_NAV_CLASSICA=1``. Por omissão a barra superior é compacta: os mesmos destinos estão na barra lateral."""
    return os.environ.get("SEEDS2_NAV_CLASSICA", "").strip() == "1"


# UI-REDESIGN-01: as cinco bancadas individuais (as MESMAS telas que os botões «ABRIR …» do Centro de Operação abrem:
# ``energy_source`` roteado por ``app.py``), na ordem do Gestor; ``kind`` = tipo do inventário, para o ícone e a cor do Gestor.
BANCADAS = (("solar", "Solar", "pv"), ("wind", "Eólica", "wind"), ("battery", "Bateria", "battery"),
            ("h2", "H₂ / PEMFC", "pemfc"), ("thermal", "Térmica", "thermal"))


def abrir_bancada(fonte: str) -> bool:
    """Abre uma bancada individual exatamente como ``home.benches``: independente da configuração da microrrede."""
    if fonte not in {b[0] for b in BANCADAS}:
        return False
    st.session_state["energy_source"] = fonte
    if fonte == "solar":
        st.session_state["current_page"] = "Visão geral"
    return True


def _on_sidebar() -> None:
    a = payload("seeds_sidebar")
    if a and a.get("type") == "nav":
        go(a["view"], a.get("tab"))
    elif a and a.get("type") == "switch":               # Catálogo com microrrede aberta = TROCAR MICRORREDE
        st.session_state[SWITCH_KEY] = True
    elif a and a.get("type") == "bancada":               # UI-REDESIGN-01: bancada individual (fonte desconhecida é ignorada)
        abrir_bancada(str(a.get("fonte") or ""))


def sidebar_items(*, view: str, tab: str | None, is_open: bool, commissioned: bool, rodada: str | None = None) -> list[dict]:
    """Destinos da barra lateral (Piso 3D-B2-A). Dá nome aos lugares da experiência Partitura: Catálogo, Planta, Caderno,
    Folha, Rodada, Arquivo e, desde o UI-REDESIGN-01, as cinco BANCADAS no lugar do antigo console V1.6."""
    def it(ident, rotulo, icone, grupo, alvo_view, alvo_tab=None, *, atual=False, curto=None, movel=False, dica=None, troca=False,
           acao=None):
        return {"id": ident, "rotulo": rotulo, "curto": curto or rotulo, "icone": icone, "grupo": grupo, "atual": bool(atual),
                "movel": movel, "dica": dica or rotulo,
                "acao": acao or ({"type": "switch"} if troca else {"type": "nav", "view": alvo_view, "tab": alvo_tab})}
    doc = it("alcance", "Alcance e limitações", "alcance", "Documentação", "alcance", atual=view == "alcance", curto="Alcance")
    # UI-REDESIGN-01: as cinco bancadas no lugar do antigo console V1.6. UI-FINISH-01: TAMBÉM sem microrrede aberta e no
    # comissionamento — as bancadas não dependem da microrrede (mesma ação de sempre, ``abrir_bancada``); uma lista por
    # contexto, logo nunca duplicadas.
    bancadas = [it(f"bancada_{fonte}", rot, f"k:{kind}", "Bancadas", None, curto=rot.split(" ")[0],
                   dica=f"Bancada {rot}: modelo físico isolado, sem usar nem alterar a configuração de nenhuma microrrede",
                   acao={"type": "bancada", "fonte": fonte}) for fonte, rot, kind in BANCADAS]
    if not is_open:
        return [it("catalogo", "Catálogo de microrredes", "catalogo", None, "gestor", atual=view == "gestor", curto="Catálogo", movel=True),
                it("arquivo", "Arquivo Científico", "arquivo", None, "arquivo", atual=view == "arquivo", curto="Arquivo", movel=True),
                *bancadas, doc]
    cat = it("catalogo", "Catálogo de microrredes", "catalogo", None, "gestor", curto="Catálogo", movel=True, troca=True,
             dica="Voltar ao Catálogo (trocar de microrrede; os dados não são alterados)")
    if not commissioned:
        return [cat, it("comissionamento", "Comissionamento", "comissionamento", "Microrrede", "comissionamento",
                        atual=view == "comissionamento", movel=True), *bancadas, doc]
    arq = view == "operacao" and tab in ("arquivo", "estudo")
    planta = view == "operacao" and tab == "planta"
    caderno = view == "operacao" and tab == "caderno"
    folha = view == "operacao" and tab in ("inicializacao", "previsoes", "estrategia", "execucao")
    # Rodada: só quando há uma rodada selecionada DESTA microrrede (``rodada`` já conferido pelo chamador).
    na_rodada = bool(rodada) and view == "operacao" and tab == "rodada"
    rod = [it("rodada", f"Rodada · {rodada[:8]}", "rodada", "Microrrede", "operacao", "rodada", atual=na_rodada, curto="Rodada",
              dica="Rodada aberta (resultados gravados; abrir não executa nada)")] if rodada else []
    return [cat,
            it("planta", "Planta", "planta", "Microrrede", "operacao", "planta", atual=planta, movel=True,
               dica="Planta: barramento equivalente e equipamentos do inventário"),
            it("caderno", "Caderno de ensaios", "ensaios", "Microrrede", "operacao", "caderno", atual=caderno, curto="Ensaios",
               movel=True, dica="Caderno de ensaios: cenários, versões e rodadas (V1.6 e V2)"),
            it("folha", "Folha de ensaio", "folha", "Microrrede", "operacao", "inicializacao", atual=folha, curto="Folha",
               dica="Folha de ensaio do cenário selecionado: estado inicial, previsões, estratégia e execução"),
            *rod,
            it("operacao", "Centro de Operação", "operacao", "Microrrede", "operacao",
               atual=view == "operacao" and not arq and not planta and not caderno and not folha and not na_rodada,
               curto="Operação", movel=True),
            it("gestao", "Gestão da Microrrede", "gestao", "Microrrede", "gestao", atual=view == "gestao", curto="Gestão", movel=True),
            it("arquivo", "Arquivo Científico", "arquivo", "Microrrede", "operacao", "arquivo", atual=arq, curto="Arquivo", movel=True),
            # UI-REDESIGN-01: o grupo «Console V1.6» (Simulação/Resultados V1.6, sem o EMS hierárquico) saiu da navegação;
            # no lugar, as cinco bancadas. As vistas antigas continuam existindo (URL ``?view=`` e navegação clássica).
            *bancadas, doc]


def _rodada_da_sessao() -> str | None:
    """Rodada aberta nesta sessão (``op_run_uid`` ou ``?run=``), SÓ se existir no banco da microrrede ativa."""
    uid = st.session_state.get("op_run_uid") or st.query_params.get("run")
    if not uid or not st.session_state.get("mg_active_uid"):
        return None
    try:
        from . import session

        return session.store().get_run(str(uid)).run_uid
    except Exception:  # noqa: BLE001 — rodada inexistente, de outra microrrede ou banco indisponível: sem destino
        return None


def sidebar(*, view: str, tab: str | None, is_open: bool, commissioned: bool, contexto: str = "") -> None:
    from . import trama

    rodada = _rodada_da_sessao() if is_open and commissioned else None
    trama.sidebar({"versao": APP_VERSION, "contexto": contexto,
                   "itens": sidebar_items(view=view, tab=tab, is_open=is_open, commissioned=commissioned, rodada=rodada)},
                  on_action=_on_sidebar)


def fmt_time(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")
    except ValueError:
        return iso


def topbar(*, view: str, items: list[tuple], site: str, site_title: str, save: dict, force_light: bool,
           home: str, switch: bool = False, site_sub: str = "", mg_name: str = "",
           aux: list[tuple[str, str]] | None = None) -> None:
    component("topbar")(key="seeds_topbar", on_action_change=_on_topbar,
                        data={"version": APP_VERSION, "view": view, "items": [list(i) for i in items], "site": site,
                              "site_title": site_title, "site_sub": site_sub, "mg_name": mg_name, "save": save,
                              "force_light": force_light, "home": home, "switch": switch,
                              "aux": [list(a) for a in (NAV_DOCS if aux is None else aux)], "compacta": not nav_classica()})
    # Piso 3D-B2-A: a barra lateral acompanha SEMPRE a barra superior (mesmo contexto; a superior continua completa).
    # ``items`` distingue os três contextos do shell: Gestor (sem microrrede), comissionamento e microrrede ativa.
    sidebar(view=view, tab=route().get("tab"), is_open=bool(switch), commissioned=items is NAV_ACTIVE,
            contexto=mg_name if switch else "Nenhuma microrrede aberta")
