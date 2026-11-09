"""Auditoria independente do PR #17 (commit auditado ``9630e73``): C-3C4-A01, C-3C4-A02 e B3C4-01.

Sintético/algébrico. Cada defeito foi REPRODUZIDO sobre o commit auditado antes da correção (saída literal em
``docs/ems_v2/EVIDENCIA_3C4_EJECUCION.md`` §4). Testes que exigem HiGHS são pulados sem Pyomo.

* **A01** — o ``RegistroMissaoHierarquica3C4`` alterado e RE-SELADO (contagens, energias finais, valoração terminal,
  hash da configuração de rede, ``missao_uid``, tempos) era aceito pela auditoria integral; agora cada campo é
  confrontado com a sua fonte (o selo só detecta alteração do conteúdo selado — não identifica uma fonte confiável).
* **A02** — uma grade sem ponto factível NÃO prova inviabilidade: só um certificado de cobertura sobre a faixa
  inteira justifica ``inviavel``; sem ele o modo é ``dominio_indeterminado`` e o sinal fica indisponível (nenhuma
  alternativa mais barata omitida em silêncio).
* **B3C4-01** — hotfix autorizado: projeção EXCLUSIVAMENTE numérica da energia no limite (excesso <= min(tolE D07,
  16 u S)), reconstruível bit a bit; excessos maiores inalterados (D07).
"""
from __future__ import annotations

import math
import tempfile
from dataclasses import replace
from functools import lru_cache
from types import SimpleNamespace

import pytest

from ems_v2 import fixtures_3c4 as F
from ems_v2.audit import Tolerancias
from ems_v2.hierarquia.contrato import DiagnosticoModo, EstadoTerminalGerador, selar_sinal, validar_sinal
from ems_v2.hierarquia.planejador import JanelaAlvo, Planejador3C4
from ems_v2.ponte.execucao import (ExecutorAlgebricoReferencia, EstadoArmazenamento, EstadoMicrorrede,
                                   KAPPA_ARREDONDAMENTO, UNIDADE_ARREDONDAMENTO, projecao_numerica_energia)
from test_ems_v2_3c4_apoio import entrada, sinal

pytestmark = pytest.mark.synthetic_algebraic

try:
    import highspy  # noqa: F401
    import pyomo  # noqa: F401
    COM_SOLVER = True
except ImportError:
    COM_SOLVER = False
solver = pytest.mark.skipif(not COM_SOLVER, reason="Pyomo/HiGHS indisponíveis (requirements-ems_v2.txt)")


# ================================================================================================ B3C4-01
@pytest.mark.parametrize("C", [1.0, 10.0, 100.0, 1000.0])
@pytest.mark.parametrize("smin,smax", [(0.0, 1.0), (0.1, 0.9)])
def test_b01_politica_nos_dois_extremos_varias_capacidades(C, smin, smax):
    lo, hi = smin * C, smax * C
    tolE = Tolerancias().energia_abs_kWh + Tolerancias().energia_rel_capacidade * C
    S = 2 * hi
    eps = min(tolE, KAPPA_ARREDONDAMENTO * UNIDADE_ARREDONDAMENTO * (S + max(lo, hi)))
    for lim, sinal_ in ((hi, +1), (lo, -1)):
        ulp = math.ulp(lim) if lim else math.ulp(1.0)
        v, corr, nome, e = projecao_numerica_energia(lim + sinal_ * ulp, lo, hi, S, tolE)
        assert (v, nome) == (lim, "superior" if sinal_ > 0 else "inferior") and corr == pytest.approx(ulp) and e == eps
        # excesso REAL pequeno mas acima de ε_num (ainda <= tolE): NÃO projetado (tratamento D07 inalterado)
        x = lim + sinal_ * (eps * 4 + ulp)
        assert projecao_numerica_energia(x, lo, hi, S, tolE)[:3] == (x, 0.0, None)
    for x in (lo, hi, (lo + hi) / 2):                     # estados interiores/no limite nunca são alterados
        assert projecao_numerica_energia(x, lo, hi, S, tolE)[:3] == (x, 0.0, None)


