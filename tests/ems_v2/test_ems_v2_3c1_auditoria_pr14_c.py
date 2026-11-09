"""Auditoria final do PR #14 (base ``1b953db``) — correção B-03: compromisso criptográfico do CONTEÚDO íntegro do
anexo 3C-1 no registro principal 3C-0.

Cada adulteração altera UM campo do conteúdo do anexo e RE-SELA o anexo deliberadamente (o selo do anexo confere);
a verificação conjunta deve rejeitá-lo porque o conteúdo já não coincide com o compromisso ``anexo_3c1_conteudo``
gravado no registro original (referência confiável). SHA-256 detecta alteração; não é assinatura: quem re-sela
registro E anexo juntos só é detectado contra o registro ORIGINAL conservado (teste explícito abaixo).
"""
from __future__ import annotations

import dataclasses as dc
import sys
from pathlib import Path

import pytest

pytest.importorskip("pyomo", exc_type=ImportError)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ems_v2_3c1_auditoria_pr14 import _cu, _decl, _inventario  # noqa: E402
from test_ems_v2_3c1_auditoria_pr14_b import _cadeia, _cenario  # noqa: E402

from ems_v2.diagnostics import ContratoInvalido  # noqa: E402
from ems_v2.fixtures import proc  # noqa: E402
from ems_v2.ponte import canonico, registro as RG  # noqa: E402
from ems_v2.ponte.compromisso import FonteDisponibilidadeExecucao as FD, vinculo_do_instantaneo  # noqa: E402
from ems_v2.ponte.registro_3c1 import (CHAVE_CONTEUDO, hash_conteudo_anexo_3c1, ler_anexo_3c1,  # noqa: E402
                                       montar_anexo_3c1, selar_anexo_3c1, verificar_anexo_3c1)

pytestmark = pytest.mark.synthetic_algebraic
FE = {"syn-fc": FD("syn-fc", "estatica_declarada", 1, proc("B03"), "Condição estática declarada do ensaio")}


@pytest.fixture()
def evidencia(tmp_path):
    return _cadeia(FE, tmp_path, "b03")


def _cods(a, reg):
    return {c.codigo for c in verificar_anexo_3c1(a, reg)}


def _adulterar(an, **mud):
    """Altera o CONTEÚDO e re-sela o anexo (ataque: o selo do anexo passa a conferir)."""
    return selar_anexo_3c1(dc.replace(an, conteudo=dc.replace(an.conteudo, **mud)))


def test_b03_evidencia_intacta_reproduzida_do_disco(evidencia):
    *_, reg, an, cr, ca = evidencia
    lido_r, lido_a = RG.ler_registro(cr), ler_anexo_3c1(ca)
    assert lido_r == reg and lido_a == an and verificar_anexo_3c1(lido_a, lido_r) == []
    assert lido_r.hashes[CHAVE_CONTEUDO] == hash_conteudo_anexo_3c1(lido_a.conteudo)
    assert lido_a.selo_registro == lido_r.selo
    # o conteúdo comprometido NÃO contém a vinculação nem o selo (dependência circular resolvida)
    assert {"selo", "selo_registro"}.isdisjoint(f.name for f in dc.fields(lido_a.conteudo))


def _d0(an, **mud):
    d = an.conteudo.disponibilidade_efetiva
    return (dc.replace(d[0], **mud),) + d[1:]


def _h0(an, **mud):
    return (dc.replace(an.conteudo.detalhe_h2[0], **mud),)


ADULTERACOES = {
    "disponibilidade_efetiva.valor": lambda an: dict(disponibilidade_efetiva=_d0(an, valor=0)),
    "disponibilidade_efetiva.uid": lambda an: dict(disponibilidade_efetiva=_d0(an, uid="syn-fc#9")),
    "detalhe_h2.uid": lambda an: dict(detalhe_h2=_h0(an, uid="syn-fc#2")),
    "detalhe_h2.massa_continua_kg": lambda an: dict(detalhe_h2=_h0(an, massa_continua_kg=0.02)),
    "detalhe_h2.massa_eventos_kg": lambda an: dict(detalhe_h2=_h0(an, massa_eventos_kg=0.0)),
    "eventos_aplicados.partidas": lambda an: dict(eventos_aplicados={"syn-fc": {"partidas": 2, "paradas": 2}}),
    "detalhe_h2.partidas": lambda an: dict(detalhe_h2=_h0(an, partidas=2, paradas=2)),
    "detalhe_h2.custo_eventos_R": lambda an: dict(detalhe_h2=_h0(an, custo_eventos_R=0.0)),
    "fonte.procedencia": lambda an: dict(fontes_disponibilidade=(dc.replace(
        an.conteudo.fontes_disponibilidade[0], procedencia=proc("B03-outra-procedencia")),)),
    "fonte.justificativa": lambda an: dict(fontes_disponibilidade=(dc.replace(
        an.conteudo.fontes_disponibilidade[0], justificativa="Outra justificativa"),)),
    "disponibilidade_efetiva.indice_plano": lambda an: dict(disponibilidade_efetiva=tuple(
        dc.replace(x, indice_plano=x.indice_plano + 1) for x in an.conteudo.disponibilidade_efetiva)),
    "disponibilidade_efetiva.observado": lambda an: dict(disponibilidade_efetiva=_d0(an, observado=None)),
    "execucao_uid": lambda an: dict(execucao_uid="f" * 32),
}


