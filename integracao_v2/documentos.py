"""Documentos científicos DERIVADOS de uma rodada do motor V2 (UI-FINISH-01, ponto 6): relatório PDF, ZIP de figuras
e planilha Excel.

Por que existe: os geradores do Piso 2D-B (``seeds2/report/run_pdf.py``, ``xlsx.py``, ``figures.py``) leem o contrato
de dados do motor V1.6 (``entradas/missao.csv``, ``saidas/despacho_ems.csv``, ``saidas/relatorio_ems.json``) e
RECUSAM rodadas V2 (``dossier.require_complete``) — documentado em ``CLAUDE.md`` («Relatórios 2D-B não cobrem rodadas
V2»). Este módulo NÃO cria uma segunda arquitetura documental: reutiliza o MESMO dossiê (``seeds2.report.dossier``:
identidade, versão do cenário e revisão do inventário com impressões digitais conferidas, SHA-256 de cada dado), o MESMO
desenho de figuras (``figures.render`` Plotly → matplotlib, PNG 300 dpi + SVG vetorial; ``figures.figures_zip`` com
``manifest.json`` e SHA-256), o MESMO miolo do PDF (estilos, tabelas, capa, cabeçalhos, figuras vetoriais e seções
genéricas de ``run_pdf``) e o MESMO escritor de planilhas (``xlsx._Book``: double exato, ausente = célula vazia, texto
literal, divisão explícita). Muda só a LEITURA: o contrato de dados ``v2/…`` (``integracao_v2.registro``).

Garantias:

* fonte = dados PERSISTIDOS da rodada (local ou estudo arquivado); a evidência é conferida por ``registro.verificar``
  (hashes, vistas regeneradas byte a byte, reauditoria independente — a mesma verificação da Partitura); falha ⇒ nenhum
  documento. Nunca importa Pyomo/HiGHS nem chama o motor; nada é gravado;
* valores gravados SEM recálculo de indicadores (os do resumo selado); ausente = N/D (nunca zero); convenção de sinais do
  registro (descarga/importação/geração injetam; carga/exportação/demanda consomem — nunca somadas como geração);
* rodada falha/interrompida ⇒ documentos de DIAGNÓSTICO (sem resultados); ZIP de figuras recusado (não há séries);
* contexto de ENSAIO: simulação algébrica offline; dados sintéticos rotulados; não é validação física.
"""
from __future__ import annotations

import pandas as pd

from seeds2.report import dossier as D
from seeds2.report import figures as FG

from . import estrategia as E
from . import preflight as PF
from . import registro as RG

MOTOR = E.MOTOR_V2
ROTULOS = {"pdf": "GERAR RELATÓRIO PDF", "fig": "BAIXAR TODAS AS FIGURAS (ZIP)", "xlsx": "EXPORTAR TABELAS EXCEL (.xlsx)"}
ROTULOS_DIAG = {"pdf": "GERAR DIAGNÓSTICO PDF", "fig": "BAIXAR TODAS AS FIGURAS (ZIP)",
                "xlsx": "EXPORTAR DIAGNÓSTICO EXCEL (.xlsx)"}
AJUDAS = {"pdf": "Relatório da RODADA V2 (não da configuração da microrrede): identificação, configuração, condições "
                 "iniciais, método e escopo do EMS hierárquico MILP–MPC, resultados gravados com figuras, armazenamento, "
                 "advertências do preflight, discussão factual, procedência (SHA-256) e limitações. Não executa o motor.",
          "fig": "ZIP com todas as figuras científicas derivadas desta rodada em PNG (300 dpi) e SVG vetorial + manifest.json "
                 "com SHA-256 de cada arquivo e dos dados de origem. Figuras de publicação (fundo claro).",
          "xlsx": "Planilha .xlsx com as tabelas gravadas (intervalos, fronteiras, janelas, planos), indicadores selados, "
                  "configuração, procedência e dicionário de dados. Números com a precisão do double (17 algarismos); o "
                  "Microsoft Excel garante 15 — reprodução exata: CSVs / .seeds2study.zip."}


# ====================================================================== leitura verificada
def carregar(source, run_uid: str):
    """Dossiê da rodada V2 (identidade e integridade do 2D-B) + verificação da evidência V2 (rodada concluída)."""
    d = D.load(source, run_uid)
    D.require_complete(d, engine=MOTOR)
    v = None
    if d.concluded:
        v = RG.verificar(source, d.run)
        if not v.ok:
            falhas = [txt for ok, txt in v.itens if not ok]
            raise D.DossierIntegrityError("A evidência V2 desta rodada NÃO passou na verificação (hashes, vistas "
                                          "regeneradas, reauditoria): " + "; ".join(falhas[:4]) + ". Nenhum documento é gerado.")
    return d, v


