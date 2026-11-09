"""Auditoria INDEPENDENTE da missão hierárquica (3C-4) e retomada verificada — só biblioteca padrão.

Composição explícita sobre a auditoria INTEGRAL 3C-3 (``rede.auditoria.auditar_missao_conectada``, inalterada:
cadeia, K6, temporal, causal, estado/memória, balanço com PCC, custos realizados, documentos 3C-0/3C-3/rede) +
seção ``hierarquica`` (``verificar_coordenacoes``):

* um ``RegistroCoordenacao3C4`` selado por posição de janela (nenhum ausente/excedente; missão, janela, k);
* janela executada: o registro 3C-0 compromete o selo e a impressão da coordenação ANTES do seu próprio selo; a
  coordenação é de uma situação que admite plano; entrada núcleo = a da janela; decomposição presente;
* sinal válido aplicado: selo, vínculo à janela (caducidade), fronteira k + N_k, modelo/configuração da missão e
  CAUSALIDADE contra o livro K6 (hash do instantâneo no instante de emissão); o termo aplicado contém EXATAMENTE o sinal;
* termo terminal RECALCULADO a partir do plano 3C-0 (energia e(N) da trajetória planejada) e da memória terminal
  planejada (plano de commitment do anexo 3C-3): modo compatível único, domínio, V̂ recalculado = ``custo_futuro_estimado``
  da decomposição e do ``custos_modelo`` do registro 3C-0; total = Σ termos 3C-3 + V̂;
* o custo REALIZADO nunca contém valor futuro (nenhum componente terminal; acumulado = Σ janelas, já conferido pelo
  3C-3);
* ``RegistroMissaoHierarquica3C4`` (selo, vínculos, sequência e contagens).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from ..audit import Tolerancias, _tol_custo
from ..diagnostics import Constatacao, ContratoInvalido, erro
from ..mpc.registro import selo_confere
from ..rede.auditoria import RelatorioAuditoriaMissaoConectada, auditar_missao_conectada
from ..rede.contrato import hash_entrada_3c3
from . import ESQUEMA_3C4, FORMULACAO_3C4
from .auditor import CHAVES_TERMINAIS
from .contrato import (hash_configuracao_planejador, modo_condicionado, validar_sinal, validar_sinal_para_janela)
from .mpc import (RegistroCoordenacao3C4, RegistroMissaoHierarquica3C4, SITUACOES_COORDENACAO, VinculoHierarquico3C4,
                  impressao_coordenacao, nome_coordenacao, nome_missao_hier, nome_vinculo_hier,
                  verificar_registro_hierarquico)
from .valor import avaliar_modo, modos_compativeis, penalidade_branda, valor_termo_declarado

COM_PLANO = ("valido", "degradado_sem_valor_futuro", "degradado_referencia")


def _selo_ok(x) -> bool:
    try:
        return selo_confere(x)
    except (TypeError, ValueError):
        return False


def _termo_recalculado(co: RegistroCoordenacao3C4, reg0, anexo) -> tuple[float | None, list[Constatacao], dict]:
    """V̂ (ou Φ declarado) recalculado no estado terminal PLANEJADO do registro 3C-0 da janela."""
    cam = f"coordenacao[{co.posicao}]"
    c: list[Constatacao] = []
    t = co.termo_aplicado
    p = reg0.plano
    N = p.N
    en = {x.uid: float(x.valores[-1]) for x in p.estados_planejados if x.grandeza == "e"}
    est = {}
    mem = getattr(getattr(getattr(anexo, "conteudo", None), "plano_rede", None), "commitment", None)
    if mem is not None:
        for mf in mem.memorias_terminais:
            est[mf.uid] = (mf.ligado, mf.obrigacao_residual_s, mf.potencia_kW)
    det = {"energias": en, "estado": est, "N": N}
    if t is None:
        return None, [erro("termo_aplicado_ausente", cam, "Janela executada sem termo terminal registrado.")], det
    if t.tipo in ("nenhum_declarado", "valor_linear_declarado", "energia_minima_declarada"):
        v = valor_termo_declarado(t, en)
        if v is None:
            c.append(erro("energia_minima_violada_no_plano", cam, f"E(N) planejada {en} < Ē."))
        return v, c, det
    s = t.sinal
    bats = s.baterias
    x = tuple(en.get(u, float("nan")) for u in bats)
    if s.tipo == "referencia_energia_dura":
        if any(a < r - 1e-6 for a, r in zip(x, s.referencia.energias_kWh)):
            c.append(erro("referencia_terminal_violada_no_plano", cam, f"E(N) {x} < E_ref."))
        return 0.0, c, det
    if s.tipo == "referencia_energia_branda":
        return penalidade_branda(s, x), c, det
    comp = modos_compativeis(s, est) if modo_condicionado(s) else [m.indice for m in s.modos]
    if len(comp) != 1:
        c.append(erro("estado_terminal_fora_dos_modos_no_plano", cam, f"Memória terminal planejada {est}: {len(comp)} "
                                                                       "modos compatíveis (exigido 1)."))
        return None, c, det
    if co.decomposicao is not None and co.decomposicao.modo != comp[0]:
        c.append(erro("modo_registrado_divergente", cam, f"Modo registrado {co.decomposicao.modo} ≠ {comp[0]}."))
    v = avaliar_modo(s, s.modos[comp[0]], x, 1e-6)
    if v is None:
        c.append(erro("estado_terminal_fora_do_dominio_no_plano", cam, f"E(N) {x} fora do domínio do modo {comp[0]}."))
    return v, c, det


def verificar_coordenacoes(cfg, registros, coordenacoes, registros_3c0, anexos_3c3, modelo_rede, cfg_plan, *, livro=None,
                           tol: Tolerancias = Tolerancias()) -> list[Constatacao]:
    out: list[Constatacao] = []
    m = cfg.identidade.missao_uid
    if len(coordenacoes) != len(registros):
        out.append(erro("coordenacoes_em_numero_divergente", "coordenacoes",
                        f"{len(coordenacoes)} registros de coordenação para {len(registros)} janelas."))
    r0 = {r.execucao_uid: r for r in registros_3c0}
    an = {a.conteudo.execucao_uid: a for a in anexos_3c3}
    hm, hc = hash_entrada_3c3(modelo_rede), hash_configuracao_planejador(cfg_plan)
    for r, co in zip(registros, coordenacoes):
        c = r.conteudo
        cam = f"coordenacao[{c.posicao}]"
        if not isinstance(co, RegistroCoordenacao3C4):
            out.append(erro("coordenacao_invalida", cam, type(co).__name__))
            continue
        if not _selo_ok(co):
            out.append(erro("coordenacao_adulterada", cam, "Selo do registro de coordenação não confere."))
        if (co.esquema, co.perfil, co.missao_uid, co.posicao, co.indice_janela, co.k) != (
                ESQUEMA_3C4, FORMULACAO_3C4, m, c.posicao, c.janela.indice_janela, c.janela.k) or \
                co.situacao not in SITUACOES_COORDENACAO:
            out.append(erro("coordenacao_de_outra_janela", cam, "Missão/posição/janela/k/esquema/situação divergentes."))
            continue
        s = co.sinal
        if co.situacao == "valido":
            if s is None or co.termo_aplicado is None or co.termo_aplicado.sinal != s:
                out.append(erro("sinal_aplicado_divergente", cam, "Situação 'valido' sem o sinal no termo aplicado."))
                continue
            out += [erro("sinal_invalido_na_auditoria", cam, f"[{x.codigo}] {x.mensagem}") for x in validar_sinal(s)]
            hi = None
            if livro is not None:
                try:
                    hi = livro.instantaneo(s.instante_emissao_utc).hash
                except ContratoInvalido:
                    hi = None
            cv = validar_sinal_para_janela(s, missao_uid=m, indice_janela=c.janela.indice_janela, k=c.janela.k,
                                           instante_utc=c.janela.inicio_utc, fronteira=c.janela.k + c.janela.N_k,
                                           hash_modelo_rede=hm, hash_configuracao=hc,
                                           hash_instantaneo_emissao=hi if livro is not None else
                                           (s.hashes or {}).get("instantaneo"))
            out += [erro("sinal_nao_vinculado_na_auditoria", cam, f"[{x.codigo}] {x.mensagem}") for x in cv]
        if c.hash_plano is None:
            continue
        reg0, ax = r0.get(c.execucao_uid), an.get(c.execucao_uid)
        if reg0 is None or ax is None:
            out.append(erro("artefatos_da_janela_ausentes", cam, "Registro 3C-0/anexo 3C-3 da janela ausentes."))
            continue
        if co.situacao not in COM_PLANO or co.decomposicao is None:
            out.append(erro("coordenacao_incoerente_com_plano", cam, f"Janela com plano e coordenação {co.situacao!r}."))
            continue
        if reg0.hashes.get("coordenacao_3c4") != co.selo or reg0.hashes.get("coordenacao_3c4_impressao") != \
                impressao_coordenacao(co):
            out.append(erro("coordenacao_nao_comprometida", cam, "O registro 3C-0 não compromete esta coordenação."))
        if co.hash_entrada_nucleo_3c3 != c.hash_entrada_3c1 or reg0.hashes.get("entrada_3c4") != co.hash_entrada_3c4:
            out.append(erro("entrada_divergente", cam, "Entrada núcleo/3C-4 ≠ comprometidas pela janela."))
        if s is not None and co.situacao == "valido" and reg0.hashes.get("sinal_valor_futuro") != s.selo:
            out.append(erro("sinal_nao_comprometido", cam, "Sinal não comprometido no registro 3C-0."))
        v, cc, det = _termo_recalculado(co, reg0, ax)
        out += cc
        d = co.decomposicao
        cm = dict(reg0.custo_objetivo_planejado)
        chaves = [k for k in cm if k in CHAVES_TERMINAIS]
        if v is not None:
            esperado_chave = d.chave_terminal
            vt = v if esperado_chave is not None else 0.0
            if esperado_chave is not None and (d.custo_futuro_estimado_R is None or abs(
                    d.custo_futuro_estimado_R - v) > _tol_custo(tol, v)):
                out.append(erro("custo_futuro_divergente", cam,
                                f"Decomposição {d.custo_futuro_estimado_R!r} ≠ V̂ recalculado {v!r}."))
            if esperado_chave is not None and (esperado_chave not in cm or abs(cm[esperado_chave] - v) > _tol_custo(tol, v)):
                out.append(erro("custo_futuro_divergente", cam, "custos_modelo do registro 3C-0 ≠ V̂ recalculado."))
            outros = math.fsum(val for k, val in cm.items() if k != "total" and k not in CHAVES_TERMINAIS)
            if "total" not in cm or abs(cm["total"] - (outros + vt)) > _tol_custo(tol, cm.get("total", 0.0)):
                out.append(erro("objetivo_total_divergente", cam, "total ≠ Σ termos 3C-3 + termo terminal."))
            if d.custo_operativo_previsto_R is None or abs(d.custo_operativo_previsto_R - outros) > _tol_custo(tol, outros):
                out.append(erro("custo_operativo_divergente", cam, "Custo operativo previsto ≠ Σ termos 3C-3."))
            for u, e_ in det["energias"].items():
                if abs(d.energias_fronteira_kWh.get(u, float("nan")) - e_) > 1e-6 * max(1.0, abs(e_)):
                    out.append(erro("energia_fronteira_divergente", cam, f"E(N) registrada ≠ plano ({u})."))
        elif len(chaves) > 0 and d.chave_terminal is None:
            out.append(erro("termo_terminal_inesperado", cam, f"custos_modelo com {chaves} sem termo declarado."))
        real = reg0.custo_realizado
        if real is not None and any(x.termo in CHAVES_TERMINAIS or "futuro" in x.termo for x in real.componentes):
            out.append(erro("valor_futuro_contabilizado_como_custo", cam, "Custo REALIZADO com componente terminal."))
        if reg0.valor_futuro.contabilizado_como_custo:
            out.append(erro("valor_futuro_contabilizado_como_custo", cam, "Registro 3C-0 declara valor futuro como custo."))
    return out


@dataclass(frozen=True)
class RelatorioAuditoriaHierarquica:
    aceito: bool
    verificacoes: dict[str, bool]
    constatacoes: tuple[Constatacao, ...]
    relatorio_3c3: RelatorioAuditoriaMissaoConectada | None

    def codigos(self) -> set[str]:
        return {c.codigo for c in self.constatacoes}


def auditar_missao_hierarquica(registro_missao, registros, livro, modelo_rede, configuracao_rede, configuracao_planejador,
                               *, registros_3c0, anexos, registro_rede, coordenacoes, registro_hierarquico, verdade=None,
                               tol: Tolerancias = Tolerancias()) -> RelatorioAuditoriaHierarquica:
    """Auditoria INTEGRAL 3C-4: todos os artefatos são obrigatórios (``None`` ⇒ reprovação, nunca omissão)."""
    falt = [n for n, v in (("registros_3c0", registros_3c0), ("anexos", anexos), ("registro_rede", registro_rede),
                           ("coordenacoes", coordenacoes), ("registro_hierarquico", registro_hierarquico)) if v is None]
    if falt:
        c = (erro("auditoria_integral_incompleta", "auditoria", f"Artefatos ausentes: {falt}."),)
        return RelatorioAuditoriaHierarquica(False, {"documental_3c4": False}, c, None)
    r3 = auditar_missao_conectada(registro_missao, registros, livro, modelo_rede, configuracao_rede,
                                  registros_3c0=registros_3c0, anexos=anexos, registro_rede=registro_rede,
                                  verdade=verdade, tol=tol)
    cfg = registro_missao.conteudo.configuracao
    ch = verificar_coordenacoes(cfg, registros, coordenacoes, registros_3c0, anexos, modelo_rede, configuracao_planejador,
                                livro=livro, tol=tol)
    cm = verificar_registro_hierarquico(registro_hierarquico, registro_missao, registro_rede, coordenacoes)
    if isinstance(registro_hierarquico, RegistroMissaoHierarquica3C4) and (
            registro_hierarquico.hash_modelo_rede != hash_entrada_3c3(modelo_rede)
            or registro_hierarquico.hash_configuracao_planejador != hash_configuracao_planejador(configuracao_planejador)):
        cm.append(erro("configuracao_hierarquica_divergente", "missao_hier",
                       "Modelo de rede/configuração do planejador fornecidos ≠ comprometidos."))
    ver = {"integral_3c3": r3.aceito, "hierarquica": not ch, "registro_hierarquico": not cm}
    return RelatorioAuditoriaHierarquica(all(ver.values()), ver, tuple(list(r3.constatacoes) + ch + cm), r3)


# ================================================================================================ retomada
def retomar_controlador_hierarquico(diretorio, cfg, modelo, provedor, resolvedor, fontes, configuracao_rede,
                                    configuracao_planejador, planejador_resolvedor, **kw):
    """Retomada VERIFICADA: a verificação 3C-3 completa (``retomar_controlador_conectado``) + coordenações seladas de
    TODAS as posições, compromisso de cada coordenação no registro 3C-0 da janela executada, vínculo hierárquico do
    último ponto (modelo, configurações, lote pendente selado). Qualquer divergência ⇒ ``ContratoInvalido``."""
    from ..mpc.persistencia import _ler
    from ..rede.mpc import hash_configuracao_rede
    from ..rede.persistencia import retomar_controlador_conectado
    from .mpc import ControladorMPCHierarquico
    c3, pt = retomar_controlador_conectado(diretorio, cfg, modelo, provedor, resolvedor, fontes, configuracao_rede, **kw)
    m = cfg.identidade.missao_uid
    d = Path(diretorio)
    regs = list(c3.registros)
    pos = len(regs) - 1
    c: list[Constatacao] = []
    coords = []
    for p in range(pos + 1):
        try:
            coords.append(_ler(RegistroCoordenacao3C4, d / nome_coordenacao(m, p), "coordenacao_3c4"))
        except ContratoInvalido as exc:
            c += list(exc.constatacoes)
    vh = _ler(VinculoHierarquico3C4, d / nome_vinculo_hier(m, pos), "vinculo_hierarquico")
    if c:
        raise ContratoInvalido(c)
    c += verificar_coordenacoes(cfg, regs, coords, c3.registros_3c0, c3.anexos_3c3, modelo, configuracao_planejador,
                                livro=c3.livro)
    if not _selo_ok(vh):
        c.append(erro("vinculo_hierarquico_adulterado", nome_vinculo_hier(m, pos), "Selo não confere."))
    if (vh.esquema, vh.missao_uid, vh.posicao, vh.selo_ultima_janela, vh.selo_coordenacao) != (
            ESQUEMA_3C4, m, pos, regs[-1].selo, coords[-1].selo if coords else None):
        c.append(erro("retomada_incoerente", "retomada.vinculo_hierarquico", "Vínculo ≠ último registro/coordenação."))
    if (vh.hash_modelo_rede, vh.hash_configuracao_rede, vh.hash_configuracao_planejador) != (
            hash_entrada_3c3(modelo), hash_configuracao_rede(configuracao_rede),
            hash_configuracao_planejador(configuracao_planejador)):
        c.append(erro("identidade_divergente", "retomada.vinculo_hierarquico",
                      "Modelo/configuração de rede/planejador ≠ os da missão."))
    emitidos = {x.selo for co in coords for x in co.lote}
    for s in vh.lote_pendente:
        if validar_sinal(s) or s.selo not in emitidos:
            c.append(erro("lote_pendente_invalido", "retomada.vinculo_hierarquico.lote_pendente",
                          "Sinal pendente adulterado ou não emitido por nenhuma coordenação registrada."))
    if c:
        raise ContratoInvalido(c)
    ctrl = ControladorMPCHierarquico(cfg, modelo, provedor, resolvedor, fontes, configuracao_rede,
                                     configuracao_planejador, planejador_resolvedor, livro=c3.livro,
                                     estado_inicial=pt.estado, diretorio=diretorio, _registros=tuple(regs),
                                     _confirmacoes=pt.confirmacoes, _comandos=pt.comandos, _k=pt.k,
                                     _j=pt.indice_janela, **kw)
    ctrl._g_conciliado = pt.k
    ctrl.registros_3c0, ctrl.anexos_3c3 = list(c3.registros_3c0), list(c3.anexos_3c3)
    ctrl.coordenacoes = list(coords)
    ctrl._lote = {s.indice_janela: s for s in vh.lote_pendente}
    ctrl.situacao, ctrl.classe_falha = c3.situacao, c3.classe_falha
    return ctrl, pt


def ler_registro_hierarquico(diretorio, missao_uid: str) -> RegistroMissaoHierarquica3C4:
    from ..mpc.persistencia import _ler
    return _ler(RegistroMissaoHierarquica3C4, Path(diretorio) / nome_missao_hier(missao_uid), "registro_hierarquico")


__all__ = ["RelatorioAuditoriaHierarquica", "auditar_missao_hierarquica", "ler_registro_hierarquico",
           "retomar_controlador_hierarquico", "verificar_coordenacoes"]
