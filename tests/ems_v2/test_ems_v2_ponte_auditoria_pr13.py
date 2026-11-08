"""Piso 3C-0 — correções da auditoria independente do PR #13 (H-01..H-04 e condições de C-3C0-01).

Testes CONTRATUAIS: dados sintéticos rotulados e microrredes de TESTE em diretório temporário. Os testes de
concorrência (H-03) usam PROCESSOS e THREADS reais sobre o sistema de arquivos — não são simulações sequenciais.
"""
from __future__ import annotations

import dataclasses
import errno
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from ems_v2 import FORMULACAO_3BP, FORMULACAO_VERSAO, MOTOR_ID
from ems_v2 import fixtures_3c0 as F
from ems_v2.contracts import hash_entrada
from ems_v2.diagnostics import ContratoInvalido
from ems_v2.ponte import canonico, cenario as CN, execucao as EX, preflight as PF, projecao as PJ, registro as RG
from ems_v2.provenance import Procedencia

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]
T2 = "2026-01-01T00:30:00+00:00"          # fronteira τ_2 (Δ = 15 min)


def _cods(cs, sev=None):
    return {c.codigo for c in cs if sev is None or c.severidade == sev}


def _com_serie(conj, uid, grandeza, **mud):
    """Cópia de um conjunto (previsão/realização) com a série ``uid:grandeza`` alterada."""
    novas = tuple(dataclasses.replace(s, serie=dataclasses.replace(s.serie, **mud))
                  if (s.uid, s.grandeza) == (uid, grandeza) else s for s in conj.series)
    return dataclasses.replace(conj, series=novas)


# ======================================================================================== H-01 separação
def test_h01_previsao_independente_identica_e_advertencia_nao_bloqueio():
    dt, p, r = F.definicao(), F.previsao(), F.realizacao()
    assert p.series[0].serie.procedencia != r.series[0].serie.procedencia     # fontes independentes
    cls = {(c.uid, c.categoria) for c in CN.classificar_separacao(p, r, dt)}
    assert cls == {("syn-carga", "coincidente_sem_evidencia"), ("syn-pv1", "coincidente_sem_evidencia")}
    cs = CN.validar_separacao(p, r, dt)
    assert _cods(cs) == {"previsao_coincide_com_realizacao"} and _cods(cs, "erro") == set()
    inv = F.inventario()
    rel, proj = PF.preflight_ems_v2(inv, F.cenario(inv), dt, p, r, F.politicas(), contexto="ensaio",
                                    compromisso=F.COMPROMISSO)
    assert rel.apto_para_otimizacao and "previsao_coincide_com_realizacao" in rel.codigos("advertencia")


def test_h01_series_constantes_identicas_nao_sao_fuga():
    dt = F.definicao()
    p = F.previsao(demanda=(25.0,) * 4, pv=(0.0,) * 4)
    r = F.realizacao(demanda=(25.0,) * 4, pv=(0.0,) * 4)
    cs = CN.validar_separacao(p, r, dt)
    assert _cods(cs, "erro") == set() and _cods(cs, "aviso") == {"previsao_coincide_com_realizacao"}


def test_h01_coincidencia_parcial_e_previsao_independente():
    dt = F.definicao()
    r = F.realizacao(demanda=(30.0, 41.0, 49.0, 21.0), pv=(20.0, 29.0, 10.0, 1.0))      # 1–2 intervalos iguais
    sep = {c.uid: c for c in CN.classificar_separacao(F.previsao(), r, dt)}
    assert sep["syn-carga"].categoria == "independente" and (sep["syn-carga"].intervalos_iguais,
                                                             sep["syn-carga"].intervalos_comparados) == (1, 4)
    assert sep["syn-pv1"].categoria == "independente" and sep["syn-pv1"].intervalos_iguais == 2
    assert CN.validar_separacao(F.previsao(), r, dt) == []


def test_h01_oraculo_explicito_coerente_e_inconsistente():
    dt = F.definicao()
    assert _cods(CN.validar_separacao(F.previsao(oraculo=True), F.realizacao(), dt)) == {"previsao_perfeita_declarada"}
    falso = CN.validar_separacao(F.previsao(oraculo=True), F.realizacao(demanda=(30.0, 45.0, 50.0, 20.0)), dt)
    assert "oraculo_diferente_da_realizacao" in _cods(falso, "erro")
    sem_just = dataclasses.replace(F.previsao(oraculo=True), justificativa_oraculo=" ")
    assert "oraculo_sem_justificativa" in _cods(CN.validar_previsao(sem_just, dt), "erro")


