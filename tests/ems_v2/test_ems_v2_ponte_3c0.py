"""Piso 3C-0 — contratos da ponte científica (núcleo, sem solver e sem ``seeds2``).

Testes CONTRATUAIS/SINTÉTICOS: verificam estruturas, rejeições, sincronização temporal, serialização e separação de
conceitos. NÃO validam física: o executor usado aqui é o dublê algébrico ``ExecutorAlgebricoReferencia``.
"""
from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ems_v2 import FORMULACAO_3BP, MOTOR_ID
from ems_v2 import fixtures_3c0 as F
from ems_v2.contracts import UIDRecurso, hash_entrada, validar_entrada
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.parameters import verificar_cadeia
from ems_v2.ponte import canonico, cenario as CN, execucao as EX, instrumentacao as IN, inventario as IV
from ems_v2.ponte import preflight as PF, projecao as PJ, registro as RG, requisitos as RQ
from ems_v2.ponte.inventario import ValorInventario
from ems_v2.provenance import TIPOS_PROCEDENCIA, Procedencia

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]
UID_EXEC = "0123456789abcdef0123456789abcdef"


# ======================================================================================== utilidades
def _projecao(inv=None, cen=None, prev=None, dt=None, pol=None, contexto="ensaio"):
    inv = inv or F.inventario()
    return PJ.montar_entrada(inv, cen or F.cenario(inv), prev or F.previsao(), dt or F.definicao(), pol or F.politicas(),
                             contexto=contexto)


def _resultado_analitico(entrada):
    """Resultado ACEITO com o despacho analítico do caso (sem solver): bateria descarrega 10 kW em t = 2."""
    desp = {"renovaveis": {"syn-pv1": {"P_R": F.PV_PREV, "C_oper": (0.0,) * 4}},
            "baterias": {"syn-bat1": {"P_c": (0.0,) * 4, "P_d": (0.0, 0.0, 10.0, 0.0), "z_b": (0.0,) * 4,
                                      "e": (50.0, 50.0, 50.0, 50.0 - 0.25 * 10.0 / 0.95, 50.0 - 0.25 * 10.0 / 0.95)}},
            "demandas": {"syn-carga": {"ell": (0.0,) * 4}}, "descarte": None,
            "geradores": {"syn-ter1": {"u": (1.0,) * 4, "p": (10.0, 10.0, 30.0, 20.0)}}}
    return SimpleNamespace(aceito=True, despacho=desp, hash_entrada=hash_entrada(entrada), motor_id=MOTOR_ID,
                           versao_formulacao=FORMULACAO_3BP, classificacao="otimo", estado_despacho="aceito_otimo",
                           custos_modelo={"curtailment_operacional": 0.0, "throughput_bess": 0.025, "total": 0.025})


@pytest.fixture(scope="module")
def base():
    proj = _projecao()
    assert proj.aceito, [c.codigo for c in proj.constatacoes if c.severidade != "aviso"]
    plano = EX.plano_de_resultado(_resultado_analitico(proj.entrada), proj.entrada)
    return SimpleNamespace(entrada=proj.entrada, plano=plano, proj=proj)


def _executor(entrada):
    return EX.ExecutorAlgebricoReferencia(entrada)


def _e0(entrada, mem=3600):
    return EX.estado_inicial_de_entrada(entrada, memoria={"syn-ter1": mem})


# ======================================================================================== 1. inventário / isolamento
def test_inventario_sintetico_valido_e_hash_deterministico():
    inv = F.inventario()
    assert IV.validar_inventario(inv).aceito
    assert IV.hash_inventario(inv) == IV.hash_inventario(F.inventario())
    assert canonico.de_json(IV.InventarioMicrorrede, canonico.json_canonico(inv)) == inv


def test_isolamento_entre_duas_microrredes_sinteticas():
    a, b = F.inventario("syn-mg-a"), F.inventario("syn-mg-b", (F.bateria("syn-mg-b", C=50.0), F.termica("syn-mg-b")))
    assert IV.validar_inventario(a).aceito and IV.validar_inventario(b).aceito
    assert all(d.microrrede_uid == "syn-mg-a" for d in a.dispositivos)
    assert IV.hash_inventario(a) != IV.hash_inventario(b)
    misto = dataclasses.replace(a, dispositivos=a.dispositivos + (F.termica("syn-mg-b", uid="syn-ter9"),))
    assert "dispositivo_de_outra_microrrede" in IV.validar_inventario(misto).codigos()
    m_a, m_b = RQ.matriz_parametros(a, contexto="ensaio"), RQ.matriz_parametros(b, contexto="ensaio")
    assert m_a.de("syn-bat1", "C_b").numero == 100.0 and m_b.de("syn-bat1", "C_b").numero == 50.0
    assert {c.uid for c in m_b.entradas} == {"syn-bat1", "syn-ter1"}


