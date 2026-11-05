"""Camada de apresentação comum: componentes v2 locais, CSS global, roteamento e barra superior."""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st

from seeds2 import APP_VERSION

STATIC = Path(__file__).resolve().parent / "static"
_KIT = (STATIC / "kit.css").read_text(encoding="utf-8")
VIEWS = ("inicio", "gestao", "simulacao", "resultados", "alcance", "comissionamento")
NAV_ACTIVE = [("inicio", "Início"), ("gestao", "Gestão da Microrrede"), ("simulacao", "Simulação"),
              ("resultados", "Resultados"), ("alcance", "Alcance")]
NAV_COMMISSIONING = [("comissionamento", "Comissionamento"), ("alcance", "Alcance")]
ROUTE_KEY = "seeds_route"


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
        view = qp.get("view", "inicio")
        ss[ROUTE_KEY] = {"view": view if view in VIEWS else "inicio", "tab": qp.get("tab")}
    return ss[ROUTE_KEY]


def go(view: str, tab: str | None = None) -> None:
    r = route()
    r["view"] = view if view in VIEWS else "inicio"
    r["tab"] = tab
    st.query_params.clear()
    st.query_params.update({"view": r["view"], **({"tab": tab} if tab else {})})


def _on_topbar() -> None:
    a = payload("seeds_topbar")
    if a and a.get("type") == "nav":
        go(a["view"])


def fmt_time(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")
    except ValueError:
        return iso


def topbar(*, view: str, items: list[tuple[str, str]], site: str, site_title: str, save: dict, force_light: bool,
           home: str) -> None:
    component("topbar")(key="seeds_topbar", on_action_change=_on_topbar,
                        data={"version": APP_VERSION, "view": view, "items": items, "site": site,
                              "site_title": site_title, "save": save, "force_light": force_light, "home": home})
