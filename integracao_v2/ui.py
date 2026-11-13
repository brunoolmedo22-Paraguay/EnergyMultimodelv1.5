"""Controles MÍNIMOS do motor V2 no Centro de Operação (Piso 3D-A) — importado só pela interface Streamlit.

* etapa 03: seleção EXPLÍCITA do motor e formulário da estratégia ``milp_mpc`` (campos científicos começam vazios);
* etapa 04: relatório do preflight V2 da versão SALVA, EXECUTAR (rodada em thread própria) e progresso real;
* rodada: leitura SOMENTE dos dados gravados (``MicrogridStore`` ou estudo arquivado), com a VERIFICAÇÃO da evidência
  (hashes, vistas regeneradas, auditoria integral) — nenhuma função daqui chama o otimizador ao abrir uma rodada.

Não é o dashboard operacional (3D-B) nem o motor gráfico JS/SVG: só tabelas, dois gráficos Plotly simples e downloads
dos dados originais, o suficiente para operar e auditar o percurso.
"""
from __future__ import annotations

import json
import re
from html import escape

import streamlit as st

from seeds2.microgrid.store import RunBusyError, StoreError
from seeds2.operation import initialization as I
from seeds2.operation import scenarios as S
from seeds2.ui import forms, session, shell

from . import estrategia as E
from . import preflight as PF
from . import registro as RG

MOTOR_V2 = E.MOTOR_V2
VAZIO = "— não declarado —"
TONS = {PF.ERROR: "bad", PF.WARNING: "warn", PF.OK: "ok", PF.INFO: "off"}
GLIFOS = {PF.ERROR: "✕", PF.WARNING: "!", PF.OK: "✓", PF.INFO: "i"}
FASES = {"fila": "Aguardando o motor (outra execução neste servidor)", "montagem": "Montando a missão e verificando o solver",
         "missao": "Missão MILP–MPC (janela a janela)", "auditoria": "Auditoria integral independente da missão",
         "gravando": "Gravando registros selados e vistas", "preparando": "Preparando a rodada", "concluida": "Concluída"}


def _ss():
    return st.session_state


def e_v2(run) -> bool:
    return RG.e_v2(run)


def motor(doc) -> str:
    return E.motor_selecionado(doc)


def custo_texto(run) -> str:
    """Texto curto do custo de uma rodada V2 para listas (só rodadas concluídas têm custo de missão)."""
    m = (run.summary or {}).get("mission") or {}
    if run.state != "concluida" or m.get("custo_realizado_total_R") is None:
        return ""
    return f"V2 · custo realizado R$ {forms.fmt(m['custo_realizado_total_R'], 2)}"