@pytest.mark.parametrize("mut,codigo", [
    (lambda inv: dataclasses.replace(inv, dispositivos=inv.dispositivos + (inv.dispositivos[0],)), "uid_duplicado"),
    (lambda inv: dataclasses.replace(inv, dispositivos=(F.arranjo("syn-mg-a", pai="syn-nada"),)), "arranjo_sem_usina"),
    (lambda inv: dataclasses.replace(inv, retirados=("syn-bat1",)), "dispositivo_retirado_ativo"),
    (lambda inv: dataclasses.replace(inv, dispositivos=(dataclasses.replace(F.termica("syn-mg-a"), quantidade=0),)),
     "quantidade_invalida"),
    (lambda inv: dataclasses.replace(inv, dispositivos=(F.com_valor(F.termica("syn-mg-a"), "pmax_kW",
                                                                  F.num("pmax_kW", "kW", float("nan"), "syn-mg-a", "x")),)),
     "valor_nao_finito"),
    (lambda inv: dataclasses.replace(inv, dispositivos=(F.com_valor(F.termica("syn-mg-a"), "pmax_kW", ValorInventario(
        "pmax_kW", "kW", "p", "ausente", None, numero=3.0)),)), "ausente_com_valor"),
    (lambda inv: dataclasses.replace(inv, dispositivos=(F.com_valor(F.termica("syn-mg-a"), "pmax_kW", ValorInventario(
        "pmax_kW", "kW", "p", "derivado", F.proc(), numero=3.0)),)), "derivacao_nao_registrada"),
    (lambda inv: dataclasses.replace(inv, dispositivos=(F.com_valor(F.termica("syn-mg-a"), "pmax_kW", ValorInventario(
        "pmax_kW", "kW", "p", "inventario_declarado", F.proc(), numero=3.0)),)), "sintetico_rotulado_como_real"),
    (lambda inv: dataclasses.replace(inv, dispositivos=(dataclasses.replace(
        F.termica("syn-mg-a"), modelo=IV.AssociacaoModelo("x", None, "renovavel", "termica")),)), "papel_incoerente"),
    (lambda inv: dataclasses.replace(inv, dispositivos=(dataclasses.replace(F.termica("syn-mg-a"), uid="ter-1"),)),
     "uid_invalido"),
])
def test_inventario_rejeicoes(mut, codigo):
    assert codigo in IV.validar_inventario(mut(F.inventario())).codigos()


def test_recursos_por_unidade_sem_inventar_identificadores():
    pem = dataclasses.replace(F.termica("syn-mg-a", uid="syn-pem"), tipo="pemfc", quantidade=3,
                              modelo=IV.AssociacaoModelo("x", None, "gerador", "pemfc"))
    assert IV.recursos_ems(pem) == (UIDRecurso("syn-pem", 1), UIDRecurso("syn-pem", 2), UIDRecurso("syn-pem", 3))
    assert IV.recursos_ems(F.bateria("syn-mg-a")) == (UIDRecurso("syn-bat1"),)
    assert IV.recursos_ems(F.usina("syn-mg-a")) == ()


def test_procedencia_estendida_preserva_tipos_3a():
    originais = {"sintetico", "medido", "fabricante", "referencia", "identificado", "decisao_responsavel", "nao_declarado"}
    assert originais < set(TIPOS_PROCEDENCIA) and "declarado_seeds2" in TIPOS_PROCEDENCIA


# ======================================================================================== 2. matriz de parâmetros
def test_cinco_classes_de_parametros():
    inv = F.inventario()
    bat = F.com_valor(F.bateria("syn-mg-a"), "eta_carga", None)
    bat = F.com_valor(bat, "energy_kWh", None)
    bat = F.com_valor(bat, "custo_throughput", None)
    bat = F.com_valor(bat, "energy_kWh_modelo", ValorInventario(
        "energy_kWh_modelo", "kWh", "p", "catalogo_referencia", Procedencia("referencia", "catálogo"), numero=99.0,
        derivacao="V·Q·Ns·Np"))
    bat = F.com_valor(bat, "soc_min_pct", ValorInventario("soc_min_pct", "%", "p", "inventario_declarado",
                                                          Procedencia("declarado_seeds2", "doc"), numero=10.0))
    inv = dataclasses.replace(inv, dispositivos=(bat,) + inv.dispositivos[1:])
    m = RQ.matriz_parametros(inv, termos=set(), contexto="ensaio")
    cl = {c.simbolo: c.classe for c in m.entradas if c.uid == "syn-bat1"}
    assert cl["s_min"] == "disponivel_verificavel"
    assert cl["C_b"] == "derivavel" and m.de("syn-bat1", "C_b").numero == 99.0
    assert cl["eta_c"] == "faltante_necessario" and m.de("syn-bat1", "eta_c").bloqueia
    assert cl["c_thr"] == "opcional" and not m.de("syn-bat1", "c_thr").bloqueia      # termo inativo
    assert cl["s_max"] == "sintetico_ensaio" and not m.de("syn-bat1", "s_max").bloqueia
    m_op = RQ.matriz_parametros(inv, contexto="operacional")
    assert m_op.de("syn-bat1", "s_max").bloqueia and m_op.de("syn-bat1", "s_max").codigo == "dado_sintetico_fora_de_ensaio"
    assert {"disponivel_verificavel", "derivavel", "faltante_necessario", "opcional", "sintetico_ensaio"} \
        == {c.classe for c in m.entradas if c.uid == "syn-bat1"} == set(RQ.CLASSES)


def test_valor_sugerido_nao_sustenta_limite():
    sug = ValorInventario("soc_min_pct", "%", "p", "inventario_sugerido_seeds2",
                          Procedencia("nao_declarado", "SEEDS2 sugerido"), numero=20.0)
    inv = F.inventario(dispositivos=(F.com_valor(F.bateria("syn-mg-a"), "soc_min_pct", sug),))
    assert IV.validar_inventario(inv).aceito
    c = RQ.matriz_parametros(inv, contexto="ensaio").de("syn-bat1", "s_min")
    assert (c.classe, c.codigo, c.bloqueia, c.numero) == ("faltante_necessario", "valor_sugerido_nao_confirmado", True, None)


