"""Comparação de missões MPC em condições COMPARÁVEIS (3C-2). Só biblioteca padrão.

Antes de comparar, ``condicoes_comparaveis`` exige (cada divergência é constatação bloqueante):

* mesma microrrede, cenário, τ_0, Δ e K_M; mesmo MODELO 3C-1 (SHA-256: parâmetros, políticas e termos idênticos);
* mesmo estado inicial; mesma verdade/planta (impressão registrada pelo laço simulado APÓS a missão);
* mesma informação: mesmo provedor (impressão) — ou, só com ``permitir_oraculo=True``, oráculo de ablação contra
  causal (comparação de REFERÊNCIA, nunca "causal principal");
* mesma configuração de solver, mesma política de aceitação e de falhas; missões encerradas com registro selado.

O resultado lista as grandezas lado a lado (A, B, B − A) sem veredito: o MPC não é presumido melhor que o open-loop.
Especificação v1.0 §12: custos de controladores só são comparáveis com a MESMA energia final armazenada ou mostrando
a diferença — a energia final de cada banco e a diferença são sempre reportadas. Nenhum valor futuro é atribuído a
essa diferença (3C-4).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..diagnostics import Constatacao, aviso, erro
from .metricas import metricas_missao


@dataclass(frozen=True)
class ComparacaoMissoes:
    rotulo_a: str
    rotulo_b: str
    tipo: str                                   # "causal" | "referencia_oraculo"
    comparavel: bool
    constatacoes: tuple[Constatacao, ...]
    linhas: dict                                # grandeza → (A, B, B − A)
    observacao: str


def _cfg_sem_malha(c) -> str:
    return json.dumps({"aceitacao": repr(c.politica_aceitacao), "falhas": sorted(c.politica_falhas.acoes.items()),
                       "revisao": c.politica_revisao_tardia, "modo": c.modo}, sort_keys=True)


def condicoes_comparaveis(ra, rb, *, permitir_oraculo: bool = False) -> list[Constatacao]:
    out: list[Constatacao] = []
    if ra.registro_missao is None or rb.registro_missao is None:
        return [erro("missao_sem_registro_selado", "comparacao", "Ambas as missões devem estar finalizadas e seladas.")]
    a, b = ra.registro_missao.conteudo, rb.registro_missao.conteudo
    ia, ib = a.identidade, b.identidade
    if (ia.microrrede_uid, ia.cenario_uid, ia.versao_cenario) != (ib.microrrede_uid, ib.cenario_uid, ib.versao_cenario):
        out.append(erro("identidade_nao_comparavel", "identidade", "Microrrede/cenário diferentes."))
    ma, mb = a.configuracao.malha, b.configuracao.malha
    if (ma.inicio(), ma.delta_s, ma.intervalos_missao) != (mb.inicio(), mb.delta_s, mb.intervalos_missao):
        out.append(erro("tempo_nao_comparavel", "malha", "τ_0, Δ ou K_M diferentes."))
    if a.hash_modelo_3c1 != b.hash_modelo_3c1:
        out.append(erro("restricoes_nao_comparaveis", "modelo", "Modelos 3C-1 (parâmetros/políticas/termos) diferentes."))
    if a.estado_inicial != b.estado_inicial:
        out.append(erro("estado_inicial_nao_comparavel", "estado_inicial", "Estados iniciais diferentes."))
    va, vb = ra.entorno.get("impressao_verdade"), rb.entorno.get("impressao_verdade")
    if va is None or va != vb:
        out.append(erro("realizacao_nao_comparavel", "entorno", "Verdade/planta diferentes ou não registradas."))
    oa, ob = a.configuracao.rotulo_informacao, b.configuracao.rotulo_informacao
    if oa != ob:
        if not permitir_oraculo:
            out.append(erro("informacao_nao_comparavel", "rotulo_informacao",
                            "Oráculo × causal só como comparação de REFERÊNCIA (permitir_oraculo=True)."))
        else:
            out.append(aviso("comparacao_de_referencia_oraculo", "rotulo_informacao",
                             "Comparação de referência: excluída das comparações causais principais."))
    elif a.impressao_provedor != b.impressao_provedor:
        out.append(erro("informacao_nao_comparavel", "provedor", "Provedores de previsão diferentes."))
    if a.resolvedor_json != b.resolvedor_json:
        out.append(erro("solver_nao_comparavel", "resolvedor", "Configurações de solver diferentes."))
    if _cfg_sem_malha(a.configuracao) != _cfg_sem_malha(b.configuracao):
        out.append(erro("regras_nao_comparaveis", "politicas", "Políticas de aceitação/falhas/revisão ou modo diferentes."))
    return out


def comparar_missoes(ra, rb, modelo, *, rotulo_a: str, rotulo_b: str, permitir_oraculo: bool = False
                     ) -> ComparacaoMissoes:
    c = condicoes_comparaveis(ra, rb, permitir_oraculo=permitir_oraculo)
    ok = not any(x.severidade == "erro" for x in c)
    ma, mb = metricas_missao(ra, modelo), metricas_missao(rb, modelo)
    a, b = ra.registro_missao.conteudo, rb.registro_missao.conteudo

    def lin(x, y):
        return (x, y, None if x is None or y is None else y - x)
    linhas = {"custo_realizado_total_R": lin(a.custo_realizado_acumulado.total_R, b.custo_realizado_acumulado.total_R),
              "intervalos_aplicados": lin(a.intervalos_aplicados, b.intervalos_aplicados),
              "janelas_registradas": lin(len(ra.registros), len(rb.registros))}
    for t in sorted({x.termo for x in a.custo_realizado_acumulado.componentes} |
                    {x.termo for x in b.custo_realizado_acumulado.componentes}):
        ga = next((x.valor_R for x in a.custo_realizado_acumulado.componentes if x.termo == t), None)
        gb = next((x.valor_R for x in b.custo_realizado_acumulado.componentes if x.termo == t), None)
        linhas[f"custo_realizado_R[{t}]"] = lin(ga, gb)
    for k in sorted(set(ma.operacao) | set(mb.operacao)):
        linhas[k] = lin(ma.operacao.get(k), mb.operacao.get(k))
    for u in sorted(set(ma.commitment) | set(mb.commitment)):
        for k in ("partidas", "paradas"):
            linhas[f"{k}[{u}]"] = lin(ma.commitment.get(u, {}).get(k), mb.commitment.get(u, {}).get(k))
    linhas["resolucoes"] = lin(ma.computacao["resolucoes"], mb.computacao["resolucoes"])
    obs = (f"Desfechos: A = {a.desfecho!r}, B = {b.desfecho!r}. Sem veredito: diferenças de energia final armazenada "
           "(E_final_kWh) e obrigações pendentes não são valoradas (valor futuro = 3C-4).")
    tipo = "causal" if {a.configuracao.rotulo_informacao, b.configuracao.rotulo_informacao} == {"causal"} \
        else "referencia_oraculo"
    return ComparacaoMissoes(rotulo_a, rotulo_b, tipo, ok, tuple(c), linhas, obs)


__all__ = ["ComparacaoMissoes", "comparar_missoes", "condicoes_comparaveis"]
