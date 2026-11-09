"""Evidência reproduzível do Piso 3C-4: ``python -m ems_v2.milp.evidencia_3c4 [--rapida]``.

Executa a campanha H1–H17 sobre fixtures SINTÉTICAS (``ems_v2.fixtures_3c4``) com HiGHS real e imprime, em Markdown:
tabela de estratégias × cenários (custo realizado, situação, energia final, janelas degradadas, avaliações e tempo do
planejador), efeitos separados (reotimização, antecipação, informação perfeita) com comparabilidade terminal,
ablação do tipo de sinal, sensibilidade a N × H_L (H13), λ(E) (H6), λ₀ × posição do pico (H4), pontos/refinamento e
política periódica (custo computacional). Simulação causal de laço fechado ALGÉBRICA: nada é validação física, fatura
real nem desempenho de tempo real; tempos valem SÓ para o ambiente impresso.
"""
from __future__ import annotations

import json
import math
import sys
import time

from .. import fixtures_3c4 as F
from ..hierarquia import experimentos as X
from ..hierarquia.comparadores import comparar
from ..hierarquia.valor import inclinacoes_1d

CENARIOS = ("h1_tarifa_plana", "h2_pico_futuro", "h3_pico_no_horizonte_curto", "h5_erro_previsao",
            "h7_limite_importacao", "h8_indisponibilidade_pcc", "h9_pemfc", "h17_dois_bancos")


def _f(x, n=4):
    return "—" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def campanha(cenarios=CENARIOS, estrategias=X.ESTRATEGIAS) -> dict:
    out = {}
    for nome in cenarios:
        c = getattr(F, nome)()
        kw = {"planejador_kw": {"pontos": 3}} if nome == "h17_dois_bancos" else {}
        ex = {}
        for e in estrategias:
            t0 = time.perf_counter()
            ex[e] = X.executar(c, e, **(kw if e.startswith("hier") else {}))
            ex[e].tempo_parede_s = time.perf_counter() - t0
        out[nome] = (ex, comparar(ex))
    return out


def _projecoes(x) -> int:
    from ..hierarquia.auditoria import reconstruir_projecoes_energia
    pj, c = reconstruir_projecoes_energia(x.modelo, x.resultado.registros, x.controlador.cfg.malha.delta_s)
    return len(pj) if not c else -1


def _certificados(x) -> str:
    coords = getattr(x.controlador, "coordenacoes", ())
    cs = [c for co in coords if co.sinal is not None for d in co.sinal.diagnostico_modos for c in d.certificados
          if c.startswith("cobertura")]
    return f"{sum(1 for c in cs if ':inviavel' in c)}/{len(cs)}" if coords else "—"