def test_compatibilidade_de_unidades():
    m = RQ.matriz_parametros(F.inventario(), termos={"geracao_termica"}, contexto="ensaio")
    smin = m.de("syn-bat1", "s_min")
    assert (smin.numero, smin.unidade, smin.numero_bruto, smin.unidade_bruta) == (0.1, "1", 10.0, "%")
    assert not verificar_cadeia((smin.numero_bruto,), smin.unidade_bruta, (smin.numero,), "1", smin.transformacoes, "s")
    assert m.de("syn-ter1", "CVU").numero == 1.1 and m.de("syn-ter1", "CVU").unidade == "R$/kWh"
    errado = F.com_valor(F.bateria("syn-mg-a"), "energy_kWh", F.num("energy_kWh", "Ah", 100.0, "syn-mg-a", "b"))
    c = RQ.classificar_dispositivo(errado, contexto="ensaio")
    cb = next(x for x in c if x.simbolo == "C_b")
    assert cb.codigo == "unidade_incompativel" and cb.bloqueia
    desconhecida = F.com_valor(F.bateria("syn-mg-a"), "p_carga_barramento_kW",
                               F.num("p_carga_barramento_kW", "hp", 1.0, "syn-mg-a", "b"))
    assert next(x for x in RQ.classificar_dispositivo(desconhecida, contexto="ensaio")
                if x.simbolo == "Pc_max").codigo == "unidade_incompativel"


def test_desabilitado_nao_bloqueia_e_3c1_so_informa():
    ter = dataclasses.replace(F.com_valor(F.termica("syn-mg-a"), "pmin_kW", None), habilitado=False)
    c = RQ.classificar_dispositivo(ter, contexto="ensaio")
    assert next(x for x in c if x.simbolo == "P_min").classe == "faltante_necessario"
    assert not any(x.bloqueia for x in c)
    r3c1 = [x for x in RQ.classificar_dispositivo(F.termica("syn-mg-a"), contexto="ensaio") if x.codigo == "necessario_3C1"]
    assert {x.simbolo for x in r3c1} >= {"rampa", "t_on_min", "t_off_min", "C_SU", "C_SD"} and not any(x.bloqueia for x in r3c1)
    assert all(c.severidade == "aviso" for c in RQ.constatacoes(RQ.matriz_parametros(F.inventario(), contexto="ensaio"))
               if c.codigo == "necessario_3C1")


def test_matriz_documentada_lista_todos_os_simbolos():
    doc = (RAIZ / "docs/ems_v2/MATRIZ_PARAMETROS_3C0.md").read_text(encoding="utf-8")
    faltam = [r.simbolo for r in RQ.REQUISITOS if f"`{r.simbolo}`" not in doc]
    assert faltam == []


# ======================================================================================== 3. cenário × microrrede
def test_cenario_coerente():
    inv = F.inventario()
    assert CN.validar_cenario(F.cenario(inv)).aceito
    assert CN.coerencia_cenario_inventario(F.cenario(inv), inv) == []


def test_cenario_inconsistente_com_microrrede():
    inv, outra = F.inventario("syn-mg-a"), F.inventario("syn-mg-b")
    cods = lambda c, i: {x.codigo for x in CN.coerencia_cenario_inventario(c, i)}  # noqa: E731
    assert "cenario_de_outra_microrrede" in cods(F.cenario(outra), inv)
    alterado = F.inventario(dispositivos=(F.bateria("syn-mg-a", C=80.0), F.usina("syn-mg-a"), F.arranjo("syn-mg-a"),
                                          F.termica("syn-mg-a")), revisao=2)
    alterado = dataclasses.replace(alterado, identidade=dataclasses.replace(alterado.identidade,
                                                                            impressao_inventario=F.h64("outro")))
    assert "inventario_divergente" in cods(F.cenario(inv), alterado)
    c = F.cenario(inv)
    assert "incarnacao_divergente" in cods(dataclasses.replace(c, referencia_inventario=dataclasses.replace(
        c.referencia_inventario, incarnacao="inc-velha")), inv)
    fantasma = dataclasses.replace(c, condicoes_iniciais=c.condicoes_iniciais + (CN.CondicaoInicialDispositivo(
        "syn-fantasma", "disponivel"),))
    assert "referencia_uid_inexistente" in cods(fantasma, inv)
    ret = dataclasses.replace(inv, retirados=("syn-velho",))
    velho = dataclasses.replace(c, condicoes_iniciais=c.condicoes_iniciais + (CN.CondicaoInicialDispositivo(
        "syn-velho", "disponivel"),))
    assert "condicao_para_dispositivo_retirado" in cods(velho, ret)
    sem = dataclasses.replace(c, condicoes_iniciais=tuple(x for x in c.condicoes_iniciais if x.uid != "syn-bat1"))
    assert "condicao_inicial_ausente" in cods(sem, inv)


def test_horizonte_de_planejamento_reservado():
    dt = dataclasses.replace(F.definicao(), horizonte_planejamento_min=1440.0)
    assert "planejamento_hierarquico_nao_ativo_3C0" in {c.codigo for c in CN.validar_definicao_temporal(dt)}


