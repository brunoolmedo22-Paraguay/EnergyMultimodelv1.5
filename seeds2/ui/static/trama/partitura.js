// PARTITURA — instrumento de rodada do SEEDS2 sobre o marco "seeds2-trama-frame" (Piso 3D-B0/B1).
// Lente Operação + inspetor + explorador de recursos. Só LÊ o marco recebido do Python (dados persistidos da rodada):
// nada é recalculado pelo motor, nada volta ao servidor. O que é DERIVADO aqui (somas por tecnologia, acumulados,
// participação, classificação de comportamento, PWL − modelo) é rotulado como derivado na própria interface.
// Dado ausente no marco (null) aparece como N/D; nenhuma curva é gerada para preencher um gráfico.
const TIPOS = {
  fv: { n: "Solar fotovoltaica", c: COR.fv, ic: "M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8zM12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" },
  wt: { n: "Eólica", c: COR.wt, ic: "M12 12v9.5M12 12l-.9-9h1.8zM12 12l7.4 4.4-.9 1.5zM12 12l-7.4 4.4.9 1.5z" },
  bat: { n: "Bateria", c: COR.bat, ic: "M3.5 8h15v8h-15zM18.5 10.5h2v3h-2M7 10.8v2.4M10 10.8v2.4M13 10.8v2.4" },
  fc: { n: "PEMFC / Hidrogênio", c: COR.fc, ic: "M12 3c3.6 4.3 6 7.3 6 10.6a6 6 0 0 1-12 0C6 10.3 8.4 7.3 12 3z" },
  grid: { n: "Rede / PCC", c: COR.grid, ic: "M12 3l5 18M12 3L7 21M8.4 15h7.2M9.7 10h4.6M5 7h14" },
  dem: { n: "Carga / Demanda", c: "var(--ink-2)", ic: "M13 2.5L5 13.5h6L10 21.5l8-11h-6z" },
  eco: { n: "Custos / Economia", c: "var(--ink-2)", ic: "M4 20h16M7 17V10M12 17V5M17 17v-4" },
};
const ico = (d, s = 16) => `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;
const soma = (a) => a.reduce((x, y) => x + (y || 0), 0);
const acum = (a, f = 1) => { let s = 0; return [0, ...a.map((v) => (s += (v || 0) * f))]; };
const maxv = (...arrs) => Math.max(0, ...arrs.flat().map((v) => (v == null ? 0 : v)));
const teto = (v) => { if (!(v > 0)) return 1; const p = 10 ** Math.floor(Math.log10(v)); return [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].map((m) => m * p).find((x) => x >= v * 1.04) || 10 * p; };
const tk = (mx) => [0, mx / 2, mx], fd = (mx) => (v) => nf(v, mx < 10 ? (mx < 1 ? 2 : 1) : 0);
const ESTADOS = { aprovada: "aprovado", coerente: "coerente", incoerente: "INCOERENTE", nao_aplicavel: "não aplicável", nao_validada: "não validado" };
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function modelo(F) {
  const I = F.intervalos, K = F.rodada.K, hD = (F.rodada.delta_min || 60) / 60, loc = F.fronteiras.local || [];
  const multi = new Set(loc.map((s) => String(s).slice(0, 10))).size > 2, semMin = loc.every((s) => String(s).slice(14, 16) === "00");
  const rot = loc.map((s) => { const t = String(s); const hm = semMin ? t.slice(11, 13) + "h" : t.slice(11, 16); return multi && t.slice(11, 16) === "00:00" ? t.slice(8, 10) + "/" + t.slice(5, 7) : hm; });
  const add = (ls, n = K) => Array.from({ length: n }, (_, i) => ls.reduce((s, a) => s + ((a && a[i]) || 0), 0));
  const R = F.recursos, ren = (k, g) => R[k].map((r) => F.renovaveis[r.uid][g]), bat = (g) => R.bat.map((r) => F.baterias[r.uid][g]), fc = (g) => R.fc.map((r) => F.pemfc[r.uid][g]);
  const din = R.fc.map((r) => F.pemfc[r.uid].dinamica).filter(Boolean);
  const A = {
    demR: I.demanda_realizada_kW, demP: I.demanda_prevista_kW, ens: I.demanda_nao_atendida_kW, at: I.demanda_atendida_kW,
    wtP: add(ren("wt", "P_R_kW")), wtA: add(ren("wt", "A_utilizavel_kW")), wtV: add(ren("wt", "vertimento_kW")),
    fvP: add(ren("fv", "P_R_kW")), fvA: add(ren("fv", "A_utilizavel_kW")), fvV: add(ren("fv", "vertimento_kW")),
    pd: add(bat("P_d_kW")), pc: add(bat("P_c_kW")), fr: add(bat("energia_kWh"), K + 1),
    fcP: add(fc("p_kW")), fcM: add(fc("m_h2_kg")), cH2: add(fc("custo_h2_R")), cEv: add(fc("custo_eventos_R")),
    fcOn: Array.from({ length: K }, (_, i) => R.fc.some((r) => (F.pemfc[r.uid].u || [])[i])),
    dinP: din.length ? Array.from({ length: K }, (_, i) => din.reduce((s, d) => s + ((d.intervalos[i] || {}).p_entregue_media_kW || 0), 0)) : null,
    impR: I.pcc_importacao_realizada_kW || Array(K).fill(0), impP: I.pcc_importacao_programada_kW, expR: I.pcc_exportacao_realizada_kW || Array(K).fill(0),
    tar: I.tarifa_importacao_decisao_R_kWh, cImp: I.custo_importacao_R || Array(K).fill(0), rec: I.receita_exportacao_R, cDes: I.custo_desvio_rede_R || Array(K).fill(0),
    cThr: I.custo_throughput_R || Array(K).fill(0), cInt: I.custo_realizado_intervalo_R, cAcc: I.custo_realizado_acumulado_R, jan: I.janela, ip: I.indice_no_plano, res: I.residuo_balanco_kW,
  };
  A.cap = soma(R.bat.map((r) => (F.baterias[r.uid].resumo || {}).capacidade_kWh));
  const conectado = F.pcc.modo === "conectado";
  const ord = ["fv", "wt", "bat", "fc"].filter((k) => R[k].length).concat(conectado ? ["grid"] : [], ["dem", "eco"]);
  const jan = F.janelas.map((w) => ({ ...w, j: Math.round(w.j), k: Math.round(w.k), Nk: Math.round(w.Nk), mk: Math.round(w.mk), ap: Math.round(w.ap || 0), ok: w.sinal_qualidade === "valido" }));
  const tv = (A.tar || []).filter((t) => t != null), tlo = Math.min(...tv), thi = Math.max(...tv);
  const nivel = (t) => (t == null ? 0 : thi > tlo ? 1 + Math.round((2 * (t - tlo)) / (thi - tlo)) : 2);
  return { K, hD, rot, A, ord, jan, conectado, nivel };
}

function Partitura(root, F) {
  const M = modelo(F), { K, hD, A } = M, R = F.recursos, bus = novoBarramento(), chave = "seeds2.partitura." + F.rodada.uid;
  const S = { cur: 0, pin: false, zoom: 0, ex: null, tab: {}, uid: {}, lay: "side", band: null };
  try { Object.assign(S, JSON.parse(sessionStorage.getItem(chave) || "{}")); } catch (_) { /* sem armazenamento */ }
  S.cur = Math.min(K - 1, Math.max(0, S.cur | 0)); if (S.ex && !M.ord.includes(S.ex)) S.ex = null;
  const salvar = () => { try { sessionStorage.setItem(chave, JSON.stringify(S)); } catch (_) { /* idem */ } };
  let HOOKS = [];
  const lab = (b) => M.rot[b] ?? String(b), ivl = (i) => `${lab(i)}–${lab(i + 1)}`;
  const setCur = (i) => { S.cur = i; HOOKS.forEach((f) => f(i)); salvar(); };
  const onPin = (i) => { S.pin = i != null; if (i != null) S.cur = i; HOOKS.forEach((f) => f(S.cur)); salvar(); };
  const abrir = (k) => { if (!M.ord.includes(k)) return; S.ex = k; salvar(); render(); };
  const fechar = () => { S.ex = null; salvar(); render(); };
  const uidDe = (k) => (R[k] && R[k].length ? (R[k].some((r) => r.uid === S.uid[k]) ? S.uid[k] : R[k][0].uid) : k === "grid" ? "PCC" : "");
  const recDe = (k) => (R[k] || []).find((r) => r.uid === uidDe(k)) || { nome: TIPOS[k].n.split(" / ")[0], tag: null, uid: "" };
  const zooms = [0, ...[2, 4].map((d) => Math.round(K / d)).filter((z) => z >= 4 && z < K)];
  const vista = () => { const z = S.zoom; if (!z || z >= K) return null; const a = Math.min(K - z, Math.max(0, Math.round(S.cur - z / 2 + .5))); return [a, a + z]; };
  const v0 = () => (vista() ? vista()[0] : 0) + .15;
  const zoomSeg = () => (zooms.length < 2 ? null : h("div", { class: "seg", role: "group", "aria-label": "Janela de tempo" }, ...zooms.map((z) => h("button", { "aria-pressed": String((S.zoom || 0) === z), onclick: () => { S.zoom = z; salvar(); render(); } }, z ? nf(z * hD, z * hD % 1 ? 1 : 0) + " h" : "tudo"))));
  const tip = (rows) => (i) => `<b>${ivl(i)} · intervalo ${i}</b>` + rows(i).filter(Boolean).map(([a, b]) => `<div><span>${a}</span><span>${b}</span></div>`).join("");
  const kvh = (rows) => rows.filter(Boolean).map(([a, b]) => `<span>${a}</span><b>${b}</b>`).join("");
  const card = (o) => h("div", { class: "card" + (o.acc ? " acc" : ""), style: o.acc ? `--acc:${o.acc}` : null },
    o.t ? h("h3", { html: o.t + (o.tag ? `<span class="tag ${o.tc || ""}">${o.tag}</span>` : "") }) : null, o.big != null ? h("div", { class: "big", html: o.big }) : null, o.sub ? h("div", { class: "sub", html: o.sub }) : null,
    o.grid ? h("div", { class: "mgrid", html: o.grid.filter(Boolean).map(([a, b]) => `<div><span>${a}</span><b>${b}</b></div>`).join("") }) : null,
    o.kv ? h("div", { class: "kv", html: kvh(o.kv) }) : null, o.nd ? o.nd.map((t) => h("div", { class: "nd", html: "<b>N/D</b> — " + t })) : null, o.note ? h("p", { class: "note", html: o.note }) : null, o.el || null);
  const tarCol = (t) => (t == null ? "var(--field)" : `var(--seq-${M.nivel(t)})`), tarLab = (t) => (t == null ? ["N/D"] : [nf(t, 2), M.nivel(t) === 3 ? "var(--surface)" : "var(--ink)"]);
  const nd = (c, t) => c.text(v0(), c.top + 13, "N/D — " + (t || "dado não persistido nesta rodada"));
  const opts = (extra) => ({ K, lab, bus, pat: "pth", cur: S.cur, pin: S.pin, fill: true, view: vista(), onCur: setCur, onPin, onRes: abrir, ...extra });

  // ---------------------------------------------------------------- lente Operação
  function balanco(g) {
    const inj = [["wt", A.wtP[g]], ["fv", A.fvP[g]], ["bat", A.pd[g]], ["fc", A.fcP[g]], ["grid", A.impR[g]]], con = [["dem", A.at ? A.at[g] : null], ["bat", A.pc[g]], ["grid", A.expR[g]]];
    const tot = Math.max(soma(inj.map((x) => x[1])), 1e-9), seg = (a, ht) => a.filter((x) => x[1] > 1e-6).map(([k, x]) => `<i class="${ht && k !== "dem" ? "ht" : ""}" style="width:${(100 * x) / tot}%;background-color:${COR[k]}" title="${nf(x, 2)} kW"></i>`).join("");
    return h("div", {}, h("div", { class: "bal", html: `<span>injeta</span><div class="b">${seg(inj)}</div><span>consome</span><div class="b">${seg(con, true)}</div>` }),
      h("p", { class: "note", html: `Σ injeção (derivado) = <b>${nf(tot, 2)} kW</b> · resíduo do balanço gravado ${A.res && A.res[g] != null ? A.res[g].toExponential(1) : "N/D"} kW` }));
  }
  function inspetor(g, T) {
    const w = M.jan[Math.round(A.jan[g])], fo = (k) => ({ onpointerenter: () => T() && T().focus(k), onpointerleave: () => T() && T().focus(null), onfocus: () => T() && T().focus(k), onblur: () => T() && T().focus(null), onclick: () => abrir(k) });
    const row = (k, t, val, ref) => h("button", { class: "rowb", ...fo(k), title: "Abrir o painel de " + TIPOS[k].n, html: `<i style="background:${COR[k]}"></i><span>${t}<small>${ref || ""}</small></span><b>${val}<small>kW</small></b>` });
    const n = (k) => (R[k].length > 1 ? ` (${R[k].length})` : "");
    return [
      card({ acc: "var(--ink)", t: `Intervalo ${g}`, tag: S.pin ? "fixado" : "", big: ivl(g), sub: `médias do intervalo · ${esc(F.rodada.fuso || "fuso não declarado")}${w ? " · decidido na janela " + w.j : ""}`, el: balanco(g) }),
      card({ t: "Recursos neste intervalo", tag: "clique para abrir", el: h("div", { class: "rows" }, row("dem", "Demanda", nf(A.demR[g], 1), "prevista " + nf(A.demP ? A.demP[g] : null, 1)),
        R.wt.length ? row("wt", "Eólica" + n("wt"), nf(A.wtP[g], 1), "de " + nf(A.wtA[g], 1)) : null, R.fv.length ? row("fv", "Solar" + n("fv"), nf(A.fvP[g], 1), "de " + nf(A.fvA[g], 1)) : null,
        R.bat.length ? row("bat", "Bateria" + n("bat"), A.pc[g] > 0 ? "−" + nf(A.pc[g], 1) : nf(A.pd[g], 1), A.pc[g] > 0 ? "carga" : A.pd[g] > 0 ? "descarga" : "repouso") : null,
        R.fc.length ? row("fc", "PEMFC" + n("fc"), nf(A.fcP[g], 1), A.fcOn[g] ? (A.dinP ? "dinâmico " + nf(A.dinP[g], 1) : "ligada") : "desligada") : null,
        M.conectado ? row("grid", "Rede", nf(A.impR[g], 1), "programada " + nf(A.impP ? A.impP[g] : null, 1)) : null) }),
      card({ t: "Estados e custos", el: h("div", { class: "kv", html: kvh([R.bat.length ? ["Energia armazenada", `${nf(A.fr[g], 1)} → ${nf(A.fr[g + 1], 1)} kWh`] : null, R.wt.length + R.fv.length ? ["Vertimento renovável", nf(A.wtV[g] + A.fvV[g], 1) + " kW"] : null,
        R.fc.length ? ["H₂ no intervalo", nf(A.fcM[g], 3) + " kg"] : null, M.conectado ? ["Tarifa de decisão", nf(A.tar ? A.tar[g] : null, 2) + " R$/kWh"] : null, ["Custo realizado", "R$ " + nf(A.cInt ? A.cInt[g] : null, 2)], ["Acumulado", "R$ " + nf(A.cAcc ? A.cAcc[g] : null, 2)]]) }) }),
      w ? card({ t: `Decisão · janela ${w.j}`, tag: w.ok ? "com valor futuro" : "sem valor futuro", tc: w.ok ? "ok" : "w", sub: `decidida às ${lab(w.k)} · posição ${Math.round(A.ip[g]) + 1} de ${w.Nk} no plano`,
        note: w.ok ? null : esc(w.sinal_motivo || "sinal de valor futuro indisponível nesta decisão") }) : null];
  }
  function lOperacao() {
    const host = h("div", { class: "host" }), col = h("div", { class: "col" }); let T = null;
    const paint = (i) => col.replaceChildren(...inspetor(i, () => T).filter(Boolean)); paint(S.cur); HOOKS.push(paint);
    const lg = (k, t) => h("button", { class: "leg", onpointerenter: () => T && T.focus(k), onpointerleave: () => T && T.focus(null), onfocus: () => T && T.focus(k), onblur: () => T && T.focus(null), onclick: () => abrir(k), title: "Abrir o painel de " + TIPOS[k].n, html: `<i style="background-color:${COR[k]}"></i>${t}` });
    const inj = [{ v: A.wtP, c: COR.wt, k: "wt" }, { v: A.fvP, c: COR.fv, k: "fv" }, { v: A.pd, c: COR.bat, k: "bat" }, { v: A.fcP, c: COR.fc, k: "fc" }, { v: A.impR, c: COR.grid, k: "grid" }];
    const tot = Array.from({ length: K }, (_, i) => soma(inj.map((s) => s.v[i]))), hi = teto(maxv(tot, A.demR)), lo = teto(maxv(A.pc, A.expR)), temNeg = maxv(A.pc, A.expR) > 1e-6;
    const lanes = [
      { title: "Decisões do MPC · bloco aplicado", h: 36, note: "cheio = com valor futuro · tracejado = sem", draw(c) { M.jan.forEach((w) => { if (!w.ap) return; const e = c.add(sv("rect", { x: c.x(w.k) + 1, y: c.top, width: w.ap * c.cw - 2, height: 16, rx: 4, style: `cursor:pointer;fill:${w.ok ? "var(--ink)" : "none"};stroke:${w.ok ? "var(--ink)" : "var(--ink-3)"}`, "stroke-dasharray": w.ok ? null : "3 3" }));
        e.addEventListener("click", (ev) => { ev.stopPropagation(); S.band = S.band === w.j ? null : w.j; salvar(); render(); }); if (w.ap * c.cw > 22) c.text(w.k + w.ap / 2, c.top + 12, "j" + w.j, { "text-anchor": "middle", "pointer-events": "none", style: `fill:${w.ok ? "var(--surface)" : "var(--ink-2)"};font-weight:600` }); }); } },
      { title: "Atendimento · injeção por recurso × demanda realizada [kW]", h: 130, w: 4, draw(c) { const y = c.sc(temNeg ? -lo * 1.15 : 0, hi); c.grid(y, temNeg ? [-lo, 0, hi / 2, hi] : tk(hi), fd(hi)); c.stack(inj, y); c.stack([{ v: A.pc, hatch: "bat", k: "bat" }, { v: A.expR, hatch: "grid", k: "grid" }], y, { neg: true }); c.step(A.demR, y, { w: 2.2, k: "dem" }); } },
      R.wt.length + R.fv.length ? { title: "Renováveis · aproveitado + vertido = potencial utilizável [kW]", h: 56, w: 1.4, draw(c) { const mx = teto(maxv(Array.from({ length: K }, (_, i) => A.wtA[i] + A.fvA[i]))), y = c.sc(0, mx); c.grid(y, tk(mx), fd(mx)); c.stack([{ v: A.wtP, c: COR.wt, k: "wt" }, { v: A.fvP, c: COR.fv, k: "fv" }, { v: A.wtV, hatch: "wt", k: "wt" }, { v: A.fvV, hatch: "fv", k: "fv" }], y); } } : null,
      R.bat.length ? { title: `Bateria · energia interna nas fronteiras [kWh]${R.bat.length > 1 ? ` · soma de ${R.bat.length} bancos (derivado)` : ""}`, res: "bat", h: 56, w: 1.4, draw(c) { const mx = A.cap > 0 ? Math.max(A.cap, maxv(A.fr)) : teto(maxv(A.fr)), y = c.sc(0, mx * 1.08); c.grid(y, tk(mx), fd(mx)); c.front(A.fr, y, { r: 2.4, k: "bat" }); } } : null,
      R.fc.length ? { title: "PEMFC · potência pedida [kW]" + (A.dinP ? " · ○ modelo dinâmico" : ""), res: "fc", h: 50, w: 1.2, draw(c) { const mx = teto(maxv(A.fcP, A.dinP || [])), y = c.sc(0, mx); c.grid(y, tk(mx), fd(mx)); c.stack([{ v: A.fcP, c: COR.fc, k: "fc" }], y); if (A.dinP) c.dots(A.fcOn.map((u, i) => (u ? A.dinP[i] : null)), y, { k: "fc", r: 2.6 }); } } : null,
      M.conectado ? { title: "Rede · importação realizada [kW] e tarifa de decisão [R$/kWh]", res: "grid", h: 66, w: 1.3, draw(c) { const lim = F.pcc.limite_importacao_kW, mx = teto(Math.max(lim || 0, maxv(A.impR))), yy = (val) => c.bot - 20 - (val / mx) * (c.bot - 20 - c.top); c.grid(yy, tk(mx), fd(mx)); c.stack([{ v: A.impR, c: COR.grid, k: "grid" }], yy); if (lim != null) c.hline(lim, yy, "limite " + nf(lim, 0) + " kW", { c: "var(--bad)" }); if (A.tar) c.strip(A.tar, c.bot - 15, 15, tarCol, tarLab); } } : null,
      { title: "Custo realizado por intervalo [R$]", res: "eco", h: 48, w: 1.1, note: "total R$ " + nf(F.resumo.custo_realizado_total_R, 2), draw(c) { const mx = teto(maxv(A.cInt || [])), y = c.sc(0, mx); c.grid(y, tk(mx), fd(mx)); c.stack([{ v: A.cImp, c: COR.grid, k: "grid" }, { v: A.cH2, c: COR.fc, k: "fc" }, { v: A.cEv, c: COR.fc, k: "fc" }, { v: A.cThr, c: COR.bat, k: "bat" }, { v: A.cDes, c: COR.grid, k: "grid" }], y); } }].filter(Boolean);
    const w = S.band != null ? M.jan[S.band] : null;
    setTimeout(() => { T = trama(host, opts({ lanes, band: w ? [w.k, Math.min(K, w.k + w.Nk)] : null, label: "Partitura da operação" })); });
    const tem = (k) => M.ord.includes(k);
    return h("div", { class: "stage" }, h("div", { class: "panel acc", style: "--acc:var(--ink-3)" },
      h("div", { class: "chead" }, tem("wt") ? lg("wt", "Eólica") : null, tem("fv") ? lg("fv", "Solar") : null, tem("bat") ? lg("bat", "Bateria") : null, tem("fc") ? lg("fc", "PEMFC") : null, tem("grid") ? lg("grid", "Rede") : null,
        h("button", { class: "leg", onclick: () => abrir("dem"), title: "Abrir o painel de Carga / Demanda", html: `<i class="ln" style="background:var(--s-dem)"></i>Demanda` }), h("span", { class: "leg", html: `<i class="ht" style="background-color:var(--ink-3)"></i>hachura = carga da bateria, exportação e vertimento` }), h("span", { class: "grow" }), zoomSeg()), host), col);
  }

  // ---------------------------------------------------------------- painéis por recurso
  function dash(k) {
    const c = TIPOS[k].c, ui = uidDe(k), fonte = F.fontes, T = S.tab[k];
    if (k === "fv" || k === "wt") {
      const r = F.renovaveis[ui], P = r.P_R_kW, Au = r.A_utilizavel_kW, V = r.vertimento_kW, rs = r.resumo || {}, par = r.parametros || {}, dg = r.diagnostico || {}, fv = k === "fv";
      const mx = teto(maxv(Au, P)), part = P.map((p, i) => (A.demR[i] > 0 ? (100 * p) / A.demR[i] : null)), Eac = r.E_aproveitada_acum_kWh, me = teto(maxv(Eac || []));
      return { src: `${fonte.intervalos} · ${fonte.renovaveis}`, lanes: [
        { title: "Potência aproveitada + vertida = potencial utilizável [kW]", h: 110, w: 3, draw(x) { const y = x.sc(0, mx); x.grid(y, tk(mx), fd(mx)); x.stack([{ v: P, c, k }, { v: V, hatch: k }], y); } },
        { title: "Energia aproveitada acumulada [kWh] · valor gravado ao fim de cada intervalo", h: 70, w: 1.6, draw(x) { if (!Eac) return nd(x); const y = x.sc(0, me); x.grid(y, tk(me), fd(me)); x.front([0, ...Eac], y, { c, r: 2.2 }); } },
        { title: "Participação na demanda realizada [%] · derivado: aproveitada ÷ demanda", h: 36, draw(x) { x.strip(part, x.top, 18, (t) => (t == null ? "var(--field)" : `color-mix(in srgb, ${c} ${Math.min(100, Math.round(t))}%, var(--field-2))`), (t) => (t != null && t > .5 ? [nf(t, 0), t > 55 ? "var(--surface)" : "var(--ink)"] : null)); } }],
        tip: tip((i) => [["Potencial utilizável", nf(Au[i], 2) + " kW"], ["Aproveitada", nf(P[i], 2) + " kW"], ["Vertida", nf(V[i], 2) + " kW"], ["Potencial previsto na decisão", nf((r.A_prevista_kW || [])[i], 2) + " kW"]]),
        cards: (i) => [
          card({ acc: c, t: `Instante ${ivl(i)}`, big: `${nf(P[i], 2)}<small>kW aproveitados</small>`, grid: [["Potencial utilizável", nf(Au[i], 2) + " kW"], ["Vertido", nf(V[i], 2) + " kW"], ["Previsto na decisão", nf((r.A_prevista_kW || [])[i], 2) + " kW"], ["Da demanda (derivado)", nf(part[i], 1) + " %"]] }),
          card({ t: "Missão", big: `${nf(rs.energia_aproveitada_kWh, 1)}<small>kWh aproveitados</small>`, grid: [["Potencial utilizável", nf(rs.energia_utilizavel_kWh, 1) + " kWh"], ["Vertida", nf(rs.energia_vertida_kWh, 1) + " kWh"], ["Pico aproveitado", nf(rs.pico_aproveitado_kW, 1) + " kW"], ["Aproveitamento (derivado)", nf(rs.energia_utilizavel_kWh ? (100 * rs.energia_aproveitada_kWh) / rs.energia_utilizavel_kWh : null, 1) + " %"]] }),
          card({ t: "Equipamento e modelo", tag: "gravado na rodada", kv: fv ? [["Módulo", esc(par.modulo ?? "N/D")], ["Arranjo (série × paralelo)", `${par.n_series ?? "N/D"} × ${par.n_parallel ?? "N/D"}`], ["Potência STC", nf(par.p_stc_arranjo_kW, 1) + " kWp"], ["NOCT · γ", `${nf(par.noct_C, 0)} °C · ${nf(par.gamma_pmax_pct_C, 2)} %/°C`], ["Sujeira · η barramento", `${nf(par.sujeira_pct, 0)} % · ${nf(par.eta_conversao_barramento, 2)}`], ["GHI máx. · T célula máx.", `${nf(dg.ghi_max_W_m2, 0)} W/m² · ${nf(dg.temperatura_celula_max_C, 1)} °C`]]
            : [["Aerogerador", esc(par.modelo_aerogerador ?? "N/D")], ["Nominal · quantidade", `${nf(par.potencia_nominal_unidade_kW, 0)} kW · ${par.quantidade ?? "N/D"}`], ["Cut-in · cut-out", `${nf(par.cut_in_m_s, 1)} · ${nf(par.cut_out_m_s, 0)} m/s`], ["Densidade do ar", nf((dg.densidade || {}).media_kg_m3, 3) + " kg/m³"], ["Horas abaixo do cut-in", nf(dg.horas_abaixo_cut_in, 1) + " h"], ["Vento médio · máx.", `${nf(dg.vento_medio_m_s, 1)} · ${nf(dg.vento_max_m_s, 1)} m/s`]],
            note: esc(r.modelo || "") + (F.clima.realizacao === "igual_a_previsao" ? " Realização = previsão nesta rodada (sem erro de previsão renovável)." : ""),
            nd: [(fv ? "irradiância e temperatura" : "velocidade do vento") + " por intervalo: a série climática está na previsão do cenário" + (F.clima.sha256_serie ? ` (SHA-256 ${esc(String(F.clima.sha256_serie).slice(0, 12))}…)` : "") + ", não nos dados da rodada", fv ? "temperatura de célula por intervalo (só o máximo é gravado)" : "curva de potência do aerogerador (está no catálogo, não na rodada)"] })] };
    }
    if (k === "bat") {
      const b = F.baterias[ui], rs = b.resumo || {}, cap = rs.capacidade_kWh, E = b.energia_kWh, pc = b.P_c_kW, pd = b.P_d_kW, dc = b.declaracao || {}, cth = dc.custo_throughput_R_kWh;
      const st = pc.map((p, i) => (p > 1e-6 ? 2 : pd[i] > 1e-6 ? 3 : E[i] > 1e-6 ? 1 : 0)), stN = ["vazia", "preserva", "carga", "descarga"], stC = ["var(--field-2)", "var(--seq-1)", "url(#pth-bat)", c], pres = st.filter((s) => s === 1).length;
      const mE = teto(Math.max(cap || 0, maxv(E))), mP = teto(maxv(pd, [dc.p_descarga_barramento_kW])), mC = teto(maxv(pc, [dc.p_carga_barramento_kW])), thr = pc.map((p, i) => (p + pd[i]) * hD), cT = cth != null ? thr.map((t) => t * cth) : null, mT = teto(maxv(cT || []));
      return { src: `${fonte.intervalos} · ${fonte.fronteiras}`, padL: 70, lanes: [
        { title: "Energia interna nas fronteiras [kWh] · SOC [%]", h: 100, w: 3, draw(x) { const y = x.sc(0, mE * 1.06); x.grid(y, [0, cap / 2, cap].filter((t) => t != null), (t) => `${nf(t, 0)} · ${nf((100 * t) / cap, 0)} %`); if (cap) x.hline(cap, y, `capacidade ${nf(cap, 0)} kWh`); x.front(E, y, { c, r: 2.8 }); } },
        { title: "Potência no barramento [kW] · descarga (+) · carga (−)", h: 84, w: 2, draw(x) { const y = x.sc(-mC * 1.15, mP * 1.1); x.grid(y, [-mC, 0, mP], fd(mP)); x.stack([{ v: pd, c, k }], y); x.stack([{ v: pc, hatch: "bat" }], y, { neg: true }); if (dc.p_descarga_barramento_kW != null) x.text(v0(), y(dc.p_descarga_barramento_kW) - 4, `limite de descarga ${nf(dc.p_descarga_barramento_kW, 0)} kW`); if (dc.p_carga_barramento_kW != null) x.text(v0(), y(-dc.p_carga_barramento_kW) + 12, `limite de carga ${nf(dc.p_carga_barramento_kW, 0)} kW`); } },
        { title: "Comportamento em cada intervalo · derivado de P e E gravados", h: 36, draw(x) { x.strip(st, x.top, 18, (s) => stC[s], (s) => [stN[s], s === 3 ? "var(--surface)" : "var(--ink)", s === 2]); } },
        M.conectado && A.tar ? { title: "Tarifa de decisão do PCC [R$/kWh] · contexto", h: 36, draw(x) { x.strip(A.tar, x.top, 18, tarCol, tarLab); } } : null,
        { title: "Custo de throughput [R$] · derivado: (P carga + P descarga) × Δ × custo declarado", h: 46, w: 1, draw(x) { if (!cT) return nd(x, "custo de throughput não declarado para este banco"); const y = x.sc(0, mT); x.grid(y, [0, mT], fd(mT)); x.stack([{ v: cT, c, k }], y); } }].filter(Boolean),
        tip: tip((i) => [["Energia (início → fim)", `${nf(E[i], 2)} → ${nf(E[i + 1], 2)} kWh`], ["SOC (início → fim)", `${nf(100 * b.soc[i], 1)} → ${nf(100 * b.soc[i + 1], 1)} %`], ["Descarga", nf(pd[i], 2) + " kW"], ["Carga", nf(pc[i], 2) + " kW"], ["Comportamento (derivado)", stN[st[i]]]]),
        cards: (i) => [
          card({ acc: c, t: `Instante ${ivl(i)}`, tag: stN[st[i]], big: `${nf(E[i], 1)} → ${nf(E[i + 1], 1)}<small>kWh</small>`, grid: [["SOC", `${nf(100 * b.soc[i], 0)} → ${nf(100 * b.soc[i + 1], 0)} %`], ["Potência no barramento", pd[i] > 0 ? "+" + nf(pd[i], 1) + " kW" : pc[i] > 0 ? "−" + nf(pc[i], 1) + " kW" : "0 kW"], M.conectado ? ["Tarifa", nf(A.tar ? A.tar[i] : null, 2) + " R$/kWh"] : null, ["Throughput (derivado)", cT ? "R$ " + nf(cT[i], 2) : "N/D"]] }),
          card({ t: "Missão", big: `${nf(rs.energia_descarregada_kWh, 1)}<small>kWh descarregados</small>`, grid: [["Carregados", nf(rs.energia_carregada_kWh, 1) + " kWh"], ["Estado inicial → final", `${nf(rs.energia_inicial_kWh, 1)} → ${nf(rs.energia_final_kWh, 1)} kWh`], ["SOC inicial → final", `${nf(100 * rs.soc_inicial, 0)} → ${nf(100 * rs.soc_final, 0)} %`], ["Throughput (derivado)", nf(soma(thr), 1) + " kWh"], ["Custo de throughput (missão)", R.bat.length === 1 ? "R$ " + nf(F.resumo.componentes_R.throughput_bess, 2) : cT ? "R$ " + nf(soma(cT), 2) : "N/D"], ["Intervalos preservando", `${pres} de ${K}`]] }),
          card({ t: "Limites e declarações", tag: "cenário v" + F.rodada.versao_cenario, kv: [["Capacidade", nf(cap, 1) + " kWh"], ["Carga · descarga no barramento", `${nf(dc.p_carga_barramento_kW, 0)} · ${nf(dc.p_descarga_barramento_kW, 0)} kW`], ["η carga · descarga", `${nf(dc.eta_carga, 2)} · ${nf(dc.eta_descarga, 2)}`], ["Custo de throughput", nf(cth, 3) + " R$/kWh"], ["Autodescarga", esc(dc.hipotese_autodescarga ?? "N/D")]],
            note: "Energia interna (kWh, estado nas fronteiras) e potência no barramento (kW, média do intervalo) são grandezas diferentes e nunca se somam. «Preserva» = potência nula com energia armazenada: a interface descreve, não atribui motivo.", nd: ["tensão, corrente e temperatura do banco (o modelo é energético)"] })] };
    }
    if (k === "fc") {
      const p = F.pemfc[ui], d = p.dinamica, dx = d ? d.intervalos : null, cv = p.curva, dc = p.declaracao || {}, rs = p.resumo || {}, rd = p.resumo_dinamica || {}, md = (p.massas_eventos || {}).modelo_dinamico || {}, t = T || "op";
      const U = p.u, Pk = p.p_kW, Q = p.q_h2_kg_h, Mh = p.m_h2_kg, Ch = p.custo_h2_R, dP = dx ? dx.map((q) => q.p_entregue_media_kW) : null, dM = dx ? dx.map((q) => q.h2_modelo_dinamico_kg) : null;
      const base = { src: `${fonte.intervalos} · ${fonte.pemfc} · ${fonte.pemfc_dinamica}`, tabs: [["op", "Operação"], ["curva", "Curva q(P) e B04"], ["din", "Verificação dinâmica"]], tab: t };
      const dom = cv ? cv.dominio_kW : [dc.p_min_kW, null], mP = teto(maxv(Pk, [dom[1]])), mQ = teto(maxv(Q)), mM = teto(maxv(Mh, dM || [])), mC = teto(maxv(Ch || []));
      if (t === "op") return { ...base, lanes: [
        { title: "Estado da unidade · partidas e paradas", h: 36, draw(x) { x.strip(U, x.top, 18, (u) => (u ? c : "var(--field-2)"), (u, i) => [p.partida[i] ? (x.cw > 64 ? "▲ partida" : "▲") : p.parada[i] ? (x.cw > 64 ? "▼ parada" : "▼") : u ? "ON" : "", u ? "var(--surface)" : "var(--ink-2)"]); } },
        { title: "Potência líquida pedida [kW]" + (dP ? " · ○ entregue no modelo dinâmico" : ""), h: 84, w: 2.4, draw(x) { const y = x.sc(0, mP * 1.08); x.grid(y, tk(mP), fd(mP)); x.stack([{ v: Pk, c, k }], y); if (dP) x.dots(U.map((u, i) => (u ? dP[i] : null)), y); if (dom[1] != null) x.text(v0(), y(dom[1]) - 4, `P máx ${nf(dom[1], 0)} kW`); if (dom[0] != null) x.text(v0(), y(dom[0]) - 4, `P mín técnica ${nf(dom[0], 0)} kW`); } },
        { title: "Vazão de H₂ suprido [kg/h] · PWL certificada", h: 60, w: 1.4, draw(x) { const y = x.sc(0, mQ); x.grid(y, tk(mQ), fd(mQ)); x.step(Q, y, { c, w: 2.2 }); } },
        { title: "Massa de H₂ por intervalo [kg] · barra = EMS" + (dM ? " · ○ = modelo dinâmico" : ""), h: 60, w: 1.4, draw(x) { const y = x.sc(0, mM); x.grid(y, tk(mM), fd(mM)); x.stack([{ v: Mh, c, k }], y); if (dM) x.dots(U.map((u, i) => (u || p.parada[i] ? dM[i] : null)), y); } },
        { title: "Massa de H₂ acumulada [kg] · valor gravado ao fim de cada intervalo", h: 56, w: 1.2, draw(x) { const a = p.m_h2_acum_kg; if (!a) return nd(x); const mA = teto(maxv(a)), y = x.sc(0, mA); x.grid(y, tk(mA), fd(mA)); x.front([0, ...a], y, { c, r: 2.2 }); } },
        { title: "Custo do hidrogênio [R$]", h: 50, w: 1, draw(x) { if (!Ch || Ch.every((q) => q == null)) return nd(x, "termo de combustível não declarado no objetivo"); const y = x.sc(0, mC); x.grid(y, tk(mC), fd(mC)); x.stack([{ v: Ch, c, k }], y); } }],
        tip: tip((i) => [["Estado", U[i] ? "ON" : "OFF"], ["Potência pedida", nf(Pk[i], 2) + " kW"], dP ? ["Entregue (dinâmico)", U[i] ? nf(dP[i], 2) + " kW" : "—"] : null, ["Vazão de H₂", nf(Q[i], 3) + " kg/h"], ["Massa no intervalo", nf(Mh[i], 3) + " kg"], ["Custo", "R$ " + nf(Ch ? Ch[i] : null, 2)]]),
        cards: (i) => [
          card({ acc: c, t: `Instante ${ivl(i)}`, tag: p.partida[i] ? "partida" : p.parada[i] ? "parada" : U[i] ? "ON" : "OFF", big: `${nf(Pk[i], 2)}<small>kW pedidos</small>`, grid: [["Entregue (dinâmico)", dP ? (U[i] ? nf(dP[i], 2) + " kW" : "—") : "N/D"], ["Vazão de H₂", nf(Q[i], 3) + " kg/h"], ["Massa (EMS · dinâmico)", `${nf(Mh[i], 3)} · ${dM ? nf(dM[i], 3) : "N/D"} kg`], ["Custo do H₂", "R$ " + nf(Ch ? Ch[i] : null, 2)]] }),
          card({ t: "Missão", big: `${nf(rs.massa_h2_kg, 3)}<small>kg de H₂</small>`, grid: [["Energia elétrica", nf(rs.energia_kWh, 1) + " kWh"], ["Custo do H₂", "R$ " + nf(rs.custo_h2_R, 2)], ["Consumo específico", nf(rs.consumo_especifico_kg_kWh, 4) + " kg/kWh"], ["Horas ligada", nf(rs.horas_ligada, 1) + " h"], ["Partidas · paradas", `${rs.partidas ?? "N/D"} · ${rs.paradas ?? "N/D"}`], ["Potência média ligada", nf(rs.potencia_media_ligada_kW, 1) + " kW"]] }),
          card({ t: "Restrições operacionais", tag: "cenário v" + F.rodada.versao_cenario, kv: [["Domínio de potência", `${nf(dom[0], 0)} – ${nf(dom[1], 0)} kW`], ["Rampa", nf(dc.rampa_kW_min, 0) + " kW/min"], ["Tempo mínimo ON · OFF", `${nf(dc.t_on_min, 0)} · ${nf(dc.t_off_min, 0)} min`], ["Partida/parada no MILP", esc(dc.abstracao ?? "N/D")], ["Massa por partida · parada", `${nf((p.massas_eventos || {}).m_partida_kg, 4)} · ${nf((p.massas_eventos || {}).m_parada_kg, 4)} kg`], ["Preço do H₂", nf(dc.preco_h2_R_kg, 2) + " R$/kg"]], note: "OFF = (0 kW, 0 kg/h) é um estado separado; não existe operação entre 0 e a potência mínima." })] };
      if (t === "din") { if (!dx) return { ...base, lanes: [{ title: "Verificação dinâmica", h: 60, draw(x) { nd(x, "verificação dinâmica não gravada nesta rodada (contrato de dados anterior ao 3D-A2-H)"); } }], cards: () => [card({ t: "Verificação dinâmica", nd: ["v2/pemfc_dinamica.json não existe nesta rodada"] })] };
        const mE = teto(maxv(dx.map((q) => q.energia_solicitada_kWh), dx.map((q) => q.energia_entregue_kWh)));
        return { ...base, lanes: [
          { title: "Estados percorridos pelo modelo dinâmico", h: 36, draw(x) { x.strip(dx, x.top, 18, (q) => (q.evento === "desligada" ? "var(--field-2)" : c), (q) => [q.evento === "desligada" ? "" : (q.estados || []).join("→"), "var(--surface)"]); } },
          { title: "Energia por intervalo [kWh] · barra = pedida · ○ = entregue", h: 84, w: 2.2, draw(x) { const y = x.sc(0, mE); x.grid(y, tk(mE), fd(mE)); x.stack([{ v: dx.map((q) => q.energia_solicitada_kWh), c, k }], y); x.dots(dx.map((q) => (q.energia_solicitada_kWh > 0 ? q.energia_entregue_kWh : null)), y); } },
          { title: "Entregue − pedida [kWh] · derivado · tolerância gravada por intervalo", h: 38, draw(x) { x.strip(dx, x.top, 18, (q) => (q.energia_solicitada_kWh > 0 ? "var(--field-2)" : "var(--field)"), (q) => (q.energia_solicitada_kWh > 0 ? [nf(q.energia_entregue_kWh - q.energia_solicitada_kWh, 3)] : null)); } },
          { title: "H₂ por intervalo [kg] · barra = EMS · ○ = modelo dinâmico", h: 70, w: 1.8, draw(x) { const y = x.sc(0, mM); x.grid(y, tk(mM), fd(mM)); x.stack([{ v: dx.map((q) => q.h2_ems_kg), c, k }], y); x.dots(dx.map((q) => (q.evento !== "desligada" ? q.h2_modelo_dinamico_kg : null)), y); } },
          { title: "Coerência por intervalo · energia e H₂ (gravada)", h: 36, draw(x) { x.strip(dx, x.top, 18, (q) => (q.coerente_energia && q.coerente_h2 ? "color-mix(in srgb, var(--ok) 22%, var(--surface))" : "color-mix(in srgb, var(--bad) 45%, var(--surface))"), (q) => [q.coerente_energia && q.coerente_h2 ? "✓" : "✕", q.coerente_energia && q.coerente_h2 ? "var(--ok)" : "var(--bad)"]); } }],
          tip: tip((i) => [["Evento", esc(dx[i].evento)], ["Estados", esc((dx[i].estados || []).join(" → "))], ["Energia pedida", nf(dx[i].energia_solicitada_kWh, 3) + " kWh"], ["Energia entregue", nf(dx[i].energia_entregue_kWh, 3) + " kWh"], ["H₂ do EMS", nf(dx[i].h2_ems_kg, 4) + " kg"], ["H₂ dinâmico", nf(dx[i].h2_modelo_dinamico_kg, 4) + " kg"]]),
          cards: (i) => { const q = dx[i], ok = q.coerente_energia && q.coerente_h2; return [
            card({ acc: c, t: `Instante ${ivl(i)}`, tag: ok ? "coerente" : "incoerente", tc: ok ? "ok" : "b", big: `${nf(q.energia_entregue_kWh, 2)}<small>kWh entregues</small>`, grid: [["Pedidos", nf(q.energia_solicitada_kWh, 2) + " kWh"], ["Tolerância de energia", "± " + nf(q.tolerancia_energia_kWh, 2) + " kWh"], ["H₂ EMS · dinâmico", `${nf(q.h2_ems_kg, 3)} · ${nf(q.h2_modelo_dinamico_kg, 3)} kg`], ["Estados", esc((q.estados || []).join(" → "))]] }),
            card({ t: "Missão · verificação a posteriori", tag: rd.coerente ? "coerente" : "incoerente", tc: rd.coerente ? "ok" : "b", big: `${nf(rd.energia_entregue_kWh, 2)}<small>de ${nf(rd.energia_solicitada_kWh, 2)} kWh</small>`, grid: [["H₂ do EMS", nf(rd.h2_ems_kg, 3) + " kg"], ["H₂ do modelo dinâmico", nf(rd.h2_modelo_dinamico_kg, 3) + " kg"], ["Intervalos incoerentes", String(rd.intervalos_incoerentes ?? "N/D")], ["Subestimação de H₂ máx.", nf(rd.h2_subestimacao_max_kg, 4) + " kg"]] }),
            card({ t: "Modelo dinâmico aproximado", kv: [["Rampa de subida · descida", `${nf(md.rampa_subida_kW_s, 1)} · ${nf(md.rampa_descida_kW_s, 1)} kW/s`], ["Partida · parada", `${nf(md.partida_s, 0)} · ${nf(md.parada_s, 0)} s`], ["Potência de espera (IDLE)", nf(md.idle_kW, 0) + " kW"], ["Temperatura ambiente", nf(p.temperatura_ambiente_C, 0) + " °C"]],
              note: "As consignas do EMS (abstração instantânea) são reavaliadas pelo modelo dinâmico depois da missão. Coerência dinâmica não é validação física: nenhum equipamento real foi ensaiado.", nd: ["medições de equipamento real (validação física não realizada)"] })]; } }; }
      if (!cv) return { ...base, lanes: [{ title: "Curva q(P)", h: 60, draw(x) { nd(x, "curva e certificado não gravados nesta rodada"); } }], cards: () => [card({ t: "Curva q(P) e B04", nd: ["v2/pemfc.json não existe nesta rodada"] })] };
      const V = cv.vertices || [], pwl = (P) => { for (let n = 1; n < V.length; n++) if (P <= V[n][0]) return V[n - 1][1] + ((P - V[n - 1][0]) / (V[n][0] - V[n - 1][0])) * (V[n][1] - V[n - 1][1]); return V.length ? V[V.length - 1][1] : null; };
      const mt = cv.metricas || {}, b4 = cv.b04 || {}, crit = b4.criterios || [], xM = teto(dom[1] || maxv(cv.P_kW)), qM = teto(maxv(cv.q_suprido_kg_h));
      const critN = { erro_rel_max: ["Erro relativo máximo", (x) => nf(100 * x, 3) + " %"], erro_abs_max_kg_h: ["Erro absoluto máximo", (x) => nf(1000 * x, 2) + " g/h"], subestimacao_rel_max: ["Subestimação relativa máxima", (x) => nf(100 * x, 3) + " %"], erro_massa_temporal_rel_max: ["Erro de massa nos perfis temporais", (x) => nf(100 * x, 3) + " %"], pontos_validacao_min: ["Pontos de validação", (x) => nf(x, 0)] };
      const cf = (q) => (critN[q.criterio] ? critN[q.criterio] : [q.criterio.replace(/_/g, " "), (x) => (typeof x === "boolean" ? (x ? "sim" : "não") : String(x))]);
      return { ...base, special(host, i) {
        const a = h("div", { style: "flex:1.7 1 0;min-height:230px;position:relative" }), b = h("div", { style: "flex:1 1 0;min-height:150px;position:relative" });
        host.replaceChildren(h("div", { style: "display:flex;flex-direction:column;gap:6px;height:100%" }, h("div", { class: "chead" }, h("span", { class: "leg", html: `<i class="ln" style="background:var(--ink-2)"></i>modelo estacionário (${cv.P_kW.length} pontos gravados)` }), h("span", { class: "leg", html: `<i style="background:none;box-shadow:inset 0 0 0 2px ${c};border-radius:50%"></i>PWL certificada (${V.length} vértices)` }), h("span", { class: "leg", html: `<i style="background:${c};border-radius:50%"></i>pontos operados na missão` })), a, b));
        const ops = U.map((u, n) => (u ? [Pk[n], Q[n], n] : null)).filter(Boolean);
        xy(a, { x: [0, xM * 1.04], y: [0, qM], xl: "potência líquida [kW]", yl: "vazão de H₂ suprido [kg/h]", label: "Curva característica q(P)",
          near(xv) { if (xv < dom[0] || xv > dom[1]) return null; let n = 0; cv.P_kW.forEach((P, j) => { if (Math.abs(P - xv) < Math.abs(cv.P_kW[n] - xv)) n = j; }); const P = cv.P_kW[n], qm = cv.q_suprido_kg_h[n]; return { x: P, y: qm, html: `<b>P = ${nf(P, 2)} kW</b><div><span>Modelo (gravado)</span><span>${nf(qm, 4)} kg/h</span></div><div><span>PWL (derivado)</span><span>${nf(pwl(P), 4)} kg/h</span></div><div><span>Diferença</span><span>${nf(1000 * (pwl(P) - qm), 2)} g/h</span></div>${cv.corrente_A ? `<div><span>Corrente</span><span>${nf(cv.corrente_A[n], 0)} A</span></div>` : ""}` }; },
          draw({ svg, X, Y, pt, H, pb }) { if (dom[0] > 0) svg.append(sv("rect", { x: X(0), y: pt, width: X(dom[0]) - X(0), height: H - pb - pt, style: "fill:var(--field)" }), sv("text", { x: X(dom[0] / 2), y: pt + 14, "text-anchor": "middle" }, "sem operação"), sv("text", { x: X(dom[0] / 2), y: pt + 27, "text-anchor": "middle" }, "entre 0 e P mín"));
            svg.append(sv("polyline", { points: cv.P_kW.map((P, j) => `${X(P)},${Y(cv.q_suprido_kg_h[j])}`).join(" "), fill: "none", style: "stroke:var(--ink-2);stroke-width:2.4" }), sv("polyline", { points: V.map((q) => `${X(q[0])},${Y(q[1])}`).join(" "), fill: "none", style: `stroke:${c};stroke-width:1.2` }));
            V.forEach((q) => svg.append(sv("circle", { cx: X(q[0]), cy: Y(q[1]), r: 3.2, style: `fill:var(--surface);stroke:${c};stroke-width:1.6` })));
            svg.append(sv("rect", { x: X(0) - 4, y: Y(0) - 4, width: 8, height: 8, style: `fill:var(--surface);stroke:${c};stroke-width:1.6` }), sv("text", { x: X(0) + 9, y: Y(0) - 7 }, "OFF (0; 0)"));
            ops.forEach(([P, q, n]) => { svg.append(sv("circle", { cx: X(P), cy: Y(q), r: n === i ? 7 : 4.5, style: `fill:${c};stroke:var(--surface);stroke-width:1.5` })); if (n === i) svg.append(sv("circle", { cx: X(P), cy: Y(q), r: 11, fill: "none", style: "stroke:var(--ink);stroke-width:1.5" }), sv("text", { x: X(P) + 15, y: Y(q) + 4, style: "fill:var(--ink);font-weight:600" }, `${lab(n)}: ${nf(P, 1)} kW · ${nf(q, 3)} kg/h`)); }); } });
        const er = (cv.validacao || []).map((q) => [q[0], 1000 * (pwl(q[0]) - q[1])]);
        if (!er.length) return b.replaceChildren(h("div", { class: "nd", html: "<b>N/D</b> — pontos de validação não gravados nesta rodada" }));
        const e1 = Math.max(...er.map((q) => q[1])), e0 = Math.min(0, ...er.map((q) => q[1])), pad = (e1 - e0) * .12 || 1;
        xy(b, { x: [0, xM * 1.04], y: [e0 - pad, e1 + pad], xl: `potência líquida [kW] · ${er.length} pontos de validação gravados`, yl: "PWL − modelo [g/h] · derivado dos pontos gravados", label: "Erro da aproximação PWL",
          draw({ svg, X, Y }) { svg.append(sv("polyline", { points: er.map((q) => `${X(q[0])},${Y(q[1])}`).join(" "), fill: "none", style: `stroke:${c};stroke-width:1.6` })); } });
      }, cards: (i) => [
        card({ acc: c, t: "Certificação B04", tag: "matemática", big: `${nf(100 * mt.erro_rel_max, 3)}<small>% de erro relativo máximo</small>`, sub: `política ${esc(b4.politica ?? "N/D")} · ${esc(String(b4.situacao_politica ?? "").replace(/_/g, " "))} · ${crit.filter((q) => q.atendido).length} de ${crit.length} critérios`,
          el: h("table", { style: "margin-top:8px", html: "<tr><th>Critério</th><th class=n>Valor</th><th class=n>Limiar</th></tr>" + crit.map((q) => `<tr><td>${esc(cf(q)[0])}</td><td class="n">${cf(q)[1](q.valor)}</td><td class="n dim3">${q.criterio === "pontos_validacao_min" ? "≥ " : typeof q.limiar === "boolean" ? "" : "≤ "}${cf(q)[1](q.limiar)}</td></tr>`).join("") }),
          note: "A B04 certifica que a PWL reproduz o <b>modelo aproximado</b> dentro dos limiares. Não valida o modelo nem o equipamento: não é validação experimental." }),
        card({ t: U[i] ? `Instante ${ivl(i)}` : `Instante ${ivl(i)} · unidade desligada`, big: U[i] ? `${nf(Q[i], 3)}<small>kg/h a ${nf(Pk[i], 1)} kW</small>` : `0<small>kg/h</small>`, sub: U[i] ? "ponto destacado na curva" : "OFF é um estado separado no MILP" }),
        card({ t: "Modelo de origem", tag: "aproximado", kv: [["Stack · ânodo · cátodo", `${nf((cv.condicoes || {}).temperatura_stack_K, 2)} K · ${nf((cv.condicoes || {}).pressao_anodo_kPag, 0)} · ${nf((cv.condicoes || {}).pressao_catodo_kPag, 0)} kPa(g)`], ["Corrente no domínio", `${nf(mt.corrente_pmin_A, 0)} – ${nf(mt.corrente_pmax_A, 0)} A`], ["Consumo em P mín · P máx", `${nf(mt.consumo_especifico_pmin_kg_kWh, 4)} · ${nf(mt.consumo_especifico_pmax_kg_kWh, 4)} kg/kWh`], ["Curva (SHA-256)", esc(String(cv.sha_curva ?? "N/D").slice(0, 16)) + "…"], ["Certificado (SHA-256)", esc(String(cv.sha_certificado ?? "N/D").slice(0, 16)) + "…"]],
          note: esc(cv.fonte || "") + ". Uma curva por configuração física, reutilizada em toda a missão.", nd: ["caracterização experimental do equipamento instalado"] })] };
    }
    if (k === "grid") {
      const lim = F.pcc.limite_importacao_kW, I = F.intervalos, noLim = lim != null ? A.impR.filter((p) => p >= lim - 1e-6).length : null, dev = A.impP ? Math.max(...A.impR.map((p, i) => Math.abs(p - (A.impP[i] ?? p)))) : null;
      const mI = teto(Math.max(lim || 0, maxv(A.impR))), mE = teto(maxv(A.expR)), temExp = maxv(A.expR) > 1e-9, mC = teto(maxv(A.cImp)), ac = acum(A.cImp), mA = teto(maxv(ac)), eImp = F.resumo.energia_importada_kWh;
      return { src: fonte.intervalos + " (anexo de rede)", lanes: [
        { title: "Importação [kW] · barra = realizada · traço = programada", h: 100, w: 3, draw(x) { const y = x.sc(0, mI * 1.1); x.grid(y, tk(mI), fd(mI)); x.stack([{ v: A.impR, c, k }], y); if (A.impP) x.step(A.impP, y, { c: "var(--ink)", w: 1.4, dash: "4 3" }); if (lim != null) x.hline(lim, y, `limite de importação ${nf(lim, 0)} kW`, { c: "var(--bad)" }); } },
        { title: "Exportação realizada [kW]", h: temExp ? 60 : 34, w: temExp ? 1.4 : 0, draw(x) { if (!temExp) return x.text(v0(), x.top + 13, `0 kW em todos os intervalos · sentidos declarados: ${String(F.pcc.sentidos ?? "N/D").replace(/_/g, " ")}`); const y = x.sc(0, mE); x.grid(y, tk(mE), fd(mE)); x.stack([{ v: A.expR, hatch: "grid" }], y); } },
        A.tar ? { title: "Tarifa de importação na decisão [R$/kWh]", h: 36, draw(x) { x.strip(A.tar, x.top, 18, tarCol, tarLab); } } : null,
        { title: "Custo de importação por intervalo [R$]", h: 60, w: 1.5, draw(x) { const y = x.sc(0, mC); x.grid(y, tk(mC), fd(mC)); x.stack([{ v: A.cImp, c, k }], y); } },
        { title: "Custo de importação acumulado [R$] · derivado", h: 60, w: 1.5, draw(x) { const y = x.sc(0, mA); x.grid(y, tk(mA), fd(mA)); x.front(ac, y, { c, r: 2.2 }); } }].filter(Boolean),
        tip: tip((i) => [["Importação realizada", nf(A.impR[i], 2) + " kW"], ["Importação programada", nf(A.impP ? A.impP[i] : null, 2) + " kW"], ["Exportação realizada", nf(A.expR[i], 2) + " kW"], ["Tarifa de decisão", nf(A.tar ? A.tar[i] : null, 2) + " R$/kWh"], ["Preço de liquidação", nf((I.preco_importacao_liquidacao_R_kWh || [])[i], 2) + " R$/kWh"], ["Custo", "R$ " + nf(A.cImp[i], 2)]]),
        cards: (i) => [
          card({ acc: c, t: `Instante ${ivl(i)}`, tag: lim != null && A.impR[i] >= lim - 1e-6 ? "no limite" : "", tc: "w", big: `${nf(A.impR[i], 2)}<small>kW importados</small>`, grid: [["Programada", nf(A.impP ? A.impP[i] : null, 2) + " kW"], ["Tarifa", nf(A.tar ? A.tar[i] : null, 2) + " R$/kWh"], ["Custo", "R$ " + nf(A.cImp[i], 2)], lim != null ? ["Folga até o limite", nf(lim - A.impR[i], 1) + " kW"] : null] }),
          card({ t: "Missão", big: `${nf(eImp, 1)}<small>kWh importados</small>`, grid: [["Custo de importação", "R$ " + nf(F.resumo.gasto_importacao_R, 2)], ["Preço médio pago (derivado)", nf(eImp ? F.resumo.gasto_importacao_R / eImp : null, 3) + " R$/kWh"], ["Intervalos no limite", noLim == null ? "N/D" : `${noLim} de ${K}`], ["Desvio máx. programado × realizado", nf(dev, 3) + " kW"], ["Exportada", nf(F.resumo.energia_exportada_kWh, 1) + " kWh"], ["Receita de exportação", "R$ " + nf(F.resumo.receita_exportacao_R, 2)]] }),
          card({ t: "Declaração do PCC", tag: esc(F.pcc.procedencia || ""), tc: "w", kv: [["Modo", esc(F.pcc.modo ?? "N/D")], ["Sentidos", esc(String(F.pcc.sentidos ?? "N/D").replace(/_/g, " "))], ["Limite de importação", nf(lim, 0) + " kW"], ["Limite de exportação", nf(F.pcc.limite_exportacao_kW, 0) + " kW"], ["Ajuste na execução", esc(String(F.pcc.ajuste ?? "N/D").replace(/_/g, " "))]], note: esc(F.pcc.rotulo_tarifa || "") + " Intercâmbio agregado no ponto de conexão: não é fluxo de potência AC nem fatura real.", nd: ["tensão, reativo, perdas e demanda contratada (fora do modelo)"] })] };
    }
    if (k === "dem") {
      const at = A.at || A.demR.map((d, i) => d - (A.ens[i] || 0)), pk = A.demR.indexOf(Math.max(...A.demR)), mn = A.demR.indexOf(Math.min(...A.demR)), nDef = A.ens.filter((e) => e > 1e-9).length, mD = teto(maxv(A.demR, A.demP || [])), mJ = teto(maxv(Array.from({ length: K }, (_, i) => A.wtP[i] + A.fvP[i] + A.pd[i] + A.fcP[i] + A.impR[i]))), mEn = teto(maxv(A.ens));
      const dif = A.demP ? A.demR.map((d, i) => (A.demP[i] == null ? null : d - A.demP[i])) : null;
      return { src: fonte.intervalos, lanes: [
        { title: "Demanda [kW] · linha = realizada · tracejado = prevista na decisão · área = atendida", h: 100, w: 3, draw(x) { const y = x.sc(0, mD); x.grid(y, tk(mD), fd(mD)); x.stack([{ v: at, c: "color-mix(in srgb, var(--ink) 16%, var(--surface))" }], y); if (A.demP) x.step(A.demP, y, { c: "var(--ink-3)", w: 1.4, dash: "4 3" }); x.step(A.demR, y, { w: 2.2 }); } },
        { title: "Déficit [kW]", h: nDef ? 60 : 34, w: nDef ? 1.4 : 0, draw(x) { if (!nDef) return x.text(v0(), x.top + 13, `nenhum déficit: 0 kW em ${K} de ${K} intervalos`); const y = x.sc(0, mEn); x.grid(y, tk(mEn), fd(mEn)); x.stack([{ v: A.ens, c: "var(--bad)" }], y); } },
        { title: "Quem injetou no barramento [kW] · inclui a potência que carregou a bateria", h: 90, w: 2.4, draw(x) { const y = x.sc(0, mJ); x.grid(y, tk(mJ), fd(mJ)); x.stack([{ v: A.wtP, c: COR.wt, k: "wt" }, { v: A.fvP, c: COR.fv, k: "fv" }, { v: A.pd, c: COR.bat, k: "bat" }, { v: A.fcP, c: COR.fc, k: "fc" }, { v: A.impR, c: COR.grid, k: "grid" }], y); x.step(A.demR, y, { w: 1.8 }); } },
        { title: "Realizada − prevista [kW] · derivado", h: 36, draw(x) { if (!dif) return nd(x, "previsão por intervalo não gravada"); x.strip(dif, x.top, 18, (t) => (t == null ? "var(--field)" : "var(--field-2)"), (t) => (t == null ? ["N/D"] : [nf(t, Math.abs(t) < 10 && t % 1 ? 1 : 0)])); } }],
        tip: tip((i) => [["Demanda realizada", nf(A.demR[i], 2) + " kW"], ["Demanda prevista", nf(A.demP ? A.demP[i] : null, 2) + " kW"], ["Atendida", nf(at[i], 2) + " kW"], ["Déficit", nf(A.ens[i], 2) + " kW"]]),
        cards: (i) => [
          card({ acc: "var(--ink)", t: `Instante ${ivl(i)}`, big: `${nf(A.demR[i], 1)}<small>kW demandados</small>`, grid: [["Prevista na decisão", nf(A.demP ? A.demP[i] : null, 1) + " kW"], ["Atendida", nf(at[i], 1) + " kW"], ["Déficit", nf(A.ens[i], 1) + " kW"], ["Cobertura (derivado)", nf(A.demR[i] ? (100 * at[i]) / A.demR[i] : null, 0) + " %"]] }),
          card({ t: "Missão", big: `${nf(F.resumo.energia_atendida_kWh, 1)}<small>kWh atendidos</small>`, grid: [["Demandados", nf(F.resumo.energia_demanda_kWh, 1) + " kWh"], ["Déficit", nf(F.resumo.energia_nao_atendida_kWh, 2) + " kWh"], ["Cobertura de energia (derivado)", nf(F.resumo.energia_demanda_kWh ? (100 * F.resumo.energia_atendida_kWh) / F.resumo.energia_demanda_kWh : null, 1) + " %"], ["Intervalos com déficit", `${nDef} de ${K}`], ["Pico", `${nf(A.demR[pk], 1)} kW às ${lab(pk)}`], ["Mínimo", `${nf(A.demR[mn], 1)} kW às ${lab(mn)}`]] }),
          card({ t: "Declaração da demanda", kv: [["Classe", esc(F.demanda.criticidade ?? "N/D")], ["Semântica", esc(String(F.demanda.semantica ?? "N/D").replace(/_/g, " "))], ["Emissão da previsão", esc(F.demanda.emissao_utc ?? "N/D")]], note: "«Realizada» é a realização simulada do ensaio, não uma medição.", nd: ["índices probabilísticos de confiabilidade (há uma única realização simulada)"] })] };
    }
    const w = (i) => M.jan[Math.round(A.jan[i])] || {}, mI = teto(maxv(A.cInt || [])), tot = A.cAcc ? [0, ...A.cAcc] : null, mT = teto(maxv(tot || [])), mO = teto(maxv(M.jan.map((q) => q.objetivo))), cp = F.resumo.componentes_R || {};
    const nomeC = { importacao_rede: ["grid", "Importação da rede"], combustivel_h2: ["fc", "Hidrogênio (PEMFC)"], throughput_bess: ["bat", "Throughput da bateria"], eventos: ["fc", "Partidas e paradas"], exportacao_rede: ["grid", "Receita de exportação"], desvio_rede: ["grid", "Desvio no PCC"] };
    return { src: `${fonte.intervalos} · ${fonte.janelas} · resumo selado`, lanes: [
      A.tar ? { title: "Tarifa de decisão do PCC [R$/kWh]", h: 36, draw(x) { x.strip(A.tar, x.top, 18, tarCol, tarLab); } } : null,
      { title: "Custo operacional realizado por intervalo [R$] · por componente", h: 80, w: 2.2, draw(x) { const y = x.sc(0, mI); x.grid(y, tk(mI), fd(mI)); x.stack([{ v: A.cImp, c: COR.grid, k: "grid" }, { v: A.cH2, c: COR.fc, k: "fc" }, { v: A.cEv, c: COR.fc, k: "fc" }, { v: A.cThr, c: COR.bat, k: "bat" }, { v: A.cDes, c: COR.grid, k: "grid" }], y); } },
      { title: "Custo operacional realizado acumulado [R$] · valor gravado", h: 84, w: 2.2, draw(x) { if (!tot) return nd(x); const y = x.sc(0, mT); x.grid(y, tk(mT), fd(mT)); x.front(tot, y, { c: "var(--ink)", r: 2.2 }); } },
      { title: "Objetivo do MILP em cada decisão [R$] · previsão para N intervalos — não é custo realizado", h: 80, w: 2, note: "cheio = com valor futuro · hachurado = sem", draw(x) { const y = x.sc(0, mO * 1.12); x.grid(y, tk(mO), fd(mO)); M.jan.forEach((q) => { if (q.objetivo == null || !q.ap) return; x.add(sv("rect", { x: x.x(q.k) + 2, y: y(q.objetivo), width: q.ap * x.cw - 4, height: Math.max(1, y(0) - y(q.objetivo)), rx: 3, style: `fill:${q.ok ? "var(--s-eco)" : "url(#pth-eco)"}` })); if (q.ap * x.cw > 26) x.text(q.k + q.ap / 2, y(q.objetivo) - 4, nf(q.objetivo, 0), { "text-anchor": "middle", class: "v" }); }); } }].filter(Boolean),
      tip: tip((i) => [["Custo realizado no intervalo", "R$ " + nf(A.cInt ? A.cInt[i] : null, 2)], ["Importação", "R$ " + nf(A.cImp[i], 2)], R.fc.length ? ["Hidrogênio", "R$ " + nf(A.cH2[i], 2)] : null, R.bat.length ? ["Throughput", "R$ " + nf(A.cThr[i], 2)] : null, ["Acumulado", "R$ " + nf(A.cAcc ? A.cAcc[i] : null, 2)], ["Objetivo MILP da janela " + (w(i).j ?? "N/D"), "R$ " + nf(w(i).objetivo, 2)]]),
      cards: (i) => [
        card({ acc: "var(--ink)", t: "Custo operacional realizado", tag: "liquidado", big: `R$ ${nf(F.resumo.custo_realizado_total_R, 2)}`, sub: `até ${lab(i + 1)}: R$ ${nf(A.cAcc ? A.cAcc[i] : null, 2)} · neste intervalo: R$ ${nf(A.cInt ? A.cInt[i] : null, 2)}`,
          el: h("div", { class: "rows", style: "margin-top:8px" }, ...Object.entries(cp).map(([q, x]) => { const [tp, t] = nomeC[q] || ["eco", q.replace(/_/g, " ")]; return h("button", { class: "rowb", onclick: () => abrir(tp), html: `<i style="background:${COR[tp]}"></i><span>${esc(t)}<small>${nf(F.resumo.custo_realizado_total_R ? (100 * x) / F.resumo.custo_realizado_total_R : null, 1)} %</small></span><b>R$ ${nf(x, 2)}</b>` }); })) }),
        card({ t: `Objetivo do MILP · janela ${w(i).j ?? "N/D"}`, tag: "previsão", big: `R$ ${nf(w(i).objetivo, 2)}`, grid: [["Custo operativo previsto", "R$ " + nf(w(i).custo_operativo_previsto, 2)], ["Custo futuro estimado", w(i).custo_futuro_estimado == null ? "N/D" : "R$ " + nf(w(i).custo_futuro_estimado, 2)], ["Planejado no bloco aplicado", "R$ " + nf(w(i).planejado_prefixo, 2)], ["Realizado no bloco", "R$ " + nf(w(i).realizado, 2)]], note: "O objetivo cobre os N intervalos previstos de uma decisão. As janelas se sobrepõem: somar objetivos não tem significado e nunca é apresentado como custo." }),
        card({ t: "Sinal de valor futuro", tag: w(i).ok ? "válido" : "indisponível", tc: w(i).ok ? "ok" : "w", big: `${M.jan.filter((q) => q.ok).length}<small>de ${M.jan.length} decisões com sinal</small>`, note: "Instrumento de decisão do planejador. Não é custo, não é receita e nunca entra no custo realizado." + (w(i).ok ? "" : " Nesta janela: " + esc(w(i).sinal_motivo || "indisponível") + ".") })] };
  }
  function explorador() {
    const k = S.ex, d = dash(k), c = TIPOS[k].c, rec = recDe(k), host = h("div", { class: "host" }), col = h("div", { class: "col" });
    const metaTxt = () => `<span>rodada <b>${esc(F.rodada.uid.slice(0, 8))}</b> · ${esc(F.rodada.cenario || "")}</span><span>instante <b>${ivl(S.cur)}</b>${S.pin ? " fixado" : ""}</span><span>leitura dos registros gravados, sem solver</span>`, meta = h("div", { class: "meta", html: metaTxt() });
    const paintCards = (i) => col.replaceChildren(...d.cards(i).filter(Boolean)); paintCards(S.cur);
    HOOKS.push((i) => { paintCards(i); if (d.special) d.special(host, i); meta.innerHTML = metaTxt(); });
    const lista = R[k] || [], nomeEq = k === "dem" ? "Demanda agregada" : k === "eco" ? "Custo realizado da missão" : k === "grid" ? "Ponto de conexão" : rec.nome;
    const el = h("div", { class: "ov", onclick: (e) => { if (e.target === el) fechar(); } }, h("div", { class: "dlg", role: "dialog", "aria-modal": "true", "aria-label": TIPOS[k].n, style: `--acc:${c}` },
      h("div", { class: "dhead" }, h("div", { class: "grow" }, h("div", { class: "eyebrow" }, TIPOS[k].n), h("h2", { html: `${esc(nomeEq)} <span class="uid">${esc([rec.tag, uidDe(k)].filter(Boolean).join(" · "))}</span>` }), meta),
        lista.length ? h("select", { class: "sel", "aria-label": "Equipamento (UID)", onchange: (e) => { S.uid[k] = e.target.value; salvar(); render(); } }, ...lista.map((r) => h("option", { value: r.uid, selected: r.uid === uidDe(k) }, `${r.nome} · ${r.uid}`))) : null,
        h("button", { class: "tool", title: "Cartões ao lado / embaixo", "aria-pressed": String(S.lay === "bot"), onclick: () => { S.lay = S.lay === "bot" ? "side" : "bot"; salvar(); render(); }, html: ico("M4 5h16v14H4zM4 14h16") }),
        h("button", { class: "tool pt-x", title: "Fechar (Esc)", "aria-label": "Fechar", onclick: fechar, html: ico("M6 6l12 12M18 6L6 18") })),
      h("div", { class: "dtools" }, h("div", { class: "seg", role: "tablist", "aria-label": "Recurso" }, ...M.ord.map((q) => h("button", { role: "tab", "aria-selected": String(q === k), onclick: () => abrir(q), html: `<i style="background:${TIPOS[q].c}"></i>${TIPOS[q].n.split(" / ")[0].replace("Solar fotovoltaica", "Solar")}` }))),
        d.tabs ? h("div", { class: "seg", role: "group", "aria-label": "Vista" }, ...d.tabs.map(([t, n]) => h("button", { "aria-pressed": String(d.tab === t), onclick: () => { S.tab[k] = t; salvar(); render(); } }, n))) : null, h("span", { class: "grow" }), d.special ? null : zoomSeg()),
      h("div", { class: "dbody" + (S.lay === "bot" ? " bot" : "") }, h("div", { class: "panel acc" }, host), col),
      h("div", { class: "dfoot", html: `<span>Fontes: ${esc(d.src)}</span><span>N/D = dado não persistido na rodada; nenhuma curva é gerada para preencher</span><span>← → movem o instante · Enter fixa · Esc fecha · 1–${M.ord.length} trocam de recurso</span>` })));
    setTimeout(() => { if (d.special) d.special(host, S.cur); else trama(host, opts({ lanes: d.lanes.filter(Boolean), padL: d.padL, tip: d.tip, label: TIPOS[k].n, escSolta: false })); const x = el.querySelector(".pt-x"); if (x && !el.contains(root.getRootNode().activeElement)) x.focus({ preventScroll: true }); });
    return el;
  }

  // ---------------------------------------------------------------- moldura
  function render() {
    HOOKS = []; bus.clear();
    const r = F.rodada, ac = F.aceitacao || {}, ver = F.verificacao, sv2 = F.resumo.sinal_valor_futuro || {}, st = h("footer", { class: "status" });
    const pt = (cls, t) => h("span", { html: `<i class="${cls}"></i>${t}` });
    const paintSt = () => st.replaceChildren(h("span", { html: `<b>RODADA ${esc(r.uid.slice(0, 8))}</b> · concluída · somente leitura` }),
      ac.algebrica ? pt(ac.algebrica.estado === "aprovada" ? "" : "b", "algébrico " + esc(ESTADOS[ac.algebrica.estado] || ac.algebrica.estado)) : null, ac.dinamica ? pt(ac.dinamica.estado === "coerente" ? "" : ac.dinamica.estado === "incoerente" ? "b" : "o", "dinâmico " + esc(ESTADOS[ac.dinamica.estado] || ac.dinamica.estado)) : null, ac.fisica ? pt("o", "físico " + esc(ESTADOS[ac.fisica.estado] || ac.fisica.estado)) : null,
      ver ? pt(ver.ok ? "" : "b", ver.ok ? `evidência verificada (${ver.itens.length} de ${ver.itens.length}) sem solver` : "EVIDÊNCIA COM PROBLEMAS") : null, r.sintetico ? pt("w", "dados sintéticos de ensaio") : null,
      h("span", { class: "grow" }), h("span", { html: `instante <b>${ivl(S.cur)}</b>${S.pin ? " fixado" : ""}` }), h("button", { class: "pill", onclick: () => abrir(S.ex || M.ord[0]) }, "Explorar recursos"));
    paintSt(); HOOKS.push(paintSt);
    const tema = h("button", { class: "tool", title: "Tema claro / escuro", "aria-label": "Alternar tema claro / escuro", onclick: () => { const t = root.dataset.theme === "dark" ? "light" : "dark"; root.dataset.theme = t; try { localStorage.setItem("seeds2.partitura.tema", t); } catch (_) { /* sem armazenamento */ } }, html: ico("M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z") });
    const bar = h("header", { class: "bar" }, h("div", {}, h("h1", {}, r.cenario || "Rodada"), h("div", { class: "ctx", html: `rodada ${esc(r.uid.slice(0, 8))} · cenário v${r.versao_cenario} · inventário rev. ${r.revisao_inventario} · ${K} intervalos de ${nf(r.delta_min, 0)} min · N ${r.N} · m ${r.m} · H_L ${r.H_L} &nbsp;—&nbsp; <b>R$ ${nf(F.resumo.custo_realizado_total_R, 2)}</b> realizados · <b>${nf(F.resumo.energia_atendida_kWh, 0)} kWh</b> atendidos · déficit <b>${nf(F.resumo.energia_nao_atendida_kWh, 1)} kWh</b> · valor futuro em <b>${sv2.valido ?? "N/D"} de ${M.jan.length}</b> decisões` })), h("span", { class: "grow" }), h("span", { class: "eyebrow" }, "Partitura · lente Operação"), tema);
    const defs = sv("svg", { width: 0, height: 0, style: "position:absolute", "aria-hidden": "true" }, sv("defs", {}, [["bat", "var(--s-bat)", 2.4], ["wt", "var(--s-wt)", 2], ["fv", "var(--s-fv)", 2], ["grid", "var(--s-grid)", 2], ["eco", "var(--s-eco)", 2]].map(([n, col, w]) => sv("pattern", { id: "pth-" + n, width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, [sv("rect", { width: 5, height: 5, style: "fill:var(--surface)" }), sv("rect", { width: w, height: 5, style: `fill:${col}` })]))));
    root.replaceChildren(defs, bar, lOperacao(), st);
    if (S.ex) root.append(explorador());
  }
  root.onkeydown = (e) => { if (!S.ex) return; if (e.key === "Escape") { fechar(); e.stopPropagation(); } else if (/^[1-9]$/.test(e.key) && !/INPUT|SELECT/.test(e.target.tagName) && M.ord[+e.key - 1]) abrir(M.ord[+e.key - 1]); };
  return { render };
}

export default function (component) {
  const { data, parentElement } = component;
  let root = parentElement.querySelector(".pt");
  if (!root) {
    root = h("div", { class: "pt" }); parentElement.appendChild(root);
    let lw = 0, lh = 0, t = null;
    if (typeof ResizeObserver !== "undefined") new ResizeObserver(() => { const w = root.clientWidth, hgt = root.clientHeight; if (Math.abs(w - lw) < 2 && Math.abs(hgt - lh) < 2) return; lw = w; lh = hgt; clearTimeout(t); t = setTimeout(() => root.__pt && root.__pt.render(), 140); }).observe(root);
  }
  let tema = null; try { tema = localStorage.getItem("seeds2.partitura.tema"); } catch (_) { /* sem armazenamento */ }
  if (tema !== "dark" && tema !== "light") { const m = /rgba?\((\d+)[, ]+(\d+)[, ]+(\d+)/.exec(getComputedStyle(document.body).backgroundColor || ""); tema = m && (0.2126 * m[1] + 0.7152 * m[2] + 0.0722 * m[3]) < 110 ? "dark" : "light"; }
  root.dataset.theme = tema;
  const F = data && data.frame;
  if (!F || F.formato !== "seeds2-trama-frame") { root.__hash = null; root.__pt = null; root.replaceChildren(h("div", { class: "nd", html: "<b>N/D</b> — marco de dados da rodada indisponível" })); return; }
  if (root.__hash === F.hash && root.__pt) return;            // rerun do Streamlit com o mesmo marco: nada é redesenhado
  const primeira = !root.__hash;
  root.__hash = F.hash; root.__pt = Partitura(root, F); root.__pt.render();
  // Ao abrir a rodada, o instrumento vem para o topo da janela (o cabeçalho da página continua logo acima).
  if (primeira) setTimeout(() => { try { root.scrollIntoView({ block: "start" }); } catch (_) { /* navegador antigo */ } }, 60);
}
