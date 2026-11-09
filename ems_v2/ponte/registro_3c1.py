"""Anexo de evidência 3C-1 ao registro de execução 3C-0 (B-02) — só biblioteca padrão.

O esquema histórico ``RegistroExecucaoEMS`` (3C-0) NÃO muda. A ligação usa o campo existente ``hashes`` (dicionário
livre de SHA-256 do registro) e um ARQUIVO PRÓPRIO, ``<execucao_uid>.ems3c1.json``, com o CONTEÚDO necessário para
reconstruir o que sustentou a execução (um hash sozinho não reconstrói nada):

* ``hashes_para_registro_3c1`` → ``{"entrada_3c1", "fontes_disponibilidade_3c1", "declaracao_3c1"?}`` a incluir em
  ``RegistroExecucaoEMS.hashes`` ANTES de selar: mudar uma fonte de disponibilidade (valor, procedência, justificativa,
  tipo) muda o hash ⇒ muda o selo do registro;
* ``AnexoExecucao3C1`` (selado): fontes de disponibilidade COMPLETAS (valor estático e procedência incluídos), a
  declaração de commitment completa (com seu vínculo ao instantâneo), a disponibilidade EFETIVA por passo executado e
  a sua origem (recalculada pela mesma regra do executor), o detalhe de H₂ por unidade e os eventos aplicados; refere o
  registro pelo ``execucao_uid`` e pelo ``selo``;
* ``verificar_anexo_3c1(anexo, registro)`` confere o selo do anexo, a identidade/selo do registro e RECALCULA os três
  hashes a partir do conteúdo do anexo, comparando-os com os gravados no registro.

Gravação EXCLUSIVA e atômica com o mesmo mecanismo do 3C-0 (``os.link``; sem hard link, reserva ``O_EXCL`` +
``os.replace``): nunca sobrescreve nem expõe arquivo parcial. Nenhuma telemetria é criada: a disponibilidade efetiva
vem só das fontes declaradas e da realização fornecida.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

from .. import FORMULACAO_3C1
from ..compromisso.contrato import EntradaCommitment3C1, hash_entrada_3c1
from ..diagnostics import Constatacao, ContratoInvalido, erro
from ..timegrid import ler_instante_utc
from .canonico import de_json, json_canonico, sha256
from .compromisso import (DeclaracaoCommitment3C1, DetalheH2Realizado, ExecutorAlgebricoCommitment3C1,
                          FonteDisponibilidadeExecucao, hash_declaracao)
from .execucao import PlanoDespacho, TrajetoriaExecutada, entorno_realizado
from .registro import RegistroExecucaoEMS, verificar_registro

VERSAO_ANEXO = 1
SUFIXO_ANEXO = ".ems3c1.json"
CHAVES_HASH_3C1 = ("entrada_3c1", "fontes_disponibilidade_3c1", "declaracao_3c1")


@dataclass(frozen=True)
class DisponibilidadeEfetivaPasso:
    uid: str
    indice_plano: int
    valor: int                                  # disponibilidade EFETIVA usada no passo
    fonte: str                                  # "observada" | "estatica_declarada"
    observado: float | None                     # valor da realização para o UID (None se não havia observação)


@dataclass(frozen=True)
class AnexoExecucao3C1:
    versao_anexo: int
    perfil: str
    execucao_uid: str
    selo_registro: str
    hash_entrada_3c1: str
    fontes_disponibilidade: tuple[FonteDisponibilidadeExecucao, ...]
    declaracao: DeclaracaoCommitment3C1 | None
    disponibilidade_efetiva: tuple[DisponibilidadeEfetivaPasso, ...]
    detalhe_h2: tuple[DetalheH2Realizado, ...]
    eventos_aplicados: dict[str, dict[str, int]]
    selo: str = ""


def _fontes_ordenadas(fontes) -> tuple[FonteDisponibilidadeExecucao, ...]:
    return tuple(fontes[k] for k in sorted(fontes)) if isinstance(fontes, dict) else tuple(fontes)


def hash_fontes_disponibilidade(fontes) -> str:
    return sha256(_fontes_ordenadas(fontes))


def hashes_para_registro_3c1(e3: EntradaCommitment3C1, fontes: dict,
                             declaracao: DeclaracaoCommitment3C1 | None = None) -> dict[str, str]:
    h = {"entrada_3c1": hash_entrada_3c1(e3), "fontes_disponibilidade_3c1": hash_fontes_disponibilidade(fontes)}
    if declaracao is not None:
        h["declaracao_3c1"] = hash_declaracao(declaracao)
    return h


def disponibilidade_efetiva_executada(e3: EntradaCommitment3C1, fontes: dict, plano: PlanoDespacho,
                                      traj: TrajetoriaExecutada, real) -> tuple[DisponibilidadeEfetivaPasso, ...]:
    """Recalcula, para cada passo EXECUTADO, a disponibilidade efetiva de cada unidade pela MESMA regra do executor."""
    ex = ExecutorAlgebricoCommitment3C1(e3, fontes)
    t0 = ler_instante_utc(plano.inicio_utc, "plano")[0]
    out: list[DisponibilidadeEfetivaPasso] = []
    for p in traj.passos:
        ent, c = entorno_realizado(real, (t0 + timedelta(seconds=plano.delta_s * p.indice_plano)).isoformat(),
                                   plano.delta_s)
        if c:
            raise ContratoInvalido(c)
        for uid in sorted(fontes):
            a, ca = ex.disponibilidade_efetiva(uid, ent)
            if ca:
                raise ContratoInvalido(ca)
            out.append(DisponibilidadeEfetivaPasso(uid, p.indice_plano, a, fontes[uid].fonte,
                                                   ent.get(f"{uid}|disponibilidade")))
    return tuple(out)


def selar_anexo_3c1(a: AnexoExecucao3C1) -> AnexoExecucao3C1:
    return replace(a, selo=sha256(replace(a, selo="")))


def montar_anexo_3c1(registro: RegistroExecucaoEMS, e3: EntradaCommitment3C1, plano: PlanoDespacho,
                     traj: TrajetoriaExecutada, real, fontes: dict, *, declaracao: DeclaracaoCommitment3C1 | None = None,
                     contabilidade=None) -> AnexoExecucao3C1:
    c = verificar_registro(registro)
    if not registro.selo:
        c.append(erro("registro_nao_selado", "registro.selo", "O anexo refere um registro SELADO."))
    esperado = hashes_para_registro_3c1(e3, fontes, declaracao)
    for k, v in esperado.items():
        if registro.hashes.get(k) != v:
            c.append(erro("registro_sem_hash_3c1", f"registro.hashes[{k}]",
                          "O registro 3C-0 deve carregar o hash 3C-1 correspondente ANTES de ser selado."))
    if c:
        raise ContratoInvalido(c)
    a = AnexoExecucao3C1(VERSAO_ANEXO, FORMULACAO_3C1, registro.execucao_uid, registro.selo, esperado["entrada_3c1"],
                         _fontes_ordenadas(fontes), declaracao,
                         disponibilidade_efetiva_executada(e3, fontes, plano, traj, real),
                         tuple(contabilidade.h2) if contabilidade is not None else (),
                         dict(contabilidade.eventos_aplicados) if contabilidade is not None else {})
    return selar_anexo_3c1(a)


def verificar_anexo_3c1(a: AnexoExecucao3C1, registro: RegistroExecucaoEMS) -> list[Constatacao]:
    out: list[Constatacao] = []
    if a.selo != sha256(replace(a, selo="")):
        out.append(erro("anexo_adulterado", "anexo.selo", "Selo não confere com o conteúdo do anexo."))
    if a.versao_anexo != VERSAO_ANEXO or a.perfil != FORMULACAO_3C1:
        out.append(erro("anexo_versao_incompativel", "anexo.versao_anexo", f"{a.versao_anexo!r} / {a.perfil!r}."))
    if a.execucao_uid != registro.execucao_uid or a.selo_registro != registro.selo:
        out.append(erro("anexo_de_outro_registro", "anexo.selo_registro",
                        "O anexo não pertence a este registro (execução ou selo divergentes)."))
    rec = {"entrada_3c1": a.hash_entrada_3c1, "fontes_disponibilidade_3c1": hash_fontes_disponibilidade(
        a.fontes_disponibilidade)}
    if a.declaracao is not None:
        rec["declaracao_3c1"] = hash_declaracao(a.declaracao)
    for k in CHAVES_HASH_3C1:
        if registro.hashes.get(k) != rec.get(k):
            out.append(erro("hash_3c1_divergente", f"registro.hashes[{k}]",
                            "Hash do registro ≠ hash recalculado do conteúdo do anexo (fonte de disponibilidade, "
                            "declaração ou entrada alterada?)."))
    return out


def gravar_anexo_3c1(diretorio: str | os.PathLike, a: AnexoExecucao3C1) -> Path:
    """Criação EXCLUSIVA e publicação atômica de ``<execucao_uid>.ems3c1.json`` (mesmo protocolo do 3C-0)."""
    import tempfile

    from .registro import _fsync_diretorio, _ja_existente, _publicar_sem_hard_link
    if a.selo != sha256(replace(a, selo="")):
        raise ContratoInvalido([erro("anexo_adulterado", "anexo.selo", "Anexo não selado ou adulterado.")])
    d = Path(diretorio)
    d.mkdir(parents=True, exist_ok=True)
    alvo = d / f"{a.execucao_uid}{SUFIXO_ANEXO}"
    texto = json_canonico(a)
    fd, nome_tmp = tempfile.mkstemp(prefix=f".{a.execucao_uid}.", suffix=".tmp", dir=d)
    tmp = Path(nome_tmp)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(texto.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, alvo)
        except FileExistsError:
            return _ja_existente(alvo, texto)
        except (OSError, NotImplementedError, AttributeError):
            _publicar_sem_hard_link(tmp, alvo, texto)
        _fsync_diretorio(d)
        return alvo
    finally:
        tmp.unlink(missing_ok=True)


def ler_anexo_3c1(caminho: str | os.PathLike) -> AnexoExecucao3C1:
    a = de_json(AnexoExecucao3C1, Path(caminho).read_text(encoding="utf-8"))
    if a.selo != sha256(replace(a, selo="")):
        raise ContratoInvalido([erro("anexo_adulterado", "anexo.selo", "Selo não confere com o conteúdo do anexo.")])
    return a


__all__ = ["AnexoExecucao3C1", "CHAVES_HASH_3C1", "DisponibilidadeEfetivaPasso", "SUFIXO_ANEXO", "VERSAO_ANEXO",
           "disponibilidade_efetiva_executada", "gravar_anexo_3c1", "hash_fontes_disponibilidade",
           "hashes_para_registro_3c1", "ler_anexo_3c1", "montar_anexo_3c1", "selar_anexo_3c1", "verificar_anexo_3c1"]
