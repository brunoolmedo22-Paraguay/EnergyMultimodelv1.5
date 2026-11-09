"""Persistência da evidência da missão MPC e retomada VERIFICADA (3C-2). Só biblioteca padrão.

Arquivos por missão (diretório escolhido pelo chamador; NUNCA o banco de uma microrrede — sem integração 3D):

* ``<execucao_uid>.ems3c0.json`` / ``<execucao_uid>.ems3c1.json`` — registro 3C-0 e anexo 3C-1 de cada janela
  executada (gravadores históricos ``gravar_registro``/``gravar_anexo_3c1``, esquemas inalterados);
* ``<missao>.p<NNNN>.janela.mpc3c2.json`` — ``RegistroJanelaMPC`` na posição NNNN da cadeia;
* ``<missao>.p<NNNN>.retomada.mpc3c2.json`` — ``PontoRetomada`` SELADO após cada registro (livro K6 completo,
  confirmações, comandos aplicados, estado conciliado, contador);
* ``<missao>.missao.mpc3c2.json`` e ``<missao>.livro.mpc3c2.json`` — registro da missão e livro final.

Gravação EXCLUSIVA e publicação atômica com o protocolo do 3C-0 (``os.link``; sem hard link, reserva ``O_EXCL`` +
``os.replace``): nunca sobrescreve nem expõe arquivo parcial; mesmo conteúdo ⇒ idempotente.

``retomar_controlador`` reconstrói um ``ControladorMPC`` a partir do diretório: verifica a cadeia de janelas, o selo
do último ponto de retomada, o vínculo ponto ↔ último registro (selo, estado final, contador), a identidade
(missão/microrrede/cenário/configuração) e REPRODUZ o livro de observações (classificações e cadeia). Qualquer
divergência ⇒ ``ContratoInvalido`` (nada é retomado).
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from ..diagnostics import ContratoInvalido, erro
from ..ponte.canonico import de_json, json_canonico, sha256
from ..ponte.execucao import EstadoMicrorrede
from ..ponte.registro import _fsync_diretorio, _ja_existente, _publicar_sem_hard_link, gravar_registro
from ..ponte.registro_3c1 import gravar_anexo_3c1
from . import ESQUEMA_MPC
from .contrato import hash_configuracao
from .entorno import ComandoIntervalo, ConfirmacaoAcao, hash_comando
from .observacoes import DocumentoLivro, LivroObservacoes
from .registro import RegistroJanelaMPC, RegistroMissaoMPC, selo_confere, verificar_cadeia_janelas


@dataclass(frozen=True)
class PontoRetomada:
    esquema: int
    missao_uid: str
    hash_configuracao: str
    posicao: int                              # posição do último registro de janela
    selo_ultima_janela: str
    k: int
    indice_janela: int
    situacao: str
    classe_falha: str | None
    estado: EstadoMicrorrede
    livro: DocumentoLivro
    confirmacoes: tuple[ConfirmacaoAcao, ...]
    comandos: tuple[ComandoIntervalo, ...]
    selo: str = ""


def comandos_aplicados(pt: PontoRetomada) -> tuple[ComandoIntervalo, ...]:
    """Comandos com confirmação 'aplicada' (para reconstituir a planta de ensaio na retomada)."""
    ok = {c.hash_comando for c in pt.confirmacoes if c.situacao == "aplicada"}
    return tuple(c for c in pt.comandos if hash_comando(c) in ok)


def gravar_exclusivo(diretorio, nome: str, texto: str) -> Path:
    d = Path(diretorio)
    d.mkdir(parents=True, exist_ok=True)
    alvo = d / nome
    fd, nome_tmp = tempfile.mkstemp(prefix=f".{nome}.", suffix=".tmp", dir=d)
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


def nome_janela(missao_uid: str, posicao: int) -> str:
    return f"{missao_uid}.p{posicao:04d}.janela.mpc3c2.json"


def nome_retomada(missao_uid: str, posicao: int) -> str:
    return f"{missao_uid}.p{posicao:04d}.retomada.mpc3c2.json"


def gravar_janela_e_retomada(diretorio, ctrl, r: RegistroJanelaMPC, reg0, anexo) -> None:
    if reg0 is not None:
        gravar_registro(diretorio, reg0)
    if anexo is not None:
        gravar_anexo_3c1(diretorio, anexo)
    m = ctrl.cfg.identidade.missao_uid
    gravar_exclusivo(diretorio, nome_janela(m, r.conteudo.posicao), json_canonico(r))
    p = PontoRetomada(ESQUEMA_MPC, m, hash_configuracao(ctrl.cfg), r.conteudo.posicao, r.selo, ctrl.k,
                      ctrl.relogio.indice_janela, ctrl.situacao, ctrl.classe_falha, ctrl.estado, ctrl.livro.exportar(),
                      tuple(sorted(ctrl._conf_por_cmd.values(), key=lambda x: (x.indice_global, x.hash_comando))),
                      tuple(ctrl._comandos))
    p = replace(p, selo=sha256(replace(p, selo="")))
    gravar_exclusivo(diretorio, nome_retomada(m, r.conteudo.posicao), json_canonico(p))


def gravar_missao(diretorio, rm: RegistroMissaoMPC, livro: LivroObservacoes) -> None:
    m = rm.conteudo.identidade.missao_uid
    gravar_exclusivo(diretorio, f"{m}.livro.mpc3c2.json", json_canonico(livro.exportar()))
    gravar_exclusivo(diretorio, f"{m}.missao.mpc3c2.json", json_canonico(rm))


def ler_janelas(diretorio, missao_uid: str) -> tuple[RegistroJanelaMPC, ...]:
    d = Path(diretorio)
    out = []
    p = 0
    while (d / nome_janela(missao_uid, p)).exists():
        out.append(de_json(RegistroJanelaMPC, (d / nome_janela(missao_uid, p)).read_text(encoding="utf-8")))
        p += 1
    return tuple(out)


def ler_missao(diretorio, missao_uid: str) -> tuple[RegistroMissaoMPC, tuple[RegistroJanelaMPC, ...], LivroObservacoes]:
    d = Path(diretorio)
    rm = de_json(RegistroMissaoMPC, (d / f"{missao_uid}.missao.mpc3c2.json").read_text(encoding="utf-8"))
    doc = de_json(DocumentoLivro, (d / f"{missao_uid}.livro.mpc3c2.json").read_text(encoding="utf-8"))
    return rm, ler_janelas(diretorio, missao_uid), LivroObservacoes.importar(doc)


def retomar_controlador(diretorio, cfg, modelo, provedor, resolvedor, fontes, **kw):
    """Reconstrói o controlador no último ponto de retomada VERIFICADO. A planta (modo 1) é responsabilidade do
    chamador (``EntornoSimuladoAlgebrico.reconstituir`` com ``PontoRetomada.comandos`` aplicados)."""
    from .orquestrador import ControladorMPC
    m = cfg.identidade.missao_uid
    regs = ler_janelas(diretorio, m)
    if not regs:
        raise ContratoInvalido([erro("sem_registros", "retomada", "Nenhum registro de janela no diretório.")])
    c = verificar_cadeia_janelas(regs, cfg)
    caminho = Path(diretorio) / nome_retomada(m, len(regs) - 1)
    pt = de_json(PontoRetomada, caminho.read_text(encoding="utf-8"))
    if not selo_confere(pt):
        c.append(erro("ponto_retomada_adulterado", caminho.name, "Selo não confere."))
    ult = regs[-1]
    if pt.missao_uid != m or pt.hash_configuracao != hash_configuracao(cfg):
        c.append(erro("identidade_divergente", "retomada", "Ponto de retomada de outra missão/configuração."))
    if pt.selo_ultima_janela != ult.selo or pt.posicao != ult.conteudo.posicao:
        c.append(erro("retomada_incoerente", "retomada", "Ponto não corresponde ao último registro de janela."))
    if ult.conteudo.estados and pt.estado != ult.conteudo.estados[-1]:
        c.append(erro("retomada_incoerente", "retomada.estado", "Estado ≠ estado final executado do último registro."))
    if pt.k != ult.conteudo.janela.k + ult.conteudo.intervalos_aplicados:
        c.append(erro("retomada_incoerente", "retomada.k", "Contador ≠ k + aplicados do último registro."))
    if pt.situacao not in ("em_andamento", "suspensa"):
        c.append(erro("missao_nao_retomavel", "retomada.situacao", f"{pt.situacao!r}: só em andamento/suspensa."))
    if c:
        raise ContratoInvalido(c)
    livro = LivroObservacoes.importar(pt.livro)
    ctrl = ControladorMPC(cfg, modelo, provedor, resolvedor, fontes, livro=livro, estado_inicial=pt.estado,
                          diretorio=diretorio, _registros=regs, _confirmacoes=pt.confirmacoes, _comandos=pt.comandos,
                          _k=pt.k, _j=pt.indice_janela, **kw)
    ctrl._g_conciliado = pt.k
    if pt.situacao == "suspensa":
        ctrl.situacao, ctrl.classe_falha = "suspensa", pt.classe_falha
    return ctrl, pt


__all__ = ["PontoRetomada", "comandos_aplicados", "gravar_exclusivo", "gravar_janela_e_retomada", "gravar_missao", "ler_janelas", "ler_missao",
           "nome_janela", "nome_retomada", "retomar_controlador"]