# ======================================================================================== 4. previsão × realização
def test_previsao_causal_e_com_emissao():
    dt = F.definicao()
    assert CN.validar_previsao(F.previsao(), dt) == []
    tarde = dataclasses.replace(F.previsao(), emissao_utc="2026-01-01T00:10:00+00:00")
    assert "previsao_nao_causal" in {c.codigo for c in CN.validar_previsao(tarde, dt)}
    p = F.previsao()
    s0 = p.series[0]
    sem_emissao = dataclasses.replace(p, series=(dataclasses.replace(s0, serie=dataclasses.replace(
        s0.serie, emissao_utc=None)),) + p.series[1:])
    assert "emissao_serie_ausente" in {c.codigo for c in CN.validar_previsao(sem_emissao, dt)}
    curta = F.previsao(demanda=(30.0, 40.0, 50.0))
    assert "cobertura_insuficiente" in {c.codigo for c in CN.validar_previsao(curta, dt)}


def test_realizacao_cobre_missao_e_nao_tem_emissao():
    dt = F.definicao()
    assert CN.validar_realizacao(F.realizacao(), dt) == []
    r = F.realizacao()
    s0 = r.series[0]
    emitida = dataclasses.replace(r, series=(dataclasses.replace(s0, serie=dataclasses.replace(
        s0.serie, emissao_utc=F.INICIO)),) + r.series[1:])
    assert "realizacao_com_emissao" in {c.codigo for c in CN.validar_realizacao(emitida, dt)}
    longa = F.definicao(n=4, missao=8)
    assert "cobertura_insuficiente" in {c.codigo for c in CN.validar_realizacao(F.realizacao(), longa)}


def test_separacao_previsao_realizacao():
    dt = F.definicao()
    cods = lambda p, r: {c.codigo for c in CN.validar_separacao(p, r, dt)}  # noqa: E731
    assert "previsao_igual_realizacao_nao_declarada" in cods(F.previsao(), F.realizacao())
    assert cods(F.previsao(oraculo=True), F.realizacao()) == {"previsao_perfeita_declarada"}
    sem_just = dataclasses.replace(F.previsao(oraculo=True), justificativa_oraculo="")
    assert "oraculo_sem_justificativa" in {c.codigo for c in CN.validar_previsao(sem_just, dt)}
    assert cods(F.previsao(), F.realizacao(demanda=(30.0, 45.0, 50.0, 20.0), pv=(19.0, 30.0, 10.0, 0.0))) == set()
    assert cods(F.previsao(), F.realizacao(demanda=(30.0, 45.0, 50.0, 20.0))) == {"previsao_igual_realizacao_nao_declarada"}
    p = F.previsao()
    mesmo = CN.Realizacao("r", "sintetica", (p.series[0],), F.proc())
    assert "mesmo_objeto_previsao_realizacao" in cods(p, mesmo)


def test_entrada_depende_so_da_previsao_nunca_da_realizacao():
    import inspect
    assert "realizacao" not in inspect.signature(PJ.montar_entrada).parameters
    h1 = hash_entrada(_projecao().entrada)
    assert h1 == hash_entrada(_projecao().entrada)
    h2 = hash_entrada(_projecao(prev=F.previsao(demanda=(30.0, 41.0, 50.0, 20.0))).entrada)
    assert h1 != h2


# ======================================================================================== 5. projeção / compatibilidade 3A
def test_projecao_compativel_com_contrato_3a(base):
    e = base.entrada
    assert validar_entrada(e).aceito and e.versao_formulacao == FORMULACAO_3BP and e.microrrede_uid == "syn-mg-a"
    b = e.baterias[0]
    assert (b.soc_min.valor, b.soc_min.valor_bruto, b.soc_min.unidade_bruta) == (0.1, 10.0, "%")
    assert e.estados_baterias[0].energia_kWh.valor == 50.0
    assert set(e.hashes_fontes) == {"inventario", "cenario", "previsao", "matriz_parametros"}
    assert base.proj.recursos == {"syn-bat1": "syn-bat1", "syn-pv1": "syn-pv1", "syn-ter1": "syn-ter1"}
    assert "entrada_de_ensaio" in {c.codigo for c in base.proj.constatacoes}


def test_projecao_bloqueia_parametro_ausente_e_sintetico_operacional():
    inv = F.inventario(dispositivos=(F.com_valor(F.bateria("syn-mg-a"), "eta_carga", None), F.usina("syn-mg-a"),
                                     F.arranjo("syn-mg-a"), F.termica("syn-mg-a")))
    p = _projecao(inv=inv)
    assert p.entrada is None and "parametro_obrigatorio_ausente" in {c.codigo for c in p.constatacoes}
    p2 = _projecao(contexto="operacional")
    assert p2.entrada is None and "dado_sintetico_fora_de_ensaio" in {c.codigo for c in p2.constatacoes}


def test_projecao_exige_politicas_declaradas():
    pol = dataclasses.replace(F.politicas(), demandas=())
    assert "classes_demanda_nao_declaradas" in {c.codigo for c in _projecao(pol=pol).constatacoes}
    pol = dataclasses.replace(F.politicas(), variante_commitment=None)
    assert "variante_commitment_nao_declarada" in {c.codigo for c in _projecao(pol=pol).constatacoes}
    inv = dataclasses.replace(F.inventario(), modo_operacao=None)
    assert "topologia_nao_declarada" in {c.codigo for c in _projecao(inv=inv, cen=F.cenario(inv)).constatacoes}