def test_b01_eps_limitado_pela_tolerancia_D07():
    v = projecao_numerica_energia(1000.0 + math.ulp(1000.0), 0.0, 1000.0, 2000.0, 1e-18)
    assert v[2] is None and v[3] == 1e-18                  # ε_num = min(tolE, κuS): D07 menor ⇒ nada projetado


def _executor(C, smin, smax, e0):
    e = entrada(1, bancos=(F.Banco(C=C, e0=e0, pmax=10.0, smin=smin, smax=smax),))
    est = EstadoMicrorrede(e.base.microrrede_uid, 0, F.INICIO, (EstadoArmazenamento(F.BESS, e0),), ())
    return ExecutorAlgebricoReferencia(e.base), est


@pytest.mark.parametrize("C,smin,smax", [(10.0, 0.0, 1.0), (20.0, 0.1, 0.9), (1000.0, 0.0, 1.0)])
def test_b01_executor_3c0_projeta_so_o_artefato(C, smin, smax):
    lo, hi = smin * C, smax * C
    for e0, pc, pd in ((hi, 0.0, -math.ulp(hi)), (lo, 0.0, math.ulp(lo) if lo else 5e-324)):
        ex, est = _executor(C, smin, smax, e0)
        p = ex.avancar(est, {f"{F.BESS}|P_c": pc, f"{F.BESS}|P_d": pd, f"{F.DEM}|ell": 0.0},
                       {f"{F.DEM}|potencia": pd - pc}, 3600)
        assert p.exequivel and p.estado_final.bateria(F.BESS).energia_kWh == e0
        assert [c.codigo for c in p.constatacoes] == ["projecao_numerica_limite_energia"]
    # violação REAL > tolE ⇒ inexequível (sem recorte); entre ε_num e tolE ⇒ aceita SEM projeção (D07)
    ex, est = _executor(C, smin, smax, hi)
    p = ex.avancar(est, {f"{F.BESS}|P_c": 0.0, f"{F.BESS}|P_d": -1e-4, f"{F.DEM}|ell": 0.0},
                   {f"{F.DEM}|potencia": -1e-4}, 3600)
    assert not p.exequivel and "estado_fora_dos_limites" in {c.codigo for c in p.constatacoes}
    p = ex.avancar(est, {f"{F.BESS}|P_c": 0.0, f"{F.BESS}|P_d": -1e-9, f"{F.DEM}|ell": 0.0},
                   {f"{F.DEM}|potencia": -1e-9}, 3600)
    assert p.exequivel and p.estado_final.bateria(F.BESS).energia_kWh == hi + 1e-9 and p.constatacoes == ()


@lru_cache(maxsize=None)
def _h9(estr, diretorio=None):
    from ems_v2.hierarquia import experimentos as X
    return X.executar(F.h9_pemfc(), estr)


