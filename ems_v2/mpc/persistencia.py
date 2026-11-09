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
from ..timegrid import ler_instante_utc
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


def _ler(cls, caminho: Path, cod: str):
    """Lê um artefato persistido; ausência/JSON inválido/estrutura incompatível ⇒ ``ContratoInvalido`` estruturado."""
    if not caminho.exists():
        raise ContratoInvalido([erro(f"{cod}_ausente", caminho.name, "Artefato persistido ausente.")])
    try:
        return de_json(cls, caminho.read_text(encoding="utf-8"))
    except ContratoInvalido:
        raise
    except Exception as exc:  # noqa: BLE001 — conteúdo ilegível/adulterado: rejeição controlada
        raise ContratoInvalido([erro(f"{cod}_ilegivel", caminho.name, f"{type(exc).__name__}: {str(exc)[:200]}")]) from None


def verificar_artefatos_janela(diretorio, cfg, r: RegistroJanelaMPC):
    """C-02: verificação INTEGRAL dos artefatos históricos de UMA janela. Janela que executou plano ⇒ registro 3C-0
    ``<execucao_uid>.ems3c0.json`` (selo e validade, ``verificar_registro``) + anexo ``<execucao_uid>.ems3c1.json``
    (``verificar_anexo_3c1`` CONJUNTA com o registro) + coerência com o ``RegistroJanelaMPC`` (selos referenciados,
    execução, missão/posição, identidade de origem, janela, plano, estados, checkpoint, previsão, instantâneo, entrada,
    intervalos aplicados e custo realizado). Janela SEM plano: nenhum artefato é exigido (e nenhum selo pode ser
    referenciado). Devolve ``(registro_3c0, anexo)`` ou ``(None, None)``; qualquer divergência ⇒ ``ContratoInvalido``."""
    from ..ponte.execucao import hash_plano
    from ..ponte.registro import RegistroExecucaoEMS, verificar_registro
    from ..ponte.registro_3c1 import AnexoExecucao3C1, verificar_anexo_3c1
    c = r.conteudo
    cam = f"janelas[{c.posicao}]"
    if c.hash_plano is None:
        if r.selo_registro_3c0 is not None or r.selo_anexo_3c1 is not None or c.passos:
            raise ContratoInvalido([erro("artefato_referenciado_sem_plano", cam,
                                         "Janela sem plano não pode referenciar registro 3C-0/anexo 3C-1 nem ter passos.")])
        return None, None
    m = cfg.identidade.missao_uid
    uid = c.execucao_uid
    esperado = sha256({"missao": m, "posicao": c.posicao})[:32]
    if uid != esperado or r.selo_registro_3c0 is None or r.selo_anexo_3c1 is None:
        raise ContratoInvalido([erro("execucao_da_janela_indeterminada", cam,
                                     "Janela com plano sem execucao_uid determinístico ou sem selos 3C-0/3C-1.")])
    d = Path(diretorio)
    reg = _ler(RegistroExecucaoEMS, d / f"{uid}.ems3c0.json", "registro_3c0")
    out = [erro("registro_3c0_adulterado", f"{cam}.registro_3c0", f"[{x.codigo}] {x.mensagem}")
           for x in verificar_registro(reg)]
    anexo = _ler(AnexoExecucao3C1, d / f"{uid}.ems3c1.json", "anexo_3c1")
    out += [erro("anexo_3c1_invalido", f"{cam}.anexo_3c1", f"[{x.codigo}] {x.mensagem}")
            for x in verificar_anexo_3c1(anexo, reg)]
    e = lambda cod, msg: out.append(erro(cod, cam, msg))  # noqa: E731
    if reg.selo != r.selo_registro_3c0:
        e("selo_registro_3c0_divergente", "Selo do registro 3C-0 ≠ referenciado pelo RegistroJanelaMPC.")
    if anexo.selo != r.selo_anexo_3c1:
        e("selo_anexo_3c1_divergente", "Selo do anexo 3C-1 ≠ referenciado pelo RegistroJanelaMPC.")
    if reg.execucao_uid != uid or anexo.conteudo.execucao_uid != uid:
        e("artefato_de_outra_execucao", "Registro/anexo de outra execução.")
    if reg.origem != cfg.identidade.referencia_origem() or reg.reproducao.get("missao_uid") != m or \
            reg.reproducao.get("posicao") != str(c.posicao) or reg.reproducao.get("indice_janela") != str(
                c.janela.indice_janela):
        e("artefato_de_outra_missao", "Identidade de origem/missão/posição do registro 3C-0 divergente.")
    p = reg.plano
    if p is None or hash_plano(p) != c.hash_plano or p.indice_fronteira_inicial != c.janela.k or \
            p.hash_entrada != c.hash_entrada_3c1 or anexo.conteudo.hash_entrada_3c1 != c.hash_entrada_3c1:
        e("plano_divergente", "Plano/entrada do registro 3C-0 ≠ janela.")
    if reg.estado_inicial != c.estados[0] or reg.estado_final != c.estados[-1]:
        e("estados_divergentes", "Estados inicial/final do registro 3C-0 ≠ estados executados da janela.")
    di = reg.discretizacao
    if (di.N, di.m, di.K_M, di.delta_s) != (c.janela.N_k, c.janela.m_k, cfg.malha.intervalos_missao, cfg.malha.delta_s):
        e("janela_divergente", "Discretização do registro 3C-0 ≠ janela.")
    if (reg.checkpoint_final.selo if reg.checkpoint_final else None) != c.selo_checkpoint_final:
        e("checkpoint_divergente", "Checkpoint final do registro 3C-0 ≠ referenciado pela janela.")
    if reg.hashes.get("previsao") != c.hash_previsao or reg.hashes.get("instantaneo_decisao") != c.hash_instantaneo:
        e("informacao_divergente", "Previsão/instantâneo comprometidos no registro 3C-0 ≠ janela.")
    if reg.custo_realizado != c.custos.realizado or (reg.custo_realizado is not None and
                                                    reg.custo_realizado.intervalos != c.intervalos_aplicados):
        e("custo_divergente", "Custo realizado/intervalos aplicados do registro 3C-0 ≠ janela.")
    if out:
        raise ContratoInvalido(out)
    return reg, anexo


