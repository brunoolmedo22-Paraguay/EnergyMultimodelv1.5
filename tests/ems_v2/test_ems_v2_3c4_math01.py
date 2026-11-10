"""MATH-01 (auditoria matemática independiente sobre ``9ebd760``) — dois defeitos P1, sintético/algébrico.

* **P1-1** ``comparadores.efeito``: a diferença ajustada pela valoração terminal declarada é
  (C_a − p·E_a) − (C_b − p·E_b) = d − p·ΔE (o código usava d + p·ΔE, penalizando a estratégia que conserva energia).
* **P1-2** ``Planejador3C4.sinal`` (política ``periodica``): uma fronteira b >= fim do PRÓPRIO planejamento com
  fim < K_M (cauda esgotada ANTES do fim da missão) recebia sinal ``valido`` = Φ_L, sem degradação nem replanejamento.
  Só b = fim = K_M (fim real da missão) é cauda vazia legítima (Φ_L exato).
"""
from __future__ import annotations

import pytest

from ems_v2.hierarquia.comparadores import LinhaEstrategia, efeito

pytestmark = pytest.mark.synthetic_algebraic


def _linha(nome: str, custo: float, energia: float) -> LinhaEstrategia:
    return LinhaEstrategia(nome, True, "encerrada", None, 12, 12, custo, {"syn-bess": energia}, {}, {}, 12, 0, 0,
                           None, None)


# ------------------------------------------------------------------------------------------------ P1-1
def test_p1_1_ajuste_terminal_com_sinal_correto_e_ordenacao_nao_robusta():
    a, b = _linha("A", 12.0, 10.0), _linha("B", 10.0, 0.0)
    ef = efeito("antecipacao", a, b, precos=(0.0, 0.5, 1.0))
    assert not ef.comparavel and ef.diferenca_R == pytest.approx(2.0)
    assert ef.ajustado_por_preco == pytest.approx({"0": 2.0, "0.5": -3.0, "1": -8.0})
    assert ef.ordenacao_robusta is False                  # a ordenação muda de sinal dentro da faixa


def test_p1_1_ordenacao_robusta_quando_o_sinal_nao_muda_e_terminais_iguais_inalterados():
    ef = efeito("x", _linha("A", 20.0, 10.0), _linha("B", 10.0, 0.0), precos=(0.0, 0.5))
    assert ef.ajustado_por_preco == pytest.approx({"0": 10.0, "0.5": 5.0}) and ef.ordenacao_robusta is True
    ig = efeito("x", _linha("A", 60.4, 0.0), _linha("B", 50.2, 0.0))
    assert ig.comparavel and ig.diferenca_R == pytest.approx(10.2) and ig.ajustado_por_preco == {}


# ------------------------------------------------------------------------------------------------ P1-2
def _executar(**kw):
    pytest.importorskip("pyomo", exc_type=ImportError)
    pytest.importorskip("highspy", exc_type=ImportError)
    from ems_v2 import fixtures_3c4 as F
    from ems_v2.hierarquia import experimentos as X
    return X.executar(F.h2_pico_futuro(), "hier_pwl", **kw)


def _premauras(sinais, K):
    return [s for s in sinais if s.intervalos_cauda == 0 and s.indice_fronteira < K]


def test_p1_2_cauda_esgotada_antes_do_fim_da_missao_nunca_e_valida():
    """N = 3, m = 1, P = 3, H_L = 4 (reprodução MATH-01): em τ_0 o lote vale para b = 3, 4, 5 com fim = 4 < K_M."""
    x = _executar(H_L=4, planejador_kw={"periodo": 3})
    K = x.controlador.cfg.malha.intervalos_missao
    co = x.controlador.coordenacoes
    assert x.resultado.situacao == "encerrada"
    emitidos = [s for c in co for s in c.lote]
    prem = _premauras(emitidos, K)
    assert prem, "a configuração deve reproduzir fronteiras além do fim do planejamento"
    for s in prem:                                         # emitidos, mas INDISPONÍVEIS e com o motivo registrado
        assert s.qualidade.estado == "indisponivel" and "esgotada prematuramente" in s.qualidade.motivo
    for c in co:                                           # nenhuma janela aplicou cauda esgotada como válida
        if c.situacao == "valido":
            assert not (c.sinal.intervalos_cauda == 0 and c.sinal.indice_fronteira < K)
    replan = [c for c in co if any(x.codigo == "sinal_do_lote_invalido_replanejado" for x in c.constatacoes)]
    assert replan and all(c.origem_sinal == "planejado_nesta_janela" for c in replan)   # política existente
    assert all(c.situacao == "valido" for c in co)
    assert x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R == pytest.approx(55.5)  # = P = 1


def test_p1_2_degradacao_declarada_registrada_se_o_replanejamento_nao_produz_sinal():
    """Sinal do lote com cauda esgotada ⇒ replanejamento; se o replanejamento falha, a degradação DECLARADA é
    aplicada e rotulada (nunca Φ_L como continuação válida). Planejador real só na emissão de τ_0."""
    pytest.importorskip("pyomo", exc_type=ImportError)
    pytest.importorskip("highspy", exc_type=ImportError)
    from types import SimpleNamespace

    from ems_v2.hierarquia.experimentos import config_solver
    from ems_v2.hierarquia.planejador import ResolvedorPlanejador3C4

    class SoNaPrimeiraEmissao(ResolvedorPlanejador3C4):
        def resolver(self, entrada):
            if "emissão k = 0" in repr(entrada.procedencia):
                return super().resolver(entrada)
            return SimpleNamespace(aceito=False, classificacao="erro", estado_despacho="sem_despacho",
                                   hash_entrada=None, custos_modelo={}, limite_dual=None,
                                   codigos=lambda: {"falha_injetada"})

    x = _executar(H_L=4, planejador_kw={"periodo": 3}, planejador_resolvedor=SoNaPrimeiraEmissao(config_solver()),
                  nome="math01-p1-2-degradacao")
    co = x.controlador.coordenacoes
    assert x.resultado.situacao == "encerrada"
    assert [c.situacao for c in co] == ["valido"] + ["degradado_sem_valor_futuro"] * 8 + ["valido"] * 3
    for c in co[1:9]:                                      # motivo e lote inválido registrados na coordenação
        assert c.termo_aplicado.tipo == "nenhum_declarado" and c.motivo
    assert any(x.codigo == "sinal_do_lote_invalido_replanejado" for x in co[1].constatacoes)
    K = x.controlador.cfg.malha.intervalos_missao
    assert all(c.sinal.indice_fronteira == K == c.sinal.indice_fim_planejamento for c in co[9:])


def test_p1_2_cauda_vazia_legitima_no_fim_real_da_missao_e_periodica_com_horizonte_suficiente():
    x = _executar(H_L=10, planejador_kw={"periodo": 3})
    K = x.controlador.cfg.malha.intervalos_missao
    co = x.controlador.coordenacoes
    assert not _premauras([s for c in co for s in c.lote], K)
    assert [c.origem_sinal for c in co] == ["planejado_nesta_janela", "lote_periodico", "lote_periodico"] * 4
    assert all(c.situacao == "valido" for c in co)
    assert x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R == pytest.approx(50.2)
    vazias = [c.sinal for c in co if c.sinal.intervalos_cauda == 0]
    assert vazias and all(s.indice_fronteira == K == s.indice_fim_planejamento and s.qualidade.estado == "valido"
                          for s in vazias)                 # Φ_L exato apenas em b = fim = K_M
