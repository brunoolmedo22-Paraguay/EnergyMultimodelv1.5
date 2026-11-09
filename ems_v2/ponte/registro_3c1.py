"""Anexo de evidência 3C-1 ao registro de execução 3C-0 (B-02, B-03) — só biblioteca padrão.

O esquema histórico ``RegistroExecucaoEMS`` (3C-0) NÃO muda. A ligação usa o campo existente ``hashes`` (dicionário
livre de SHA-256 do registro) e um ARQUIVO PRÓPRIO, ``<execucao_uid>.ems3c1.json``, com o CONTEÚDO necessário para
reconstruir o que sustentou a execução (um hash sozinho não reconstrói nada).

Protocolo em duas fases (B-03; resolve a dependência circular anexo ↔ registro):

1. ``preparar_conteudo_anexo_3c1`` monta o CONTEÚDO VERIFICÁVEL (``ConteudoAnexo3C1``): identidade da execução, hash da
   entrada 3C-1, fontes de disponibilidade COMPLETAS (valor estático e procedência), declaração de commitment
   completa, disponibilidade EFETIVA por passo executado (recalculada pela regra do executor), detalhe de H₂ por
   unidade e eventos aplicados. NÃO contém o selo do registro nem selo próprio;
2. ``hashes_para_registro_3c1(conteudo)`` → ``{"entrada_3c1", "fontes_disponibilidade_3c1", "declaracao_3c1"?,
   "anexo_3c1_conteudo"}`` a incluir em ``RegistroExecucaoEMS.hashes`` ANTES de selar o registro: o registro passa a
   COMPROMETER o conteúdo íntegro do anexo (``anexo_3c1_conteudo`` = SHA-256 do JSON canônico do conteúdo);
3. ``montar_anexo_3c1(registro_selado, conteudo)`` acrescenta a VINCULAÇÃO (``selo_registro``) e o selo do anexo.

``verificar_anexo_3c1(anexo, registro)`` confere: integridade do REGISTRO (``verificar_registro``: validade e selo);
selo do anexo; identidade e selo do registro referido; o compromisso ``anexo_3c1_conteudo`` RECALCULADO do conteúdo;
os hashes de entrada/fontes/declaração; e a coerência do conteúdo com os metadados verificáveis do registro (UID da
execução, hash da entrada no plano, unidades do plano, número e índices dos passos executados, paridade partidas ×
paradas com os estados inicial/final, H₂ do custo realizado, vínculo da declaração × origem).

**SHA-256 não é assinatura:** detecta alteração em relação a uma referência CONFIÁVEL (o registro selado conservado);
quem puder reescrever e re-selar registro E anexo juntos não é detectado. Autenticidade de origem exigiria assinatura
digital (fora do escopo do 3C-1).

Gravação EXCLUSIVA e atômica com o mesmo mecanismo do 3C-0 (``os.link``; sem hard link, reserva ``O_EXCL`` +
``os.replace``): nunca sobrescreve nem expõe arquivo parcial. Nenhuma telemetria é criada: a disponibilidade efetiva
vem só das fontes declaradas e da realização fornecida.
"""
from __future__ import annotations

import math
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

VERSAO_ANEXO = 2                                 # 2 = conteúdo verificável separado e comprometido no registro (B-03)
SUFIXO_ANEXO = ".ems3c1.json"
CHAVE_CONTEUDO = "anexo_3c1_conteudo"
CHAVES_HASH_3C1 = ("entrada_3c1", "fontes_disponibilidade_3c1", "declaracao_3c1", CHAVE_CONTEUDO)


@dataclass(frozen=True)
class DisponibilidadeEfetivaPasso:
    uid: str
    indice_plano: int
    valor: int                                  # disponibilidade EFETIVA usada no passo
    fonte: str                                  # "observada" | "estatica_declarada"
    observado: float | None                     # valor da realização para o UID (None se não havia observação)


@dataclass(frozen=True)
class ConteudoAnexo3C1:
    """Conteúdo VERIFICÁVEL do anexo (B-03): tudo o que o registro compromete por ``anexo_3c1_conteudo``. Não contém
    campos de vinculação (selo do registro) nem selo próprio."""
    versao_anexo: int
    perfil: str
    execucao_uid: str
    hash_entrada_3c1: str
    fontes_disponibilidade: tuple[FonteDisponibilidadeExecucao, ...]
    declaracao: DeclaracaoCommitment3C1 | None
    disponibilidade_efetiva: tuple[DisponibilidadeEfetivaPasso, ...]
    detalhe_h2: tuple[DetalheH2Realizado, ...]
    eventos_aplicados: dict[str, dict[str, int]]


