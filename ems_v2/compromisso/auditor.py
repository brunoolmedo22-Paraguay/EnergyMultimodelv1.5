"""Auditor algébrico INDEPENDENTE do perfil 3C-1 (commitment dinâmico) — sem Pyomo/HiGHS, sem ``ems_v2.reference``.

Recebe a entrada 3C-1 e uma candidata EXPLÍCITA (``audit.CandidatoDespacho``; para cada gerador: ``u``, ``p``, ``y``,
``z`` e ``q`` se houver curva PWL) e mede resíduos físicos. Não é solver, não corrige, não recorta: qualquer resíduo
acima da tolerância (as MESMAS tolerâncias provisórias D07 do auditor 3A) rejeita a candidata.

Famílias verificadas:

* núcleo herdado do 3B-P, REIMPLEMENTADO aqui de forma independente: balanço M02 (com a potência dos geradores),
  renováveis M03-v1.1, serviço/descarte M04, BESS M06–M08, domínio ON/OFF M10, vazão PWL M15/M16, KPIs B01 e
  custos (curtailment, throughput, ENS, combustível H₂ com massas de evento m^SU/m^SD, eventos e total);
* M09: integralidade de u, y, z; transição ``u_t − u_{t−1} = y_t − z_t`` com ``u_{−1}`` DECLARADO; ``y + z <= 1``;
  ``u <= a``; eventos fictícios (y sem OFF→ON real, z sem ON→OFF real);
* M11: ``p_t − p_{t−1} <= R⁺Δ u_{t−1} + S⁺ y_t`` e ``p_{t−1} − p_t <= R⁻Δ u_t + S⁻ z_t`` com ``p_{−1}`` declarado;
  transições não representáveis (S < mínimo ON, ou abstração ``transicoes_bloqueadas``) ⇒ y/z devem ser 0;
* M12 em DUAS formas independentes: (i) somas em janela ``Σ_{j=t−U+1}^{t} y_j <= u_t`` e
  ``Σ_{j=t−D+1}^{t} z_j <= 1 − u_t``; (ii) comprimento das corridas ON/OFF reconstruídas da sequência de estados
  (corrida inicial >= obrigação herdada; corrida interna >= U ou D; corrida final conforme a política terminal);
* política terminal ``cumprir_na_janela``: nenhuma partida com t + U > N nem parada com t + D > N;
* fidelidade ao compromisso parcial fixado, quando fornecido.

Discretização RECALCULADA aqui com ``decimal`` (U = ⌈T·60/Δs⌉, D, r = ⌈obrigação/Δs⌉, R·Δ, S efetivos), sem usar
``ems_v2.compromisso.contrato.discretizar`` (que alimenta o MILP): uma conversão errada num dos dois é detectada.
"""
from __future__ import annotations

import math
from decimal import ROUND_CEILING, Decimal

from ..audit import (CandidatoDespacho, RelatorioAuditoria, Tolerancias, _Coletor, _finalizar, _interp_bisect,
                     _tol_custo, _vetor, validar_tolerancias)
from ..diagnostics import Constatacao, erro, pendente
from ..series import alinhar_a_malha
from .contrato import EntradaCommitment3C1
from .preflight import preflight_3c1

RECONSTRUTIVEIS_3C1 = {"curtailment_operacional": "M21-v1.1", "throughput_bess": "M21-v1.1",
                       "energia_nao_suprida": "M21-v1.1", "combustivel_h2": "B05-INST", "eventos": "M21-v1.1",
                       "total": "M21-v1.1"}
NAO_MODELADAS_3C1 = ("auxiliares_evento_M05", "potencias_de_extremo_M11_EXT", "multimodo_M20", "terminal_energia",
                     "valor_futuro")


def _dec(x) -> Decimal:
    return Decimal(repr(float(x))) if not isinstance(x, int) else Decimal(x)