def _nomes(d) -> dict:
    eqs = ((d.scenario or {}).get("inventory_ref") or {}).get("equipment") or {}
    return {eid: (ref.get("name") or eid) + (f" ({ref['tag']})" if ref.get("tag") else "") for eid, ref in eqs.items()}


def _nome(nomes: dict, uid: str) -> str:
    base, _, unid = uid.partition("#")
    return nomes.get(base, base) + (f" · unidade {unid}" if unid else "")


def _curto(d, uid: str) -> str:
    """Rótulo CURTO para legendas (TAG do inventário, ou arranjo FV): o nome completo fica na legenda da figura no PDF,
    no manifesto e na planilha."""
    eqs = ((d.scenario or {}).get("inventory_ref") or {}).get("equipment") or {}
    base, _, unid = uid.partition("#")
    ref = eqs.get(base) or {}
    txt = ref.get("tag") or (ref.get("name") or "")[:16] or (("FV " + base[4:12]) if base.startswith("arr-") else base[:14])
    return txt + (f"#{unid}" if unid else "")


def _uids(cols, sufixo: str) -> list[str]:
    return [c[: -len(sufixo)] for c in cols if c.endswith(sufixo)]


def tabelas(d) -> tuple[pd.DataFrame, pd.DataFrame]:
    return d.table(RG.N_INTERVALOS), d.table(RG.N_FRONTEIRAS)


# ====================================================================== figuras (dados gravados)
COR = {"dem": "#1F2933", "prev": "#8A94A3", "imp": "#C2364A", "exp": "#E07B39", "desc": "#7A63E0", "carga": "#B9A8F0",
       "ren": "#C98A00", "vert": "#E3B341", "fc": "#1F9E8F", "custo": "#0E5E66", "tarifa": "#2F6FED"}


def _instantes(it: pd.DataFrame):
    ini = pd.to_datetime(it["inicio_utc"], utc=True).dt.tz_localize(None)
    fim = pd.to_datetime(it["fim_utc"], utc=True).dt.tz_localize(None)
    return list(ini), list(fim)


def _degraus(ini, fim, vals) -> tuple[list, list]:
    """Média de intervalo = segmento horizontal em [início, fim); ausente (N/D) = lacuna, nunca zero."""
    xs, ys = [], []
    for a, b, v in zip(ini, fim, vals):
        y = None if v is None or (isinstance(v, float) and v != v) else float(v)
        xs += [a, b, b]
        ys += [y, y, None]
    return xs, ys


def _sub(d, it) -> str:
    from html import escape

    mis = (d.summary or {}).get("mission") or {}
    return escape(f"Rodada {d.run_uid[:8]} · {d.scenario_name} v{d.run.scenario_version} · {len(it)} intervalos de "
                  f"{mis.get('delta_min', '?')} min · N = {mis.get('N', '?')} · m = {mis.get('m', '?')} · H_L = "
                  f"{mis.get('H_L', '?')} · instantes em UTC")


