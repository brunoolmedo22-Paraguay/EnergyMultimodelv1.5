"""Piso 3C-0 — compatibilidade da ponte com o núcleo MILP 3B-P (HiGHS real).

Cadeia de ENSAIO (dados sintéticos rotulados): preflight → entrada canônica 3A → ``resolver`` 3B-P → plano →
execução pelo dublê algébrico → registro selado. Prova continuidade contratual; NÃO é validação física nem MPC.
Sem Pyomo/HiGHS os testes são pulados explicitamente (como os demais testes 3B-P).
"""
from __future__ import annotations

import dataclasses
import time

import pytest

pytest.importorskip("pyomo")
pytest.importorskip("highspy")

from ems_v2 import fixtures_3c0 as F  # noqa: E402
from ems_v2.contracts import hash_entrada  # noqa: E402
from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.milp.config import CONFIG_ANALITICA, configuracao_registro  # noqa: E402
from ems_v2.milp.solver import resolver  # noqa: E402
from ems_v2.ponte import canonico, execucao as EX, instrumentacao as IN, registro as RG  # noqa: E402
from ems_v2.ponte.cenario import hash_previsao, hash_realizacao  # noqa: E402
from ems_v2.ponte.inventario import hash_inventario  # noqa: E402
from ems_v2.ponte.preflight import hash_preflight, preflight_ems_v2  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
UID = "fedcba9876543210fedcba9876543210"


def _cadeia(real, prev=None):
    cr = IN.Cronometro()
    inv = F.inventario()
    cen, dt, pol = F.cenario(inv), F.definicao(), F.politicas()
    prev = prev or F.previsao(oraculo=True)
    with cr.fase("preparacao_dados"):
        rel, proj = preflight_ems_v2(inv, cen, dt, prev, real, pol, contexto="ensaio", compromisso=F.COMPROMISSO)
    assert rel.aceito, rel.texto()
    with cr.fase("resolucao"):
        res = resolver(proj.entrada, CONFIG_ANALITICA, F.COMPROMISSO)
    cr.registrar("construcao_modelo", res.tempos_s.get("construcao_s"))
    with cr.fase("processamento_resultado"):
        plano = EX.plano_de_resultado(res, proj.entrada)
    e0 = EX.estado_inicial_de_entrada(proj.entrada, memoria={"syn-ter1": 3600})
    with cr.fase("avanco_simulacao"):
        traj = EX.executar(plano, e0, EX.ExecutorAlgebricoReferencia(proj.entrada), real, execucao_uid=UID)
    return inv, cen, dt, prev, rel, proj, res, plano, traj, cr