@solver
def test_b01_mesmo_valor_corrigido_na_continuidade_registros_e_auditorias():
    from ems_v2.hierarquia.auditoria import reconstruir_projecoes_energia
    x = _h9("mpc_sem_sinal")                               # perfil 3C-3 ORIGINAL (ControladorMPCConectado)
    r = x.resultado
    pj, c = reconstruir_projecoes_energia(x.modelo, r.registros, 3600)
    assert c == [] and [(p.indice_global, p.limite, p.energia_bruta_kWh, p.correcao_kWh) for p in pj] == [
        (8, "superior", 10.000000000000002, 1.7763568394002505e-15)]
    i = next(j for j, w in enumerate(r.registros) if w.conteudo.janela.k == 8)
    assert r.registros[i].conteudo.estados[-1].bateria(F.BESS).energia_kWh == 10.0          # trajetória da janela
    r0 = next(z for z in r.registros_3c0 if z.execucao_uid == r.registros[i].conteudo.execucao_uid)
    assert r0.estado_final.bateria(F.BESS).energia_kWh == 10.0                              # registro 3C-0
    assert r0.checkpoint_final.estado.bateria(F.BESS).energia_kWh == 10.0                   # checkpoint selado
    assert r.registros[i + 1].conteudo.estados[0].bateria(F.BESS).energia_kWh == 10.0        # continuidade do MPC
    # adulterar o estado transportado (sem projeção) é detectado pela reconstrução
    w = r.registros[i]
    est = list(w.conteudo.estados)
    est[-1] = replace(est[-1], armazenamento=(EstadoArmazenamento(F.BESS, 10.000000000000002),))
    alt = list(r.registros)
    alt[i] = replace(w, conteudo=replace(w.conteudo, estados=tuple(est)))
    assert {k.codigo for k in reconstruir_projecoes_energia(x.modelo, alt, 3600)[1]} == {
        "estado_transportado_fora_da_politica_numerica"}


@solver
def test_b01_retomada_3c3_usa_o_estado_projetado():
    from ems_v2.hierarquia import experimentos as X
    from ems_v2.mpc.orquestrador import executar_missao_simulada
    from ems_v2.rede.persistencia import retomar_controlador_conectado
    cont = _h9("mpc_sem_sinal")
    with tempfile.TemporaryDirectory() as d:
        ctrl, ent, mod, N, m = X.montar(F.h9_pemfc(), "mpc_sem_sinal", diretorio=d)
        executar_missao_simulada(ctrl, ent, max_janelas=9, finalizar=False)
        c2, pt = retomar_controlador_conectado(d, ctrl.cfg, mod, ctrl.provedor, ctrl.resolvedor, ctrl.fontes,
                                               ctrl.cfg_rede, identificadores_verdade=ctrl.id_verdade,
                                               fontes_verdade=ctrl.fontes_verdade)
        assert pt.k == 9 and pt.estado.bateria(F.BESS).energia_kWh == 10.0
        r2 = executar_missao_simulada(c2, ent)
    assert r2.registro_missao.impressao_deterministica == cont.resultado.registro_missao.impressao_deterministica


@solver
def test_b01_b10_segundo_artefato_C01_agora_normalizado_pelo_hotfix_b3c4_10():
    """Antes do hotfix B3C4-10 a missão parava em k = 10 (C-01 recusava P_imp = −8,88e-16 do solver); agora o resíduo é
    normalizado na extração (detalhes em test_ems_v2_3c4_b3c4_10.py) e a missão conclui."""
    a = _h9("mpc_sem_sinal")
    assert a.controlador.k == 12 and a.resultado.situacao == "encerrada"


@solver
def test_b01_h9_cinco_estrategias():
    from ems_v2.hierarquia.auditoria import reconstruir_projecoes_energia
    res = {e: _h9(e) for e in ("mpc_sem_sinal", "hier_pwl", "hier_ref_dura", "hier_ref_branda", "mpc_encolhido")}
    for e, x in res.items():
        assert reconstruir_projecoes_energia(x.modelo, x.resultado.registros, 3600)[1] == []
    fim = {e: (x.resultado.situacao, x.controlador.k) for e, x in res.items()}
    assert fim == {e: ("encerrada", 12) for e in res}                    # após B3C4-01 + B3C4-10
    custo = {e: x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R for e, x in res.items()}
    assert custo == pytest.approx({"mpc_sem_sinal": 129.8, "hier_pwl": 129.6, "hier_ref_dura": 129.6,
                                   "hier_ref_branda": 129.6, "mpc_encolhido": 127.6})
    for e in res:
        c = res[e].controlador
        assert c.obrigacoes_pendentes()[0] == {} and [b.energia_kWh for b in c.estado.armazenamento] == [0.0]
        assert c.estado.geracao[0].ligado is True


