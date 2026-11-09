"""Piso 3C-2 — correções da auditoria independente do PR #15 (commit auditado ``d97f831``).

* **C-01** — integridade temporal do livro K6: um instantâneo I_k nunca depende de um evento cuja recepção declarada é
  posterior a τ_k, QUALQUER que seja a classificação (aceita, rejeitada, duplicata, inválida, fora de sequência);
  recepções não ordenáveis (retroativas ou ilegíveis) vão para a QUARENTENA (append-only, cadeia própria, nunca num
  prefixo causal); a auditoria verifica a propriedade temporal de TODAS as entradas do prefixo.
* **C-02** — retomada verifica INTEGRALMENTE os artefatos persistidos: registro 3C-0 + anexo 3C-1 de cada janela
  executada (selos, ``verificar_anexo_3c1``, identidade, janela, plano, estados, índices, custo) e restaura os
  históricos; janela sem plano não exige artefatos.

Antes da correção (reproduzido em ``d97f831``): um evento REJEITADO com recepção 45 min depois de τ_2 entrava no
prefixo de τ_2 (n = 2, hash dependente dele), o corte τ_2 era selado e a auditoria causal nada detectava; a retomada
aceitava registro 3C-0 eliminado/alterado e anexo eliminado, sem restaurar históricos (0/0). Sintético/algébrico.
"""
from __future__ import annotations

import dataclasses
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from ems_v2 import fixtures_3c2 as F
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.mpc import auditoria as A
from ems_v2.mpc import experimentos as X
from ems_v2.mpc import orquestrador as O
from ems_v2.mpc.observacoes import (LivroObservacoes, Observacao, instantaneo_de_prefixo, genese_livro,
                                    verificar_cadeia_livro)
from ems_v2.mpc.persistencia import (PontoRetomada, comandos_aplicados, nome_retomada, retomar_controlador,
                                     verificar_artefatos_janela)
from ems_v2.mpc.registro import selar
from ems_v2.ponte.canonico import de_json, json_canonico, sha256

from mpc_util import ResolvedorRegraAnalitica  # noqa: E402

pytestmark = pytest.mark.synthetic_algebraic
T0 = datetime.fromisoformat(F.INICIO)
D = timedelta(minutes=15)
MG = "syn-microrrede-fixture"
NS = dict(K=6, N=3, m=2, L=[10.0] * 6, pv_prev=[5, 5, 15, 15, 5, 5], pv_real=[5, 6, 16, 16, 7, 6], tipo="correcao",
          modelo_kw={"com_fc": False})


def t(i, s=0):
    return (T0 + i * D + timedelta(seconds=s)).isoformat()


def obs(ev, g, rec, *, seq, mg=MG, uid=F.DEM, valor=30.0):
    return Observacao(ev, "c", seq, mg, uid, "potencia", "kW", t(g), t(g + 1), valor, rec, F.proc("pr15"))


def livro():
    return LivroObservacoes(F.missao_uid("pr15"), MG, {F.DEM: ("potencia",)})


# ======================================================================================== C-01
EVENTOS_FUTUROS = {     # classificação → evento com recepção DEPOIS de τ_2 (após um original válido "ok" seq 0)
    "rejeitada_outra_microrrede": lambda: obs("f", 2, t(3, 600), seq=1, mg="syn-outra"),
    "rejeitada_recurso_desconhecido": lambda: obs("f", 2, t(3, 600), seq=1, uid="syn-x"),
    "rejeitada_invalida": lambda: obs("f", 2, t(3, 600), seq=1, valor=-1.0),
    "rejeitada_conflito_evento_uid": lambda: obs("ok", 0, t(3, 600), seq=1),
    "rejeitada_conflito_sequencia": lambda: obs("f", 2, t(3, 600), seq=0),
    "duplicata_semantica": lambda: obs("f", 0, t(3, 600), seq=1),
    "aceita": lambda: obs("f", 2, t(3, 600), seq=1),
    "aceita_fora_de_sequencia": lambda: obs("g", 2, t(3, 600), seq=1),          # original "ok" com seq 5
}