def tabela_campanha(res: dict) -> str:
    ln = ["| Cenário | Estratégia | Situação | k final | Custo realizado [R$] | E final [kWh] | Degradadas | Avaliações "
          "planejador | Certificados A02 (inviável/total) | Projeções B3C4-01 | Tempo planejador [s] | Tempo total [s] |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for nome, (ex, cmp) in res.items():
        for e, l in cmp["linhas"].items():
            ln.append(f"| {nome} | {e} | {l.situacao}{'' if l.classe_falha is None else '/' + l.classe_falha} | "
                      f"{l.intervalos_aplicados} | {_f(l.custo_realizado_R, 2)} | "
                      f"{json.dumps({k: round(v, 6) for k, v in l.energias_finais_kWh.items()})} "
                      f"| {l.janelas_degradadas} | {l.avaliacoes_planejador} | {_certificados(ex[e])} | "
                      f"{_projecoes(ex[e])} | {_f(l.tempo_planejador_s, 3)} | {_f(ex[e].tempo_parede_s, 2)} |")
    return "\n".join(ln)


def _normalizacoes(x) -> str:
    """B3C4-10: normalizações de resíduos do solver no PCC RECONSTRUÍDAS dos artefatos selados (k global da janela)."""
    from ..hierarquia.auditoria import reconstruir_normalizacoes_pcc
    r = x.resultado
    r0, ax = getattr(r, "registros_3c0", None), getattr(r, "anexos_3c3", None)
    if r0 is None or ax is None:
        return "—"
    out = []
    for w in r.registros:
        nz, c = reconstruir_normalizacoes_pcc(x.modelo, [w], r0, ax)
        if c:
            return f"DESVIO {sorted({k.codigo for k in c})}"
        out += [(w.conteudo.janela.k + n.indice_janela, n.grandeza, n.valor_bruto_kW, n.limiar_kW) for n in nz]
    return str(out)


def tabela_h9(res: dict) -> str:
    from ..hierarquia.auditoria import reconstruir_projecoes_energia
    ex = res["h9_pemfc"][0]
    ln = ["| Estratégia | Situação | k final | Custo [R$] | E final [kWh] | PEMFC ligada / p [kW] / tempo no estado [s] "
          "| Obrigações pendentes | Projeções B3C4-01 (k, limite, correção kWh) | Normalizações B3C4-10 (k, grandeza, "
          "bruto kW, limiar kW) | Falha |", "|---|---|---|---|---|---|---|---|---|---|"]
    for e in ("mpc_sem_sinal", "hier_pwl", "hier_ref_dura", "hier_ref_branda", "mpc_encolhido", "open_loop", "oraculo"):
        x = ex[e]
        c, r = x.controlador, x.resultado
        g = c.estado.geracao[0]
        pj, _ = reconstruir_projecoes_energia(x.modelo, r.registros, c.cfg.malha.delta_s)
        f = [k.mensagem[:90] for k in r.registros[-1].conteudo.constatacoes if k.severidade == "erro"][:1]
        ln.append(f"| {e} | {r.situacao} | {c.k} | {r.registro_missao.conteudo.custo_realizado_acumulado.total_R!r} | "
                  f"{[b.energia_kWh for b in c.estado.armazenamento]} | {g.ligado} / {g.potencia_kW} / "
                  f"{g.tempo_no_estado_s} | {c.obrigacoes_pendentes()[0]} | "
                  f"{[(p.indice_global, p.limite, p.correcao_kWh) for p in pj]} | {_normalizacoes(x)} | "
                  f"{f[0] if f else '—'} |")
    return "\n".join(ln)


def tabela_efeitos(res: dict) -> str:
    ln = ["| Cenário | Efeito | a − b | Diferença [R$] | Comparável | Motivo |", "|---|---|---|---|---|---|"]
    for nome, (_, cmp) in res.items():
        for k, e in cmp["efeitos"].items():
            if k.startswith("informacao_perfeita_") and k not in ("informacao_perfeita_mpc_sem_sinal",
                                                                    "informacao_perfeita_hier_pwl"):
                continue
            ln.append(f"| {nome} | {k} | {e.estrategia_a} − {e.estrategia_b} | {_f(e.diferenca_R, 2)} | "
                      f"{'sim' if e.comparavel else 'NÃO'} | {e.motivo[:110]} |")
    return "\n".join(ln)


def sensibilidade_horizontes() -> str:
    c = F.h2_pico_futuro()
    ln = ["| N | H_L | MPC sem sinal [R$] | Hierárquico PWL [R$] | Avaliações | Tempo planejador [s] |",
          "|---|---|---|---|---|---|"]
    for N in (2, 3, 4):
        base = X.executar(c, "mpc_sem_sinal", N=N).resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R
        for H in sorted({N + 1, 6, 8, 10, 12}):
            x = X.executar(c, "hier_pwl", N=N, H_L=H)
            rh = x.resultado.registro_hierarquico
            ln.append(f"| {N} | {H} | {_f(base, 2)} | "
                      f"{_f(x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R, 2)} | "
                      f"{rh.contagens['avaliacoes_planejador']} | {_f(rh.tempos_planejador_s.get('total_s'), 3)} |")
    return "\n".join(ln)


def lambda_por_energia() -> str:
    x = X.executar(F.h2_pico_futuro(), "hier_pwl")
    co = x.controlador.coordenacoes[6]
    m = co.sinal.modos[0]
    ln = ["| Segmento E [kWh] | V nos extremos [R$] | λ_E = −dV/dE [R$/kWh] |", "|---|---|---|"]
    for (a, b), s in zip(zip(m.pontos, m.pontos[1:]), inclinacoes_1d(m.pontos)):
        ln.append(f"| [{a.energias_kWh[0]:g}, {b.energias_kWh[0]:g}] | {a.valor_R:.4f} → {b.valor_R:.4f} | {-s:.4f} |")
    return "\n".join(ln)


def lambda_por_pico() -> str:
    ln = ["| Perfil (previsão causal) | λ₀ em τ_0 (E ∈ [0, 5]) [R$/kWh] |", "|---|---|"]
    b = (F.Banco(pcmax=5.0),)
    for rot, c in (("plana 0,5", F.h1_tarifa_plana(bancos=b)), ("pico h4–5", F.h4_pico_deslocado(4, bancos=b)),
                   ("pico h6–7", F.h4_pico_deslocado(6, bancos=b)), ("pico h8–9", F.h4_pico_deslocado(8, bancos=b))):
        s = X.executar(c, "hier_pwl").controlador.coordenacoes[0].sinal
        ln.append(f"| {rot} | {-inclinacoes_1d(s.modos[0].pontos)[0]:.4f} |")
    return "\n".join(ln)


def custo_computacional() -> str:
    c = F.h2_pico_futuro()
    ln = ["| Configuração | Custo [R$] | Janelas válidas/degradadas | Avaliações | Planejador [s] | Erro máx. [R$] |",
          "|---|---|---|---|---|---|"]
    for rot, kw in (("PWL pontos=3, máx 9", {"pontos": 3, "pontos_max": 9}), ("PWL pontos=5, máx 9", {}),
                    ("PWL pontos=4, máx 4 (sem refinamento)", {"pontos": 4, "pontos_max": 4}),
                    ("periódica P=2", {"periodo": 2}), ("periódica P=3", {"periodo": 3}),
                    ("periódica P=4", {"periodo": 4})):
        x = X.executar(c, "hier_pwl", planejador_kw=kw)
        rh = x.resultado.registro_hierarquico
        co = x.controlador.coordenacoes
        em = max((c_.sinal.qualidade.erro_interpolacao_max_R or 0.0) for c_ in co if c_.sinal is not None)
        ln.append(f"| {rot} | {_f(x.resultado.registro_missao.conteudo.custo_realizado_acumulado.total_R, 2)} | "
                  f"{rh.contagens['valido']}/{rh.contagens['degradado_sem_valor_futuro']} | "
                  f"{rh.contagens['avaliacoes_planejador']} | {_f(rh.tempos_planejador_s.get('total_s'), 3)} | "
                  f"{em:.3g} |")
    return "\n".join(ln)


def ambiente() -> str:
    from ..mpc.orquestrador import ambiente_execucao
    from .ambiente import verificar_ambiente
    return json.dumps({**ambiente_execucao(), "solver": verificar_ambiente()}, sort_keys=True, default=str)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    t0 = time.perf_counter()
    res = campanha(CENARIOS[:4] if "--rapida" in argv else CENARIOS)
    print("## Ambiente\n\n```json\n" + ambiente() + "\n```\n")
    print("## Campanha (estratégias × cenários)\n\n" + tabela_campanha(res) + "\n")
    print("## Efeitos separados\n\n" + tabela_efeitos(res) + "\n")
    if "h9_pemfc" in res:
        print("## H9 — PEMFC: estados finais, memória e obrigações\n\n" + tabela_h9(res) + "\n")
    if "--rapida" not in argv:
        print("## H13 — horizonte curto × longo (H2)\n\n" + sensibilidade_horizontes() + "\n")
        print("## H6/H10 — λ(E) na fronteira b = 9 (τ_6, H2)\n\n" + lambda_por_energia() + "\n")
        print("## H4 — λ₀ × posição do pico\n\n" + lambda_por_pico() + "\n")
        print("## Custo computacional (H2)\n\n" + custo_computacional() + "\n")
    print(f"_Tempo total da evidência: {time.perf_counter() - t0:.1f} s (só este ambiente)._")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
_ = math
