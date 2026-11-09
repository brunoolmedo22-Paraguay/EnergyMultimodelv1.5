"""Anexo de evidência 3C-3 ao registro de execução 3C-0 — só biblioteca padrão.

Mesmo protocolo em três fases do anexo 3C-1 (B-03), sem alterar nenhum esquema histórico:

1. ``preparar_conteudo_anexo_3c3`` monta o CONTEÚDO VERIFICÁVEL (``ConteudoAnexo3C3``): identidade da execução, hash da
   entrada 3C-3 e do núcleo 3C-1, plano de rede COMPLETO (intercâmbio programado + commitment planejado), política de
   ajuste COMPLETA (tipo, injeção renovável, liquidação, perfis de liquidação), fontes de disponibilidade das unidades,
   disponibilidade efetiva por passo (regra do executor 3C-1), evidência do PCC por passo (programado, observado,
   exigido, realizado, medido, renovável consigna × efetiva, ajuste aplicado), liquidação por passo, desvios, detalhe
   de H₂ e eventos aplicados;
2. ``hashes_para_registro_3c3(conteudo)`` → compromissos a gravar em ``RegistroExecucaoEMS.hashes`` ANTES de selar o
   registro (``entrada_3c3``, ``plano_rede_3c3``, ``politica_ajuste_3c3``, ``fontes_disponibilidade_3c3``,
   ``anexo_3c3_conteudo``);
3. ``montar_anexo_3c3(registro_selado, conteudo)`` acrescenta a vinculação (``selo_registro``) e sela.

``verificar_anexo_3c3`` confere integridade do registro, selo do anexo, vinculação, os compromissos recalculados e a
coerência do conteúdo com o registro (formulação 3C-3 do plano, hash do plano, passos executados, Σ do gasto/crédito
liquidados = componentes do custo realizado, paridade de eventos, H₂). Uma execução 3C-3 NUNCA produz anexo 3C-1:
o verificador 3C-1 exige plano ``v1.1-3C-1`` (nenhum perfil se faz passar por outro).

**SHA-256 não é assinatura:** detecta alteração frente a um registro selado CONFIÁVEL (brecha K10 herdada).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

from ..diagnostics import Constatacao, ContratoInvalido, erro
from ..ponte.canonico import de_json, json_canonico, sha256
from ..ponte.compromisso import DetalheH2Realizado, FonteDisponibilidadeExecucao
from ..ponte.execucao import PlanoDespacho, TrajetoriaExecutada, hash_plano
from ..ponte.registro import RegistroExecucaoEMS, verificar_registro
from ..ponte.registro_3c1 import (DisponibilidadeEfetivaPasso, disponibilidade_efetiva_executada,
                                  hash_fontes_disponibilidade)
from . import FORMULACAO_3C3
from .contrato import EntradaRede3C3, hash_entrada_3c3
from .execucao import (ContabilidadeRealizada3C3, DesvioIntercambio, LiquidacaoPasso, PlanoRede3C3, PoliticaAjustePCC,
                       RegistroPassoPCC, hash_plano_rede, hash_politica_ajuste)

VERSAO_ANEXO_3C3 = 1
SUFIXO_ANEXO_3C3 = ".ems3c3.json"
CHAVE_CONTEUDO_3C3 = "anexo_3c3_conteudo"
CHAVES_HASH_3C3 = ("entrada_3c3", "plano_rede_3c3", "politica_ajuste_3c3", "fontes_disponibilidade_3c3",
                   CHAVE_CONTEUDO_3C3)


@dataclass(frozen=True)
class ConteudoAnexo3C3:
    versao_anexo: int
    perfil: str
    execucao_uid: str
    hash_entrada_3c3: str
    hash_nucleo_3c1: str
    plano_rede: PlanoRede3C3
    politica_ajuste: PoliticaAjustePCC
    fontes_disponibilidade: tuple[FonteDisponibilidadeExecucao, ...]
    disponibilidade_efetiva: tuple[DisponibilidadeEfetivaPasso, ...]
    passos_pcc: tuple[RegistroPassoPCC, ...]
    liquidacao: tuple[LiquidacaoPasso, ...]
    desvios: tuple[DesvioIntercambio, ...]
    detalhe_h2: tuple[DetalheH2Realizado, ...]
    eventos_aplicados: dict[str, dict[str, int]]
    hash_tarifas_liquidacao: dict[str, str]


@dataclass(frozen=True)
class AnexoExecucao3C3:
    conteudo: ConteudoAnexo3C3
    selo_registro: str
    selo: str = ""


def preparar_conteudo_anexo_3c3(e: EntradaRede3C3, plano: PlanoDespacho, pr: PlanoRede3C3, traj: TrajetoriaExecutada,
                                real, fontes: dict, politica: PoliticaAjustePCC, passos_pcc,
                                contab: ContabilidadeRealizada3C3) -> ConteudoAnexo3C3:
    from ..compromisso.contrato import hash_entrada_3c1
    fo = tuple(fontes[k] for k in sorted(fontes))
    return ConteudoAnexo3C3(VERSAO_ANEXO_3C3, FORMULACAO_3C3, traj.execucao_uid, hash_entrada_3c3(e),
                            hash_entrada_3c1(e.compromisso), pr, politica, fo,
                            disponibilidade_efetiva_executada(e.compromisso, fontes, plano, traj, real),
                            tuple(passos_pcc), tuple(contab.liquidacao), tuple(contab.desvios), tuple(contab.h2),
                            dict(contab.eventos_aplicados), dict(contab.hash_tarifas_liquidacao))


def hashes_para_registro_3c3(c: ConteudoAnexo3C3) -> dict[str, str]:
    return {"entrada_3c3": c.hash_entrada_3c3, "plano_rede_3c3": hash_plano_rede(c.plano_rede),
            "politica_ajuste_3c3": hash_politica_ajuste(c.politica_ajuste),
            "fontes_disponibilidade_3c3": hash_fontes_disponibilidade(c.fontes_disponibilidade),
            CHAVE_CONTEUDO_3C3: sha256(c)}


def _coerencia(c: ConteudoAnexo3C3, r: RegistroExecucaoEMS) -> list[Constatacao]:
    out: list[Constatacao] = []

    def e(cod, cam, msg):
        out.append(erro(cod, cam, msg))
    if c.execucao_uid != r.execucao_uid:
        e("anexo_de_outra_execucao", "anexo3c3.conteudo.execucao_uid", "UID da execução ≠ registro.")
    p = r.plano
    if p is None:
        e("registro_sem_plano", "registro.plano", "Registro sem plano: anexo 3C-3 não verificável.")
        return out
    if p.hash_entrada != c.hash_entrada_3c3 or p.versao_formulacao != FORMULACAO_3C3:
        e("anexo_de_outra_entrada", "anexo3c3.conteudo.hash_entrada_3c3",
          "Hash da entrada 3C-3 ≠ do plano do registro (ou plano não 3C-3).")
    pr = c.plano_rede
    if pr.hash_plano != hash_plano(p) or pr.hash_entrada_3c3 != c.hash_entrada_3c3 or \
            pr.indice_fronteira_inicial != p.indice_fronteira_inicial or len(pr.importacao_programada_kW) != p.N:
        e("plano_rede_de_outro_plano", "anexo3c3.conteudo.plano_rede", "Plano de rede não ligado ao plano do registro.")
    ei, ef = r.estado_inicial, r.estado_final
    if ei is not None and ef is not None:
        n = ef.indice_fronteira - ei.indice_fronteira
        k0 = ei.indice_fronteira
        idx = [x.indice_global for x in c.passos_pcc]
        if idx != list(range(k0, k0 + n)) or [x.indice_global for x in c.liquidacao] not in (idx, []) or \
                [x.indice_global for x in c.desvios] != idx:
            e("anexo_passos_incoerentes", "anexo3c3.conteudo.passos_pcc",
              f"Passos do PCC/liquidação/desvios ≠ {n} intervalo(s) executado(s) desde k = {k0}.")
        for x in c.passos_pcc:
            j = x.indice_global - pr.indice_fronteira_inicial
            if not 0 <= j < len(pr.importacao_programada_kW) or \
                    (x.importacao_programada_kW, x.exportacao_programada_kW) != (pr.importacao_programada_kW[j],
                                                                                 pr.exportacao_programada_kW[j]):
                e("anexo_programado_incoerente", f"anexo3c3.conteudo.passos_pcc[{x.indice_global}]",
                  "Programado do passo ≠ plano de rede.")
        gers = {g.uid for g in ei.geracao}
        for u, ev in c.eventos_aplicados.items():
            gi, gf = ei.gerador(u), ef.gerador(u)
            if u not in gers or gi is None or gf is None or \
                    ev.get("partidas", 0) - ev.get("paradas", 0) != int(gf.ligado) - int(gi.ligado):
                e("anexo_eventos_incoerentes", f"anexo3c3.conteudo.eventos_aplicados[{u}]",
                  "Partidas − paradas ≠ variação do estado entre as fronteiras do registro.")
    cr = r.custo_realizado
    if cr is not None:
        comp = {x.termo: x.valor_R for x in cr.componentes}
        g = math.fsum(x.gasto_importacao_R for x in c.liquidacao)
        rc = math.fsum(x.receita_exportacao_R for x in c.liquidacao)
        dv = math.fsum(x.custo_desvio_R for x in c.liquidacao)
        for termo, v in (("importacao_rede", g), ("exportacao_rede", -rc), ("desvio_rede", dv)):
            if termo in comp and abs(comp[termo] - v) > 1e-9 * max(1.0, abs(v)):
                e("anexo_liquidacao_incoerente", f"registro.custo_realizado[{termo}]",
                  f"Componente {comp[termo]!r} ≠ Σ da liquidação do anexo {v!r}.")
        if c.detalhe_h2:
            tot = math.fsum(h.custo_continuo_R + h.custo_eventos_R for h in c.detalhe_h2)
            if "combustivel_h2" not in comp or abs(comp["combustivel_h2"] - tot) > 1e-9 * max(1.0, abs(tot)):
                e("anexo_h2_incoerente", "anexo3c3.conteudo.detalhe_h2", "Σ H₂ ≠ componente combustivel_h2.")
    return out


def montar_anexo_3c3(registro: RegistroExecucaoEMS, conteudo: ConteudoAnexo3C3) -> AnexoExecucao3C3:
    c = verificar_registro(registro)
    if not registro.selo:
        c.append(erro("registro_nao_selado", "registro.selo", "O anexo refere um registro SELADO."))
    for k, v in hashes_para_registro_3c3(conteudo).items():
        if registro.hashes.get(k) != v:
            c.append(erro("registro_sem_hash_3c3", f"registro.hashes[{k}]",
                          "O registro 3C-0 deve comprometer o conteúdo 3C-3 ANTES de ser selado."))
    c += _coerencia(conteudo, registro)
    if c:
        raise ContratoInvalido(c)
    a = AnexoExecucao3C3(conteudo, registro.selo)
    return replace(a, selo=sha256(replace(a, selo="")))


def verificar_anexo_3c3(a: AnexoExecucao3C3, registro: RegistroExecucaoEMS) -> list[Constatacao]:
    out = list(verificar_registro(registro))
    if not isinstance(a, AnexoExecucao3C3) or not isinstance(a.conteudo, ConteudoAnexo3C3):
        return out + [erro("anexo_invalido", "anexo3c3", "Estrutura de anexo 3C-3 inválida.")]
    c = a.conteudo
    if a.selo != sha256(replace(a, selo="")):
        out.append(erro("anexo_adulterado", "anexo3c3.selo", "Selo não confere com o conteúdo do anexo."))
    if c.versao_anexo != VERSAO_ANEXO_3C3 or c.perfil != FORMULACAO_3C3:
        out.append(erro("anexo_versao_incompativel", "anexo3c3.conteudo.versao_anexo", f"{c.versao_anexo!r}/{c.perfil!r}."))
    if c.execucao_uid != registro.execucao_uid or a.selo_registro != registro.selo:
        out.append(erro("anexo_de_outro_registro", "anexo3c3.selo_registro", "Anexo de outra execução/registro."))
    if CHAVE_CONTEUDO_3C3 not in registro.hashes:
        out.append(erro("registro_sem_compromisso_do_anexo", f"registro.hashes[{CHAVE_CONTEUDO_3C3}]",
                        "O registro não compromete o conteúdo do anexo 3C-3."))
    rec = hashes_para_registro_3c3(c)
    for k in CHAVES_HASH_3C3:
        if registro.hashes.get(k) != rec.get(k):
            out.append(erro("conteudo_anexo_divergente" if k == CHAVE_CONTEUDO_3C3 else "hash_3c3_divergente",
                            f"registro.hashes[{k}]", "Hash comprometido no registro ≠ recalculado do anexo."))
    out += _coerencia(c, registro)
    return out


def gravar_anexo_3c3(diretorio, a: AnexoExecucao3C3) -> Path:
    from ..mpc.persistencia import gravar_exclusivo
    if a.selo != sha256(replace(a, selo="")):
        raise ContratoInvalido([erro("anexo_adulterado", "anexo3c3.selo", "Anexo não selado ou adulterado.")])
    return gravar_exclusivo(diretorio, f"{a.conteudo.execucao_uid}{SUFIXO_ANEXO_3C3}", json_canonico(a))


def ler_anexo_3c3(caminho) -> AnexoExecucao3C3:
    return de_json(AnexoExecucao3C3, Path(caminho).read_text(encoding="utf-8"))


__all__ = ["AnexoExecucao3C3", "CHAVES_HASH_3C3", "CHAVE_CONTEUDO_3C3", "ConteudoAnexo3C3", "SUFIXO_ANEXO_3C3",
           "VERSAO_ANEXO_3C3", "gravar_anexo_3c3", "hashes_para_registro_3c3", "ler_anexo_3c3", "montar_anexo_3c3",
           "preparar_conteudo_anexo_3c3", "verificar_anexo_3c3"]