def test_h01_procedencia_compartilhada_e_advertencia_suspeita():
    dt, r = F.definicao(), F.realizacao(demanda=(30.0, 45.0, 50.0, 20.0))
    comum = r.serie("syn-carga", "potencia").serie.procedencia
    p = _com_serie(F.previsao(), "syn-carga", "potencia", procedencia=comum)
    sep = {c.uid: c for c in CN.classificar_separacao(p, r, dt)}
    assert sep["syn-carga"].categoria == "procedencia_compartilhada"
    assert _cods(CN.validar_separacao(p, r, dt), "aviso") >= {"procedencia_compartilhada_suspeita"}
    assert _cods(CN.validar_separacao(p, r, dt), "erro") == set()


def test_h01_evidencia_de_fuga_bloqueia():
    dt, r = F.definicao(), F.realizacao(demanda=(30.0, 45.0, 50.0, 20.0))
    h = canonico.sha256(r.serie("syn-carga", "potencia").serie)
    derivada = _com_serie(F.previsao(), "syn-carga", "potencia",
                          procedencia=Procedencia("identificado", "pipeline de previsão", "carga", sha256=h))
    assert "previsao_derivada_da_realizacao" in _cods(CN.validar_separacao(derivada, r, dt), "erro")
    p = F.previsao()
    mesmo = CN.Realizacao("r", "sintetica", (p.series[0],), F.proc())
    assert "mesmo_objeto_previsao_realizacao" in _cods(CN.validar_separacao(p, mesmo, dt), "erro")
    oraculo = dataclasses.replace(derivada, previsao_perfeita=True, justificativa_oraculo="ablação")
    assert _cods(CN.validar_separacao(oraculo, r, dt), "erro") == {"oraculo_diferente_da_realizacao"}


def test_h01_causalidade_por_emissao_continua_bloqueante():
    dt = F.definicao()
    tarde = _com_serie(F.previsao(), "syn-carga", "potencia", emissao_utc="2026-01-01T00:01:00+00:00")
    assert "serie_emitida_depois_do_conjunto" in _cods(CN.validar_previsao(tarde, dt), "erro")
    conj = dataclasses.replace(F.previsao(), emissao_utc="2026-01-01T00:01:00+00:00")
    assert "previsao_nao_causal" in _cods(CN.validar_previsao(conj, dt), "erro")


# ======================================================================================== H-02 preflight × políticas
def _pf(pol, *, finalidade="otimizacao", compromisso=F.COMPROMISSO, cen=None, prev=None):
    inv = F.inventario()
    return PF.preflight_ems_v2(inv, cen or F.cenario(inv), F.definicao(), prev or F.previsao(), F.realizacao(), pol,
                               contexto="ensaio", compromisso=compromisso, finalidade=finalidade)


def test_h02_politicas_ausentes_bloqueiam_otimizacao():
    rel, proj = _pf(None)
    assert proj is None and not rel.aceito and not rel.apto_para_otimizacao
    assert {"politicas_ausentes", "projecao_nao_aceita"} <= rel.codigos("bloqueante")


def test_h02_diagnostico_parcial_sem_politicas_artificiais():
    rel, proj = _pf(None, finalidade="diagnostico")
    assert proj is None and rel.aceito and not rel.apto_para_otimizacao
    assert "politicas_nao_fornecidas_diagnostico_parcial" in rel.codigos("advertencia")
    assert "DIAGNÓSTICO PARCIAL" in rel.texto() and rel.por_area("solver") == ()
    com, _ = _pf(F.politicas(), finalidade="diagnostico")
    assert com.aceito and not com.apto_para_otimizacao                        # diagnóstico nunca autoriza


