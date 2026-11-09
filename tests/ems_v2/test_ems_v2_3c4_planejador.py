"""Piso 3C-4 — planejador de longo prazo e custo de continuação contra HiGHS real (H4, H6, H10, H13, políticas).

Sintético/algébrico. Valores ANALÍTICOS da cauda de H2 (banco 20 kWh, carga ≤ 5 kW, descarga ≤ 10 kW, η = 1,
c_thr = 0,01; demanda 10 kW; tarifa 0,5 salvo 1,5 nas horas 8–9; Φ_L = 0 declarado; K_M = 12):

em τ_6 (N = 3 ⇒ fronteira b = 9; fim do planejamento min(6 + 10, 12) = 12) a cauda é [9, 12): hora 9 a 1,5 e horas
10–11 a 0,5 (nenhuma recarga útil). V(E) = 1,5 (10 − min(E, 10)) + 0,5 (20 − max(0, E − 10)) + 0,01 E:
V(0) = 25, V(5) = 17,55, V(10) = 10,1, V(15) = 7,65, V(20) = 5,2 ⇒ λ_E = 1,49 R$/kWh em [0, 10] (energia usada no
pico) e 0,49 em [10, 20] (energia usada fora do pico): sinal, unidade e quebra conferidos por reotimizações
INDEPENDENTES (H10) e por SOC baixo/médio/alto (H6).
"""
from __future__ import annotations

from functools import lru_cache
from types import SimpleNamespace

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
pytest.importorskip("highspy", exc_type=ImportError)

from ems_v2 import fixtures_3c4 as F  # noqa: E402
from ems_v2.hierarquia import experimentos as X  # noqa: E402
from ems_v2.hierarquia.planejador import ResolvedorPlanejador3C4  # noqa: E402
from ems_v2.hierarquia.valor import inclinacoes_1d  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
V_ANALITICO = {0.0: 25.0, 5.0: 17.55, 10.0: 10.1, 15.0: 7.65, 20.0: 5.2}


@lru_cache(maxsize=None)
def run(estr, cen="h2_pico_futuro", **kw):
    return X.executar(getattr(F, cen)(), estr, **dict(kw))


def run_kw(estr, cen="h2_pico_futuro", **kw):
    return run(estr, cen, **{k: (tuple(sorted(v.items())) if isinstance(v, dict) else v) for k, v in kw.items()})


def pk(**kw):
    return tuple(sorted(kw.items()))


def coord(x, j):
    return x.controlador.coordenacoes[j]


def test_h10_valores_e_inclinacoes_analiticos():
    co = coord(run("hier_pwl"), 6)
    assert co.situacao == "valido" and co.sinal.indice_fronteira == 9 and co.sinal.indice_fim_planejamento == 12
    m = co.sinal.modos[0]
    vals = {p.energias_kWh[0]: p.valor_R for p in m.pontos}
    for E, V in V_ANALITICO.items():
        assert vals[E] == pytest.approx(V, abs=1e-9)
    assert [-x for x in inclinacoes_1d(m.pontos)] == pytest.approx([1.49, 1.49, 0.49, 0.49], abs=1e-9)
    assert all(v.erro_R <= 1e-6 for v in co.sinal.qualidade.validacoes)       # pontos médios reotimizados
    assert co.sinal.unidade_valor == "R$" and co.sinal.unidade_energia == "kWh"


def test_h6_soc_baixo_medio_alto():
    m = coord(run("hier_pwl"), 6).sinal.modos[0]
    lam = dict(zip(("baixo", "medio_inferior", "medio_superior", "alto"), [-x for x in inclinacoes_1d(m.pontos)]))
    assert lam["baixo"] == pytest.approx(1.49) and lam["alto"] == pytest.approx(0.49)
    assert lam["baixo"] >= lam["medio_superior"] - 1e-9 >= lam["alto"] - 2e-9 > 0   # marginal decrescente (convexo)


