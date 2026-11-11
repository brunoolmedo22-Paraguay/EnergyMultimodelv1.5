"""C-3DA2H-01 — certificado B04 verificável no contrato (sem solver, só biblioteca padrão + o contrato).

Dados SINTÉTICOS de teste (função convexa conhecida q = 0,3 + 0,05·P + 0,0004·P² [kg/h], não é PEMFC): verificam que o
contrato RECOMPUTA os critérios, rejeita política não aprovada, certificados adulterados, rótulo sem certificado, hash
sem registro e vértices divergentes — nenhuma curva fica "certificada" por declaração ou presença de hash.
"""
from __future__ import annotations

import math
from dataclasses import replace

import pytest

from ems_v2 import contracts as K
from ems_v2.provenance import Procedencia

pytestmark = pytest.mark.synthetic_algebraic


def q(p: float) -> float:
    return 0.3 + 0.05 * p + 0.0004 * p * p


def _cert(situacao: str = K.SITUACAO_B04_APROVADA, n_vert: int = 9, **pol):
    ps = [10.0 + 40.0 * i / (n_vert - 1) for i in range(n_vert)]
    vs = tuple((p, q(p)) for p in ps)
    val = tuple((10.0 + 40.0 * (k + 0.37) / 250, q(10.0 + 40.0 * (k + 0.37) / 250)) for k in range(250))
    perfil = K.PerfilMassaB04("variavel", 1 / 60, tuple(10.0 + 40.0 * (k % 37) / 36.5 for k in range(600)),
                              tuple(q(10.0 + 40.0 * (k % 37) / 36.5) for k in range(600)))
    politica = K.PoliticaB04("b04-teste", situacao, pol.get("erro_rel_max", 0.005), pol.get("erro_abs_max_kg_h", 0.02),
                             pol.get("subestimacao_rel_max", 0.001), pol.get("erro_massa_temporal_rel_max", 0.002),
                             pol.get("pontos_validacao_min", 200))
    return K.CertificadoB04(1, politica, vs, val, (perfil,), "a" * 64,
                            Procedencia("sintetico", "teste C-3DA2H-01", "curva convexa conhecida"))


def _curva(cert, classificacao="real_certificada_b04", sha=None):
    proc = Procedencia("sintetico", "teste C-3DA2H-01", "curva", sha256=sha)
    return K.CurvaPWL(cert.vertices, classificacao, proc)


def _codigos(cs):
    return {c.codigo for c in cs}


def test_certificado_valido_e_registrado_habilita_a_curva():
    c = _cert()
    h, cs = K.registrar_certificado_b04(c)
    assert cs == [] and K.certificado_b04_registrado(h) is c
    assert not [x for x in K.validar_curva(_curva(c, sha=h), 10.0, 50.0, "g") if x.severidade != "aviso"]


def test_politica_nao_aprovada_nao_registra():
    c = _cert(situacao="proposta_congelada_pendente_de_aprovacao")
    h, cs = K.registrar_certificado_b04(c)
    assert "politica_b04_nao_aprovada" in _codigos(cs) and K.certificado_b04_registrado(h) is None
    assert "pwl_certificado_b04_nao_verificado" in _codigos(K.validar_curva(_curva(c, sha=h), 10.0, 50.0, "g"))


def test_rotulo_sem_certificado_e_hash_sem_registro_nao_bastam():
    c = _cert()
    assert "pwl_certificado_b04_nao_verificado" in _codigos(K.validar_curva(_curva(c, sha=None), 10.0, 50.0, "g"))
    falso = K.hash_certificado_b04(replace(c, identidade_sha256="b" * 64))     # hash "plausível", nunca registrado
    assert "pwl_certificado_b04_nao_verificado" in _codigos(K.validar_curva(_curva(c, sha=falso), 10.0, 50.0, "g"))


def test_criterios_sao_recomputados_dos_dados():
    # validação adulterada (modelo "declarado" mais baixo) ⇒ erro relativo e subestimação reprovados
    c = _cert()
    val = tuple((p, v * 0.98) for p, v in c.validacao)
    _h, cs = K.registrar_certificado_b04(replace(c, validacao=val))
    assert "b04_criterio_reprovado" in _codigos(cs)
    # PWL grossa (2 vértices) numa curva convexa ⇒ erro acima do limiar
    _h, cs = K.registrar_certificado_b04(_cert(n_vert=2))
    assert "b04_criterio_reprovado" in _codigos(cs)
    # massa temporal adulterada
    pf = c.perfis[0]
    _h, cs = K.registrar_certificado_b04(replace(c, perfis=(replace(pf, vazoes_modelo_kg_h=tuple(
        v * 1.01 for v in pf.vazoes_modelo_kg_h)),)))
    assert any(x.codigo == "b04_criterio_reprovado" and "perfis" in x.caminho for x in cs)


@pytest.mark.parametrize("mutar, codigo", [
    (lambda c: replace(c, validacao=c.validacao[:50]), "b04_pontos_validacao_insuficientes"),
    (lambda c: replace(c, validacao=c.validacao + ((c.vertices[3][0], c.vertices[3][1]),)), "b04_validacao_invalida"),
    (lambda c: replace(c, validacao=c.validacao + ((60.0, 4.0),)), "b04_validacao_invalida"),
    (lambda c: replace(c, perfis=()), "b04_sem_perfil_temporal"),
    (lambda c: replace(c, vertices=((0.0, 0.0),) + c.vertices), "vertices_b04_invalidos"),
    (lambda c: replace(c, identidade_sha256="x"), "identidade_b04_invalida"),
    (lambda c: replace(c, politica=replace(c.politica, erro_rel_max=math.inf)), "politica_b04_invalida"),
])
def test_certificado_incoerente_e_rejeitado(mutar, codigo):
    _h, cs = K.registrar_certificado_b04(mutar(_cert()))
    assert codigo in _codigos(cs)


def test_vertices_da_curva_diferentes_dos_certificados_sao_rejeitados():
    c = _cert()
    h, cs = K.registrar_certificado_b04(c)
    assert cs == []
    vs = list(c.vertices)
    vs[4] = (vs[4][0], vs[4][1] * 1.001)
    curva = K.CurvaPWL(tuple(vs), "real_certificada_b04", Procedencia("sintetico", "t", "c", sha256=h))
    assert "pwl_certificado_b04_divergente" in _codigos(K.validar_curva(curva, 10.0, 50.0, "g"))


def test_classificacoes_anteriores_inalteradas():
    c = _cert()
    assert "pwl_real_requer_certificacao_estatica" in _codigos(K.validar_curva(_curva(c, "real"), 10.0, 50.0, "g"))
    assert not [x for x in K.validar_curva(_curva(c, "sintetica_exata"), 10.0, 50.0, "g") if x.severidade != "aviso"]


def test_certificado_serializa_e_reconstroi_estritamente():
    c = _cert()
    d = K.para_dict(c)
    r = K.de_dict(K.CertificadoB04, d, "CertificadoB04")
    assert r == c and K.hash_certificado_b04(r) == K.hash_certificado_b04(c)
