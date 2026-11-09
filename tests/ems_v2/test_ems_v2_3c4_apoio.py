"""Apoio (sem testes) das suítes 3C-4: entradas de janela sintéticas e sinais SELADOS construídos à mão.

Nada aqui chama o solver. Os sinais são DECLARADOS no teste (pontos analíticos); hashes de procedência fictícios de 64
hexadecimais, com os valores da missão quando a validação de janela os exige.
"""
from __future__ import annotations

from dataclasses import replace

from ems_v2 import fixtures_3c4 as F
from ems_v2.hierarquia import ESQUEMA_3C4, FORMULACAO_3C4
from ems_v2.hierarquia.contrato import (CONVENCAO_SINAIS, EntradaHierarquica3C4, EstadoTerminalGerador, ModoValor,
                                        PontoValor, QualidadeSinal, ReferenciaTerminal, SensibilidadeLocal,
                                        SinalValorFuturo, TermoTerminal3C4, selar_sinal)

H = "a" * 64
MISSAO = "b" * 32


def cenario(K: int = 3, **kw):
    kw.setdefault("bancos", (F.Banco(C=20.0, e0=10.0, pmax=10.0),))
    return F.Cenario3C4("T3C4", K, (10.0,) * K, (0.5,) * K, **kw)


def entrada(K: int = 3, **kw):
    return F.modelo(cenario(K, **kw))


def instante(h: int) -> str:
    return F.serie("potencia", [0], "x").inicio_utc.replace("T00:", f"T{h:02d}:")


def modo(pontos, *, i=0, geradores=(), rep="intervalos_consecutivos_1d", dom=None, conv=True, inv=()):
    pts = tuple(PontoValor(tuple(float(x) for x in (e if isinstance(e, tuple) else (e,))), float(v), float(v), "otimo")
                for e, v in pontos)
    if dom is None:
        d = len(pts[0].energias_kWh)
        dom = (tuple(min(p.energias_kWh[j] for p in pts) for j in range(d)),
               tuple(max(p.energias_kWh[j] for p in pts) for j in range(d)))
    return ModoValor(i, tuple(geradores), rep, pts, tuple(inv), dom[0], dom[1], conv)


def sinal(*, tipo="custo_futuro_pwl", modos=None, baterias=(F.BESS,), geradores=(), k=0, N=3, fim=10, janela=0,
          emissao=None, estado="valido", referencia=None, sens=None, rho=None, microrrede="syn-microrrede-fixture",
          cenario_uid="syn-cenario-3c2", hashes=None, termo_longo=None, missao=MISSAO):
    if modos is None:
        modos = (modo(((0, 35.0), (10, 30.0), (20, 25.0))),)
    return selar_sinal(SinalValorFuturo(
        ESQUEMA_3C4, FORMULACAO_3C4, tipo, missao, microrrede, cenario_uid, janela, k, instante(k),
        emissao or instante(k), k + N, instante(k + N), fim, fim - (k + N), tuple(baterias), tuple(geradores), "R$", "kWh",
        CONVENCAO_SINAIS, tuple(modos), referencia, sens, rho, termo_longo or F.termo_longo(),
        QualidadeSinal(estado, "teste" if estado == "valido" else "indisponível no teste", 0.0, 1e-6, 0.0, 1, ()),
        dict(hashes or {"instantaneo": H, "modelo_rede": H, "configuracao_planejador": H}),
        F.proc("sinal-teste")))


def termo(s, just="Sinal declarado no teste"):
    return TermoTerminal3C4("sinal_valor_futuro", (), (), s, just, F.proc("termo"))


def entrada4(e, t):
    return EntradaHierarquica3C4(ESQUEMA_3C4, FORMULACAO_3C4, e, t, F.proc("entrada4"))


def ger(uid=F.FC, ligado=False, obrig=0, pfix=None):
    return EstadoTerminalGerador(uid, ligado, obrig, pfix)


def ref(E=(10.0,), geradores=()):
    return ReferenciaTerminal(tuple(E), tuple(geradores), None, "plano_longo")


def sens(E0=10.0, d=2.0, V0=30.0, lam=0.5):
    return SensibilidadeLocal(0, (E0,), d, (E0 - d,), (E0 + d,), V0, (V0 + lam * d,), (V0 - lam * d,), (lam,),
                              "diferenca_central")


_ = replace