# ================================================================================================ A02
def _planejador(cert=None, tol_dom=0.05):
    c = F.Cenario3C4("A02", 12, (10.0,) * 12, (0.5,) * 12, bancos=(F.Banco(C=20.0, e0=10.0, pmax=10.0),),
                     pemfc=F.Pemfc())
    ctx = SimpleNamespace(modelo_rede=F.modelo(c), cfg=F.configuracao_mpc("a02", c, 3, 1),
                          cfg_plan=F.configuracao_planejador(H_L=10, tol_dom=tol_dom), k=0, instante_utc=F.INICIO,
                          estado=None, previsao_longa=None, hash_instantaneo="a" * 64, alvos=(),
                          entrada_janela_atual=None, cfg_rede=None)
    p = Planejador3C4(ctx, SimpleNamespace(configuracao_registro=lambda: {"resolvedor": "funcao-sintetica"}))
    p._hashes = lambda: {}
    if cert is not None:
        p._cobertura = cert
    return p


LO, HI = 7.1, 7.9
OFF, ON = (EstadoTerminalGerador(F.FC, False, 0, None),), (EstadoTerminalGerador(F.FC, True, 0, None),)
ALVO = JanelaAlvo(0, 0, 3)


def _fac(on_ok):
    def f(b, modo, en, p_ref):
        if any(x.ligado for x in modo):
            return ("ok", 10.0, 10.0) if on_ok(en[0]) else ("inviavel", None, None)
        return ("ok", 30.0 - 0.1 * en[0], 30.0 - 0.1 * en[0])
    return f


def _cert(on_ok_faixa):
    def c(b, modo, p_ref, faixas):
        (a, z), = faixas
        if not any(x.ligado for x in modo):
            return "factivel", (a,), "cobertura:otimo"
        r = on_ok_faixa(a, z)
        return ("factivel", (r,), "cobertura:otimo") if r is not None else ("inviavel", None, "cobertura:inviavel")
    return c


def test_a02_grade_sem_factivel_sem_certificado_e_indeterminado_e_sinal_indisponivel():
    p = _planejador()
    p.avaliar = _fac(lambda E: LO <= E <= HI)
    assert p._modo_1d(ALVO, ON, {F.FC: 5.0})[0] == "dominio_indeterminado"
    s = p._sinal_pwl(ALVO, None, [OFF, ON], {F.FC: 5.0})
    assert s.qualidade.estado == "indisponivel" and s.qualidade.motivo.startswith("dominio_indeterminado")
    assert [d.estado for d in s.diagnostico_modos] == ["valido", "dominio_indeterminado"]


def test_a02_regiao_estreita_encontrada_pelo_certificado_e_alternativa_mais_barata_incluida():
    p = _planejador(_cert(lambda a, z: None if (z < LO or a > HI) else max(a, LO)))
    p.avaliar = _fac(lambda E: LO <= E <= HI)
    s = p._sinal_pwl(ALVO, None, [OFF, ON], {F.FC: 5.0})
    assert s.qualidade.estado == "valido" and [d.estado for d in s.diagnostico_modos] == ["valido", "valido"]
    on = s.modos[1]
    assert on.dominio_min_kWh[0] >= LO and on.dominio_max_kWh[0] <= HI          # aproximação INTERNA
    assert HI - on.dominio_max_kWh[0] <= 0.05 + 1e-12                            # margem <= tolerância de domínio
    assert all(p_.valor_R == 10.0 for p_ in on.pontos)
    assert any("ponto_factivel_encontrado_fora_da_grade" in c for c in s.diagnostico_modos[1].certificados)


def test_a02_inviavel_so_com_certificado_de_cobertura():
    p = _planejador(_cert(lambda a, z: None))
    p.avaliar = _fac(lambda E: False)
    s = p._sinal_pwl(ALVO, None, [OFF, ON], {F.FC: 5.0})
    assert s.qualidade.estado == "valido" and len(s.modos) == 1
    d = s.diagnostico_modos[1]
    assert d.estado == "inviavel" and d.certificados == ("cobertura:inviavel",) and "TODA a faixa" in d.justificativa