def test_estado_por_unidade_nao_inventado():
    ter = dataclasses.replace(F.termica("syn-mg-a"), quantidade=2)
    inv = F.inventario(dispositivos=(F.bateria("syn-mg-a"), F.usina("syn-mg-a"), F.arranjo("syn-mg-a"), ter))
    c = F.cenario(inv)
    c1 = dataclasses.replace(c, condicoes_iniciais=tuple(dataclasses.replace(x, unidades_ligadas=1)
                                                          if x.uid == "syn-ter1" else x for x in c.condicoes_iniciais))
    p = _projecao(inv=inv, cen=c1)
    assert p.entrada is None and "estado_por_unidade_nao_declarado" in {x.codigo for x in p.constatacoes}
    partida = F.cenario(F.inventario(), ter_estado="em_partida")
    assert "estado_em_partida_nao_representavel" in {x.codigo for x in _projecao(cen=partida).constatacoes}


def test_indisponivel_entra_com_a_zero_sem_alterar_inventario():
    inv = F.inventario()
    cen = F.cenario(inv, disponibilidade={"syn-pv1": "indisponivel"})
    p = _projecao(inv=inv, cen=cen)
    assert p.aceito
    r = p.entrada.renovaveis[0]
    assert r.disponibilidade.serie.valores == (0.0,) * 4 and "ESTÁTICA" in r.disponibilidade.serie.procedencia.observacoes
    assert IV.hash_inventario(inv) == IV.hash_inventario(F.inventario())


# ======================================================================================== 6. plano e malha N/N+1
def test_plano_de_resultado_aceito_e_rejeicoes(base):
    p = base.plano
    assert EX.validar_plano(p) == [] and p.N == 4 and p.hash_entrada == hash_entrada(base.entrada)
    assert len(p.consigna("syn-bat1", "P_d").valores) == 4 and len(p.estados_planejados[0].valores) == 5
    assert "z_b" not in {c.grandeza for c in p.consignas}
    rej = SimpleNamespace(aceito=False, despacho=None, estado_despacho="rejeitado_auditoria")
    with pytest.raises(ContratoInvalido) as ei:
        EX.plano_de_resultado(rej, base.entrada)
    assert "plano_de_solucao_nao_aceita" in ei.value.codigos
    outro = _resultado_analitico(base.entrada)
    outro.hash_entrada = "0" * 64
    with pytest.raises(ContratoInvalido) as ei:
        EX.plano_de_resultado(outro, base.entrada)
    assert "plano_entrada_divergente" in ei.value.codigos


@pytest.mark.parametrize("mut,codigo", [
    (lambda c: dataclasses.replace(c, valores=c.valores + (0.0,)), "instante_terminal_como_intervalo"),
    (lambda c: dataclasses.replace(c, valores=c.valores[:3]), "comprimento_incompativel"),
    (lambda c: dataclasses.replace(c, valores=(float("nan"),) + c.valores[1:]), "valor_nao_finito"),
    (lambda c: dataclasses.replace(c, unidade="W"), "unidade_incompativel"),
])
def test_malha_n_intervalos_consignas(base, mut, codigo):
    p = base.plano
    cs = tuple(mut(c) if (c.uid, c.grandeza) == ("syn-bat1", "P_d") else c for c in p.consignas)
    assert codigo in {x.codigo for x in EX.validar_plano(dataclasses.replace(p, consignas=cs))}


def test_malha_estados_n_mais_1_e_binario(base):
    p = base.plano
    t = p.estados_planejados[0]
    curto = dataclasses.replace(p, estados_planejados=(dataclasses.replace(t, valores=t.valores[:4]),))
    assert "comprimento_incompativel" in {x.codigo for x in EX.validar_plano(curto)}
    cs = tuple(dataclasses.replace(c, valores=(0.5,) * 4) if c.grandeza == "u" else c for c in p.consignas)
    assert "consigna_binaria_fracionaria" in {x.codigo for x in EX.validar_plano(dataclasses.replace(p, consignas=cs))}


# ======================================================================================== 7. execução, estados, checkpoints
def test_execucao_completa_n_intervalos_n_mais_1_estados(base):
    t = EX.executar(base.plano, _e0(base.entrada), _executor(base.entrada), F.realizacao(), execucao_uid=UID_EXEC)
    assert t.situacao == "concluida" and len(t.passos) == 4 and len(t.estados) == 5
    assert [e.indice_fronteira for e in t.estados] == [0, 1, 2, 3, 4]
    assert [e.instante_utc[11:16] for e in t.estados] == ["00:00", "00:15", "00:30", "00:45", "01:00"]
    assert t.estados[-1].bateria("syn-bat1").energia_kWh == 50.0 - 0.25 * 10.0 / 0.95
    assert max(abs(d.desvio) for d in t.desvios) == 0.0
    assert t.estados[-1].gerador("syn-ter1").tempo_no_estado_s == 3600 + 4 * 900     # memória transportada
    assert len(t.checkpoints) == 4 and all(EX.verificar_checkpoint(c) == [] for c in t.checkpoints)
    assert [c.hash_anterior for c in t.checkpoints[1:]] == [c.selo for c in t.checkpoints[:-1]]


def test_retomada_reproduz_execucao_continua(base):
    ex, real = _executor(base.entrada), F.realizacao()
    total = EX.executar(base.plano, _e0(base.entrada), ex, real, execucao_uid=UID_EXEC)
    parte = EX.executar(base.plano, _e0(base.entrada), ex, real, execucao_uid=UID_EXEC, intervalos=2)
    assert parte.cursor_final == 2 and parte.checkpoints[-1].cursor_plano == 2
    cp = canonico.de_json(EX.Checkpoint, canonico.json_canonico(parte.checkpoints[-1]))   # persistido e relido
    resto = EX.retomar(cp, base.plano, ex, real)
    assert resto.estados[-1] == total.estados[-1]
    assert resto.checkpoints[-1] == total.checkpoints[-1]
    assert parte.passos + resto.passos == total.passos
    assert parte.checkpoints + resto.checkpoints == total.checkpoints