@pytest.mark.parametrize("cl", sorted(EVENTOS_FUTUROS))
def test_c01_evento_futuro_de_qualquer_classificacao_nunca_entra_no_instantaneo(cl):
    base = livro()
    base.registrar(obs("ok", 0, t(1), seq=0 if cl != "aceita_fora_de_sequencia" else 5))
    lv = livro()
    lv.registrar(obs("ok", 0, t(1), seq=0 if cl != "aceita_fora_de_sequencia" else 5))
    e = lv.registrar(EVENTOS_FUTUROS[cl]())
    assert e.classificacao == cl
    i_base, i = base.instantaneo(t(2)), lv.instantaneo(t(2))
    assert (i.n_entradas, i.hash) == (i_base.n_entradas, i_base.hash) == (1, i_base.hash)   # não depende do futuro
    with pytest.raises(ContratoInvalido) as exc:
        lv.selar_corte(t(2))                                  # o livro já contém recepção posterior a τ_2
    assert "corte_antes_de_recepcao_registrada" in exc.value.codigos
    lv.selar_corte(t(3, 600))                                 # cortes posteriores à marca d'água continuam válidos


def test_c01_eventos_antes_do_corte_de_todas_as_classificacoes_entram_no_prefixo():
    lv = livro()
    for o in (obs("ok", 0, t(1), seq=0), obs("ok", 0, t(1), seq=0), obs("x", 0, t(1, 1), seq=1, mg="syn-outra"),
              obs("y", 1, t(1, 2), seq=1, valor=float("nan")), obs("z", 1, t(2), seq=3), obs("w", 1, t(2), seq=2)):
        lv.registrar(o)
    assert [e.classificacao for e in lv.entradas] == ["aceita", "duplicata_identica", "rejeitada_outra_microrrede",
                                                      "rejeitada_invalida", "aceita", "duplicata_semantica"]
    # retransmissão idêntica DEPOIS de uma recepção posterior: tempo declarado retroativo ⇒ quarentena (C-01)
    assert lv.registrar(obs("ok", 0, t(1), seq=0)).classificacao == "quarentena_recepcao_retroativa"
    lv.selar_corte(t(2))
    assert lv.instantaneo(t(2)).n_entradas == 6 and verificar_cadeia_livro(lv.exportar()) == []


def test_c01_recepcao_retroativa_ou_ilegivel_vai_para_quarentena_e_nunca_muda_o_corte():
    lv = livro()
    lv.registrar(obs("ok", 0, t(1), seq=0))
    lv.selar_corte(t(2))
    i2 = lv.instantaneo(t(2))
    retro = [lv.registrar(o) for o in (obs("r1", 1, t(2), seq=1), obs("r2", 1, t(1, 30), seq=2),
                                       obs("r3", 1, t(2), seq=3, mg="syn-outra"))]
    ileg = lv.registrar(obs("r4", 1, "2026-01-01T00:40:00", seq=4))         # sem fuso: nenhuma hora inventada
    assert [x.classificacao for x in retro] == ["quarentena_recepcao_retroativa"] * 3
    assert ileg.classificacao == "quarentena_recepcao_invalida"
    assert len(lv.entradas) == 1 and len(lv.quarentena) == 4 and lv.instantaneo(t(2)) == i2
    assert [(q.apos_entradas, q.apos_cortes) for q in lv.quarentena] == [(1, 1)] * 4
    novo = lv.registrar(obs("r1", 2, t(3), seq=1))           # quarentena não define identidade nem consome sequência
    assert novo.classificacao == "aceita"
    doc = de_json(type(lv.exportar()), json_canonico(lv.exportar()))
    assert verificar_cadeia_livro(doc) == [] and LivroObservacoes.importar(doc).hash_cadeia_quarentena() == \
        lv.hash_cadeia_quarentena()
    q = list(doc.quarentena)
    q[0] = dataclasses.replace(q[0], observacao=dataclasses.replace(q[0].observacao, valor=99.0))
    assert verificar_cadeia_livro(dataclasses.replace(doc, quarentena=tuple(q)))
    with pytest.raises(ContratoInvalido):
        LivroObservacoes.importar(dataclasses.replace(doc, quarentena=tuple(q)))


def test_c01_fora_de_sequencia_dos_dois_lados_do_corte():
    lv = livro()
    lv.registrar(obs("a", 0, t(1), seq=5))
    assert lv.registrar(obs("b", 0, t(1, 10), seq=3, uid=F.DEM, valor=31.0)).classificacao == "aceita_original_conflitante"
    lv.selar_corte(t(1, 10))
    assert lv.registrar(obs("c", 1, t(1, 5), seq=4)).classificacao == "quarentena_recepcao_retroativa"
    assert lv.registrar(obs("d", 1, t(2), seq=2)).classificacao == "aceita_fora_de_sequencia"
    assert lv.instantaneo(t(1, 10)).n_entradas == 2 and lv.instantaneo(t(2)).n_entradas == 3