def test_a02_componente_adicional_certificada_torna_indisponivel():
    p = _planejador(_cert(lambda a, z: 1.0 if a <= 1.0 else None))      # componente extra em [0, 2]
    p.avaliar = _fac(lambda E: 0.0 <= E <= 2.0 or 15.0 <= E <= 20.0)    # grade vê só [15, 20] e o 0
    assert p._modo_1d(ALVO, ON, {F.FC: 5.0})[0] == "indisponivel"


def test_a02_sinal_valido_nao_pode_omitir_modo_nao_resolvido():
    d = DiagnosticoModo(ON, "dominio_indeterminado", "sem cobertura", ((0.0, 20.0),), ())
    s = selar_sinal(replace(sinal(), diagnostico_modos=(d,)))
    assert "sinal_valido_com_modo_nao_resolvido" in {c.codigo for c in validar_sinal(s)}


@solver
def test_a02_certificado_real_de_cobertura_milp():
    from ems_v2.hierarquia.contrato import EntradaHierarquica3C4
    from ems_v2.milp.config import CONFIG_ANALITICA
    from ems_v2.milp.solver_3c4 import resolver_cobertura_3c4
    from test_ems_v2_3c4_apoio import entrada4

    def e4(K):
        return entrada4(entrada(K, imp=(0.0,) * K), F.termo_longo())        # PCC sem importação: só o banco
    assert resolver_cobertura_3c4(e4(3), CONFIG_ANALITICA, {F.BESS: (0.0, 20.0)})["classificacao"] == "inviavel"
    r = resolver_cobertura_3c4(e4(2), CONFIG_ANALITICA, {F.BESS: (0.0, 20.0)})
    assert r["classificacao"] == "otimo" and r["energias"][F.BESS] == pytest.approx(20.0)
    assert resolver_cobertura_3c4(e4(2), CONFIG_ANALITICA, {F.BESS: (0.0, 15.0)})["classificacao"] == "inviavel"
    _ = EntradaHierarquica3C4


@solver
@pytest.mark.parametrize("cen", ["h7_limite_importacao", "h8_indisponibilidade_pcc"])
def test_a02_h7_h8_exclusao_do_dominio_certificada_e_custos_mantidos(cen):
    from ems_v2.hierarquia import experimentos as X
    x = X.executar(getattr(F, cen)(), "hier_pwl")
    assert x.resultado.situacao == "encerrada"
    assert x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R == pytest.approx(50.2)
    certs = [c for co in x.controlador.coordenacoes if co.sinal is not None for d in co.sinal.diagnostico_modos
             for c in d.certificados]
    assert any(":inviavel/provenInfeasible" in c for c in certs)          # prova do B&B do HiGHS


# ================================================================================================ A01
@lru_cache(maxsize=None)
def _h2():
    from ems_v2.hierarquia import experimentos as X
    return X.executar(F.h2_pico_futuro(), "hier_pwl")


def _aud(x, rh, **kw):
    from ems_v2.hierarquia.auditoria import auditar_missao_hierarquica
    r, c = x.resultado, x.controlador
    a = dict(registros_3c0=r.registros_3c0, anexos=r.anexos_3c3, registro_rede=r.registro_rede,
             coordenacoes=r.coordenacoes, registro_hierarquico=rh, verdade=x.entorno._verdade)
    a.update(kw)
    return auditar_missao_hierarquica(r.registro_missao, r.registros, r.livro, x.modelo, c.cfg_rede, c.cfg_plan, **a)


