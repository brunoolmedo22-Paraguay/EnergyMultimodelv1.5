"""C-3DA2H-01 — certificado B04 verificável no contrato (sem solver, só biblioteca padrão + o contrato).

Dados SINTÉTICOS de teste (função convexa conhecida q = 0,3 + 0,05·P + 0,0004·P² [kg/h], não é PEMFC): verificam que o
contrato RECOMPUTA os critérios, rejeita política não aprovada, certificados adulterados, rótulo sem certificado, hash
sem registro e vértices divergentes — nenhuma curva fica "certificada" por declaração ou presença de hash.

AUTORIDADE (auditoria do PR #23, ponto C): a política sintética ``b04-teste`` só é reconhecida porque ESTE teste a
registra em ``POLITICAS_B04_NUCLEO`` (fixture ``politica_de_teste``); uma política autodeclarada, alterada ou com
situação divergente é rejeitada pelo núcleo, qualquer que seja o campo ``situacao`` do certificado.
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


def _registrar_politica(monkeypatch, situacao=K.SITUACAO_B04_APROVADA, **pol):
    """Registro da política SINTÉTICA no núcleo — aprovação SIMULADA, restaurada pelo ``monkeypatch`` ao fim do teste."""
    p = _cert(situacao, **pol).politica
    monkeypatch.setitem(K.POLITICAS_B04_NUCLEO, K.hash_politica_b04(p),
                        {"versao": p.versao, "situacao": situacao, "congelada_em": "teste"})


def sem_registro_de_politica(f):
    """O teste roda com o registro de políticas do núcleo INTACTO (sem a política sintética aprovada)."""
    f.sem_registro_de_politica = True
    return f


@pytest.fixture(autouse=True)
def politica_de_teste(request, monkeypatch):
    if not getattr(request.function, "sem_registro_de_politica", False):
        _registrar_politica(monkeypatch)


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


def test_politica_nao_aprovada_nao_registra(monkeypatch):
    _registrar_politica(monkeypatch, situacao="proposta_congelada_pendente_de_aprovacao")
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


# ------------------------------------------------------------------ autoridade da política (auditoria PR #23, C)
@sem_registro_de_politica
def test_politica_autodeclarada_aprovada_com_limiares_arbitrarios_e_rejeitada():
    """Um certificado que traz a SUA política 'aprovada_pelo_responsavel' com limiares frouxos não tem autoridade."""
    for c in (_cert(erro_rel_max=1.0, erro_abs_max_kg_h=10.0, subestimacao_rel_max=1.0,
                    erro_massa_temporal_rel_max=1.0, pontos_validacao_min=1), _cert(n_vert=2, erro_rel_max=1.0)):
        h, cs = K.registrar_certificado_b04(c)
        assert h == "" and "politica_b04_desconhecida" in _codigos(cs)
        assert "pwl_certificado_b04_nao_verificado" in _codigos(
            K.validar_curva(_curva(c, sha=K.hash_certificado_b04(c)), 10.0, 50.0, "g"))


@sem_registro_de_politica
def test_politica_congelada_com_limiar_alterado_e_rejeitada():
    (h_pol, reg), = [(h, r) for h, r in K.POLITICAS_B04_NUCLEO.items() if r["versao"] == "b04-proposta-2"]
    base = K.PoliticaB04("b04-proposta-2", reg["situacao"], 0.005, 0.02, 0.001, 0.002, 200)
    assert K.hash_politica_b04(base) == h_pol                       # o conteúdo congelado é exatamente este
    for alterada in (replace(base, erro_rel_max=0.05), replace(base, pontos_validacao_min=20),
                     replace(base, situacao=K.SITUACAO_B04_APROVADA, subestimacao_rel_max=0.5)):
        _h, cs = K.registrar_certificado_b04(replace(_cert(), politica=alterada))
        assert "politica_b04_alterada" in _codigos(cs) and _h == ""


@sem_registro_de_politica
def test_situacao_declarada_no_certificado_diverge_do_nucleo(monkeypatch):
    """A situação do certificado nunca decide: declarar o oposto do núcleo é erro, nos dois sentidos."""
    (h_pol, reg), = [(h, r) for h, r in K.POLITICAS_B04_NUCLEO.items() if r["versao"] == "b04-proposta-2"]
    assert reg["situacao"] == K.SITUACAO_B04_APROVADA                 # estado REAL: aprovada pelo responsável (PR #23)
    pendente = K.PoliticaB04("b04-proposta-2", "proposta_congelada_pendente_de_aprovacao", 0.005, 0.02, 0.001, 0.002, 200)
    h, cs = K.registrar_certificado_b04(replace(_cert(), politica=pendente))
    assert h == "" and "politica_b04_situacao_divergente" in _codigos(cs)
    monkeypatch.setitem(reg, "situacao", "proposta_congelada_pendente_de_aprovacao")      # REVOGAÇÃO simulada
    forjada = K.PoliticaB04("b04-proposta-2", K.SITUACAO_B04_APROVADA, 0.005, 0.02, 0.001, 0.002, 200)
    h, cs = K.registrar_certificado_b04(replace(_cert(), politica=forjada))
    assert h == "" and "politica_b04_situacao_divergente" in _codigos(cs)
    assert K.certificado_b04_registrado(K.hash_certificado_b04(replace(_cert(), politica=forjada))) is None


def test_politica_aprovada_no_nucleo_nao_dispensa_a_verificacao_quantitativa():
    for c in (_cert(n_vert=2), replace(_cert(), validacao=tuple((p, v * 0.98) for p, v in _cert().validacao)),
              replace(_cert(), validacao=_cert().validacao[:150])):
        h, cs = K.registrar_certificado_b04(c)
        assert h == "" and {"b04_criterio_reprovado", "b04_pontos_validacao_insuficientes"} & _codigos(cs)