def test_retomada_incoerente_ou_adulterada_e_recusada(base):
    ex, real = _executor(base.entrada), F.realizacao()
    cp = EX.executar(base.plano, _e0(base.entrada), ex, real, execucao_uid=UID_EXEC, intervalos=2).checkpoints[-1]
    bat = cp.estado.armazenamento[0]
    adulterado = dataclasses.replace(cp, estado=dataclasses.replace(cp.estado, armazenamento=(
        dataclasses.replace(bat, energia_kWh=bat.energia_kWh + 1.0),)))
    with pytest.raises(ContratoInvalido) as ei:
        EX.retomar(adulterado, base.plano, ex, real)
    assert "checkpoint_adulterado" in ei.value.codigos
    outro_plano = dataclasses.replace(base.plano, custo_objetivo_planejado={"total": 1.0})
    with pytest.raises(ContratoInvalido) as ei:
        EX.retomar(cp, outro_plano, ex, real)
    assert "retomada_incoerente" in ei.value.codigos
    with pytest.raises(ContratoInvalido) as ei:
        EX.executar(base.plano, cp.estado, ex, real, execucao_uid=UID_EXEC, cursor=1, checkpoint_anterior=cp)
    assert {"estado_dessincronizado", "retomada_incoerente"} <= ei.value.codigos


def test_estado_dessincronizado_ou_de_outra_microrrede(base):
    ex, real, e0 = _executor(base.entrada), F.realizacao(), _e0(base.entrada)
    with pytest.raises(ContratoInvalido) as ei:
        EX.executar(base.plano, dataclasses.replace(e0, instante_utc="2026-01-01T00:05:00+00:00"), ex, real,
                    execucao_uid=UID_EXEC)
    assert "estado_dessincronizado" in ei.value.codigos
    with pytest.raises(ContratoInvalido) as ei:
        EX.executar(base.plano, dataclasses.replace(e0, microrrede_uid="syn-mg-b"), ex, real, execucao_uid=UID_EXEC)
    assert "estado_de_outra_microrrede" in ei.value.codigos
    with pytest.raises(ContratoInvalido) as ei:
        EX.executar(base.plano, dataclasses.replace(e0, armazenamento=()), ex, real, execucao_uid=UID_EXEC)
    assert "estado_incompativel_com_plano" in ei.value.codigos


def test_executor_que_dessincroniza_e_detectado(base):
    class Errado:
        identificador, natureza = "errado", "algebrico_referencia"

        def avancar(self, estado, consignas, entorno, delta_s):
            return EX.PassoAplicado(dict(consignas), dataclasses.replace(estado, indice_fronteira=estado.indice_fronteira + 2),
                                    True)
    with pytest.raises(ContratoInvalido) as ei:
        EX.executar(base.plano, _e0(base.entrada), Errado(), F.realizacao(), execucao_uid=UID_EXEC)
    assert "executor_dessincronizou" in ei.value.codigos


def test_realizacao_diferente_interrompe_sem_recorte(base):
    real = F.realizacao(demanda=(30.0, 45.0, 50.0, 20.0))
    t = EX.executar(base.plano, _e0(base.entrada), _executor(base.entrada), real, execucao_uid=UID_EXEC)
    assert t.situacao == "interrompida_inexequivel" and t.cursor_final == 1 and len(t.estados) == 2
    assert "balanco_realizado_violado" in {c.codigo for c in t.constatacoes}
    assert t.checkpoints[-1].cursor_plano == 1 and t.checkpoints[-1].estado == t.estados[-1]
    real_pv = F.realizacao(pv=(20.0, 20.0, 10.0, 0.0))
    t2 = EX.executar(base.plano, _e0(base.entrada), _executor(base.entrada), real_pv, execucao_uid=UID_EXEC)
    assert "consigna_inexequivel_renovavel" in {c.codigo for c in t2.constatacoes}


# ======================================================================================== 8. registro, custo × valor futuro
def _registro(base, traj, real):
    ind, custo = RG.indicadores_e_custo(base.entrada, base.plano, traj, real)
    e = base.entrada
    return RG.RegistroExecucaoEMS(
        1, UID_EXEC, "2026-11-08T00:00:00+00:00",
        RG.ReferenciaOrigem(e.microrrede_uid, "inc-syn", 1, F.h64("cfgsyn-mg-a1"), F.h64("x"), F.h64("y"),
                            e.cenario_uid, 1, F.h64("cenario")),
        {"ponte": "3C-0", "motor": e.motor_id, "formulacao": e.versao_formulacao},
        {"entrada": hash_entrada(e), "plano": EX.hash_plano(base.plano)},
        RG.Discretizacao(F.INICIO, 900, 4, 4, 4), None, base.plano, traj.estados[0], traj.estados[-1], traj.situacao,
        traj.checkpoints[-1], ind, custo, dict(base.plano.custo_objetivo_planejado),
        RG.valor_futuro_nao_implementado(traj.estados[-1].indice_fronteira), "exito", "teste", {"construcao_modelo": 0.1},
        tuple(traj.constatacoes), {"semente": "0"})


