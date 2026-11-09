"""C-3C4-A03 — último fecho da auditoria do PR #17 (HEAD auditado ``8dd8edb``): coerência DOCUMENTAL de B3C4-10.

Reproduzido ANTES da correção (EVIDENCIA_3C4_EJECUCION §4.5) com cadeias seladas CONSISTENTES (o próprio resolvedor
fabrica as evidências, de modo que nenhum selo diverge):

* **A03-1** — a resolução selada declarava ``normalizacao_numerica_pcc`` mas o registro 3C-0 não tinha aviso nem hash:
  ``reconstruir_normalizacoes_pcc`` pulava a janela (``if not avs and not tem_hash: continue``) e aceitava;
* **A03-2** — a auditoria INTEGRAL 3C-3 não reconstruía as normalizações: uma normalização injustificada (bruto
  −1e-3 ≫ limiar) registrada numa cadeia consistente era aceita.

Agora o verificador ÚNICO vive em ``ems_v2/rede/auditoria.py`` (sem dependência de ``ems_v2.hierarquia``) e é usado
pela auditoria integral 3C-3 (seção ``normalizacoes_pcc``); a 3C-4 espelha essa seção (sem duplicar constatações).
Três evidências — código na resolução, avisos e hash no registro 3C-0 — ou estão TODAS presentes e coerentes, ou TODAS
ausentes (janela sem normalização, inclusive registros anteriores a B3C4-10). Os selos SHA-256 detectam alteração
frente ao artefato selado; não são assinatura nem provam a procedência autêntica do solver (B3C4-08).
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

from ems_v2 import fixtures_3c4 as F

pytestmark = pytest.mark.synthetic_algebraic
RAIZ = Path(__file__).resolve().parents[2]
BASE_3C3 = "10365c5"
COD = "normalizacao_numerica_pcc"

try:
    import highspy  # noqa: F401
    import pyomo  # noqa: F401
    COM_SOLVER = True
except ImportError:
    COM_SOLVER = False
solver = pytest.mark.skipif(not COM_SOLVER, reason="Pyomo/HiGHS indisponíveis (requirements-ems_v2.txt)")


# ================================================================================================ apoio
@lru_cache(maxsize=None)
def _h9(estr, fabricacao=None):
    """Missão H9. ``fabricacao`` substitui o normalizador do resolvedor 3C-3 (cadeia selada CONSISTENTE)."""
    import ems_v2.milp.solver_3c3 as S3
    from ems_v2.hierarquia import experimentos as X
    from ems_v2.rede.execucao import normalizar_residuos_pcc as real
    if fabricacao is None:
        return X.executar(F.h9_pemfc(), estr)
    S3.normalizar_residuos_pcc = FABRICACOES[fabricacao]
    try:
        return X.executar(F.h9_pemfc(), estr)
    finally:
        S3.normalizar_residuos_pcc = real


def _injustificada(e, pcc, d, tol):
    from ems_v2.rede.execucao import normalizar_residuos_pcc
    p, ns, c = normalizar_residuos_pcc(e, pcc, d, tol)
    return p, tuple(replace(n, valor_bruto_kW=-1e-3, diferenca_kW=1e-3) for n in ns), c


def _codigo_sem_registro(e, pcc, d, tol):
    from ems_v2.rede.execucao import aviso_normalizacao_pcc, normalizar_residuos_pcc
    p, ns, c = normalizar_residuos_pcc(e, pcc, d, tol)
    return p, (), c + [aviso_normalizacao_pcc(n) for n in ns]


FABRICACOES = {"injustificada": _injustificada, "codigo_sem_registro": _codigo_sem_registro}


def integral_3c3(x, **over):
    from ems_v2.rede.auditoria import auditar_missao_conectada
    r, c = x.resultado, x.controlador
    a = dict(registros_3c0=r.registros_3c0, anexos=r.anexos_3c3, registro_rede=r.registro_rede,
             verdade=x.entorno._verdade)
    regs = over.pop("registros", r.registros)
    a.update(over)
    return auditar_missao_conectada(r.registro_missao, regs, r.livro, x.modelo, c.cfg_rede, **a)


def integral_3c4(x, **over):
    from ems_v2.hierarquia.auditoria import auditar_missao_hierarquica
    r, c = x.resultado, x.controlador
    a = dict(registros_3c0=r.registros_3c0, anexos=r.anexos_3c3, registro_rede=r.registro_rede,
             coordenacoes=r.coordenacoes, registro_hierarquico=r.registro_hierarquico, verdade=x.entorno._verdade)
    regs = over.pop("registros", r.registros)
    a.update(over)
    return auditar_missao_hierarquica(r.registro_missao, regs, r.livro, x.modelo, c.cfg_rede, c.cfg_plan, **a)


def erros(rel):
    return {k.codigo for k in rel.constatacoes if k.severidade == "erro"}


def _janela(x):
    """(índice no registro de janelas, registro 3C-0) da janela k = 10 de H9 (a normalizada)."""
    r = x.resultado
    i = next(j for j, w in enumerate(r.registros) if w.conteudo.janela.k == 10)
    z = next(z for z in r.registros_3c0 if z.execucao_uid == r.registros[i].conteudo.execucao_uid)
    return i, z


def _trocar_r0(x, novo):
    _, z = _janela(x)
    return tuple(novo if q is z else q for q in x.resultado.registros_3c0)


def _sem_codigo(x):
    r = x.resultado
    i, _ = _janela(x)
    w = r.registros[i]
    cods = tuple(k for k in w.conteudo.resolucao.codigos if k != COD)
    regs = list(r.registros)
    regs[i] = replace(w, conteudo=replace(w.conteudo, resolucao=replace(w.conteudo.resolucao, codigos=cods)))
    return tuple(regs)


def _sem_aviso(z):
    return replace(z, constatacoes=tuple(k for k in z.constatacoes if k.codigo != COD))


def _sem_hash(z):
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC as CH
    return replace(z, hashes={k: v for k, v in z.hashes.items() if k != CH})


def _hash_alterado(z):
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC as CH
    return replace(z, hashes={**z.hashes, CH: "0" * 64})


# ================================================================================================ válidas
@solver
def test_h9_3c3_valida_com_normalizacao_aceita_pela_auditoria_integral():
    x = _h9("mpc_sem_sinal")
    rel = integral_3c3(x)
    assert rel.aceito and rel.integridade_documental_certificada, erros(rel)
    assert rel.verificacoes["normalizacoes_pcc"] is True
    assert [(n.grandeza, n.indice_janela, n.valor_bruto_kW) for n in rel.normalizacoes_pcc] == [
        ("P_imp", 0, -8.881784197001252e-16)]


@solver
@pytest.mark.parametrize("estr,n", [("hier_ref_dura", 1), ("hier_pwl", 0)])
def test_h9_3c4_valida_aceita_pela_auditoria_integral(estr, n):
    x = _h9(estr)
    rel = integral_3c4(x)
    assert rel.aceito, rel.codigos()
    assert rel.verificacoes["normalizacoes_pcc"] is True and rel.relatorio_3c3.verificacoes["normalizacoes_pcc"]
    assert len(rel.normalizacoes_pcc) == n and rel.normalizacoes_pcc == rel.relatorio_3c3.normalizacoes_pcc
    # uma ÚNICA verificação: nenhuma constatação duplicada entre as seções 3C-3 e 3C-4
    assert len(rel.constatacoes) == len(set(rel.constatacoes))


@solver
def test_janelas_legitimas_sem_normalizacao_aceitas_sem_obrigacao_nova():
    from ems_v2.rede import experimentos as X
    from ems_v2.rede.auditoria import reconstruir_normalizacoes_pcc
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC as CH
    g = X.g11_mpc_conectado()
    r = g.resultado
    assert all(CH not in z.hashes and COD not in {k.codigo for k in z.constatacoes} for z in r.registros_3c0)
    assert all(COD not in w.conteudo.resolucao.codigos for w in r.registros if w.conteudo.resolucao)
    from ems_v2.rede.auditoria import auditar_missao_conectada
    rel = auditar_missao_conectada(r.registro_missao, r.registros, r.livro, g.modelo, g.configuracao_rede,
                                   registros_3c0=r.registros_3c0, anexos=r.anexos_3c3, registro_rede=r.registro_rede,
                                   verdade=g.verdade)
    assert rel.aceito and rel.verificacoes["normalizacoes_pcc"] and rel.normalizacoes_pcc == ()
    assert reconstruir_normalizacoes_pcc(g.modelo, r.registros, r.registros_3c0, r.anexos_3c3) == ((), [])
    # H9: as 11 janelas sem normalização também não carregam evidência alguma
    x = _h9("mpc_sem_sinal")
    _, z = _janela(x)
    outras = [q for q in x.resultado.registros_3c0 if q is not z]
    assert len(outras) == 11 and all(CH not in q.hashes for q in outras)


# ================================================================================================ A03-1 (três evidências)
@solver
@pytest.mark.parametrize("auditoria", ["3c3", "3c4"])
@pytest.mark.parametrize("caso,codigos", [
    ("aviso_ausente_hash_presente", {"normalizacao_pcc_nao_comprometida"}),
    ("hash_ausente_aviso_presente", {"normalizacao_pcc_nao_comprometida"}),
    ("aviso_e_hash_ausentes_codigo_presente", {"normalizacao_pcc_declarada_sem_registro"}),
    ("codigo_ausente_aviso_e_hash_presentes", {"normalizacao_pcc_sem_origem_no_solver"}),
    ("hash_alterado", {"normalizacao_pcc_nao_comprometida"}),
])
def test_a03_1_evidencias_incoerentes_rejeitadas(caso, codigos, auditoria):
    x = _h9("mpc_sem_sinal" if auditoria == "3c3" else "hier_ref_dura")
    _, z = _janela(x)
    over = {
        "aviso_ausente_hash_presente": dict(registros_3c0=_trocar_r0(x, _sem_aviso(z))),
        "hash_ausente_aviso_presente": dict(registros_3c0=_trocar_r0(x, _sem_hash(z))),
        "aviso_e_hash_ausentes_codigo_presente": dict(registros_3c0=_trocar_r0(x, _sem_hash(_sem_aviso(z)))),
        "codigo_ausente_aviso_e_hash_presentes": dict(registros=_sem_codigo(x)),
        "hash_alterado": dict(registros_3c0=_trocar_r0(x, _hash_alterado(z))),
    }[caso]
    rel = integral_3c3(x, **over) if auditoria == "3c3" else integral_3c4(x, **over)
    assert not rel.aceito and rel.verificacoes["normalizacoes_pcc"] is False
    assert codigos <= erros(rel), erros(rel)


@solver
def test_a03_1_codigo_sem_aviso_nem_hash_em_cadeia_selada_consistente():
    """O resolvedor declara a normalização (código) mas não a entrega ao registro: TODOS os selos conferem; só a
    coerência das três evidências reprova (antes de A03: aceito)."""
    x = _h9("mpc_sem_sinal", "codigo_sem_registro")
    assert x.resultado.situacao == "encerrada"
    i, z = _janela(x)
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC as CH
    assert COD in x.resultado.registros[i].conteudo.resolucao.codigos and CH not in z.hashes
    rel = integral_3c3(x)
    assert not rel.aceito and rel.verificacoes["documental"] and rel.verificacoes["normalizacoes_pcc"] is False
    assert erros(rel) == {"normalizacao_pcc_declarada_sem_registro"}


# ================================================================================================ A03-2 (perfil 3C-3)
@solver
def test_a03_2_normalizacao_injustificada_rejeitada_pela_auditoria_integral_3c3():
    """Bruto −1e-3 ≫ limiar, registrado numa cadeia selada CONSISTENTE (selos, documental, balanço e custos
    aprovados): só a reconstrução da política reprova (antes de A03: auditoria integral 3C-3 aceitava)."""
    x = _h9("mpc_sem_sinal", "injustificada")
    rel = integral_3c3(x)
    assert not rel.aceito and rel.verificacoes["normalizacoes_pcc"] is False
    assert all(v for k, v in rel.verificacoes.items() if k != "normalizacoes_pcc"), rel.verificacoes
    assert erros(rel) == {"normalizacao_pcc_fora_da_politica"}


@solver
def test_a03_2_auditoria_analitica_parcial_nao_e_afetada():
    """O escopo analítico parcial (sem artefatos documentais) continua sem seção documental/normalizações."""
    from ems_v2.rede.auditoria import auditar_missao_conectada_analitica
    x = _h9("mpc_sem_sinal")
    r, c = x.resultado, x.controlador
    rel = auditar_missao_conectada_analitica(r.registro_missao, r.registros, r.livro, x.modelo, c.cfg_rede,
                                             verdade=x.entorno._verdade)
    assert rel.aceito and "normalizacoes_pcc" not in rel.verificacoes and rel.normalizacoes_pcc == ()


# ================================================================================================ registro histórico
def _exige_base():
    try:
        subprocess.run(["git", "cat-file", "-e", BASE_3C3], cwd=RAIZ, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip(f"Histórico git sem a base {BASE_3C3} (clone raso): verificação feita no PR.")


@solver
def test_registro_historico_3c3_anterior_a_b3c4_10_aceito_sem_obrigacao_nova(tmp_path):
    """G11 executado pelo CÓDIGO da base ``10365c5`` (anterior a B3C4-10), artefatos gravados em disco por aquele
    código, relidos e auditados pela auditoria integral ATUAL: aceito, sem exigir avisos/hash/código novos."""
    _exige_base()
    base = tmp_path / "base"
    base.mkdir()
    tar = subprocess.run(["git", "archive", "--format=tar", BASE_3C3, "ems_v2"], cwd=RAIZ, capture_output=True,
                         check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(base, filter="data")
    d = tmp_path / "artefatos"
    d.mkdir()
    env = {**os.environ, "PYTHONPATH": str(base), "PYTHONDONTWRITEBYTECODE": "1"}
    prog = ("import ems_v2, sys; assert ems_v2.__file__.startswith(sys.argv[2]), ems_v2.__file__\n"
            "from ems_v2.rede import experimentos as X\n"
            "import ems_v2.rede.execucao as E; assert not hasattr(E, 'normalizar_residuos_pcc')\n"
            "x = X.g11_mpc_conectado(diretorio=sys.argv[1]); print(x.resultado.situacao)")
    out = subprocess.run([sys.executable, "-c", prog, str(d), str(base)], cwd=tmp_path, env=env,
                         capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == "encerrada", out.stderr[-2000:]

    from ems_v2.mpc.persistencia import _ler, ler_missao
    from ems_v2.ponte.registro import ler_registro
    from ems_v2.rede import experimentos as X
    from ems_v2.rede.auditoria import auditar_missao_conectada
    from ems_v2.rede.mpc import CHAVE_HASH_NORMALIZACOES_PCC as CH, RegistroMissaoRede3C3
    from ems_v2.rede.registro import SUFIXO_ANEXO_3C3, ler_anexo_3c3
    from ems_v2 import fixtures_3c3 as F3
    ctrl, ent, mod, ver, pol, crd = X.montar("g11-mpc-conectado", L_real=X.L_G11, pv_real=X.PV_REAL_G11,
                                             tarifas=F3.tarifas_decisao(8, revisao_1_em="2026-01-01T01:00:00+00:00"))
    uid = ctrl.cfg.identidade.missao_uid
    rm, regs, livro = ler_missao(d, uid)
    exe = [w.conteudo.execucao_uid for w in regs if w.conteudo.hash_plano is not None]
    r0 = tuple(ler_registro(d / f"{u}.ems3c0.json") for u in exe)
    anx = tuple(ler_anexo_3c3(d / f"{u}{SUFIXO_ANEXO_3C3}") for u in exe)
    rr = _ler(RegistroMissaoRede3C3, d / f"{uid}.rede.missao.mpc3c3.json", "registro_rede")
    assert exe and all(CH not in z.hashes for z in r0)                      # artefatos SEM evidência B3C4-10
    rel = auditar_missao_conectada(rm, regs, livro, mod, crd, registros_3c0=r0, anexos=anx, registro_rede=rr,
                                   verdade=ver)
    assert rel.aceito and rel.integridade_documental_certificada, erros(rel)
    assert rel.verificacoes["normalizacoes_pcc"] is True and rel.normalizacoes_pcc == ()
    # e são os MESMOS artefatos que o código atual produz (nenhuma semântica histórica alterada)
    atual = X.g11_mpc_conectado()
    assert atual.resultado.registro_missao.impressao_deterministica == rm.impressao_deterministica