def _real_ou_none(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def indicadores_rodada(run) -> dict:
    """Indicadores de UMA rodada V2 para o Caderno, lidos SÓ do resumo persistido (``summary.mission`` / ``execution``)
    e do manifesto. Nada é recalculado nem estimado: ausente ⇒ ``None`` (N/D); só uma rodada CONCLUÍDA tem custo de missão
    (o custo parcial de uma missão interrompida nunca é custo da missão). ``h2_kg`` é «não aplicável» (``"na"``) só com
    evidência: missão concluída cujo resumo registra o bloco PEMFC vazio."""
    man = run.manifest if isinstance(run.manifest, dict) else {}
    sm = run.summary if isinstance(run.summary, dict) else {}
    m = sm.get("mission") if isinstance(sm.get("mission"), dict) else {}
    ex = sm.get("execution") if isinstance(sm.get("execution"), dict) else {}
    mis = man.get("mission") if isinstance(man.get("mission"), dict) else {}
    malha = (man.get("strategy") or {}).get("malha") or {}
    conc = run.state == "concluida" and m.get("missao_completa") is True and not m.get("custo_realizado_parcial")
    pem = m.get("pemfc")
    if conc and isinstance(pem, dict) and pem:
        vals = [_real_ou_none((x or {}).get("massa_h2_kg")) for x in pem.values()]
        h2 = None if any(v is None for v in vals) else sum(vals)
    elif conc and isinstance(pem, dict):
        h2 = "na"
    else:
        h2 = None
    sv = m.get("sinal_valor_futuro") if isinstance(m.get("sinal_valor_futuro"), dict) else None
    sinal = None
    if conc and sv is not None:
        sinal = {"valido": sv.get("valido"), "degradado": (sv.get("degradado_sem_valor_futuro") or 0) + (sv.get("degradado_referencia") or 0),
                 "sem_coordenacao": sv.get("sem_coordenacao"), "janelas": m.get("janelas")}
    pcc = ((man.get("strategy") or {}).get("pcc") or {}).get("modo") or m.get("pcc_modo")
    return {"motor": "V2", "delta_min": _real_ou_none(mis.get("delta_min", malha.get("delta_min"))),
            "N": mis.get("N", malha.get("N")), "m": mis.get("m", malha.get("m")), "H_L": mis.get("H_L", malha.get("H_L")),
            "intervalos": mis.get("intervals"), "passo_s": _real_ou_none(mis.get("step_s")),
            "inicio_utc": mis.get("start_utc"), "duracao_min": _real_ou_none(mis.get("duration_min")),
            "pcc": pcc, "custo": _real_ou_none(m.get("custo_realizado_total_R")) if conc else None,
            "custo_natureza": "custo_realizado_v2",
            "energia_importada_kWh": _real_ou_none(m.get("energia_importada_kWh")) if conc else None,
            "energia_exportada_kWh": _real_ou_none(m.get("energia_exportada_kWh")) if conc else None,
            "energia_demanda_kWh": _real_ou_none(m.get("energia_demanda_kWh")) if conc else None,
            "energia_nao_atendida_kWh": _real_ou_none(m.get("energia_nao_atendida_kWh")) if conc else None,
            "h2_kg": h2, "sinal": sinal,
            "auditoria": ex.get("auditoria_integral_aprovada") if conc else None,
            "aceitacao": ((ex.get("aceitacao") or {}).get("classificacao")) if conc else None,
            "formulacao": m.get("formulacao") or ((man.get("engine") or {}).get("formulations") or {}).get("hierarquia"),
            "contrato_dados": (man.get("engine") or {}).get("data_version")}


SERIES_COMPARAVEIS = (("custo_realizado_acumulado_R", "Custo realizado acumulado", "R$"),
                      ("pcc_importacao_realizada_kW", "Importação realizada no PCC", "kW"),
                      ("demanda_realizada_kW", "Demanda realizada", "kW"))


def series_rodada(source, run) -> dict | None:
    """Séries GRAVADAS de uma rodada V2 concluída (``v2/intervalos.csv``) para a comparação temporal: só leitura, sem
    reamostrar nem preencher. Coluna ausente (contrato de dados anterior) ⇒ série ausente."""
    import io

    import pandas as pd

    if run.state != "concluida" or "v2/intervalos.csv" not in (run.data or {}):
        return None
    df = pd.read_csv(io.BytesIO(source.run_data(run.run_uid, "v2/intervalos.csv")))
    if "inicio_utc" not in df.columns:
        return None
    out = {"inicio_utc": [str(x) for x in df["inicio_utc"]], "series": {}}
    for col, _rot, _un in SERIES_COMPARAVEIS:
        if col in df.columns:
            out["series"][col] = [None if pd.isna(v) else float(v) for v in df[col]]
    return out


# ======================================================================= widgets de declaração (vazio = não declarado)
def _sel(rotulo: str, opcoes: dict, atual, chave: str, *, ajuda: str | None = None):
    vals = [None, *opcoes]
    if atual not in vals:
        vals.append(atual)
    return st.selectbox(rotulo, vals, index=vals.index(atual), key=chave, help=ajuda,
                        format_func=lambda v: VAZIO if v is None else f"{v} — {opcoes.get(v, '?')}"[:110])


def _num(rotulo: str, atual, chave: str, *, inteiro: bool = False, minimo=None, passo=None, fmt: str | None = None,
         ajuda: str | None = None):
    if inteiro:
        v = st.number_input(rotulo, min_value=minimo, value=None if atual is None else int(atual), step=passo or 1,
                            key=chave, help=ajuda)
        return None if v is None else int(v)
    v = st.number_input(rotulo, min_value=minimo, value=None if atual is None else float(atual), step=passo, key=chave,
                        format=fmt, help=ajuda)
    return None if v is None else float(v)


def _txt(rotulo: str, atual, chave: str, *, ajuda: str | None = None, max_chars: int = 300) -> str:
    return st.text_input(rotulo, value=atual or "", key=chave, help=ajuda, max_chars=max_chars)


def _instante(rotulo: str, atual, chave: str, ajuda: str):
    v = st.text_input(rotulo, value=atual or "", key=chave, help=ajuda, placeholder="2026-01-01T00:00:00+00:00").strip()
    if not v:
        return None
    if not E.instante_valido(v):
        st.error(f"{rotulo}: use ISO 8601 com fuso explícito (p. ex. 2026-01-01T00:00:00+00:00).")
    return v


def _lista(rotulo: str, atual, chave: str, ajuda: str):
    texto = st.text_area(rotulo, value="" if atual is None else " ".join(f"{v:g}" for v in atual), key=chave, help=ajuda,
                         height=70)
    toks = [t for t in re.split(r"[\s;]+", texto.strip()) if t]
    if not toks:
        return None
    try:
        return [float(t.replace(",", ".")) for t in toks]
    except ValueError:
        st.error(f"{rotulo}: valores não numéricos — a declaração anterior foi mantida.")
        return atual


def _proc(d: dict, chave: str, *, so_sintetico: bool = False) -> None:
    c1, c2 = st.columns([1, 2])
    if so_sintetico:
        d["tipo"] = "sintetico"
        c1.text_input("Procedência", value="sintetico (planta simulada)", key=f"{chave}_pt", disabled=True)
    else:
        with c1:
            d["tipo"] = _sel("Procedência (tipo)", E.TIPOS_DECLARAVEIS, d.get("tipo"), f"{chave}_pt")
    with c2:
        d["fonte"] = _txt("Fonte (documento, pessoa ou 'sintético de ensaio')", d.get("fonte"), f"{chave}_pf")


# ======================================================================= etapa 03 — motor e estratégia
def seletor_motor(doc: dict, tok: int) -> str:
    atual = motor(doc)
    ops = list(E.MOTORES)
    with st.container(border=True):
        st.html('<div class="op-k">Motor de execução deste cenário</div><p class="op-d">A seleção é gravada na versão do '
                'cenário e vale para as rodadas dessa versão. Nenhum motor substitui o outro em silêncio: um cenário V2 '
                'nunca é executado pelo motor V1.6 (nem o contrário).</p>')
        novo = st.radio("Motor", ops, index=ops.index(atual) if atual in ops else 0, key=f"opw_sg_{tok}_motor",
                        format_func=lambda m: E.MOTORES[m], label_visibility="collapsed")
    if novo != atual:
        if novo == E.MOTOR_V16:
            doc.pop(E.CHAVE_MOTOR, None)              # ausência = V1.6 (documentos V1.6 mantêm a forma anterior)
        else:
            doc[E.CHAVE_MOTOR] = novo
        st.rerun()
    return novo


# Folha de Ensaio (Piso 3D-B2 · finalização): subseções NAVEGÁVEIS da estratégia V2 e régua dos horizontes. Só
# apresentação: os campos, chaves, validações e a gravação são os do formulário abaixo (nada é acrescentado nem omitido).
SUBSECOES = (("motor", "Motor de execução"), ("malha", "Malha temporal e horizontes"), ("demanda", "Demanda e realização"),
             ("baterias", "Bancos de baterias"), ("renovaveis", "Recursos renováveis"), ("pemfc", "PEMFC e hidrogênio"),
             ("pcc", "Rede, PCC e objetivo"), ("planejador", "Planejamento de longo prazo"), ("solver", "MPC e solver"),
             ("revisao", "Declarações pendentes e políticas fixas"))
# Primeiro segmento do caminho de uma pendência/erro do bloco → subseção onde o campo é editado.
_SUB_DO_CAMPO = {"declarante": "malha", "malha": "malha", "contexto": "malha", "demanda": "demanda", "realizacao": "demanda",
                 "baterias": "baterias", "clima": "renovaveis", "renovaveis": "renovaveis", "pemfc": "pemfc", "pcc": "pcc",
                 "objetivo": "pcc", "planejador": "planejador", "solver": "solver"}


def _subs_presentes(doc: dict) -> list[str]:
    b = doc.get(E.CHAVE_BLOCO)
    if not isinstance(b, dict):
        return ["motor"]
    fmt = b.get("format_version", 1)
    tem = {"baterias": bool(E.baterias_do_cenario(doc)), "renovaveis": bool(E.renovaveis_do_cenario(doc)) and fmt >= 2,
           "pemfc": bool(E.pemfc_do_cenario(doc)) and fmt >= 3}
    return [k for k, _t in SUBSECOES if tem.get(k, True)]


def subsecoes_estrategia(doc: dict) -> list[dict]:
    """Subseções da etapa 03 (motor V2) na ordem do formulário, com o número de declarações AUSENTES de cada uma (as
    MESMAS de ``estrategia.pendencias``; com erro estrutural, as pendências não são calculadas e ficam ``None``)."""
    pres = _subs_presentes(doc)
    b = doc.get(E.CHAVE_BLOCO)
    pend: dict[str, int] | None = None
    if isinstance(b, dict):
        try:
            errs = E.erros_estruturais(b, doc)
            if not errs:
                pend = {}
                for cam, _msg in E.pendencias(b, doc):
                    sub = _SUB_DO_CAMPO.get(cam.split(".")[0].split("[")[0], "revisao")
                    pend[sub] = pend.get(sub, 0) + 1
        except Exception:  # noqa: BLE001 — o índice nunca impede o uso do formulário
            pend = None
    titulos = dict(SUBSECOES)
    return [{"id": k, "n": f"03.{i}", "titulo": titulos[k], "pend": None if pend is None else pend.get(k, 0)}
            for i, k in enumerate(pres, 1)]


def _sub(sid: str, doc: dict) -> None:
    """Cabeçalho-âncora de uma subseção (alvo da navegação do índice da Folha)."""
    pres = _subs_presentes(doc)
    n = f"03.{pres.index(sid) + 1}" if sid in pres else "03"
    st.html(f'<div class="fl-sub" data-fl-sub="{escape(sid)}"><span class="fl-sub-n">{n}</span>'
            f'{escape(dict(SUBSECOES)[sid])}</div>')


def regua_dados(doc: dict) -> dict:
    """Dados da régua dos horizontes a partir SÓ do que está declarado (malha da estratégia V2 e janela da missão da
    etapa 04). Nada é inferido: ausente ⇒ ``None`` e a lista ``faltam``. As relações mostradas são as que o preflight V2
    verifica (``integracao_v2.preflight``); aqui só são exibidas, nunca impostas."""
    b = doc.get(E.CHAVE_BLOCO) if isinstance(doc.get(E.CHAVE_BLOCO), dict) else {}
    m = b.get("malha") or {}

    def inteiro(v):
        return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None
    delta, N, mm, HL = (inteiro(m.get(k)) for k in ("delta_min", "N", "m", "H_L"))
    mis = doc.get("mission") if isinstance(doc.get("mission"), dict) else {}
    dur = inteiro(mis.get("duration_min"))
    faltam = [r for r, v in (("passo Δ", delta), ("horizonte curto N", N), ("bloco aplicado m", mm),
                             ("horizonte longo H_L", HL), ("duração da missão (seção 04)", dur)) if v is None]
    K = dur // delta if dur and delta and dur % delta == 0 else None
    rel = []
    if dur and delta:
        rel.append(["Duração da missão múltipla de Δ", dur % delta == 0, f"{dur} min ÷ {delta} min"])
    if K is not None:
        rel.append([f"K_M ≤ {E.LIMITES['intervalos_missao']} intervalos", K <= E.LIMITES["intervalos_missao"], f"K_M = {K}"])
    if N and mm:
        rel.append(["1 ≤ m ≤ N", mm <= N, f"m = {mm}, N = {N}"])
    if N and HL:
        rel.append(["H_L > N", HL > N, f"H_L = {HL}, N = {N}"])
    if HL and K is not None:
        rel.append(["H_L ≤ K_M (sem previsão pós-missão)", HL <= K, f"H_L = {HL}, K_M = {K}"])
    return {"delta_min": delta, "N": N, "m": mm, "H_L": HL, "duracao_min": dur, "K": K, "faltam": faltam, "relacoes": rel,
            "terminal": _fixo("politica_terminal_missao"), "cobertura": _fixo("cobertura_fim_missao")}


def regua(doc: dict, *, titulo: str | None = None, key: str = "seeds_folha_regua") -> None:
    """Régua dos horizontes (componente da Folha; desenhada no navegador a partir de ``regua_dados``, sem motor)."""
    from seeds2.ui import trama

    trama.pagina("folha", {"parte": "regua", "regua": regua_dados(doc), "titulo": titulo}, key=key, wide=False)


def _fixo(chave: str) -> str:
    from . import montagem as MT

    return str(MT.FIXOS.get(chave) or "N/D").replace("_", " ")


def render_estrategia(store, cur, oc) -> None:
    doc = oc.work()
    tok = int(_ss().get("op_token") or 0)
    tone, label, detail = E.status_estrategia(doc)
    shell.hero("Estratégia EMS · motor V2 experimental", doc["name"],
               "Declarações do EMS hierárquico MILP–MPC (Pyomo + HiGHS) para as rodadas deste cenário. Simulação OFFLINE "
               "de ensaio: não é controle de equipamentos nem validação física. Nenhum parâmetro físico tem valor padrão.",
               [("Cenário", f"v{cur.version}" + (" · alterações não salvas" if oc.is_dirty() else "")),
                ("Estratégia", label + (f" · {detail}" if detail else "")),
                ("Inventário de referência", f"rev. {doc['inventory_ref']['config_revision']}")])
    _sub("motor", doc)
    seletor_motor(doc, tok)
    b = doc.get(E.CHAVE_BLOCO)
    if b is None:
        shell.callout("<b>Estratégia MILP–MPC ainda não definida.</b> O formulário é criado com os campos científicos "
                      "VAZIOS (eficiências, potências no barramento, PCC, tarifas, políticas): cada um precisa ser "
                      "declarado com procedência. Só os parâmetros numéricos do planejador/solver começam com os "
                      f"{escape(E.ROTULO_REFERENCIA)}.", "warn")
        if st.button("CRIAR DECLARAÇÃO DA ESTRATÉGIA V2 (CAMPOS EM BRANCO)", key="op_sg_v2_novo", type="primary"):
            doc[E.CHAVE_BLOCO] = E.novo_bloco(doc)
            st.rerun()
        oc._save_bar(store, cur, I.summarize(S.findings(doc)))
        return
    if (E.renovaveis_do_cenario(doc) or E.pemfc_do_cenario(doc)) and (
            b.get("format_version", 1) < E.FORMATO or set(E.renovaveis_do_cenario(doc)) - set(b.get("renovaveis") or {})
            or set(E.pemfc_do_cenario(doc)) - set(b.get("pemfc") or {})):
        doc[E.CHAVE_BLOCO] = b = E.atualizar_bloco(b, doc)   # seções de renováveis VAZIAS (nada é preenchido)
    if E.erros_estruturais(b, doc) and set(b) != set(E.novo_bloco(doc)):
        st.error("A estratégia V2 gravada tem estrutura incompatível com esta versão do formulário.")
        oc._save_bar(store, cur, I.summarize(S.findings(doc)))
        return
    k = f"opw_sg_{tok}_v2"
    _sub("malha", doc)
    with st.container(border=True):
        st.html('<div class="op-k">Malha temporal (N intervalos · N + 1 fronteiras)</div>')
        m = b["malha"]
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            m["delta_min"] = _num("Passo Δ [min]", m["delta_min"], f"{k}_delta", inteiro=True, minimo=1,
                                  ajuda="Igual ao passo da série de demanda: o motor não reamostra.")
        with a2:
            m["N"] = _num("Horizonte curto N [intervalos]", m["N"], f"{k}_N", inteiro=True, minimo=1)
        with a3:
            m["m"] = _num("Bloco aplicado m [intervalos]", m["m"], f"{k}_m", inteiro=True, minimo=1)
        with a4:
            m["H_L"] = _num("Horizonte longo H_L [intervalos]", m["H_L"], f"{k}_HL", inteiro=True, minimo=2,
                            ajuda="H_L > N e H_L ≤ intervalos da missão (a previsão cobre só a missão).")
        regua(doc)
        st.html('<div class="op-k" style="margin-top:.5rem">Quem declara as políticas</div>')
        _proc(b["declarante"], f"{k}_decl")
    _sub("demanda", doc)
    with st.container(border=True):
        st.html('<div class="op-k">Demanda: previsão disponível ao decidir</div>')
        d = b["demanda"]
        d["nome"] = _txt("Nome da classe de demanda", d["nome"], f"{k}_dn", max_chars=120)
        a1, a2 = st.columns(2)
        with a1:
            d["criticidade"] = _sel("Criticidade", E.CRITICIDADES, d["criticidade"], f"{k}_dc")
        with a2:
            d["semantica"] = _sel("Semântica da série", E.SEMANTICAS, d["semantica"], f"{k}_ds",
                                  ajuda="O Piso 2B não registra a semântica; o MILP só aceita médias de intervalo declaradas.")
        d["emissao_utc"] = _instante("Emissão da previsão (UTC)", d["emissao_utc"], f"{k}_de",
                                     "Instante em que a previsão ficou disponível; deve ser anterior ao início da missão.")
        st.html('<div class="op-k" style="margin-top:.5rem">Realização SIMULADA posterior (só a planta a recebe)</div>')
        r = b["realizacao"]
        r["tipo"] = _sel("Realização", E.REALIZACOES, r["tipo"], f"{k}_rt")
        if r["tipo"] == "serie_declarada":
            r["demanda_kW"] = _lista("Demanda realizada [kW] — um valor por intervalo", r["demanda_kW"], f"{k}_rv",
                                     "Separados por espaço, quebra de linha ou ';' (vírgula decimal aceita).")
        else:
            r["demanda_kW"] = None
        _proc(r["procedencia"], f"{k}_rp", so_sintetico=True)
    bats = E.baterias_do_cenario(doc)
    if bats:
        _sub("baterias", doc)
    for eid, ref in bats.items():
        x = b["baterias"].setdefault(eid, {**{c: None for c in E.CAMPOS_BATERIA}, "hipotese_autodescarga": None,
                                           "procedencia": {"tipo": None, "fonte": ""}})
        with st.container(border=True):
            st.html(f'<div class="op-k">Bateria · {escape(ref.get("name") or eid)} <span class="op-m">{escape(eid)}</span>'
                    '</div><p class="op-d">Capacidade e limites de SOC vêm do inventário; o que o inventário não tem é '
                    'declarado aqui, por dispositivo. Potências no BARRAMENTO (não no terminal CC).</p>')
            cols = st.columns(5)
            for i, (campo, (rot, un, _ch, _dom)) in enumerate(E.CAMPOS_BATERIA.items()):
                with cols[i]:
                    x[campo] = _num(f"{rot} [{un}]", x[campo], f"{k}_b_{eid}_{campo}", minimo=0.0, fmt="%.6g")
            x["hipotese_autodescarga"] = _sel("Hipótese de autodescarga", E.HIPOTESES_AUTODESCARGA,
                                              x["hipotese_autodescarga"], f"{k}_b_{eid}_hip")
            _proc(x["procedencia"], f"{k}_b_{eid}")
    for eid in [e for e in list(b["baterias"]) if e not in bats]:
        b["baterias"].pop(eid)                        # banco retirado/desabilitado: declaração órfã não é mantida
    _renovaveis_form(b, doc, k)
    _pemfc_form(b, doc, k)
    _sub("pcc", doc)
    with st.container(border=True):
        st.html('<div class="op-k">PCC, tarifas e objetivo</div>')
        c = b["pcc"]
        a1, a2, a3 = st.columns(3)
        with a1:
            c["modo"] = _sel("Modo do PCC", E.MODOS_CONEXAO, c["modo"], f"{k}_pm")
            c["limite_importacao_kW"] = _num("Limite de importação [kW]", c["limite_importacao_kW"], f"{k}_pli", minimo=0.0)
            c["disponibilidade"] = _sel("Disponibilidade do PCC", E.DISPONIBILIDADES_PCC, c["disponibilidade"], f"{k}_pd")
        with a2:
            c["sentidos"] = _sel("Sentidos permitidos", E.SENTIDOS, c["sentidos"], f"{k}_ps")
            c["limite_exportacao_kW"] = _num("Limite de exportação [kW]", c["limite_exportacao_kW"], f"{k}_ple", minimo=0.0)
            c["remuneracao_exportacao"] = _sel("Remuneração da exportação", E.REMUNERACOES_EXPORTACAO,
                                               c["remuneracao_exportacao"], f"{k}_pr")
        with a3:
            c["ajuste"] = _sel("Ajuste do PCC na execução", E.TIPOS_AJUSTE, c["ajuste"], f"{k}_pa")
            c["tarifa_liquidacao"] = _sel("Liquidação", E.LIQUIDACOES, c["tarifa_liquidacao"], f"{k}_pl")
            c["tarifa_emissao_utc"] = _instante("Emissão das tarifas (UTC)", c["tarifa_emissao_utc"], f"{k}_pe",
                                                "Tarifa de decisão: só vale se emitida até o início da missão.")
        a1, a2 = st.columns(2)
        with a1:
            c["tarifa_importacao_R_kWh"] = _lista("Tarifa de importação [R$/kWh] — um valor por intervalo",
                                                  c["tarifa_importacao_R_kWh"], f"{k}_pti", "Um preço por intervalo da missão.")
        with a2:
            c["tarifa_exportacao_R_kWh"] = _lista("Tarifa de exportação [R$/kWh] — um valor por intervalo",
                                                  c["tarifa_exportacao_R_kWh"], f"{k}_pte", "Só com exportação remunerada.")
        a1, a2 = st.columns(2)
        with a1:
            c["rotulo_tarifa"] = _txt("Rótulo da tarifa (p. ex. 'SINTÉTICA — não é tarifa real')", c["rotulo_tarifa"], f"{k}_prot")
        with a2:
            c["justificativa"] = _txt("Justificativa da declaração do PCC", c["justificativa"], f"{k}_pj")
        _proc(c["procedencia"], f"{k}_pcc")
        b["objetivo"]["termos"] = st.multiselect("Termos de custo no objetivo", list(E.TERMOS_BASE),
                                                 default=[t for t in b["objetivo"]["termos"] if t in E.TERMOS_BASE],
                                                 format_func=lambda t: E.TERMOS_BASE[t], key=f"{k}_termos")
    _sub("planejador", doc)
    g, s = b["planejador"], b["solver"]
    with st.container(border=True):
        st.html('<div class="op-k">Planejador de longo prazo</div><p class="op-d">Parâmetros numéricos iniciais = '
                f'{escape(E.ROTULO_REFERENCIA)}. Termo terminal Φ_L e degradação NÃO têm valor inicial.</p>')
        a1, a2, a3 = st.columns(3)
        with a1:
            g["tipo_sinal"] = _sel("Sinal de valor futuro", E.TIPOS_SINAL, g["tipo_sinal"], f"{k}_gs")
            g["politica_atualizacao"] = _sel("Atualização do planejador", E.POLITICAS_ATUALIZACAO, g["politica_atualizacao"],
                                             f"{k}_ga")
            g["periodo_janelas"] = _num("Período [janelas]", g["periodo_janelas"], f"{k}_gp", inteiro=True, minimo=1)
        with a2:
            g["degradacao"] = _sel("Degradação (sinal indisponível)", E.DEGRADACOES, g["degradacao"], f"{k}_gd")
            g["pontos_iniciais"] = _num("Pontos iniciais por banco", g["pontos_iniciais"], f"{k}_gpi", inteiro=True, minimo=2)
            g["pontos_max"] = _num("Pontos máximos (refino)", g["pontos_max"], f"{k}_gpm", inteiro=True, minimo=2)
        with a3:
            g["tolerancia_interpolacao_R"] = _num("Tolerância de interpolação [R$]", g["tolerancia_interpolacao_R"],
                                                  f"{k}_gti", minimo=0.0, fmt="%.3g")
            g["tolerancia_dominio_kWh"] = _num("Tolerância do domínio [kWh]", g["tolerancia_dominio_kWh"], f"{k}_gtd",
                                               minimo=0.0, fmt="%.3g")
            g["max_modos"] = _num("Máximo de modos", g["max_modos"], f"{k}_gmm", inteiro=True, minimo=1)
        t = g["termo_longo"]
        t["tipo"] = _sel("Termo terminal Φ_L (fim do horizonte longo)", {x: x for x in E.TERMOS_DECLARADOS}, t["tipo"], f"{k}_tt")
        if t["tipo"] in ("valor_linear_declarado", "energia_minima_declarada"):
            un = "R$/kWh" if t["tipo"] == "valor_linear_declarado" else "kWh"
            for eid in bats:
                t["valores"][eid] = _num(f"Φ_L · {eid} [{un}]", t["valores"].get(eid), f"{k}_tv_{eid}", minimo=0.0)
            t["valores"] = {u: v for u, v in t["valores"].items() if v is not None and u in bats}
        else:
            t["valores"] = {}
        t["justificativa"] = _txt("Justificativa do termo terminal Φ_L", t["justificativa"], f"{k}_tj", max_chars=500)
        g["justificativa"] = _txt("Justificativa dos parâmetros do planejador", g["justificativa"], f"{k}_gj", max_chars=500)
    _sub("solver", doc)
    with st.container(border=True):
        st.html('<div class="op-k">MPC · solver de cada resolução (HiGHS)</div><p class="op-d">Limites numéricos de cada '
                'resolução MILP das janelas MPC e do planejador; a aceitação continua sendo a do auditor independente.</p>')
        a1, a2, a3 = st.columns(3)
        with a1:
            s["time_limit_s"] = _num("Solver · limite de tempo por resolução [s]", s["time_limit_s"], f"{k}_stl", minimo=0.0)
            s["rel_gap"] = _num("Solver · gap relativo", s["rel_gap"], f"{k}_srg", minimo=0.0, fmt="%.3g")
        with a2:
            s["threads"] = _num("Solver · threads", s["threads"], f"{k}_sth", inteiro=True, minimo=1)
            s["abs_gap"] = _num("Solver · gap absoluto [R$]", s["abs_gap"], f"{k}_sag", minimo=0.0, fmt="%.3g")
        with a3:
            s["semente"] = _num("Solver · semente", s["semente"], f"{k}_sse", inteiro=True, minimo=0)
    _sub("revisao", doc)
    errs = E.erros_estruturais(b, doc)
    for e in errs:
        st.error(e)
    pend = [] if errs else E.pendencias(b, doc)
    if pend:
        shell.callout(f"<b>{len(pend)} declaração(ões) ausente(s).</b> O cenário pode ser salvo assim, mas o preflight V2 "
                      "bloqueia a execução até que tudo esteja declarado (nenhum valor é presumido).", "warn")
        st.html("".join(f'<div class="op-f"><i class="warn">!</i><span>{escape(msg)} '
                        f'<span class="op-m">[{escape(cam)}]</span></span></div>' for cam, msg in pend))
    elif not errs:
        shell.callout("Estratégia V2 completa: todas as declarações têm valor e procedência. A compatibilidade científica é "
                      "verificada pelo preflight V2 na etapa 04, sobre a versão SALVA.", "ok")
    with st.expander("Políticas fixas da integração V2 (informativas, gravadas em cada rodada)"):
        from . import montagem as MT

        st.html('<table class="op-tbl">' + "".join(f"<tr><td>{escape(a)}</td><td>{escape(str(v))}</td></tr>"
                                                    for a, v in MT.FIXOS.items()) + "</table>")
    oc._save_bar(store, cur, I.summarize(S.findings(doc)))


def _renovaveis_form(b: dict, doc: dict, k: str) -> None:
    """Clima previsto e declarações por equipamento renovável (Piso 3D-A2-R). O potencial NÃO é declarado: é derivado
    pelos modelos físicos do SEEDS2 no preflight, a partir do inventário e da previsão climática do cenário."""
    rens = E.renovaveis_do_cenario(doc)
    if not rens or b.get("format_version", 1) < 2:
        return
    _sub("renovaveis", doc)
    with st.container(border=True):
        st.html('<div class="op-k">Renováveis: clima previsto e declarações por equipamento</div><p class="op-d">O potencial '
                'disponível no barramento é calculado pelos MODELOS FÍSICOS do SEEDS2 (FV por arranjo; eólica por registro) '
                'sobre a previsão climática da etapa 02 — nenhum perfil é digitado aqui. Disponível ≠ despachado: o '
                'vertimento é decisão do EMS.</p>')
        cl = b["clima"]
        a1, a2 = st.columns(2)
        with a1:
            cl["semantica"] = _sel("Semântica da série climática", E.SEMANTICAS_CLIMA, cl["semantica"], f"{k}_cls",
                                   ajuda="O Piso 2B não registra se as amostras são médias ou instantâneas.")
        with a2:
            cl["emissao_utc"] = _instante("Emissão da previsão climática (UTC)", cl["emissao_utc"], f"{k}_cle",
                                          "Deve ser anterior ao início da missão (causalidade).")
        curt = "curtailment_operacional" in b["objetivo"]["termos"]
        for eid, ref in rens.items():
            x = b["renovaveis"][eid]
            tec = x["tecnologia"]
            st.html(f'<div class="op-k" style="margin-top:.6rem">{"Fotovoltaica" if tec == "fv" else "Eólica"} · '
                    f'{escape(ref.get("name") or eid)} <span class="op-m">{escape(eid)}</span></div>')
            a1, a2 = st.columns(2)
            with a1:
                if tec == "fv":
                    x["eta_conversao_barramento"] = _num("Conversão CC → barramento η [1]", x["eta_conversao_barramento"],
                                                         f"{k}_rn_{eid}_eta", minimo=0.0, fmt="%.4g",
                                                         ajuda="O modelo FV entrega potência CC do arranjo (sem inversor).")
                else:
                    x["hipotese_densidade"] = _sel("Densidade do ar", E.HIPOTESES_DENSIDADE, x["hipotese_densidade"],
                                                   f"{k}_rn_{eid}_rho")
            with a2:
                if curt:
                    x["custo_curtailment_R_kWh"] = _num("Custo de vertimento c_curt [R$/kWh]", x["custo_curtailment_R_kWh"],
                                                        f"{k}_rn_{eid}_cc", minimo=0.0, fmt="%.4g")
            _proc(x["procedencia"], f"{k}_rn_{eid}")


def _pemfc_form(b: dict, doc: dict, k: str) -> None:
    """Declarações PEMFC (Piso 3D-A2-H): inicialização física da curva, limites e commitment por unidade. A curva q(P)
    NÃO é digitada: é gerada pelo modelo físico no preflight e só entra no MILP com certificado B04 aprovado."""
    regs = E.pemfc_do_cenario(doc)
    if not regs or b.get("format_version", 1) < 3:
        return
    _sub("pemfc", doc)
    with st.container(border=True):
        st.html('<div class="op-k">PEMFC / H₂: inicialização física e commitment</div><p class="op-d">A curva de consumo '
                'q(P) é gerada pelo MODELO FÍSICO do SEEDS2 a partir destas condições (uma vez por configuração) e só entra '
                'no MILP com certificado B04 APROVADO pelo responsável. Modelo aproximado — não é caracterização '
                'experimental do equipamento.</p>')
        termos = b["objetivo"]["termos"]
        for eid, ref in regs.items():
            x = b["pemfc"][eid]
            st.html(f'<div class="op-k" style="margin-top:.4rem">{escape(ref.get("name") or eid)} '
                    f'<span class="op-m">{escape(eid)}</span></div>')
            cols = st.columns(4)
            for i, (campo, (rot, un)) in enumerate(E.CONDICOES_PEMFC.items()):
                with cols[i]:
                    x["condicoes"][campo] = _num(f"{rot} [{un}]", x["condicoes"][campo], f"{k}_fc_{eid}_{campo}", fmt="%.6g")
            cols = st.columns(4)
            vis = [c for c in E.CAMPOS_PEMFC if c not in ("custo_partida_R", "custo_parada_R") or "eventos" in termos]
            for i, campo in enumerate(vis):
                rot, un, _d = E.CAMPOS_PEMFC[campo]
                with cols[i % 4]:
                    x[campo] = _num(f"{rot} [{un}]", x[campo], f"{k}_fc_{eid}_{campo}", fmt="%.6g")
            a1, a2 = st.columns(2)
            with a1:
                x["abstracao"] = _sel("Abstração de partida/parada (D05)", E.ABSTRACOES_PEMFC, x["abstracao"],
                                      f"{k}_fc_{eid}_abs")
            with a2:
                x["limites_transicao"] = _sel("Limites de partida/parada", E.LIMITES_PEMFC, x["limites_transicao"],
                                              f"{k}_fc_{eid}_lim")
            for i, un in enumerate(x["unidades"]):
                c1, c2, c3 = st.columns(3)
                with c1:
                    un["estado"] = _sel(f"Unidade {i + 1} · estado inicial", E.ESTADOS_UNIDADE, un["estado"],
                                        f"{k}_fc_{eid}_u{i}_e")
                with c2:
                    un["potencia_kW"] = _num(f"Unidade {i + 1} · potência anterior [kW]", un["potencia_kW"],
                                             f"{k}_fc_{eid}_u{i}_p", minimo=0.0, fmt="%.6g")
                with c3:
                    un["tempo_no_estado_min"] = _num(f"Unidade {i + 1} · tempo no estado [min]", un["tempo_no_estado_min"],
                                                     f"{k}_fc_{eid}_u{i}_t", minimo=0.0, fmt="%.6g")
            _proc(x["procedencia"], f"{k}_fc_{eid}")


# ======================================================================= etapa 04 — preflight e execução
def preflight(store, cur) -> PF.PreflightV2:
    """Preflight V2 da versão SALVA ``cur`` (cache por versão do cenário e revisão do inventário)."""
    saved = session.saved()
    key = ("v2", cur.scenario_uid, cur.version, cur.fingerprint, saved.revision if saved else None)
    c = _ss().get("op_ex_pf_v2")
    if c is None or c[0] != key:
        pf = PF.preparar(store, cur)
        _ss()["op_ex_pf_v2"] = (key, pf)
        return pf
    return c[1]


def stage_state(store, cur) -> tuple[str, str, str]:
    try:
        pf = preflight(store, cur)
    except StoreError as exc:
        return "bad", "Indisponível", str(exc)[:80]
    n = pf.count(PF.ERROR)
    done = sum(1 for r in store.list_runs(cur.scenario_uid, limit=50) if r.state == "concluida")
    hist = f" · {done} rodada(s) concluída(s)" if done else ""
    if n:
        return "bad", "Não executável (V2)", f"{n} bloqueio(s) na versão salva v{cur.version}{hist}"
    return "ok", "Pronto para executar (V2)", f"versão salva v{cur.version}{hist}"


def _matriz_html(linhas: list[dict]) -> str:
    cab = ("Dado", "UID", "Valor", "Fonte / procedência", "Transformação", "Validação", "Registro", "Vista")
    corpo = "".join(
        "<tr>" + "".join(f"<td>{escape(str(x))}</td>" for x in (
            r["dado"], r["uid"], f"{r['valor']} {r['unidade']}".strip(), r["fonte"], r["transformacao"], r["validacao"],
            r["registro"], r["vista"])) + "</tr>" for r in linhas)
    return '<table class="op-tbl"><tr>' + "".join(f"<th>{c}</th>" for c in cab) + "</tr>" + corpo + "</table>"


# UI-FINISH-01 (ponto 3A): hierarquia COMPACTA do relatório do preflight — só apresentação. Os itens, níveis, contagens,
# critérios e a capacidade de executar são os MESMOS objetos do preflight V2 (``PF.PreflightV2.report()``); nada é
# reclassificado. Bloqueios sempre visíveis com o texto inteiro; advertências resumidas por área (texto completo a um
# clique); informações visíveis em letra menor; verificações aprovadas recolhidas, agrupadas por área.
# «Onde revisar» é ORIENTAÇÃO de navegação por área, só onde a seção é inequívoca — não é diagnóstico novo.
ONDE_REVISAR = {"estrategia": "03 · Motor e estratégia", "parametros": "03 · Motor e estratégia", "contrato": "03 · Motor e estratégia",
                "motor": "03 · Motor e estratégia", "pcc": "03 · Motor e estratégia (PCC e tarifas)",
                "pemfc": "03 · Motor e estratégia (PEMFC / H₂)", "previsoes": "02 · Previsões",
                "solver": "ambiente do servidor (dependências do motor V2: requirements-ems_v2.txt)",
                "inventario": "Gestão da microrrede (inventário) e a referência do cenário"}
PF_CSS = """<style>
.pf-res { display: flex; flex-wrap: wrap; gap: .4rem .5rem; margin: .1rem 0 .6rem 0; }
.pf-c { display: inline-flex; align-items: baseline; gap: .35rem; padding: .22rem .65rem; border-radius: 999px; font-size: .8rem;
  border: 1px solid rgba(128,128,128,.28); font-variant-numeric: tabular-nums; }
.pf-c b { font-size: .95rem; } .pf-c.b { border-color: #C2364A; color: #C2364A; } .pf-c.w { border-color: #C77700; color: #A35F00; }
.pf-c.ok { border-color: color-mix(in srgb, #2E8B57 60%, transparent); color: #2E8B57; } .pf-c.z { opacity: .55; }
.pf-k { font-size: .7rem; font-weight: 760; letter-spacing: .1em; text-transform: uppercase; opacity: .62; margin: .8rem 0 .35rem 0; }
.pf-it { display: grid; grid-template-columns: 1.3rem minmax(0, 1fr); gap: .1rem .5rem; padding: .5rem .2rem; border-top: 1px solid rgba(128,128,128,.16); }
.pf-it:first-of-type { border-top: 0; }
.pf-it > i { font-style: normal; font-weight: 800; text-align: center; line-height: 1.35; }
.pf-it .t { font-weight: 700; font-size: .9rem; line-height: 1.3; }
.pf-it .d { grid-column: 2; font-size: .82rem; line-height: 1.45; opacity: .82; overflow-wrap: anywhere; }
.pf-it .o { grid-column: 2; font-size: .76rem; margin-top: .15rem; opacity: .9; }
.pf-it.b > i { color: #C2364A; } .pf-it.w > i { color: #C77700; } .pf-it.ok > i { color: #2E8B57; } .pf-it.i > i { opacity: .55; }
.pf-blq { border: 1px solid color-mix(in srgb, #C2364A 45%, transparent); border-left: 4px solid #C2364A; border-radius: 12px;
  padding: .35rem .8rem; margin: .2rem 0 .5rem 0; background: color-mix(in srgb, #C2364A 5%, transparent); }
.pf-adv { display: flex; flex-wrap: wrap; gap: .35rem; margin: .1rem 0 .3rem 0; }
.pf-adv span { font-size: .78rem; padding: .15rem .55rem; border-radius: 8px; background: color-mix(in srgb, #C77700 10%, transparent); }
.pf-info .pf-it .t { font-size: .82rem; } .pf-info .pf-it .d { font-size: .78rem; }
.pf-grp { font-size: .74rem; font-weight: 760; letter-spacing: .06em; text-transform: uppercase; opacity: .6; margin: .7rem 0 .1rem 0; }
</style>"""


def _area(it: dict) -> str:
    return PF.AREA_LABELS.get(it.get("area"), it.get("area") or "")


def _item_html(it: dict, *, onde: bool = False) -> str:
    lv = it["level"]
    cls = {PF.ERROR: "b", PF.WARNING: "w", PF.OK: "ok", PF.INFO: "i"}.get(lv, "")
    o = ONDE_REVISAR.get(it.get("area")) if onde else None
    return (f'<div class="pf-it {cls}"><i aria-hidden="true">{GLIFOS.get(lv, "·")}</i><span class="t">{escape(_area(it))}</span>'
            f'<span class="d">{escape(it["message"])}</span>'
            + (f'<span class="o">Onde revisar (orientação): <b>{escape(o)}</b></span>' if o else "") + "</div>")


def _agrupado(items: list[dict]) -> str:
    grupos: dict[str, list[dict]] = {}
    for it in items:
        grupos.setdefault(_area(it), []).append(it)
    return "".join(f'<div class="pf-grp">{escape(g)} · {len(v)}</div>' + "".join(_item_html(x) for x in v) for g, v in grupos.items())


def resumo_preflight(rep: dict) -> dict:
    """Contagens e bloqueios DO preflight (os mesmos números do relatório e do cartão de rodada)."""
    c = rep["counts"]
    return {"ok": bool(rep["ok"]), "aprovadas": int(c[PF.OK]), "avisos": int(c[PF.WARNING]), "bloqueios": int(c[PF.ERROR]),
            "info": int(c[PF.INFO]), "excluidos": len(rep["excluded"]),
            "areas_bloqueio": list(dict.fromkeys(_area(i) for i in rep["items"] if i["level"] == PF.ERROR))}


def relatorio_preflight(rep: dict, matriz: list[dict], versao) -> None:
    r = resumo_preflight(rep)
    por = {lv: [i for i in rep["items"] if i["level"] == lv] for lv in (PF.ERROR, PF.WARNING, PF.INFO, PF.OK)}
    st.html(PF_CSS)
    st.markdown(f'<div class="sd-section">Preflight V2 · versão salva v{versao}</div>', unsafe_allow_html=True)
    if not rep["ok"]:
        shell.callout("<b>Este cenário NÃO pode ser executado pelo motor V2.</b> Cada bloqueio abaixo explica o que falta ou "
                      "o que não é representável; nada é preenchido automaticamente e o motor V1.6 não é usado como "
                      "substituto.", "bad")
    else:
        shell.callout("<b>Apto para o motor V2.</b> Parâmetros e séries suficientes, contratos 3C-0…3C-4 aceitos e solver "
                      "disponível.", "ok")
    chip = lambda n, rot, cls: f'<span class="pf-c {cls if n else "z"}"><b>{n}</b> {rot}</span>'  # noqa: E731
    st.html('<div class="pf-res" data-pf="resumo">' + chip(r["bloqueios"], "bloqueio(s) — impedem a execução", "b")
            + chip(r["avisos"], "advertência(s) — não bloqueiam", "w") + chip(r["aprovadas"], "verificação(ões) aprovada(s)", "ok")
            + chip(r["info"], "informação(ões)", "") + chip(r["excluidos"], "excluído(s) no cenário", "") + "</div>")
    if por[PF.ERROR]:
        st.html('<div class="pf-k">Bloqueios — impedem a execução</div><div class="pf-blq" data-pf="bloqueios">'
                + "".join(_item_html(i, onde=True) for i in por[PF.ERROR]) + "</div>")
    if por[PF.WARNING]:
        cont: dict[str, int] = {}
        for i in por[PF.WARNING]:
            cont[_area(i)] = cont.get(_area(i), 0) + 1
        st.html('<div class="pf-k">Advertências — não bloqueiam</div><div class="pf-adv" data-pf="avisos">'
                + "".join(f"<span>{escape(a)} · {n}</span>" for a, n in cont.items()) + "</div>")
        with st.expander(f"Ver as {len(por[PF.WARNING])} advertência(s) (texto completo)"):
            st.html(_agrupado(por[PF.WARNING]))
    if por[PF.INFO]:
        st.html('<div class="pf-info" data-pf="info">' + "".join(_item_html(i) for i in por[PF.INFO]) + "</div>")
    if rep["excluded"]:
        st.html("<div class='op-k' style='margin-top:.5rem'>Excluídos desta missão (inventário inalterado)</div>"
                '<table class="op-tbl">' + "".join(f"<tr><td>{escape(e['name'])}</td><td>{escape(e['reason'])}</td></tr>"
                                                    for e in rep["excluded"]) + "</table>")
    if por[PF.OK]:
        with st.expander(f"Ver {len(por[PF.OK])} verificações aprovadas (por classe; procedência, horários, séries e "
                         "critérios 3C-0…3C-4 em texto completo)"):
            st.html(_agrupado(por[PF.OK]))
    if matriz:
        with st.expander("Matriz fonte → transformação → validação → registro → vista (o que chega ao motor)"):
            st.html(_matriz_html(matriz))
    if rep.get("bridge"):
        with st.expander("Relatório da ponte científica 3C-0/3C-1 (texto original)"):
            st.code(rep["bridge"]["texto"], language="text")
            st.caption(f"SHA-256 do relatório: {rep['bridge']['sha256']}")


CTA_SLOT = "fl_cta_slot"          # UI-FINISH-01: a Folha de Ensaio desenha o cartão de rodada na coluna esquerda
ABRIR_MODAL = "op_v2_abrir_modal"  # pedido de reabrir o modal de acompanhamento (vem do cartão de rodada)
CTA_CSS = """<style>
.st-key-fl_cta { border-radius: 16px !important; border: 1.5px solid color-mix(in srgb, var(--primary-color, #0E7C86) 45%, rgba(128,128,128,.3)) !important;
  background: linear-gradient(160deg, color-mix(in srgb, var(--primary-color, #0E7C86) 9%, transparent), transparent 70%); margin-top: .7rem; }
.st-key-fl_cta { gap: .55rem !important; }
.st-key-fl_cta button[kind="primary"] { min-height: 2.7rem; font-weight: 760; letter-spacing: .04em; font-size: .9rem;
  box-shadow: 0 6px 18px color-mix(in srgb, var(--primary-color, #0E7C86) 28%, transparent); }
.st-key-fl_cta button[kind="primary"]:disabled { box-shadow: none; }
.rc-ey { font-size: .66rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; opacity: .62; display: flex; align-items: center; gap: .45rem; }
.rc-ey i { width: 8px; height: 8px; border-radius: 50%; background: currentColor; display: inline-block; }
.rc-ey.ok { color: #2E8B57; opacity: 1; } .rc-ey.b { color: #C2364A; opacity: 1; } .rc-ey.w { color: #C77700; opacity: 1; } .rc-ey.run { color: #2F6FED; opacity: 1; }
.rc-ey.run i { animation: rcled 1.4s ease-in-out infinite; } @keyframes rcled { 50% { opacity: .3; } }
@media (prefers-reduced-motion: reduce) { .rc-ey.run i { animation: none; } }
.rc-t { font-size: .98rem; font-weight: 760; line-height: 1.25; margin: .3rem 0 .1rem 0; }
.rc-s { font-size: .76rem; opacity: .75; line-height: 1.35; }
.rc-n { display: flex; flex-wrap: wrap; gap: .25rem .3rem; margin: .45rem 0 .1rem 0; }
.rc-n span { display: inline-flex; align-items: baseline; gap: .25rem; border-radius: 999px; padding: .12rem .5rem; font-size: .72rem;
  background: rgba(128,128,128,.1); font-variant-numeric: tabular-nums; }
.rc-n b { font-size: .86rem; } .rc-n .b b { color: #C2364A; } .rc-n .w b { color: #C77700; } .rc-n .ok b { color: #2E8B57; } .rc-n .z { opacity: .55; }
.rc-r { font-size: .76rem; line-height: 1.4; margin: .4rem 0 0 0; padding: .35rem .5rem; border-radius: 9px;
  background: color-mix(in srgb, #C2364A 8%, transparent); border-left: 3px solid #C2364A; }
.rc-r.w { background: color-mix(in srgb, #C77700 8%, transparent); border-left-color: #C77700; }
.rc-r.run { background: color-mix(in srgb, #2F6FED 8%, transparent); border-left-color: #2F6FED; }
</style>"""


def cartao_rodada(store, cur, dirty: bool, active, pf) -> None:
    """Cartão «Rodada · execução V2» (UI-FINISH-01, ponto 3B): o ÚNICO lugar do botão de executar da etapa 04 V2.
    Mesmo botão (chave, rótulo, ajuda), mesmas razões de bloqueio e a MESMA chamada ``X.submit`` com o ``request_id``
    idempotente de sempre; estado = contagens do preflight V2 da versão SALVA (nenhum número estimado)."""
    from . import execucao as X

    r = resumo_preflight(pf.report())
    req_key = f"op_ex_req_v2_{cur.scenario_uid}_{cur.version}"
    req = _ss().setdefault(req_key, X.new_request_id())
    reason = ("há alterações não salvas" if dirty else "o preflight V2 tem bloqueios" if not pf.ok else
              "outra rodada está em execução nesta microrrede" if active is not None else "")
    if active is not None:
        tom, titulo = "run", "Em execução"
        sub = (f"Rodada {active.run_uid[:8]}… · versão v{active.scenario_version}"
               + ("" if active.scenario_uid == cur.scenario_uid else " de OUTRO cenário desta microrrede"))
    elif dirty:
        tom, titulo, sub = "w", "Alterações não salvas", f"Salve o cenário: a execução usa sempre a versão salva v{cur.version}."
    elif not pf.ok:
        tom, titulo, sub = "b", "Execução bloqueada", f"Versão salva v{cur.version} · {r['bloqueios']} bloqueio(s) no preflight V2."
    else:
        tom, titulo, sub = "ok", f"Pronto para executar a versão salva v{cur.version}", ""
    n = lambda v, rot, cls: f'<span class="{cls if v else "z"}"><b>{v}</b>{rot}</span>'  # noqa: E731
    revisar = ""
    if r["areas_bloqueio"]:
        revisar = ('<div class="rc-r" data-rc="bloqueios"><b>Revisar:</b> ' + escape("; ".join(r["areas_bloqueio"]))
                   + ". Detalhes na seção ao lado.</div>")
    elif tom == "run":
        revisar = '<div class="rc-r run">A execução continua no servidor; o painel de acompanhamento mostra o progresso real.</div>'
    elif dirty:
        revisar = '<div class="rc-r w">Há alterações não salvas: salve para executá-las.</div>'
    st.html(CTA_CSS)
    with st.container(border=True, key="fl_cta"):
        st.html(f'<div data-rc="estado" data-tom="{tom}"><div class="rc-ey {tom}"><i></i>Rodada · execução V2</div>'
                f'<div class="rc-t">{escape(titulo)}</div>' + (f'<div class="rc-s">{escape(sub)}</div>' if sub else "") +
                f'<div class="rc-n" data-rc="contagens">{n(r["aprovadas"], "aprovadas", "ok")}{n(r["avisos"], "advertências", "w")}'
                f'{n(r["bloqueios"], "bloqueios", "b")}</div>{revisar}</div>')
        if st.button(f"▶ EXECUTAR MISSÃO V2 · VERSÃO {cur.version}", key="op_ex_run_v2", type="primary", disabled=bool(reason),
                     width="stretch",
                     help=f"Indisponível: {reason}." if reason else "Executa o EMS hierárquico MILP–MPC (HiGHS) sobre a versão salva."):
            try:
                run = X.submit(store, cur.scenario_uid, cur.version, req, background=True)
            except X.PreflightV2Error as exc:
                _ss().pop("op_ex_pf_v2", None)
                st.error(shell.md(exc))
                return
            except (RunBusyError, StoreError) as exc:
                st.error(shell.md(exc))
                return
            _ss().pop(req_key, None)                      # pedido consumido: o mesmo clique nunca executa duas vezes
            _ss()["op_flash"] = ("info", f"Rodada V2 {run.run_uid[:8]}… iniciada sobre a versão {cur.version}.")
            st.rerun()
        if reason:
            st.caption(f"Execução indisponível: {reason}.")
        if active is not None and st.button("VER PROGRESSO DA RODADA", key="op_ex_ver_v2", width="stretch",
                                             help="Reabre o painel de acompanhamento (não executa nada)."):
            _ss()[ABRIR_MODAL] = active.run_uid
            st.rerun()


def render_execucao(store, cur, dirty: bool, active, live) -> None:
    """Corpo da etapa 04 para o motor V2 (janela da missão, barra de salvar e histórico ficam com a página comum)."""
    try:
        pf = preflight(store, cur)
    except StoreError as exc:
        st.error(shell.md(exc))
        return
    regua(cur.document, titulo=f"Régua dos horizontes · versão salva v{cur.version} (a que será executada)",
          key="seeds_folha_regua_04")
    relatorio_preflight(pf.report(), pf.matriz, cur.version)
    st.markdown('<div class="sd-section">Executar (motor V2 experimental)</div>', unsafe_allow_html=True)
    if active is not None:
        if e_v2(active):
            _ss()[SEGUIR] = active.run_uid                # UI-RUNNING-01: o desfecho desta rodada será mostrado
        live(store, active.run_uid)
    else:
        fim = seguir_desfecho(store, cur)                 # rodada acompanhada que terminou: desfecho até ser dispensado
        if fim is not None:
            live(store, fim.run_uid)
    # UI-FINISH-01: o botão de executar fica UM só, no cartão de rodada sob a Folha de Ensaio (coluna esquerda). A Folha
    # abre o «slot» antes da etapa e desenha o cartão depois do índice; fora da Folha o cartão é desenhado aqui mesmo.
    cta = lambda: cartao_rodada(store, cur, dirty, active, pf)  # noqa: E731
    slot = _ss().get(CTA_SLOT)
    if isinstance(slot, list):
        slot.append(cta)
        st.html('<div class="op-d" data-rc="aponta">O botão <b>EXECUTAR MISSÃO V2</b> está no cartão <b>Rodada · execução '
                'V2</b>, logo abaixo da Folha de Ensaio, com o resumo da prontidão desta versão salva.</div>')
    else:
        cta()


def progresso(run) -> None:
    p = run.progress or {}
    fase = p.get("phase", "preparando")
    if fase == "missao" and p.get("n"):
        k, n = int(p.get("k", 0)), int(p["n"])
        st.progress(min(k / n, 1.0), text=f"{FASES['missao']} · intervalo {k} de {n} · {int(p.get('janelas', 0))} janela(s)")
    else:
        st.caption("⏳ " + FASES.get(fase, fase))


# ======================================================================= UI-RUNNING-01: modal de acompanhamento
# O modal SÓ LÊ o que o runner já grava (``run.progress``: fase, k de n intervalos, janelas — o mesmo mecanismo do cartão
# «Execução em andamento») e é redesenhado pelo fragmento existente (``execution_ui._live``, 1 s). Nenhum progresso é
# estimado: porcentagem só na fase «missao» com k < n; nas demais fases a barra é indeterminada; 100 % só com a rodada
# CONCLUÍDA no banco. Ocultar o painel é estado do navegador; CANCELAR é uma ação real (``cancelar``).
SEGUIR = "op_v2_seguir"                          # rodada V2 acompanhada nesta sessão (mostra o desfecho até ser dispensado)
CANCEL_KIND = "cancelada_pelo_usuario"
RERUN_APP = "op_v2_rerun_app"                  # ação do modal que muda a página inteira (FECHAR, VER DIAGNÓSTICO)
RESPOSTA_CANCEL = "op_v2_cancel_resp_"          # + run_uid: última resposta do servidor a um pedido de cancelamento
# UI-FINISH-01 (ponto 4): a cada ciclo do fragmento (1 s) o Streamlit marca o contêiner do componente como «stale» e lhe dá
# ``transition: opacity 1s ease-in 0.5s``. Medido em Chromium: enquanto essa transição está pendente o contêiner vira uma
# nova RAIZ DE FUNDO (backdrop root) e o ``backdrop-filter`` do overlay só desfoca o que está DENTRO dele — o resto da
# página aparece nítido por alguns quadros (o «piscar»). O modal nunca deve esmaecer como conteúdo desatualizado: só o
# contêiner dele fica fora desse efeito (os demais elementos da página continuam com o comportamento do Streamlit).
MODAL_ESTAVEL_CSS = ("<style>.st-key-seeds_execucao, .st-key-seeds_execucao[data-stale=\"true\"] "
                     "{ transition: none !important; opacity: 1 !important; }</style>")
FASES_MODAL = ("fila", "montagem", "missao", "auditoria", "gravando")


def _cancelada(run) -> bool:
    return run.state == "interrompida" and (run.error or {}).get("kind") == CANCEL_KIND


def cancelar(store, run_uid: str) -> tuple[str, str]:
    """Cancelamento COOPERATIVO de uma rodada V2 em execução NESTE processo, pela API existente do armazenamento:
    ``fail_run(estado = 'interrompida')`` — transação condicionada a «em execução por este dono». O runner percebe no
    próximo ``beat`` (entre janelas, antes da auditoria ou da gravação: ``RunStateError``) e termina SEM gravar nada; a
    janela em curso não é interrompida no meio do solver (termina e é descartada). Nenhum resultado parcial vira
    resultado; nenhuma outra rodada é afetada. Devolve (situação, mensagem)."""
    from datetime import datetime, timezone

    from seeds2.microgrid.store import RunNotFound, RunStateError

    from . import execucao as X

    try:
        run = store.get_run(run_uid)
    except RunNotFound:
        return "inexistente", "A rodada não existe nesta microrrede."
    if run.state != "em_execucao":
        return "finalizada", f"A rodada já terminou ({run.state}); nada foi cancelado."
    if not X.is_running_here(run_uid):
        return "outro_processo", ("A rodada é executada por outro processo do servidor: o cancelamento só é possível no "
                                  "processo que a executa. Nada foi alterado.")
    p = run.progress or {}
    if p.get("phase") in ("auditoria", "gravando"):
        return "tarde", ("A missão já terminou e a auditoria/gravação atômica está em andamento: não é possível cancelar "
                         "agora. Nada foi alterado.")
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    k, n = p.get("k"), p.get("n")
    msg = ("Execução CANCELADA pelo usuário" + (f" após {k} de {n} intervalo(s) aplicado(s)" if k is not None and n else "")
           + ". A janela em curso foi descartada; nenhum resultado foi gravado (o custo parcial não é o custo da missão).")
    try:
        store.fail_run(run_uid, X.OWNER, {"kind": CANCEL_KIND, "message": msg, "requested_utc": agora,
                                         "progress_at_request": dict(p)},
                       state="interrompida",
                       outcome={"engine": {"id": E.MOTOR_V2}, "mission": None,
                                "cancelamento": {"solicitado_utc": agora, "progresso_no_pedido": dict(p)}})
    except RunStateError:
        return "finalizada", "A rodada terminou antes do pedido de cancelamento; nada foi cancelado."
    return "solicitado", msg


def dados_modal(run, *, vivo: bool) -> dict:
    """Estado do modal a partir SÓ da rodada gravada (sem estimativas). ``vivo`` = a thread do runner ainda roda aqui."""
    man = run.manifest if isinstance(run.manifest, dict) else {}
    mis = man.get("mission") if isinstance(man.get("mission"), dict) else {}
    p = run.progress if isinstance(run.progress, dict) else {}
    fase = p.get("phase") or "preparando"
    k = p.get("k") if isinstance(p.get("k"), int) else None
    n = p.get("n") if isinstance(p.get("n"), int) and p.get("n") > 0 else None
    err = run.error or {}
    if run.state == "em_execucao":
        situacao = "andamento"
    elif run.state == "concluida":
        situacao = "concluida"
    elif _cancelada(run):
        situacao = "cancelando" if vivo else "cancelada"
    else:
        situacao = "falha"
    determinado = situacao == "andamento" and fase == "missao" and k is not None and n is not None and k < n
    cancelavel, motivo = False, None
    if situacao == "andamento":
        if not vivo:
            motivo = "A rodada é executada por outro processo do servidor: o cancelamento só é possível nele."
        elif fase in ("auditoria", "gravando"):
            motivo = "A missão terminou; auditoria e gravação em andamento — não é possível cancelar agora."
        else:
            cancelavel = True
    return {"run": run.run_uid, "curto": run.run_uid[:8], "estado": run.state, "situacao": situacao, "fase": fase,
            "fase_rotulo": FASES.get(fase, fase), "fases": list(FASES_MODAL),
            "k": k, "n": n, "janelas": p.get("janelas") if isinstance(p.get("janelas"), int) else None,
            "determinado": determinado, "fracao": (k / n) if determinado else (1.0 if situacao == "concluida" else None),
            "N": mis.get("N"), "m": mis.get("m"), "H_L": mis.get("H_L"), "delta_min": mis.get("delta_min"),
            "cenario": (man.get("scenario") or {}).get("name") or "cenário", "versao": run.scenario_version,
            "motor": "EMS V2 · MILP–MPC hierárquico (experimental)", "inicio": shell.fmt_time(run.created_at),
            "cancelavel": cancelavel, "motivo_cancelamento": motivo,
            "mensagem": (err.get("message") or "")[:900] if situacao in ("falha", "cancelando", "cancelada") else "",
            "titulo_falha": "Missão interrompida" if run.state == "interrompida" else "Falha na execução"}


def _acao_modal(store, open_run) -> None:
    a = shell.payload("seeds_execucao")
    if not a or not a.get("run"):
        return
    ss = _ss()
    if a.get("type") == "cancelar":
        situacao, mensagem = cancelar(store, str(a["run"]))
        # resposta REAL do servidor, vinculada ao pedido do navegador (``t``): o modal só sai de «solicitado» com ela
        ss[RESPOSTA_CANCEL + str(a["run"])] = {"pedido": a.get("t"), "situacao": situacao, "mensagem": mensagem}
    elif a.get("type") == "diagnostico":
        ss.pop(SEGUIR, None)
        open_run(str(a["run"]))
        ss[RERUN_APP] = True          # ``st.rerun`` num callback não tem efeito: o próximo ciclo do fragmento o pede
    elif a.get("type") == "fechar":
        ss.pop(SEGUIR, None)
        ss[f"op_v2_ok_{a['run']}"] = True
        ss[RERUN_APP] = True          # mesmo efeito do «OK» da página: o desfecho sai da tela inteira, não só o painel


def acompanhar(store, run, *, open_run, vivo: bool) -> None:
    """Corpo do fragmento de acompanhamento para uma rodada V2 (chamado por ``execution_ui._live`` a cada 1 s): cartão
    de estado da página (fallback sempre visível) + modal. Concluída ⇒ «Concluída» por um ciclo e abertura da rodada
    (comportamento anterior); falha/interrupção/cancelamento ⇒ o desfecho fica visível até o usuário dispensar."""
    from seeds2.ui import trama

    ss = _ss()
    if ss.pop(RERUN_APP, False):
        st.rerun(scope="app")
    d = dados_modal(run, vivo=vivo)
    if d["situacao"] == "concluida":
        chave = f"op_v2_fim_{run.run_uid}"
        if ss.get(chave):
            ss.pop(SEGUIR, None)
            ss["op_flash"] = ("ok", f"Rodada {run.run_uid[:8]}… concluída.")
            open_run(run.run_uid)
            st.rerun(scope="app")
        ss[chave] = True
    resp = ss.get(RESPOSTA_CANCEL + run.run_uid)
    if resp:
        d["resposta_cancelamento"] = dict(resp)
    if ss.get(ABRIR_MODAL) == run.run_uid:            # UI-FINISH-01: «VER PROGRESSO DA RODADA» do cartão de rodada
        ss.pop(ABRIR_MODAL, None)
        ss["op_v2_abrir_n"] = int(ss.get("op_v2_abrir_n", 0)) + 1
        d["abrir"] = ss["op_v2_abrir_n"]
    with st.container(border=True):
        if d["situacao"] == "andamento":
            st.html(f'<div class="op-row"><div class="op-t">Execução em andamento · rodada {escape(run.run_uid[:8])}…</div>'
                    '<span class="op-pill info">Em execução</span></div><p class="op-d">Cenário v'
                    f'{run.scenario_version} · iniciada {escape(shell.fmt_time(run.created_at))}. A execução continua no '
                    'servidor mesmo que esta página seja recarregada ou fechada.</p>')
            progresso(run)
        else:
            tom = {"concluida": "ok", "cancelando": "warn", "cancelada": "warn"}.get(d["situacao"], "bad")
            rot = {"concluida": "Concluída", "cancelando": "Cancelamento solicitado", "cancelada": "Cancelada"}.get(
                d["situacao"], d["titulo_falha"])
            st.html(f'<div class="op-row"><div class="op-t">{escape(rot)} · rodada {escape(run.run_uid[:8])}…</div>'
                    f'<span class="op-pill {tom}">{escape(rot)}</span></div>'
                    + (f'<p class="op-d">{escape(d["mensagem"])}</p>' if d["mensagem"] else ""))
            if d["situacao"] != "concluida":
                c1, c2, _ = st.columns([1.2, 1, 3])
                if c1.button("VER DIAGNÓSTICO", key=f"op_v2_diag_{run.run_uid}", width="stretch"):
                    ss.pop(SEGUIR, None)
                    open_run(run.run_uid)
                    st.rerun(scope="app")
                if c2.button("OK", key=f"op_v2_ok_btn_{run.run_uid}", width="stretch",
                             disabled=d["situacao"] == "cancelando"):
                    ss.pop(SEGUIR, None)
                    ss[f"op_v2_ok_{run.run_uid}"] = True
                    st.rerun(scope="app")
        st.html(MODAL_ESTAVEL_CSS)
        trama.pagina("execucao", d, key="seeds_execucao", on_action=lambda: _acao_modal(store, open_run), wide=False)


def seguir_desfecho(store, cur):
    """Rodada V2 acompanhada nesta sessão que JÁ terminou e cujo desfecho ainda não foi dispensado (ou ``None``)."""
    uid = _ss().get(SEGUIR)
    if not uid:
        return None
    try:
        r = store.get_run(uid)
    except StoreError:
        _ss().pop(SEGUIR, None)
        return None
    if r.state == "em_execucao":
        return None                                   # ainda ativa: o fluxo normal (rodada ativa) a acompanha
    if r.scenario_uid != cur.scenario_uid or _ss().get(f"op_v2_ok_{uid}"):
        _ss().pop(SEGUIR, None)
        return None
    return r


# ======================================================================= rodada V2 (somente leitura)
def _verificacao(source, run):
    cache = _ss().setdefault("op_v2_verif", {})
    chave = (run.run_uid, run.state, getattr(source, "archive_uid", None) or "local")
    if chave not in cache:
        if len(cache) > 8:
            cache.clear()
        cache[chave] = RG.verificar(source, run)
    return cache[chave]


def _nomes_do_inventario(source, run) -> dict:
    """{uid: (nome, tag)} do inventário de referência da versão do cenário executada, quando a origem o expõe."""
    try:
        doc = source.get_scenario(run.scenario_uid, run.scenario_version).document
        return {eid: (ref.get("name"), ref.get("tag")) for eid, ref in doc["inventory_ref"]["equipment"].items()}
    except (AttributeError, KeyError, TypeError, StoreError):
        return {}


CLASSICA = "Vista clássica — tabelas completas, gráficos anteriores, descargas e procedência"


def _partitura(source, run, v, key: str) -> bool:
    """Piso 3D-B — instrumento Partitura (motor gráfico Trama) sobre os dados GRAVADOS da rodada. Só é desenhado com a
    evidência verificada; o marco de dados é montado uma vez por sessão e rodada. Devolve ``True`` se foi desenhado
    (a vista clássica fica então recolhida num expansor identificado; senão continua aberta, como antes)."""
    if not v.ok:
        return False
    from seeds2.ui import trama as TR

    from . import trama_frame as TF

    cache = _ss().setdefault("op_v2_frame", {})
    # origem do marco: estudo ARQUIVADO (identidade local do arquivo) ou microrrede aberta — nunca compartilham cache
    chave = (run.run_uid, getattr(getattr(source, "study", None), "archive_uid", None) or "local")
    if chave not in cache:
        if len(cache) > 4:
            cache.clear()
        try:
            cache[chave] = TF.montar(source, run, verificacao=v, nomes=_nomes_do_inventario(source, run))
        except (StoreError, KeyError, ValueError, TypeError) as exc:
            st.caption(f"Partitura indisponível para esta rodada ({shell.md(exc)}). A vista clássica abaixo continua "
                       "completa.")
            return False
    TR.partitura(cache[chave], key=f"{key}_partitura")
    return True


def planta_rodada(source, run) -> dict | None:
    """Piso 3D-B2-B — valores GRAVADOS de uma rodada V2 concluída, por UID, para a Planta da microrrede. É uma SELEÇÃO do
    marco da Partitura (``trama_frame``): nenhuma aritmética, nenhum solver, nenhum modelo. ``None`` se a evidência não for
    verificada ou o marco não puder ser montado (a Planta mostra então só o inventário)."""
    from . import trama_frame as TF

    try:
        v = RG.verificar(source, run)
        if not v.ok:
            return None
        f = TF.montar(source, run, verificacao=v)
    except (StoreError, KeyError, ValueError, TypeError):
        return None
    it, series = f["intervalos"], {}
    for u, r in f["renovaveis"].items():
        series[u] = {"p": r.get("P_R_kW"), "pot": r.get("A_utilizavel_kW")}
    for u, b in f["baterias"].items():
        series[u] = {"pd": b.get("P_d_kW"), "pc": b.get("P_c_kW"), "e": b.get("energia_kWh")}
    for u, g in f["pemfc"].items():
        series[u] = {"p": g.get("p_kW"), "u": g.get("u"), "q": g.get("q_h2_kg_h")}
    con = f["pcc"]["modo"] == "conectado"
    return {"uid": run.run_uid, "cenario": f["rodada"]["cenario"], "versao": f["rodada"]["versao_cenario"], "K": f["rodada"]["K"],
            "delta_min": f["rodada"]["delta_min"], "local": f["fronteiras"]["local"], "revisao": f["rodada"]["revisao_inventario"],
            "series": series, "hash": f["hash"],
            "demanda": {"realizada": it.get("demanda_realizada_kW"), "atendida": it.get("demanda_atendida_kW")},
            "pcc": {"conectado": con, "imp": it.get("pcc_importacao_realizada_kW") if con else None,
                    "exp": it.get("pcc_exportacao_realizada_kW") if con else None,
                    "tarifa": it.get("tarifa_importacao_decisao_R_kWh") if con else None}}


def _provenance(run) -> None:
    m = run.manifest
    with st.expander("Procedência da rodada (manifesto imutável)"):
        ref, sw, eng = m.get("reference") or {}, m.get("software") or {}, m.get("engine") or {}
        rows = [("Microrrede", f"{ref.get('microgrid_uid')} · incarnação {ref.get('microgrid_incarnation')}"),
                ("Cenário", f"{ref.get('scenario_uid')} · v{ref.get('scenario_version')} · "
                            f"{str(ref.get('scenario_fingerprint'))[:16]}…"),
                ("Inventário", f"revisão {ref.get('config_revision')} · {str(ref.get('config_fingerprint'))[:16]}…"),
                ("Motor", f"{eng.get('id')} · formulações {eng.get('formulations')} · integração {eng.get('integration')}"),
                ("Solver", f"Pyomo {sw.get('pyomo')} · highspy {sw.get('highspy')} · HiGHS {sw.get('highs')} · Python "
                           f"{sw.get('python')}"),
                ("Código do motor V2", f"SHA-256 {str((sw.get('science') or {}).get('sha256'))[:16]}… "
                                       f"({(sw.get('science') or {}).get('files')} arquivos)"),
                ("Alcance", m.get("scope") or "")]
        st.html('<table class="op-tbl">' + "".join(f"<tr><td>{escape(a)}</td><td>{escape(str(b))}</td></tr>" for a, b in rows)
                + "</table>")
        st.json(m, expanded=False)


def _figuras(it, fr, bats: list[str], key: str, rens: list[str] = (), gers: list[str] = ()) -> None:
    import plotly.graph_objects as go

    x = it["intervalo"]
    fig = go.Figure()
    fig.add_bar(x=x, y=it["pcc_importacao_realizada_kW"] if "pcc_importacao_realizada_kW" in it else None,
                name="Importação da rede (realizada)")
    for u in rens:
        fig.add_bar(x=x, y=it[f"{u}|P_R_kW"], name=f"Renovável {u} (aproveitada)")
    for u in gers:
        fig.add_bar(x=x, y=it[f"{u}|p_kW"], name=f"PEMFC {u}")
    for b in bats:
        fig.add_bar(x=x, y=it[f"{b}|P_d_kW"], name=f"Descarga {b}")
    fig.add_scatter(x=x, y=it["demanda_realizada_kW"], name="Demanda realizada", mode="lines+markers",
                    line={"shape": "hvh", "color": "#222"})
    fig.add_scatter(x=x, y=it["demanda_prevista_kW"], name="Demanda prevista (na decisão)", mode="lines",
                    line={"shape": "hvh", "dash": "dot", "color": "#888"})
    for b in bats:
        fig.add_bar(x=x, y=-it[f"{b}|P_c_kW"], name=f"Carga {b} (consumo; não é geração)")
    fig.update_layout(barmode="relative", height=380, margin={"l": 50, "r": 10, "t": 96, "b": 44},
                      title="Demanda × atendimento por recurso — médias de intervalo [kW]",
                      xaxis_title="intervalo aplicado (índice global)", yaxis_title="kW",
                      legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0})
    st.plotly_chart(fig, key=f"{key}_pot", width="stretch")
    fig2 = go.Figure()
    for b in bats:
        fig2.add_scatter(x=fr["fronteira"], y=fr[f"{b}|energia_kWh"], name=f"Energia {b}", mode="lines+markers")
    fig2.update_layout(height=300, margin={"l": 50, "r": 10, "t": 76, "b": 44},
                       title="Energia armazenada nas fronteiras de estado [kWh] (N + 1 pontos)",
                       xaxis_title="fronteira (índice global)", yaxis_title="kWh",
                       legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0})
    st.plotly_chart(fig2, key=f"{key}_ene", width="stretch")
    if rens:
        fig3 = go.Figure()
        for u in rens:
            fig3.add_bar(x=x, y=it[f"{u}|P_R_kW"], name=f"Aproveitada {u}")
            fig3.add_bar(x=x, y=it[f"{u}|vertimento_kW"], name=f"Vertida {u}")
            fig3.add_scatter(x=x, y=it[f"{u}|A_utilizavel_kW"], name=f"Disponível a·A {u}", mode="lines+markers",
                             line={"shape": "hvh", "dash": "dot"})
        fig3.update_layout(barmode="stack", height=340, margin={"l": 50, "r": 10, "t": 96, "b": 44},
                           title="Potencial renovável por UID: disponível × aproveitado × vertido [kW]",
                           xaxis_title="intervalo aplicado (índice global)", yaxis_title="kW",
                           legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0})
        st.plotly_chart(fig3, key=f"{key}_ren", width="stretch")