def test_custo_realizado_separado_do_valor_futuro(base):
    real = F.realizacao()
    traj = EX.executar(base.plano, _e0(base.entrada), _executor(base.entrada), real, execucao_uid=UID_EXEC)
    ind, custo = RG.indicadores_e_custo(base.entrada, base.plano, traj, real)
    assert ind["E_bess_descarga_kWh"] == 2.5 and ind["E_demanda_realizada_kWh"] == 35.0
    assert {c.termo for c in custo.componentes} == {"curtailment_operacional", "throughput_bess"}
    assert abs(custo.total_R - 0.025) < 1e-12 and all(c.base == "realizado" for c in custo.componentes)
    reg = RG.selar_registro(_registro(base, traj, real))
    assert reg.valor_futuro.valor_R is None and reg.valor_futuro.contabilizado_como_custo is False
    vf = reg.valor_futuro
    for ruim, cod in [
        (dataclasses.replace(vf, contabilizado_como_custo=True), "valor_futuro_contabilizado_como_custo"),
        (dataclasses.replace(vf, valor_R=12.0), "valor_futuro_sem_metodo"),
        (dataclasses.replace(vf, metodo="duais_milp"), "metodo_valor_futuro_nao_suportado_3C0")]:
        assert cod in {c.codigo for c in RG.validar_registro(dataclasses.replace(reg, valor_futuro=ruim))}
    term = dataclasses.replace(custo, componentes=custo.componentes + (RG.ComponenteCusto("terminal", 5.0, "realizado"),),
                               total_R=custo.total_R + 5.0)
    assert "valor_futuro_contabilizado_como_custo" in {c.codigo for c in RG.validar_registro(
        dataclasses.replace(reg, custo_realizado=term))}
    plan = dataclasses.replace(custo, componentes=(dataclasses.replace(custo.componentes[0], base="objetivo_plano"),)
                               + custo.componentes[1:])
    assert "custo_planejado_como_realizado" in {c.codigo for c in RG.validar_registro(
        dataclasses.replace(reg, custo_realizado=plan))}
    assert "total_incoerente" in {c.codigo for c in RG.validar_registro(
        dataclasses.replace(reg, custo_realizado=dataclasses.replace(custo, total_R=1.0)))}


def test_registro_selado_serializacao_e_persistencia_imutavel(base, tmp_path):
    real = F.realizacao()
    traj = EX.executar(base.plano, _e0(base.entrada), _executor(base.entrada), real, execucao_uid=UID_EXEC)
    reg = RG.selar_registro(_registro(base, traj, real))
    assert RG.verificar_registro(reg) == []
    assert canonico.de_json(RG.RegistroExecucaoEMS, canonico.json_canonico(reg)) == reg
    caminho = RG.gravar_registro(tmp_path, reg)
    assert RG.ler_registro(caminho) == reg
    assert RG.gravar_registro(tmp_path, reg) == caminho                     # idempotente
    outro = RG.selar_registro(dataclasses.replace(reg, selo="", justificativa_desfecho="outro"))
    with pytest.raises(RG.RegistroImutavelError):
        RG.gravar_registro(tmp_path, outro)
    d = json.loads(caminho.read_text(encoding="utf-8"))
    d["indicadores"]["E_bess_descarga_kWh"] = 0.0
    adult = tmp_path / "adult.json"
    adult.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ContratoInvalido) as ei:
        RG.ler_registro(adult)
    assert "registro_adulterado" in ei.value.codigos


def test_serializacao_deterministica_de_todos_os_contratos(base):
    inv = F.inventario()
    objetos = [(IV.InventarioMicrorrede, inv), (CN.CenarioEMS, F.cenario(inv)), (CN.ConjuntoPrevisao, F.previsao()),
               (CN.Realizacao, F.realizacao()), (EX.PlanoDespacho, base.plano),
               (EX.EstadoMicrorrede, _e0(base.entrada)),
               (RQ.MatrizParametros, RQ.matriz_parametros(inv, contexto="ensaio"))]
    for cls, obj in objetos:
        txt = canonico.json_canonico(obj)
        assert canonico.de_json(cls, txt) == obj, cls.__name__
        assert canonico.json_canonico(canonico.de_json(cls, txt)) == txt
    with pytest.raises(canonico.ErroSerializacao):
        canonico.de_json(EX.EstadoMicrorrede, '{"microrrede_uid": "x"}')
    with pytest.raises(canonico.ErroSerializacao):
        canonico.de_json(EX.EstadoMicrorrede, '{"microrrede_uid": NaN}')


# ======================================================================================== 9. instrumentação
def test_cronometro_e_estatisticas():
    t = iter([0.0, 1.5, 2.0, 2.25])
    cr = IN.Cronometro(relogio=lambda: next(t))
    with cr.fase("resolucao"):
        pass
    with cr.fase("persistencia"):
        pass
    cr.registrar("construcao_modelo", None)
    assert cr.duracoes_s == {"resolucao": 1.5, "persistencia": 0.25}
    with pytest.raises(ValueError):
        cr.registrar("fase_inventada", 1.0)
    e = IN.estatisticas(range(1, 101))
    assert (e.n, e.p50, e.p95, e.p99, e.maximo, e.media) == (100, 50.0, 95.0, 99.0, 100.0, 50.5)
    assert IN.estatisticas([]).p95 is None
    with pytest.raises(ValueError):
        IN.estatisticas([1.0, float("inf")])