def test_h10_sensibilidade_local_por_diferenca_central():
    """τ_0: E_ref = 20 (plano longo preserva o banco); só o lado inferior é factível (E = C s_max) ⇒ diferença
    UNILATERAL; λ = 0,51 = custo de REPOR 1 kWh da rede antes do pico (0,5 + 0,01). τ_6: E_ref = 10 está NA quebra de
    V (1,49 | 0,49) ⇒ a diferença central (0,99) não representa V em [8, 12] ⇒ sinal INDISPONÍVEL (não defensável)."""
    x = run("hier_local")
    co = coord(x, 0)
    s = co.sinal
    assert co.situacao == "valido" and s.tipo == "valor_marginal_local"
    sl = s.sensibilidade
    assert sl.energias_referencia_kWh == (20.0,) and sl.metodo == "diferenca_unilateral_no_limite"
    assert sl.lambdas_R_kWh[0] == pytest.approx(0.51, abs=1e-9)
    assert s.modos[0].dominio_min_kWh == (18.0,) and s.modos[0].dominio_max_kWh == (20.0,)
    c6 = coord(x, 6)
    assert c6.sinal.qualidade.estado == "indisponivel" and c6.situacao == "degradado_sem_valor_futuro"
    assert c6.sinal.sensibilidade.lambdas_R_kWh[0] == pytest.approx(0.99)      # evidência conservada, não usada
    assert "NÃO defensável" in c6.sinal.qualidade.motivo
    assert c6.sinal.qualidade.erro_interpolacao_max_R == pytest.approx(1.0, abs=1e-9)   # |(1,49 − 0,99)·2|


def test_phi_l_linear_declarado_com_cauda_vazia():
    x = run_kw("hier_pwl", planejador_kw={"termo": F.termo_longo("valor_linear_declarado", valores={F.BESS: 0.3})})
    co = coord(x, 9)                                       # b = 12 = fim ⇒ V^tail ≡ Φ_L (exato, sem resolver)
    assert co.sinal.intervalos_cauda == 0 and co.sinal.qualidade.avaliacoes == 0
    assert [(p.energias_kWh[0], p.valor_R) for p in co.sinal.modos[0].pontos] == [(0.0, 0.0), (20.0, -6.0)]


def _lambda0(c):
    co = X.executar(c, "hier_pwl").controlador.coordenacoes[0]
    return -inclinacoes_1d(co.sinal.modos[0].pontos)[0]


def test_h4_deslocamento_do_pico_muda_o_valor_coerentemente():
    b = (F.Banco(pcmax=5.0),)
    cedo, tarde = _lambda0(F.h4_pico_deslocado(4, bancos=b)), _lambda0(F.h4_pico_deslocado(8, bancos=b))
    plano = _lambda0(F.h1_tarifa_plana(bancos=b))
    assert plano == pytest.approx(0.49)                    # sem incentivo: energia vale a tarifa plana − c_thr
    assert cedo == pytest.approx(1.49)                     # pico logo após a fronteira: não há tempo para recarregar
    assert tarde == pytest.approx(0.51)                    # pico distante: a energia é REPOSTA da rede a 0,5 + 0,01
    assert cedo > tarde > plano


def test_h13_horizontes_curto_e_longo():
    custos = {H: run_kw("hier_pwl", H_L=H).resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R
              for H in (4, 6, 8, 10)}
    sem = run("mpc_sem_sinal").resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R
    assert sem == pytest.approx(60.4) and custos[10] == pytest.approx(50.2)
    assert all(custos[a] >= custos[b] - 1e-9 for a, b in ((4, 6), (6, 8), (8, 10)))   # mais informação ⇒ nunca pior
    assert all(v <= sem + 1e-9 for v in custos.values())
    N4 = {N: run_kw("mpc_sem_sinal", N=N).resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R
          for N in (2, 3, 4)}
    assert N4 == pytest.approx({2: 65.3, 3: 60.4, 4: 55.5})   # sem sinal: melhora com N, mas H_S curto é míope
    assert custos[10] < min(N4.values())


def test_politica_periodica_lote_e_auditoria():
    x = run_kw("hier_pwl", planejador_kw={"periodo": 3})
    co = x.controlador.coordenacoes
    assert [c.origem_sinal for c in co] == ["planejado_nesta_janela", "lote_periodico", "lote_periodico"] * 4
    assert all(c.situacao == "valido" for c in co)
    assert x.resultado.registro_hierarquico.contagens["sinais_de_lote"] == 8
    assert x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R == pytest.approx(50.2)
    for c in co:                                           # cada sinal só vale para a SUA janela/fronteira
        assert c.sinal.indice_janela == c.indice_janela and c.sinal.k_aplicacao == c.k


