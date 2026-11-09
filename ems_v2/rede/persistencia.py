"""Retomada VERIFICADA de uma missão MPC conectada (3C-3) — só biblioteca padrão.

Reutiliza a persistência 3C-2 sem alterá-la (gravação exclusiva/atômica, ``RegistroJanelaMPC``, ``PontoRetomada``,
leitura e verificação da cadeia, do livro × instantâneos comprometidos). Acrescenta, por janela executada, a
verificação INTEGRAL do registro 3C-0 + anexo 3C-3 (``verificar_artefatos_janela_3c3``, mesmas conferências do C-02
3C-2 com o anexo do perfil 3C-3) e, por ponto de retomada, o ``VinculoRede3C3`` selado (modelo 3C-3 e configuração de
rede da missão). Qualquer divergência ⇒ ``ContratoInvalido`` (nada é retomado).
"""
from __future__ import annotations

from pathlib import Path

from ..diagnostics import ContratoInvalido, erro
from ..mpc.contrato import hash_configuracao
from ..mpc.persistencia import PontoRetomada, _ler, _verificar_livro_contra_janelas, ler_janelas, nome_retomada
from ..mpc.registro import selo_confere, verificar_cadeia_janelas
from ..mpc.observacoes import LivroObservacoes
from ..ponte.canonico import sha256
from .contrato import hash_entrada_3c3
from .mpc import ControladorMPCConectado, VinculoRede3C3, hash_configuracao_rede, nome_vinculo
from .registro import AnexoExecucao3C3, SUFIXO_ANEXO_3C3, verificar_anexo_3c3


def verificar_artefatos_carregados_3c3(cfg, r, reg, anexo) -> list:
    """Verificação PURA (sem disco) dos artefatos históricos de UMA janela executada: registro 3C-0 (validade e selo),
    anexo 3C-3 (``verificar_anexo_3c3`` conjunta com o registro), selos comprometidos no ``RegistroJanelaMPC``,
    ``execucao_uid`` determinístico, identidade de origem/missão/posição, plano/entrada, plano de rede, estados,
    discretização, checkpoint, informação e custo. Usada pela retomada e pela auditoria INTEGRAL (C-02)."""
    from ..ponte.execucao import hash_plano
    from ..ponte.registro import RegistroExecucaoEMS, verificar_registro
    c = r.conteudo
    cam = f"janelas[{c.posicao}]"
    out = []

    def e(cod, msg):
        out.append(erro(cod, cam, msg))
    m = cfg.identidade.missao_uid
    uid = c.execucao_uid
    if uid != sha256({"missao": m, "posicao": c.posicao})[:32] or r.selo_registro_3c0 is None or r.selo_anexo_3c1 is None:
        e("execucao_da_janela_indeterminada", "Janela com plano sem execucao_uid determinístico ou sem selos 3C-0/3C-3.")
    if not isinstance(reg, RegistroExecucaoEMS):
        return out + [erro("registro_3c0_ausente", f"{cam}.registro_3c0", "Registro 3C-0 da janela ausente.")]
    if not isinstance(anexo, AnexoExecucao3C3):
        return out + [erro("anexo_3c3_ausente", f"{cam}.anexo_3c3", "Anexo 3C-3 da janela ausente.")]
    out += [erro("registro_3c0_adulterado", f"{cam}.registro_3c0", f"[{x.codigo}] {x.mensagem}")
            for x in verificar_registro(reg)]
    out += [erro("anexo_3c3_invalido", f"{cam}.anexo_3c3", f"[{x.codigo}] {x.mensagem}")
            for x in verificar_anexo_3c3(anexo, reg)]
    if reg.execucao_uid != uid or anexo.conteudo.execucao_uid != uid:
        e("artefato_de_outra_execucao", "Registro 3C-0/anexo de outra execução (UID ≠ da janela).")
    if reg.selo != r.selo_registro_3c0:
        e("selo_registro_3c0_divergente", "Selo do registro 3C-0 ≠ referenciado pela janela.")
    if anexo.selo != r.selo_anexo_3c1:
        e("selo_anexo_3c3_divergente", "Selo do anexo 3C-3 ≠ referenciado pela janela.")
    if reg.origem != cfg.identidade.referencia_origem() or reg.reproducao.get("missao_uid") != m or \
            reg.reproducao.get("posicao") != str(c.posicao) or reg.reproducao.get("indice_janela") != str(
                c.janela.indice_janela):
        e("artefato_de_outra_missao", "Identidade de origem/missão/posição do registro 3C-0 divergente.")
    p = reg.plano
    if p is None or hash_plano(p) != c.hash_plano or p.indice_fronteira_inicial != c.janela.k or \
            p.hash_entrada != c.hash_entrada_3c1 or anexo.conteudo.hash_entrada_3c3 != c.hash_entrada_3c1:
        e("plano_divergente", "Plano/entrada do registro 3C-0 ≠ janela.")
    if c.hash_plano_commitment != sha256(anexo.conteudo.plano_rede):
        e("plano_rede_divergente", "Plano de rede do anexo ≠ comprometido pela janela.")
    if not c.estados or reg.estado_inicial != c.estados[0] or reg.estado_final != c.estados[-1]:
        e("estados_divergentes", "Estados do registro 3C-0 ≠ estados executados da janela.")
    di = reg.discretizacao
    if (di.N, di.m, di.K_M, di.delta_s) != (c.janela.N_k, c.janela.m_k, cfg.malha.intervalos_missao, cfg.malha.delta_s):
        e("janela_divergente", "Discretização do registro 3C-0 ≠ janela.")
    if (reg.checkpoint_final.selo if reg.checkpoint_final else None) != c.selo_checkpoint_final:
        e("checkpoint_divergente", "Checkpoint final ≠ referenciado pela janela.")
    if reg.hashes.get("previsao") != c.hash_previsao or reg.hashes.get("instantaneo_decisao") != c.hash_instantaneo:
        e("informacao_divergente", "Previsão/instantâneo comprometidos ≠ janela.")
    if reg.custo_realizado != c.custos.realizado:
        e("custo_divergente", "Custo realizado do registro 3C-0 ≠ janela.")
    return out