def test_h02_politicas_incompletas_e_projecao_rejeitada():
    rel, _ = _pf(dataclasses.replace(F.politicas(), demandas=()))
    assert {"classes_demanda_nao_declaradas", "projecao_nao_aceita"} <= rel.codigos("bloqueante")
    rel, _ = _pf(dataclasses.replace(F.politicas(), variante_commitment=None))
    assert {"variante_commitment_nao_declarada", "projecao_nao_aceita"} <= rel.codigos("bloqueante")
    inv = F.inventario()
    rel, proj = _pf(F.politicas(), cen=F.cenario(inv, soc_pct=95.0))
    assert proj.entrada is None and "projecao_nao_aceita" in rel.codigos("bloqueante")


def test_h02_preparacao_para_o_solver():
    rel, proj = _pf(F.politicas())
    assert rel.apto_para_otimizacao and proj.aceito and "APTO PARA OTIMIZAÇÃO" in rel.texto()
    sem_compromisso, _ = _pf(F.politicas(), compromisso=None)
    assert "compromisso_livre_nao_suportado_3BP" in sem_compromisso.codigos("bloqueante")
    transicao, _ = _pf(F.politicas(), compromisso={"syn-ter1": [1, 0, 0, 0]})
    assert "transicao_nao_modelada_3BP" in transicao.codigos("bloqueante")
    form_3a, proj_3a = _pf(dataclasses.replace(F.politicas(termos=("curtailment_operacional",)),
                                               versao_formulacao=FORMULACAO_VERSAO))
    assert proj_3a.aceito and "formulacao_sem_solver" in form_3a.codigos("bloqueante")
    with pytest.raises(ValueError):
        _pf(F.politicas(), finalidade="executar")


# ======================================================================================== H-03 imutabilidade concorrente
def _registro(justificativa: str, uid: str = "abcdefabcdefabcdefabcdefabcdef01") -> RG.RegistroExecucaoEMS:
    return RG.selar_registro(RG.RegistroExecucaoEMS(
        1, uid, "2026-11-08T00:00:00+00:00",
        RG.ReferenciaOrigem("syn-mg-a", "inc-syn", 1, F.h64("c"), F.h64("i"), F.h64("e"), "syn-cenario-3c0", 1, F.h64("s")),
        {"ponte": "3C-0"}, {}, RG.Discretizacao(F.INICIO, 900, 4, 4, 4), None, None, None, None, None, None, {}, None,
        {}, RG.valor_futuro_nao_implementado(None), "bloqueado_validacao", justificativa, {}, (), {}))


FILHO = r"""
import sys, time, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from ems_v2.ponte import canonico, registro as RG
reg = canonico.de_json(RG.RegistroExecucaoEMS, Path(sys.argv[2]).read_text(encoding="utf-8"))
destino, pronto, largada = Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
pronto.write_text("1")
while not largada.exists():
    time.sleep(0.0005)
try:
    RG.gravar_registro(destino, reg)
    print("ok")
except RG.RegistroImutavelError:
    print("imutavel")
"""


@pytest.mark.parametrize("rodada", range(3))
def test_h03_concorrencia_real_entre_processos(tmp_path, rodada):
    a, b = _registro(f"conteúdo A {rodada}"), _registro(f"conteúdo B {rodada}")
    fa, fb = tmp_path / "a.json", tmp_path / "b.json"
    fa.write_text(canonico.json_canonico(a), encoding="utf-8")
    fb.write_text(canonico.json_canonico(b), encoding="utf-8")
    destino, largada = tmp_path / "registros", tmp_path / "largada"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    procs, prontos = [], []
    for i in range(8):
        pr = tmp_path / f"pronto{i}"
        prontos.append(pr)
        procs.append(subprocess.Popen([sys.executable, "-c", FILHO, str(RAIZ), str(fa if i % 2 else fb), str(destino),
                                       str(pr), str(largada)], stdout=subprocess.PIPE, text=True, env=env))
    limite = time.monotonic() + 60
    while not all(p.exists() for p in prontos):
        assert time.monotonic() < limite
        time.sleep(0.005)
    largada.write_text("vai")
    saidas = [p.communicate(timeout=60)[0].strip() for p in procs]
    assert all(p.returncode == 0 for p in procs), saidas
    alvo = destino / f"{a.execucao_uid}{RG.SUFIXO_ARQUIVO}"
    final = RG.ler_registro(alvo)
    vencedor = "A" if final == a else "B"
    assert final in (a, b)
    esperado = ["ok" if (i % 2 == 1) == (vencedor == "A") else "imutavel" for i in range(8)]
    assert saidas == esperado                                  # exatamente um conteúdo vence; o outro é recusado
    assert sorted(x.name for x in destino.iterdir()) == [alvo.name]   # nenhum temporário restante


