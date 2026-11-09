"""Piso 3C-4 — MPC HIERÁRQUICO de ponta a ponta com HiGHS real (H1–H3, H5, H7–H9, H12, H14–H17).

Simulação causal de laço fechado ALGÉBRICA sobre fixtures SINTÉTICAS (``ems_v2.fixtures_3c4``; valores analíticos nas
docstrings dos cenários): não é validação física, fatura real nem tempo real. Sem Pyomo/HiGHS: pulados.
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2 import fixtures_3c4 as F  # noqa: E402
from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.hierarquia import experimentos as X  # noqa: E402
from ems_v2.hierarquia.auditoria import auditar_missao_hierarquica, retomar_controlador_hierarquico  # noqa: E402
from ems_v2.hierarquia.comparadores import comparar  # noqa: E402
from ems_v2.hierarquia.mpc import nome_coordenacao, nome_vinculo_hier  # noqa: E402
from ems_v2.mpc.orquestrador import executar_missao_simulada  # noqa: E402
from ems_v2.mpc.registro import selar  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic


@lru_cache(maxsize=None)
def run(cen: str, estr: str, **kw):
    kw = {k: (dict(v) if k == "planejador_kw" else v) for k, v in kw.items()}
    return X.executar(getattr(F, cen)(), estr, **kw)


def custo(x):
    return x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R


def auditar(x, **over):
    r, c = x.resultado, x.controlador
    a = dict(registros_3c0=r.registros_3c0, anexos=r.anexos_3c3, registro_rede=r.registro_rede,
             coordenacoes=r.coordenacoes, registro_hierarquico=r.registro_hierarquico, verdade=x.entorno._verdade)
    cfg_plan = over.pop("cfg_plan", c.cfg_plan)
    a.update(over)
    return auditar_missao_hierarquica(r.registro_missao, r.registros, r.livro, x.modelo, c.cfg_rede, cfg_plan, **a)


# ------------------------------------------------------------------------------------------------ H1 · H2 · H3 · H14
def test_h2_h14_comparacao_de_politicas_e_efeitos():
    ex = {e: run("h2_pico_futuro", e) for e in X.ESTRATEGIAS}
    cmp = comparar(ex)
    L = cmp["linhas"]
    assert {k: round(v.custo_realizado_R, 9) for k, v in L.items()} == {
        "open_loop": 50.2, "mpc_sem_sinal": 60.4, "mpc_encolhido": 50.2, "hier_pwl": 50.2, "hier_local": 50.2,
        "hier_ref_dura": 50.2, "hier_ref_branda": 50.2, "oraculo": 50.2}
    assert all(v.concluida and v.energias_finais_kWh == {F.BESS: 0.0} for v in L.values())
    e = cmp["efeitos"]
    assert e["reotimizacao"].comparavel and e["reotimizacao"].diferenca_R == pytest.approx(0.0)
    assert e["antecipacao"].comparavel and e["antecipacao"].diferenca_R == pytest.approx(10.2)
    assert e["informacao_perfeita_hier_pwl"].diferenca_R == pytest.approx(0.0)
    assert not L["oraculo"].causal
    assert auditar(ex["hier_pwl"]).aceito


def test_h1_tarifa_plana_sem_incentivo_artificial():
    a, b = run("h1_tarifa_plana", "mpc_sem_sinal"), run("h1_tarifa_plana", "hier_pwl")
    assert custo(a) == pytest.approx(50.2) and custo(b) == pytest.approx(50.2)
    cmp = comparar({"mpc_sem_sinal": a, "hier_pwl": b})
    assert cmp["efeitos"]["antecipacao"].comparavel and cmp["efeitos"]["antecipacao"].diferenca_R == pytest.approx(0.0)
    s0 = b.controlador.coordenacoes[0].sinal          # tarifa plana ⇒ λ = 0,5 − 0,01 em todo o domínio
    from ems_v2.hierarquia.valor import inclinacoes_1d
    assert [-x for x in inclinacoes_1d(s0.modos[0].pontos)] == pytest.approx([0.49] * 4)


def test_h3_pico_dentro_do_horizonte_curto_sem_beneficio_adicional():
    a, b = run("h3_pico_no_horizonte_curto", "mpc_sem_sinal"), run("h3_pico_no_horizonte_curto", "hier_pwl")
    assert custo(a) == pytest.approx(custo(b))
    assert comparar({"mpc_sem_sinal": a, "hier_pwl": b})["efeitos"]["antecipacao"].diferenca_R == pytest.approx(0.0)


# ------------------------------------------------------------------------------------------------ H5 erro de previsão
def test_h5_erro_de_previsao_mesma_verdade():
    L_real = (10.0, 10.0, 13.0, 13.0, 13.0, 13.0, 10.0, 10.0, 12.0, 12.0, 8.0, 10.0)
    c = F.h2_pico_futuro(L_real=L_real)
    a, b = X.executar(c, "mpc_sem_sinal"), X.executar(c, "hier_pwl")
    cmp = comparar({"mpc_sem_sinal": a, "hier_pwl": b})
    ef = cmp["efeitos"]["antecipacao"]
    assert cmp["linhas"]["hier_pwl"].concluida and cmp["linhas"]["mpc_sem_sinal"].concluida
    assert ef.comparavel and ef.diferenca_R > 0
    assert a.entorno._verdade == b.entorno._verdade      # MESMA verdade sintética
    assert auditar(b).aceito                             # inclui separação previsão × realização (verdade)


# ------------------------------------------------------------------------------------------------ H7 · H8 reserva física
@pytest.mark.parametrize("cen", ["h7_limite_importacao", "h8_indisponibilidade_pcc"])
def test_h7_h8_valor_de_reserva_por_restricao_fisica(cen):
    a, b = run(cen, "mpc_sem_sinal"), run(cen, "hier_pwl")
    assert a.resultado.situacao == "interrompida" and a.resultado.classe_falha == "inviavel"
    assert b.resultado.situacao == "encerrada" and custo(b) == pytest.approx(50.2)
    doms = [c.sinal.modos[0].dominio_min_kWh[0] for c in b.controlador.coordenacoes
            if c.sinal is not None and c.sinal.modos and c.sinal.intervalos_cauda > 0]
    assert max(doms) > 0                                 # reserva mínima exigida pela factibilidade da cauda
    assert any(c.sinal.modos[0].energias_inviaveis for c in b.controlador.coordenacoes
               if c.sinal is not None and c.sinal.modos)
    assert "antecipacao" in comparar({"mpc_sem_sinal": a, "hier_pwl": b})["efeitos"]
    assert not comparar({"mpc_sem_sinal": a, "hier_pwl": b})["efeitos"]["antecipacao"].comparavel
    assert auditar(b).aceito


# ------------------------------------------------------------------------------------------------ H9 · H17 recursos
def test_h9_pemfc_obrigacoes_e_modos():
    b = run("h9_pemfc", "hier_pwl")
    assert b.resultado.situacao == "encerrada" and b.controlador.obrigacoes_pendentes()[0] == {}
    com_cauda = [c for c in b.controlador.coordenacoes if c.sinal is not None and c.sinal.intervalos_cauda > 0]
    assert com_cauda and all(len(c.sinal.modos) == 2 for c in com_cauda)
    for c in com_cauda:                                  # valor do estado LIGADO separado do valor da energia
        off, on = c.sinal.modos
        assert (off.geradores[0].ligado, on.geradores[0].ligado) == (False, True)
    for a in b.resultado.anexos_3c3:                     # memória terminal PLANEJADA sem obrigação residual
        assert all(m.obrigacao_residual_s == 0 for m in a.conteudo.plano_rede.commitment.memorias_terminais)
    assert auditar(b).aceito


def test_h9_linha_de_base_apos_hotfix_B3C4_01_e_artefato_C01_documentado_B3C4_10():
    """Após o hotfix B3C4-01 (auditoria do PR #17) a deriva de ENERGIA é projetada (k = 8, 1 ulp) e a missão segue;
    ela para em k = 10 por um SEGUNDO artefato herdado, fora da autorização (B3C4-10): o solver devolve
    P_imp = −8,88e-16 kW e a regra C-01 do 3C-3 (real >= 0, sem recorte) recusa o plano. Nenhuma superioridade é
    afirmada (missão não concluída)."""
    a = run("h9_pemfc", "mpc_sem_sinal")
    assert a.resultado.situacao == "interrompida" and a.resultado.classe_falha == "integridade" and a.controlador.k == 10
    msg = " ".join(c.mensagem for c in a.resultado.registros[-1].conteudo.constatacoes)
    assert "intercambio_programado_invalido" in msg and "-8.881784197001252e-16" in msg
    assert not comparar({"mpc_sem_sinal": a, "hier_pwl": run("h9_pemfc", "hier_pwl")})["efeitos"][
        "antecipacao"].comparavel


def test_h17_dois_bancos_envoltoria_convexa():
    a = run("h17_dois_bancos", "mpc_sem_sinal")
    b = run("h17_dois_bancos", "hier_pwl", planejador_kw=(("pontos", 3),))
    assert custo(a) == pytest.approx(55.5) and custo(b) == pytest.approx(50.2)
    c0 = b.controlador.coordenacoes[0].sinal
    assert c0.modos[0].representacao == "envoltoria_convexa_nd" and c0.modos[0].convexidade_verificada_na_amostra
    assert c0.baterias == (F.BESS, F.BESS2)
    assert auditar(b).aceito


# ------------------------------------------------------------------------------------------------ H12 causalidade
def test_h12_causalidade_por_intervencao():
    """Provedor que corrige a demanda pela ÚLTIMA observação; verdades A e B iguais até a hora 6 e diferentes depois
    (14 kW). Decisões em τ_k <= τ_6 só podem usar observações de intervalos < k ⇒ coordenação (sinal, plano longo,
    decomposição) e planos IDÊNTICOS para k <= 6; a intervenção altera decisões posteriores (não é vácua)."""
    base = F.h2_pico_futuro()
    vb = replace(base, L_real=(10.0,) * 6 + (14.0,) * 6)
    a = X.executar(base, "hier_pwl", prov="correcao", nome="h12")
    b = X.executar(vb, "hier_pwl", prov="correcao", nome="h12")
    from ems_v2.hierarquia.mpc import impressao_coordenacao
    ia = [impressao_coordenacao(c) for c in a.controlador.coordenacoes]
    ib = [impressao_coordenacao(c) for c in b.controlador.coordenacoes]
    assert ia[:7] == ib[:7]
    assert [r.conteudo.hash_plano for r in a.resultado.registros][:7] == \
        [r.conteudo.hash_plano for r in b.resultado.registros][:7]
    assert ia[7:] != ib[7:]


# ------------------------------------------------------------------------------------------------ H15 retomada
def _parcial(d, n=5, **kw):
    c = F.h2_pico_futuro()
    ctrl, ent, mod, N, m = X.montar(c, "hier_pwl", nome="h15", diretorio=d, **kw)
    executar_missao_simulada(ctrl, ent, max_janelas=n, finalizar=False)
    return ctrl, ent, mod


def _retomar(ctrl, mod, d):
    return retomar_controlador_hierarquico(d, ctrl.cfg, mod, ctrl.provedor, ctrl.resolvedor, ctrl.fontes,
                                           ctrl.cfg_rede, ctrl.cfg_plan, ctrl.res_plan,
                                           identificadores_verdade=ctrl.id_verdade, fontes_verdade=ctrl.fontes_verdade)


def test_h15_retomada_deterministica_com_lote_pendente():
    kw = {"planejador_kw": {"periodo": 2}}
    cont = X.executar(F.h2_pico_futuro(), "hier_pwl", nome="h15", **kw)
    with tempfile.TemporaryDirectory() as d:
        ctrl, ent, mod = _parcial(d, 5, **kw)
        assert ctrl._lote                                  # janela 5 planejou o lote {5, 6}: 6 pendente
        c2, pt = _retomar(ctrl, mod, d)
        assert pt.k == 5 and c2._lote.keys() == ctrl._lote.keys()
        r2 = executar_missao_simulada(c2, ent)
    assert r2.registro_missao.impressao_deterministica == cont.resultado.registro_missao.impressao_deterministica
    assert r2.registro_hierarquico.impressoes_coordenacao == cont.resultado.registro_hierarquico.impressoes_coordenacao
    assert r2.registro_missao.conteudo.custo_realizado_acumulado.total_R == pytest.approx(50.2)


@pytest.mark.parametrize("alvo", ["coord_sem_reselar", "coord_reselada", "vinculo_lote", "config_planejador"])
def test_h15_h16_retomada_recusa_artefatos_adulterados(alvo):
    kw = {"planejador_kw": {"periodo": 2}}
    with tempfile.TemporaryDirectory() as d:
        ctrl, ent, mod = _parcial(d, 5, **kw)
        m = ctrl.cfg.identidade.missao_uid
        if alvo.startswith("coord"):
            p = Path(d) / nome_coordenacao(m, 2)
            doc = json.loads(p.read_text())
            doc["decomposicao"]["custo_futuro_estimado_R"] += 1.0
            if alvo == "coord_reselada":
                from ems_v2.hierarquia.mpc import RegistroCoordenacao3C4
                from ems_v2.ponte.canonico import de_json, json_canonico
                doc = json.loads(json_canonico(selar(de_json(RegistroCoordenacao3C4, json.dumps(doc)))))
            p.write_text(json.dumps(doc))
        elif alvo == "vinculo_lote":
            p = Path(d) / nome_vinculo_hier(m, 4)
            doc = json.loads(p.read_text())
            doc["lote_pendente"][0]["modos"][0]["pontos"][0]["valor_R"] -= 1.0
            p.write_text(json.dumps(doc))
        else:
            ctrl.cfg_plan = replace(ctrl.cfg_plan, tolerancia_interpolacao_R=1e-3)
        with pytest.raises(ContratoInvalido):
            _retomar(ctrl, mod, d)


# ------------------------------------------------------------------------------------------------ H16 auditoria
def _reselar_coord(c, **mud):
    return selar(replace(c, **mud))


def test_h16_auditoria_de_missao_adversarial():
    x = run("h2_pico_futuro", "hier_pwl")
    co = list(x.resultado.coordenacoes)
    assert auditar(x).aceito

    def rej(**kw):
        r = auditar(x, **kw)
        assert not r.aceito
        return r.codigos()
    d = co[3].decomposicao
    alt = co[:3] + [_reselar_coord(co[3], decomposicao=replace(d, custo_futuro_estimado_R=d.custo_futuro_estimado_R
                                                               + 1.0))] + co[4:]
    assert {"coordenacao_nao_comprometida", "custo_futuro_divergente"} <= rej(coordenacoes=tuple(alt))
    m = co[2].sinal.modos[0]
    s_alt = replace(co[2].sinal, modos=(replace(m, pontos=(replace(m.pontos[0], valor_R=m.pontos[0].valor_R + 5),)
                                                + m.pontos[1:]),))
    alt = co[:2] + [_reselar_coord(co[2], sinal=s_alt)] + co[3:]
    assert {"sinal_invalido_na_auditoria", "sinal_aplicado_divergente"} & rej(coordenacoes=tuple(alt))
    assert "coordenacoes_em_numero_divergente" in rej(coordenacoes=tuple(co[:-1]))
    assert "auditoria_integral_incompleta" in rej(registro_hierarquico=None)
    outra = replace(x.controlador.cfg_plan, pontos_iniciais=6)
    assert {"sinal_nao_vinculado_na_auditoria", "configuracao_hierarquica_divergente"} <= rej(cfg_plan=outra)
    rh = x.resultado.registro_hierarquico
    assert "registro_hierarquico_adulterado" in rej(registro_hierarquico=replace(rh, contagens={**rh.contagens,
                                                                                               "valido": 0}))


def test_custo_realizado_nunca_contem_valor_futuro_e_decomposicao():
    x = run("h2_pico_futuro", "hier_pwl")
    for r0 in x.resultado.registros_3c0:
        assert not any("futuro" in c.termo for c in r0.custo_realizado.componentes)
        assert not r0.valor_futuro.contabilizado_como_custo
        cm = r0.custo_objetivo_planejado
        assert cm["total"] == pytest.approx(sum(v for k, v in cm.items() if k != "total"))
    for c in x.controlador.coordenacoes:
        d = c.decomposicao
        assert d.objetivo_total_R == pytest.approx(d.custo_operativo_previsto_R + (d.custo_futuro_estimado_R or 0.0))
    acc = x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R
    assert acc == pytest.approx(sum(r.custo_realizado.total_R for r in x.resultado.registros_3c0))


def test_reproducao_deterministica():
    a = X.executar(F.h2_pico_futuro(), "hier_pwl", nome="det")
    b = X.executar(F.h2_pico_futuro(), "hier_pwl", nome="det")
    assert a.resultado.registro_missao.impressao_deterministica == b.resultado.registro_missao.impressao_deterministica
    assert a.resultado.registro_hierarquico.impressoes_coordenacao == \
        b.resultado.registro_hierarquico.impressoes_coordenacao