def _verificar_livro_contra_janelas(livro: LivroObservacoes, regs) -> list:
    """O livro restaurado deve reproduzir os instantâneos (decisão e conciliações) comprometidos por TODAS as janelas."""
    from .observacoes import genese_livro, instantaneo_de_prefixo
    ent = livro.entradas
    out = []
    for r in regs:
        c = r.conteudo
        for corte, h, n in ((c.instante_decisao_utc, c.hash_instantaneo, c.n_entradas_instantaneo),) + c.conciliacoes:
            if n > len(ent) or instantaneo_de_prefixo(livro.missao_uid, livro.microrrede_uid, ler_instante_utc(
                    corte, "c")[0].isoformat(), ent[:n], ent[n - 1].hash_cadeia if n else genese_livro(
                    livro.missao_uid, livro.microrrede_uid)).hash != h:
                out.append(erro("livro_incoerente_com_janelas", f"janelas[{c.posicao}]",
                                f"Instantâneo em {corte} não reproduzido pelo livro do ponto de retomada."))
    return out


def retomar_controlador(diretorio, cfg, modelo, provedor, resolvedor, fontes, **kw):
    """Reconstrói o controlador no último ponto de retomada VERIFICADO (C-02: cadeia MPC + artefatos 3C-0/3C-1 de TODAS
    as janelas executadas + livro × instantâneos comprometidos + ponto de retomada). Restaura os históricos
    ``registros_3c0``/``anexos_3c1``. A planta (modo 1) é responsabilidade do chamador
    (``EntornoSimuladoAlgebrico.reconstituir`` com ``comandos_aplicados(ponto)``)."""
    from .orquestrador import ControladorMPC
    m = cfg.identidade.missao_uid
    try:
        regs = ler_janelas(diretorio, m)
    except Exception as exc:  # noqa: BLE001
        raise ContratoInvalido([erro("registro_janela_ilegivel", "retomada", f"{type(exc).__name__}: {exc}")]) from None
    if not regs:
        raise ContratoInvalido([erro("sem_registros", "retomada", "Nenhum registro de janela no diretório.")])
    c = verificar_cadeia_janelas(regs, cfg)
    pt = _ler(PontoRetomada, Path(diretorio) / nome_retomada(m, len(regs) - 1), "ponto_retomada")
    if not selo_confere(pt):
        c.append(erro("ponto_retomada_adulterado", nome_retomada(m, len(regs) - 1), "Selo não confere."))
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
    hist0, hist1 = [], []
    for r in regs:
        try:
            r0, a1 = verificar_artefatos_janela(diretorio, cfg, r)
        except ContratoInvalido as exc:
            c += list(exc.constatacoes)
            continue
        if r0 is not None:
            hist0.append(r0)
            hist1.append(a1)
    if c:
        raise ContratoInvalido(c)
    livro = LivroObservacoes.importar(pt.livro)
    cl = _verificar_livro_contra_janelas(livro, regs)
    if cl:
        raise ContratoInvalido(cl)
    ctrl = ControladorMPC(cfg, modelo, provedor, resolvedor, fontes, livro=livro, estado_inicial=pt.estado,
                          diretorio=diretorio, _registros=regs, _confirmacoes=pt.confirmacoes, _comandos=pt.comandos,
                          _k=pt.k, _j=pt.indice_janela, **kw)
    ctrl._g_conciliado = pt.k
    ctrl.registros_3c0, ctrl.anexos_3c1 = hist0, hist1          # históricos restaurados (nenhuma evidência perdida)
    if pt.situacao == "suspensa":
        ctrl.situacao, ctrl.classe_falha = "suspensa", pt.classe_falha
    return ctrl, pt


__all__ = ["PontoRetomada", "comandos_aplicados", "verificar_artefatos_janela", "gravar_exclusivo", "gravar_janela_e_retomada", "gravar_missao", "ler_janelas", "ler_missao",
           "nome_janela", "nome_retomada", "retomar_controlador"]