@pytest.mark.parametrize("nome", sorted(ADULTERACOES))
def test_b03_conteudo_adulterado_e_re_selado_rejeitado(evidencia, nome):
    *_, reg, an, _, _ = evidencia
    falso = _adulterar(an, **ADULTERACOES[nome](an))
    assert falso.selo == canonico.sha256(dc.replace(falso, selo=""))       # o selo do anexo confere (ataque)
    cods = _cods(falso, reg)
    assert "conteudo_anexo_divergente" in cods, (nome, cods)


def test_b03_declaracao_comprometida_e_coerente_com_a_origem(tmp_path):
    un = [_cu("syn-ter1#1", "em_operacao", 10.0), _cu("syn-ter1#2", "desligada", 0.0)]
    inv = _inventario(2)
    v = vinculo_do_instantaneo(inv, _cenario(inv, 2))
    d = _decl(un, v)
    i = v.inventario
    origem = RG.ReferenciaOrigem(i.microrrede_uid, i.incarnacao, i.revisao_config, i.impressao_config,
                                 i.impressao_inventario, "0" * 64, v.cenario_uid, v.versao_cenario, v.impressao_cenario)
    *_, reg, an, _, _ = _cadeia(FE, tmp_path, "decl", declaracao=d, origem=origem)
    assert verificar_anexo_3c1(an, reg) == []
    # procedência da declaração alterada e anexo re-selado ⇒ compromisso e hash da declaração divergentes
    falso = _adulterar(an, declaracao=dc.replace(d, procedencia=proc("B03-outra")))
    assert {"conteudo_anexo_divergente", "hash_3c1_divergente"} <= _cods(falso, reg)
    # declaração de OUTRA origem, registro selado sobre ela: o compromisso confere, mas a coerência com a origem não
    outra = dc.replace(origem, versao_cenario=origem.versao_cenario + 1)
    with pytest.raises(ContratoInvalido) as exc:
        _cadeia(FE, tmp_path, "decl3", declaracao=d, origem=outra)
    assert "anexo_declaracao_de_outra_origem" in exc.value.codigos


def test_b03_integridade_do_registro_verificada_na_comprovacao_conjunta(evidencia):
    *_, reg, an, _, _ = evidencia
    adult = dc.replace(reg, hashes={**reg.hashes, CHAVE_CONTEUDO: "1" * 64})          # sem re-selar
    assert "registro_adulterado" in _cods(an, adult)
    sem = RG.selar_registro(dc.replace(reg, hashes={k: v for k, v in reg.hashes.items() if k != CHAVE_CONTEUDO},
                                       selo=""))
    assert {"registro_sem_compromisso_do_anexo", "anexo_de_outro_registro"} <= _cods(an, sem)


def test_b03_sha256_nao_e_assinatura_re_selar_ambos_so_e_detectado_contra_o_original(evidencia):
    """Limitação declarada: um adversário que re-sela registro E anexo cria um par internamente coerente; só a
    comparação com o registro ORIGINAL (referência confiável conservada) o detecta."""
    *_, reg, an, _, _ = evidencia
    c_falso = dc.replace(an.conteudo, disponibilidade_efetiva=_d0(an, observado=0.5))
    reg_falso = RG.selar_registro(dc.replace(reg, hashes={**reg.hashes, CHAVE_CONTEUDO: hash_conteudo_anexo_3c1(c_falso)},
                                             selo=""))
    an_falso = montar_anexo_3c1(reg_falso, c_falso)
    assert verificar_anexo_3c1(an_falso, reg_falso) == []                # par forjado é coerente entre si
    assert reg_falso.selo != reg.selo                                     # ... mas o registro mudou de selo
    assert {"conteudo_anexo_divergente", "anexo_de_outro_registro"} <= _cods(an_falso, reg)


def test_b03_coerencia_com_metadados_do_registro_mesmo_com_compromisso_valido(evidencia):
    """Conteúdo incoerente com o registro é recusado ao montar, mesmo que o registro o comprometa (montagem honesta
    de dados errados)."""
    *_, reg, an, _, _ = evidencia

    def forjar(**mud):
        c = dc.replace(an.conteudo, **mud)
        r = RG.selar_registro(dc.replace(reg, hashes={**reg.hashes, CHAVE_CONTEUDO: hash_conteudo_anexo_3c1(c)},
                                         selo=""))
        with pytest.raises(ContratoInvalido) as exc:
            montar_anexo_3c1(r, c)
        return exc.value.codigos
    assert "anexo_eventos_incoerentes" in forjar(eventos_aplicados={"syn-fc": {"partidas": 2, "paradas": 0}})
    assert "anexo_h2_incoerente" in forjar(detalhe_h2=_h0(an, custo_eventos_R=0.0))
    assert "anexo_passos_incoerentes" in forjar(disponibilidade_efetiva=an.conteudo.disponibilidade_efetiva[:-1])
    assert "anexo_unidades_incoerentes" in forjar(fontes_disponibilidade=(dc.replace(
        an.conteudo.fontes_disponibilidade[0], uid="syn-fc#2"),))
    assert "anexo_de_outra_entrada" in forjar(hash_entrada_3c1="2" * 64)