ALTERACOES = {
    "contagens": lambda rh: dict(contagens={**rh.contagens, "valido": rh.contagens["valido"] - 1,
                                            "degradado_sem_valor_futuro": 1}),
    "energias_finais_kWh": lambda rh: dict(energias_finais_kWh={F.BESS: 7.5}),
    "valoracao_terminal_declarada_R": lambda rh: dict(valoracao_terminal_declarada_R=-12.0),
    "hash_configuracao_rede": lambda rh: dict(hash_configuracao_rede="0" * 64),
    "hash_modelo_rede": lambda rh: dict(hash_modelo_rede="1" * 64),
    "hash_configuracao_planejador": lambda rh: dict(hash_configuracao_planejador="2" * 64),
    "missao_uid": lambda rh: dict(missao_uid="f" * 32),
    "tempos_negativo": lambda rh: dict(tempos_planejador_s={**rh.tempos_planejador_s, "total_s": -1.0}),
    "tempos_inflado": lambda rh: dict(tempos_planejador_s={**rh.tempos_planejador_s, "total_s": 1.0e6}),
    "tempos_chave_extra": lambda rh: dict(tempos_planejador_s={**rh.tempos_planejador_s, "solver_s": 0.1}),
    "contagens_tipo": lambda rh: dict(contagens={**rh.contagens, "valido": float(rh.contagens["valido"])}),
}


@solver
def test_a01_missao_valida_aceita():
    x = _h2()
    a = _aud(x, x.resultado.registro_hierarquico)
    assert a.aceito and a.verificacoes["registro_hierarquico"] and a.verificacoes["projecoes_numericas"]


@solver
@pytest.mark.parametrize("campo", sorted(ALTERACOES))
def test_a01_registro_final_alterado_e_reselado_e_rejeitado(campo):
    from ems_v2.mpc.registro import selar
    x = _h2()
    rh = x.resultado.registro_hierarquico
    a = _aud(x, selar(replace(rh, **ALTERACOES[campo](rh))))
    assert not a.aceito and not a.verificacoes["registro_hierarquico"]
    assert a.verificacoes["integral_3c3"] and a.verificacoes["hierarquica"]    # balanços/custos continuam corretos


@solver
def test_a01_tempo_nao_finito_sem_reselo_rejeitado_sem_excecao():
    x = _h2()
    rh = x.resultado.registro_hierarquico
    a = _aud(x, replace(rh, tempos_planejador_s={**rh.tempos_planejador_s, "cauda_s": float("inf")}))
    assert not a.aceito and {"registro_hierarquico_adulterado", "tempos_planejador_invalidos"} <= a.codigos()


@solver
def test_a01_objetos_de_configuracao_obrigatorios_e_tempos_apos_retomada():
    from ems_v2.hierarquia import experimentos as X
    from ems_v2.hierarquia.auditoria import retomar_controlador_hierarquico
    from ems_v2.hierarquia.mpc import tempos_planejador_de, verificar_registro_hierarquico
    from ems_v2.mpc.orquestrador import executar_missao_simulada
    x = _h2()
    r = x.resultado
    c = verificar_registro_hierarquico(r.registro_hierarquico, r.registro_missao, r.registro_rede, r.coordenacoes)
    assert "auditoria_integral_incompleta" in {k.codigo for k in c}
    with tempfile.TemporaryDirectory() as d:
        ctrl, ent, mod, N, m = X.montar(F.h2_pico_futuro(), "hier_pwl", nome="a01-ret", diretorio=d)
        executar_missao_simulada(ctrl, ent, max_janelas=4, finalizar=False)
        c2, _ = retomar_controlador_hierarquico(d, ctrl.cfg, mod, ctrl.provedor, ctrl.resolvedor, ctrl.fontes,
                                                ctrl.cfg_rede, ctrl.cfg_plan, ctrl.res_plan,
                                                identificadores_verdade=ctrl.id_verdade,
                                                fontes_verdade=ctrl.fontes_verdade)
        r2 = executar_missao_simulada(c2, ent)
    assert r2.registro_hierarquico.tempos_planejador_s == tempos_planejador_de(r2.coordenacoes)
    xr = SimpleNamespace(resultado=r2, controlador=c2, modelo=mod, entorno=ent)
    assert _aud(xr, r2.registro_hierarquico).aceito