@pytest.mark.parametrize("cl,est,term,aceito,esperado", [
    ("otimo", "aceito_otimo", "convergenceCriteriaSatisfied", True, "exito"),
    ("otimo", "rejeitado_auditoria", "convergenceCriteriaSatisfied", False, "erro_numerico"),
    ("factivel_nao_otimo", "aceito_factivel_nao_otimo", "maxTimeLimit", True, "timeout"),
    ("factivel_nao_otimo", "aceito_factivel_nao_otimo", "iterationLimit", True, "exito"),
    ("sem_solucao", "sem_despacho", "maxTimeLimit", False, "timeout"),
    ("inviavel", "sem_despacho", "provenInfeasible", False, "inviavel"),
    ("ilimitado", "sem_despacho", "unbounded", False, "erro_numerico"),
    ("erro", "sem_despacho", "error", False, "erro_numerico"),
    ("bloqueado_validacao", "sem_despacho", None, False, "bloqueado_validacao"),
    ("solver_indisponivel", "sem_despacho", None, False, "erro_integracao"),
])
def test_classificacao_de_desfechos(cl, est, term, aceito, esperado):
    r = SimpleNamespace(classificacao=cl, estado_despacho=est, terminacao=term, aceito=aceito)
    assert IN.classificar_desfecho(r)[0] == esperado


def test_desfecho_de_excecao_de_integracao():
    assert IN.classificar_desfecho(excecao=KeyError("x"))[0] == "erro_integracao"


# ======================================================================================== 10. preflight
def test_preflight_ensaio_aceito_e_operacional_bloqueado():
    inv = F.inventario()
    rel, proj = PF.preflight_ems_v2(inv, F.cenario(inv), F.definicao(), F.previsao(oraculo=True), F.realizacao(),
                                    F.politicas(), contexto="ensaio", compromisso=F.COMPROMISSO)
    assert rel.aceito and proj.aceito, rel.texto()
    assert "dado_sintetico_em_ensaio" in rel.codigos("advertencia")
    assert {i.area for i in rel.itens if i.severidade == "aceitavel"} >= {"inventario", "cenario", "tempo", "referencias"}
    assert PF.hash_preflight(rel) == PF.hash_preflight(PF.preflight_ems_v2(
        inv, F.cenario(inv), F.definicao(), F.previsao(oraculo=True), F.realizacao(), F.politicas(), contexto="ensaio",
        compromisso=F.COMPROMISSO)[0])
    op, _ = PF.preflight_ems_v2(inv, F.cenario(inv), F.definicao(), F.previsao(oraculo=True), F.realizacao(),
                                F.politicas(), contexto="operacional")
    assert not op.aceito and "dado_sintetico_fora_de_ensaio" in op.codigos("bloqueante") and "BLOQUEADO" in op.texto()


def test_preflight_referencias_restricoes_e_series():
    inv = F.inventario()
    p = F.previsao()
    fantasma = dataclasses.replace(p, series=p.series + (CN.SerieRecurso("syn-fantasma", "potencia", p.series[0].serie),))
    pol = F.politicas(termos=("curtailment_operacional", "throughput_bess", "combustivel_h2"))
    rel, _ = PF.preflight_ems_v2(inv, F.cenario(inv), F.definicao(), fantasma,
                                 CN.Realizacao("r", "sintetica", F.realizacao().series[:1], F.proc()), pol,
                                 contexto="ensaio", compromisso={"syn-nada": [1, 1, 1, 1]})
    b = rel.codigos("bloqueante")
    assert {"referencia_uid_inexistente", "compromisso_uid_inexistente", "termo_sem_recurso",
            "realizacao_ausente_para_recurso"} <= b
    sem_prev, proj = PF.preflight_ems_v2(inv, F.cenario(inv), F.definicao(), None, None, None, contexto="ensaio")
    assert "previsao_ausente" in sem_prev.codigos("bloqueante") and proj is None
    assert "realizacao_nao_fornecida" in sem_prev.codigos("advertencia")


def test_preflight_estado_inicial_fora_dos_limites():
    inv = F.inventario()
    rel, proj = PF.preflight_ems_v2(inv, F.cenario(inv, soc_pct=95.0), F.definicao(), F.previsao(), None, F.politicas(),
                                    contexto="ensaio", compromisso=F.COMPROMISSO)
    assert "soc_inicial_fora_dos_limites" in rel.codigos("bloqueante") and proj.entrada is None
    rel2, _ = PF.preflight_ems_v2(inv, F.cenario(inv, ter_p=50.0), F.definicao(), F.previsao(), None, F.politicas(),
                                  contexto="ensaio")
    assert "on_fora_do_dominio" in rel2.codigos("bloqueante")


# ======================================================================================== 11. isolamento
PROIBIDOS = ["streamlit", "pyomo", "highspy", "seeds2", "ems_integration", "orchestrator_runtime", "models", "h2_pemfc",
             "simulation", "config", "numpy", "scipy", "pandas"]


def test_nucleo_da_ponte_so_biblioteca_padrao():
    codigo = (
        "import sys, json, importlib, pkgutil, ems_v2.ponte, ems_v2.fixtures_3c0, ems_v2.ponte_seeds2\n"
        "mods = [m.name for m in pkgutil.iter_modules(ems_v2.ponte.__path__, 'ems_v2.ponte.')]\n"
        "[importlib.import_module(m) for m in mods]\n"
        f"print(json.dumps({{'mods': mods, 'carregados': [p for p in {PROIBIDOS!r} if p in sys.modules]}}))\n")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, env=env, check=True)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert len(res["mods"]) >= 9 and res["carregados"] == [], res