def test_cadeia_completa_com_milp_real(tmp_path):
    real = F.realizacao()
    inv, cen, dt, prev, rel, proj, res, plano, traj, cr = _cadeia(real)
    assert res.classificacao == "otimo" and res.estado_despacho == "aceito_otimo" and res.aceito
    assert res.hash_entrada == hash_entrada(proj.entrada) == plano.hash_entrada
    assert res.microrrede_uid == "syn-mg-a" and res.cenario_uid == cen.cenario_uid
    assert plano.consigna("syn-bat1", "P_d").valores[2] == pytest.approx(10.0, abs=1e-6)     # analítico
    assert traj.situacao == "concluida" and len(traj.estados) == plano.N + 1
    assert max(abs(d.desvio) for d in traj.desvios) <= 1e-9                                 # oráculo declarado
    ind, custo = RG.indicadores_e_custo(proj.entrada, plano, traj, real)
    assert custo.total_R == pytest.approx(res.custos_modelo["total"], abs=1e-9) == pytest.approx(0.025, abs=1e-9)
    desf, just = IN.classificar_desfecho(res)
    with cr.fase("persistencia"):
        reg = RG.selar_registro(RG.RegistroExecucaoEMS(
            1, UID, "2026-11-08T00:00:00+00:00",
            RG.ReferenciaOrigem(inv.identidade.uid, inv.identidade.incarnacao, inv.identidade.revisao_config,
                                inv.identidade.impressao_config, inv.identidade.impressao_inventario, hash_inventario(inv),
                                cen.cenario_uid, cen.versao_cenario, cen.impressao_cenario),
            {"ponte": "3C-0", "motor": res.motor_id, "formulacao": res.versao_formulacao},
            {"entrada": res.hash_entrada, "plano": EX.hash_plano(plano), "preflight": hash_preflight(rel),
             "previsao": hash_previsao(prev), "realizacao": hash_realizacao(real),
             **proj.hashes},
            RG.Discretizacao(dt.malha.inicio_utc, dt.malha.delta_s, dt.malha.N, dt.malha.intervalos_reotimizacao,
                             dt.malha.intervalos_missao),
            RG.ResumoSolver(res.classificacao, res.estado_despacho, res.terminacao, res.objetivo, res.limite_dual,
                            res.gap_abs, res.gap_rel, canonico.json_canonico(configuracao_registro(CONFIG_ANALITICA)),
                            canonico.json_canonico(res.ambiente)),
            plano, traj.estados[0], traj.estados[-1], traj.situacao, traj.checkpoints[-1], ind, custo,
            dict(plano.custo_objetivo_planejado), RG.valor_futuro_nao_implementado(traj.estados[-1].indice_fronteira),
            desf, just, dict(cr.duracoes_s), tuple(res.constatacoes) + tuple(traj.constatacoes),
            {"semente_highs": str(CONFIG_ANALITICA.semente), "hash_compromisso": res.hash_compromisso or ""}))
        caminho = RG.gravar_registro(tmp_path, reg)
    assert desf == "exito" and RG.ler_registro(caminho) == reg
    assert set(cr.duracoes_s) >= {"preparacao_dados", "construcao_modelo", "resolucao", "processamento_resultado",
                                  "avanco_simulacao"}
    assert reg.valor_futuro.contabilizado_como_custo is False and reg.valor_futuro.valor_R is None


def test_reproducao_deterministica_do_plano_e_da_trajetoria():
    a = _cadeia(F.realizacao())
    b = _cadeia(F.realizacao())
    assert EX.hash_plano(a[7]) == EX.hash_plano(b[7])
    assert a[8].checkpoints[-1] == b[8].checkpoints[-1]


def test_erro_de_previsao_interrompe_execucao_e_registra_apenas_o_executado():
    prev = F.previsao()                                         # não é oráculo
    real = F.realizacao(demanda=(30.0, 40.0, 55.0, 20.0), pv=(20.0, 30.0, 10.0, 0.5))
    *_, proj, res, plano, traj, _ = _cadeia(real, prev)
    assert res.aceito and traj.situacao == "interrompida_inexequivel" and traj.cursor_final == 2
    assert "balanco_realizado_violado" in {c.codigo for c in traj.constatacoes}
    ind, custo = RG.indicadores_e_custo(proj.entrada, plano, traj, real)
    assert custo.intervalos == 2 and ind["E_bess_descarga_kWh"] == 0.0


def test_solucao_inviavel_nao_vira_plano():
    inv = F.inventario()
    prev = F.previsao(demanda=(30.0, 40.0, 500.0, 20.0))
    rel, proj = preflight_ems_v2(inv, F.cenario(inv), F.definicao(), prev, None, F.politicas(), contexto="ensaio",
                                 compromisso=F.COMPROMISSO)
    assert proj.aceito
    res = resolver(proj.entrada, CONFIG_ANALITICA, F.COMPROMISSO)
    assert res.classificacao in ("inviavel", "inviavel_ou_ilimitado") and not res.aceito
    assert IN.classificar_desfecho(res)[0] == "inviavel"
    with pytest.raises(ContratoInvalido) as ei:
        EX.plano_de_resultado(res, proj.entrada)
    assert "plano_de_solucao_nao_aceita" in ei.value.codigos


def test_tempos_medidos_sao_registrados_sem_meta_de_desempenho():
    amostras = []
    for _ in range(5):
        t0 = time.perf_counter()
        _cadeia(F.realizacao())
        amostras.append(time.perf_counter() - t0)
    e = IN.estatisticas(amostras)
    assert e.n == 5 and e.p95 == e.maximo == max(amostras) and e.p50 <= e.maximo
    assert dataclasses.asdict(e)["definicao"].startswith("percentil de posto mais próximo")