def _downloads(source, run, key: str) -> None:
    st.markdown('<div class="sd-section">Dados gravados (originais; SHA-256 do conteúdo)</div>', unsafe_allow_html=True)
    st.caption("Relatórios PDF/Excel/figuras do Piso 2D-B ainda não cobrem o motor V2 (previstos para os pisos seguintes). "
               "Os dados integrais desta rodada estão abaixo e no pacote .seeds2study.zip do cenário.")
    for nome, d in run.data.items():
        c1, c2 = st.columns([4, 1.2], vertical_alignment="center")
        c1.html(f'<span class="op-m">{escape(nome)}</span> · {d["size"]:,} bytes · {escape(d["sha256"][:16])}…')
        try:
            c2.download_button("Baixar", source.run_data(run.run_uid, nome), file_name=nome.replace("/", "_"),
                               mime=d["media_type"], key=f"{key}_dl_{nome}", width="stretch")
        except StoreError as exc:
            c2.caption(str(exc)[:60])


def _aceitacao(run) -> None:
    """Estados de aceitação SEPARADOS (auditoria do PR #23, B): algébrico × dinâmico × físico. Rodadas anteriores ao
    3D-A2-H (sem o campo) mostram só a aceitação algébrica implícita em ``concluida``."""
    acc = ((run.summary or {}).get("execution") or {}).get("aceitacao")
    if not acc:
        return
    din = acc.get("dinamica") or {}
    tom = {"coerente": "ok", "incoerente": "bad"}.get(din.get("estado"), "")
    st.html('<table class="op-tbl"><tr><th>Critério de aceitação</th><th>Estado</th><th>Critério</th></tr>'
            f"<tr><td>Algébrico (MILP–MPC + auditoria independente)</td><td><b>APROVADO</b></td>"
            f"<td>{escape((acc.get('algebrica') or {}).get('criterio') or '')}</td></tr>"
            f"<tr><td>Dinâmico (modelo dinâmico aproximado da PEMFC)</td><td><b>"
            f"{escape({'coerente': 'COERENTE', 'incoerente': 'INCOERENTE', 'nao_aplicavel': 'não aplicável'}.get(din.get('estado'), '—'))}"
            f"</b></td><td>{escape(din.get('criterio') or '')}</td></tr>"
            f"<tr><td>Físico (equipamento real)</td><td><b>NÃO VALIDADO</b></td>"
            f"<td>{escape((acc.get('fisica') or {}).get('motivo') or '')}</td></tr></table>")
    shell.callout(f"<b>{escape(acc.get('rotulo') or '')}</b>", tom or "warn")
    if din.get("estado") == "incoerente":
        n = sum((din.get("intervalos_incoerentes") or {}).values())
        st.error(f"DINAMICAMENTE INCOERENTE — {n} intervalo(s) fora das tolerâncias. O custo e a energia exibidos abaixo são "
                 "os do despacho ALGÉBRICO; o modelo dinâmico entregaria outra potência/consumiria outra massa de H₂ "
                 "(detalhes em v2/pemfc_dinamica.json). Não usar como operação executável.")