def verificar_artefatos_janela_3c3(diretorio, cfg, r):
    c = r.conteudo
    cam = f"janelas[{c.posicao}]"
    if c.hash_plano is None:
        if r.selo_registro_3c0 is not None or r.selo_anexo_3c1 is not None or c.passos:
            raise ContratoInvalido([erro("artefato_referenciado_sem_plano", cam,
                                         "Janela sem plano não pode referenciar registro/anexo nem ter passos.")])
        return None, None
    from ..ponte.registro import RegistroExecucaoEMS
    if c.execucao_uid is None or r.selo_registro_3c0 is None or r.selo_anexo_3c1 is None:
        raise ContratoInvalido([erro("execucao_da_janela_indeterminada", cam,
                                     "Janela com plano sem execucao_uid determinístico ou sem selos 3C-0/3C-3.")])
    d = Path(diretorio)
    reg = _ler(RegistroExecucaoEMS, d / f"{c.execucao_uid}.ems3c0.json", "registro_3c0")
    anexo = _ler(AnexoExecucao3C3, d / f"{c.execucao_uid}{SUFIXO_ANEXO_3C3}", "anexo_3c3")
    out = verificar_artefatos_carregados_3c3(cfg, r, reg, anexo)
    if out:
        raise ContratoInvalido(out)
    return reg, anexo


