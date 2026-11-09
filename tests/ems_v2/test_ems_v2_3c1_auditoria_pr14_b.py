"""Segunda auditoria do PR #14 (base ``20243aa``) — correções B-01 e B-02.

* B-01: estados POR UNIDADE × condição AGREGADA do registro no cenário (``unidades_ligadas``, estado discreto,
  potência do registro): contradição ⇒ erro estruturado ANTES de aceitar a projeção; nada é inferido nem distribuído.
* B-02: a declaração de commitment fica vinculada ao instantâneo que a sustenta (incarnação, revisão e impressões do
  inventário; versão e impressão do cenário) e a evidência da execução 3C-1 (anexo selado ao registro 3C-0) conserva
  as fontes de disponibilidade COMPLETAS, recalculáveis e ligadas por hash ao registro.
Sintético/algébrico.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ems_v2_3c1_auditoria_pr14 import (_cenario, _cu, _decl, _inventario, _montar, _plano_pemfc,  # noqa: E402
                                            _real_pemfc, est)

from ems_v2 import fixtures_3c0 as F0  # noqa: E402
from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.fixtures import proc  # noqa: E402
from ems_v2.ponte import canonico, registro as RG  # noqa: E402
from ems_v2.ponte.compromisso import (FonteDisponibilidadeExecucao as FD, declaracao_de_json,  # noqa: E402
                                      hash_declaracao, montar_entrada_3c1, vinculo_do_instantaneo)

pytestmark = pytest.mark.synthetic_algebraic


def _cods(r):
    return {c.codigo for c in r[1]}


# =============================================================================== B-01
def test_b01_exemplo_da_auditoria_uma_ligada_no_cenario_e_duas_ON_declaradas():
    r = _montar([_cu("syn-ter1#1", "em_operacao", 5.0), _cu("syn-ter1#2", "em_operacao", 5.0)], ligadas=1)
    assert r[0] is None and "unidades_ligadas_incoerente" in _cods(r)
    assert r[2].entrada is None                       # rejeitado ANTES da projeção (nenhuma entrada base montada)


@pytest.mark.parametrize("ligadas,agregado,un,ok", [
    (1, 10.0, [("em_operacao", 10.0), ("desligada", 0.0)], True),     # coerente
    (2, 13.0, [("em_operacao", 7.0), ("em_operacao", 6.0)], True),    # duas ON com potências diferentes, Σ = 13
    (0, 10.0, [("desligada", 0.0), ("desligada", 0.0)], False),       # 0 ON, mas o registro diz 'em_operacao', 10 kW
    (2, 10.0, [("em_operacao", 10.0), ("desligada", 0.0)], False),    # contagem incoerente
    (0, 10.0, [("em_operacao", 10.0), ("desligada", 0.0)], False),
])
def test_b01_contagem_de_unidades_ligadas(ligadas, agregado, un, ok):
    r = _montar([_cu(f"syn-ter1#{i + 1}", e, p) for i, (e, p) in enumerate(un)], ligadas=ligadas, agregado=agregado)
    assert (r[0] is not None) is ok, sorted(_cods(r))


def test_b01_estado_discreto_agregado():
    r = _montar([_cu("syn-ter1#1", "em_operacao", 10.0), _cu("syn-ter1#2", "desligada", 0.0)], estado="desligada")
    assert r[0] is None and "estado_agregado_incoerente" in _cods(r)
    r = _montar([_cu("syn-ter1#1", "desligada", 0.0), _cu("syn-ter1#2", "desligada", 0.0)], ligadas=0,
                agregado=0.0, estado="em_operacao")
    assert r[0] is None and "estado_agregado_incoerente" in _cods(r)
    r = _montar([_cu("syn-ter1#1", "em_operacao", 10.0), _cu("syn-ter1#2", "desligada", 0.0)], estado="em_partida")
    assert r[0] is None and "estado_agregado_incoerente" in _cods(r)
    e3, cs, _ = _montar([_cu("syn-ter1#1", "desligada", 0.0), _cu("syn-ter1#2", "desligada", 0.0)], ligadas=0,
                        agregado=0.0, estado="desligada")
    assert e3 is not None


def test_b01_potencia_agregada_soma_e_tolerancia():
    un = lambda p1: [_cu("syn-ter1#1", "em_operacao", p1), _cu("syn-ter1#2", "desligada", 0.0)]  # noqa: E731
    r = _montar(un(25.0), agregado=10.0)
    assert r[0] is None and "potencia_agregada_incoerente" in _cods(r)
    r = _montar(un(10.0 + 1e-3), agregado=10.0)                                     # acima da tolerância D07
    assert r[0] is None and "potencia_agregada_incoerente" in _cods(r)
    assert _montar(un(10.0 + 1e-7), agregado=10.0)[0] is not None                  # dentro da tolerância provisória
    assert _montar(un(10.0), agregado=None)[0] is not None                         # agregado não declarado: nada inferido


def test_b01_declaracao_parcial_nao_reparte_potencia():
    # só #1 declarada: ON ≤ k e Σ ≤ agregado são conferidos; #2 (k = 1 já ocupado por #1) continua sem estado próprio
    r = _montar([_cu("syn-ter1#1", "em_operacao", 10.0)], ligadas=1)
    assert r[0] is None and "estado_por_unidade_nao_declarado" in _cods(r)
    assert "unidades_ligadas_incoerente" not in _cods(r) and "potencia_agregada_incoerente" not in _cods(r)
    r = _montar([_cu("syn-ter1#1", "em_operacao", 15.0)], ligadas=1)               # parcial já excede o agregado
    assert r[0] is None and "potencia_agregada_incoerente" in _cods(r)
    r = _montar([_cu("syn-ter1#1", "desligada", 0.0), ], ligadas=2)                 # OFF > q − k
    assert r[0] is None and "unidades_ligadas_incoerente" in _cods(r)


# =============================================================================== B-02 (vínculo)
def test_b02_declaracao_obsoleta_em_nova_versao_do_cenario_bloqueada():
    un = [_cu("syn-ter1#1", "em_operacao", 10.0), _cu("syn-ter1#2", "desligada", 0.0)]
    inv = _inventario(2)
    cen = _cenario(inv, 2)
    cen_v2 = dataclasses.replace(cen, versao_cenario=2, impressao_cenario=F0.h64("cenario-v2"))
    r = _montar(un, cen_aplicado=cen_v2)
    assert r[0] is None and "declaracao_de_outra_versao_do_cenario" in _cods(r)
    mesma_v_outra_imp = dataclasses.replace(cen, impressao_cenario=F0.h64("adulterado"))
    assert "declaracao_de_outra_versao_do_cenario" in _cods(_montar(un, cen_aplicado=mesma_v_outra_imp))


@pytest.mark.parametrize("campo,valor,cod", [
    ("revisao_config", 2, "declaracao_de_outra_revisao_do_inventario"),
    ("impressao_config", F0.h64("cfg-2"), "declaracao_de_outra_revisao_do_inventario"),
    ("impressao_inventario", F0.h64("inv-2"), "declaracao_de_outra_revisao_do_inventario"),
    ("incarnacao", "inc-outra", "declaracao_de_outra_incarnacao"),
])
def test_b02_declaracao_de_outra_revisao_ou_incarnacao_bloqueada(campo, valor, cod):
    un = [_cu("syn-ter1#1", "em_operacao", 10.0), _cu("syn-ter1#2", "desligada", 0.0)]
    inv = _inventario(2)
    inv2 = dataclasses.replace(inv, identidade=dataclasses.replace(inv.identidade, **{campo: valor}))
    r = _montar(un, inv_aplicado=inv2)
    assert r[0] is None and cod in _cods(r)


def test_b02_vinculo_correto_aceito_e_hash_na_procedencia_da_entrada():
    un = [_cu("syn-ter1#1", "em_operacao", 10.0), _cu("syn-ter1#2", "desligada", 0.0)]
    inv = _inventario(2)
    cen = _cenario(inv, 2)
    d = _decl(un, vinculo_do_instantaneo(inv, cen))
    e3, cs, _ = montar_entrada_3c1(inv, cen, F0.previsao(), F0.definicao(), F0.politicas(), d, contexto="ensaio")
    assert e3 is not None and e3.procedencia.sha256 == hash_declaracao(d)
    assert declaracao_de_json(canonico.json_canonico(d)) == d                    # conteúdo reconstruível
    d2 = dataclasses.replace(d, unidades=(un[0], dataclasses.replace(un[1], tempo_no_estado_s=301)))
    assert hash_declaracao(d2) != hash_declaracao(d)


# =============================================================================== B-02 (evidência da disponibilidade)
def _cadeia(fontes, tmp_path, sub):
    pytest.importorskip("pyomo", exc_type=ImportError)
    from ems_v2.ponte.compromisso import contabilidade_realizada_3c1, estado_inicial_3c1, ExecutorAlgebricoCommitment3C1
    from ems_v2.ponte.execucao import executar, hash_plano
    from ems_v2.ponte.registro_3c1 import gravar_anexo_3c1, hashes_para_registro_3c1, montar_anexo_3c1
    e, r, p, pc = _plano_pemfc()
    real = _real_pemfc()
    uid = "0123456789abcdef0123456789abcdef"
    t = executar(p, estado_inicial_3c1(e), ExecutorAlgebricoCommitment3C1(e, fontes), real, execucao_uid=uid)
    cont = contabilidade_realizada_3c1(e, p, t, real)
    h = "0" * 64
    reg = RG.selar_registro(RG.RegistroExecucaoEMS(
        1, uid, "2026-11-09T00:00:00+00:00", RG.ReferenciaOrigem(e.base.microrrede_uid, None, 1, h, h, h,
                                                                 e.base.cenario_uid, 1, h),
        {"ponte": "3C-0", "perfil": "v1.1-3C-1"},
        {"entrada": r.hash_entrada, "plano": hash_plano(p), **hashes_para_registro_3c1(e, fontes)},
        RG.Discretizacao(e.base.malha.inicio_utc, e.base.malha.delta_s, 4, 4, 4),
        RG.ResumoSolver(r.classificacao, r.estado_despacho, r.terminacao, r.objetivo, r.limite_dual, r.gap_abs,
                        r.gap_rel, "{}", canonico.json_canonico(r.ambiente)),
        p, t.estados[0], t.estados[-1], t.situacao, t.checkpoints[-1], cont.indicadores, cont.custo,
        dict(p.custo_objetivo_planejado), RG.valor_futuro_nao_implementado(t.estados[-1].indice_fronteira),
        "exito", "ensaio 3C-1", {}, (), {}))
    an = montar_anexo_3c1(reg, e, p, t, real, fontes, contabilidade=cont)
    d = tmp_path / sub
    return e, p, t, real, reg, an, RG.gravar_registro(d, reg), gravar_anexo_3c1(d, an)


def test_b02_anexo_reconstroi_fontes_estatica_e_observada(tmp_path):
    from ems_v2.ponte.registro_3c1 import ler_anexo_3c1, verificar_anexo_3c1
    fe = {"syn-fc": FD("syn-fc", "estatica_declarada", 1, proc("B02-disp"), "Condição estática declarada do ensaio")}
    e, p, t, real, reg, an, cr, ca = _cadeia(fe, tmp_path, "estatica")
    lido_r, lido_a = RG.ler_registro(cr), ler_anexo_3c1(ca)
    assert verificar_anexo_3c1(lido_a, lido_r) == [] and lido_a == an
    f = lido_a.fontes_disponibilidade[0]
    assert (f.fonte, f.valor, f.procedencia.referencia, f.justificativa) == ("estatica_declarada", 1, "B02-disp",
                                                                             "Condição estática declarada do ensaio")
    # disponibilidade efetiva por passo: estática (1) e o valor observado coincidente (1) registrados
    assert [(x.indice_plano, x.valor, x.fonte, x.observado) for x in lido_a.disponibilidade_efetiva] == [
        (i, 1, "estatica_declarada", 1.0) for i in range(4)]
    assert lido_a.detalhe_h2[0].massa_eventos_kg == pytest.approx(0.003, abs=1e-12)        # K8: detalhe por unidade
    fo = {"syn-fc": FD("syn-fc", "observada")}
    *_, reg_o, an_o, _, _ = _cadeia(fo, tmp_path, "observada")
    assert verificar_anexo_3c1(an_o, reg_o) == [] and an_o.disponibilidade_efetiva[0].fonte == "observada"


def test_b02_mudar_a_declaracao_de_disponibilidade_altera_a_evidencia(tmp_path):
    from ems_v2.ponte.registro_3c1 import hash_fontes_disponibilidade, verificar_anexo_3c1
    f1 = {"syn-fc": FD("syn-fc", "estatica_declarada", 1, proc("B02-a"), "Condição A")}
    f2 = {"syn-fc": FD("syn-fc", "estatica_declarada", 1, proc("B02-b"), "Condição A")}   # só a procedência muda
    f3 = {"syn-fc": FD("syn-fc", "estatica_declarada", 1, proc("B02-a"), "Condição B")}   # só a justificativa muda
    h = {hash_fontes_disponibilidade(x) for x in (f1, f2, f3, {"syn-fc": FD("syn-fc", "observada")})}
    assert len(h) == 4
    *_, reg1, an1, _, _ = _cadeia(f1, tmp_path, "a")
    *_, reg2, an2, _, _ = _cadeia(f2, tmp_path, "b")
    assert reg1.selo != reg2.selo and an1.selo != an2.selo
    assert "anexo_de_outro_registro" in {c.codigo for c in verificar_anexo_3c1(an1, reg2)}
    falso = dataclasses.replace(an1, fontes_disponibilidade=an2.fontes_disponibilidade)
    falso = dataclasses.replace(falso, selo=canonico.sha256(dataclasses.replace(falso, selo="")))   # re-selado
    assert "hash_3c1_divergente" in {c.codigo for c in verificar_anexo_3c1(falso, reg1)}


def test_b02_registro_sem_hashes_3c1_ou_anexo_adulterado_recusados(tmp_path):
    pytest.importorskip("pyomo", exc_type=ImportError)
    from ems_v2.ponte.registro_3c1 import gravar_anexo_3c1, ler_anexo_3c1, montar_anexo_3c1
    fe = {"syn-fc": FD("syn-fc", "estatica_declarada", 1, proc("B02"), "Condição estática")}
    e, p, t, real, reg, an, cr, ca = _cadeia(fe, tmp_path, "x")
    sem = RG.selar_registro(dataclasses.replace(reg, hashes={"entrada": reg.hashes["entrada"]}, selo=""))
    with pytest.raises(ContratoInvalido) as exc:
        montar_anexo_3c1(sem, e, p, t, real, fe)
    assert "registro_sem_hash_3c1" in exc.value.codigos
    ca.write_text(ca.read_text(encoding="utf-8").replace('"valor":1', '"valor":0'), encoding="utf-8")
    with pytest.raises(ContratoInvalido):
        ler_anexo_3c1(ca)
    with pytest.raises(ContratoInvalido):                                   # nunca sobrescreve um anexo existente
        gravar_anexo_3c1(tmp_path / "x", dataclasses.replace(an, eventos_aplicados={}, selo=canonico.sha256(
            dataclasses.replace(an, eventos_aplicados={}, selo=""))))
    _ = est