def _ceil_div(num: Decimal, den: Decimal) -> int:
    return int((num / den).to_integral_value(rounding=ROUND_CEILING))


def _discretizacao_independente(e: EntradaCommitment3C1) -> dict[str, dict]:
    m = e.base.malha
    ds = Decimal(m.delta_s)
    dmin = ds / 60
    est = {str(s.uid): s for s in e.base.estados_geradores}
    out = {}
    for g in e.base.geradores:
        k = str(g.uid)
        sp, mem, st = e.unidade(k), e.memoria(k), est[k]
        pmin, pmax = float(g.p_min_kW.valor), float(g.p_max_kW.valor)
        if g.curva_h2 is not None:
            lo, hi = max(pmin, float(g.curva_h2.vertices[0][0])), min(pmax, float(g.curva_h2.vertices[-1][0]))
        else:
            lo, hi = pmin, pmax
        rs = None if sp.rampa_subida_kW_min is None else float(_dec(sp.rampa_subida_kW_min.valor) * dmin)
        rd = None if sp.rampa_descida_kW_min is None else float(_dec(sp.rampa_descida_kW_min.valor) * dmin)
        transita = sp.abstracao_transicao == "instantanea_unidade_quente"
        if not transita:
            Sp = Sd = None
        elif sp.limites_transicao == "declarados":
            Sp, Sd = float(sp.potencia_partida_max_kW.valor), float(sp.potencia_parada_max_kW.valor)
        else:
            Sp, Sd = rs, rd
        U = D = 0
        if transita:
            U = _ceil_div(_dec(sp.tempo_min_ligado_min.valor) * 60, ds)
            D = _ceil_div(_dec(sp.tempo_min_desligado_min.valor) * 60, ds)
        obr = (mem.obrigacao_residual_s or 0) if (transita and mem is not None) else 0
        r = _ceil_div(Decimal(obr), ds) if obr > 0 else 0
        out[k] = dict(lo=lo, hi=hi, rs=rs, rd=rd, Sp=Sp, Sd=Sd, U=U, D=D, r=r, u0=int(bool(st.ligado)),
                      p0=float(st.p_anterior_kW.valor), rep_p=transita and Sp is not None and Sp >= lo,
                      rep_z=transita and Sd is not None and Sd >= lo, transita=transita)
    return out


def _bin(x: float) -> int:
    return 1 if x > 0.5 else 0