def test_h03_concorrencia_real_entre_threads(tmp_path):
    a, b = _registro("thread A"), _registro("thread B")
    barreira, res = threading.Barrier(16), [None] * 16

    def trabalho(i):
        barreira.wait()
        try:
            RG.gravar_registro(tmp_path, a if i % 2 else b)
            res[i] = "ok"
        except RG.RegistroImutavelError:
            res[i] = "imutavel"
    ts = [threading.Thread(target=trabalho, args=(i,)) for i in range(16)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    final = RG.ler_registro(tmp_path / f"{a.execucao_uid}{RG.SUFIXO_ARQUIVO}")
    venceu_a = final == a
    assert res == ["ok" if (i % 2 == 1) == venceu_a else "imutavel" for i in range(16)]
    assert len(list(tmp_path.iterdir())) == 1


def test_h03_idempotencia_e_conteudo_diferente(tmp_path):
    a = _registro("único")
    p = RG.gravar_registro(tmp_path, a)
    antes = p.read_bytes()
    assert RG.gravar_registro(tmp_path, a) == p and p.read_bytes() == antes
    with pytest.raises(RG.RegistroImutavelError):
        RG.gravar_registro(tmp_path, _registro("outro"))
    assert p.read_bytes() == antes and len(list(tmp_path.iterdir())) == 1
    adult = dataclasses.replace(a, justificativa_desfecho="adulterado")      # selo antigo ⇒ recusado antes de gravar
    with pytest.raises(ContratoInvalido) as ei:
        RG.gravar_registro(tmp_path / "x", adult)
    assert "registro_adulterado" in ei.value.codigos and not (tmp_path / "x" / p.name).exists()


def _sem_hard_link(monkeypatch):
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EPERM, "sem hard link")))


def test_h03_falha_limpa_temporarios_e_nao_deixa_alvo(tmp_path, monkeypatch):
    """Falha ao escrever o temporário e falha na publicação da rota alternativa: nada fica no diretório."""
    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(errno.EIO, "E/S simulada")))
    with pytest.raises(OSError):
        RG.gravar_registro(tmp_path, _registro("falha"))
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(os, "fsync", real_fsync)
    _sem_hard_link(monkeypatch)
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.ENOSPC, "disco cheio")))
    with pytest.raises(OSError):
        RG.gravar_registro(tmp_path, _registro("falha"))
    assert list(tmp_path.iterdir()) == []                       # sem temporário, sem reserva, sem alvo


def test_c03_reserva_orfa_nunca_e_sobrescrita(tmp_path, monkeypatch):
    _sem_hard_link(monkeypatch)
    monkeypatch.setattr(RG, "_ESPERA_RESERVA_S", 0.05)
    a = _registro("órfã")
    reserva = tmp_path / f".{a.execucao_uid}{RG.SUFIXO_ARQUIVO}.reserva"
    reserva.write_text("escritor interrompido")
    with pytest.raises(RG.RegistroReservaOrfaError) as ei:
        RG.gravar_registro(tmp_path, a)
    assert "reserva_orfa" in ei.value.codigos
    assert sorted(x.name for x in tmp_path.iterdir()) == [reserva.name]      # nada publicado, reserva intacta


class _Lento:
    """Arquivo cuja escrita avança em pedaços pequenos (expõe qualquer leitura de arquivo parcialmente escrito)."""

    def __init__(self, f):
        self._f = f

    def write(self, dados):
        for k in range(0, len(dados), 64):
            self._f.write(dados[k:k + 64])
            self._f.flush()
            time.sleep(0.002)
        return len(dados)

    def __getattr__(self, nome):
        return getattr(self._f, nome)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self._f.__exit__(*exc)