def test_c01_auditoria_verifica_a_propriedade_temporal_de_todas_as_entradas_do_prefixo():
    lv = livro()
    lv.registrar(obs("ok", 0, t(1), seq=0))
    lv.registrar(obs("f", 2, t(3, 600), seq=1, mg="syn-outra"))                # REJEITADA, recepção > τ_2
    doc = lv.exportar()
    falso = instantaneo_de_prefixo(doc.missao_uid, MG, t(2), doc.entradas[:2], doc.entradas[1].hash_cadeia)
    reg = SimpleNamespace(conteudo=SimpleNamespace(posicao=0, instante_decisao_utc=t(2), n_entradas_instantaneo=2,
                                                   hash_instantaneo=falso.hash, previsao=None, conciliacoes=(),
                                                   passos=(), confirmacoes=()))
    cfg = SimpleNamespace(malha=F.configuracao("pr15", 8, 4, 2).malha, rotulo_informacao="causal")
    assert "informacao_futura_no_instantaneo" in {c.codigo for c in A._causal(cfg, [reg], doc)}
    ok = SimpleNamespace(conteudo=SimpleNamespace(**{**vars(reg.conteudo), "n_entradas_instantaneo": 1,
                                                     "hash_instantaneo": lv.instantaneo(t(2)).hash}))
    assert A._causal(cfg, [ok], doc) == []
    # corte gravado cujo prefixo contém recepção posterior / livro principal fora de ordem ⇒ cadeia temporal inválida
    assert "corte_inclui_recepcao_posterior" in {c.codigo for c in verificar_cadeia_livro(
        dataclasses.replace(doc, cortes=((2, t(2)),)))}
    assert genese_livro(doc.missao_uid, MG) == LivroObservacoes(doc.missao_uid, MG, {}).hash_cadeia()


def test_c01_controlador_recusa_decidir_com_evento_futuro_no_livro():
    ctrl, ent, _, _ = X.montar("pr15-ctrl", **{**NS, "resolvedor": ResolvedorRegraAnalitica(),
                                               "cfg_kw": {"modo": "preparacao_online"}})
    ctrl.receber([Observacao("futuro", "x", 0, "syn-outra", F.DEM, "potencia", "kW", t(0), t(1), 10.0, t(1),
                             F.proc("pr15"))])                                    # rejeitada, recebida em τ_1 > τ_0
    assert ctrl.decidir() is None and ctrl.classe_falha == "integridade" and ctrl._comandos == []
    assert "corte_antes_de_recepcao_registrada" in str(ctrl.registros[-1].conteudo.constatacoes)


def test_c01_missao_completa_auditada_registra_quarentena(tmp_path):
    from ems_v2.mpc.auditoria import auditar_missao
    ex = X.executar("pr15-q", **{**NS, "resolvedor": ResolvedorRegraAnalitica()})
    r = ex.resultado
    rm = r.registro_missao
    assert rm.conteudo.n_quarentena == 0 and rm.conteudo.hash_cadeia_quarentena == r.livro.hash_cadeia_quarentena()
    assert A.auditar_missao(rm, r.registros, r.livro, ex.modelo, verdade=ex.verdade).aceito
    falso = dataclasses.replace(rm, conteudo=dataclasses.replace(rm.conteudo, n_quarentena=1))
    assert "quarentena_divergente_da_missao" in {c.codigo for c in auditar_missao(falso, r.registros, r.livro,
                                                                                    ex.modelo).constatacoes}


# ======================================================================================== C-02
def _preparar(tmp_path: Path, nome="pr15-ret", janelas=2, **kw):
    d = tmp_path / nome
    ctrl, ent, _, _ = X.montar(nome, **{**NS, "resolvedor": ResolvedorRegraAnalitica(), "diretorio": d, **kw})
    O.executar_missao_simulada(ctrl, ent, max_janelas=janelas, finalizar=False)
    return d, ctrl


def _retomar(d, ctrl, **kw):
    return retomar_controlador(d, ctrl.cfg, ctrl.modelo, ctrl.provedor, ResolvedorRegraAnalitica(), F.fontes(False), **kw)


def _uid(ctrl, p):
    return ctrl.registros[p].conteudo.execucao_uid


def _regravar(caminho: Path, obj):
    caminho.chmod(0o644)
    caminho.write_text(json_canonico(obj), encoding="utf-8")