def run_results(source, run, *, key: str) -> None:
    """Rodada V2 FINALIZADA lida de ``source`` (``MicrogridStore`` ou estudo arquivado). Nunca chama o otimizador."""
    m = run.manifest
    v = _verificacao(source, run)
    desenhada = run.state == "concluida" and _partitura(source, run, v, key)      # Piso 3D-B: instrumento Partitura
    shell.callout(f"<b>Motor V2 experimental (MILP–MPC hierárquico).</b> {escape(m.get('scope') or PF.ESCOPO)} Dados "
                  "sintéticos/declarados estão rotulados na procedência.", "warn")
    exportacoes(source, run, key)                 # UI-FINISH-01: área de exportações VISÍVEL (não dentro da vista clássica)
    if not desenhada:                         # rodada falha/interrompida, evidência com problemas ou marco indisponível
        _vista_classica(source, run, v, key)
        return
    # Decisão do responsável (3D-B3): com a Partitura desenhada, a vista clássica fica RECOLHIDA por padrão, inteira e
    # acessível num expansor identificado (tabelas originais, gráficos anteriores, descargas, procedência).
    with st.expander(CLASSICA, expanded=False):
        st.caption("Vista anterior ao Piso 3D-B, mantida inteira durante a migração para a Partitura. Os números são os "
                   "mesmos: as duas vistas leem os dados gravados da rodada.")
        _vista_classica(source, run, v, key)