def test_c03_leitor_concorrente_nunca_ve_registro_parcial_na_rota_alternativa(tmp_path, monkeypatch):
    _sem_hard_link(monkeypatch)
    real_fdopen = os.fdopen
    monkeypatch.setattr(os, "fdopen", lambda fd, modo="r", *a, **k: _Lento(real_fdopen(fd, modo, *a, **k))
                        if "w" in modo else real_fdopen(fd, modo, *a, **k))
    a = _registro("leitura concorrente " + "x" * 2000)
    alvo = tmp_path / f"{a.execucao_uid}{RG.SUFIXO_ARQUIVO}"
    final = canonico.json_canonico(a)
    vistos, parar = [], threading.Event()

    def leitor():
        while not parar.is_set():
            try:
                vistos.append(alvo.read_text(encoding="utf-8"))
            except FileNotFoundError:
                vistos.append(None)
    t = threading.Thread(target=leitor)
    t.start()
    try:
        RG.gravar_registro(tmp_path, a)
        time.sleep(0.02)
    finally:
        parar.set()
        t.join()
    assert None in vistos and final in vistos                  # o leitor observou antes e depois da publicação
    assert {v for v in vistos if v is not None} == {final}     # nenhuma leitura parcial
    assert RG.ler_registro(alvo) == a


