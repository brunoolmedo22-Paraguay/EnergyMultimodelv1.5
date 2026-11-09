"""Comparação de missões CONECTADAS (3C-3) em condições comparáveis — só biblioteca padrão.

Reutiliza ``mpc.comparadores`` (3C-2, inalterado: mesma microrrede/cenário, τ_0/Δ/K_M, núcleo 3C-1, estado inicial,
verdade, provedor, solver e políticas) e exige ADICIONALMENTE os mesmos: modelo 3C-3 (PCC, limites, disponibilidade
declarada, tarifas de decisão do modelo), configuração de rede (política de ajuste, perfis de liquidação e de decisão).

Rótulos:

* ``causal`` — comparável (todas as condições iguais). ``comparavel_para_superioridade`` só é verdadeiro se, além disso,
  a energia final de cada banco e as obrigações de permanência pendentes coincidirem (especificação v1.0 §12): uma
  diferença de custo com energia final diferente NÃO é prova de superioridade econômica (sem valor futuro — 3C-4);
* ``contraste_de_topologia`` — conectado × isolado declarado: contraste de FACTIBILIDADE e de uso da rede, nunca
  comparação de benefício econômico (modelos diferentes por construção).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..diagnostics import Constatacao, erro
from ..mpc.comparadores import comparar_missoes


@dataclass(frozen=True)
class ComparacaoMissoes3C3:
    rotulo_a: str
    rotulo_b: str
    tipo: str                                   # "causal" | "referencia_oraculo" | "contraste_de_topologia"
    comparavel: bool
    comparavel_para_superioridade: bool
    constatacoes: tuple[Constatacao, ...]
    linhas: dict
    observacao: str


def _lin(x, y):
    return (x, y, None if x is None or y is None else y - x)


def comparar_missoes_3c3(xa, xb, *, rotulo_a: str, rotulo_b: str, permitir_oraculo: bool = False
                         ) -> ComparacaoMissoes3C3:
    """``xa``/``xb``: ``rede.experimentos.ExecucaoConectada`` (resultado + modelo 3C-3)."""
    ra, rb = xa.resultado, xb.resultado
    base = comparar_missoes(ra, rb, xa.modelo.compromisso, rotulo_a=rotulo_a, rotulo_b=rotulo_b,
                            permitir_oraculo=permitir_oraculo)
    c = list(base.constatacoes)
    wa, wb = ra.registro_rede, rb.registro_rede
    topologia = wa is not None and wb is not None and wa.modo_conexao != wb.modo_conexao
    if wa is None or wb is None:
        c.append(erro("missao_rede_sem_registro", "comparacao", "Registro de missão de rede ausente."))
    elif not topologia and (wa.hash_modelo_3c3 != wb.hash_modelo_3c3 or
                            wa.hash_configuracao_rede != wb.hash_configuracao_rede):
        c.append(erro("rede_nao_comparavel", "rede",
                      "PCC/limites/tarifas do modelo ou política de ajuste/liquidação diferentes."))
    linhas = dict(base.linhas)
    a, b = ra.registro_missao.conteudo, rb.registro_missao.conteudo
    for bat in sorted({x.uid for x in a.estado_final.armazenamento} | {x.uid for x in b.estado_final.armazenamento}):
        ea, eb = a.estado_final.bateria(bat), b.estado_final.bateria(bat)
        linhas[f"E_final_kWh[{bat}]"] = _lin(ea and ea.energia_kWh, eb and eb.energia_kWh)
    linhas["obrigacoes_pendentes_s"] = _lin(sum(a.obrigacoes_pendentes_fim_s.values()),
                                            sum(b.obrigacoes_pendentes_fim_s.values()))
    for k in sorted(set((wa.totais if wa else {})) | set((wb.totais if wb else {}))):
        linhas[k] = _lin((wa.totais if wa else {}).get(k), (wb.totais if wb else {}).get(k))
    ok = not any(x.severidade == "erro" for x in c) and not topologia
    mesma_energia = all(v[2] is not None and abs(v[2]) <= 1e-9 for k, v in linhas.items() if k.startswith("E_final_kWh"))
    sup = ok and mesma_energia and linhas["obrigacoes_pendentes_s"][2] == 0
    tipo = "contraste_de_topologia" if topologia else base.tipo
    obs = (f"{base.observacao} Rede: {wa.modo_conexao if wa else '?'} × {wb.modo_conexao if wb else '?'}. "
           + ("Contraste de TOPOLOGIA: factibilidade e uso da rede, não benefício econômico. " if topologia else "")
           + ("Energia final/obrigações iguais." if mesma_energia and linhas['obrigacoes_pendentes_s'][2] == 0 else
              "Energia final ou obrigações DIFERENTES: a diferença de custo não é conclusiva."))
    return ComparacaoMissoes3C3(rotulo_a, rotulo_b, tipo, ok, sup, tuple(c), linhas, obs)


__all__ = ["ComparacaoMissoes3C3", "comparar_missoes_3c3"]