@dataclass(frozen=True)
class AnexoExecucao3C1:
    conteudo: ConteudoAnexo3C1
    selo_registro: str                          # vinculação ao registro selado que compromete o conteúdo
    selo: str = ""                              # integridade do próprio arquivo (conteúdo + vinculação)


def _fontes_ordenadas(fontes) -> tuple[FonteDisponibilidadeExecucao, ...]:
    return tuple(fontes[k] for k in sorted(fontes)) if isinstance(fontes, dict) else tuple(fontes)


def hash_fontes_disponibilidade(fontes) -> str:
    return sha256(_fontes_ordenadas(fontes))


def hash_conteudo_anexo_3c1(c: ConteudoAnexo3C1) -> str:
    """SHA-256 do JSON canônico (determinístico: chaves ordenadas, sem NaN) do conteúdo verificável."""
    return sha256(c)


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


def preparar_conteudo_anexo_3c1(e3: EntradaCommitment3C1, plano: PlanoDespacho, traj: TrajetoriaExecutada, real,
                                fontes: dict, *, declaracao: DeclaracaoCommitment3C1 | None = None,
                                contabilidade=None) -> ConteudoAnexo3C1:
    """Fase 1 (antes de selar o registro): conteúdo verificável da evidência 3C-1."""
    return ConteudoAnexo3C1(VERSAO_ANEXO, FORMULACAO_3C1, traj.execucao_uid, hash_entrada_3c1(e3),
                            _fontes_ordenadas(fontes), declaracao,
                            disponibilidade_efetiva_executada(e3, fontes, plano, traj, real),
                            tuple(contabilidade.h2) if contabilidade is not None else (),
                            dict(contabilidade.eventos_aplicados) if contabilidade is not None else {})


def hashes_para_registro_3c1(conteudo: ConteudoAnexo3C1) -> dict[str, str]:
    """Fase 2: compromissos a gravar em ``RegistroExecucaoEMS.hashes`` ANTES de selar o registro (todos derivados do
    MESMO conteúdo verificável)."""
    h = {"entrada_3c1": conteudo.hash_entrada_3c1,
         "fontes_disponibilidade_3c1": hash_fontes_disponibilidade(conteudo.fontes_disponibilidade),
         CHAVE_CONTEUDO: hash_conteudo_anexo_3c1(conteudo)}
    if conteudo.declaracao is not None:
        h["declaracao_3c1"] = hash_declaracao(conteudo.declaracao)
    return h


def selar_anexo_3c1(a: AnexoExecucao3C1) -> AnexoExecucao3C1:
    return replace(a, selo=sha256(replace(a, selo="")))