def test_c03_escritores_concorrentes_na_rota_alternativa(tmp_path, monkeypatch):
    _sem_hard_link(monkeypatch)
    a, b = _registro("alt A"), _registro("alt B")
    barreira, res = threading.Barrier(12), [None] * 12

    def trabalho(i):
        barreira.wait()
        try:
            RG.gravar_registro(tmp_path, a if i % 2 else b)
            res[i] = "ok"
        except RG.RegistroImutavelError:
            res[i] = "imutavel"
    ts = [threading.Thread(target=trabalho, args=(i,)) for i in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    final = RG.ler_registro(tmp_path / f"{a.execucao_uid}{RG.SUFIXO_ARQUIVO}")
    assert res == ["ok" if (i % 2 == 1) == (final == a) else "imutavel" for i in range(12)]
    assert len(list(tmp_path.iterdir())) == 1


def test_h03_fallback_sem_hard_link_tambem_e_exclusivo(tmp_path, monkeypatch):
    _sem_hard_link(monkeypatch)
    a = _registro("fallback A")
    p = RG.gravar_registro(tmp_path, a)
    assert RG.ler_registro(p) == a and RG.gravar_registro(tmp_path, a) == p
    with pytest.raises(RG.RegistroImutavelError):
        RG.gravar_registro(tmp_path, _registro("fallback B"))
    assert [x.name for x in tmp_path.iterdir()] == [p.name]


# ======================================================================================== H-04 realização incremental
def _parcial(**kw):
    return F.realizacao(demanda=F.DEMANDA_PREV[:2], pv=F.PV_PREV[:2], disp_pv=(1, 1), observado_ate=T2, **kw)


def test_h04_observacao_online_valida_so_ate_o_instante_observado():
    dt = F.definicao()
    assert CN.validar_realizacao(_parcial(), dt) == []
    assert CN.intervalos_observados(_parcial(), dt) == (2, [])
    zero = CN.Realizacao("r", "sintetica", (), F.proc("r"), "incremental_online", F.INICIO)
    assert CN.validar_realizacao(zero, dt) == [] and CN.intervalos_observados(zero, dt)[0] == 0
    assert canonico.de_json(CN.Realizacao, canonico.json_canonico(_parcial())) == _parcial()


@pytest.mark.parametrize("real,codigo", [
    (lambda: F.realizacao(observado_ate=T2), "realizacao_alem_do_observado"),           # valores futuros
    (lambda: F.realizacao(demanda=(30.0,), pv=(20.0,), disp_pv=(1,), observado_ate=T2), "cobertura_insuficiente"),
    (lambda: dataclasses.replace(_parcial(), observado_ate_utc="2026-01-01T00:20:00+00:00"), "observado_ate_fora_da_malha"),
    (lambda: dataclasses.replace(_parcial(), observado_ate_utc="2026-01-01T02:00:00+00:00"), "observado_ate_alem_da_missao"),
    (lambda: dataclasses.replace(_parcial(), observado_ate_utc="2026-01-01T00:30:00"), "fuso_ambiguo"),
    (lambda: dataclasses.replace(F.realizacao(), observado_ate_utc=T2), "observado_ate_em_modo_offline"),
    (lambda: dataclasses.replace(F.realizacao(), modo="tempo_real"), "modo_realizacao_invalido"),
])
def test_h04_rejeicoes_da_observacao_incremental(real, codigo):
    assert codigo in _cods(CN.validar_realizacao(real(), F.definicao()), "erro")


def test_h04_offline_continua_exigindo_a_missao_inteira():
    curta = F.realizacao(demanda=F.DEMANDA_PREV[:2], pv=F.PV_PREV[:2], disp_pv=(1, 1))
    assert "cobertura_insuficiente" in _cods(CN.validar_realizacao(curta, F.definicao()), "erro")


def _plano_analitico():
    inv = F.inventario()
    proj = PJ.montar_entrada(inv, F.cenario(inv), F.previsao(), F.definicao(), F.politicas(), contexto="ensaio")
    e = proj.entrada
    desp = {"renovaveis": {"syn-pv1": {"P_R": F.PV_PREV, "C_oper": (0.0,) * 4}},
            "baterias": {"syn-bat1": {"P_c": (0.0,) * 4, "P_d": (0.0, 0.0, 10.0, 0.0), "z_b": (0.0,) * 4,
                                      "e": (50.0, 50.0, 50.0, 50.0 - 2.5 / 0.95, 50.0 - 2.5 / 0.95)}},
            "demandas": {"syn-carga": {"ell": (0.0,) * 4}}, "descarte": None,
            "geradores": {"syn-ter1": {"u": (1.0,) * 4, "p": (10.0, 10.0, 30.0, 20.0)}}}
    res = SimpleNamespace(aceito=True, despacho=desp, hash_entrada=hash_entrada(e), motor_id=MOTOR_ID,
                          versao_formulacao=FORMULACAO_3BP, classificacao="otimo", estado_despacho="aceito_otimo",
                          custos_modelo={"total": 0.025})
    return e, EX.plano_de_resultado(res, e)


def test_h04_execucao_nunca_ultrapassa_o_observado_e_retoma_com_nova_observacao():
    e, plano = _plano_analitico()
    ex, e0 = EX.ExecutorAlgebricoReferencia(e), EX.estado_inicial_de_entrada(e)
    uid = "1234567890abcdef1234567890abcdef"
    alem = EX.executar(plano, e0, ex, _parcial(), execucao_uid=uid)
    # C-02: pausa por observação pendente (não inviabilidade), antes de consultar o entorno
    assert alem.situacao == "pausada_aguardando_observacoes" and alem.cursor_final == 2
    assert _cods(alem.constatacoes) == {"aguardando_observacoes"}
    ate = EX.executar(plano, e0, ex, _parcial(), execucao_uid=uid, intervalos=2)
    assert ate.situacao == "concluida" and ate.checkpoints[-1].cursor_plano == 2
    nova = F.realizacao(observado_ate="2026-01-01T01:00:00+00:00")                 # observação posterior (τ_4)
    assert CN.validar_realizacao(nova, F.definicao()) == []
    resto = EX.retomar(ate.checkpoints[-1], plano, ex, nova)
    continuo = EX.executar(plano, e0, ex, F.realizacao(), execucao_uid=uid)
    assert resto.estados[-1] == continuo.estados[-1] and resto.checkpoints[-1] == continuo.checkpoints[-1]


def test_h04_preflight_aceita_observacao_online_parcial():
    inv = F.inventario()
    rel, _ = PF.preflight_ems_v2(inv, F.cenario(inv), F.definicao(), F.previsao(), _parcial(), F.politicas(),
                                 contexto="ensaio", compromisso=F.COMPROMISSO)
    assert rel.apto_para_otimizacao, rel.texto()
    sep = {c.uid: c for c in CN.classificar_separacao(F.previsao(), _parcial(), F.definicao())}
    assert sep["syn-carga"].intervalos_comparados == 2                        # compara só o já observado


# ======================================================================================== C-01 preflight × k observados
def _real_online(k: int, uids=("syn-carga", "syn-pv1"), cobre=None):
    """Observação online até τ_k; ``cobre`` = intervalos efetivamente presentes nas séries (padrão: k)."""
    cobre = k if cobre is None else cobre
    t_k = (F.definicao().malha.fronteiras_utc()[k]).isoformat()
    base = F.realizacao(demanda=F.DEMANDA_PREV[:cobre], pv=F.PV_PREV[:cobre], disp_pv=(1,) * cobre, observado_ate=t_k) \
        if cobre else CN.Realizacao("r", "sintetica", (), F.proc("r"), "incremental_online", t_k)
    return dataclasses.replace(base, series=tuple(x for x in base.series if x.uid in uids))


def _pf_real(real):
    inv = F.inventario()
    return PF.preflight_ems_v2(inv, F.cenario(inv), F.definicao(), F.previsao(), real, F.politicas(), contexto="ensaio",
                               compromisso=F.COMPROMISSO)[0]


def test_c01_k0_valido_para_preparar_otimizacao():
    rel = _pf_real(_real_online(0))
    assert rel.apto_para_otimizacao, rel.texto()
    assert "nenhum_intervalo_observado" in rel.codigos("advertencia")
    assert "realizacao_ausente_para_recurso" not in rel.codigos()


def test_c01_k1_exige_series_observadas_coerentes():
    assert _pf_real(_real_online(1)).apto_para_otimizacao
    sem_pv = _pf_real(_real_online(1, uids=("syn-carga",)))
    assert "realizacao_ausente_para_recurso" in sem_pv.codigos("bloqueante")


def test_c01_cobertura_parcial_e_series_ausentes():
    parcial = _pf_real(_real_online(2, cobre=1))                       # observado até τ_2, dados só de 1 intervalo
    assert "cobertura_insuficiente" in parcial.codigos("bloqueante")
    sem_series = _pf_real(dataclasses.replace(_real_online(2), series=()))
    assert "realizacao_ausente_para_recurso" in sem_series.codigos("bloqueante")


def test_c01_offline_continua_exigindo_series():
    real = F.realizacao()
    sem = dataclasses.replace(real, series=tuple(x for x in real.series if x.uid != "syn-pv1"))
    assert "realizacao_ausente_para_recurso" in _pf_real(sem).codigos("bloqueante")
    assert _pf_real(real).apto_para_otimizacao


# ======================================================================================== C-02 limite temporal da execução
class _ExecutorCego:
    """Executor ALTERNATIVO que deliberadamente NÃO consulta o entorno: aplica a consigna e avança o relógio."""
    identificador, natureza = "cego", "algebrico_referencia"

    def __init__(self):
        self.chamadas = 0

    def avancar(self, estado, consignas, entorno, delta_s):
        from datetime import timedelta
        from ems_v2.timegrid import ler_instante_utc
        self.chamadas += 1
        t1 = ler_instante_utc(estado.instante_utc, "e")[0] + timedelta(seconds=delta_s)
        return EX.PassoAplicado(dict(consignas), dataclasses.replace(
            estado, indice_fronteira=estado.indice_fronteira + 1, instante_utc=t1.isoformat()), True)


def test_c02_limite_observado_pertence_ao_contrato_nao_ao_executor():
    e, plano = _plano_analitico()
    # realização online declarada até τ_2 MAS com valores para os 4 intervalos (dados offline mal rotulados):
    # sem a barreira do contrato, um executor que não consulta o entorno aplicaria os intervalos 2 e 3.
    vazada = dataclasses.replace(F.realizacao(), modo="incremental_online", observado_ate_utc=T2)
    cego = _ExecutorCego()
    t = EX.executar(plano, EX.estado_inicial_de_entrada(e), cego, vazada, execucao_uid="c" * 32)
    assert cego.chamadas == 2 and t.cursor_final == 2 and len(t.estados) == 3
    assert t.situacao == "pausada_aguardando_observacoes" and _cods(t.constatacoes) == {"aguardando_observacoes"}
    assert t.checkpoints[-1].cursor_plano == 2 and t.checkpoints[-1].estado == t.estados[-1]
    t0 = EX.executar(plano, EX.estado_inicial_de_entrada(e), _ExecutorCego(), _real_online(0), execucao_uid="c" * 32)
    assert t0.situacao == "pausada_aguardando_observacoes" and t0.cursor_final == 0 and len(t0.estados) == 1
    assert "realizacao_alem_do_observado" in _cods(CN.validar_realizacao(vazada, F.definicao()), "erro")


def test_c02_pausa_inviabilidade_e_erro_de_dados_sao_distintos():
    e, plano = _plano_analitico()
    ex, e0, uid = EX.ExecutorAlgebricoReferencia(e), EX.estado_inicial_de_entrada(e), "d" * 32
    pausa = EX.executar(plano, e0, ex, _parcial(), execucao_uid=uid)
    inex = EX.executar(plano, e0, ex, F.realizacao(demanda=(30.0, 45.0, 50.0, 20.0)), execucao_uid=uid)
    buraco = dataclasses.replace(F.realizacao(), series=tuple(x for x in F.realizacao().series if x.uid != "syn-carga"))
    dados = EX.executar(plano, e0, ex, buraco, execucao_uid=uid)
    ilegivel = EX.executar(plano, e0, ex, dataclasses.replace(_parcial(), observado_ate_utc="ontem"), execucao_uid=uid)
    assert (pausa.situacao, inex.situacao, dados.situacao, ilegivel.situacao) == (
        "pausada_aguardando_observacoes", "interrompida_inexequivel", "erro_dados", "erro_dados")
    assert "balanco_realizado_violado" in _cods(inex.constatacoes)
    assert _cods(dados.constatacoes) == {"realizacao_ausente"} and dados.cursor_final == 0
    tardia = _com_serie(F.realizacao(), "syn-carga", "potencia", inicio_utc="2026-01-01T00:15:00+00:00")
    t_tardia = EX.executar(plano, e0, ex, tardia, execucao_uid=uid)
    assert t_tardia.situacao == "erro_dados" and "realizacao_sem_cobertura" in _cods(t_tardia.constatacoes)
    assert ilegivel.cursor_final == 0 and "instante_invalido" in _cods(ilegivel.constatacoes)
    assert set(EX.SITUACOES) == {"concluida", "pausada_aguardando_observacoes", "interrompida_inexequivel", "erro_dados"}


def test_c02_pausa_retoma_do_checkpoint_sem_falsificar_inviabilidade():
    e, plano = _plano_analitico()
    cego, uid = _ExecutorCego(), "e" * 32
    p1 = EX.executar(plano, EX.estado_inicial_de_entrada(e), cego, _real_online(1), execucao_uid=uid)
    assert p1.situacao == "pausada_aguardando_observacoes" and p1.cursor_final == 1
    p2 = EX.retomar(p1.checkpoints[-1], plano, cego, _real_online(3))
    assert p2.situacao == "pausada_aguardando_observacoes" and p2.cursor_final == 3
    p3 = EX.retomar(p2.checkpoints[-1], plano, cego, _real_online(4))
    assert p3.situacao == "concluida" and p3.cursor_final == 4 and cego.chamadas == 4
    continuo = EX.executar(plano, EX.estado_inicial_de_entrada(e), _ExecutorCego(), F.realizacao(), execucao_uid=uid)
    assert p3.estados[-1] == continuo.estados[-1] and p3.passos[-1] == continuo.passos[-1]


# ======================================================================================== C-3C0-01 condições
def test_c3c001_leitor_nao_muta_armazenamento_e_preserva_identidade(tmp_path):
    sys.path.insert(0, str(RAIZ / "tests"))
    from seeds2_fixtures import v16_equivalent_config
    from ems_v2.ponte_seeds2 import leitor as L
    from seeds2.microgrid.registry import MicrogridRegistry
    from seeds2.operation import service as SV
    dados = tmp_path / "dados"
    reg = MicrogridRegistry(dados, adopt_legacy=False)
    cfg = v16_equivalent_config()
    reg.create(cfg)
    uid = cfg["installation"]["uid"]
    sc = SV.create(reg.open(uid), name="Cenário")

    def arvore():
        return {str(p.relative_to(dados)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(dados.rglob("*")) if p.is_file()}
    antes = arvore()
    for _ in range(3):
        inv = L.ler_inventario(reg, uid)
        L.ler_inventario(reg, uid, revisao=1)
        L.ler_cenario(reg, uid, sc.scenario_uid)
    assert arvore() == antes                                                   # nenhum arquivo criado/alterado
    ent = reg.get(uid)
    assert (inv.identidade.uid, inv.identidade.incarnacao, inv.identidade.revisao_config) == (uid, ent.incarnation, 1)
    assert json.loads(json.dumps(canonico.json_canonico(inv)))                # serializável e estável
