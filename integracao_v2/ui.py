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
    if E.erros_estruturais(b, doc) and set(b) != set(E.novo_bloco(doc)):
        st.error("A estratégia V2 gravada tem estrutura incompatível com esta versão do formulário.")
        oc._save_bar(store, cur, I.summarize(S.findings(doc)))
        return
    k = f"opw_sg_{tok}_v2"
    c1, c2 = st.columns(2, gap="large")
    with c1, st.container(border=True):
        st.html('<div class="op-k">Malha temporal (N intervalos · N + 1 fronteiras)</div>')
        m = b["malha"]
        a1, a2 = st.columns(2)
        with a1:
            m["delta_min"] = _num("Passo Δ [min]", m["delta_min"], f"{k}_delta", inteiro=True, minimo=1,
                                  ajuda="Igual ao passo da série de demanda: o motor não reamostra.")
            m["m"] = _num("Bloco aplicado m [intervalos]", m["m"], f"{k}_m", inteiro=True, minimo=1)
        with a2:
            m["N"] = _num("Horizonte curto N [intervalos]", m["N"], f"{k}_N", inteiro=True, minimo=1)
            m["H_L"] = _num("Horizonte longo H_L [intervalos]", m["H_L"], f"{k}_HL", inteiro=True, minimo=2,
                            ajuda="H_L > N e H_L ≤ intervalos da missão (a previsão cobre só a missão).")
        st.html('<div class="op-k" style="margin-top:.5rem">Quem declara as políticas</div>')
        _proc(b["declarante"], f"{k}_decl")
    with c2, st.container(border=True):
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
        b["objetivo"]["termos"] = st.multiselect("Termos de custo das baterias no objetivo", list(E.TERMOS_BASE),
                                                 default=[t for t in b["objetivo"]["termos"] if t in E.TERMOS_BASE],
                                                 format_func=lambda t: E.TERMOS_BASE[t], key=f"{k}_termos")
    with st.container(border=True):
        st.html('<div class="op-k">Planejador de longo prazo e solver</div><p class="op-d">Parâmetros numéricos iniciais = '
                f'{escape(E.ROTULO_REFERENCIA)}. Termo terminal Φ_L e degradação NÃO têm valor inicial.</p>')
        g, s = b["planejador"], b["solver"]
        a1, a2, a3 = st.columns(3)
        with a1:
            g["tipo_sinal"] = _sel("Sinal de valor futuro", E.TIPOS_SINAL, g["tipo_sinal"], f"{k}_gs")
            g["politica_atualizacao"] = _sel("Atualização do planejador", E.POLITICAS_ATUALIZACAO, g["politica_atualizacao"],
                                             f"{k}_ga")
            g["periodo_janelas"] = _num("Período [janelas]", g["periodo_janelas"], f"{k}_gp", inteiro=True, minimo=1)
            g["degradacao"] = _sel("Degradação (sinal indisponível)", E.DEGRADACOES, g["degradacao"], f"{k}_gd")
        with a2:
            g["pontos_iniciais"] = _num("Pontos iniciais por banco", g["pontos_iniciais"], f"{k}_gpi", inteiro=True, minimo=2)
            g["pontos_max"] = _num("Pontos máximos (refino)", g["pontos_max"], f"{k}_gpm", inteiro=True, minimo=2)
            g["tolerancia_interpolacao_R"] = _num("Tolerância de interpolação [R$]", g["tolerancia_interpolacao_R"],
                                                  f"{k}_gti", minimo=0.0, fmt="%.3g")
            g["tolerancia_dominio_kWh"] = _num("Tolerância do domínio [kWh]", g["tolerancia_dominio_kWh"], f"{k}_gtd",
                                               minimo=0.0, fmt="%.3g")
        with a3:
            g["max_modos"] = _num("Máximo de modos", g["max_modos"], f"{k}_gmm", inteiro=True, minimo=1)
            s["time_limit_s"] = _num("Solver · limite de tempo por resolução [s]", s["time_limit_s"], f"{k}_stl", minimo=0.0)
            s["threads"] = _num("Solver · threads", s["threads"], f"{k}_sth", inteiro=True, minimo=1)
            s["semente"] = _num("Solver · semente", s["semente"], f"{k}_sse", inteiro=True, minimo=0)
        a1, a2 = st.columns(2)
        with a1:
            s["rel_gap"] = _num("Solver · gap relativo", s["rel_gap"], f"{k}_srg", minimo=0.0, fmt="%.3g")
        with a2:
            s["abs_gap"] = _num("Solver · gap absoluto [R$]", s["abs_gap"], f"{k}_sag", minimo=0.0, fmt="%.3g")
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
    with st.expander("Políticas fixas da integração 3D-A (informativas, gravadas em cada rodada)"):
        from . import montagem as MT

        st.html('<table class="op-tbl">' + "".join(f"<tr><td>{escape(a)}</td><td>{escape(str(v))}</td></tr>"
                                                    for a, v in MT.FIXOS.items()) + "</table>")
    oc._save_bar(store, cur, I.summarize(S.findings(doc)))


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