def _codigos(exc):
    return exc.value.codigos


def test_c02_retomada_intacta_restaura_historicos_completos(tmp_path):
    d, ctrl = _preparar(tmp_path)
    c2, pt = _retomar(d, ctrl)
    assert pt.k == 4 and len(c2.registros_3c0) == len(c2.anexos_3c1) == 2
    assert [x.selo for x in c2.registros_3c0] == [x.selo for x in ctrl.registros_3c0]
    assert [x.selo for x in c2.anexos_3c1] == [x.selo for x in ctrl.anexos_3c1]


@pytest.mark.parametrize("alvo", ["ems3c0", "ems3c1"])
def test_c02_artefato_eliminado_recusa(tmp_path, alvo):
    d, ctrl = _preparar(tmp_path)
    (d / f"{_uid(ctrl, 1)}.{alvo}.json").unlink()
    with pytest.raises(ContratoInvalido) as e:
        _retomar(d, ctrl)
    assert {"registro_3c0_ausente", "anexo_3c1_ausente"} & _codigos(e)


def test_c02_registro_3c0_alterado_com_ou_sem_novo_selo(tmp_path):
    from ems_v2.ponte.registro import RegistroExecucaoEMS
    d, ctrl = _preparar(tmp_path)
    p = d / f"{_uid(ctrl, 0)}.ems3c0.json"
    reg = de_json(RegistroExecucaoEMS, p.read_text(encoding="utf-8"))
    alterado = dataclasses.replace(reg, justificativa_desfecho="adulterado")
    _regravar(p, alterado)                                     # sem novo selo
    with pytest.raises(ContratoInvalido) as e:
        _retomar(d, ctrl)
    assert "registro_3c0_adulterado" in _codigos(e)
    _regravar(p, dataclasses.replace(alterado, selo=sha256(dataclasses.replace(alterado, selo=""))))   # re-selado
    with pytest.raises(ContratoInvalido) as e:
        _retomar(d, ctrl)
    assert {"selo_registro_3c0_divergente", "anexo_3c1_invalido"} <= _codigos(e)


def test_c02_anexo_alterado_e_reselado_recusa(tmp_path):
    from ems_v2.ponte.registro_3c1 import AnexoExecucao3C1, selar_anexo_3c1
    d, ctrl = _preparar(tmp_path)
    p = d / f"{_uid(ctrl, 1)}.ems3c1.json"
    a = de_json(AnexoExecucao3C1, p.read_text(encoding="utf-8"))
    c = a.conteudo
    a2 = selar_anexo_3c1(dataclasses.replace(a, conteudo=dataclasses.replace(c, eventos_aplicados={"syn-x": {
        "partidas": 0, "paradas": 0}})))
    _regravar(p, a2)
    with pytest.raises(ContratoInvalido) as e:
        _retomar(d, ctrl)
    assert {"selo_anexo_3c1_divergente", "anexo_3c1_invalido"} <= _codigos(e)


def test_c02_artefatos_de_outra_execucao_ou_trocados_recusam(tmp_path):
    d, ctrl = _preparar(tmp_path)
    u0, u1 = _uid(ctrl, 0), _uid(ctrl, 1)
    for ext in ("ems3c0", "ems3c1"):                          # troca dos arquivos das janelas 0 e 1
        a, b = d / f"{u0}.{ext}.json", d / f"{u1}.{ext}.json"
        tmp = d / "tmp.json"
        shutil.move(a, tmp), shutil.move(b, a), shutil.move(tmp, b)
    with pytest.raises(ContratoInvalido) as e:
        _retomar(d, ctrl)
    assert {"selo_registro_3c0_divergente", "artefato_de_outra_execucao"} <= _codigos(e)
    d2, ctrl2 = _preparar(tmp_path, "pr15-anexo")
    (d2 / f"{_uid(ctrl2, 1)}.ems3c1.json").unlink()            # anexo de OUTRA execução no lugar
    shutil.copy(d2 / f"{_uid(ctrl2, 0)}.ems3c1.json", d2 / f"{_uid(ctrl2, 1)}.ems3c1.json")
    with pytest.raises(ContratoInvalido) as e:
        _retomar(d2, ctrl2)
    assert {"anexo_3c1_invalido", "selo_anexo_3c1_divergente", "artefato_de_outra_execucao"} <= _codigos(e)