def _coerencia_com_registro(c: ConteudoAnexo3C1, r: RegistroExecucaoEMS) -> list[Constatacao]:
    """Item 8 (B-03): conferências do conteúdo contra os metadados VERIFICÁVEIS do registro (o registro não contém as
    séries completas; o que não pode ser derivado dele fica coberto pelo compromisso ``anexo_3c1_conteudo``)."""
    out: list[Constatacao] = []

    def e(cod, cam, msg):
        out.append(erro(cod, cam, msg))
    if c.execucao_uid != r.execucao_uid:
        e("anexo_de_outra_execucao", "anexo.conteudo.execucao_uid", "UID da execução ≠ registro.")
    p = r.plano
    if p is None:
        e("registro_sem_plano", "registro.plano", "Registro sem plano: o anexo 3C-1 não é verificável.")
        return out
    if p.hash_entrada != c.hash_entrada_3c1 or p.versao_formulacao != FORMULACAO_3C1:
        e("anexo_de_outra_entrada", "anexo.conteudo.hash_entrada_3c1",
          "Hash da entrada 3C-1 ≠ hash da entrada do plano do registro (ou plano não 3C-1).")
    gers = {x.uid for x in p.consignas if x.grandeza == "u"}
    fontes = [f.uid for f in c.fontes_disponibilidade]
    if sorted(fontes) != sorted(gers) or len(set(fontes)) != len(fontes):
        e("anexo_unidades_incoerentes", "anexo.conteudo.fontes_disponibilidade",
          f"Unidades das fontes {sorted(fontes)} ≠ unidades geradoras do plano {sorted(gers)}.")
    ei, ef = r.estado_inicial, r.estado_final
    n = None
    if ei is not None and ef is not None:
        n = ef.indice_fronteira - ei.indice_fronteira
        cur0 = ei.indice_fronteira - p.indice_fronteira_inicial
        if r.custo_realizado is not None and r.custo_realizado.intervalos != n:
            e("anexo_registro_inconsistente", "registro.custo_realizado.intervalos", "Intervalos ≠ fronteiras executadas.")
        esperado = {(u, j) for u in gers for j in range(cur0, cur0 + n)}
        visto = [(x.uid, x.indice_plano) for x in c.disponibilidade_efetiva]
        if set(visto) != esperado or len(visto) != len(esperado):
            e("anexo_passos_incoerentes", "anexo.conteudo.disponibilidade_efetiva",
              f"Passos/unidades da disponibilidade efetiva ≠ {n} intervalo(s) executado(s) × unidades do plano.")
        for x in c.disponibilidade_efetiva:
            if x.valor not in (0, 1) or isinstance(x.valor, bool) or x.fonte not in ("observada", "estatica_declarada"):
                e("anexo_disponibilidade_invalida", f"anexo.conteudo.disponibilidade_efetiva[{x.uid}:{x.indice_plano}]",
                  "Valor/fonte inválidos.")
        for u, ev in c.eventos_aplicados.items():
            gi, gf = ei.gerador(u), ef.gerador(u)
            if u not in gers or gi is None or gf is None:
                e("anexo_unidades_incoerentes", f"anexo.conteudo.eventos_aplicados[{u}]", "Unidade fora do plano.")
                continue
            if ev.get("partidas", 0) - ev.get("paradas", 0) != int(gf.ligado) - int(gi.ligado) or \
                    ev.get("partidas", 0) + ev.get("paradas", 0) > n or min(ev.get("partidas", 0), ev.get("paradas", 0)) < 0:
                e("anexo_eventos_incoerentes", f"anexo.conteudo.eventos_aplicados[{u}]",
                  "Partidas − paradas ≠ variação do estado entre as fronteiras inicial e final do registro (ou > n).")
    for h in c.detalhe_h2:
        ev = c.eventos_aplicados.get(h.uid, {"partidas": 0, "paradas": 0})
        if h.uid not in gers or (h.partidas, h.paradas) != (ev.get("partidas", 0), ev.get("paradas", 0)):
            e("anexo_h2_incoerente", f"anexo.conteudo.detalhe_h2[{h.uid}]",
              "Detalhe de H₂ de unidade fora do plano ou com eventos ≠ eventos aplicados.")
    if c.detalhe_h2 and r.custo_realizado is not None:
        comp = {x.termo: x.valor_R for x in r.custo_realizado.componentes}
        tot = math.fsum(h.custo_continuo_R + h.custo_eventos_R for h in c.detalhe_h2)
        if "combustivel_h2" not in comp or abs(comp["combustivel_h2"] - tot) > 1e-9 * max(1.0, abs(tot)):
            e("anexo_h2_incoerente", "anexo.conteudo.detalhe_h2",
              f"Σ H₂ do anexo (R$ {tot!r}) ≠ componente combustivel_h2 do custo realizado do registro.")
    d = c.declaracao
    if d is not None:
        o, v = r.origem, d.vinculo
        if (v.inventario.microrrede_uid, v.inventario.incarnacao, v.inventario.revisao_config,
                v.inventario.impressao_config, v.inventario.impressao_inventario, v.cenario_uid, v.versao_cenario,
                v.impressao_cenario) != (o.microrrede_uid, o.incarnacao, o.revisao_config, o.impressao_config,
                                         o.impressao_inventario, o.cenario_uid, o.versao_cenario, o.impressao_cenario):
            e("anexo_declaracao_de_outra_origem", "anexo.conteudo.declaracao.vinculo",
              "Vínculo da declaração ≠ origem (microrrede/revisão/cenário/versão) do registro.")
    return out