class PlanejadorQueFalha:
    natureza = "ensaio_falha_injetada"
    identificador = "planejador-falha"

    def resolver(self, e):
        return SimpleNamespace(aceito=False, classificacao="erro", estado_despacho="sem_despacho", hash_entrada=None,
                               custos_modelo={}, limite_dual=None, codigos=lambda: {"falha_injetada"})

    def configuracao_registro(self):
        return {"resolvedor": self.identificador}


def test_degradacao_sem_valor_futuro_equivale_ao_mpc_3c3():
    """Planejador sempre falhando ⇒ todas as janelas DEGRADADAS e rotuladas; planos IDÊNTICOS (hash) ao MPC 3C-3."""
    base = run("mpc_sem_sinal")
    x = X.executar(F.h2_pico_futuro(), "hier_pwl", planejador_resolvedor=PlanejadorQueFalha(),
                   nome=base.controlador.cfg.identidade.missao_uid and "H2-mpc_sem_sinal-N3-m1")
    sit = [c.situacao for c in x.controlador.coordenacoes]
    # cauda não vazia ⇒ degradada; cauda VAZIA (b = fim) ⇒ V ≡ Φ_L = 0 exato, sem resolver (válido)
    assert sit == ["degradado_sem_valor_futuro"] * 9 + ["valido"] * 3
    assert all(c.sinal.intervalos_cauda == 0 for c in x.controlador.coordenacoes[9:])
    assert [p.aplicado for r in x.resultado.registros for p in r.conteudo.passos] == \
        [p.aplicado for r in base.resultado.registros for p in r.conteudo.passos]
    assert [r.conteudo.hash_plano for r in x.resultado.registros][:9] == [r.conteudo.hash_plano for r in
                                                                          base.resultado.registros][:9]
    assert x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R == pytest.approx(60.4)


def test_degradacao_interromper():
    x = X.executar(F.h2_pico_futuro(), "hier_pwl", planejador_resolvedor=PlanejadorQueFalha(), nome="deg-int",
                   planejador_kw={"degradacao": "interromper"})
    assert x.resultado.situacao == "interrompida" and x.resultado.classe_falha == "bloqueado_validacao"
    assert [c.situacao for c in x.controlador.coordenacoes] == ["indisponivel_interrompe"]
    assert x.resultado.registros[0].conteudo.hash_plano is None


def test_degradacao_referencia_por_tolerancia_nao_atingida():
    """Grade de 4 pontos sem refinamento (pontos_max = 4) e tolerância 1e-6: a quebra de V em E = 10 cai DENTRO de um
    segmento ⇒ erro no ponto médio > tolerância ⇒ sinal indisponível (motivo registrado) ⇒ referência dura do plano
    longo (degradação declarada), nunca uma aproximação inválida aceita."""
    x = run_kw("hier_pwl", planejador_kw={"pontos": 4, "pontos_max": 4, "degradacao": "referencia_terminal_do_plano_longo"})
    sit = [c.situacao for c in x.controlador.coordenacoes]
    assert "degradado_referencia" in sit
    for c in x.controlador.coordenacoes:
        if c.situacao == "degradado_referencia":
            assert "tolerância de interpolação não atingida" in c.sinal.qualidade.motivo
            assert c.termo_aplicado.tipo == "energia_minima_declarada"
    assert x.resultado.situacao == "encerrada"


def test_refinamento_adaptativo_insere_a_quebra():
    x = run_kw("hier_pwl", planejador_kw={"pontos": 4, "pontos_max": 9})
    m = coord(x, 6).sinal.modos[0]
    es = [p.energias_kWh[0] for p in m.pontos]
    assert len(es) > 4 and coord(x, 6).sinal.qualidade.estado == "valido"
    assert coord(x, 6).sinal.qualidade.erro_interpolacao_max_R <= 1e-6


def test_custo_computacional_registrado():
    x = run("hier_pwl")
    rh = x.resultado.registro_hierarquico
    assert rh.contagens["avaliacoes_planejador"] > 0 and rh.contagens["execucoes_planejador"] == 12
    assert rh.tempos_planejador_s["total_s"] > 0 and "cauda_s" in rh.tempos_planejador_s
    assert isinstance(ResolvedorPlanejador3C4(None).configuracao_registro(), dict)