def _itens_html(items: list[dict]) -> str:
    ordem = {PF.ERROR: 0, PF.WARNING: 1, PF.OK: 2, PF.INFO: 3}
    rows = []
    for it in sorted(items, key=lambda i: ordem.get(i["level"], 9)):
        lv = it["level"]
        rows.append(f'<div class="op-f"><i class="{TONS.get(lv, "off")}">{GLIFOS.get(lv, "·")}</i><span><b>'
                    f'{escape(PF.AREA_LABELS.get(it.get("area"), it.get("area") or ""))}:</b> {escape(it["message"])}'
                    '</span></div>')
    return "".join(rows)


def _matriz_html(linhas: list[dict]) -> str:
    cab = ("Dado", "UID", "Valor", "Fonte / procedência", "Transformação", "Validação", "Registro", "Vista")
    corpo = "".join(
        "<tr>" + "".join(f"<td>{escape(str(x))}</td>" for x in (
            r["dado"], r["uid"], f"{r['valor']} {r['unidade']}".strip(), r["fonte"], r["transformacao"], r["validacao"],
            r["registro"], r["vista"])) + "</tr>" for r in linhas)
    return '<table class="op-tbl"><tr>' + "".join(f"<th>{c}</th>" for c in cab) + "</tr>" + corpo + "</table>"


def relatorio_preflight(rep: dict, matriz: list[dict], versao) -> None:
    c = rep["counts"]
    st.markdown(f'<div class="sd-section">Preflight V2 · versão salva v{versao}</div>', unsafe_allow_html=True)
    shell.kpis([("Bloqueios", str(c[PF.ERROR]), "impedem a execução"), ("Advertências", str(c[PF.WARNING]), "não bloqueiam"),
                ("Verificações", str(c[PF.OK]), "aprovadas"),
                ("Excluídos", str(len(rep["excluded"])), "indisponíveis no cenário")])
    if not rep["ok"]:
        shell.callout("<b>Este cenário NÃO pode ser executado pelo motor V2.</b> Cada bloqueio abaixo explica o que falta ou "
                      "o que não é representável; nada é preenchido automaticamente e o motor V1.6 não é usado como "
                      "substituto.", "bad")
    else:
        shell.callout("<b>Apto para o motor V2.</b> Parâmetros e séries suficientes, contratos 3C-0…3C-4 aceitos e solver "
                      "disponível.", "ok")
    st.html(_itens_html(rep["items"]))
    if rep["excluded"]:
        st.html("<div class='op-k' style='margin-top:.5rem'>Excluídos desta missão (inventário inalterado)</div>"
                '<table class="op-tbl">' + "".join(f"<tr><td>{escape(e['name'])}</td><td>{escape(e['reason'])}</td></tr>"
                                                    for e in rep["excluded"]) + "</table>")
    if matriz:
        with st.expander("Matriz fonte → transformação → validação → registro → vista (o que chega ao motor)"):
            st.html(_matriz_html(matriz))
    if rep.get("bridge"):
        with st.expander("Relatório da ponte científica 3C-0/3C-1 (texto original)"):
            st.code(rep["bridge"]["texto"], language="text")
            st.caption(f"SHA-256 do relatório: {rep['bridge']['sha256']}")