def montar_anexo_3c1(registro: RegistroExecucaoEMS, conteudo: ConteudoAnexo3C1) -> AnexoExecucao3C1:
    """Fase 3: vincula o conteúdo ao registro SELADO que o compromete e sela o anexo."""
    c = verificar_registro(registro)
    if not registro.selo:
        c.append(erro("registro_nao_selado", "registro.selo", "O anexo refere um registro SELADO."))
    for k, v in hashes_para_registro_3c1(conteudo).items():
        if registro.hashes.get(k) != v:
            c.append(erro("registro_sem_hash_3c1", f"registro.hashes[{k}]",
                          "O registro 3C-0 deve comprometer o conteúdo 3C-1 (hashes) ANTES de ser selado."))
    c += _coerencia_com_registro(conteudo, registro)
    if c:
        raise ContratoInvalido(c)
    return selar_anexo_3c1(AnexoExecucao3C1(conteudo, registro.selo))


def verificar_anexo_3c1(a: AnexoExecucao3C1, registro: RegistroExecucaoEMS) -> list[Constatacao]:
    """Verificação CONJUNTA registro + anexo (B-03). Lista vazia = íntegros e coerentes ENTRE SI em relação ao registro
    fornecido como referência confiável (não é prova de autoria: SHA-256 não é assinatura)."""
    out: list[Constatacao] = list(verificar_registro(registro))
    if not isinstance(a, AnexoExecucao3C1) or not isinstance(a.conteudo, ConteudoAnexo3C1):
        return out + [erro("anexo_invalido", "anexo", "Estrutura de anexo 3C-1 inválida.")]
    c = a.conteudo
    if a.selo != sha256(replace(a, selo="")):
        out.append(erro("anexo_adulterado", "anexo.selo", "Selo não confere com o conteúdo do anexo."))
    if c.versao_anexo != VERSAO_ANEXO or c.perfil != FORMULACAO_3C1:
        out.append(erro("anexo_versao_incompativel", "anexo.conteudo.versao_anexo", f"{c.versao_anexo!r} / {c.perfil!r}."))
    if c.execucao_uid != registro.execucao_uid or a.selo_registro != registro.selo:
        out.append(erro("anexo_de_outro_registro", "anexo.selo_registro",
                        "O anexo não pertence a este registro (execução ou selo divergentes)."))
    if CHAVE_CONTEUDO not in registro.hashes:
        out.append(erro("registro_sem_compromisso_do_anexo", f"registro.hashes[{CHAVE_CONTEUDO}]",
                        "O registro não compromete o conteúdo do anexo: evidência 3C-1 não verificável."))
    rec = hashes_para_registro_3c1(c)
    for k in CHAVES_HASH_3C1:
        if registro.hashes.get(k) != rec.get(k):
            cod = "conteudo_anexo_divergente" if k == CHAVE_CONTEUDO else "hash_3c1_divergente"
            out.append(erro(cod, f"registro.hashes[{k}]",
                            "Hash comprometido no registro ≠ hash recalculado do conteúdo do anexo (conteúdo alterado?)."))
    out += _coerencia_com_registro(c, registro)
    return out


def gravar_anexo_3c1(diretorio: str | os.PathLike, a: AnexoExecucao3C1) -> Path:
    """Criação EXCLUSIVA e publicação atômica de ``<execucao_uid>.ems3c1.json`` (mesmo protocolo do 3C-0)."""
    import tempfile

    from .registro import _fsync_diretorio, _ja_existente, _publicar_sem_hard_link
    if a.selo != sha256(replace(a, selo="")):
        raise ContratoInvalido([erro("anexo_adulterado", "anexo.selo", "Anexo não selado ou adulterado.")])
    d = Path(diretorio)
    d.mkdir(parents=True, exist_ok=True)
    alvo = d / f"{a.conteudo.execucao_uid}{SUFIXO_ANEXO}"
    texto = json_canonico(a)
    fd, nome_tmp = tempfile.mkstemp(prefix=f".{a.conteudo.execucao_uid}.", suffix=".tmp", dir=d)
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


__all__ = ["AnexoExecucao3C1", "CHAVE_CONTEUDO", "CHAVES_HASH_3C1", "ConteudoAnexo3C1", "DisponibilidadeEfetivaPasso",
           "SUFIXO_ANEXO", "VERSAO_ANEXO", "disponibilidade_efetiva_executada", "gravar_anexo_3c1",
           "hash_conteudo_anexo_3c1", "hash_fontes_disponibilidade", "hashes_para_registro_3c1", "ler_anexo_3c1",
           "montar_anexo_3c1", "preparar_conteudo_anexo_3c1", "selar_anexo_3c1", "verificar_anexo_3c1"]
