"""Pré-verificação do perfil 3C-1 ANTES do solver (sem Pyomo).

Além de ``validar_entrada_3c1`` (parâmetros, memória, políticas, termos), verifica:

* compromisso PARCIAL opcional: ``{uid: (0 | 1 | None, …)}`` com exatamente N valores (``int`` estrito 0/1 ou ``None`` =
  livre; ``bool``/``float``/texto/NaN são rejeitados sem conversão — mesma regra do C-3B-01);
* unidades com transições bloqueadas: um valor fixado diferente de ``u^{-1}`` exige transição não representável ⇒
  constatação BLOQUEANTE (``transicao_fixada_nao_representavel``);
* obrigações herdadas × disponibilidade: ``u`` forçado em 1 num intervalo com ``a = 0`` ⇒ erro (parada forçada sem
  envoltória de emergência documentada — especificação v1.0 §7.1); unidade ON com ``a_0 = 0`` exige parada
  representável em t = 0 com ``p^{-1} <= S⁻`` (senão erro);
* compromisso parcial × obrigações herdadas, × disponibilidade e × representabilidade das transições fixadas
  (pares consecutivos fixados, inclusive com ``u^{-1}``).

Nada aqui altera o inventário, a entrada ou os parâmetros: só constata.
"""
from __future__ import annotations

from ..diagnostics import Constatacao, erro
from .contrato import EntradaCommitment3C1, discretizar, disponibilidade, validar_entrada_3c1


def programa_parcial_valido(prog, N: int) -> bool:
    return (isinstance(prog, (list, tuple)) and len(prog) == N
            and all(x is None or (type(x) is int and x in (0, 1)) for x in prog))


def preflight_3c1(e: EntradaCommitment3C1, compromisso_parcial: dict | None = None) -> list[Constatacao]:
    rel = validar_entrada_3c1(e)
    out: list[Constatacao] = list(rel.constatacoes)
    if not rel.aceito:
        return out
    N = e.base.malha.N
    cp = {} if compromisso_parcial is None else compromisso_parcial
    if not isinstance(cp, dict):
        return out + [erro("compromisso_invalido", "compromisso_parcial",
                           f"Esperado dicionário UID → programa parcial; recebido {type(cp).__name__}.")]
    ger = {str(g.uid): g for g in e.base.geradores}
    for k in sorted((x for x in cp if x not in ger), key=repr):
        out.append(erro("compromisso_uid_desconhecido", f"compromisso_parcial[{k!r}]",
                        "Chave não é UID (texto) de gerador da entrada."))
    disc = discretizar(e)
    for k, g in ger.items():
        dz = disc[k]
        a = disponibilidade(g, e.base.malha)
        cam = f"unidades[{k}]"
        # obrigação herdada × disponibilidade
        for t in range(dz.intervalos_forcados):
            if dz.u_anterior == 1 and a[t] != 1.0:
                out.append(erro("obrigacao_ligado_com_indisponibilidade", f"{cam}.u[{t}]",
                                "Permanência ON herdada num intervalo com a = 0: parada forçada exige envoltória de "
                                "emergência documentada (não modelada no 3C-1)."))
                break
        if dz.u_anterior == 1 and a[0] != 1.0 and dz.intervalos_forcados == 0:
            if not dz.parada_representavel or dz.limite_parada_kW is None or dz.p_anterior_kW > dz.limite_parada_kW:
                out.append(erro("parada_forcada_nao_representavel", f"{cam}.u[0]",
                                f"Unidade ON com a_0 = 0: a parada em t = 0 exige parada representável com p^-1 = "
                                f"{dz.p_anterior_kW} kW <= S⁻ = {dz.limite_parada_kW} kW."))
        if dz.abstracao == "transicoes_bloqueadas" and dz.u_anterior == 1 and any(x != 1.0 for x in a):
            out.append(erro("indisponibilidade_com_transicoes_bloqueadas", cam,
                            "Unidade ON sem transição representável e com a = 0 em algum intervalo."))
        if k not in cp:
            continue
        prog = cp[k]
        if not programa_parcial_valido(prog, N):
            out.append(erro("compromisso_invalido", f"compromisso_parcial[{k}]",
                            f"Exigida sequência de {N} valores em {{0, 1, None}} (int estrito; sem bool/float/texto)."))
            continue
        for t, x in enumerate(prog):
            if x == 1 and a[t] != 1.0:
                out.append(erro("compromisso_com_indisponibilidade", f"compromisso_parcial[{k}][{t}]", "u = 1 com a = 0."))
            if x is not None and t < dz.intervalos_forcados and x != dz.u_anterior:
                out.append(erro("compromisso_parcial_viola_obrigacao", f"compromisso_parcial[{k}][{t}]",
                                f"Permanência herdada exige u = {dz.u_anterior} nos {dz.intervalos_forcados} primeiros "
                                "intervalos."))
        anterior = [dz.u_anterior] + list(prog)
        for t in range(N):
            ua, ub = anterior[t], anterior[t + 1]
            if ua is None or ub is None or ua == ub:
                continue
            if (ub == 1 and not dz.partida_representavel) or (ub == 0 and not dz.parada_representavel):
                out.append(erro("transicao_fixada_nao_representavel", f"compromisso_parcial[{k}][{t}]",
                                f"Programa fixa {'partida' if ub == 1 else 'parada'} em t = {t}, não representável com os "
                                f"parâmetros declarados (abstração {dz.abstracao!r}, S⁺ = {dz.limite_partida_kW}, "
                                f"S⁻ = {dz.limite_parada_kW}, mínimo ON {dz.p_on_min_kW} kW)."))
    return out


__all__ = ["preflight_3c1", "programa_parcial_valido"]
