"""Exportações científicas de uma rodada (Piso 2D-B) — painel comum à rodada local (Piso 2C) e à rodada de um estudo
arquivado (Piso 2D-A).

* Os documentos são produzidos SOB DEMANDA (clique), nunca a cada renderização; o resultado fica na sessão só para a
  rodada aberta (um documento por tipo) e é entregue por ``st.download_button``.
* Progresso honesto: etapas reais da geração (``st.status``), sem porcentagens inventadas.
* A fonte é a mesma de ``run_results``: ``MicrogridStore`` (rodada local) ou ``StudyView`` (estudo arquivado). Nada
  aqui chama modelos nem o otimizador; nenhum dado persistido é alterado.
Estado de sessão: ``rx_<run_uid>_<tipo>`` = (nome do arquivo, bytes, mime, avisos, gerado em).
"""
from __future__ import annotations

import io
import zipfile
from html import escape

import streamlit as st

from seeds2.microgrid.store import StoreError
from seeds2.report import dossier as D

STATE_PREFIX = "rx_"
KINDS = {
    "pdf": ("RELATÓRIO PDF", "application/pdf"),
    "xlsx": ("DADOS EXCEL", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "fig": ("FIGURAS (PNG + SVG)", "application/zip"),
}
EXCEL_PRECISION_CAPTION = (
    "Precisão do Excel: o arquivo .xlsx preserva cada número com a precisão do double persistido (até 17 algarismos; "
    "leitura exata por Python/pandas), mas o Microsoft Excel documenta precisão de 15 algarismos significativos — ao "
    "abrir, editar ou salvar no Excel, valores podem ser arredondados. Para reprodução exata, use os CSVs originais da "
    "rodada ou o pacote .seeds2study.zip.")
CSS = """
<style>
.rx-note { font-size: .82rem; opacity: .85; margin: -.2rem 0 .5rem 0; }
</style>
"""


def clear_state() -> None:
    for k in [k for k in list(st.session_state.keys()) if str(k).startswith(STATE_PREFIX)]:
        st.session_state.pop(k, None)


def _key(run_uid: str, kind: str) -> str:
    return f"{STATE_PREFIX}{run_uid}_{kind}"


def _forget_other_runs(run_uid: str) -> None:
    """Só os documentos da rodada aberta ficam na sessão (memória limitada)."""
    for k in [k for k in list(st.session_state.keys()) if str(k).startswith(STATE_PREFIX) and run_uid not in str(k)]:
        st.session_state.pop(k, None)


def generate(source, run_uid: str, kind: str, progress=None) -> tuple[str, bytes, str, list[str], str]:
    """Gera um documento derivado (sem Streamlit; usado pela interface e pelos testes)."""
    say = progress or (lambda _m: None)
    say("Lendo os dados gravados da rodada e conferindo SHA-256 e impressões digitais")
    d = D.load(source, run_uid)
    when = D.utc_now()
    if kind == "pdf":
        from seeds2.report import run_pdf

        return run_pdf.report_filename(d), run_pdf.build_report(d, generated_at=when, progress=say), KINDS[kind][1], [], when
    if kind == "xlsx":
        from seeds2.report import xlsx

        res = xlsx.build_workbook(d, generated_at=when, progress=say)
        return D.safe_stem(d, "dados" if d.concluded else "diagnostico") + ".xlsx", res.data, KINDS[kind][1], res.warnings, when
    if kind == "fig":
        from seeds2.report import figures

        data, _ = figures.figures_zip(d, generated_at=when, progress=say)
        return D.safe_stem(d, "figuras") + ".zip", data, KINDS[kind][1], [], when
    raise ValueError(kind)


def render(source, run, *, key: str) -> None:
    """Painel EXPORTAR (PDF / Excel / figuras) da rodada ``run`` lida de ``source``."""
    ss = st.session_state
    _forget_other_runs(run.run_uid)
    st.html(CSS)
    done = run.state == "concluida"
    st.markdown('<div class="sd-section">Exportações científicas</div>', unsafe_allow_html=True)
    origin = "estudo arquivado" if not hasattr(source, "start_run") else "armazenamento desta microrrede"
    st.html(f'<div class="rx-note">Documentos <b>derivados</b> desta rodada, gerados sob demanda a partir dos dados '
            f'gravados ({escape(origin)}). Gerar um documento não executa modelos nem o EMS e não altera rodadas, '
            'cenários ou estudos; o pacote <b>.seeds2study.zip</b> continua sendo a fonte portátil integral.'
            + ("" if done else " Rodada não concluída: somente documentos de <b>diagnóstico</b> (sem resultados).")
            + "</div>")
    cols = st.columns(3)
    labels = {"pdf": "EXPORTAR RELATÓRIO PDF" if done else "EXPORTAR DIAGNÓSTICO PDF",
              "xlsx": "EXPORTAR DADOS EXCEL" if done else "EXPORTAR DIAGNÓSTICO EXCEL",
              "fig": "EXPORTAR FIGURAS"}
    helps = {"pdf": "Relatório técnico-científico (capa, resumo, configuração, condições iniciais, previsões, metodologia, "
                    "resultados, armazenamento/H₂, discussão factual, procedência e limitações).",
             "xlsx": "Planilha .xlsx com todas as colunas das entradas, do despacho e dos modelos, indicadores persistidos, "
                     "configuração, procedência e dicionário de dados. Números serializados com precisão de double (17 "
                     "algarismos); o Microsoft Excel garante 15 — reprodução exata: CSVs / .seeds2study.zip.",
             "fig": "ZIP com as figuras em PNG (300 dpi) e SVG vetorial + manifest.json com SHA-256 de cada arquivo."}
    clicked = None
    for col, kind in zip(cols, ("pdf", "xlsx", "fig")):
        with col:
            disabled = kind == "fig" and not done
            if st.button(labels[kind], key=f"{key}_rx_{kind}", width="stretch", disabled=disabled, help=helps[kind]
                         if not disabled else "Rodada sem séries de resultados: não há figuras a exportar."):
                clicked = kind
    if clicked:
        with st.status(f"Gerando {KINDS[clicked][0].lower()}…", expanded=True) as box:
            try:
                ss[_key(run.run_uid, clicked)] = generate(source, run.run_uid, clicked, progress=box.write)
                box.update(label=f"{KINDS[clicked][0]} pronto para download.", state="complete", expanded=False)
            except D.DossierIntegrityError as exc:
                ss.pop(_key(run.run_uid, clicked), None)
                box.update(label="Geração recusada: dados inconsistentes ou corrompidos.", state="error")
                st.error(f"Nenhum documento foi gerado: {exc}")
            except (StoreError, ValueError) as exc:
                ss.pop(_key(run.run_uid, clicked), None)
                box.update(label="Não foi possível gerar o documento.", state="error")
                st.error(str(exc))
            except Exception as exc:                    # noqa: BLE001 — falha inesperada: mensagem legível, sem documento
                ss.pop(_key(run.run_uid, clicked), None)
                box.update(label="Falha inesperada ao gerar o documento.", state="error")
                st.error(f"Nenhum documento foi gerado ({type(exc).__name__}: {str(exc)[:300]}). Os dados da rodada não "
                         "foram alterados.")
    for kind in ("pdf", "xlsx", "fig"):
        item = ss.get(_key(run.run_uid, kind))
        if not item:
            continue
        name, data, mime, warnings, when = item
        c1, c2 = st.columns([3, 2], vertical_alignment="center")
        c1.caption(f"{name} · {len(data) / 1024:,.0f} KiB · gerado em {when}".replace(",", "."))
        c2.download_button(f"BAIXAR {KINDS[kind][0]}", data=data, file_name=name, mime=mime, key=f"{key}_dl_{kind}",
                           width="stretch", type="primary", on_click="ignore")
        if kind == "xlsx":
            st.caption(EXCEL_PRECISION_CAPTION)
        for w in warnings:
            st.warning(w)
        if kind == "fig":
            zf = zipfile.ZipFile(io.BytesIO(data))
            files = [x for x in zf.namelist() if x.startswith("figuras/")]
            a, b = st.columns([3, 2], vertical_alignment="bottom")
            pick = a.selectbox("Figura individual", files, format_func=lambda n: n.split("/", 1)[1], key=f"{key}_rx_pick")
            b.download_button("BAIXAR FIGURA SELECIONADA", data=zf.read(pick), file_name=pick.rsplit("/", 1)[1],
                              mime="image/png" if pick.endswith(".png") else "image/svg+xml", key=f"{key}_dl_one",
                              width="stretch", on_click="ignore")


__all__ = ["EXCEL_PRECISION_CAPTION", "KINDS", "STATE_PREFIX", "clear_state", "generate", "render"]