def test_c02_selo_referenciado_incorreto_e_janela_sem_plano_que_referencia_artefato(tmp_path):
    d, ctrl = _preparar(tmp_path)
    r = ctrl.registros[1]
    with pytest.raises(ContratoInvalido) as e:
        verificar_artefatos_janela(d, ctrl.cfg, dataclasses.replace(r, selo_registro_3c0="0" * 64))
    assert "selo_registro_3c0_divergente" in _codigos(e)
    with pytest.raises(ContratoInvalido) as e:
        verificar_artefatos_janela(d, ctrl.cfg, dataclasses.replace(r, conteudo=dataclasses.replace(
            r.conteudo, execucao_uid="f" * 32)))
    assert "execucao_da_janela_indeterminada" in _codigos(e)
    sem = dataclasses.replace(r, conteudo=dataclasses.replace(r.conteudo, hash_plano=None, passos=()))
    with pytest.raises(ContratoInvalido) as e:
        verificar_artefatos_janela(d, ctrl.cfg, sem)
    assert "artefato_referenciado_sem_plano" in _codigos(e)


def test_c02_ponto_de_retomada_com_livro_truncado_e_reselado_recusa(tmp_path):
    d, ctrl = _preparar(tmp_path)
    p = d / nome_retomada(ctrl.cfg.identidade.missao_uid, 1)
    pt = de_json(PontoRetomada, p.read_text(encoding="utf-8"))
    curto = dataclasses.replace(pt.livro, entradas=pt.livro.entradas[:3],
                                cortes=tuple(c for c in pt.livro.cortes if c[0] <= 3))
    _regravar(p, selar(dataclasses.replace(pt, livro=curto)))
    with pytest.raises(ContratoInvalido) as e:
        _retomar(d, ctrl)
    assert "livro_incoerente_com_janelas" in _codigos(e)


def test_c02_retomadas_sucessivas_identicas_a_execucao_continua(tmp_path):
    cont = X.executar("pr15-multi", **{**NS, "resolvedor": ResolvedorRegraAnalitica()}).resultado
    d, ctrl = _preparar(tmp_path, "pr15-multi", janelas=1)
    for _ in range(2):                                         # retoma, executa 1 janela, "interrompe" de novo
        novo, ent, _, _ = X.montar("pr15-multi", **{**NS, "resolvedor": ResolvedorRegraAnalitica()})
        c2, pt = _retomar(d, ctrl)
        ent.reconstituir(comandos_aplicados(pt), O.instante_fronteira(ctrl.cfg.malha, pt.k))
        r = O.executar_missao_simulada(c2, ent, max_janelas=1)
        ctrl = c2
    assert r.registro_missao.impressao_deterministica == cont.registro_missao.impressao_deterministica
    assert len(r.registros_3c0) == len(r.anexos_3c1) == 3 == len(cont.registros_3c0)
    assert [x.execucao_uid for x in r.registros_3c0] == [x.execucao_uid for x in cont.registros_3c0]


def test_c02_janela_sem_plano_nao_exige_artefatos_e_missao_suspensa_retoma(tmp_path):
    from ems_v2.mpc.experimentos import ResolvedorComFalha, resultado_sem_solucao
    d = tmp_path / "pr15-susp"
    ctrl, ent, _, _ = X.montar("pr15-susp", **{**NS, "diretorio": d,
                                               "resolvedor": ResolvedorComFalha(ResolvedorRegraAnalitica(), 1,
                                                                                resultado_sem_solucao),
                                               "cfg_kw": {"falhas": F.politica_falhas(suspender=("falha_solver",))}})
    O.executar_missao_simulada(ctrl, ent, finalizar=False)
    assert ctrl.situacao == "suspensa" and ctrl.registros[-1].conteudo.desfecho == "sem_plano"
    assert ctrl.registros[-1].conteudo.execucao_uid is None
    c2, pt = _retomar(d, ctrl)
    assert pt.situacao == "suspensa" and len(c2.registros_3c0) == 1     # só a janela executada
    c2.retomar_suspensa()
    ent2 = X.montar("pr15-susp", **{**NS, "resolvedor": ResolvedorRegraAnalitica()})[1]
    ent2.reconstituir(comandos_aplicados(pt), O.instante_fronteira(ctrl.cfg.malha, pt.k))
    fim = O.executar_missao_simulada(c2, ent2)
    assert fim.situacao == "encerrada" and len(fim.registros_3c0) == 3 and len(fim.registros) == 4
    _ = json
