"""Ações de documentação da configuração: exportar ZIP (backup verificável) e gerar relatório técnico PDF.

Ambas usam a configuração SALVA (revisão atual), nunca a edição pendente. O ZIP é o mesmo formato de backup
seguro (SHA-256, validação, restauração atômica); o PDF é gerado localmente (reportlab), sem serviços externos.
"""
from __future__ import annotations

import streamlit as st

from seeds2.microgrid.store import StoreError, backup_filename

from . import session, shell


def export_actions(*, key: str) -> None:
    saved = session.saved()
    if saved is None:
        st.caption("Salve a configuração para exportá-la.")
        return
    if session.is_dirty():
        st.caption("Há edição pendente: os documentos abaixo refletem a revisão SALVA "
                   f"({saved.revision}), não as alterações ainda não salvas.")
    ss = st.session_state
    c1, c2 = st.columns(2, gap="large")
    with c1, st.container(border=True, key=f"{key}_zip_card"):
        st.markdown("**Configuração completa (ZIP)**")
        st.caption("Equipamentos, arranjos FV, dispositivos importados, dados de entrada, histórico e manifesto com "
                   "hashes SHA-256. Restaurável em Gestão → Histórico e backups.")
        if st.button("EXPORTAR CONFIGURAÇÃO DA MICRORREDE (ZIP)", key=f"{key}_zip", width="stretch", type="primary"):
            try:
                ss[f"{key}_zip_data"] = (saved.fingerprint, backup_filename(saved.config), session.store().export_backup())
            except StoreError as exc:
                st.error(shell.md(exc))
        z = ss.get(f"{key}_zip_data")
        if z and z[0] == saved.fingerprint:
            st.download_button("⬇ Baixar ZIP", z[2], file_name=z[1], mime="application/zip", key=f"{key}_zip_dl",
                               width="stretch")
    with c2, st.container(border=True, key=f"{key}_pdf_card"):
        st.markdown("**Relatório técnico (PDF)**")
        st.caption("Documento editorial da configuração salva: inventário, arranjos FV, curvas eólicas, baterias, PEMFC, "
                   "balanço energético, compatibilidade com a simulação e rastreabilidade.")
        if st.button("GERAR RELATÓRIO TÉCNICO (PDF)", key=f"{key}_pdf", width="stretch", type="primary"):
            from seeds2.report.pdf import build_report, report_filename

            with st.spinner("Gerando o relatório técnico…"):
                try:
                    ss[f"{key}_pdf_data"] = (saved.fingerprint, report_filename(saved.config), build_report(saved, session.store()))
                except Exception as exc:  # noqa: BLE001 — falha de geração não pode derrubar a página
                    st.error(f"Não foi possível gerar o relatório: {shell.md(exc)}")
        p = ss.get(f"{key}_pdf_data")
        if p and p[0] == saved.fingerprint:
            st.download_button("⬇ Baixar PDF", p[2], file_name=p[1], mime="application/pdf", key=f"{key}_pdf_dl",
                               width="stretch")