def auditar_3c1(e: EntradaCommitment3C1, cand: CandidatoDespacho, tol: Tolerancias = Tolerancias(),
                compromisso_parcial: dict | None = None) -> RelatorioAuditoria:
    col = _Coletor()
    ct = validar_tolerancias(tol)
    if ct:
        col.constatacoes += ct
        return _finalizar(col, [])
    pf = preflight_3c1(e, compromisso_parcial)
    col.constatacoes += pf
    if any(c.severidade in ("erro", "pendente") for c in pf):
        return _finalizar(col, [])
    if cand.auxiliares is not None:
        col.constatacoes.append(pendente("auxiliares_nao_suportados_3C1", "auxiliares", "M05 não é modelado no 3C-1."))
        return _finalizar(col, ["auxiliares_M05"])
    b = e.base
    m = b.malha
    N, h = m.N, m.delta_s / 3600.0
    L = {str(d.uid): alinhar_a_malha(d.potencia, m, "")[0] for d in b.demandas}
    chi = {}
    for d in b.demandas:
        if b.politica_servico.modo == "duro" or d.criticidade == "critica" or d.fracao_interrompivel is None:
            chi[str(d.uid)] = [0.0] * N
        else:
            chi[str(d.uid)] = list(alinhar_a_malha(d.fracao_interrompivel, m, "")[0])
    A = {str(r.uid): alinhar_a_malha(r.potencial, m, "")[0] for r in b.renovaveis}
    aR = {str(r.uid): alinhar_a_malha(r.disponibilidade.serie, m, "")[0] for r in b.renovaveis}
    aB = {str(x.uid): alinhar_a_malha(x.disponibilidade.serie, m, "")[0] for x in b.baterias}
    aG = {str(g.uid): alinhar_a_malha(g.disponibilidade.serie, m, "")[0] for g in b.geradores}
    P_scale = max([1.0] + [sum(L[k][t] for k in L) for t in range(N)] + [sum(A[k][t] for k in A) for t in range(N)]
                  + [max(float(x.p_carga_max_kW.valor), float(x.p_descarga_max_kW.valor)) for x in b.baterias]
                  + [float(g.p_max_kW.valor) for g in b.geradores])
    tolP = tol.potencia_abs_kW + tol.potencia_rel_escala * P_scale
    tb = tol.binario
    for nome, esperados, dados in (("renovaveis", set(A), cand.renovaveis), ("baterias", set(aB), cand.baterias),
                                   ("demandas", set(L), cand.demandas), ("geradores", set(aG), cand.geradores)):
        for k in sorted(set(dados) - esperados):
            col.constatacoes.append(erro("uid_desconhecido_na_candidata", f"{nome}[{k}]", "UID inexistente na entrada."))
        for k in sorted(esperados - set(dados)):
            col.constatacoes.append(erro("variavel_candidata_ausente", f"{nome}[{k}]", "UID sem valores na candidata."))
    gen, carga = [0.0] * N, [0.0] * N
    # ------------------------------------------------ renováveis M03-v1.1
    kpi_ind, kpi_cur, custos = {}, {}, {}
    curt, curt_ok = 0.0, bool(b.renovaveis)
    for r in b.renovaveis:
        k = str(r.uid)
        c = cand.renovaveis.get(k, {})
        P = _vetor(c, "P_R", N, f"renovaveis[{k}].P_R", col, N + 1)
        C = _vetor(c, "C_oper", N, f"renovaveis[{k}].C_oper", col, N + 1)
        kpi_ind[k] = sum((1.0 - aR[k][t]) * A[k][t] for t in range(N)) * h
        if P is None or C is None:
            curt_ok = False
            continue
        for t in range(N):
            gen[t] += P[t]
            col.r("renovavel", "M03-v1.1", k, t, P[t] + C[t] - aR[k][t] * A[k][t], "kW", tolP)
            col.limite_inferior("renovavel", "M03-v1.1", k, t, P[t], 0.0, "kW", tolP)
            col.limite_inferior("renovavel", "M03-v1.1", k, t, C[t], 0.0, "kW", tolP)
            if aR[k][t] == 0.0 and C[t] > tolP:
                col.constatacoes.append(erro("indisponibilidade_registrada_como_curtailment", f"renovaveis[{k}].C_oper[{t}]",
                                             "a = 0: potência indisponível não é vertimento operacional (B01)."))
        kpi_cur[k] = sum(C) * h
        if r.custo_curtailment is not None and r.custo_curtailment.valor is not None:
            curt += float(r.custo_curtailment.valor) * kpi_cur[k]
        else:
            curt_ok = False
    if curt_ok:
        custos["curtailment_operacional"] = curt
    # ------------------------------------------------ demanda M04 e descarte
    ens, ens_ok = 0.0, True
    for d in b.demandas:
        k = str(d.uid)
        ell = _vetor(cand.demandas.get(k, {}), "ell", N, f"demandas[{k}].ell", col, N + 1)
        if ell is None:
            ens_ok = False
            continue
        for t in range(N):
            carga[t] += L[k][t] - ell[t]
            col.limite_inferior("servico", "M04", k, t, ell[t], 0.0, "kW", tolP)
            lim = chi[k][t] * L[k][t]
            col.limite_superior("servico", "M04", k, t, ell[t], lim, "kW", tolP)
            if ell[t] > lim + tolP and lim == 0.0:
                col.constatacoes.append(erro("interrupcao_nao_autorizada", f"demandas[{k}].ell[{t}]",
                                             "Carga desconectada sem autorização (crítica ou serviço duro)."))
        if d.criticidade == "interrompivel":
            if d.custo_energia_nao_suprida is None or d.custo_energia_nao_suprida.valor is None:
                ens_ok = False
            else:
                ens += float(d.custo_energia_nao_suprida.valor) * h * sum(ell)
    if ens_ok:
        custos["energia_nao_suprida"] = ens
    desc = b.politica_servico.descarte
    if desc is not None and cand.descarte is None:
        col.constatacoes.append(erro("variavel_candidata_ausente", "descarte", "Descarte declarado sem d na candidata."))
    elif cand.descarte is not None:
        dv = _vetor({"d": cand.descarte}, "d", N, "descarte", col, N + 1)
        if dv is not None:
            Dmax = 0.0 if desc is None else float(desc.p_max_kW.valor)
            for t in range(N):
                carga[t] += dv[t]
                col.limite_inferior("descarte", "M04", "-" if desc is None else str(desc.uid), t, dv[t], 0.0, "kW", tolP)
                col.limite_superior("descarte", "M04", "-" if desc is None else str(desc.uid), t, dv[t], Dmax, "kW", tolP)
            if desc is None and any(x > tolP for x in dv):
                col.constatacoes.append(erro("descarte_sem_dispositivo_fisico", "descarte", "D̄ = 0 sem dispositivo."))
    # ------------------------------------------------ BESS M06–M08
    e0 = {str(s.uid): float(s.energia_kWh.valor) for s in b.estados_baterias}
    thr, thr_ok = 0.0, True
    for x in b.baterias:
        k = str(x.uid)
        c = cand.baterias.get(k, {})
        Pc = _vetor(c, "P_c", N, f"baterias[{k}].P_c", col, N + 1)
        Pd = _vetor(c, "P_d", N, f"baterias[{k}].P_d", col, N + 1)
        en = _vetor(c, "e", N + 1, f"baterias[{k}].e", col)
        if Pc is None or Pd is None or en is None:
            thr_ok = False
            continue
        Cb = float(x.capacidade_kWh.valor)
        alpha = 1.0 if x.hipotese_autodescarga == "nao_modelada_alpha_1" else math.exp(-float(x.autodescarga_1_h.valor) * h)
        tolE = tol.energia_abs_kWh + tol.energia_rel_capacidade * Cb
        for t in range(N):
            gen[t] += Pd[t] - Pc[t]
            col.limite_inferior("bess_potencia", "M06", k, t, Pc[t], 0.0, "kW", tolP)
            col.limite_inferior("bess_potencia", "M06", k, t, Pd[t], 0.0, "kW", tolP)
            col.limite_superior("bess_potencia", "M06", k, t, Pc[t], aB[k][t] * float(x.p_carga_max_kW.valor), "kW", tolP)
            col.limite_superior("bess_potencia", "M06", k, t, Pd[t], aB[k][t] * float(x.p_descarga_max_kW.valor), "kW", tolP)
            col.r("bess_exclusividade", "M06", k, t, min(Pc[t], Pd[t]), "kW", tolP)
            prev = alpha * en[t] + h * float(x.eta_carga.valor) * Pc[t] - h * Pd[t] / float(x.eta_descarga.valor)
            col.r("bess_energia", "M07", k, t, en[t + 1] - prev, "kWh", tolE)
        col.r("bess_estado_inicial", "M08", k, 0, en[0] - e0[k], "kWh", tolE)
        for i, v in enumerate(en):
            col.limite_inferior("bess_soc", "M08", k, i, v, Cb * float(x.soc_min.valor), "kWh", tol.soc_fracao * Cb)
            col.limite_superior("bess_soc", "M08", k, i, v, Cb * float(x.soc_max.valor), "kWh", tol.soc_fracao * Cb)
        if x.custo_throughput is not None and x.custo_throughput.valor is not None:
            thr += float(x.custo_throughput.valor) * h * (sum(Pc) + sum(Pd))
        else:
            thr_ok = False
    if thr_ok:
        custos["throughput_bess"] = thr
    # ------------------------------------------------ geradores: M09–M12, M10, M15/M16
    disc = _discretizacao_independente(e)
    cp = compromisso_parcial or {}
    termos = set(e.termos)
    pol = e.politica_permanencia.tipo
    h2, h2_ok, ev, ev_ok = 0.0, True, 0.0, True
    residuais: dict[str, float] = {}
    for g in b.geradores:
        k = str(g.uid)
        dz, sp, a = disc[k], e.unidade(k), aG[k]
        c = cand.geradores.get(k, {})
        u = _vetor(c, "u", N, f"geradores[{k}].u", col, N + 1)
        p = _vetor(c, "p", N, f"geradores[{k}].p", col, N + 1)
        y = _vetor(c, "y", N, f"geradores[{k}].y", col, N + 1)
        z = _vetor(c, "z", N, f"geradores[{k}].z", col, N + 1)
        curva = g.curva_h2
        q = _vetor(c, "q", N, f"geradores[{k}].q", col, N + 1) if curva is not None else None
        if curva is None and isinstance(c, dict) and c.get("q") is not None:
            col.constatacoes.append(erro("vazao_sem_curva", f"geradores[{k}].q", "Vazão informada sem curva PWL."))
        if None in (u, p, y, z) or (curva is not None and q is None):
            h2_ok = ev_ok = False
            continue
        ur, yr, zr = [_bin(x) for x in u], [_bin(x) for x in y], [_bin(x) for x in z]
        uprev = [dz["u0"]] + u[:-1]
        urprev = [dz["u0"]] + ur[:-1]
        pprev = [dz["p0"]] + p[:-1]
        Ps = [float(v[0]) for v in curva.vertices] if curva is not None else []
        Qs = [float(v[1]) for v in curva.vertices] if curva is not None else []
        tolQ = tol.vazao_abs_kg_h + tol.vazao_rel_qmax * (max(Qs) if Qs else 0.0)
        for t in range(N):
            gen[t] += p[t]
            for nome, v in (("u", u[t]), ("y", y[t]), ("z", z[t])):
                col.r("integralidade", "M09", k, t, min(abs(v), abs(v - 1.0)), "1", tb)
            col.r("transicao_M09", "M09", k, t, (u[t] - uprev[t]) - (y[t] - z[t]), "1", tb)
            col.limite_superior("eventos_simultaneos", "M09", k, t, y[t] + z[t], 1.0, "1", tb)
            col.limite_superior("disponibilidade_commitment", "M09", k, t, u[t], a[t], "1", tb)
            if yr[t] and not (urprev[t] == 0 and ur[t] == 1):
                col.constatacoes.append(erro("evento_ficticio", f"geradores[{k}].y[{t}]",
                                             "Partida registrada sem transição OFF→ON real."))
                col.r("evento_ficticio", "M09", k, t, 1.0, "1", tb)
            if zr[t] and not (urprev[t] == 1 and ur[t] == 0):
                col.constatacoes.append(erro("evento_ficticio", f"geradores[{k}].z[{t}]",
                                             "Parada registrada sem transição ON→OFF real."))
                col.r("evento_ficticio", "M09", k, t, 1.0, "1", tb)
            if ur[t] == 1 and a[t] != 1.0:
                col.constatacoes.append(erro("on_indisponivel", f"geradores[{k}].u[{t}]", "Unidade ON com a = 0."))
            # M10 (+ PWL)
            if ur[t] == 0:
                col.r("dominio_on_off", "M10", k, t, p[t], "kW", tolP)
                if q is not None:
                    col.r("vazao_pwl", "M16", k, t, q[t], "kg/h", tolQ)
            else:
                col.limite_inferior("dominio_on_off", "M10", k, t, p[t], dz["lo"], "kW", tolP)
                col.limite_superior("dominio_on_off", "M10", k, t, p[t], dz["hi"], "kW", tolP)
                if p[t] < dz["lo"] - tolP or p[t] > dz["hi"] + tolP:
                    col.constatacoes.append(erro("on_fora_do_dominio", f"geradores[{k}].p[{t}]",
                                                 f"ON em {p[t]} kW fora de [{dz['lo']}, {dz['hi']}] kW."))
                elif q is not None:
                    col.r("vazao_pwl", "M16", k, t, q[t] - _interp_bisect(Ps, Qs, min(max(p[t], Ps[0]), Ps[-1])),
                          "kg/h", tolQ)
            # M11 rampas e transições
            if dz["rs"] is not None or dz["rd"] is not None:
                sup = (dz["rs"] or 0.0) * uprev[t] + (dz["Sp"] or 0.0) * y[t]
                inf = (dz["rd"] or 0.0) * u[t] + (dz["Sd"] or 0.0) * z[t]
                if dz["rs"] is None and (uprev[t] > 0.5 and u[t] > 0.5):
                    col.constatacoes.append(erro("rampa_ausente_em_operacao", f"geradores[{k}]", "Rampa não declarada."))
                col.limite_superior("rampa_M11a", "M11a", k, t, p[t] - pprev[t], sup, "kW", tolP)
                col.limite_superior("rampa_M11b", "M11b", k, t, pprev[t] - p[t], inf, "kW", tolP)
            elif ur[t] == 1 or urprev[t] == 1:
                col.constatacoes.append(erro("rampa_ausente_em_operacao", f"geradores[{k}].p[{t}]",
                                             "Unidade em operação sem rampa declarada (ausente ≠ ilimitada)."))
            if not dz["rep_p"]:
                col.r("transicao_nao_representavel", "M11a", k, t, y[t], "1", tb)
                col.r("transicao_nao_representavel", "M09", k, t, max(0.0, u[t] - uprev[t]), "1", tb)
            if not dz["rep_z"]:
                col.r("transicao_nao_representavel", "M11b", k, t, z[t], "1", tb)
                col.r("transicao_nao_representavel", "M09", k, t, max(0.0, uprev[t] - u[t]), "1", tb)
            # M12 (somas em janela)
            U, D = dz["U"], dz["D"]
            if U > 0:
                col.limite_superior("permanencia_M12", "M12", k, t, sum(y[max(0, t - U + 1):t + 1]), u[t], "1", tb)
            if D > 0:
                col.limite_superior("permanencia_M12", "M12", k, t, sum(z[max(0, t - D + 1):t + 1]), 1.0 - u[t], "1", tb)
            if t < min(dz["r"], N):
                col.r("obrigacao_herdada_M12", "M12", k, t, u[t] - dz["u0"], "1", tb)
            if pol == "cumprir_na_janela":
                if U > 0 and t + U > N:
                    col.r("politica_terminal_M12", "M12", k, t, y[t], "1", tb)
                if D > 0 and t + D > N:
                    col.r("politica_terminal_M12", "M12", k, t, z[t], "1", tb)
            fix = cp.get(k)
            if fix is not None and fix[t] is not None:
                col.r("compromisso_parcial", "M09", k, t, u[t] - fix[t], "1", tb)
        # M12 por corridas (forma independente): sequência de estados arredondada
        seq = [dz["u0"]] + ur
        corridas, ini = [], 1
        for t in range(2, N + 2):
            if t == N + 1 or seq[t] != seq[t - 1]:
                corridas.append((ini - 1, t - ini, seq[ini]))      # (intervalo inicial, comprimento, estado)
                ini = t
        for idx, (s0, comp, v) in enumerate(corridas):
            final = s0 + comp == N
            if idx == 0 and v == dz["u0"]:
                exig = min(dz["r"], N)
                col.limite_inferior("permanencia_corridas", "M12", k, s0, comp, exig, "intervalos", 0.0)
                continue
            exig = dz["U"] if v == 1 else dz["D"]
            if not final:
                col.limite_inferior("permanencia_corridas", "M12", k, s0, comp, exig, "intervalos", 0.0)
            elif pol == "cumprir_na_janela":
                col.limite_inferior("permanencia_corridas", "M12", k, s0, comp, exig, "intervalos", 0.0)
            else:
                residuais[k] = max(0, exig - comp)
        # custos
        if "eventos" in termos:
            if sp.custo_partida is not None and sp.custo_parada is not None:
                ev += float(sp.custo_partida.valor) * sum(y) + float(sp.custo_parada.valor) * sum(z)
            elif dz["transita"]:
                ev_ok = False
        if g.tecnologia == "pemfc" and q is not None:
            if g.preco_h2 is not None and g.preco_h2.valor is not None:
                massa = h * sum(q)
                if sp.massa_h2_partida_kg is not None:
                    massa += float(sp.massa_h2_partida_kg.valor) * sum(y) + float(sp.massa_h2_parada_kg.valor) * sum(z)
                elif dz["transita"] and "combustivel_h2" in termos:
                    h2_ok = False
                h2 += float(g.preco_h2.valor) * massa
            else:
                h2_ok = False
    pem = [g for g in b.geradores if g.tecnologia == "pemfc"]
    if h2_ok and (not pem or all(g.curva_h2 is not None for g in pem)):
        custos["combustivel_h2"] = h2
    if ev_ok and "eventos" in termos:
        custos["eventos"] = ev
    # ------------------------------------------------ balanço M02
    for t in range(N):
        col.r("balanco", "M02", "barramento", t, gen[t] - carga[t], "kW", tolP)
    if all(t in custos for t in e.termos):
        custos["total"] = math.fsum(custos[t] for t in e.termos)
    for nome, rep in cand.custos_reportados.items():
        if nome not in RECONSTRUTIVEIS_3C1:
            col.constatacoes.append(pendente("custo_nao_reconstruivel_3C1", f"custos_reportados[{nome}]",
                                             "Termo de custo sem reconstrução independente."))
        elif nome not in custos:
            col.constatacoes.append(erro("custo_nao_reconstruivel", f"custos_reportados[{nome}]",
                                         "Coeficiente ausente: custo reportado não pode ser conferido."))
        else:
            col.r("custo", RECONSTRUTIVEIS_3C1[nome], nome, None, float(rep) - custos[nome], "R$",
                  _tol_custo(tol, custos[nome]))
    kpis = {"E_indisp_kWh": kpi_ind, "E_curt_oper_kWh": kpi_cur,
            "obrigacao_residual_intervalos": {k: float(v) for k, v in residuais.items()}}
    for nome, por_uid in cand.kpis_reportados.items():
        if nome not in kpis:
            col.constatacoes.append(erro("kpi_desconhecido", f"kpis_reportados[{nome}]", "KPI não reconstruível."))
            continue
        for k, v in por_uid.items():
            if k not in kpis[nome]:
                col.constatacoes.append(erro("kpi_uid_desconhecido", f"kpis_reportados[{nome}][{k}]", "UID sem KPI."))
                continue
            col.r("kpi_energia", "B01", k, None, float(v) - kpis[nome][k], "kWh",
                  tol.energia_abs_kWh + tol.energia_rel_capacidade * max(1.0, abs(kpis[nome][k])))
    return _finalizar(col, [], custos, kpis, NAO_MODELADAS_3C1)


__all__ = ["NAO_MODELADAS_3C1", "RECONSTRUTIVEIS_3C1", "auditar_3c1"]
_ = Constatacao