def figuras(d) -> list[FG.FigureSpec]:
    """Figuras científicas da rodada V2 — só o que os dados gravados sustentam (nada é sintetizado)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if not d.concluded:
        return []
    it, fr = tabelas(d)
    nomes = _nomes(d)
    ini, fim = _instantes(it)
    sub = _sub(d, it)
    specs: list[FG.FigureSpec] = []
    bats, rens, gers = _uids(it.columns, "|P_c_kW"), _uids(it.columns, "|P_R_kW"), _uids(it.columns, "|p_kW")
    pcc = "pcc_importacao_realizada_kW" in it.columns
    paineis = ["Demanda [kW]"] + (["PCC — importação injeta · exportação consome [kW]"] if pcc else []) \
        + (["Bateria(s) — descarga injeta · carga consome [kW]"] if bats else []) \
        + (["Renováveis — aproveitada × vertida [kW]"] if rens else []) + (["PEMFC — potência líquida [kW]"] if gers else [])
    fig = make_subplots(rows=len(paineis), cols=1, shared_xaxes=True, subplot_titles=paineis, vertical_spacing=0.06)

    def linha(row, col, nome, cor, dash=None):
        x, y = _degraus(ini, fim, it[col].tolist())
        fig.add_scatter(x=x, y=y, name=nome, mode="lines", line={"color": cor, "width": 2, "dash": dash}, row=row, col=1)
    r = 1
    linha(r, "demanda_realizada_kW", "Demanda realizada", COR["dem"])
    linha(r, "demanda_prevista_kW", "Demanda prevista", COR["prev"], "dot")
    if "demanda_nao_atendida_kW" in it.columns:
        linha(r, "demanda_nao_atendida_kW", "Não atendida", "#B42335", "dash")
    if pcc:
        r += 1
        linha(r, "pcc_importacao_realizada_kW", "Importação (injeta)", COR["imp"])
        linha(r, "pcc_exportacao_realizada_kW", "Exportação (consome)", COR["exp"], "dash")
    if bats:
        r += 1
        for b in bats:
            linha(r, f"{b}|P_d_kW", f"Descarga {_curto(d, b)}", COR["desc"])
            linha(r, f"{b}|P_c_kW", f"Carga {_curto(d, b)} (consome)", COR["carga"], "dash")
    if rens:
        r += 1
        for u in rens:
            linha(r, f"{u}|P_R_kW", f"Aproveitada {_curto(d, u)}", COR["ren"])
            if f"{u}|vertimento_kW" in it.columns:
                linha(r, f"{u}|vertimento_kW", f"Vertida {_curto(d, u)}", COR["vert"], "dash")
    if gers:
        r += 1
        for u in gers:
            linha(r, f"{u}|p_kW", f"PEMFC {_curto(d, u)}", COR["fc"])
    fig.update_layout(title=f"Demanda e potência por recurso — médias de intervalo<br><span>{sub}</span>",
                      height=180 + 150 * len(paineis))
    fig.update_xaxes(title_text="instante (UTC)", row=len(paineis), col=1)
    fontes = [RG.N_INTERVALOS]
    specs.append(FG.FigureSpec("01_demanda_potencia_por_recurso", "Demanda e potência por recurso",
                               "Médias de intervalo GRAVADAS [kW] no barramento equivalente, por recurso e por UID, em "
                               "painéis separados (convenção do registro: descarga/importação/geração injetam; "
                               "carga/exportação/demanda consomem — nunca somadas como geração). Lacuna = dado ausente.",
                               "kW", fontes, fig, 180 + 150 * len(paineis)))
    fx = pd.to_datetime(fr["instante_utc"], utc=True).dt.tz_localize(None).tolist()
    for i, b in enumerate(_uids(fr.columns, "|energia_kWh"), start=1):
        f2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                           subplot_titles=["Energia interna nas fronteiras [kWh]", "Estado de carga nas fronteiras [%]"])
        f2.add_scatter(x=fx, y=fr[f"{b}|energia_kWh"].tolist(), name="Energia interna", mode="lines+markers",
                       line={"color": COR["desc"], "width": 2}, marker={"size": 5}, row=1, col=1)
        if f"{b}|soc" in fr.columns:
            f2.add_scatter(x=fx, y=[None if v != v else 100.0 * float(v) for v in fr[f"{b}|soc"].tolist()],
                           name="SOC (fração × 100)", mode="lines+markers", line={"color": "#5B4BB7", "width": 2},
                           marker={"size": 5}, row=2, col=1)
        f2.update_layout(title=f"Bateria {_nome(nomes, b)} — estados de fronteira (N + 1 pontos)<br><span>{sub}</span>",
                         height=420)
        f2.update_xaxes(title_text="instante da fronteira (UTC)", row=2, col=1)
        specs.append(FG.FigureSpec(f"{1 + i:02d}_bateria_{b.replace('|', '_').replace('#', '_')}", f"Bateria {_nome(nomes, b)}",
                                   "Energia interna e SOC GRAVADOS nas N + 1 fronteiras de estado (grandezas de estado, "
                                   "diferentes da potência média de intervalo).", "kWh; %", [RG.N_FRONTEIRAS], f2, 420))
    n = len(specs)
    cols_t = [c for c in ("tarifa_importacao_decisao_R_kWh", "tarifa_exportacao_decisao_R_kWh") if c in it.columns]
    f3 = make_subplots(rows=2 if cols_t else 1, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                       subplot_titles=(["Tarifa de decisão do PCC [R$/kWh]"] if cols_t else [])
                       + ["Custo realizado por intervalo e acumulado [R$]"])
    rr = 1
    if cols_t:
        for c, nm, cor in (("tarifa_importacao_decisao_R_kWh", "Tarifa importação", COR["tarifa"]),
                           ("tarifa_exportacao_decisao_R_kWh", "Remuneração exportação", COR["exp"])):
            if c in it.columns:
                x, y = _degraus(ini, fim, it[c].tolist())
                f3.add_scatter(x=x, y=y, name=nm, mode="lines", line={"color": cor, "width": 2}, row=1, col=1)
        rr = 2
    x, y = _degraus(ini, fim, it["custo_realizado_intervalo_R"].tolist())
    f3.add_scatter(x=x, y=y, name="Custo do intervalo", mode="lines", line={"color": COR["custo"], "width": 2},
                   row=rr, col=1)
    f3.add_scatter(x=fim, y=it["custo_realizado_acumulado_R"].tolist(), name="Custo acumulado (fim do intervalo)",
                   mode="lines+markers", line={"color": "#1F2933", "width": 1.6, "dash": "dot"}, marker={"size": 4},
                   row=rr, col=1)
    f3.update_layout(title=f"Tarifas de decisão e custo realizado<br><span>{sub}</span>", height=430 if cols_t else 300)
    f3.update_xaxes(title_text="instante (UTC)", row=rr, col=1)
    specs.append(FG.FigureSpec(f"{n + 1:02d}_tarifas_e_custo_realizado", "Tarifas de decisão e custo realizado",
                               "Tarifa vigente na DECISÃO de cada intervalo e custo REALIZADO gravado (por intervalo e "
                               "acumulado); o custo futuro estimado do planejador NUNCA entra no custo realizado.",
                               "R$/kWh; R$", [RG.N_INTERVALOS], f3, 430 if cols_t else 300))
    return specs


def zip_figuras(source, run_uid: str, progress=None) -> tuple[str, bytes]:
    d, _v = carregar(source, run_uid)
    if not d.concluded:
        raise FG.FigureError("Rodada não concluída: não há séries de resultado gravadas para figuras.")
    data, _ = FG.figures_zip(d, specs=figuras(d), generated_at=D.utc_now(), progress=progress)
    return D.safe_stem(d, "figuras") + ".zip", data


# ====================================================================== PDF
def _dict_txt(x) -> str:
    from seeds2.report.run_pdf import t

    if isinstance(x, dict):
        return t("; ".join(f"{k} = {v}" for k, v in x.items())) or "—"
    return t(x) if x not in (None, "") else "—"


def pdf(source, run_uid: str, progress=None) -> tuple[str, bytes]:
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import BaseDocTemplate, CondPageBreak, Frame, NextPageTemplate, PageBreak, PageTemplate, Spacer

    from seeds2 import APP_NAME, APP_VERSION
    from seeds2.report import run_pdf as RP

    say = progress or (lambda _m: None)
    say("Lendo os dados gravados da rodada, conferindo SHA-256 e verificando a evidência V2 (sem solver)")
    d, v = carregar(source, run_uid)
    RP._fonts()
    RP.S.update(RP._styles())
    t, P, num = RP.t, RP.P, RP.num
    generated_at = D.utc_now()
    reg: list = []
    story: list = RP._cover(d, generated_at) + [NextPageTemplate("page"), PageBreak()]
    mis = (d.summary or {}).get("mission") or {}
    exe = (d.summary or {}).get("execution") or {}
    sint = bool(mis.get("dados_sinteticos"))
    if d.concluded:
        say("Preparando figuras a partir das séries gravadas")
        figs = figuras(d)
        it, fr = tabelas(d)
        story += RP.section(1, "Resumo executivo", "valores selados da rodada · motor V2")
        story.append(RP.note("<b>Ensaio — simulação OFFLINE algébrica de laço fechado</b> (EMS hierárquico MILP–MPC: o "
                             "controlador decide com a previsão declarada e uma planta algébrica realiza cada intervalo). "
                             "Não é controle de equipamentos, telemetria nem validação física."
                             + (" <b>A rodada usa dados SINTÉTICOS rotulados.</b>" if sint else ""), "warn"))
        story.append(Spacer(1, 3 * mm))
        story.append(RP.kpis([
            ("Custo realizado", num(mis.get("custo_realizado_total_R"), 2, "R$"), "selado; sem valor futuro"),
            ("Energia demandada", num(mis.get("energia_demanda_kWh"), 2, "kWh"), "realizada"),
            ("Energia não atendida", num(mis.get("energia_nao_atendida_kWh"), 2, "kWh"), "déficit"),
            ("Intervalos aplicados", f"{mis.get('intervalos_aplicados', '—')} de {mis.get('intervalos_missao', '—')}",
             "missão completa" if mis.get("missao_completa") else "missão INCOMPLETA"),
            ("Energia importada", num(mis.get("energia_importada_kWh"), 2, "kWh"), "PCC"),
            ("Energia exportada", num(mis.get("energia_exportada_kWh"), 2, "kWh"), "PCC"),
            ("Janelas MPC", str(mis.get("janelas", "—")), "decisões"),
            ("Auditoria integral", "aprovada" if exe.get("auditoria_integral_aprovada") else "NÃO aprovada", "independente")]))
        ac = exe.get("aceitacao") or {}
        if ac:
            story.append(P("Aceitação registrada — três dimensões SEPARADAS", "h2"))
            linhas = [(f"Aceitação {nome}", f"<b>{t((ac.get(k) or {}).get('estado'))}</b> — critério: {t((ac.get(k) or {}).get('criterio'))}"
                       + (f" — {t(ac[k]['motivo'])}" if (ac.get(k) or {}).get("motivo") else ""))
                      for k, nome in (("algebrica", "algébrica"), ("dinamica", "dinâmica"), ("fisica", "física")) if k in ac]
            story.append(RP.kv(linhas + [("Rótulo", t(ac.get("rotulo")))], (0.24, 0.76)))
        story += RP._configuration(d, 2)
        story += RP._initial(d, 3)
        story += RP.section(4, "Método e escopo", "EMS hierárquico MILP–MPC · motor V2 experimental")
        story.append(P(t((d.manifest or {}).get("scope") or PF.ESCOPO)))
        story.append(RP.kv([("Motor", t(((d.manifest or {}).get("engine") or {}).get("label") or MOTOR)),
                            ("Formulação", t(mis.get("formulacao"))), ("Passo Δ", f"{mis.get('delta_min', '—')} min"),
                            ("Horizonte curto N / bloco aplicado m", f"{mis.get('N', '—')} / {mis.get('m', '—')}"),
                            ("Horizonte longo H_L", str(mis.get("H_L", "—"))), ("PCC", t(mis.get("pcc_modo"))),
                            ("Sinal de valor futuro (contagens)", _dict_txt(mis.get("sinal_valor_futuro"))),
                            ("Solver (na execução)", _dict_txt(mis.get("solver")))]))
        story.append(P("Convenções do registro", "h2"))
        story += RP.bullets([f"<b>{t(k)}:</b> {t(x)}" for k, x in RG.CONVENCOES.items()])
        story += [CondPageBreak(150 * mm)] + RP.section(5, "Resultados", "séries gravadas · figuras derivadas")
        for i, spec in enumerate(figs, start=1):
            if spec.data_sources == [RG.N_FRONTEIRAS]:
                continue
            story.append(RP.figure_block(spec, i, reg))
        rows = [[k, num(mis.get(k), 4)] for k in ("custo_realizado_total_R", "gasto_importacao_R", "receita_exportacao_R",
                                                   "energia_demanda_kWh", "energia_atendida_kWh", "energia_nao_atendida_kWh",
                                                   "energia_importada_kWh", "energia_exportada_kWh")]
        rows += [[f"componente · {k}", num(x, 4)] for k, x in (mis.get("custo_realizado_componentes_R") or {}).items()]
        story.append(P("Indicadores selados (sem recálculo)", "h2"))
        story.append(RP.table(["indicador (chave do resumo selado)", "valor"], rows, [3.2, 1.2], mono_cols=(0,), align_right=(1,)))
        story += [CondPageBreak(130 * mm)] + RP.section(6, "Armazenamento", "estados de fronteira")
        for i, spec in enumerate(figs, start=1):
            if spec.data_sources == [RG.N_FRONTEIRAS]:
                story.append(RP.figure_block(spec, i, reg))
        brows = []
        for b in _uids(fr.columns, "|energia_kWh"):
            e = fr[f"{b}|energia_kWh"].tolist()
            brows.append([_nome(_nomes(d), b), num(e[0], 3, "kWh"), num(e[-1], 3, "kWh"), num(min(e), 3, "kWh"),
                          num(max(e), 3, "kWh")])
        if brows:
            story.append(RP.table(["Banco", "Energia inicial", "Energia final", "Mínimo", "Máximo"], brows,
                                  [2.2, 1, 1, 1, 1], align_right=(1, 2, 3, 4)))
        story += RP.section(7, "Advertências do preflight", "registradas na versão executada")
        pre = d.json_data(RG.N_PREFLIGHT) or {}
        itens = [i for i in (pre.get("items") or []) if i.get("level") in (PF.WARNING, PF.INFO, PF.ERROR)]
        story += RP.bullets([f"[{t(PF.LEVEL_LABELS.get(i['level'], i['level']))}] <b>{t(PF.AREA_LABELS.get(i.get('area'), i.get('area')))}:</b> "
                             f"{t(i.get('message'))}" for i in itens]) or [P("Nenhuma advertência registrada.")]
        story += RP.section(8, "Discussão factual", "apenas o que foi gravado")
        story += RP.bullets([
            f"A missão aplicou {t(mis.get('intervalos_aplicados'))} de {t(mis.get('intervalos_missao'))} intervalos em "
            f"{t(mis.get('janelas'))} janela(s) do MPC; situação registrada: {t(mis.get('situacao_missao'))}.",
            f"Custo realizado selado: {num(mis.get('custo_realizado_total_R'), 2, 'R$')}; o custo futuro estimado pelo "
            "planejador não está incluído (registro: custo_realizado_inclui_valor_futuro = "
            f"{t(mis.get('custo_realizado_inclui_valor_futuro'))}).",
            f"Energia demandada {num(mis.get('energia_demanda_kWh'), 2, 'kWh')}, atendida "
            f"{num(mis.get('energia_atendida_kWh'), 2, 'kWh')}, não atendida {num(mis.get('energia_nao_atendida_kWh'), 2, 'kWh')}.",
            "Este documento descreve valores registrados; não atribui causas às decisões do controlador."])
    else:
        story += RP._diagnostic(d)
        story += RP._configuration(d, 2)
        story += RP._initial(d, 3)
    n0 = 9 if d.concluded else 4
    story += RP.section(n0, "Procedência", "identidade, SHA-256 e verificação")
    story.append(RP.kv([("Rodada", d.run_uid), ("Microrrede", f"{d.microgrid.get('name')} · {d.run.microgrid_uid}"),
                        ("Cenário", f"{d.scenario_name} · v{d.run.scenario_version} · {d.run.scenario_fingerprint}"),
                        ("Inventário", f"revisão {d.run.config_revision} · {d.run.config_fingerprint}"),
                        ("Origem dos dados", D.ORIGIN_LABELS[d.kind]), ("Gerado em", generated_at)], mono=False))
    story.append(RP.table(["Dado gravado", "SHA-256", "bytes"],
                          [[n, d.run.data[n]["sha256"], d.run.data[n]["size"]] for n in d.data_names()], [1.6, 3.2, 0.6],
                          mono_cols=(0, 1), align_right=(2,)))
    if v is not None:
        story.append(P("Verificação da evidência V2 nesta leitura (sem solver)", "h2"))
        story += RP.bullets([("✓ " if ok else "✕ ") + t(txt) for ok, txt in v.itens])
    story += RP.section(n0 + 1, "Limitações", "alcance científico")
    story += RP.bullets([t(PF.ESCOPO)] + [t(x) for x in (RG.LIMITACOES if isinstance(RG.LIMITACOES, (list, tuple)) else [RG.LIMITACOES])]
                        + ["Figuras e tabelas são DERIVADAS dos dados gravados; a fonte integral é o pacote .seeds2study.zip."])
    say("Montando o documento")
    buf = io.BytesIO()
    meta = {"header": "SEEDS2 · " + ("RELATÓRIO DA RODADA · EMS V2" if d.concluded else "DIAGNÓSTICO DA RODADA · EMS V2"),
            "right": f"{d.microgrid.get('name')} · {d.scenario_name} v{d.run.scenario_version}", "run": d.run_uid,
            "generated": generated_at}
    cover, page = RP._decor(meta)
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=RP.MX, rightMargin=RP.MX, topMargin=RP.MT, bottomMargin=RP.MB,
                          title=f"SEEDS2 — {'Relatório' if d.concluded else 'Diagnóstico'} da rodada V2 · {d.scenario_name} "
                                f"v{d.run.scenario_version}", author=f"{APP_NAME} {APP_VERSION}", subject=f"Rodada {d.run_uid}",
                          creator=f"{APP_NAME} {APP_VERSION}")
    frame = Frame(RP.MX, RP.MB, RP.TEXT_W, RP.PAGE_H - RP.MT - RP.MB, id="f", leftPadding=0, rightPadding=0, topPadding=0,
                  bottomPadding=0)
    doc.addPageTemplates([PageTemplate("cover", [frame], onPage=cover), PageTemplate("page", [frame], onPage=page)])
    doc.build(story, canvasmaker=RP._NumberedCanvas)
    out = buf.getvalue()
    if reg:
        out = RP._merge_figures(out, reg, say)
    return D.safe_stem(d, "relatorio" if d.concluded else "diagnostico") + ".pdf", out


# ====================================================================== Excel
_UNIDADES = (("_R_kWh", "R$/kWh"), ("_kWh", "kWh"), ("_kW", "kW"), ("_kg_h", "kg/h"), ("_kg", "kg"), ("_R", "R$"),
             ("|soc", "fração 0–1"), ("_utc", "instante UTC (ISO 8601)"), ("_local", "relógio de parede do fuso da missão"),
             ("disponibilidade", "fração 0–1"))


def _unidade(col: str) -> str:
    for suf, u in _UNIDADES:
        if col.endswith(suf) or (suf.startswith("|") and col.endswith(suf)) or (suf == "disponibilidade" and suf in col):
            return u
    return "adimensional / índice"


def xlsx(source, run_uid: str, progress=None) -> tuple[str, bytes, list[str]]:
    import io

    from seeds2.report import xlsx as XL

    say = progress or (lambda _m: None)
    say("Lendo os dados gravados da rodada, conferindo SHA-256 e verificando a evidência V2 (sem solver)")
    d, v = carregar(source, run_uid)
    generated_at = D.utc_now()
    book = XL._Book()
    index_ws = book.wb.create_sheet(book.sheet_name("00 Índice"))
    book.kv_sheet("01 Identificação", "Identificação da rodada V2 e procedência", XL._identification(d, generated_at),
                  note="Identificadores científicos preservados da rodada original (motor V2 · MILP–MPC hierárquico).")
    tabs: list[tuple[str, str, pd.DataFrame]] = []
    mis = (d.summary or {}).get("mission") or {}
    if d.concluded:
        rows = [("§", "Resumo selado da missão (valores gravados; nenhum recálculo)")] + \
               [(k, x) for k, x in XL._flatten(mis)] + \
               [("§", "Execução e aceitação")] + [(k, x) for k, x in XL._flatten((d.summary or {}).get("execution") or {})]
        book.kv_sheet("02 Indicadores", "Indicadores selados da rodada V2", rows,
                      note="Valores do resumo SELADO da rodada; ausente = vazio. O custo futuro estimado nunca é custo realizado.")
        for nome, titulo, conteudo in ((RG.N_INTERVALOS, "06 Intervalos", "Intervalos aplicados (v2/intervalos.csv)"),
                                      (RG.N_FRONTEIRAS, "07 Fronteiras", "Estados de fronteira (v2/fronteiras.csv)"),
                                      (RG.N_JANELAS, "08 Janelas", "Janelas do MPC (v2/janelas.csv)"),
                                      (RG.N_PLANOS, "09 Planos", "Planos de cada janela (v2/planos.csv)")):
            tabs.append((titulo, conteudo, d.table(nome)))
        cells = sum(df.shape[0] * df.shape[1] for _, _, df in tabs)
        if cells > XL.MAX_CELLS:
            raise XL.WorkbookLimitError(f"As tabelas desta rodada somam {cells:,} células (limite: {XL.MAX_CELLS:,}). "
                                        "Use o pacote .seeds2study.zip (CSVs originais).")
    else:
        err = d.run.error or {}
        book.kv_sheet("02 Diagnóstico", "Diagnóstico — rodada NÃO concluída (sem resultados)",
                      [("Estado", d.state_label), ("Tipo", err.get("kind")), ("Mensagem", err.get("message")),
                       ("Último progresso", str(d.run.progress or {}))],
                      note="Rodada não concluída: nenhuma série de resultado foi gravada; nenhum indicador é apresentado.")
    head, rows = XL._equipment_rows(d)
    XL._table_sheet_simple(book, "03 Equipamentos", f"Inventário de referência (revisão {d.run.config_revision})", head, rows)
    head, rows = XL._initial_rows(d)
    XL._table_sheet_simple(book, "04 Condições iniciais", "Estados iniciais declarados no cenário", head, rows)
    estr = (d.scenario or {}).get(E.CHAVE_BLOCO) or {}
    book.kv_sheet("05 Estratégia V2", "Estratégia MILP–MPC declarada (versão executada)", list(XL._flatten(estr)),
                  note="Declarações da versão imutável do cenário, com procedência; nada é preenchido.")
    nomes = _nomes(d)
    for titulo, conteudo, df in tabs:
        say(f"Gravando {conteudo}")
        com = {c: f"Unidade: {_unidade(c)}" + (f"\nRecurso: {_nome(nomes, c.split('|')[0])} ({c.split('|')[0]})" if "|" in c else "")
               for c in df.columns}
        book.table_sheet(titulo, conteudo, df, tz="UTC", comments=com)
    say("Gravando procedência e dicionário")
    prov = XL._provenance_rows(d)
    if v is not None:
        prov += [("§", "Verificação da evidência V2 nesta leitura (sem solver)")] + [("✓" if ok else "✕", txt, None, None)
                                                                                   for ok, txt in v.itens]
    book.kv_sheet("10 Procedência", "Procedência, hashes e manifesto da rodada", prov,
                  headers=("Campo / dado", "Valor / SHA-256", "Tamanho (bytes) / pontos", "Tipo / rótulo"),
                  widths=(58, 70, 20, 30), note="Hashes SHA-256 dos dados originais; o manifesto não é reescrito.")
    dic = [[titulo, str(c), _unidade(str(c)), _nome(nomes, str(c).split("|")[0]) if "|" in str(c) else "",
            str(df[c].dtype), int(df[c].isna().sum())] for titulo, _, df in tabs for c in df.columns]
    XL._table_sheet_simple(book, "11 Dicionário de dados", "Unidade e recurso de cada coluna (convenções do registro V2)",
                           ["folha", "coluna", "unidade", "recurso (inventário)", "tipo", "valores ausentes"], dic)
    stt = book.stats
    warnings = list(stt.split)
    if stt.nan:
        warnings.append(f"{stt.nan} valor(es) ausente(s) (N/D) gravado(s) como célula VAZIA (nunca zero).")
    if stt.over15:
        warnings.append(f"{stt.over15} valor(es) com mais de {XL.EXCEL_SIG_DIGITS} algarismos significativos: preservados no "
                        ".xlsx (leitura por Python exata), mas o Microsoft Excel pode arredondá-los ao abrir/salvar.")
    ws = index_ws
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 30, 100
    ws.append([book.text(ws, "SEEDS2 — Planilha científica da rodada (motor V2)", font=XL.TITLE_FONT)])
    ws.append([book.text(ws, f"{d.scenario_name} · versão {d.run.scenario_version} · rodada {d.run_uid} · {d.state_label}",
                         font=XL.META_FONT)])
    ws.append([book.text(ws, D.DERIVED_NOTE, font=XL.NOTE_FONT)])
    ws.append([book.text(ws, XL.PRECISION_NOTE, font=XL.NOTE_FONT)])
    ws.append([book.text(ws, "Convenção do registro V2: " + "; ".join(f"{k}: {x}" for k, x in RG.CONVENCOES.items()),
                         font=XL.NOTE_FONT)])
    ws.append([book.text(ws, "Ensaio — simulação offline algébrica; dados sintéticos rotulados na procedência; não é validação "
                             "física." if mis.get("dados_sinteticos") else "Ensaio — simulação offline algébrica; não é "
                             "validação física.", font=XL.NOTE_FONT)])
    ws.append([])
    hc = [book.text(ws, h, font=XL.HEAD_FONT) for h in ("Folha", "Conteúdo", "Linhas", "Colunas")]
    for c in hc:
        c.fill = XL.HEAD_FILL
    ws.append(hc)
    for name, content, n, k in stt.sheets:
        ws.append([book.text(ws, name), book.text(ws, content), book.number(ws, n), book.number(ws, k)])
    ws.append([])
    ws.append([book.text(ws, "Avisos da exportação", font=XL.META_FONT)])
    for w in warnings or ["Nenhum: todas as tabelas foram representadas integralmente."]:
        ws.append([book.text(ws, "•"), book.text(ws, w)])
    say("Compactando o arquivo .xlsx")
    buf = io.BytesIO()
    book.wb.properties.creator = f"{D.APP_NAME} {D.APP_VERSION}"
    book.wb.properties.title = f"SEEDS2 · rodada V2 {d.run_uid}"
    book.wb.save(buf)
    return D.safe_stem(d, "dados" if d.concluded else "diagnostico") + ".xlsx", buf.getvalue(), warnings


# ====================================================================== ponto único (painel de exportações)
def gerar(source, run_uid: str, kind: str, progress=None) -> tuple[str, bytes, str, list[str], str]:
    """Mesmo contrato de ``seeds2.ui.report_exports.generate`` (nome, bytes, mime, avisos, gerado em)."""
    from seeds2.ui.report_exports import KINDS

    when = D.utc_now()
    if kind == "pdf":
        nome, data = pdf(source, run_uid, progress)
        return nome, data, KINDS["pdf"][1], [], when
    if kind == "xlsx":
        nome, data, avisos = xlsx(source, run_uid, progress)
        return nome, data, KINDS["xlsx"][1], avisos, when
    if kind == "fig":
        nome, data = zip_figuras(source, run_uid, progress)
        return nome, data, KINDS["fig"][1], [], when
    raise ValueError(kind)


__all__ = ["AJUDAS", "MOTOR", "ROTULOS", "ROTULOS_DIAG", "carregar", "figuras", "gerar", "pdf", "xlsx", "zip_figuras"]