def render_execucao(store, cur, dirty: bool, active, live) -> None:
    """Corpo da etapa 04 para o motor V2 (janela da missão, barra de salvar e histórico ficam com a página comum)."""
    from . import execucao as X

    try:
        pf = preflight(store, cur)
    except StoreError as exc:
        st.error(shell.md(exc))
        return
    relatorio_preflight(pf.report(), pf.matriz, cur.version)
    st.markdown('<div class="sd-section">Executar (motor V2 experimental)</div>', unsafe_allow_html=True)
    if active is not None:
        live(store, active.run_uid)
    req_key = f"op_ex_req_v2_{cur.scenario_uid}_{cur.version}"
    req = _ss().setdefault(req_key, X.new_request_id())
    reason = ("há alterações não salvas" if dirty else "o preflight V2 tem bloqueios" if not pf.ok else
              "outra rodada está em execução nesta microrrede" if active is not None else "")
    if st.button(f"▶ EXECUTAR MISSÃO V2 · VERSÃO {cur.version}", key="op_ex_run_v2", type="primary", disabled=bool(reason),
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


def progresso(run) -> None:
    p = run.progress or {}
    fase = p.get("phase", "preparando")
    if fase == "missao" and p.get("n"):
        k, n = int(p.get("k", 0)), int(p["n"])
        st.progress(min(k / n, 1.0), text=f"{FASES['missao']} · intervalo {k} de {n} · {int(p.get('janelas', 0))} janela(s)")
    else:
        st.caption("⏳ " + FASES.get(fase, fase))


# ======================================================================= rodada V2 (somente leitura)
def _verificacao(source, run):
    cache = _ss().setdefault("op_v2_verif", {})
    chave = (run.run_uid, run.state, getattr(source, "archive_uid", None) or "local")
    if chave not in cache:
        if len(cache) > 8:
            cache.clear()
        cache[chave] = RG.verificar(source, run)
    return cache[chave]


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


def _figuras(it, fr, bats: list[str], key: str) -> None:
    import plotly.graph_objects as go

    x = it["intervalo"]
    fig = go.Figure()
    fig.add_bar(x=x, y=it["pcc_importacao_realizada_kW"] if "pcc_importacao_realizada_kW" in it else None,
                name="Importação da rede (realizada)")
    for b in bats:
        fig.add_bar(x=x, y=it[f"{b}|P_d_kW"], name=f"Descarga {b}")
    fig.add_scatter(x=x, y=it["demanda_realizada_kW"], name="Demanda realizada", mode="lines+markers",
                    line={"shape": "hvh", "color": "#222"})
    fig.add_scatter(x=x, y=it["demanda_prevista_kW"], name="Demanda prevista (na decisão)", mode="lines",
                    line={"shape": "hvh", "dash": "dot", "color": "#888"})
    for b in bats:
        fig.add_bar(x=x, y=-it[f"{b}|P_c_kW"], name=f"Carga {b} (consumo; não é geração)")
    fig.update_layout(barmode="relative", height=340, margin={"l": 50, "r": 10, "t": 40, "b": 40},
                      title="Demanda × atendimento por recurso — médias de intervalo [kW]",
                      xaxis_title="intervalo aplicado (índice global)", yaxis_title="kW", legend={"orientation": "h"})
    st.plotly_chart(fig, key=f"{key}_pot", width="stretch")
    fig2 = go.Figure()
    for b in bats:
        fig2.add_scatter(x=fr["fronteira"], y=fr[f"{b}|energia_kWh"], name=f"Energia {b}", mode="lines+markers")
    fig2.update_layout(height=280, margin={"l": 50, "r": 10, "t": 40, "b": 40},
                       title="Energia armazenada nas fronteiras de estado [kWh] (N + 1 pontos)",
                       xaxis_title="fronteira (índice global)", yaxis_title="kWh", legend={"orientation": "h"})
    st.plotly_chart(fig2, key=f"{key}_ene", width="stretch")


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


def run_results(source, run, *, key: str) -> None:
    """Rodada V2 FINALIZADA lida de ``source`` (``MicrogridStore`` ou estudo arquivado). Nunca chama o otimizador."""
    m = run.manifest
    shell.callout(f"<b>Motor V2 experimental (MILP–MPC hierárquico).</b> {escape(m.get('scope') or PF.ESCOPO)} Dados "
                  "sintéticos/declarados estão rotulados na procedência.", "warn")
    v = _verificacao(source, run)
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
    try:
        it, fr = RG.ler_csv(source, run, RG.N_INTERVALOS), RG.ler_csv(source, run, RG.N_FRONTEIRAS)
        ja = RG.ler_csv(source, run, RG.N_JANELAS)
    except StoreError as exc:
        st.error(shell.md(exc))
        return
    _figuras(it, fr, bats, key)
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


__all__ = ["MOTOR_V2", "custo_texto", "e_v2", "estrategia_arquivada", "motor", "preflight", "progresso",
           "relatorio_preflight", "render_estrategia", "render_execucao", "run_results", "seletor_motor", "stage_state"]
_ = json