def exportacoes(source, run, key: str) -> None:
    """Exportações científicas da rodada V2 (UI-FINISH-01, ponto 6): o MESMO painel do Piso 2D-B
    (``seeds2.ui.report_exports.render``: geração sob demanda, progresso real, cache por rodada, erros sem perder a
    página) com os geradores V2 de ``documentos`` (dossiê, figuras e escritores do 2D-B sobre o contrato ``v2/…``)."""
    from seeds2.ui import report_exports as RX

    from . import documentos as DOC

    done = run.state == "concluida"
    with st.container(key=f"{key}_exportacoes_v2"):
        RX.render(source, run, key=f"{key}_v2", gerador=DOC.gerar, rotulos=DOC.ROTULOS if done else DOC.ROTULOS_DIAG,
                  ajudas=DOC.AJUDAS)


def _vista_classica(source, run, v, key: str) -> None:
    """Página da rodada V2 anterior ao Piso 3D-B (verificação, indicadores, figuras Plotly, tabelas, descargas e
    procedência). Conteúdo inalterado; só o invólucro mudou."""
    with st.expander(("✓ Evidência verificada" if v.ok else "✕ EVIDÊNCIA COM PROBLEMAS") +
                     " — reabertura sem otimizador (hashes, vistas regeneradas, auditoria integral)", expanded=not v.ok):
        st.html("".join(shell.check(escape(t), "ok" if ok else "bad") for ok, t in v.itens))
    if run.state != "concluida":
        err = run.error or {}
        shell.callout(f"<b>Rodada {escape(run.state)}</b> — {escape(err.get('message') or '')} Nenhum resultado foi gravado "
                      "como concluído.", "bad")
        ev = (run.outcome or {}).get("evidence")
        if isinstance(ev, dict) and ev.get("vistas"):
            import pandas as pd

            st.markdown('<div class="sd-section">Evidência PARCIAL da missão (até a interrupção)</div>', unsafe_allow_html=True)
            st.caption(ev.get("aviso") or "")
            for nome in ("intervalos", "janelas"):
                t = ev["vistas"].get(nome) or {}
                if t.get("linhas"):
                    st.caption(f"{nome} (parcial)")
                    st.dataframe(pd.DataFrame(t["linhas"], columns=t["colunas"]), hide_index=True, width="stretch")
        _provenance(run)
        return
    _aceitacao(run)
    s = (run.summary or {}).get("mission") or {}
    comp = s.get("custo_realizado_componentes_R") or {}
    sv = s.get("sinal_valor_futuro") or {}
    shell.kpis([
        ("Custo REALIZADO", f"R$ {forms.fmt(s.get('custo_realizado_total_R'), 2)}",
         "sem valor futuro · " + ", ".join(f"{k} {forms.fmt(x, 2)}" for k, x in comp.items())),
        ("Energia atendida", forms.fmt(s.get("energia_atendida_kWh"), 2, "kWh"),
         f"de {forms.fmt(s.get('energia_demanda_kWh'), 2, 'kWh')} demandados"),
        ("Não atendida", forms.fmt(s.get("energia_nao_atendida_kWh"), 3, "kWh"), "déficit (serviço duro)"),
        ("Importada da rede", forms.fmt(s.get("energia_importada_kWh"), 2, "kWh"),
         f"exportada {forms.fmt(s.get('energia_exportada_kWh'), 2, 'kWh')}"),
        ("Janelas · sinal válido", f"{s.get('janelas')} · {sv.get('valido', '—')}",
         f"N = {s.get('N')} · m = {s.get('m')} · H_L = {s.get('H_L')} · Δ = {forms.fmt(s.get('delta_min'), 0, 'min')}")])
    bats = list((s.get("baterias") or {}))
    if bats:
        st.html('<table class="op-tbl"><tr><th>Banco (UID)</th><th>Energia inicial → final [kWh]</th><th>SOC inicial → final'
                '</th><th>Carregada [kWh]</th><th>Descarregada [kWh]</th></tr>' + "".join(
                    f"<tr><td class='op-m'>{escape(u)}</td><td>{forms.fmt(b['energia_inicial_kWh'], 3)} → "
                    f"{forms.fmt(b['energia_final_kWh'], 3)}</td><td>{forms.fmt(100 * b['soc_inicial'], 1)} % → "
                    f"{forms.fmt(100 * b['soc_final'], 1)} %</td><td>{forms.fmt(b['energia_carregada_kWh'], 3)}</td>"
                    f"<td>{forms.fmt(b['energia_descarregada_kWh'], 3)}</td></tr>" for u, b in s["baterias"].items())
                + "</table>")
    ren = s.get("renovaveis") or {}
    if ren:
        st.html('<table class="op-tbl"><tr><th>Renovável (UID)</th><th>Tecnologia</th><th>Potencial utilizável [kWh]</th>'
                '<th>Aproveitada [kWh]</th><th>Vertida [kWh]</th><th>Pico aproveitado [kW]</th></tr>' + "".join(
                    f"<tr><td class='op-m'>{escape(u)}</td><td>{escape({'fv': 'Fotovoltaica', 'eolica': 'Eólica'}.get(r['tecnologia'], r['tecnologia']))}"
                    f"</td><td>{forms.fmt(r['energia_utilizavel_kWh'], 3)}</td><td>{forms.fmt(r['energia_aproveitada_kWh'], 3)}"
                    f"</td><td>{forms.fmt(r['energia_vertida_kWh'], 3)}</td><td>{forms.fmt(r['pico_aproveitado_kW'], 3)}</td></tr>"
                    for u, r in ren.items()) + "</table>")
        st.caption("Potencial derivado pelos modelos físicos do SEEDS2 no preflight da rodada e GRAVADO (v2/renovaveis.json); "
                   "a reabertura não reexecuta modelos nem otimizador. Realização renovável = previsão (sem erro de previsão "
                   "renovável nesta simulação).")
    pem = s.get("pemfc") or {}
    if pem:
        din = ((run.summary or {}).get("execution") or {}).get("pemfc_dinamica") or {}
        st.html('<table class="op-tbl"><tr><th>PEMFC (unidade)</th><th>Energia [kWh]</th><th>H₂ suprido [kg]</th>'
                '<th>Custo H₂ [R$]</th><th>Consumo específico [kg/kWh]</th><th>Partidas · paradas</th>'
                '<th>Verificação dinâmica</th><th>Subestimação de H₂ (EMS × dinâmico) [kg]</th></tr>' + "".join(
                    f"<tr><td class='op-m'>{escape(u)}</td><td>{forms.fmt(r['energia_kWh'], 3)}</td>"
                    f"<td>{forms.fmt(r['massa_h2_kg'], 4)}</td><td>{forms.fmt(r['custo_h2_R'], 2)}</td>"
                    f"<td>{forms.fmt(r['consumo_especifico_kg_kWh'], 4)}</td><td>{r['partidas']} · {r['paradas']}</td>"
                    f"<td>{'coerente' if (din.get(u) or {}).get('coerente') else 'INCOERENTE'} "
                    f"({forms.fmt((din.get(u) or {}).get('energia_entregue_kWh'), 2)} de "
                    f"{forms.fmt((din.get(u) or {}).get('energia_solicitada_kWh'), 2)} kWh)</td>"
                    f"<td>máx. {forms.fmt((din.get(u) or {}).get('h2_subestimacao_max_kg'), 4)} · total "
                    f"{forms.fmt((din.get(u) or {}).get('h2_subestimacao_total_kg'), 4)}</td></tr>"
                    for u, r in pem.items()) + "</table>")
        st.caption("Curva q(P) derivada do modelo físico APROXIMADO com certificado B04 (v2/pemfc.json); consignas avaliadas "
                   "a posteriori pelo modelo dinâmico (v2/pemfc_dinamica.json). A abstração instantânea do MILP não é "
                   "validação física; consignas fora das tolerâncias são declaradas NÃO coerentes. O H₂ do EMS NÃO é cota "
                   "superior global: as massas por evento são conservadoras, mas rampas de DESCIDA em operação contínua "
                   "consomem um pouco mais no modelo dinâmico (subestimação mostrada por unidade).")
    try:
        it, fr = RG.ler_csv(source, run, RG.N_INTERVALOS), RG.ler_csv(source, run, RG.N_FRONTEIRAS)
        ja = RG.ler_csv(source, run, RG.N_JANELAS)
    except StoreError as exc:
        st.error(shell.md(exc))
        return
    _figuras(it, fr, bats, key, list(ren), list(pem))
    with st.expander("Intervalos aplicados (dados originais gravados)"):
        st.dataframe(it, hide_index=True, width="stretch")
    with st.expander("Decisões por janela: solver, gap, custos planejado × realizado, sinal de valor futuro"):
        st.dataframe(ja, hide_index=True, width="stretch")
    avisos = ((run.summary or {}).get("execution") or {}).get("avisos") or []
    if avisos:
        st.markdown('<div class="sd-section">Advertências do preflight V2 registradas na rodada</div>', unsafe_allow_html=True)
        st.html("".join(shell.check(escape(a), "warn") for a in avisos))
    _downloads(source, run, key)
    _provenance(run)


def estrategia_arquivada(doc: dict) -> None:
    """Estratégia V2 de uma versão de cenário ARQUIVADA (somente leitura)."""
    st.html('<table class="op-tbl">' + f"<tr><td>Motor selecionado</td><td>{escape(E.MOTORES.get(motor(doc), motor(doc)))}"
            "</td></tr></table>")
    if doc.get(E.CHAVE_BLOCO) is not None:
        st.json(doc[E.CHAVE_BLOCO], expanded=False)


__all__ = ["MOTOR_V2", "custo_texto", "e_v2", "estrategia_arquivada", "motor", "planta_rodada", "preflight", "progresso",
           "relatorio_preflight", "render_estrategia", "render_execucao", "run_results", "seletor_motor", "stage_state"]
_ = json