def retomar_controlador_conectado(diretorio, cfg, modelo, provedor, resolvedor, fontes, configuracao_rede, **kw):
    m = cfg.identidade.missao_uid
    try:
        regs = ler_janelas(diretorio, m)
    except Exception as exc:  # noqa: BLE001
        raise ContratoInvalido([erro("registro_janela_ilegivel", "retomada", f"{type(exc).__name__}: {exc}")]) from None
    if not regs:
        raise ContratoInvalido([erro("sem_registros", "retomada", "Nenhum registro de janela no diretório.")])
    c = verificar_cadeia_janelas(regs, cfg)
    pos = len(regs) - 1
    pt = _ler(PontoRetomada, Path(diretorio) / nome_retomada(m, pos), "ponto_retomada")
    vr = _ler(VinculoRede3C3, Path(diretorio) / nome_vinculo(m, pos), "vinculo_rede")
    ult = regs[-1]
    if not selo_confere(pt):
        c.append(erro("ponto_retomada_adulterado", nome_retomada(m, pos), "Selo não confere."))
    if not selo_confere(vr):
        c.append(erro("vinculo_rede_adulterado", nome_vinculo(m, pos), "Selo não confere."))
    if pt.missao_uid != m or pt.hash_configuracao != hash_configuracao(cfg):
        c.append(erro("identidade_divergente", "retomada", "Ponto de retomada de outra missão/configuração."))
    if vr.missao_uid != m or vr.posicao != pos or vr.selo_ultima_janela != ult.selo:
        c.append(erro("retomada_incoerente", "retomada.vinculo_rede", "Vínculo de rede não corresponde ao último registro."))
    if vr.hash_modelo_3c3 != hash_entrada_3c3(modelo) or vr.hash_configuracao_rede != hash_configuracao_rede(
            configuracao_rede):
        c.append(erro("identidade_divergente", "retomada.vinculo_rede",
                      "Modelo 3C-3 (PCC/tarifas) ou configuração de rede ≠ os da missão (nenhum modo/tarifa trocado)."))
    if pt.selo_ultima_janela != ult.selo or pt.posicao != ult.conteudo.posicao:
        c.append(erro("retomada_incoerente", "retomada", "Ponto não corresponde ao último registro de janela."))
    if ult.conteudo.estados and pt.estado != ult.conteudo.estados[-1]:
        c.append(erro("retomada_incoerente", "retomada.estado", "Estado ≠ estado final executado do último registro."))
    if pt.k != ult.conteudo.janela.k + ult.conteudo.intervalos_aplicados:
        c.append(erro("retomada_incoerente", "retomada.k", "Contador ≠ k + aplicados do último registro."))
    if pt.situacao not in ("em_andamento", "suspensa"):
        c.append(erro("missao_nao_retomavel", "retomada.situacao", f"{pt.situacao!r}: só em andamento/suspensa."))
    hist0, hist3 = [], []
    for r in regs:
        try:
            r0, a3 = verificar_artefatos_janela_3c3(diretorio, cfg, r)
        except ContratoInvalido as exc:
            c += list(exc.constatacoes)
            continue
        if r0 is not None:
            hist0.append(r0)
            hist3.append(a3)
    if c:
        raise ContratoInvalido(c)
    livro = LivroObservacoes.importar(pt.livro)
    cl = _verificar_livro_contra_janelas(livro, regs)
    if cl:
        raise ContratoInvalido(cl)
    ctrl = ControladorMPCConectado(cfg, modelo, provedor, resolvedor, fontes, configuracao_rede, livro=livro,
                                   estado_inicial=pt.estado, diretorio=diretorio, _registros=regs,
                                   _confirmacoes=pt.confirmacoes, _comandos=pt.comandos, _k=pt.k, _j=pt.indice_janela,
                                   **kw)
    ctrl._g_conciliado = pt.k
    ctrl.registros_3c0, ctrl.anexos_3c3 = hist0, hist3
    if pt.situacao == "suspensa":
        ctrl.situacao, ctrl.classe_falha = "suspensa", pt.classe_falha
    return ctrl, pt


__all__ = ["retomar_controlador_conectado", "verificar_artefatos_carregados_3c3", "verificar_artefatos_janela_3c3"]
