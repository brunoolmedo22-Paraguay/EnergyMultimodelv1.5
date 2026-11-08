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


def test_h03_falha_limpa_temporarios_e_nao_deixa_alvo(tmp_path, monkeypatch):
    def falha(*a, **k):
        raise OSError(errno.EIO, "falha de E/S simulada")
    monkeypatch.setattr(os, "link", falha)
    real_open = os.open
    monkeypatch.setattr(os, "open", lambda p, *a, **k: falha() if str(p).endswith(RG.SUFIXO_ARQUIVO) else real_open(p, *a, **k))
    with pytest.raises(OSError):
        RG.gravar_registro(tmp_path, _registro("falha"))
    assert list(tmp_path.iterdir()) == []


def test_h03_falha_durante_escrita_no_fallback_remove_alvo_proprio(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EPERM, "sem hard link")))
    real_fsync, chamadas = os.fsync, []

    def fsync(fd):
        chamadas.append(fd)
        if len(chamadas) == 2:                 # 1º = temporário; 2º = alvo criado com O_EXCL
            raise OSError(errno.ENOSPC, "disco cheio simulado")
        return real_fsync(fd)
    monkeypatch.setattr(os, "fsync", fsync)
    with pytest.raises(OSError):
        RG.gravar_registro(tmp_path, _registro("fallback"))
    assert list(tmp_path.iterdir()) == []


def test_h03_fallback_sem_hard_link_tambem_e_exclusivo(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EPERM, "sem hard link")))
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
    assert alem.situacao == "interrompida_inexequivel" and alem.cursor_final == 2
    assert "realizacao_sem_cobertura" in _cods(alem.constatacoes)                # nada é inventado após τ_2
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
