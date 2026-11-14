// PARTITURA — instrumento de rodada do SEEDS2 sobre o marco "seeds2-trama-frame" (Pisos 3D-B0/B1/B3).
// Lentes Operação, Decisão, Economia e Evidência + inspetor + explorador de recursos. Só LÊ o marco recebido do Python (dados
// persistidos da rodada): nada é recalculado pelo motor, nada volta ao servidor. O que é DERIVADO aqui (somas por tecnologia,
// acumulados, participação, classificação de comportamento, PWL − modelo) é rotulado como derivado na própria interface.
//
// Três situações distintas, nunca confundidas:
//   • zero gravado          → número 0 (desenhado e somado como zero);
//   • dado AUSENTE (null)    → "N/D": não é somado, não é desenhado como zero e torna N/D toda soma que dependa dele;
//   • NÃO APLICÁVEL (undefined) → o recurso/termo não existe nesta microrrede ou não foi declarado: é omitido, sem N/D.
const TIPOS = {
  fv: { n: "Solar fotovoltaica", c: COR.fv },
  wt: { n: "Eólica", c: COR.wt },
  bat: { n: "Bateria", c: COR.bat },
  fc: { n: "PEMFC / Hidrogênio", c: COR.fc },
  grid: { n: "Rede / PCC", c: COR.grid },
  dem: { n: "Carga / Demanda", c: "var(--ink-2)" },
  liq: { n: "Carga líquida", c: COR.liq },
  eco: { n: "Custos / Economia", c: "var(--ink-2)" },
};
// UI-RESULTADOS-02: «Visão Geral» entra no MESMO nível das quatro lentes, por último; a abertura continua em Operação.
const LENTES = [["operacao", "Operação"], ["decisao", "Decisão"], ["economia", "Economia"], ["evidencia", "Evidência"], ["visao", "Visão Geral"]];
const ico = (d, s = 16) => `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;
// (os utilitários puros de N/D — agg, el, mais, vezes, menos, razao, somaT, acum, termo… — vivem em trama.js, partilhados
// com os componentes de página)
const tk = (mx) => [0, mx / 2, mx], fd = (mx) => (v) => nf(v, mx < 10 ? (mx < 1 ? 2 : 1) : 0);
const ESTADOS = { aprovada: "aprovado", coerente: "coerente", incoerente: "INCOERENTE", nao_aplicavel: "não aplicável", nao_validada: "não validado" };
const GRUPOS_AVISO = [["Abstrações declaradas do modelo", /abstra|instant[âa]nea|amostra clim/i], ["Previsão × realização coincidentes (sem evidência de fuga)", /previsao_coincide|IGUAL à previsão|REALIZADO = potencial/], ["Parâmetros cobertos por declaração", /necessario_3C1|herdada|redundante/], ["Dados sintéticos", /SINT[ÉE]TIC/i]];
function agruparAvisos(avisos) { const usados = new Set(), out = GRUPOS_AVISO.map(([t, re]) => [t, avisos.filter((a, n) => !usados.has(n) && re.test(a) && usados.add(n))]); const resto = avisos.filter((_, n) => !usados.has(n)); return out.concat(resto.length ? [["Outras advertências", resto]] : []).filter((g) => g[1].length); }

function modelo(F) {
  const I = F.intervalos, K = F.rodada.K, hD = (F.rodada.delta_min || 60) / 60, loc = F.fronteiras.local || [];
  const multi = new Set(loc.map((s) => String(s).slice(0, 10))).size > 2, semMin = loc.every((s) => String(s).slice(14, 16) === "00");
  const rot = loc.map((s) => { const t = String(s); const hm = semMin ? t.slice(11, 13) + "h" : t.slice(11, 16); return multi && t.slice(11, 16) === "00:00" ? t.slice(8, 10) + "/" + t.slice(5, 7) : hm; });
  const R = F.recursos, onde = { fv: "renovaveis", wt: "renovaveis", bat: "baterias", fc: "pemfc" };
  const col = (k, g) => R[k].map((r) => (F[onde[k]][r.uid] || {})[g] ?? null), con = F.pcc.modo === "conectado", pcc = (c) => (con ? I[c] ?? null : undefined);
  const din = R.fc.map((r) => (F.pemfc[r.uid] || {}).dinamica);
  const A = {
    demR: I.demanda_realizada_kW ?? null, demP: I.demanda_prevista_kW ?? null, ens: I.demanda_nao_atendida_kW ?? null, at: I.demanda_atendida_kW ?? null,
    wtP: agg(col("wt", "P_R_kW"), K), wtA: agg(col("wt", "A_utilizavel_kW"), K), wtV: agg(col("wt", "vertimento_kW"), K),
    fvP: agg(col("fv", "P_R_kW"), K), fvA: agg(col("fv", "A_utilizavel_kW"), K), fvV: agg(col("fv", "vertimento_kW"), K),
    pd: agg(col("bat", "P_d_kW"), K), pc: agg(col("bat", "P_c_kW"), K), fr: agg(col("bat", "energia_kWh"), K + 1),
    fcP: agg(col("fc", "p_kW"), K), fcM: agg(col("fc", "m_h2_kg"), K), cH2: termoAgg(col("fc", "custo_h2_R"), declarado(F, "combustivel_h2"), K), cEv: termoAgg(col("fc", "custo_eventos_R"), declarado(F, "eventos"), K),
    fcOn: R.fc.length ? Array.from({ length: K }, (_, i) => R.fc.some((r) => ((F.pemfc[r.uid] || {}).u || [])[i])) : undefined,
    dinP: !R.fc.length ? undefined : din.some((d) => !d) ? null : Array.from({ length: K }, (_, i) => { let s = 0; for (const d of din) { const v = (d.intervalos[i] || {}).p_entregue_media_kW; if (v == null) return null; s += v; } return s; }),
    impR: pcc("pcc_importacao_realizada_kW"), impP: pcc("pcc_importacao_programada_kW"), expR: pcc("pcc_exportacao_realizada_kW"), expP: pcc("pcc_exportacao_programada_kW"),
    tar: pcc("tarifa_importacao_decisao_R_kWh"), cImp: pcc("custo_importacao_R"), rec: pcc("receita_exportacao_R"), cDes: con ? I.custo_desvio_rede_R ?? null : undefined,
    cThr: R.bat.length ? termo(I.custo_throughput_R ?? null, declarado(F, "throughput_bess")) : undefined, cInt: I.custo_realizado_intervalo_R ?? null, cAcc: I.custo_realizado_acumulado_R ?? null,
    jan: I.janela ?? null, ip: I.indice_no_plano ?? null, res: I.residuo_balanco_kW ?? null,
  };
  A.cap = R.bat.length ? somaT(R.bat.map((r) => ((F.baterias[r.uid] || {}).resumo || {}).capacidade_kWh ?? null)) : undefined;
  // UI-RESULTADOS-02: remuneração de exportação da decisão (evidência de «não aplicável» = sentidos declarados) e renovável
  // APROVEITADA total (soma derivada por intervalo; undefined = microrrede sem renováveis)
  A.tarE = tarifaExportacao(F);
  A.renP = agg([...col("fv", "P_R_kW"), ...col("wt", "P_R_kW")], K);
  const ord = ["fv", "wt", "bat", "fc"].filter((k) => R[k].length).concat(con ? ["grid"] : [], ["dem", "liq", "eco"]);
  const jan = (F.janelas || []).map((w) => ({ ...w, j: Math.round(w.j), k: Math.round(w.k), Nk: Math.round(w.Nk), mk: Math.round(w.mk), ap: w.ap == null ? null : Math.round(w.ap), ok: w.sinal_qualidade === "valido" }));
  return { K, hD, rot, A, ord, jan, conectado: con };
}
// Balanço do barramento num intervalo: o que injeta, o que consome e o que FALTA (ausente). Total = null se faltar parcela.
function balancoDe(A, g) {
  const inj = [["wt", el(A.wtP, g)], ["fv", el(A.fvP, g)], ["bat", el(A.pd, g)], ["fc", el(A.fcP, g)], ["grid", el(A.impR, g)]].filter((x) => x[1] !== undefined);
  const con = [["dem", el(A.at, g)], ["bat", el(A.pc, g)], ["grid", el(A.expR, g)]].filter((x) => x[1] !== undefined);
  const faltam = [...inj, ...con].filter((x) => x[1] === null).map((x) => x[0]);
  return { inj, con, faltam, total: inj.some((x) => x[1] === null) ? null : inj.reduce((s, x) => s + x[1], 0) };
}
// Plano de UMA decisão agregado por tecnologia (mesma regra de N/D): séries "<uid>|<grandeza>" de v2/planos.csv.
function planoPorTipo(F, P) {
  if (!P) return null;
  const R = F.recursos, n = (P.intervalo || []).length, s = (k, g) => agg(R[k].map((r) => P.series[`${r.uid}|${g}`] ?? null), n), con = F.pcc.modo === "conectado";
  return { n, wt: s("wt", "P_R"), fv: s("fv", "P_R"), pd: s("bat", "P_d"), pc: s("bat", "P_c"), fc: s("fc", "p"), imp: con ? P.series.pcc_importacao_programada_kW ?? null : undefined,
    exp: con ? P.series.pcc_exportacao_programada_kW ?? null : undefined, dem: P.demanda_prevista_kW ?? null, aplicado: (P.aplicado || []).map((a) => !!a) };
}

// ---------------------------------------------------------------- UI-RESULTADOS-02 · grandezas derivadas (puras)
// Tudo aqui é DERIVADO das séries e do resumo GRAVADOS da rodada (mesma regra de N/D: null contamina, undefined omite) e é
// executado também em Node pelos testes. A interface e o relatório PDF usam ESTAS funções: não há uma segunda implementação.
const EXPORTA = ["importacao_e_exportacao", "somente_exportacao"];
// Remuneração de exportação usada na decisão. Série vazia só é «não aplicável» com EVIDÊNCIA: sentidos do PCC declarados SEM
// exportação. Exportação permitida, ou sentidos não declarados, com a série vazia = dado ausente (N/D).
function tarifaExportacao(F) {
  if ((F.pcc || {}).modo !== "conectado") return undefined;
  const a = F.intervalos.tarifa_exportacao_decisao_R_kWh ?? null, s = F.pcc.sentidos;
  if (!vazia(a)) return a;
  return s == null ? null : EXPORTA.includes(s) ? null : undefined;
}
// Índices em que começa um período tarifário (valor diferente do anterior; ausente interrompe o período).
function mudancasTarifa(a) {
  const out = []; if (!a) return out; let prev = null;
  a.forEach((v, i) => { if (v == null) { prev = null; return; } if (prev === null || v !== prev) out.push(i); prev = v; });
  return out;
}
// Carga líquida: P_liq(g) = P_demanda(g) − Σ P_renovável APROVEITADA(g) (depois do vertimento; nunca o potencial). Pode ser
// negativa (excedente renovável) e é preservada assim. Compensação pelos recursos controláveis, na convenção de sinais do
// registro: descarga + PEMFC + importação + demanda não atendida (suprem) − carga − exportação (absorvem). O fechamento
// (compensação − carga líquida) é, pela própria equação de balanço, o resíduo gravado (residuo_balanco_kW).
function cargaLiquida(M) {
  const { A, K, hD } = M, seq = (f) => Array.from({ length: K }, (_, i) => f(i)), ren = A.renP;
  const liq = A.demR == null ? null : seq((i) => (ren === undefined ? A.demR[i] : menos(A.demR[i], el(ren, i))));
  const comp = seq((i) => menos(mais(el(A.pd, i), el(A.fcP, i), el(A.impR, i), el(A.ens, i)), mais(el(A.pc, i), el(A.expR, i))));
  const fech = liq == null ? null : seq((i) => menos(comp[i], liq[i]));
  const E = (a) => (a === undefined ? undefined : vezes(somaT(a), hD));
  const parte = (f) => (liq == null || liq.some((v) => v == null) ? null : liq.reduce((s, v) => s + f(v), 0) * hD);
  const ok = liq != null && liq.every((v) => v != null), ipk = ok ? liq.indexOf(Math.max(...liq)) : null, imn = ok ? liq.indexOf(Math.min(...liq)) : null;
  const termos = [["bat", "Descarga da bateria", E(A.pd), 1], ["fc", "PEMFC", E(A.fcP), 1], ["grid", "Importação da rede", E(A.impR), 1],
    ["ens", "Demanda não atendida", E(A.ens), 1], ["bat", "Carga da bateria", E(A.pc), -1], ["grid", "Exportação", E(A.expR), -1]].filter((t) => t[2] !== undefined);
  const soma = termos.some((t) => t[2] == null) ? null : termos.reduce((s, t) => s + t[3] * t[2], 0);
  const dRes = fech == null || A.res == null || fech.some((v, i) => v == null || A.res[i] == null) ? null : Math.max(0, ...fech.map((v, i) => Math.abs(v - A.res[i])));
  return { liq, comp, fech, ren, eDem: E(A.demR), eRen: ren === undefined ? undefined : E(ren), eLiq: E(liq), ePos: parte((v) => Math.max(v, 0)), eNeg: parte((v) => Math.min(v, 0)),
    nNeg: conta(liq, (v) => v < -1e-9), pico: ipk == null ? null : [ipk, liq[ipk]], min: imn == null ? null : [imn, liq[imn]], termos, somaTermos: soma,
    fechMax: fech == null || fech.some((v) => v == null) ? null : Math.max(0, ...fech.map(Math.abs)), difResiduo: dRes };
}
// Síntese da missão (lente Visão Geral e seção 02 do relatório). Cada valor leva a ORIGEM: «selado» = resumo gravado da missão
// (indicadores selados), «derivado» = calculado aqui a partir de valores gravados. Ausente = null (N/D); recurso inexistente =
// undefined (omitido). A descarga da bateria é energia armazenada antes (vinda das outras fontes): é sempre apresentada junto
// da energia carregada e nunca como geração primária adicional.
function visaoGeral(F, M) {
  const { A, K, hD } = M, R = F.recursos, s = F.resumo || {}, I = s.indicadores_selados || {}, con = M.conectado, lim = (F.pcc || {}).limite_importacao_kW ?? null;
  const V = (v, o) => ({ v: v === undefined ? undefined : v ?? null, o: v === undefined ? null : o });
  const somaR = (k, onde, campo) => { if (!R[k].length) return undefined; let t = 0; for (const r of R[k]) { const x = (((F[onde] || {})[r.uid] || {}).resumo || {})[campo]; if (x == null) return null; t += x; } return t; };
  const selOu = (chave, alt) => (I[chave] != null ? V(I[chave], "selado") : V(alt, R.bat.length > 1 ? "derivado" : "selado"));
  const temRen = R.fv.length + R.wt.length > 0, porR = (k, onde, campo) => V(somaR(k, onde, campo), R[k].length > 1 ? "derivado" : "selado");
  const fv = { aprov: porR("fv", "renovaveis", "energia_aproveitada_kWh"), vert: porR("fv", "renovaveis", "energia_vertida_kWh") };
  const wt = { aprov: porR("wt", "renovaveis", "energia_aproveitada_kWh"), vert: porR("wt", "renovaveis", "energia_vertida_kWh") };
  const v = {
    dem: V(s.energia_demanda_kWh, "selado"), at: V(s.energia_atendida_kWh, "selado"), ens: V(s.energia_nao_atendida_kWh, "selado"),
    custo: V(s.custo_realizado_total_R, "selado"), imp: con ? V(s.energia_importada_kWh, "selado") : V(undefined), exp: con ? V(s.energia_exportada_kWh, "selado") : V(undefined),
    ren: temRen ? (I.E_renovavel_usada_kWh != null ? V(I.E_renovavel_usada_kWh, "selado") : V(mais(fv.aprov.v, wt.aprov.v), "derivado")) : V(undefined),
    vert: temRen ? (I.E_curtailment_kWh != null ? V(I.E_curtailment_kWh, "selado") : V(mais(fv.vert.v, wt.vert.v), "derivado")) : V(undefined),
    batC: R.bat.length ? selOu("E_bess_carga_kWh", somaR("bat", "baterias", "energia_carregada_kWh")) : V(undefined),
    batD: R.bat.length ? selOu("E_bess_descarga_kWh", somaR("bat", "baterias", "energia_descarregada_kWh")) : V(undefined),
    fc: R.fc.length ? (I.E_geracao_kWh != null ? V(I.E_geracao_kWh, "selado") : V(somaR("fc", "pemfc", "energia_kWh"), "derivado")) : V(undefined),
    e0: porR("bat", "baterias", "energia_inicial_kWh"), e1: porR("bat", "baterias", "energia_final_kWh") };
  v.cobertura = V(razao(v.at.v, v.dem.v), "derivado");
  v.custoKwh = V(razao(v.custo.v, v.at.v, 1), "derivado");
  // SOC [fração]: um banco = valor gravado; vários bancos = energia total ÷ capacidade total (derivado)
  const soc = (campo, e) => (R.bat.length === 1 ? V(((F.baterias[R.bat[0].uid] || {}).resumo || {})[campo], "selado") : R.bat.length ? V(razao(e, A.cap, 1), "derivado") : V(undefined));
  v.soc0 = soc("soc_inicial", v.e0.v); v.soc1 = soc("soc_final", v.e1.v);
  // participação nas INJEÇÕES do barramento (denominador explícito); renováveis por tecnologia a partir do resumo por recurso
  const fatias = [["fv", "Solar · aproveitada", temRen && R.fv.length ? fv.aprov.v : undefined], ["wt", "Eólica · aproveitada", temRen && R.wt.length ? wt.aprov.v : undefined],
    ["bat", "Bateria · descarga", v.batD.v], ["fc", "PEMFC", v.fc.v], ["grid", "Rede · importação", v.imp.v]].filter((f) => f[2] !== undefined);
  const inj = fatias.some((f) => f[2] == null) ? null : fatias.reduce((t, f) => t + f[2], 0);
  const saidas = [["dem", "Demanda atendida", v.at.v], ["bat", "Bateria · carga", v.batC.v], ["grid", "Rede · exportação", v.exp.v]].filter((f) => f[2] !== undefined);
  const sai = saidas.some((f) => f[2] == null) ? null : saidas.reduce((t, f) => t + f[2], 0);
  v.inj = V(inj, "derivado"); v.sai = V(sai, "derivado"); v.fech = V(menos(inj, sai), "derivado");
  const fr = fatias.filter((f) => f[0] === "fv" || f[0] === "wt"), eRen = fr.some((f) => f[2] == null) ? null : fr.reduce((t, f) => t + f[2], 0);
  v.partRen = temRen ? V(razao(eRen, inj), "derivado") : V(undefined);
  // PCC: pico de importação, utilização do limite contratado, intervalos no limite (derivados das médias de intervalo gravadas)
  const okI = con && A.impR != null && A.impR.every((q) => q != null), ip = okI ? A.impR.indexOf(Math.max(...A.impR)) : null;
  v.pmax = con ? V(okI ? A.impR[ip] : null, "derivado") : V(undefined); v.ipmax = ip;
  v.lim = con ? V(lim, "declarado") : V(undefined);
  v.uPico = con && lim != null ? V(razao(v.pmax.v, lim), "derivado") : V(undefined);
  v.uMedia = con && lim != null ? V(razao(vezes(v.imp.v, 1 / (K * hD)), lim), "derivado") : V(undefined);
  v.noLim = con && lim != null ? V(conta(A.impR, (q) => q >= lim - 1e-6), "derivado") : V(undefined);
  v.auditoria = V(F.auditoria ? F.auditoria.aceito : null, "selado"); v.missao = V(s.missao_completa, "selado"); v.verificada = V(F.verificacao ? F.verificacao.ok : null, "servidor");
  const fontes = [R.fv.length ? ["fv", "Solar", [["aproveitada", fv.aprov], ["vertida", fv.vert, "ht"]]] : null, R.wt.length ? ["wt", "Eólica", [["aproveitada", wt.aprov], ["vertida", wt.vert, "ht"]]] : null,
    con ? ["grid", "Rede", [["importada", v.imp], ["exportada", v.exp, "ht"]]] : null, R.bat.length ? ["bat", "Bateria", [["descarregada", v.batD], ["carregada", v.batC, "ht"]]] : null,
    R.fc.length ? ["fc", "PEMFC", [["produzida", v.fc]]] : null].filter(Boolean);
  return { v, fv, wt, fatias, saidas, fontes };
}

function Partitura(root, F) {
  const M = modelo(F), { K, hD, A } = M, R = F.recursos, bus = novoBarramento(), chave = "seeds2.partitura." + F.rodada.uid, porJ = new Map(M.jan.map((w) => [w.j, w]));
  const S = { lens: "operacao", cur: 0, pin: false, zoom: 0, ex: null, tab: {}, uid: {}, lay: "side", band: null, jan: null, depois: true, tabela: null };
  try { Object.assign(S, JSON.parse(sessionStorage.getItem(chave) || "{}")); } catch (_) { /* sem armazenamento */ }
  if (S.lens === "visao") S.lens = "operacao";             // UI-RESULTADOS-02: abrir uma rodada NUNCA começa na Visão Geral
  S.cur = Math.min(K - 1, Math.max(0, S.cur | 0)); if (S.ex && !M.ord.includes(S.ex)) S.ex = null; if (!LENTES.some((l) => l[0] === S.lens)) S.lens = "operacao";
  const salvar = () => { try { sessionStorage.setItem(chave, JSON.stringify(S)); } catch (_) { /* idem */ } };
  let HOOKS = [];
  const lab = (b) => M.rot[b] ?? String(b), ivl = (i) => `${lab(i)}–${lab(i + 1)}`, janDe = (g) => porJ.get(Math.round(el(A.jan, g)));
  const setCur = (i) => { S.cur = i; HOOKS.forEach((f) => f(i)); salvar(); };
  const onPin = (i) => { S.pin = i != null; if (i != null) S.cur = i; HOOKS.forEach((f) => f(S.cur)); salvar(); };
  const abrir = (k) => { if (!M.ord.includes(k)) return; S.ex = k; salvar(); render(); };
  const fechar = () => { S.ex = null; salvar(); render(); };
  const irLente = (l, j) => { S.lens = l; if (j != null) S.jan = j; salvar(); render(); };
  const uidDe = (k) => (R[k] && R[k].length ? (R[k].some((r) => r.uid === S.uid[k]) ? S.uid[k] : R[k][0].uid) : k === "grid" ? "PCC" : "");
  const recDe = (k) => (R[k] || []).find((r) => r.uid === uidDe(k)) || { nome: TIPOS[k].n.split(" / ")[0], tag: null, uid: "" };
  const zooms = [0, ...[2, 4].map((d) => Math.round(K / d)).filter((z) => z >= 4 && z < K)];
  const vista = () => { const z = S.zoom; if (!z || z >= K) return null; const a = Math.min(K - z, Math.max(0, Math.round(S.cur - z / 2 + .5))); return [a, a + z]; };
  const v0 = () => (vista() ? vista()[0] : 0) + .15;
  const zoomSeg = () => (zooms.length < 2 ? null : h("div", { class: "seg", role: "group", "aria-label": "Janela de tempo" }, ...zooms.map((z) => h("button", { "aria-pressed": String((S.zoom || 0) === z), onclick: () => { S.zoom = z; salvar(); render(); } }, z ? nf(z * hD, z * hD % 1 ? 1 : 0) + " h" : "tudo"))));
  const tip = (rows) => (i) => `<b>${ivl(i)} · intervalo ${i}</b>` + rows(i).filter(Boolean).map(([a, b]) => `<div><span>${a}</span><span>${b}</span></div>`).join("");
  const kvh = (rows) => rows.filter(Boolean).map(([a, b]) => `<span>${a}</span><b>${b}</b>`).join("");
  const card = (o) => Object.assign(h("div", { class: "card" + (o.acc ? " acc" : ""), style: o.acc ? `--acc:${o.acc}` : null },
    o.t ? h("h3", { html: o.t + (o.tag ? `<span class="tag ${o.tc || ""}">${o.tag}</span>` : "") }) : null, o.big != null ? h("div", { class: "big", html: o.big }) : null, o.sub ? h("div", { class: "sub", html: o.sub }) : null,
    o.grid ? h("div", { class: "mgrid", html: o.grid.filter(Boolean).map(([a, b]) => `<div><span>${a}</span><b>${b}</b></div>`).join("") }) : null,
    o.kv ? h("div", { class: "kv", html: kvh(o.kv) }) : null, o.nd ? o.nd.map((t) => h("div", { class: "nd", html: "<b>N/D</b> — " + t })) : null, o.note ? h("p", { class: "note", html: o.note }) : null, o.el || null), { __o: o });   // __o: o MESMO conteúdo vai para o relatório PDF
  const nd = (c, t) => c.nd(t);
  // UI-FINISH-01: metadados de exportação de cada gráfico (título = o do gráfico; identificação = a da rodada gravada;
  // legenda = a mostrada junto do gráfico; fontes = os dados persistidos desenhados)
  const expMeta = (svg) => {
    const r = F.rodada, dlg = svg.closest(".dlg"), rec = dlg ? (dlg.querySelector(".dhead h2") || {}).textContent : null;
    const caixa = svg.closest(".dlg,.panel,.stage") || svg.parentElement;
    const legenda = [...caixa.querySelectorAll(".chead .leg, .dhead .leg")].map((l) => { const i = l.querySelector("i"); return { t: l.textContent.trim(), estilo: i ? i.getAttribute("style") : "", ht: !!(i && i.classList.contains("ht")) }; }).filter((x) => x.t);
    const titulo = (rec ? rec.replace(/\s+/g, " ").trim() + " — " : "") + (svg.getAttribute("aria-label") || "Gráfico") + (dlg ? "" : ` · lente ${(LENTES.find((l) => l[0] === S.lens) || [0, ""])[1]}`);
    return { titulo, rodada: r.uid, cenario: r.cenario, legenda, fontes: [...new Set(Object.values(F.fontes || {}).filter((x) => typeof x === "string" && (F.arquivos || []).some((a) => a[0] === x)))],
      sub: `${r.cenario || "Rodada"} · cenário v${r.versao_cenario} · rodada ${String(r.uid).slice(0, 8)} · ${K} intervalos de ${nf(r.delta_min, 0)} min · N ${r.N} · m ${r.m} · H_L ${r.H_L} · ${r.fuso || "fuso não declarado"}`,
      aviso: r.sintetico ? "dados sintéticos de ensaio" : "" };
  };
  const opts = (extra) => ({ K, lab, bus, pat: "pth", cur: S.cur, pin: S.pin, fill: true, view: vista(), onCur: setCur, onPin, onRes: abrir, exp: expMeta, ...extra });
  const painel = (t, ...k) => h("div", { class: "panel" }, h("div", { class: "chead" }, h("span", { class: "ttl" }, t)), ...k);
  const painel2 = (t, ...k) => { const e = painel(t, ...k); e.classList.add("larga"); return e; };
  const rs = (v, d = 2) => (v == null ? "N/D" : "R$ " + nf(v, d));

  // ---------------------------------------------------------------- UI-RESULTADOS-02 · peças comuns às lentes e aos painéis
  // (1) Tarifa de decisão como CURVA ESCALONADA: um degrau por intervalo [t_k, t_k+1) com o valor GRAVADO, sem interpolação;
  // o início de cada período tarifário é marcado e rotulado. Importação (cor da rede, cheia) × remuneração de exportação
  // (verde, tracejada; omitida só quando os sentidos declarados do PCC excluem a exportação).
  function laneTarifa(o = {}) {
    return { title: o.title || "Tarifa de decisão [R$/kWh] · degrau por intervalo [t_k, t_k+1)", res: o.res, h: o.h || 46, w: o.w ?? 1, note: o.note, draw(c) {
      const aI = A.tar, aE = A.tarE, mx = teto(maxv(aI || [], aE || [])), y = c.sc(0, mx * 1.2);
      c.grid(y, [0, mx / 2, mx], (v) => nf(v, 2));
      if (aI === null) c.nd("tarifa de importação da decisão não persistida"); else if (aI !== undefined) c.step(aI, y, { c: COR.grid, w: 2, k: "tar" });
      if (aE === null) c.nd("remuneração de exportação da decisão não persistida"); else if (aE !== undefined) c.step(aE, y, { c: COR.tarx, w: 1.8, dash: "6 3", k: "tarx" });
      [[aI, COR.grid, -5], [aE, COR.tarx, 12]].forEach(([a, cor, dy]) => { if (!a) return; const m = mudancasTarifa(a);
        m.forEach((i, n) => { const fim = n + 1 < m.length ? m[n + 1] : a.length;
          if (i > 0 && a[i - 1] != null) c.add(sv("line", { x1: c.x(i), x2: c.x(i), y1: c.top, y2: c.bot, style: `stroke:${cor};stroke-opacity:.5`, "stroke-dasharray": "2 3", "data-k": "tarmuda" }));
          if ((fim - i) * c.cw >= 30) c.text(i, y(a[i]) + dy, nf(a[i], 2), { dx: 3, class: "v", style: `fill:${cor};font-weight:600`, "data-k": "tarval" }); }); });
    } };
  }
  const tipTar = (i) => [M.conectado ? ["Tarifa de importação (decisão)", nf(el(A.tar, i), 2) + " R$/kWh"] : null, A.tarE !== undefined ? ["Remuneração de exportação (decisão)", nf(el(A.tarE, i), 2) + " R$/kWh"] : null];
  const legTar = () => (M.conectado ? [{ t: "tarifa de importação [R$/kWh]", c: COR.grid, tipo: "linha" }, A.tarE !== undefined ? { t: "remuneração de exportação [R$/kWh]", c: COR.tarx, tipo: "tracejado" } : null] : []);
  // (2) Demanda TOTAL como referência nos gráficos de potência das fontes: linha fina e neutra no mesmo eixo kW, nunca somada à
  // geração; havendo déficit gravado, a demanda ATENDIDA aparece pontilhada.
  const temDef = () => A.ens != null && A.ens.some((e) => e != null && e > 1e-9);
  const demRef = (x, y) => { x.step(A.demR, y, { c: COR.ref, w: 1.3, k: "demref" }); if (temDef()) x.step(A.at, y, { c: COR.ref, w: 1.2, dash: "2 2", k: "demref" }); };
  const legDem = () => [{ t: "demanda total", c: COR.ref, tipo: "linha" }, temDef() ? { t: "demanda atendida (há déficit)", c: COR.ref, tipo: "pontilhado" } : null];
  const tipDem = (i) => [["Demanda total", nf(el(A.demR, i), 2) + " kW"], temDef() ? ["Demanda atendida", nf(el(A.at, i), 2) + " kW"] : null];
  // legenda: área · linha · tracejado · pontilhado · hachura · ponto (a mesma lista vai para a exportação e para o relatório)
  const LEG_CLS = { linha: "ln", tracejado: "ln tr", pontilhado: "ln pt2", hachura: "ht", ponto: "pto", area: "" };
  const legEl = (it) => h("span", { class: "leg", "data-tipo": it.tipo || "area", html: `<i class="${LEG_CLS[it.tipo || "area"]}" style="background-color:${it.c}"></i>${esc(it.t)}` });
  const legRow = (itens) => h("div", { class: "chead" }, ...itens.filter(Boolean).map(legEl));
  // (3) Cascata horizontal de ENERGIA da carga líquida: cada termo parte do acumulado anterior (suprem: +, absorvem: −) e a
  // última barra é a carga líquida da missão. Energias = médias gravadas × Δ (derivadas). Painel e relatório usam a mesma.
  function cascata(CL, W = 292) {
    const itens = CL.termos.map(([k, t, v, s]) => ({ k, t, v: v == null ? null : s * v, ht: s < 0 })), total = CL.eLiq;
    const rowH = 21, lw = Math.min(150, Math.round(W * .38)), vw = 64, bw = W - lw - vw - 6, H = (itens.length + 1) * rowH + 8;
    const svg = sv("svg", { class: "trama", width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Balanço da carga líquida (energia)" });
    const pts = [0]; let a = 0; for (const it of itens) { if (it.v == null) { a = null; break; } a += it.v; pts.push(a); }
    if (total != null) pts.push(total);
    const lo = Math.min(0, ...pts), hi = Math.max(0, ...pts), X = (v) => lw + ((v - lo) / (hi - lo || 1)) * bw, val = (v) => (v > 0 ? "+" : "") + nf(v, 1);
    svg.append(sv("line", { x1: X(0), x2: X(0), y1: 2, y2: H - 4, class: "ax" }));
    a = 0;
    itens.forEach((it, n) => { const yy = 4 + n * rowH; svg.append(sv("text", { x: 0, y: yy + 14 }, it.t));
      if (it.v == null || a == null) { a = null; svg.append(sv("text", { x: W, y: yy + 14, "text-anchor": "end", class: "v nd" }, "N/D")); return; }
      const x0 = X(Math.min(a, a + it.v)), x1 = X(Math.max(a, a + it.v));
      if (Math.abs(it.v) > 1e-9) svg.append(sv("rect", { x: x0, y: yy + 4, width: Math.max(1, x1 - x0), height: rowH - 8, rx: 2, "data-k": it.k, style: `fill:${it.ht ? `url(#pth-${it.k})` : COR[it.k]}` }));
      svg.append(sv("text", { x: W, y: yy + 14, "text-anchor": "end", class: "v" }, val(it.v))); a += it.v; });
    const yy = 4 + itens.length * rowH;
    svg.append(sv("text", { x: 0, y: yy + 14, style: "font-weight:700" }, "= carga líquida"));
    if (total == null) svg.append(sv("text", { x: W, y: yy + 14, "text-anchor": "end", class: "v nd" }, "N/D"));
    else svg.append(sv("rect", { x: Math.min(X(0), X(total)), y: yy + 4, width: Math.max(1, Math.abs(X(total) - X(0))), height: rowH - 8, rx: 2, "data-k": "liq", style: `fill:${COR.liq}` }),
      sv("text", { x: W, y: yy + 14, "text-anchor": "end", class: "v", style: "font-weight:700" }, val(total) + " kWh"));
    return svg;
  }

  // ---------------------------------------------------------------- lente Operação
  const NOMES = { wt: "eólica", fv: "solar", bat: "bateria", fc: "PEMFC", grid: "rede", dem: "demanda atendida" };
  function balanco(g) {
    const B = balancoDe(A, g), tot = B.total, base = Math.max(tot || 0, 1e-9);
    const seg = (a, ht) => a.filter((x) => x[1] > 1e-6).map(([k, x]) => `<i class="${ht && k !== "dem" ? "ht" : ""}" style="width:${(100 * x) / base}%;background-color:${COR[k]}" title="${nf(x, 2)} kW"></i>`).join("");
    if (B.faltam.length) return h("div", {}, h("div", { class: "nd", html: `<b>N/D</b> — balanço incompleto: ${[...new Set(B.faltam)].map((k) => NOMES[k]).join(", ")} sem dado neste intervalo. Nada é assumido como zero.` }));
    return h("div", {}, h("div", { class: "bal", html: `<span>injeta</span><div class="b">${seg(B.inj)}</div><span>consome</span><div class="b">${seg(B.con, true)}</div>` }),
      h("p", { class: "note", html: `Σ injeção (derivado) = <b>${nf(tot, 2)} kW</b> · resíduo do balanço gravado ${ne(el(A.res, g), 1)} kW` }));
  }
  function inspetor(g, T) {
    const w = janDe(g), fo = (k) => ({ onpointerenter: () => T() && T().focus(k), onpointerleave: () => T() && T().focus(null), onfocus: () => T() && T().focus(k), onblur: () => T() && T().focus(null), onclick: () => abrir(k) });
    const row = (k, t, val, ref) => h("button", { class: "rowb", ...fo(k), title: "Abrir o painel de " + TIPOS[k].n, html: `<i style="background:${COR[k]}"></i><span>${t}<small>${ref || ""}</small></span><b>${val}<small>kW</small></b>` });
    const n = (k) => (R[k].length > 1 ? ` (${R[k].length})` : ""), pc = el(A.pc, g), pd = el(A.pd, g), on = el(A.fcOn, g);
    return [
      card({ acc: "var(--ink)", t: `Intervalo ${g}`, tag: S.pin ? "fixado" : "", big: ivl(g), sub: `médias do intervalo · ${esc(F.rodada.fuso || "fuso não declarado")}${w ? " · decidido na janela " + w.j : ""}`, el: balanco(g) }),
      card({ t: "Recursos neste intervalo", tag: "clique para abrir", el: h("div", { class: "rows" }, row("dem", "Demanda", nf(el(A.demR, g), 1), "prevista " + nf(el(A.demP, g), 1)),
        A.wtP !== undefined ? row("wt", "Eólica" + n("wt"), nf(el(A.wtP, g), 1), "de " + nf(el(A.wtA, g), 1)) : null, A.fvP !== undefined ? row("fv", "Solar" + n("fv"), nf(el(A.fvP, g), 1), "de " + nf(el(A.fvA, g), 1)) : null,
        A.pd !== undefined ? row("bat", "Bateria" + n("bat"), pc == null || pd == null ? "N/D" : pc > 0 ? "−" + nf(pc, 1) : nf(pd, 1), pc == null || pd == null ? "sem dado" : pc > 0 ? "carga" : pd > 0 ? "descarga" : "repouso") : null,
        A.fcP !== undefined ? row("fc", "PEMFC" + n("fc"), nf(el(A.fcP, g), 1), on ? (A.dinP ? "dinâmico " + nf(el(A.dinP, g), 1) : "ligada") : "desligada") : null,
        M.conectado ? row("grid", "Rede", nf(el(A.impR, g), 1), "programada " + nf(el(A.impP, g), 1)) : null) }),
      card({ t: "Estados e custos", el: h("div", { class: "kv", html: kvh([A.fr !== undefined ? ["Energia armazenada", `${nf(el(A.fr, g), 1)} → ${nf(el(A.fr, g + 1), 1)} kWh`] : null, A.wtV !== undefined || A.fvV !== undefined ? ["Vertimento renovável", nf(mais(el(A.wtV, g), el(A.fvV, g)), 1) + " kW"] : null,
        A.fcM !== undefined ? ["H₂ no intervalo", nf(el(A.fcM, g), 3) + " kg"] : null, M.conectado ? ["Tarifa de decisão", nf(el(A.tar, g), 2) + " R$/kWh"] : null, ["Custo realizado", rs(el(A.cInt, g))], ["Acumulado", rs(el(A.cAcc, g))]]) }) }),
      w ? card({ t: `Decisão · janela ${w.j}`, tag: w.ok ? "com valor futuro" : "sem valor futuro", tc: w.ok ? "ok" : "w", sub: `decidida às ${lab(w.k)} · posição ${el(A.ip, g) == null ? "N/D" : Math.round(el(A.ip, g)) + 1} de ${w.Nk} no plano`,
        note: w.ok ? null : esc(w.sinal_motivo || "sinal de valor futuro indisponível nesta decisão"), el: h("button", { class: "pill", style: "margin-top:10px", onclick: () => irLente("decisao", w.j) }, "Ver esta decisão") }) : null];
  }
  // Raias da lente Operação (partilhadas com o relatório PDF: o mesmo desenho, missão completa).
  function lanesOperacao() {
    const inj = [{ v: A.wtP, c: COR.wt, k: "wt" }, { v: A.fvP, c: COR.fv, k: "fv" }, { v: A.pd, c: COR.bat, k: "bat" }, { v: A.fcP, c: COR.fc, k: "fc" }, { v: A.impR, c: COR.grid, k: "grid" }];
    const tot = Array.from({ length: K }, (_, i) => mais(...inj.map((s) => el(s.v, i)))), hi = teto(maxv(tot, A.demR)), lo = teto(maxv(A.pc, A.expR)), temNeg = maxv(A.pc, A.expR) > 1e-6;
    const lanes = [
      { title: "Decisões do MPC · bloco aplicado", h: 36, note: "cheio = com valor futuro · tracejado = sem", draw(c) { M.jan.forEach((w) => { if (!w.ap) return; const e = c.add(sv("rect", { x: c.x(w.k) + 1, y: c.top, width: w.ap * c.cw - 2, height: 16, rx: 4, style: `cursor:pointer;fill:${w.ok ? "var(--ink)" : "none"};stroke:${w.ok ? "var(--ink)" : "var(--ink-3)"}`, "stroke-dasharray": w.ok ? null : "3 3" }));
        e.addEventListener("click", (ev) => { ev.stopPropagation(); S.band = S.band === w.j ? null : w.j; S.jan = w.j; salvar(); render(); }); if (w.ap * c.cw > 22) c.text(w.k + w.ap / 2, c.top + 12, "j" + w.j, { "text-anchor": "middle", "pointer-events": "none", style: `fill:${w.ok ? "var(--surface)" : "var(--ink-2)"};font-weight:600` }); }); } },
      { title: "Atendimento · injeção por recurso × demanda realizada [kW]", h: 130, w: 4, draw(c) { const y = c.sc(temNeg ? -lo * 1.15 : 0, hi); c.grid(y, temNeg ? [-lo, 0, hi / 2, hi] : tk(hi), fd(hi)); c.stack(inj, y); c.stack([{ v: A.pc, hatch: "bat", k: "bat" }, { v: A.expR, hatch: "grid", k: "grid" }], y, { neg: true }); c.step(A.demR, y, { w: 2.2, k: "dem" }); } },
      A.wtP !== undefined || A.fvP !== undefined ? { title: "Renováveis · aproveitado + vertido = potencial utilizável [kW]", h: 56, w: 1.4, draw(c) { const mx = teto(maxv(Array.from({ length: K }, (_, i) => mais(el(A.wtA, i), el(A.fvA, i))))), y = c.sc(0, mx); c.grid(y, tk(mx), fd(mx)); c.stack([{ v: A.wtP, c: COR.wt, k: "wt" }, { v: A.fvP, c: COR.fv, k: "fv" }, { v: A.wtV, hatch: "wt", k: "wt" }, { v: A.fvV, hatch: "fv", k: "fv" }], y); } } : null,
      A.fr !== undefined ? { title: `Bateria · energia interna nas fronteiras [kWh]${R.bat.length > 1 ? ` · soma de ${R.bat.length} bancos (derivado)` : ""}`, res: "bat", h: 56, w: 1.4, draw(c) { const mx = A.cap > 0 ? Math.max(A.cap, maxv(A.fr)) : teto(maxv(A.fr)), y = c.sc(0, mx * 1.08); c.grid(y, tk(mx), fd(mx)); c.front(A.fr, y, { r: 2.4, k: "bat" }); } } : null,
      A.fcP !== undefined ? { title: "PEMFC · potência pedida [kW]" + (A.dinP ? " · ○ modelo dinâmico" : ""), res: "fc", h: 50, w: 1.2, draw(c) { const mx = teto(maxv(A.fcP, A.dinP || [])), y = c.sc(0, mx); c.grid(y, tk(mx), fd(mx)); c.stack([{ v: A.fcP, c: COR.fc, k: "fc" }], y); if (A.dinP) c.dots(A.fcOn.map((u, i) => (u ? A.dinP[i] : null)), y, { k: "fc", r: 2.6 }); } } : null,
      M.conectado ? { title: "Rede · importação realizada [kW]", res: "grid", h: 52, w: 1.2, draw(c) { const lim = F.pcc.limite_importacao_kW, mx = teto(Math.max(lim || 0, maxv(A.impR))), y = c.sc(0, mx); c.grid(y, tk(mx), fd(mx)); c.stack([{ v: A.impR, c: COR.grid, k: "grid" }], y); if (lim != null) c.hline(lim, y, "limite " + nf(lim, 0) + " kW", { c: "var(--bad)" }); } } : null,
      M.conectado ? laneTarifa({ res: "grid", h: 42, w: .9 }) : null,
      { title: "Custo realizado por intervalo [R$]", res: "eco", h: 48, w: 1.1, note: "total " + rs(F.resumo.custo_realizado_total_R), draw(c) { if (A.cInt == null) return c.nd("custo por intervalo não persistido"); const mx = teto(maxv(A.cInt)), y = c.sc(0, mx); c.grid(y, tk(mx), fd(mx)); c.stack(compCusto(), y); } }].filter(Boolean);
    return lanes;
  }
  function lOperacao() {
    const host = h("div", { class: "host" }), col = h("div", { class: "col" }); let T = null;
    const paint = (i) => col.replaceChildren(...inspetor(i, () => T).filter(Boolean)); paint(S.cur); HOOKS.push(paint);
    const lg = (k, t) => h("button", { class: "leg", onpointerenter: () => T && T.focus(k), onpointerleave: () => T && T.focus(null), onfocus: () => T && T.focus(k), onblur: () => T && T.focus(null), onclick: () => abrir(k), title: "Abrir o painel de " + TIPOS[k].n, html: `<i style="background-color:${COR[k]}"></i>${t}` });
    const lanes = lanesOperacao();
    const w = S.band != null ? porJ.get(S.band) : null;
    setTimeout(() => { T = trama(host, opts({ lanes, band: w ? [w.k, Math.min(K, w.k + w.Nk)] : null, label: "Partitura da operação" })); });
    const tem = (k) => M.ord.includes(k);
    return h("div", { class: "stage" }, h("div", { class: "panel acc", style: "--acc:var(--ink-3)" },
      h("div", { class: "chead" }, tem("wt") ? lg("wt", "Eólica") : null, tem("fv") ? lg("fv", "Solar") : null, tem("bat") ? lg("bat", "Bateria") : null, tem("fc") ? lg("fc", "PEMFC") : null, tem("grid") ? lg("grid", "Rede") : null,
        h("button", { class: "leg", onclick: () => abrir("dem"), title: "Abrir o painel de Carga / Demanda", html: `<i class="ln" style="background:var(--s-dem)"></i>Demanda` }), h("span", { class: "leg", html: `<i class="ht" style="background-color:var(--ink-3)"></i>hachura = carga da bateria, exportação e vertimento` }),
        ...legTar().filter(Boolean).map(legEl), h("span", { class: "grow" }), zoomSeg()), host), col);
  }
  // componentes do custo realizado por intervalo (só os termos declarados; ausente = N/D no motor)
  const compCusto = () => [{ v: A.cImp, c: COR.grid, k: "grid" }, { v: A.cH2, c: COR.fc, k: "fc" }, { v: A.cEv, c: COR.fc, k: "fc" }, { v: A.cThr, c: COR.bat, k: "bat" }, { v: A.cDes, c: COR.grid, k: "grid" }];
  const legCusto = () => [M.conectado ? { t: "Rede", c: COR.grid } : null, A.cH2 !== undefined ? { t: "Hidrogênio e eventos", c: COR.fc } : null, A.cThr !== undefined ? { t: "Throughput", c: COR.bat } : null,
    { t: "objetivo do MILP: operativo previsto", c: "var(--s-eco)" }, { t: "+ valor futuro estimado", c: "var(--s-eco)", tipo: "hachura" }].filter(Boolean);

  // ---------------------------------------------------------------- explorador de recursos (painéis)
  // Regra dos painéis: toda leitura passa por el()/vezes()/menos()/razao(); nenhuma expressão aritmética toca um valor ausente.
  function dash(k) {
    const c = TIPOS[k].c, ui = uidDe(k), fonte = F.fontes, T = S.tab[k], seq = (f) => Array.from({ length: K }, (_, i) => f(i));
    if (k === "fv" || k === "wt") {
      const r = F.renovaveis[ui] || {}, P = r.P_R_kW ?? null, Au = r.A_utilizavel_kW ?? null, V = r.vertimento_kW ?? null, Ap = r.A_prevista_kW ?? null, rsm = r.resumo || {}, par = r.parametros || {}, dg = r.diagnostico || {}, fv = k === "fv";
      const mx = teto(maxv(Au, P, A.demR)), part = P == null || A.demR == null ? null : seq((i) => razao(P[i], A.demR[i])), Eac = r.E_aproveitada_acum_kWh ?? null, me = teto(maxv(Eac));
      return { src: `${fonte.intervalos} · ${fonte.renovaveis}`, leg: [{ t: "aproveitada", c, tipo: "area" }, { t: "vertida", c, tipo: "hachura" }, ...legDem()], lanes: [
        { title: "Potência aproveitada + vertida = potencial utilizável [kW] · linha fina = demanda total da microrrede", h: 110, w: 3, draw(x) { const y = x.sc(0, mx); x.grid(y, tk(mx), fd(mx)); x.stack([{ v: P, c, k }, { v: V, hatch: k }], y); demRef(x, y); } },
        { title: "Energia aproveitada acumulada [kWh] · valor gravado ao fim de cada intervalo", h: 70, w: 1.6, draw(x) { if (!Eac) return nd(x); const y = x.sc(0, me); x.grid(y, tk(me), fd(me)); x.front([0, ...Eac], y, { c, r: 2.2 }); } },
        { title: "Participação na demanda realizada [%] · derivado: aproveitada ÷ demanda", h: 36, draw(x) { x.strip(part, x.top, 18, (t) => (t == null ? "var(--field)" : `color-mix(in srgb, ${c} ${Math.min(100, Math.round(t))}%, var(--field-2))`), (t) => (t === null ? ["N/D", "var(--warn)"] : t !== undefined && t > .5 ? [nf(t, 0), t > 55 ? "var(--surface)" : "var(--ink)"] : null)); } }],
        tip: tip((i) => [["Potencial utilizável", nf(el(Au, i), 2) + " kW"], ["Aproveitada", nf(el(P, i), 2) + " kW"], ["Vertida", nf(el(V, i), 2) + " kW"], ["Potencial previsto na decisão", nf(el(Ap, i), 2) + " kW"], ...tipDem(i)]),
        cards: (i) => [
          card({ acc: c, t: `Instante ${ivl(i)}`, big: `${nf(el(P, i), 2)}<small>kW aproveitados</small>`, grid: [["Potencial utilizável", nf(el(Au, i), 2) + " kW"], ["Vertido", nf(el(V, i), 2) + " kW"], ["Previsto na decisão", nf(el(Ap, i), 2) + " kW"], ["Da demanda (derivado)", nfu(el(part, i), 1, " %")]] }),
          card({ t: "Missão", big: `${nf(rsm.energia_aproveitada_kWh, 1)}<small>kWh aproveitados</small>`, grid: [["Potencial utilizável", nf(rsm.energia_utilizavel_kWh, 1) + " kWh"], ["Vertida", nf(rsm.energia_vertida_kWh, 1) + " kWh"], ["Pico aproveitado", nf(rsm.pico_aproveitado_kW, 1) + " kW"], ["Aproveitamento (derivado)", nfu(razao(rsm.energia_aproveitada_kWh, rsm.energia_utilizavel_kWh), 1, " %")]] }),
          card({ t: "Equipamento e modelo", tag: "gravado na rodada", kv: fv ? [["Módulo", esc(par.modulo ?? "N/D")], ["Arranjo (série × paralelo)", `${par.n_series ?? "N/D"} × ${par.n_parallel ?? "N/D"}`], ["Potência STC", nf(par.p_stc_arranjo_kW, 1) + " kWp"], ["NOCT · γ", `${nf(par.noct_C, 0)} °C · ${nf(par.gamma_pmax_pct_C, 2)} %/°C`], ["Sujeira · η barramento", `${nf(par.sujeira_pct, 0)} % · ${nf(par.eta_conversao_barramento, 2)}`], ["GHI máx. · T célula máx.", `${nf(dg.ghi_max_W_m2, 0)} W/m² · ${nf(dg.temperatura_celula_max_C, 1)} °C`]]
            : [["Aerogerador", esc(par.modelo_aerogerador ?? "N/D")], ["Nominal · quantidade", `${nf(par.potencia_nominal_unidade_kW, 0)} kW · ${par.quantidade ?? "N/D"}`], ["Cut-in · cut-out", `${nf(par.cut_in_m_s, 1)} · ${nf(par.cut_out_m_s, 0)} m/s`], ["Densidade do ar", nf((dg.densidade || {}).media_kg_m3, 3) + " kg/m³"], ["Horas abaixo do cut-in", nf(dg.horas_abaixo_cut_in, 1) + " h"], ["Vento médio · máx.", `${nf(dg.vento_medio_m_s, 1)} · ${nf(dg.vento_max_m_s, 1)} m/s`]],
            note: esc(r.modelo || "") + (F.clima.realizacao === "igual_a_previsao" ? " Realização = previsão nesta rodada (sem erro de previsão renovável)." : ""),
            nd: [(fv ? "irradiância e temperatura" : "velocidade do vento") + " por intervalo: a série climática está na previsão do cenário" + (F.clima.sha256_serie ? ` (SHA-256 ${esc(String(F.clima.sha256_serie).slice(0, 12))}…)` : "") + ", não nos dados da rodada", fv ? "temperatura de célula por intervalo (só o máximo é gravado)" : "curva de potência do aerogerador (está no catálogo, não na rodada)"] })] };
    }
    if (k === "bat") {
      const b = F.baterias[ui] || {}, rsm = b.resumo || {}, cap = rsm.capacidade_kWh ?? null, E = b.energia_kWh ?? null, pc = b.P_c_kW ?? null, pd = b.P_d_kW ?? null, soc = b.soc ?? null, dc = b.declaracao || {}, cth = dc.custo_throughput_R_kWh ?? null;
      // comportamento DERIVADO: 4 = N/D (falta potência ou energia do intervalo)
      const st = seq((i) => { const qc = el(pc, i), qd = el(pd, i), e = el(E, i); return qc == null || qd == null ? 4 : qc > 1e-6 ? 2 : qd > 1e-6 ? 3 : e == null ? 4 : e > 1e-6 ? 1 : 0; });
      const stN = ["vazia", "preserva", "carga", "descarga", "N/D"], stC = ["var(--field-2)", "var(--seq-1)", "url(#pth-bat)", c, "var(--field)"], pres = st.filter((s) => s === 1).length, semDado = st.filter((s) => s === 4).length;
      const thr = seq((i) => vezes(mais(el(pc, i) ?? null, el(pd, i) ?? null), hD)), cT = cth != null ? thr.map((t) => vezes(t, cth)) : b.declaracao ? undefined : null;
      const mE = teto(Math.max(cap || 0, maxv(E))), mP = teto(maxv(pd, [dc.p_descarga_barramento_kW], A.demR)), mC = teto(maxv(pc, [dc.p_carga_barramento_kW])), mT = teto(maxv(cT));
      const pbar = (i) => { const qd = el(pd, i), qc = el(pc, i); return qd == null || qc == null ? "N/D" : qd > 0 ? "+" + nf(qd, 1) + " kW" : qc > 0 ? "−" + nf(qc, 1) + " kW" : "0 kW"; };
      const socTxt = (i, d) => `${nf(vezes(el(soc, i), 100), d)} → ${nf(vezes(el(soc, i + 1), 100), d)} %`;
      return { src: `${fonte.intervalos} · ${fonte.fronteiras}`, padL: 70, leg: [{ t: "energia interna (fronteiras)", c, tipo: "ponto" }, { t: "descarga (+)", c, tipo: "area" }, { t: "carga (−)", c, tipo: "hachura" }, ...legDem(), ...legTar()], lanes: [
        { title: "Energia interna nas fronteiras [kWh] · SOC [%]", h: 100, w: 3, draw(x) { const y = x.sc(0, mE * 1.06); if (cap) { x.grid(y, [0, cap / 2, cap], (t) => `${nf(t, 0)} · ${nf((100 * t) / cap, 0)} %`); x.hline(cap, y, `capacidade ${nf(cap, 0)} kWh`); } else x.grid(y, tk(mE), fd(mE)); x.front(E, y, { c, r: 2.8 }); } },
        { title: "Potência no barramento [kW] · descarga (+) · carga (−) · linha fina = demanda total", h: 84, w: 2, draw(x) { const y = x.sc(-mC * 1.15, mP * 1.1); x.grid(y, [-mC, 0, mP], fd(mP)); x.stack([{ v: pd, c, k }], y); x.stack([{ v: pc, hatch: "bat" }], y, { neg: true }); demRef(x, y); if (dc.p_descarga_barramento_kW != null) x.text(v0(), y(dc.p_descarga_barramento_kW) - 4, `limite de descarga ${nf(dc.p_descarga_barramento_kW, 0)} kW`); if (dc.p_carga_barramento_kW != null) x.text(v0(), y(-dc.p_carga_barramento_kW) + 12, `limite de carga ${nf(dc.p_carga_barramento_kW, 0)} kW`); } },
        { title: "Comportamento em cada intervalo · derivado de P e E gravados", h: 36, draw(x) { x.strip(st, x.top, 18, (s) => stC[s], (s) => [stN[s], s === 3 ? "var(--surface)" : s === 4 ? "var(--warn)" : "var(--ink)", s === 2]); } },
        M.conectado ? laneTarifa({ title: "Tarifa de decisão do PCC [R$/kWh] · contexto · degrau por intervalo", h: 46 }) : null,
        { title: "Custo de throughput [R$] · derivado: (P carga + P descarga) × Δ × custo declarado", h: 46, w: 1, draw(x) { if (cT === undefined) return x.text(v0(), x.top + 13, "custo de throughput não declarado para este banco (termo fora do objetivo)"); const y = x.sc(0, mT); x.grid(y, [0, mT], fd(mT)); x.stack([{ v: cT, c, k }], y); } }].filter(Boolean),
        tip: tip((i) => [["Energia (início → fim)", `${nf(el(E, i), 2)} → ${nf(el(E, i + 1), 2)} kWh`], ["SOC (início → fim)", socTxt(i, 1)], ["Descarga", nf(el(pd, i), 2) + " kW"], ["Carga", nf(el(pc, i), 2) + " kW"], ["Comportamento (derivado)", stN[st[i]]], ...tipDem(i), ...tipTar(i)]),
        cards: (i) => [
          card({ acc: c, t: `Instante ${ivl(i)}`, tag: stN[st[i]], tc: st[i] === 4 ? "w" : "", big: `${nf(el(E, i), 1)} → ${nf(el(E, i + 1), 1)}<small>kWh</small>`, grid: [["SOC", socTxt(i, 0)], ["Potência no barramento", pbar(i)], M.conectado ? ["Tarifa", nf(el(A.tar, i), 2) + " R$/kWh"] : null, ["Throughput (derivado)", cT === undefined ? "não declarado" : rs(el(cT, i))]] }),
          card({ t: "Missão", big: `${nf(rsm.energia_descarregada_kWh, 1)}<small>kWh descarregados</small>`, grid: [["Carregados", nf(rsm.energia_carregada_kWh, 1) + " kWh"], ["Estado inicial → final", `${nf(rsm.energia_inicial_kWh, 1)} → ${nf(rsm.energia_final_kWh, 1)} kWh`], ["SOC inicial → final", `${nf(vezes(rsm.soc_inicial, 100), 0)} → ${nf(vezes(rsm.soc_final, 100), 0)} %`], ["Throughput (derivado)", nf(somaT(thr), 1) + " kWh"],
            ["Custo de throughput (missão)", cT === undefined ? "não declarado" : R.bat.length === 1 ? rs((F.resumo.componentes_R || {}).throughput_bess) : rs(somaT(cT))], ["Intervalos preservando", `${pres} de ${K}` + (semDado ? ` · ${semDado} sem dado` : "")]] }),
          card({ t: "Limites e declarações", tag: "cenário v" + F.rodada.versao_cenario, kv: [["Capacidade", nf(cap, 1) + " kWh"], ["Carga · descarga no barramento", `${nf(dc.p_carga_barramento_kW, 0)} · ${nf(dc.p_descarga_barramento_kW, 0)} kW`], ["η carga · descarga", `${nf(dc.eta_carga, 2)} · ${nf(dc.eta_descarga, 2)}`], ["Custo de throughput", nf(cth, 3) + " R$/kWh"], ["Autodescarga", esc(dc.hipotese_autodescarga ?? "N/D")]],
            note: "Energia interna (kWh, estado nas fronteiras) e potência no barramento (kW, média do intervalo) são grandezas diferentes e nunca se somam. «Preserva» = potência nula com energia armazenada: a interface descreve, não atribui motivo.", nd: ["tensão, corrente e temperatura do banco (o modelo é energético)"] })] };
    }
    if (k === "fc") {
      const p = F.pemfc[ui] || {}, d = p.dinamica, dx = d && d.intervalos ? d.intervalos : null, cv = p.curva, dc = p.declaracao || {}, rsm = p.resumo || {}, rd = p.resumo_dinamica || {}, me = p.massas_eventos || {}, md = me.modelo_dinamico || {}, t = T || "op";
      const U = p.u ?? null, Pk = p.p_kW ?? null, Q = p.q_h2_kg_h ?? null, Mh = p.m_h2_kg ?? null, Ch = termo(p.custo_h2_R ?? null, declarado(F, "combustivel_h2")), par = p.partida ?? null, pad = p.parada ?? null;
      const dP = dx ? dx.map((q) => q.p_entregue_media_kW ?? null) : null, dM = dx ? dx.map((q) => q.h2_modelo_dinamico_kg ?? null) : null;
      const base = { src: `${fonte.intervalos} · ${fonte.pemfc} · ${fonte.pemfc_dinamica}`, tabs: [["op", "Operação"], ["curva", "Curva q(P) e B04"], ["din", "Verificação dinâmica"]], tab: t };
      const dom = (cv && cv.dominio_kW) || [dc.p_min_kW ?? null, null], mP = teto(maxv(Pk, [dom[1]], A.demR)), mQ = teto(maxv(Q)), mM = teto(maxv(Mh, dM)), mC = teto(maxv(Ch));
      const est = (i) => (el(U, i) == null ? "N/D" : el(par, i) ? "partida" : el(pad, i) ? "parada" : U[i] ? "ON" : "OFF"), entr = (i) => (dP ? (el(U, i) == null ? "N/D" : U[i] ? nf(dP[i], 2) + " kW" : "—") : "N/D");
      const custoH = (i) => (Ch === undefined ? "não declarado" : rs(el(Ch, i)));
      if (t === "op") return { ...base, leg: [{ t: "potência líquida pedida", c, tipo: "area" }, dP ? { t: "entregue no modelo dinâmico", c: "var(--ink)", tipo: "ponto" } : null, ...legDem()], lanes: [
        { title: "Estado da unidade · partidas e paradas", h: 36, draw(x) { x.strip(U, x.top, 18, (u) => (u == null ? "var(--field)" : u ? c : "var(--field-2)"), (u, i) => (u == null ? ["N/D", "var(--warn)"] : [el(par, i) ? (x.cw > 64 ? "▲ partida" : "▲") : el(pad, i) ? (x.cw > 64 ? "▼ parada" : "▼") : u ? "ON" : "", u ? "var(--surface)" : "var(--ink-2)"])); } },
        { title: "Potência líquida pedida [kW]" + (dP ? " · ○ entregue no modelo dinâmico" : "") + " · linha fina = demanda total", h: 84, w: 2.4, draw(x) { const y = x.sc(0, mP * 1.08); x.grid(y, tk(mP), fd(mP)); x.stack([{ v: Pk, c, k }], y); demRef(x, y); if (dP) x.dots(mapa(U, (u, i) => (u ? dP[i] : null)), y); if (dom[1] != null) x.text(v0(), y(dom[1]) - 4, `P máx ${nf(dom[1], 0)} kW`); if (dom[0] != null) x.text(v0(), y(dom[0]) - 4, `P mín técnica ${nf(dom[0], 0)} kW`); } },
        { title: "Vazão de H₂ suprido [kg/h] · PWL certificada", h: 60, w: 1.4, draw(x) { const y = x.sc(0, mQ); x.grid(y, tk(mQ), fd(mQ)); x.step(Q, y, { c, w: 2.2 }); } },
        { title: "Massa de H₂ por intervalo [kg] · barra = EMS" + (dM ? " · ○ = modelo dinâmico" : ""), h: 60, w: 1.4, draw(x) { const y = x.sc(0, mM); x.grid(y, tk(mM), fd(mM)); x.stack([{ v: Mh, c, k }], y); if (dM) x.dots(mapa(U, (u, i) => (u || el(pad, i) ? dM[i] : null)), y); } },
        { title: "Massa de H₂ acumulada [kg] · valor gravado ao fim de cada intervalo", h: 56, w: 1.2, draw(x) { const a = p.m_h2_acum_kg; if (!a) return nd(x); const mA = teto(maxv(a)), y = x.sc(0, mA); x.grid(y, tk(mA), fd(mA)); x.front([0, ...a], y, { c, r: 2.2 }); } },
        { title: "Custo do hidrogênio [R$]", h: 50, w: 1, draw(x) { if (Ch === undefined) return x.text(v0(), x.top + 13, "termo de combustível não declarado no objetivo desta rodada"); const y = x.sc(0, mC); x.grid(y, tk(mC), fd(mC)); x.stack([{ v: Ch, c, k }], y); } }],
        tip: tip((i) => [["Estado", est(i)], ["Potência pedida", nf(el(Pk, i), 2) + " kW"], dP ? ["Entregue (dinâmico)", entr(i)] : null, ["Vazão de H₂", nf(el(Q, i), 3) + " kg/h"], ["Massa no intervalo", nf(el(Mh, i), 3) + " kg"], ["Custo", custoH(i)], ...tipDem(i)]),
        cards: (i) => [
          card({ acc: c, t: `Instante ${ivl(i)}`, tag: est(i), tc: el(U, i) == null ? "w" : "", big: `${nf(el(Pk, i), 2)}<small>kW pedidos</small>`, grid: [["Entregue (dinâmico)", entr(i)], ["Vazão de H₂", nf(el(Q, i), 3) + " kg/h"], ["Massa (EMS · dinâmico)", `${nf(el(Mh, i), 3)} · ${nf(el(dM, i), 3)} kg`], ["Custo do H₂", custoH(i)]] }),
          card({ t: "Missão", big: `${nf(rsm.massa_h2_kg, 3)}<small>kg de H₂</small>`, grid: [["Energia elétrica", nf(rsm.energia_kWh, 1) + " kWh"], ["Custo do H₂", rs(rsm.custo_h2_R)], ["Consumo específico", nf(rsm.consumo_especifico_kg_kWh, 4) + " kg/kWh"], ["Horas ligada", nf(rsm.horas_ligada, 1) + " h"], ["Partidas · paradas", `${rsm.partidas ?? "N/D"} · ${rsm.paradas ?? "N/D"}`], ["Potência média ligada", nf(rsm.potencia_media_ligada_kW, 1) + " kW"]] }),
          card({ t: "Restrições operacionais", tag: "cenário v" + F.rodada.versao_cenario, kv: [["Domínio de potência", `${nf(dom[0], 0)} – ${nf(dom[1], 0)} kW`], ["Rampa", nf(dc.rampa_kW_min, 0) + " kW/min"], ["Tempo mínimo ON · OFF", `${nf(dc.t_on_min, 0)} · ${nf(dc.t_off_min, 0)} min`], ["Partida/parada no MILP", esc(dc.abstracao ?? "N/D")], ["Massa por partida · parada", `${nf(me.m_partida_kg, 4)} · ${nf(me.m_parada_kg, 4)} kg`], ["Preço do H₂", nf(dc.preco_h2_R_kg, 2) + " R$/kg"]], note: "OFF = (0 kW, 0 kg/h) é um estado separado; não existe operação entre 0 e a potência mínima." })] };
      if (t === "din") { if (!dx) return { ...base, lanes: [{ title: "Verificação dinâmica", h: 60, draw(x) { nd(x, "verificação dinâmica não gravada nesta rodada (contrato de dados anterior ao 3D-A2-H)"); } }], cards: () => [card({ t: "Verificação dinâmica", nd: ["v2/pemfc_dinamica.json não existe nesta rodada"] })] };
        const eS = dx.map((q) => q.energia_solicitada_kWh ?? null), eE = dx.map((q) => q.energia_entregue_kWh ?? null), hE = dx.map((q) => q.h2_ems_kg ?? null), mE = teto(maxv(eS, eE)), okq = (q) => (q.coerente_energia == null || q.coerente_h2 == null ? null : !!(q.coerente_energia && q.coerente_h2));
        return { ...base, lanes: [
          { title: "Estados percorridos pelo modelo dinâmico", h: 36, draw(x) { x.strip(dx, x.top, 18, (q) => (q.evento === "desligada" ? "var(--field-2)" : c), (q) => [q.evento === "desligada" ? "" : (q.estados || []).join("→"), "var(--surface)"]); } },
          { title: "Energia por intervalo [kWh] · barra = pedida · ○ = entregue", h: 84, w: 2.2, draw(x) { const y = x.sc(0, mE); x.grid(y, tk(mE), fd(mE)); x.stack([{ v: eS, c, k }], y); x.dots(eS.map((s, i) => (s > 0 ? eE[i] : null)), y); } },
          { title: "Entregue − pedida [kWh] · derivado · tolerância gravada por intervalo", h: 38, draw(x) { x.strip(eS, x.top, 18, (s) => (s > 0 ? "var(--field-2)" : "var(--field)"), (s, i) => (s == null ? ["N/D", "var(--warn)"] : s > 0 ? [nf(menos(eE[i], s), 3)] : null)); } },
          { title: "H₂ por intervalo [kg] · barra = EMS · ○ = modelo dinâmico", h: 70, w: 1.8, draw(x) { const y = x.sc(0, mM); x.grid(y, tk(mM), fd(mM)); x.stack([{ v: hE, c, k }], y); x.dots(dx.map((q, i) => (q.evento !== "desligada" ? dM[i] : null)), y); } },
          { title: "Coerência por intervalo · energia e H₂ (gravada)", h: 36, draw(x) { x.strip(dx.map(okq), x.top, 18, (o) => (o == null ? "var(--field)" : o ? "color-mix(in srgb, var(--ok) 22%, var(--surface))" : "color-mix(in srgb, var(--bad) 45%, var(--surface))"), (o) => (o == null ? ["N/D", "var(--warn)"] : [o ? "✓" : "✕", o ? "var(--ok)" : "var(--bad)"])); } }],
          tip: tip((i) => [["Evento", esc(dx[i].evento ?? "N/D")], ["Estados", esc((dx[i].estados || []).join(" → "))], ["Energia pedida", nf(eS[i], 3) + " kWh"], ["Energia entregue", nf(eE[i], 3) + " kWh"], ["H₂ do EMS", nf(hE[i], 4) + " kg"], ["H₂ dinâmico", nf(dM[i], 4) + " kg"]]),
          cards: (i) => { const q = dx[i] || {}, ok = okq(q); return [
            card({ acc: c, t: `Instante ${ivl(i)}`, tag: ok == null ? "N/D" : ok ? "coerente" : "incoerente", tc: ok == null ? "w" : ok ? "ok" : "b", big: `${nf(eE[i], 2)}<small>kWh entregues</small>`, grid: [["Pedidos", nf(eS[i], 2) + " kWh"], ["Tolerância de energia", "± " + nf(q.tolerancia_energia_kWh, 2) + " kWh"], ["H₂ EMS · dinâmico", `${nf(hE[i], 3)} · ${nf(dM[i], 3)} kg`], ["Estados", esc((q.estados || []).join(" → "))]] }),
            card({ t: "Missão · verificação a posteriori", tag: rd.coerente == null ? "N/D" : rd.coerente ? "coerente" : "incoerente", tc: rd.coerente == null ? "w" : rd.coerente ? "ok" : "b", big: `${nf(rd.energia_entregue_kWh, 2)}<small>de ${nf(rd.energia_solicitada_kWh, 2)} kWh</small>`, grid: [["H₂ do EMS", nf(rd.h2_ems_kg, 3) + " kg"], ["H₂ do modelo dinâmico", nf(rd.h2_modelo_dinamico_kg, 3) + " kg"], ["Intervalos incoerentes", String(rd.intervalos_incoerentes ?? "N/D")], ["Subestimação de H₂ máx.", nf(rd.h2_subestimacao_max_kg, 4) + " kg"]] }),
            card({ t: "Modelo dinâmico aproximado", kv: [["Rampa de subida · descida", `${nf(md.rampa_subida_kW_s, 1)} · ${nf(md.rampa_descida_kW_s, 1)} kW/s`], ["Partida · parada", `${nf(md.partida_s, 0)} · ${nf(md.parada_s, 0)} s`], ["Potência de espera (IDLE)", nf(md.idle_kW, 0) + " kW"], ["Temperatura ambiente", nf(p.temperatura_ambiente_C, 0) + " °C"]],
              note: "As consignas do EMS (abstração instantânea) são reavaliadas pelo modelo dinâmico depois da missão. Coerência dinâmica não é validação física: nenhum equipamento real foi ensaiado.", nd: ["medições de equipamento real (validação física não realizada)"] })]; } }; }
      if (!cv || !cv.P_kW || !cv.q_suprido_kg_h) return { ...base, lanes: [{ title: "Curva q(P)", h: 60, draw(x) { nd(x, "curva e certificado não gravados nesta rodada"); } }], cards: () => [card({ t: "Curva q(P) e B04", nd: ["v2/pemfc.json não traz a curva nesta rodada"] })] };
      const V = cv.vertices || [], pwl = (Pv) => { for (let n = 1; n < V.length; n++) if (Pv <= V[n][0]) return V[n - 1][1] + ((Pv - V[n - 1][0]) / (V[n][0] - V[n - 1][0])) * (V[n][1] - V[n - 1][1]); return V.length ? V[V.length - 1][1] : null; };
      const mt = cv.metricas || {}, b4 = cv.b04 || {}, crit = b4.criterios || [], xM = teto(dom[1] || maxv(cv.P_kW)), qM = teto(maxv(cv.q_suprido_kg_h));
      const critN = { erro_rel_max: ["Erro relativo máximo", (x) => nf(vezes(x, 100), 3) + " %"], erro_abs_max_kg_h: ["Erro absoluto máximo", (x) => nf(vezes(x, 1000), 2) + " g/h"], subestimacao_rel_max: ["Subestimação relativa máxima", (x) => nf(vezes(x, 100), 3) + " %"], erro_massa_temporal_rel_max: ["Erro de massa nos perfis temporais", (x) => nf(vezes(x, 100), 3) + " %"], pontos_validacao_min: ["Pontos de validação", (x) => nf(x, 0)] };
      const cf = (q) => (critN[q.criterio] ? critN[q.criterio] : [String(q.criterio).replace(/_/g, " "), (x) => (x == null ? "N/D" : typeof x === "boolean" ? (x ? "sim" : "não") : String(x))]);
      return { ...base, special(host, i) {
        const a = h("div", { style: "flex:1.7 1 0;min-height:230px;position:relative" }), b = h("div", { style: "flex:1 1 0;min-height:150px;position:relative" });
        host.replaceChildren(h("div", { style: "display:flex;flex-direction:column;gap:6px;height:100%" }, h("div", { class: "chead" }, h("span", { class: "leg", html: `<i class="ln" style="background:var(--ink-2)"></i>modelo estacionário (${cv.P_kW.length} pontos gravados)` }), h("span", { class: "leg", html: `<i style="background:none;box-shadow:inset 0 0 0 2px ${c};border-radius:50%"></i>PWL certificada (${V.length} vértices)` }), h("span", { class: "leg", html: `<i style="background:${c};border-radius:50%"></i>pontos operados na missão` })), a, b));
        const ops = (U || []).map((u, n) => (u && el(Pk, n) != null && el(Q, n) != null ? [Pk[n], Q[n], n] : null)).filter(Boolean);
        xy(a, { exp: expMeta, x: [0, xM * 1.04], y: [0, qM], xl: "potência líquida [kW]", yl: "vazão de H₂ suprido [kg/h]", label: "Curva característica q(P)",
          near(xv) { if (xv < dom[0] || xv > dom[1]) return null; let n = 0; cv.P_kW.forEach((Pv, j) => { if (Math.abs(Pv - xv) < Math.abs(cv.P_kW[n] - xv)) n = j; }); const Pv = cv.P_kW[n], qm = cv.q_suprido_kg_h[n], qp = V.length ? pwl(Pv) : null; return { x: Pv, y: qm, html: `<b>P = ${nf(Pv, 2)} kW</b><div><span>Modelo (gravado)</span><span>${nf(qm, 4)} kg/h</span></div><div><span>PWL (derivado)</span><span>${nf(qp, 4)} kg/h</span></div><div><span>Diferença</span><span>${nf(vezes(menos(qp, qm), 1000), 2)} g/h</span></div>${cv.corrente_A ? `<div><span>Corrente</span><span>${nf(cv.corrente_A[n], 0)} A</span></div>` : ""}` }; },
          draw({ svg, X, Y, pt, H, pb }) { if (dom[0] > 0) svg.append(sv("rect", { x: X(0), y: pt, width: X(dom[0]) - X(0), height: H - pb - pt, style: "fill:var(--field)" }), sv("text", { x: X(dom[0] / 2), y: pt + 14, "text-anchor": "middle" }, "sem operação"), sv("text", { x: X(dom[0] / 2), y: pt + 27, "text-anchor": "middle" }, "entre 0 e P mín"));
            svg.append(sv("polyline", { points: cv.P_kW.map((Pv, j) => `${X(Pv)},${Y(cv.q_suprido_kg_h[j])}`).join(" "), fill: "none", style: "stroke:var(--ink-2);stroke-width:2.4" }), sv("polyline", { points: V.map((q) => `${X(q[0])},${Y(q[1])}`).join(" "), fill: "none", style: `stroke:${c};stroke-width:1.2` }));
            V.forEach((q) => svg.append(sv("circle", { cx: X(q[0]), cy: Y(q[1]), r: 3.2, style: `fill:var(--surface);stroke:${c};stroke-width:1.6` })));
            svg.append(sv("rect", { x: X(0) - 4, y: Y(0) - 4, width: 8, height: 8, style: `fill:var(--surface);stroke:${c};stroke-width:1.6` }), sv("text", { x: X(0) + 9, y: Y(0) - 7 }, "OFF (0; 0)"));
            ops.forEach(([Pv, q, n]) => { svg.append(sv("circle", { cx: X(Pv), cy: Y(q), r: n === i ? 7 : 4.5, style: `fill:${c};stroke:var(--surface);stroke-width:1.5` })); if (n === i) svg.append(sv("circle", { cx: X(Pv), cy: Y(q), r: 11, fill: "none", style: "stroke:var(--ink);stroke-width:1.5" }), sv("text", { x: X(Pv) + 15, y: Y(q) + 4, style: "fill:var(--ink);font-weight:600" }, `${lab(n)}: ${nf(Pv, 1)} kW · ${nf(q, 3)} kg/h`)); }); } });
        const er = V.length ? (cv.validacao || []).filter((q) => q[0] != null && q[1] != null).map((q) => [q[0], 1000 * (pwl(q[0]) - q[1])]) : [];
        if (!er.length) return b.replaceChildren(h("div", { class: "nd", html: "<b>N/D</b> — pontos de validação não gravados nesta rodada" }));
        const e1 = Math.max(...er.map((q) => q[1])), e0 = Math.min(0, ...er.map((q) => q[1])), pd2 = (e1 - e0) * .12 || 1;
        xy(b, { exp: expMeta, x: [0, xM * 1.04], y: [e0 - pd2, e1 + pd2], xl: `potência líquida [kW] · ${er.length} pontos de validação gravados`, yl: "PWL − modelo [g/h] · derivado dos pontos gravados", label: "Erro da aproximação PWL",
          draw({ svg, X, Y }) { svg.append(sv("polyline", { points: er.map((q) => `${X(q[0])},${Y(q[1])}`).join(" "), fill: "none", style: `stroke:${c};stroke-width:1.6` })); } });
      }, cards: (i) => [
        card({ acc: c, t: "Certificação B04", tag: "matemática", big: `${nf(vezes(mt.erro_rel_max, 100), 3)}<small>% de erro relativo máximo</small>`, sub: `política ${esc(b4.politica ?? "N/D")} · ${esc(String(b4.situacao_politica ?? "N/D").replace(/_/g, " "))} · ${crit.filter((q) => q.atendido).length} de ${crit.length} critérios`,
          el: h("table", { style: "margin-top:8px", html: "<tr><th>Critério</th><th class=n>Valor</th><th class=n>Limiar</th></tr>" + crit.map((q) => `<tr><td>${esc(cf(q)[0])}</td><td class="n">${cf(q)[1](q.valor)}</td><td class="n dim3">${q.criterio === "pontos_validacao_min" ? "≥ " : typeof q.limiar === "boolean" ? "" : "≤ "}${cf(q)[1](q.limiar)}</td></tr>`).join("") }),
          note: "A B04 certifica que a PWL reproduz o <b>modelo aproximado</b> dentro dos limiares. Não valida o modelo nem o equipamento: não é validação experimental." }),
        card({ t: el(U, i) == null ? `Instante ${ivl(i)} · estado N/D` : U[i] ? `Instante ${ivl(i)}` : `Instante ${ivl(i)} · unidade desligada`, big: el(U, i) == null ? "N/D" : U[i] ? `${nf(el(Q, i), 3)}<small>kg/h a ${nf(el(Pk, i), 1)} kW</small>` : `0<small>kg/h</small>`, sub: el(U, i) == null ? "estado da unidade não persistido" : U[i] ? "ponto destacado na curva" : "OFF é um estado separado no MILP" }),
        card({ t: "Modelo de origem", tag: "aproximado", kv: [["Stack · ânodo · cátodo", `${nf((cv.condicoes || {}).temperatura_stack_K, 2)} K · ${nf((cv.condicoes || {}).pressao_anodo_kPag, 0)} · ${nf((cv.condicoes || {}).pressao_catodo_kPag, 0)} kPa(g)`], ["Corrente no domínio", `${nf(mt.corrente_pmin_A, 0)} – ${nf(mt.corrente_pmax_A, 0)} A`], ["Consumo em P mín · P máx", `${nf(mt.consumo_especifico_pmin_kg_kWh, 4)} · ${nf(mt.consumo_especifico_pmax_kg_kWh, 4)} kg/kWh`], ["Curva (SHA-256)", esc(String(cv.sha_curva ?? "N/D").slice(0, 16)) + "…"], ["Certificado (SHA-256)", esc(String(cv.sha_certificado ?? "N/D").slice(0, 16)) + "…"]],
          note: esc(cv.fonte || "") + ". Uma curva por configuração física, reutilizada em toda a missão.", nd: ["caracterização experimental do equipamento instalado"] })] };
    }
    if (k === "grid") {
      const lim = F.pcc.limite_importacao_kW ?? null, I = F.intervalos, noLim = lim != null ? conta(A.impR, (q) => q >= lim - 1e-6) : undefined;
      const dvs = A.impP == null || A.impR == null ? null : seq((i) => menos(A.impR[i], A.impP[i])), dev = dvs == null || dvs.some((q) => q == null) ? null : Math.max(...dvs.map(Math.abs));
      const mI = teto(Math.max(lim || 0, maxv(A.impR, A.demR))), mE = teto(maxv(A.expR)), expND = A.expR == null || A.expR.some((q) => q == null), temExp = maxv(A.expR) > 1e-9, mC = teto(maxv(A.cImp)), ac = acum(A.cImp), mA = teto(maxv(ac)), eImp = F.resumo.energia_importada_kWh ?? null;
      const noLimI = (i) => lim != null && el(A.impR, i) != null && A.impR[i] >= lim - 1e-6;
      return { src: fonte.intervalos + " (anexo de rede)", leg: [{ t: "importação realizada", c, tipo: "area" }, { t: "importação programada", c: "var(--ink)", tipo: "tracejado" }, lim != null ? { t: "limite de importação", c: "var(--bad)", tipo: "tracejado" } : null, { t: "exportação realizada", c, tipo: "hachura" }, ...legDem(), ...legTar()], lanes: [
        { title: "Importação [kW] · barra = realizada · traço = programada · linha fina = demanda total", h: 100, w: 3, draw(x) { const y = x.sc(0, mI * 1.1); x.grid(y, tk(mI), fd(mI)); x.stack([{ v: A.impR, c, k }], y); x.step(A.impP, y, { c: "var(--ink)", w: 1.4, dash: "4 3" }); demRef(x, y); if (lim != null) x.hline(lim, y, `limite de importação ${nf(lim, 0)} kW`, { c: "var(--bad)" }); } },
        { title: "Exportação realizada [kW]", h: temExp || expND ? 60 : 34, w: temExp || expND ? 1.4 : 0, draw(x) { if (!temExp && !expND) return x.text(v0(), x.top + 13, `0 kW em todos os intervalos · sentidos declarados: ${String(F.pcc.sentidos ?? "N/D").replace(/_/g, " ")}`); const y = x.sc(0, mE); x.grid(y, tk(mE), fd(mE)); x.stack([{ v: A.expR, hatch: "grid" }], y); } },
        laneTarifa({ title: "Tarifas de decisão [R$/kWh] · importação × remuneração de exportação · degrau por intervalo", h: 62, w: 1.3 }),
        { title: "Custo de importação por intervalo [R$]", h: 60, w: 1.5, draw(x) { const y = x.sc(0, mC); x.grid(y, tk(mC), fd(mC)); x.stack([{ v: A.cImp, c, k }], y); } },
        { title: "Custo de importação acumulado [R$] · derivado (interrompido onde falta dado)", h: 60, w: 1.5, draw(x) { const y = x.sc(0, mA); x.grid(y, tk(mA), fd(mA)); x.front(ac, y, { c, r: 2.2 }); } }],
        tip: tip((i) => [["Importação realizada", nf(el(A.impR, i), 2) + " kW"], ["Importação programada", nf(el(A.impP, i), 2) + " kW"], ["Exportação realizada", nf(el(A.expR, i), 2) + " kW"], ...tipTar(i), ["Preço de liquidação", nf(el(I.preco_importacao_liquidacao_R_kWh, i), 2) + " R$/kWh"], ["Custo", rs(el(A.cImp, i))], ...tipDem(i)]),
        cards: (i) => [
          card({ acc: c, t: `Instante ${ivl(i)}`, tag: noLimI(i) ? "no limite" : "", tc: "w", big: `${nf(el(A.impR, i), 2)}<small>kW importados</small>`, grid: [["Programada", nf(el(A.impP, i), 2) + " kW"], ["Tarifa", nf(el(A.tar, i), 2) + " R$/kWh"], ["Custo", rs(el(A.cImp, i))], lim != null ? ["Folga até o limite", nf(menos(lim, el(A.impR, i)), 1) + " kW"] : null] }),
          card({ t: "Missão", big: `${nf(eImp, 1)}<small>kWh importados</small>`, grid: [["Custo de importação", rs(F.resumo.gasto_importacao_R)], ["Preço médio pago (derivado)", nfu(razao(F.resumo.gasto_importacao_R, eImp, 1), 3, " R$/kWh")], ["Intervalos no limite", noLim === undefined ? "limite não declarado" : noLim === null ? "N/D" : `${noLim} de ${K}`], ["Desvio máx. programado × realizado", nf(dev, 3) + " kW"], ["Exportada", nf(F.resumo.energia_exportada_kWh, 1) + " kWh"], ["Receita de exportação", rs(F.resumo.receita_exportacao_R)]] }),
          card({ t: "Declaração do PCC", tag: esc(F.pcc.procedencia || ""), tc: "w", kv: [["Modo", esc(F.pcc.modo ?? "N/D")], ["Sentidos", esc(String(F.pcc.sentidos ?? "N/D").replace(/_/g, " "))], ["Limite de importação", nf(lim, 0) + " kW"], ["Limite de exportação", nf(F.pcc.limite_exportacao_kW, 0) + " kW"], ["Ajuste na execução", esc(String(F.pcc.ajuste ?? "N/D").replace(/_/g, " "))]], note: esc(F.pcc.rotulo_tarifa || "") + " Intercâmbio agregado no ponto de conexão: não é fluxo de potência AC nem fatura real.", nd: ["tensão, reativo, perdas e demanda contratada (fora do modelo)"] })] };
    }
    if (k === "dem") {
      const at = A.at, dR = A.demR, ok = dR != null && dR.every((q) => q != null), pk = ok ? dR.indexOf(Math.max(...dR)) : null, mn = ok ? dR.indexOf(Math.min(...dR)) : null, nDef = conta(A.ens, (e) => e > 1e-9), ensND = A.ens == null || A.ens.some((q) => q == null);
      const inj = [{ v: A.wtP, c: COR.wt, k: "wt" }, { v: A.fvP, c: COR.fv, k: "fv" }, { v: A.pd, c: COR.bat, k: "bat" }, { v: A.fcP, c: COR.fc, k: "fc" }, { v: A.impR, c: COR.grid, k: "grid" }];
      const mD = teto(maxv(dR, A.demP)), mJ = teto(maxv(seq((i) => mais(...inj.map((s) => el(s.v, i)))), dR)), mEn = teto(maxv(A.ens)), dif = dR == null || A.demP == null ? null : seq((i) => menos(dR[i], A.demP[i]));
      return { src: fonte.intervalos, leg: [{ t: "demanda realizada", c: COR.dem, tipo: "linha" }, { t: "prevista na decisão", c: "var(--ink-3)", tipo: "tracejado" }, { t: "atendida", c: "color-mix(in srgb, var(--ink) 16%, var(--surface))", tipo: "area" }, { t: "déficit", c: "var(--bad)", tipo: "area" }], lanes: [
        { title: "Demanda [kW] · linha = realizada · tracejado = prevista na decisão · área = atendida", h: 100, w: 3, draw(x) { const y = x.sc(0, mD); x.grid(y, tk(mD), fd(mD)); x.stack([{ v: at, c: "color-mix(in srgb, var(--ink) 16%, var(--surface))" }], y); x.step(A.demP, y, { c: "var(--ink-3)", w: 1.4, dash: "4 3" }); x.step(dR, y, { w: 2.2 }); } },
        { title: "Déficit [kW]", h: nDef || ensND ? 60 : 34, w: nDef || ensND ? 1.4 : 0, draw(x) { if (!nDef && !ensND) return x.text(v0(), x.top + 13, `nenhum déficit: 0 kW em ${K} de ${K} intervalos`); const y = x.sc(0, mEn); x.grid(y, tk(mEn), fd(mEn)); x.stack([{ v: A.ens, c: "var(--bad)" }], y); } },
        { title: "Quem injetou no barramento [kW] · inclui a potência que carregou a bateria", h: 90, w: 2.4, draw(x) { const y = x.sc(0, mJ); x.grid(y, tk(mJ), fd(mJ)); x.stack(inj, y); x.step(dR, y, { w: 1.8 }); } },
        { title: "Realizada − prevista [kW] · derivado", h: 36, draw(x) { if (!dif) return nd(x, "demanda realizada ou prevista por intervalo não persistida"); x.strip(dif, x.top, 18, (q) => (q == null ? "var(--field)" : "var(--field-2)"), (q) => (q == null ? ["N/D", "var(--warn)"] : [nf(q, Math.abs(q) < 10 && q % 1 ? 1 : 0)])); } }],
        tip: tip((i) => [["Demanda realizada", nf(el(dR, i), 2) + " kW"], ["Demanda prevista", nf(el(A.demP, i), 2) + " kW"], ["Atendida", nf(el(at, i), 2) + " kW"], ["Déficit", nf(el(A.ens, i), 2) + " kW"]]),
        cards: (i) => [
          card({ acc: "var(--ink)", t: `Instante ${ivl(i)}`, big: `${nf(el(dR, i), 1)}<small>kW demandados</small>`, grid: [["Prevista na decisão", nf(el(A.demP, i), 1) + " kW"], ["Atendida", nf(el(at, i), 1) + " kW"], ["Déficit", nf(el(A.ens, i), 1) + " kW"], ["Cobertura (derivado)", nfu(razao(el(at, i), el(dR, i)), 0, " %")]] }),
          card({ t: "Missão", big: `${nf(F.resumo.energia_atendida_kWh, 1)}<small>kWh atendidos</small>`, grid: [["Demandados", nf(F.resumo.energia_demanda_kWh, 1) + " kWh"], ["Déficit", nf(F.resumo.energia_nao_atendida_kWh, 2) + " kWh"], ["Cobertura de energia (derivado)", nfu(razao(F.resumo.energia_atendida_kWh, F.resumo.energia_demanda_kWh), 1, " %")], ["Intervalos com déficit", nDef == null ? "N/D" : `${nDef} de ${K}`], ["Pico", pk == null ? "N/D" : `${nf(dR[pk], 1)} kW às ${lab(pk)}`], ["Mínimo", mn == null ? "N/D" : `${nf(dR[mn], 1)} kW às ${lab(mn)}`]] }),
          card({ t: "Declaração da demanda", kv: [["Classe", esc(F.demanda.criticidade ?? "N/D")], ["Semântica", esc(String(F.demanda.semantica ?? "N/D").replace(/_/g, " "))], ["Emissão da previsão", esc(F.demanda.emissao_utc ?? "N/D")]], note: "«Realizada» é a realização simulada do ensaio, não uma medição.", nd: ["índices probabilísticos de confiabilidade (há uma única realização simulada)"] })] };
    }
    if (k === "liq") {
      // UI-RESULTADOS-02 (melhoria 03) — carga líquida = demanda − renováveis APROVEITADAS; tudo derivado das séries gravadas
      const CL = cargaLiquida(M), L = CL.liq, D = A.demR, ren = CL.ren, semRen = ren === undefined, cl = COR.liq;
      const pos = [{ v: A.pd, c: COR.bat, k: "bat" }, { v: A.fcP, c: COR.fc, k: "fc" }, { v: A.impR, c: COR.grid, k: "grid" }, { v: A.ens, c: COR.ens, k: "ens" }];
      const neg = [{ v: A.pc, hatch: "bat", k: "bat" }, { v: A.expR, hatch: "grid", k: "grid" }];
      const lo = Math.min(0, ...(L || []).filter((v) => v != null)), mN = lo < -1e-9 ? teto(-lo) : 0, mD = teto(maxv(D, L));
      const sP = seq((i) => mais(...pos.map((q) => el(q.v, i)))), sN = seq((i) => mais(...neg.map((q) => el(q.v, i))));
      const mPos = teto(maxv(sP, L)), mNeg = Math.max(maxv(sN) > 1e-6 ? teto(maxv(sN)) : 0, mN);
      const vR = (i) => (semRen ? "sem renováveis" : nf(el(ren, i), 2) + " kW"), pk = (p) => (p == null ? "N/D" : `${nf(p[1], 1)} kW às ${lab(p[0])}`);
      return { src: `${fonte.intervalos} · derivado: demanda − renováveis aproveitadas`,
        leg: [{ t: "demanda total", c: COR.dem, tipo: "linha" }, { t: "carga líquida", c: cl, tipo: "linha" }, R.fv.length ? { t: "solar aproveitada", c: COR.fv } : null, R.wt.length ? { t: "eólica aproveitada", c: COR.wt } : null,
          A.pd !== undefined ? { t: "descarga", c: COR.bat } : null, A.fcP !== undefined ? { t: "PEMFC", c: COR.fc } : null, M.conectado ? { t: "importação", c: COR.grid } : null, { t: "não atendida", c: COR.ens },
          A.pc !== undefined ? { t: "carga da bateria", c: COR.bat, tipo: "hachura" } : null, M.conectado ? { t: "exportação", c: COR.grid, tipo: "hachura" } : null],
        lanes: [
          { title: "Demanda total × carga líquida [kW] · carga líquida = demanda − renováveis aproveitadas (derivado)", h: 110, w: 3, draw(x) {
            const y = x.sc(mN ? -mN * 1.1 : 0, mD * 1.04); x.grid(y, mN ? [-mN, 0, mD / 2, mD] : tk(mD), fd(mD));
            if (!semRen && L) for (let i = 0; i < K; i++) {                     // faixa renovável entre a carga líquida e a demanda
              let b = el(L, i); if (b == null) continue;
              for (const [a, cor] of [[A.fvP, COR.fv], [A.wtP, COR.wt]]) { const v = el(a, i); if (v == null || v <= 1e-6) continue;
                x.add(sv("rect", { x: x.x(i) + 1, y: y(b + v), width: Math.max(x.cw - 2, 1), height: Math.max(.8, y(b) - y(b + v)), style: `fill:${cor};opacity:.38`, "data-k": "ren" })); b += v; } }
            x.step(D, y, { c: COR.dem, w: 2, k: "dem" }); x.step(L, y, { c: cl, w: 2.4, k: "liq" }); } },
          { title: "Compensação da carga líquida [kW] · acima de zero: recursos que suprem · abaixo: recursos que absorvem · linha = carga líquida", h: 110, w: 3, draw(x) {
            const y = x.sc(mNeg ? -mNeg * 1.15 : 0, mPos * 1.04); x.grid(y, mNeg ? [-mNeg, 0, mPos / 2, mPos] : tk(mPos), fd(mPos));
            x.stack(pos, y); x.stack(neg, y, { neg: true }); x.step(L, y, { c: cl, w: 2.2, k: "liq" }); } },
          { title: "Fechamento do balanço [kW] · derivado: compensação − carga líquida (= resíduo gravado do barramento)", h: 38, w: 0, draw(x) {
            x.strip(CL.fech, x.top, 18, (v) => (v == null ? "var(--field)" : Math.abs(v) <= 1e-6 ? "color-mix(in srgb, var(--ok) 16%, var(--surface))" : "color-mix(in srgb, var(--warn) 32%, var(--surface))"), (v) => (v == null ? ["N/D", "var(--warn)"] : [ne(v, 0)])); } }],
        tip: tip((i) => [["Demanda total", nf(el(D, i), 2) + " kW"], ["Renováveis aproveitadas", vR(i)], ["Carga líquida (derivado)", nf(el(L, i), 2) + " kW"], A.pd !== undefined ? ["Descarga · carga", `${nf(el(A.pd, i), 2)} · ${nf(el(A.pc, i), 2)} kW`] : null,
          A.fcP !== undefined ? ["PEMFC", nf(el(A.fcP, i), 2) + " kW"] : null, M.conectado ? ["Importação · exportação", `${nf(el(A.impR, i), 2)} · ${nf(el(A.expR, i), 2)} kW`] : null, ["Demanda não atendida", nf(el(A.ens, i), 2) + " kW"], ["Fechamento (derivado)", ne(el(CL.fech, i), 1) + " kW"]]),
        cards: (i) => [
          card({ acc: cl, inst: 1, t: `Instante ${ivl(i)}`, big: `${nf(el(L, i), 2)}<small>kW de carga líquida</small>`, grid: [["Demanda total", nf(el(D, i), 2) + " kW"], ["Renováveis aproveitadas", vR(i)], ["Compensação (derivado)", nf(el(CL.comp, i), 2) + " kW"], ["Fechamento (derivado)", ne(el(CL.fech, i), 1) + " kW"]] }),
          card({ t: "Missão", tag: "derivado", big: `${nf(CL.eLiq, 1)}<small>kWh de carga líquida</small>`, grid: [["Energia demandada", nf(CL.eDem, 1) + " kWh"], ["Renováveis aproveitadas", semRen ? "sem renováveis" : nf(CL.eRen, 1) + " kWh"],
            ["Parcela positiva", nf(CL.ePos, 1) + " kWh"], ["Excedente renovável (parcela negativa)", nf(CL.eNeg, 1) + " kWh"], ["Pico", pk(CL.pico)], ["Mínimo", pk(CL.min)], ["Intervalos com carga líquida negativa", CL.nNeg == null ? "N/D" : `${CL.nNeg} de ${K}`], ["Fechamento máximo |Δ|", ne(CL.fechMax, 1) + " kW"]] }),
          card({ t: "Balanço da carga líquida", tag: "energia · derivado", el: cascata(CL), note: `Energia = média de intervalo gravada × Δ. Σ (suprem − absorvem) = <b>${nf(CL.somaTermos, 2)} kWh</b> · carga líquida = <b>${nf(CL.eLiq, 2)} kWh</b>. O fechamento por intervalo coincide com o resíduo gravado do barramento (diferença máxima ${ne(CL.difResiduo, 1)} kW).` }),
          card({ t: "Definição e convenções", note: "Carga líquida = demanda total − renováveis <b>efetivamente aproveitadas</b> (depois do vertimento; não o potencial), em cada intervalo [t_k, t_k+1). Valores negativos = excedente renovável e são preservados. Descarga, PEMFC, importação e demanda não atendida <b>suprem</b> a carga líquida; carga da bateria e exportação a <b>absorvem</b>. As séries são as gravadas por UID (arranjos, bancos, unidades), somadas por tecnologia uma única vez: nenhum equipamento nem agrupador é contado duas vezes." + (semRen ? " Sem renováveis nesta microrrede: a carga líquida é a própria demanda." : "") })] };
    }
    const w = (i) => janDe(i) || {}, mI = teto(maxv(A.cInt)), tot = A.cAcc ? [0, ...A.cAcc] : null, mT = teto(maxv(tot)), mO = teto(maxv(M.jan.map((q) => q.objetivo))), cp = F.resumo.componentes_R || {};
    return { src: `${fonte.intervalos} · ${fonte.janelas} · resumo selado`, leg: [...legCusto(), ...legTar()], lanes: [
      M.conectado ? laneTarifa({ title: "Tarifa de decisão do PCC [R$/kWh] · degrau por intervalo", h: 46 }) : null,
      { title: "Custo operacional realizado por intervalo [R$] · por componente", h: 80, w: 2.2, draw(x) { const y = x.sc(0, mI); x.grid(y, tk(mI), fd(mI)); x.stack(compCusto(), y); } },
      { title: "Custo operacional realizado acumulado [R$] · valor gravado", h: 84, w: 2.2, draw(x) { if (!tot) return nd(x); const y = x.sc(0, mT); x.grid(y, tk(mT), fd(mT)); x.front(tot, y, { c: "var(--ink)", r: 2.2 }); } },
      laneObjetivo(mO)].filter(Boolean),
      tip: tip((i) => [["Custo realizado no intervalo", rs(el(A.cInt, i))], ...tipTar(i), M.conectado ? ["Importação", rs(el(A.cImp, i))] : null, A.cH2 !== undefined ? ["Hidrogênio", rs(el(A.cH2, i))] : null, A.cThr !== undefined ? ["Throughput", rs(el(A.cThr, i))] : null, ["Acumulado", rs(el(A.cAcc, i))], ["Objetivo MILP da janela " + (w(i).j ?? "N/D"), rs(w(i).objetivo)]]),
      cards: (i) => [cardCusto(i, cp), cardObjetivo(w(i)), cardSinal(w(i))] };
  }
  const NOME_C = { importacao_rede: ["grid", "Importação da rede"], combustivel_h2: ["fc", "Hidrogênio (PEMFC)"], throughput_bess: ["bat", "Throughput da bateria"], eventos: ["fc", "Partidas e paradas"], exportacao_rede: ["grid", "Receita de exportação"], desvio_rede: ["grid", "Desvio no PCC"] };
  const laneObjetivo = (mO) => ({ title: "Objetivo do MILP por decisão [R$] · previsão: operativo previsto + valor futuro estimado (hachura)", h: 80, w: 2, note: "∅ = sem valor futuro · não é custo realizado", draw(x) { const y = x.sc(0, mO * 1.14); x.grid(y, tk(mO), fd(mO)); M.jan.forEach((q) => { if (!q.ap) return; const x0 = x.x(q.k) + 2, lw = Math.max(1, q.ap * x.cw - 4), meio = q.k + q.ap / 2;
    if (q.objetivo == null) { x.text(meio, x.bot - 6, "N/D", { "text-anchor": "middle", class: "v nd" }); return; }
    const op = q.custo_operativo_previsto, fut = q.custo_futuro_estimado, ir = (e) => { e.addEventListener("click", (ev) => { ev.stopPropagation(); S.ex = null; irLente("decisao", q.j); }); return e; };
    ir(x.add(sv("rect", { x: x0, y: y(op ?? q.objetivo), width: lw, height: Math.max(1, y(0) - y(op ?? q.objetivo)), rx: 3, style: "cursor:pointer;fill:var(--s-eco)" })));
    if (op != null && fut != null && fut > 1e-9) ir(x.add(sv("rect", { x: x0, y: y(op + fut), width: lw, height: Math.max(1, y(op) - y(op + fut)), rx: 3, style: "cursor:pointer;fill:url(#pth-eco)" })));
    if (q.ap * x.cw > 26) x.text(meio, y(q.objetivo) - 4, nf(q.objetivo, 0) + (q.ok ? "" : " ∅"), { "text-anchor": "middle", class: "v" }); }); } });
  const cardCusto = (i, cp) => card({ acc: "var(--ink)", t: "Custo operacional realizado", tag: "liquidado", big: rs(F.resumo.custo_realizado_total_R), sub: `até ${lab(i + 1)}: ${rs(el(A.cAcc, i))} · neste intervalo: ${rs(el(A.cInt, i))}`,
    el: h("div", { class: "rows", style: "margin-top:8px" }, ...Object.entries(cp).map(([q, x]) => { const [tp, t] = NOME_C[q] || ["eco", q.replace(/_/g, " ")]; return h("button", { class: "rowb", onclick: () => abrir(tp), html: `<i style="background:${COR[tp]}"></i><span>${esc(t)}<small>${nfu(razao(x, F.resumo.custo_realizado_total_R), 1, " %")}</small></span><b>${rs(x)}</b>` }); })) });
  const cardObjetivo = (w) => card({ t: `Objetivo do MILP · janela ${w.j ?? "N/D"}`, tag: "previsão", big: rs(w.objetivo), grid: [["Custo operativo previsto", rs(w.custo_operativo_previsto)], ["Custo futuro estimado", w.custo_futuro_estimado == null ? "N/D" : rs(w.custo_futuro_estimado)], ["Planejado no bloco aplicado", rs(w.planejado_prefixo)], ["Realizado no bloco", rs(w.realizado)]], note: "O objetivo cobre os N intervalos previstos de uma decisão. As janelas se sobrepõem: somar objetivos não tem significado e nunca é apresentado como custo." });
  const cardSinal = (w) => card({ t: "Sinal de valor futuro", tag: w.ok ? "válido" : "indisponível", tc: w.ok ? "ok" : "w", big: `${M.jan.filter((q) => q.ok).length}<small>de ${M.jan.length} decisões com sinal</small>`, note: "Instrumento de decisão do planejador. Não é custo, não é receita e nunca entra no custo realizado." + (w.ok || w.j == null ? "" : " Nesta janela: " + esc(w.sinal_motivo || "indisponível") + ".") });

  function explorador() {
    const k = S.ex, d = dash(k), c = TIPOS[k].c, rec = recDe(k), host = h("div", { class: "host" }), col = h("div", { class: "col" });
    const metaTxt = () => `<span>rodada <b>${esc(F.rodada.uid.slice(0, 8))}</b> · ${esc(F.rodada.cenario || "")}</span><span>instante <b>${ivl(S.cur)}</b>${S.pin ? " fixado" : ""}</span><span>leitura dos registros gravados, sem solver</span>`, meta = h("div", { class: "meta", html: metaTxt() });
    const paintCards = (i) => col.replaceChildren(...d.cards(i).filter(Boolean)); paintCards(S.cur);
    HOOKS.push((i) => { paintCards(i); if (d.special) d.special(host, i); meta.innerHTML = metaTxt(); });
    const lista = R[k] || [], nomeEq = k === "dem" ? "Demanda agregada" : k === "eco" ? "Custo realizado da missão" : k === "grid" ? "Ponto de conexão" : rec.nome;
    const ov = h("div", { class: "ov", onclick: (e) => { if (e.target === ov) fechar(); } }, h("div", { class: "dlg", role: "dialog", "aria-modal": "true", "aria-label": TIPOS[k].n, style: `--acc:${c}` },
      h("div", { class: "dhead" }, h("div", { class: "grow" }, h("div", { class: "eyebrow" }, TIPOS[k].n), h("h2", { html: `${esc(nomeEq)} <span class="uid">${esc([rec.tag, uidDe(k)].filter(Boolean).join(" · "))}</span>` }), meta),
        lista.length ? h("select", { class: "sel", "aria-label": "Equipamento (UID)", onchange: (e) => { S.uid[k] = e.target.value; salvar(); render(); } }, ...lista.map((r) => h("option", { value: r.uid, selected: r.uid === uidDe(k) }, `${r.nome} · ${r.uid}`))) : null,
        h("button", { class: "tool", title: "Cartões ao lado / embaixo", "aria-pressed": String(S.lay === "bot"), onclick: () => { S.lay = S.lay === "bot" ? "side" : "bot"; salvar(); render(); }, html: ico("M4 5h16v14H4zM4 14h16") }),
        h("button", { class: "tool pt-x", title: "Fechar (Esc)", "aria-label": "Fechar", onclick: fechar, html: ico("M6 6l12 12M18 6L6 18") })),
      h("div", { class: "dtools" }, h("div", { class: "seg", role: "tablist", "aria-label": "Recurso" }, ...M.ord.map((q) => h("button", { role: "tab", "aria-selected": String(q === k), onclick: () => abrir(q), html: `<i style="background:${TIPOS[q].c}"></i>${TIPOS[q].n.split(" / ")[0].replace("Solar fotovoltaica", "Solar")}` }))),
        d.tabs ? h("div", { class: "seg", role: "group", "aria-label": "Vista" }, ...d.tabs.map(([t, n]) => h("button", { "aria-pressed": String(d.tab === t), onclick: () => { S.tab[k] = t; salvar(); render(); } }, n))) : null, h("span", { class: "grow" }), d.special ? null : zoomSeg()),
      h("div", { class: "dbody" + (S.lay === "bot" ? " bot" : "") }, h("div", { class: "panel acc" }, d.leg && !d.special ? legRow(d.leg) : null, host), col),
      h("div", { class: "dfoot", html: `<span>Fontes: ${esc(d.src)}</span><span>N/D = dado não persistido na rodada; nenhuma curva é gerada para preencher</span><span>← → movem o instante · Enter fixa · Esc fecha · 1–${M.ord.length} trocam de recurso</span>` })));
    setTimeout(() => { if (d.special) d.special(host, S.cur); else trama(host, opts({ lanes: d.lanes.filter(Boolean), padL: d.padL, tip: d.tip, label: TIPOS[k].n, escSolta: false })); const x = ov.querySelector(".pt-x"); if (x && !ov.contains(root.getRootNode().activeElement)) x.focus({ preventScroll: true }); });
    return ov;
  }

  // ---------------------------------------------------------------- lente Decisão
  // O que o controlador SABIA em τ_k (estado executado até τ_k, previsão da janela, plano longo, sinal de valor futuro) fica
  // separado do que OCORREU DEPOIS (execução e realização a partir de τ_k), que pode ser ocultado. Nada aqui atribui causas.
  const janSel = () => { const j = S.jan != null && porJ.has(S.jan) ? S.jan : (janDe(S.cur) || M.jan[0] || {}).j; return j == null ? null : porJ.get(j); };
  const planoDe = (j) => (F.planos || []).find((p) => Math.round(p.janela) === j) || null, coordDe = (j) => (F.coordenacoes || []).find((q) => q.janela === j) || null;
  const modoTxt = (m) => (m.geradores || []).map((g) => `${(R.fc.find((r) => r.uid === g.uid) || {}).nome || g.uid} ${g.ligado ? "ligada" : "desligada"}${g.potencia_fixada_kW != null ? " a " + nf(g.potencia_fixada_kW, 1) + " kW" : ""}`).join(" · ") || "sem geradores";
  function tapetes() {
    const o = R.bat.map((r) => ({ id: "bat:" + r.uid, nome: `Energia planejada · ${r.nome} [kWh]`, cor: COR.bat, un: "kWh", get: (P) => P.series[`${r.uid}|e_fim`] ?? null, max: ((F.baterias[r.uid] || {}).resumo || {}).capacidade_kWh ?? null }));
    if (R.fc.length) o.push({ id: "fc", nome: "PEMFC planejada [kW]", cor: COR.fc, un: "kW", get: (P) => agg(R.fc.map((r) => P.series[`${r.uid}|p`] ?? null), (P.intervalo || []).length), max: null });
    if (M.conectado) o.push({ id: "imp", nome: "Importação programada [kW]", cor: COR.grid, un: "kW", get: (P) => P.series.pcc_importacao_programada_kW ?? null, max: F.pcc.limite_importacao_kW ?? null });
    return o;
  }
  function sinalVE(box, w, C) {
    const s = C && C.sinal, ui = uidDe("bat");
    if (!C) return box.replaceChildren(h("div", { class: "nd", html: "<b>N/D</b> — registro de coordenação desta janela não persistido (v2/coordenacoes.json)" }));
    if (!s) return box.replaceChildren(h("div", { class: "nd", html: `<b>N/D</b> — nenhum sinal de valor futuro foi produzido nesta decisão${C.motivo ? ": " + esc(C.motivo) : ""}` }));
    const modos = s.modos || [], q = s.qualidade || {}, valido = q.estado === "valido", dec = C.decomposicao || {};
    const aviso = valido ? null : h("div", { class: "nd", html: `<b>Sinal indisponível</b> — não foi usado nesta decisão. ${esc(q.motivo || "motivo não registrado")}. Os pontos avaliados pelo planejador aparecem só como registro.` });
    if (!modos.some((m) => (m.pontos || []).length)) return box.replaceChildren(...[aviso, h("div", { class: "nd", html: "<b>N/D</b> — o sinal não traz pontos V(E) gravados" })].filter(Boolean));
    if ((s.baterias || []).length !== 1) {                                                   // 2 bancos: sem projeção inventada; tabela dos pontos gravados
      const cab = (s.baterias || []).map((u) => `<th class=n>E ${esc((R.bat.find((r) => r.uid === u) || {}).nome || u)} [kWh]</th>`).join("");
      return box.replaceChildren(...[aviso, h("p", { class: "note", html: `Sinal com ${(s.baterias || []).length} bancos: V depende de mais de uma energia. Pontos gravados (sem projeção):` }), h("div", { class: "tabx", style: "max-height:210px", html: `<table><tr><th>modo</th>${cab}<th class=n>V [R$]</th></tr>${modos.flatMap((m) => (m.pontos || []).map((p) => `<tr><td>${m.indice}</td>${(p.energias_kWh || []).map((e) => `<td class=n>${nf(e, 2)}</td>`).join("")}<td class=n>${nf(p.valor_R, 4)}</td></tr>`)).join("")}</table>` })].filter(Boolean));
    }
    const pts = (m) => (m.pontos || []).filter((p) => p.valor_R != null && (p.energias_kWh || [])[0] != null).map((p) => [p.energias_kWh[0], p.valor_R, p]).sort((a, b) => a[0] - b[0]);
    const todos = modos.flatMap(pts), val = (q.validacoes || []).filter((v) => v.valor_reotimizado_R != null && (v.energias_kWh || [])[0] != null), inv = modos.flatMap((m) => (m.energias_inviaveis || []).map((e) => (Array.isArray(e) ? e[0] : e))).filter((e) => e != null);
    const xs = todos.map((p) => p[0]).concat(inv, modos.flatMap((m) => [(m.dominio_min_kWh || [])[0], (m.dominio_max_kWh || [])[0]]).filter((e) => e != null)), ys = todos.map((p) => p[1]).concat(val.map((v) => v.valor_reotimizado_R));
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(0, ...ys), y1 = Math.max(...ys), py = (y1 - y0) * .1 || 1, px = (x1 - x0) * .04 || 1;
    const eT = (dec.energias_fronteira_kWh || {})[s.baterias[0]], eR = ((s.referencia || {}).energias_kWh || [])[0], cor = valido ? COR.bat : "var(--ink-3)", ch = h("div", { style: "height:200px;position:relative" });
    box.replaceChildren(...[aviso, ch, h("p", { class: "note", html: `V [R$] = custo de continuação estimado a partir de ${lab(s.indice_fronteira)} em função da energia armazenada nessa fronteira${s.baterias[0] !== ui ? " (banco " + esc(s.baterias[0]) + ")" : ""}. ${modos.length} modo(s) terminal(is) · ${todos.length} pontos · ${val.length} validações${inv.length ? " · " + inv.length + " energia(s) inviável(is)" : ""}. Instrumento de decisão: não é custo realizado.` })].filter(Boolean));
    xy(ch, { exp: expMeta, h: 200, x: [x0 - px, x1 + px], y: [y0 - py, y1 + py], xl: "energia na fronteira [kWh]", yl: "V [R$]", label: "Sinal de valor futuro V(E)",
      near(xv) { let b = null; todos.forEach((p) => { if (!b || Math.abs(p[0] - xv) < Math.abs(b[0] - xv) || (Math.abs(p[0] - xv) === Math.abs(b[0] - xv) && p[2].__m === dec.modo)) b = p; }); return b && { x: b[0], y: b[1], html: `<b>E = ${nf(b[0], 2)} kWh · modo ${b[2].__m}</b><div><span>V (gravado)</span><span>${rs(b[1], 4)}</span></div><div><span>Limite inferior</span><span>${rs(b[2].limite_inferior_R, 4)}</span></div><div><span>Classificação</span><span>${esc(b[2].classificacao ?? "N/D")}</span></div>` }; },
      draw({ svg, X, Y, pt, H, pb }) {
        modos.forEach((m) => { const P = pts(m), sel = valido && dec.modo === m.indice; P.forEach((p) => { p[2].__m = m.indice; });
          const d0 = (m.dominio_min_kWh || [])[0], d1 = (m.dominio_max_kWh || [])[0]; if (sel && d0 != null && d1 != null) svg.append(sv("rect", { x: X(d0), y: H - pb - 4, width: Math.max(1, X(d1) - X(d0)), height: 4, style: `fill:${cor};opacity:.5` }));
          if (P.length) svg.append(sv("polyline", { points: P.map((p) => `${X(p[0])},${Y(p[1])}`).join(" "), fill: "none", style: `stroke:${cor};stroke-width:${sel ? 2.4 : 1.3};opacity:${sel || !valido ? 1 : .55}`, "stroke-dasharray": valido ? null : "4 3" }));
          P.forEach((p) => svg.append(sv("circle", { cx: X(p[0]), cy: Y(p[1]), r: sel ? 3.4 : 2.6, style: `fill:${sel ? cor : "var(--surface)"};stroke:${cor};stroke-width:1.4` })));
          if (P.length) svg.append(sv("text", { x: X(P[P.length - 1][0]) - 4, y: Y(P[P.length - 1][1]) - 6, "text-anchor": "end", class: "v" }, "modo " + m.indice)); });
        val.forEach((v) => { const cx = X(v.energias_kWh[0]), cy = Y(v.valor_reotimizado_R); svg.append(sv("path", { d: `M${cx - 3},${cy - 3}l6,6M${cx + 3},${cy - 3}l-6,6`, style: "stroke:var(--ink);stroke-width:1.2" })); });
        inv.forEach((e) => svg.append(sv("path", { d: `M${X(e) - 4},${H - pb - 9}l8,8M${X(e) + 4},${H - pb - 9}l-8,8`, style: "stroke:var(--bad);stroke-width:1.6" })));
        if (eR != null) svg.append(sv("line", { x1: X(eR), x2: X(eR), y1: pt, y2: H - pb, style: "stroke:var(--ink-3)", "stroke-dasharray": "5 4" }), sv("text", { x: X(eR) + 4, y: pt + 20, class: "v" }, "ref. plano longo"));
        if (eT != null) svg.append(sv("line", { x1: X(eT), x2: X(eT), y1: pt, y2: H - pb, style: "stroke:var(--ink);stroke-width:1.4" }), sv("text", { x: X(eT) + 4, y: pt + 9, class: "v", style: "fill:var(--ink);font-weight:600" }, "plano MPC: " + nf(eT, 1) + " kWh")); } });
  }
  // Raias da lente Decisão para a janela w (tapete com as janelas «filas»; energia planejada × executada; despacho planejado).
  // Partilhadas pela lente e pelo relatório PDF (UI-RESULTADOS-02): o mesmo desenho, sem cópia.
  const vaiJan = (q) => { if (!q) return; S.jan = q.j; S.band = null; salvar(); render(); };
  function decisaoLanes(w, tp, filas, o = {}) {
    const P = planoDe(w.j), C = coordDe(w.j), T = planoPorTipo(F, P), ui = uidDe("bat"), bat = F.baterias[ui] || null, n = T ? T.n : w.Nk, fimJ = w.k + n, vai = vaiJan;
    const E = bat ? bat.energia_kWh ?? null : undefined, cap = bat ? (bat.resumo || {}).capacidade_kWh ?? null : null, pl = C && C.plano_longo ? (C.plano_longo.energias_kWh || {})[ui] ?? null : null, sf = C && C.sinal ? C.sinal.indice_fronteira : null;
    const ei = P ? P.series[`${ui}|e_inicio`] ?? null : null, ef = P ? P.series[`${ui}|e_fim`] ?? null : null, planoE = ei && ef ? [ei[0], ...ef] : null, eRef = C && C.sinal && (C.sinal.baterias || []).includes(ui) ? ((C.sinal.referencia || {}).energias_kWh || [])[C.sinal.baterias.indexOf(ui)] : null;
    const inj = T ? [{ v: T.wt, c: COR.wt, k: "wt" }, { v: T.fv, c: COR.fv, k: "fv" }, { v: T.pd, c: COR.bat, k: "bat" }, { v: T.fc, c: COR.fc, k: "fc" }, { v: T.imp, c: COR.grid, k: "grid" }] : [];
    const totP = T ? Array.from({ length: n }, (_, i) => mais(...inj.map((s) => el(s.v, i)))) : [], hi = teto(maxv(totP, T ? T.dem : [], S.depois && A.demR ? A.demR.slice(w.k, fimJ) : [])), lo = teto(maxv(T ? T.pc : [], T ? T.exp : [])), temNeg = T && maxv(T.pc, T.exp) > 1e-6;
    const lanes = [
      o.tapete === false ? null : { title: tp ? `Tapete de decisões · ${tp.nome} · uma linha por janela` : "Tapete de decisões", h: Math.max(64, filas.length * 9 + 18), w: 2.2, note: "▁ aplicado · clique numa linha para selecionar a janela", draw(c) {
        if (!(F.planos || []).length || !tp) return c.nd("planos por janela não persistidos nesta rodada (v2/planos.csv)");
        const serie = filas.map((q) => { const Pq = planoDe(q.j); return Pq ? tp.get(Pq) : null; }), mx = tp.max || maxv(...serie.map((s) => s || [])) || 1, rh = Math.max(4, (c.bot - c.top - 16) / filas.length), ya = c.top + 16;
        filas.forEach((q, r) => { const Pq = planoDe(q.j), sr = serie[r], y = ya + r * rh, nq = Pq ? (Pq.intervalo || []).length : q.Nk;
          for (let i = 0; i < nq; i++) { const v = sr == null ? null : sr[i], e = c.add(sv("rect", { x: c.x(q.k + i) + .5, y: y + .5, width: Math.max(c.cw - 1, 1), height: Math.max(rh - 1, 1), rx: Math.min(2, rh / 3), style: `cursor:pointer;fill:${v == null ? "var(--field)" : `color-mix(in srgb, ${tp.cor} ${Math.round(8 + 92 * Math.min(1, Math.max(0, v / mx)))}%, var(--field-2))`}`, "stroke-dasharray": v == null ? "2 2" : null, stroke: v == null ? "var(--warn)" : null }));
            e.addEventListener("click", (ev) => { ev.stopPropagation(); setCur(Math.min(K - 1, q.k + i)); vai(q); });
            if (Pq && (Pq.aplicado || [])[i]) c.add(sv("rect", { x: c.x(q.k + i) + 1.5, y: y + rh - 2.2, width: Math.max(c.cw - 3, 1), height: 1.7, "pointer-events": "none", style: "fill:var(--ink)" })); }
          if (!o.semDestaque && q.j === w.j) c.add(sv("rect", { x: c.x(q.k) - 1, y: y - .5, width: nq * c.cw + 2, height: rh + 1, rx: 3, fill: "none", "pointer-events": "none", style: "stroke:var(--ink);stroke-width:1.6" }));
          if (rh >= 8) c.text(q.k, y + rh / 2 + 3.5, (q.ok ? "j" : "j") + q.j + (q.ok ? "" : " ∅"), { dx: -4, "text-anchor": "end", class: "v", "pointer-events": "none", style: !o.semDestaque && q.j === w.j ? "fill:var(--ink);font-weight:700" : null }); }); } },
      E !== undefined ? { title: `Energia de ${esc((recDe("bat") || {}).nome || "bateria")} nas fronteiras [kWh] · conhecido em ${lab(w.k)} × plano × o que ocorreu depois`, h: 96, w: 2.6, draw(c) {
        const mx = cap > 0 ? Math.max(cap, maxv(E, planoE, pl)) : teto(maxv(E, planoE, pl)), y = c.sc(0, mx * 1.08); c.grid(y, tk(mx), fd(mx));
        if (pl) c.front(pl, y, { c: "var(--ink-3)", w: 1.4, dash: "6 4", dots: false }, C.plano_longo.k);
        if (E === null) c.nd("energia executada da bateria não persistida"); else { c.front(E.slice(0, w.k + 1), y, { r: 2.6, k: "bat" }); if (S.depois) c.front(E.slice(w.k), y, { r: 2, op: .5, dash: "2 3", k: "bat" }, w.k); }
        if (planoE) c.front(planoE, y, { c: "var(--ink)", hollow: true, r: 3, w: 1.8 }, w.k); else c.nd("plano de energia desta janela não persistido");
        if (sf != null) { c.add(sv("line", { x1: c.x(sf), x2: c.x(sf), y1: c.top + 14, y2: c.bot, style: "stroke:var(--ink-2)", "stroke-dasharray": "3 3" })); c.text(sf, c.top + 24, "fronteira do sinal", { dx: -4, "text-anchor": "end", class: "v" });
          if (eRef != null) c.add(sv("path", { d: `M${c.x(sf)},${y(eRef) - 5}l5,5l-5,5l-5,-5z`, style: "fill:var(--surface);stroke:var(--ink-2);stroke-width:1.4" })); } } } : null,
      { title: `Despacho planejado na janela ${w.j} [kW] · cheio = aplicado · claro = planejado e depois revisto`, h: 100, w: 2.6, draw(c) {
        if (!T) return c.nd("plano desta janela não persistido (v2/planos.csv)");
        const y = c.sc(temNeg ? -lo * 1.15 : 0, hi), op = (i) => (T.aplicado[i] ? 1 : .4); c.grid(y, temNeg ? [-lo, 0, hi / 2, hi] : tk(hi), fd(hi));
        c.stack(inj, y, { n, b0: w.k, op }); c.stack([{ v: T.pc, hatch: "bat", k: "bat" }, { v: T.exp, hatch: "grid", k: "grid" }], y, { neg: true, n, b0: w.k, op });
        c.step(T.dem, y, { b0: w.k, w: 1.8, c: "var(--ink)", dash: "5 3", k: "dem" }); if (S.depois) c.step(A.demR == null ? A.demR : A.demR.slice(w.k, fimJ), y, { b0: w.k, w: 2.2, k: "dem" }); } }].filter(Boolean);
    return { lanes, E, planoE, pl, C, T, n, fimJ };
  }
  function lDecisao() {
    const host = h("div", { class: "host" }), col = h("div", { class: "col" }), w = janSel(), TP = tapetes(), tp = TP.find((t) => t.id === S.tap) || TP[0] || null;
    if (!w) return h("div", { class: "stage" }, painel("Decisões do MPC", h("div", { class: "nd", html: "<b>N/D</b> — nenhuma janela de decisão persistida nesta rodada (v2/janelas.csv)" })), col);
    const P = planoDe(w.j), C = coordDe(w.j), T = planoPorTipo(F, P), ui = uidDe("bat"), bat = F.baterias[ui] || null, n = T ? T.n : w.Nk, fimJ = w.k + n, idx = M.jan.indexOf(w);
    const vai = vaiJan, veCaixa = h("div", {}), dec = (C && C.decomposicao) || {};
    const emJ = (g) => g >= w.k && g < fimJ, pj = (a, g) => (a == null ? a : a[g - w.k] ?? null);
    const exec = { wt: A.wtP, fv: A.fvP, pd: A.pd, pc: A.pc, fc: A.fcP, imp: A.impR, exp: A.expR, dem: A.demR };
    const linhas = [["wt", "Eólica", "wt"], ["fv", "Solar", "fv"], ["pd", "Bateria · descarga", "bat"], ["pc", "Bateria · carga", "bat"], ["fc", "PEMFC", "fc"], ["imp", "Importação", "grid"], ["exp", "Exportação", "grid"], ["dem", "Demanda", "dem"]];
    const depois = (v, d = 1) => (S.depois ? nf(v, d) : "oculto");
    const cards = (g) => { const dentro = emJ(g), ap = dentro && T ? T.aplicado[g - w.k] : null, wg = janDe(g);
      return [
        card({ acc: "var(--ink)", t: `Decisão · janela ${w.j}`, tag: w.ok ? "com valor futuro" : "sem valor futuro", tc: w.ok ? "ok" : "w", big: `${lab(w.k)}<small>instante da decisão τ</small>`, sub: `horizonte ${ivl(w.k).split("–")[0]}–${lab(Math.min(K, fimJ))} (${n} intervalos) · aplicou ${w.ap} de ${w.mk} previstos`,
          grid: [["Solver", esc(w.classe ?? "N/D")], ["Gap relativo", ne(w.gap_rel, 1)], ["Objetivo do MILP", rs(w.objetivo)], ["Custo operativo previsto", rs(w.custo_operativo_previsto)], ["Custo futuro estimado", w.custo_futuro_estimado == null ? "N/D" : rs(w.custo_futuro_estimado)], ["Termo terminal", esc(String(w.termo_terminal ?? "N/D").replace(/_/g, " "))]],
          note: w.ok ? null : "Sem sinal válido, esta decisão foi tomada <b>sem valor futuro</b> (degradação declarada): " + esc(w.sinal_motivo || "motivo não registrado") + "." }),
        card({ t: `Valor futuro · fronteira ${C && C.sinal ? lab(C.sinal.indice_fronteira) : "N/D"}`, tag: C && C.sinal ? esc(((C.sinal.qualidade || {}).estado || "N/D").replace("valido", "válido").replace("indisponivel", "indisponível")) : "N/D", tc: w.ok ? "ok" : "w", el: veCaixa }),
        C && C.sinal ? card({ t: "Qualidade do sinal", kv: [["Origem", esc(String(C.origem_sinal ?? "N/D").replace(/_/g, " "))], ["Erro de interpolação máx.", rs((C.sinal.qualidade || {}).erro_interpolacao_max_R, 6)], ["Tolerância declarada", rs((C.sinal.qualidade || {}).tolerancia_interpolacao_R, 6)], ["Avaliações do planejador", String((C.sinal.qualidade || {}).avaliacoes ?? "N/D")], dec.modo != null ? ["Modo terminal escolhido", `${dec.modo} · ${esc(modoTxt((C.sinal.modos || []).find((m) => m.indice === dec.modo) || {}))}`] : null] }) : null,
        card({ t: `Instante ${ivl(g)} nesta decisão`, tag: !dentro ? "fora do horizonte" : ap ? "aplicado" : "planejado, depois revisto", tc: ap ? "ok" : "", sub: dentro ? `posição ${g - w.k + 1} de ${n} no plano · ${ap ? "o MPC executou este intervalo com esta decisão" : "decidido de novo numa janela posterior"}` : `a janela ${w.j} não planeja este intervalo` + (wg ? ` · quem o decidiu foi a janela ${wg.j}` : ""),
          el: dentro && T ? h("table", { style: "margin-top:8px", html: `<tr><th>kW</th><th class=n>planejado em ${lab(w.k)}</th><th class=n>executado</th></tr>` + linhas.filter(([q]) => T[q] !== undefined || exec[q] !== undefined).map(([q, t, cr]) => `<tr><td><i style="display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px;background:${COR[cr]}"></i>${t}${q === "dem" ? " (prevista × realizada)" : ""}</td><td class="n">${nfu(pj(T[q], g), 1)}</td><td class="n dim3">${exec[q] === undefined ? "—" : depois(el(exec[q], g))}</td></tr>`).join("") }) : !dentro && wg ? h("button", { class: "pill", style: "margin-top:10px", onclick: () => vai(wg) }, `Ver a janela ${wg.j}`) : dentro ? h("div", { class: "nd", html: "<b>N/D</b> — plano desta janela não persistido (v2/planos.csv)" }) : null,
          note: dentro ? (S.depois ? "«Executado» é posterior à decisão: o controlador não o conhecia em " + lab(w.k) + "." : "Execução oculta: a vista mostra só o que era conhecido em " + lab(w.k) + ".") : null }),
        card({ t: "Bloco aplicado · previsto × realizado", tag: "R$", grid: [["Previsto para o bloco", rs(w.planejado_prefixo)], ["Realizado no bloco", S.depois ? rs(w.realizado) : "oculto"], ["Diferença (derivado)", S.depois ? rs(menos(w.realizado, w.planejado_prefixo)) : "oculto"], ["Plano longo · objetivo", rs(((C || {}).plano_longo || {}).objetivo_R)]],
          note: "São grandezas diferentes: o custo previsto do bloco e o objetivo do MILP são <b>previsões</b> da decisão; o custo realizado é liquidado depois. O objetivo cobre os " + n + " intervalos da janela e não se soma entre janelas." })];
    };
    const paint = (g) => col.replaceChildren(...cards(g).filter(Boolean)); paint(S.cur); HOOKS.push(paint); setTimeout(() => sinalVE(veCaixa, w, C));
    const filas = M.jan.length > 36 ? M.jan.slice(Math.max(0, Math.min(M.jan.length - 36, idx - 18)), Math.max(0, Math.min(M.jan.length - 36, idx - 18)) + 36) : M.jan;
    const { lanes, E, planoE, pl } = decisaoLanes(w, tp, filas);
    setTimeout(() => trama(host, opts({ lanes, band: [w.k, Math.min(K, fimJ)], label: "Decisões do MPC", onRes: null,
      tip: tip((g) => [["Janela selecionada", `j${w.j} · ${emJ(g) ? "posição " + (g - w.k + 1) + " de " + n : "fora do horizonte"}`], emJ(g) && T ? ["Demanda prevista", nf(pj(T.dem, g), 1) + " kW"] : null, emJ(g) && S.depois ? ["Demanda realizada", nf(el(A.demR, g), 1) + " kW"] : null, emJ(g) && planoE ? ["Energia planejada (fim)", nf(planoE[g - w.k + 1], 1) + " kWh"] : null, E && (S.depois || g < w.k) ? ["Energia executada (fim)", nf(E[g + 1], 1) + " kWh"] : null, pl && g + 1 >= C.plano_longo.k && g + 1 <= C.plano_longo.indice_fim ? ["Plano longo (fim)", nf(pl[g + 1 - C.plano_longo.k], 1) + " kWh"] : null]) })));
    const sel = h("select", { class: "sel", "aria-label": "Janela de decisão", onchange: (e) => vai(porJ.get(+e.target.value)) }, ...M.jan.map((q) => h("option", { value: q.j, selected: q.j === w.j }, `janela ${q.j} · ${lab(q.k)} · ${q.ok ? "com valor futuro" : "sem valor futuro"}`)));
    const lg = (html) => h("span", { class: "leg", html });
    return h("div", { class: "stage wide" }, h("div", { class: "panel acc", style: "--acc:var(--ink-3)" },
      h("div", { class: "chead" }, h("button", { class: "tool", title: "Janela anterior", "aria-label": "Janela anterior", disabled: idx <= 0 ? "" : null, onclick: () => vai(M.jan[idx - 1]), html: ico("M15 6l-6 6 6 6") }), sel, h("button", { class: "tool", title: "Janela seguinte", "aria-label": "Janela seguinte", disabled: idx >= M.jan.length - 1 ? "" : null, onclick: () => vai(M.jan[idx + 1]), html: ico("M9 6l6 6-6 6") }),
        h("button", { class: "pill", title: "Selecionar a janela que decidiu o instante do cursor", onclick: () => vai(janDe(S.cur)) }, "Janela do instante"),
        TP.length > 1 ? h("select", { class: "sel", "aria-label": "Grandeza do tapete", onchange: (e) => { S.tap = e.target.value; if (S.tap.startsWith("bat:")) S.uid.bat = S.tap.slice(4); salvar(); render(); } }, ...TP.map((t) => h("option", { value: t.id, selected: tp && t.id === tp.id }, t.nome))) : null,
        h("span", { class: "grow" }), h("button", { class: "pill" + (S.depois ? " on" : ""), "aria-pressed": String(!!S.depois), title: "Mostrar ou ocultar o que só ocorreu depois da decisão", onclick: () => { S.depois = !S.depois; salvar(); render(); } }, S.depois ? "Mostrando o que ocorreu depois" : "Só o que se sabia na decisão"), zoomSeg()),
      h("div", { class: "chead" }, lg(`<i style="background:${COR.bat};border-radius:50%"></i>executado até ${lab(w.k)}`), S.depois ? lg(`<i class="ln" style="background:${COR.bat};opacity:.5"></i>executado depois`) : null, lg(`<i style="background:none;box-shadow:inset 0 0 0 2px var(--ink);border-radius:50%"></i>plano MPC da janela`), lg(`<i class="ln" style="background:var(--ink-3)"></i>plano de longo prazo`), lg(`<i class="ln" style="background:var(--ink)"></i>demanda prevista (tracejada) ${S.depois ? "× realizada" : ""}`)), host), col);
  }

  // ---------------------------------------------------------------- lente Economia
  // Três grandezas que nunca se confundem: custo operacional REALIZADO (liquidado), objetivo do MILP (previsão de uma janela)
  // e valor futuro estimado (instrumento de decisão). Somas apresentadas são rotuladas como derivadas.
  // Raias da lente Economia (partilhadas com o relatório PDF).
  function lanesEconomia() {
    const tot = A.cAcc ? [0, ...A.cAcc] : null, mI = teto(maxv(A.cInt)), mT = teto(maxv(tot)), mO = teto(maxv(M.jan.map((q) => q.objetivo))), mB = teto(maxv(M.jan.map((q) => q.planejado_prefixo), M.jan.map((q) => q.realizado)));
    const lanes = [
      M.conectado ? laneTarifa({ res: "grid", h: 46, w: 1 }) : null,
      { title: "Custo operacional REALIZADO por intervalo [R$] · por componente", res: "eco", h: 78, w: 2.2, draw(x) { if (A.cInt == null) x.nd("custo realizado por intervalo não persistido"); const y = x.sc(0, mI); x.grid(y, tk(mI), fd(mI)); x.stack(compCusto(), y); } },
      { title: "Custo operacional realizado ACUMULADO [R$] · valor gravado", h: 70, w: 1.8, note: "total " + rs(F.resumo.custo_realizado_total_R), draw(x) { if (!tot) return x.nd("custo acumulado não persistido"); const y = x.sc(0, mT); x.grid(y, tk(mT), fd(mT)); x.front(tot, y, { c: "var(--ink)", r: 2.2 }); } },
      { title: "Bloco aplicado de cada decisão [R$] · contorno = previsto na decisão · cheio = realizado", h: 70, w: 1.8, draw(x) { const y = x.sc(0, mB * 1.12); x.grid(y, tk(mB), fd(mB)); M.jan.forEach((q) => { if (!q.ap) return; const x0 = x.x(q.k) + 2, lw = q.ap * x.cw - 4;
        if (q.realizado != null) x.add(sv("rect", { x: x0, y: y(q.realizado), width: lw, height: Math.max(1, y(0) - y(q.realizado)), rx: 3, style: "fill:var(--s-eco)" }));
        if (q.planejado_prefixo != null) x.add(sv("rect", { x: x0, y: y(q.planejado_prefixo), width: lw, height: Math.max(1, y(0) - y(q.planejado_prefixo)), rx: 3, fill: "none", style: "stroke:var(--ink);stroke-width:1.3", "stroke-dasharray": "4 3" }));
        if (q.realizado == null || q.planejado_prefixo == null) x.text(q.k + q.ap / 2, x.bot - 6, "N/D", { "text-anchor": "middle", class: "v nd" }); }); } },
      laneObjetivo(mO)].filter(Boolean);
    return lanes;
  }
  const cardTres = (sPrev, sReal, nOk) => card({ t: "Três grandezas que não se somam", kv: [["Custo operacional realizado (missão)", rs(F.resumo.custo_realizado_total_R)], ["Σ realizado dos blocos aplicados (derivado)", rs(sReal)], ["Σ previsto para os blocos aplicados (derivado)", rs(sPrev)], ["Realizado − previsto (derivado)", rs(menos(sReal, sPrev))], ["Decisões com valor futuro", `${nOk} de ${M.jan.length}`]],
        note: "O <b>custo realizado</b> é o aplicado × realização, liquidado pela tarifa declarada. O <b>objetivo do MILP</b> é a previsão de uma janela de N intervalos (as janelas se sobrepõem). O <b>valor futuro</b> é um instrumento do planejador: nunca entra no custo realizado. A interface não soma objetivos nem valores futuros." });
  function lEconomia() {
    const host = h("div", { class: "host" }), col = h("div", { class: "col" }), cp = F.resumo.componentes_R || {}, w = (i) => janDe(i) || {}, temRec = maxv(A.rec) > 1e-9;
    const sPrev = somaT(M.jan.map((q) => q.planejado_prefixo ?? null)), sReal = somaT(M.jan.map((q) => q.realizado ?? null)), nOk = M.jan.filter((q) => q.ok).length;
    const comp = (i) => [M.conectado ? ["Importação da rede", el(A.cImp, i)] : null, A.cH2 !== undefined ? ["Hidrogênio (PEMFC)", el(A.cH2, i)] : null, A.cEv !== undefined ? ["Partidas e paradas", el(A.cEv, i)] : null, A.cThr !== undefined ? ["Throughput da bateria", el(A.cThr, i)] : null, A.cDes !== undefined ? ["Desvio no PCC", el(A.cDes, i)] : null, M.conectado && temRec ? ["Receita de exportação", vezes(el(A.rec, i), -1)] : null].filter(Boolean);
    const cards = (i) => [cardCusto(i, cp),
      card({ t: `Intervalo ${ivl(i)}`, tag: "realizado", big: rs(el(A.cInt, i)), sub: `acumulado até ${lab(i + 1)}: ${rs(el(A.cAcc, i))}` + (M.conectado ? ` · tarifa de decisão ${nf(el(A.tar, i), 2)} R$/kWh` : ""), kv: comp(i).map(([t, v]) => [t, rs(v)]) }),
      card({ t: `Decisão que aplicou este intervalo · janela ${w(i).j ?? "N/D"}`, tag: w(i).ok ? "com valor futuro" : "sem valor futuro", tc: w(i).ok ? "ok" : "w", grid: [["Objetivo do MILP", rs(w(i).objetivo)], ["Custo operativo previsto", rs(w(i).custo_operativo_previsto)], ["Custo futuro estimado", w(i).custo_futuro_estimado == null ? "N/D" : rs(w(i).custo_futuro_estimado)], ["Bloco: previsto → realizado", `${rs(w(i).planejado_prefixo)} → ${rs(w(i).realizado)}`]], el: w(i).j != null ? h("button", { class: "pill", style: "margin-top:10px", onclick: () => irLente("decisao", w(i).j) }, "Ver esta decisão") : null }),
      cardTres(sPrev, sReal, nOk)];
    const paint = (i) => col.replaceChildren(...cards(i).filter(Boolean)); paint(S.cur); HOOKS.push(paint);
    const lanes = lanesEconomia();
    setTimeout(() => trama(host, opts({ lanes, label: "Economia da missão", tip: tip((i) => [["Custo realizado no intervalo", rs(el(A.cInt, i))], ...comp(i).map(([t, v]) => [t, rs(v)]), ["Acumulado", rs(el(A.cAcc, i))], ...tipTar(i), ["Objetivo MILP · janela " + (w(i).j ?? "N/D"), rs(w(i).objetivo)]]) })));
    return h("div", { class: "stage" }, h("div", { class: "panel acc", style: "--acc:var(--ink-3)" },
      h("div", { class: "chead" }, ...legCusto().map(legEl), ...legTar().filter(Boolean).map(legEl), h("span", { class: "grow" }), zoomSeg()), host), col);
  }

  // ---------------------------------------------------------------- lente Evidência
  // Só EXIBE o que o servidor verificou e o que a rodada gravou: o navegador não refaz auditorias nem verificações.
  function lEvidencia() {
    const ver = F.verificacao, ac = F.aceitacao || {}, au = F.auditoria, pr = F.procedencia || {}, sol = F.resumo.solver || {}, r = F.rodada;
    const marca = (ok) => (ok == null ? `<span class="tag w">N/D</span>` : ok ? `<span class="tag ok">✓</span>` : `<span class="tag b">✕</span>`), curto = (s, n = 16) => (s == null ? "N/D" : esc(String(s).slice(0, n)) + (String(s).length > n ? "…" : ""));
    const kv = (rows) => h("div", { class: "kv ev", html: kvh(rows) }), txt = (v) => esc(v == null ? "N/D" : String(v).replace(/_/g, " "));
    const acRow = (nome, a, cls) => (a ? `<tr><td><b>${nome}</b></td><td><span class="tag ${cls}">${esc(ESTADOS[a.estado] || a.estado || "N/D")}</span></td><td class="dim3">${esc(a.criterio || "")}${a.motivo ? " — " + esc(a.motivo) : ""}</td></tr>` : `<tr><td><b>${nome}</b></td><td><span class="tag w">N/D</span></td><td class="dim3">estado não gravado nesta rodada</td></tr>`);
    const tabs = Object.keys(F.tabelas || {}), tn = tabs.includes(S.tabela) ? S.tabela : tabs[0], tb = tn ? F.tabelas[tn] : null, LIM = 200;
    const cel = (v) => (v == null ? `<td class="dim3">N/D</td>` : `<td${typeof v === "number" ? " class=n" : ""}>${esc(v)}</td>`);
    const grupos = agruparAvisos(F.avisos || []);
    const classica = () => { try { const s = [...document.querySelectorAll('[data-testid="stExpander"] summary')].find((x) => /Vista clássica/.test(x.textContent)); if (!s) return; if (!s.parentElement.open) s.click(); s.scrollIntoView({ block: "start", behavior: "smooth" }); } catch (_) { /* página sem a vista clássica */ } };
    return h("div", { class: "rolar" }, h("div", { class: "g2" },
      painel("Estado e integridade da rodada", h("div", { class: "card", style: "padding:0" }, h("div", { class: "big", html: ver == null ? "N/D" : ver.ok ? "Evidência verificada" : "EVIDÊNCIA COM PROBLEMAS" }), h("div", { class: "sub", html: ver == null ? "a verificação do servidor não acompanha este marco" : `${ver.itens.filter((x) => x[0]).length} de ${ver.itens.length} verificações aprovadas pelo servidor ao abrir a rodada (hashes, vistas regeneradas e reauditoria independente; sem solver)` })),
        kv([["Rodada", esc(r.uid)], ["Estado", txt(r.estado) + " · somente leitura"], ["Missão completa", F.resumo.missao_completa == null ? "N/D" : F.resumo.missao_completa ? "sim" : "não"], ["Criada · finalizada (UTC)", `${esc(r.criada ?? "N/D")} · ${esc(r.finalizada ?? "N/D")}`], ["Contexto", txt(r.contexto) + (r.sintetico ? " · dados sintéticos" : "")], ["Contrato de dados", "v" + (r.versao_dados ?? "N/D")]]),
        ver ? h("details", {}, h("summary", { html: `Verificações do servidor <b>${ver.itens.length}</b>` }), h("div", { class: "tabx", html: `<table>${ver.itens.map(([ok, t]) => `<tr><td>${marca(ok)}</td><td style="white-space:normal">${esc(t)}</td></tr>`).join("")}</table>` })) : null,
        h("p", { class: "note", html: "A verificação é feita pelo servidor (<code>registro.verificar</code>) a cada abertura. O navegador apenas a exibe: não a substitui nem a repete." })),
      painel("Aceitação · três estados separados", h("table", { html: `<tr><th>Nível</th><th>Estado</th><th>Critério</th></tr>${acRow("Algébrica", ac.algebrica, ac.algebrica && ac.algebrica.estado === "aprovada" ? "ok" : "b")}${acRow("Dinâmica", ac.dinamica, ac.dinamica && ac.dinamica.estado === "coerente" ? "ok" : ac.dinamica && ac.dinamica.estado === "incoerente" ? "b" : "w")}${acRow("Física", ac.fisica, "w")}` }),
        h("p", { class: "lead", style: "margin-top:8px", html: esc(ac.rotulo || "") }), h("p", { class: "note", html: "Aprovação algébrica e coerência dinâmica referem-se a <b>modelos</b>. Nenhuma delas é validação física: nenhum equipamento real foi ensaiado." })),
      painel("Auditoria independente da missão", au ? h("div", {}, h("div", { class: "card", style: "padding:0" }, h("div", { class: "big", html: au.aceito == null ? "N/D" : au.aceito ? "Aceita" : "REJEITADA" }), h("div", { class: "sub", html: esc(au.metodo || "método não registrado") })),
        h("table", { style: "margin-top:8px", html: `<tr><th>Verificação gravada</th><th class=n>Resultado</th></tr>${Object.entries(au.verificacoes || {}).map(([q, ok]) => `<tr><td>${txt(q)}</td><td class=n>${marca(ok)}</td></tr>`).join("")}` }),
        kv([["Constatações", String(au.constatacoes ?? "N/D") + (au.constatacoes_por_severidade ? " (" + Object.entries(au.constatacoes_por_severidade).map(([q, n]) => `${n} ${esc(q)}`).join(" · ") + ")" : "")], ["Normalizações numéricas do PCC", String(au.normalizacoes_pcc ?? "N/D")], ["Projeções numéricas de energia", String(au.projecoes_numericas_energia ?? "N/D")], ["Tolerâncias", esc(au.tolerancias ?? "N/D")]])) : h("div", { class: "nd", html: "<b>N/D</b> — v2/auditoria.json não persistido nesta rodada" })),
      painel2("Solver e critérios por decisão", kv([["Janelas resolvidas · ótimas", `${sol.janelas_resolvidas ?? "N/D"} · ${sol.janelas_otimas ?? "N/D"}`], ["Gap relativo máximo", ne(sol.gap_rel_max, 2)], ["Solver", esc([pr.software && pr.software.pyomo ? "Pyomo " + pr.software.pyomo : null, pr.software && pr.software.highs ? "HiGHS " + pr.software.highs : null].filter(Boolean).join(" · ") || "N/D")]]),
        h("div", { class: "tabx", style: "margin-top:8px", html: `<table><tr><th>j</th><th>τ</th><th class=n>N</th><th class=n>aplic.</th><th>classe</th><th>terminação</th><th class=n>objetivo [R$]</th><th class=n>limite dual [R$]</th><th class=n>gap rel.</th><th class=n>var.</th><th class=n>bin.</th><th class=n>restr.</th><th>valor futuro</th></tr>${M.jan.map((q) => `<tr data-j="${q.j}" style="cursor:pointer"><td>${q.j}</td><td>${lab(q.k)}</td><td class=n>${q.Nk}</td><td class=n>${q.ap}</td><td>${txt(q.classe)}</td><td>${txt(q.terminacao)}</td><td class=n>${nf(q.objetivo, 4)}</td><td class=n>${nf(q.limite_dual, 4)}</td><td class=n>${ne(q.gap_rel, 1)}</td><td class=n>${nf(q.variaveis, 0)}</td><td class=n>${nf(q.binarias, 0)}</td><td class=n>${nf(q.restricoes, 0)}</td><td>${q.ok ? '<span class="tag ok">válido</span>' : '<span class="tag w">indisponível</span>'}</td></tr>`).join("")}</table>`, onclick: (e) => { const tr = e.target.closest("tr[data-j]"); if (tr) irLente("decisao", +tr.dataset.j); } }),
        h("p", { class: "note", html: "Clique numa linha para abrir a decisão. Objetivo e limite dual são do MILP de cada janela (previsão), não custo realizado." })),
      painel("Procedência e versões", kv([["Microrrede (UID · incarnação)", `${curto(pr.microrrede_uid, 12)} · ${curto(pr.incarnacao, 12)}`], ["Cenário (UID · versão)", `${curto(pr.cenario_uid, 12)} · v${pr.cenario_versao ?? "N/D"}`], ["Impressão do cenário", curto(pr.cenario_impressao)], ["Inventário (revisão · impressão)", `rev. ${pr.inventario_revisao ?? "N/D"} · ${curto(pr.inventario_impressao)}`], ["Motor", esc(pr.motor ?? "N/D")], ["Formulações", esc(Object.entries(pr.formulacoes || {}).map(([q, v]) => `${q} ${v}`).join(" · ") || "N/D")], ["Integração · contrato de dados", `${esc(pr.integracao ?? "N/D")} · v${pr.contrato_dados ?? "N/D"}`], ["Software", esc(Object.entries(pr.software || {}).map(([q, v]) => `${q} ${v}`).join(" · ") || "N/D")], ["Código científico (SHA-256)", curto(pr.codigo_cientifico_sha256)], ["Declarante", esc(pr.declarante ?? "N/D")]]),
        h("p", { class: "note", html: esc(pr.rotulo_motor || "") }), pr.alcance ? h("p", { class: "note", html: esc(pr.alcance) }) : null),
      painel("Arquivos da evidência", h("div", { class: "tabx", html: `<table><tr><th>Arquivo</th><th>SHA-256</th><th class=n>bytes</th></tr>${(F.arquivos || []).map(([n, s, b]) => `<tr><td>${esc(n)}</td><td title="${esc(s ?? "")}"><code>${curto(s, 20)}</code></td><td class=n>${nf(b, 0)}</td></tr>`).join("")}</table>` }),
        h("p", { class: "note", html: "Arquivos gravados com a rodada (identificados pelo SHA-256 do conteúdo). As descargas, as tabelas completas e a exportação do estudo ficam na vista clássica." }), h("button", { class: "pill", style: "margin-top:8px", onclick: classica }, "Abrir a vista clássica (tabelas, descargas e exportações)")),
      h("div", { class: "panel", style: "grid-column:1/-1" }, h("div", { class: "chead" }, h("span", { class: "ttl" }, "Tabelas originais gravadas"), h("span", { class: "grow" }), tabs.length ? h("div", { class: "seg", role: "group", "aria-label": "Tabela" }, ...tabs.map((t) => h("button", { "aria-pressed": String(t === tn), onclick: () => { S.tabela = t; salvar(); render(); } }, t.replace("v2/", "")))) : null),
        tb ? h("div", {}, h("div", { class: "tabx", html: `<table><tr>${tb.colunas.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>${tb.linhas.slice(0, LIM).map((l) => `<tr>${l.map(cel).join("")}</tr>`).join("")}</table>` }), h("p", { class: "note", html: `${esc(tn)} · ${tb.linhas.length} linhas × ${tb.colunas.length} colunas, valores como gravados (sem arredondamento)${tb.linhas.length > LIM ? ` · mostrando as primeiras ${LIM}; a tabela completa está na vista clássica` : ""}. Célula vazia no arquivo = N/D.` })) : h("div", { class: "nd", html: "<b>N/D</b> — tabelas não incluídas neste marco" })),
      painel(`Advertências registradas · ${(F.avisos || []).length}`, grupos.length ? h("div", {}, ...grupos.map(([t, l]) => h("details", {}, h("summary", { html: `${esc(t)} <b>${l.length}</b>` }), h("ul", { class: "lead", style: "margin:6px 0 0 18px", html: l.map((a) => `<li>${esc(a)}</li>`).join("") })))) : h("p", { class: "lead" }, "Nenhuma advertência registrada nesta rodada.")),
      painel("Limitações científicas e convenções", h("ul", { class: "lead", style: "margin-left:18px", html: (F.limitacoes || []).map((a) => `<li>${esc(a)}</li>`).join("") || "<li>N/D — limitações não registradas neste marco</li>" }), h("details", {}, h("summary", { html: `Convenções de leitura <b>${Object.keys(F.convencoes || {}).length}</b>` }), kv(Object.entries(F.convencoes || {}).map(([q, v]) => [esc(q), esc(v)]))))));
  }

  // ---------------------------------------------------------------- lente Visão Geral (UI-RESULTADOS-02, melhoria 04)
  // Síntese energética, econômica e operacional da missão. Valores do resumo SELADO quando existem; o que é calculado aqui é
  // marcado «derivado». A descarga da bateria nunca aparece como geração primária: vem sempre com a energia carregada.
  const ORIG = { selado: "selado", derivado: "derivado", declarado: "declarado", servidor: "servidor" };
  const vgFmt = (x, d = 1, u = "") => (x.v === undefined ? "—" : nfu(x.v, d, u));
  const kpiEl = (q) => h("div", { class: "kpi" + (q.acc ? " acc" : ""), style: q.acc ? `--acc:${q.acc}` : null, "data-kpi": q.id },
    h("div", { class: "k-l", html: `${esc(q.t)}${q.o ? `<span class="tag ${q.o === "derivado" ? "i" : ""}">${ORIG[q.o] || esc(q.o)}</span>` : ""}` }),
    h("div", { class: "k-v", html: `${q.big}${q.u ? `<small>${q.u}</small>` : ""}` }), q.sub ? h("div", { class: "k-s", html: q.sub }) : null);
  function kpisVisao(VG) {
    const v = VG.v, R = F.recursos;
    return [
      { id: "dem", t: "Energia demandada", big: vgFmt(v.dem, 1), u: "kWh", o: v.dem.o, acc: COR.dem },
      { id: "at", t: "Energia atendida", big: vgFmt(v.at, 1), u: "kWh", o: v.at.o, sub: `${vgFmt(v.cobertura, 1, " %")} da demanda <span class="dim3">(derivado)</span>` },
      { id: "ens", t: "Energia não atendida", big: vgFmt(v.ens, 2), u: "kWh", o: v.ens.o, acc: v.ens.v > 1e-9 ? "var(--bad)" : null },
      { id: "custo", t: "Custo realizado", big: v.custo.v == null ? "N/D" : "R$ " + nf(v.custo.v, 2), o: v.custo.o, sub: "liquidado · sem valor futuro" },
      { id: "custokwh", t: "Custo médio por kWh atendido", big: v.custoKwh.v == null ? "N/D" : v.custoKwh.v === undefined ? "—" : "R$ " + nf(v.custoKwh.v, 3), u: "/kWh", o: "derivado", sub: "custo realizado ÷ energia atendida" },
      v.ren.v !== undefined ? { id: "ren", t: "Renovável aproveitada", big: vgFmt(v.ren, 1), u: "kWh", o: v.ren.o, acc: R.fv.length ? COR.fv : COR.wt, sub: `vertida ${vgFmt(v.vert, 1, " kWh")}` } : null,
      M.conectado ? { id: "pcc", t: "Rede · importada | exportada", big: `${vgFmt(v.imp, 1)} <span class="dim3">|</span> ${vgFmt(v.exp, 1)}`, u: "kWh", o: v.imp.o, acc: COR.grid } : null].filter(Boolean);
  }
  // Energia por fonte: barras horizontais por tecnologia (cheia = injeta; hachura = vertida / exportada / carregada)
  function barrasFontes(VG, W = 560) {
    const linhas = VG.fontes.flatMap(([k, n, it]) => it.map(([t, x, ht], j) => ({ k, n: j ? "" : n, t, v: x.v, ht: !!ht })));
    const rowH = 23, lw = 168, vw = 92, bw = Math.max(60, W - lw - vw - 8), gap = VG.fontes.length * 6, H = linhas.length * rowH + gap + 6;
    const svg = sv("svg", { class: "trama", width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Energia por fonte" });
    const mx = teto(maxv(linhas.map((l) => (l.v == null ? 0 : Math.abs(l.v))))); let y = 2, ult = null;
    linhas.forEach((l) => { if (l.k !== ult) { y += ult ? 6 : 0; ult = l.k; }
      if (l.n) svg.append(sv("circle", { cx: 6, cy: y + 11.5, r: 4.5, style: `fill:${COR[l.k]}` }), sv("text", { x: 16, y: y + 15, style: "font-weight:600" }, l.n));
      svg.append(sv("text", { x: lw - 6, y: y + 15, "text-anchor": "end" }, l.t));
      if (l.v == null) svg.append(sv("text", { x: lw + 4, y: y + 15, class: "v nd" }, "N/D"));
      else { const wd = Math.max(l.v > 1e-9 ? 1.5 : 0, (Math.max(0, l.v) / mx) * bw);
        svg.append(sv("rect", { x: lw, y: y + 5, width: wd, height: rowH - 9, rx: 2.5, "data-k": l.k, style: `fill:${l.ht ? `url(#pth-${l.k})` : COR[l.k]}` }),
          sv("text", { x: lw + wd + 6, y: y + 15, class: "v", style: "fill:var(--ink)" }, nf(l.v, 1) + " kWh")); }
      y += rowH; });
    return svg;
  }
  // Participação nas injeções do barramento (rosca): o denominador é escrito no centro.
  function rosca(VG, W = 300) {
    const fat = VG.fatias.filter((f) => f[2] != null && f[2] > 1e-9), tot = VG.v.inj.v, H = Math.min(W, 260), cx = W / 2, cy = H / 2, r1 = H / 2 - 6, r0 = r1 * .6;
    const svg = sv("svg", { class: "trama", width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Participação energética nas injeções", style: `max-width:${W}px;margin:0 auto` });
    if (tot == null) { svg.append(sv("text", { x: cx, y: cy, "text-anchor": "middle", class: "nd" }, "N/D — alguma parcela não foi gravada")); return svg; }
    let a = -Math.PI / 2;
    const pt = (ang, r) => [cx + r * Math.cos(ang), cy + r * Math.sin(ang)];
    fat.forEach(([k, t, x]) => { const b = a + (2 * Math.PI * x) / (tot || 1), big = b - a > Math.PI ? 1 : 0, [x1, y1] = pt(a, r1), [x2, y2] = pt(b, r1), [x3, y3] = pt(b, r0), [x4, y4] = pt(a, r0);
      const d = b - a >= 2 * Math.PI - 1e-9 ? `M${cx - r1},${cy}a${r1},${r1} 0 1,0 ${2 * r1},0a${r1},${r1} 0 1,0 ${-2 * r1},0M${cx - r0},${cy}a${r0},${r0} 0 1,1 ${2 * r0},0a${r0},${r0} 0 1,1 ${-2 * r0},0z`
        : `M${x1},${y1}A${r1},${r1} 0 ${big},1 ${x2},${y2}L${x3},${y3}A${r0},${r0} 0 ${big},0 ${x4},${y4}z`;
      svg.append(sv("path", { d, "data-k": k, style: `fill:${k === "bat" ? "url(#pth-bat)" : COR[k]};stroke:var(--surface);stroke-width:1.5` }));
      const m = (a + b) / 2, [lx, ly] = pt(m, (r0 + r1) / 2); if (b - a > .32) svg.append(sv("text", { x: lx, y: ly + 4, "text-anchor": "middle", class: "v", style: `fill:${k === "bat" ? "var(--ink)" : "var(--surface)"};font-weight:700;paint-order:stroke;stroke:${k === "bat" ? "var(--surface)" : "none"};stroke-width:3px` }, nf((100 * x) / tot, 0) + "%"));
      a = b; });
    svg.append(sv("text", { x: cx, y: cy - 6, "text-anchor": "middle", style: "font-size:11px" }, "Σ injeções"), sv("text", { x: cx, y: cy + 12, "text-anchor": "middle", class: "v", style: "fill:var(--ink);font-size:15px;font-weight:700" }, nf(tot, 0) + " kWh"));
    return svg;
  }
  // Balanço energético da missão: entradas × saídas em duas barras empilhadas; o fechamento é mostrado quando verificável.
  function balancoSvg(VG, W = 900) {
    const ent = VG.fatias, sai = VG.saidas, mx = Math.max(VG.v.inj.v || 0, VG.v.sai.v || 0) || 1, lw = 92, rw = 120, bw = W - lw - rw - 10, H = 112;
    const svg = sv("svg", { class: "trama", width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Balanço energético da missão" });
    [[ent, "Entradas", 10, VG.v.inj.v], [sai, "Saídas", 62, VG.v.sai.v]].forEach(([its, nome, y, tot]) => {
      svg.append(sv("text", { x: 0, y: y + 22, style: "font-weight:600;fill:var(--ink-2)" }, nome));
      if (tot == null) { svg.append(sv("text", { x: lw, y: y + 22, class: "v nd" }, "N/D — parcela não gravada")); return; }
      let x0 = lw; its.forEach(([k, t, x]) => { if (!(x > 1e-9)) return; const wd = (x / mx) * bw;
        svg.append(sv("rect", { x: x0, y: y + 4, width: Math.max(1, wd - 1), height: 30, rx: 3, "data-k": k, style: `fill:${(nome === "Saídas" && k !== "dem") || (k === "bat" && nome === "Entradas") ? `url(#pth-${k})` : k === "dem" ? "color-mix(in srgb, var(--ink) 22%, var(--surface))" : COR[k]}` }));
        if (wd > 64) svg.append(sv("text", { x: x0 + 6, y: y + 23, class: "v", style: `fill:var(--ink);font-weight:600;paint-order:stroke;stroke:var(--surface);stroke-width:3px` }, `${t.replace(/ · .*/, "")} ${nf(x, 0)}`));
        x0 += wd; });
      svg.append(sv("text", { x: lw + bw + 8, y: y + 23, class: "v", style: "fill:var(--ink);font-weight:700" }, nf(tot, 1) + " kWh")); });
    return svg;
  }
  // Indicadores complementares da Visão Geral: [rótulo, valor formatado, origem]
  function complementares(VG) {
    const v = VG.v, R = F.recursos, bat = R.bat.length > 0;
    return [
      M.conectado ? ["Potência máxima importada", v.pmax.v == null ? "N/D" : `${nf(v.pmax.v, 1)} kW às ${lab(v.ipmax)}`, "derivado"] : null,
      M.conectado && v.lim.v != null ? ["Utilização do PCC · pico ÷ limite", `${nfu(v.uPico.v, 1, " %")} de ${nf(v.lim.v, 0)} kW`, "derivado"] : null,
      M.conectado && v.lim.v != null ? ["Utilização média do PCC (importação média ÷ limite)", nfu(v.uMedia.v, 1, " %"), "derivado"] : null,
      M.conectado && v.lim.v != null ? ["Intervalos no limite de importação", v.noLim.v == null ? "N/D" : `${v.noLim.v} de ${K}`, "derivado"] : null,
      v.ren.v !== undefined ? ["Renovável vertida", vgFmt(v.vert, 1, " kWh"), v.vert.o] : null,
      v.ren.v !== undefined ? ["Participação renovável nas injeções", vgFmt(v.partRen, 1, " %"), "derivado"] : null,
      bat ? ["Bateria · carregada | descarregada", `${vgFmt(v.batC, 1)} | ${vgFmt(v.batD, 1)} kWh`, v.batC.o] : null,
      bat ? ["SOC inicial → final", `${nfu(vezes(v.soc0.v, 100), 0)} → ${nfu(vezes(v.soc1.v, 100), 0)} %`, v.soc0.o] : null,
      R.fc.length ? ["PEMFC · energia elétrica produzida", vgFmt(v.fc, 1, " kWh"), v.fc.o] : null,
      ["Auditoria independente da missão", v.auditoria.v == null ? "N/D" : v.auditoria.v ? "aceita" : "REJEITADA", "selado"],
      ["Missão", v.missao.v == null ? "N/D" : v.missao.v ? "completa (concluída)" : "INCOMPLETA", "selado"],
      ["Evidência ao abrir (servidor)", v.verificada.v == null ? "N/D" : v.verificada.v ? "verificada, sem solver" : "COM PROBLEMAS", "servidor"]].filter(Boolean);
  }
  function lVisao() {
    const VG = visaoGeral(F, M), v = VG.v, R = F.recursos, host = h("div", { class: "host vg-temp" }), bat = R.bat.length > 0;
    const fatLeg = VG.fatias.map(([k, t, x]) => `<div class="vg-li"><i style="background-color:${COR[k]}" class="${k === "bat" ? "ht" : ""}"></i><span>${esc(t)}</span><b>${nf(x, 1)} kWh</b><em>${v.inj.v == null || x == null ? "N/D" : nf(razao(x, v.inj.v), 1) + " %"}</em></div>`).join("");
    const notaBat = bat ? `A <b>descarga da bateria</b> devolve energia armazenada antes, vinda das outras fontes: carregada ${vgFmt(v.batC, 1, " kWh")} · descarregada ${vgFmt(v.batD, 1, " kWh")} · saldo descarga − carga ${nfu(menos(v.batD.v, v.batC.v), 1, " kWh")} (derivado). Não é geração primária adicional.` : "";
    const compl = complementares(VG);
    const pnl = (t, cls, ...k) => h("div", { class: "panel " + cls }, h("div", { class: "chead" }, h("span", { class: "ttl" }, t)), ...k);
    const legTemp = [...["fv", "wt"].filter((k) => R[k].length).map((k) => ({ t: TIPOS[k].n.split(" ")[0] + " aproveitada", c: COR[k] })), bat ? { t: "descarga", c: COR.bat } : null, R.fc.length ? { t: "PEMFC", c: COR.fc } : null,
      M.conectado ? { t: "importação", c: COR.grid } : null, { t: "demanda total", c: COR.dem, tipo: "linha" }, bat ? { t: "carga da bateria (abaixo de zero)", c: COR.bat, tipo: "hachura" } : null, M.conectado ? { t: "exportação (abaixo de zero)", c: COR.grid, tipo: "hachura" } : null];
    setTimeout(() => trama(host, opts({ lanes: lanesTemporais(), label: "Participação temporal do suprimento", fill: false, view: null,
      tip: tip((i) => [...supr().map((q) => [q.n, nf(el(q.v, i), 2) + " kW"]), ["Demanda total", nf(el(A.demR, i), 2) + " kW"]]) })));
    // gráficos não temporais desenhados na largura REAL do painel (depois de montados), com o mesmo menu de exportação
    const caixaSvg = (fn) => { const bx = h("div", { class: "vg-svg" }); setTimeout(() => { const svg = fn(Math.max(280, Math.floor(bx.clientWidth || 0) || 560)); bx.replaceChildren(svg); exportavel(bx, svg, expMeta); }); return bx; };
    return h("div", { class: "rolar" }, h("div", { class: "vg" },
      h("div", { class: "vg-kpis" }, ...kpisVisao(VG).map(kpiEl)),
      pnl("Energia por fonte [kWh]", "s7", caixaSvg((w) => barrasFontes(VG, w)), h("p", { class: "note", html: "Valores da missão (resumo selado; soma de recursos da mesma tecnologia = derivado). Hachura = energia vertida, exportada ou carregada na bateria (não é injeção primária)." })),
      pnl("Participação energética", "s5", h("div", { class: "vg-ros" }, caixaSvg((w) => rosca(VG, Math.min(w, 300))), h("div", { class: "vg-lis", html: fatLeg })),
        h("p", { class: "note", html: `<b>Denominador:</b> energia injetada no barramento = Σ renováveis aproveitadas + descarga da bateria + PEMFC + importação = ${vgFmt(v.inj, 1, " kWh")} (derivado). ${notaBat}` })),
      pnl("Balanço energético da missão", "s12", caixaSvg((w) => balancoSvg(VG, w)),
        h("p", { class: "note", html: `Entradas ${vgFmt(v.inj, 2, " kWh")} · saídas ${vgFmt(v.sai, 2, " kWh")} · <b>fechamento (entradas − saídas) ${v.fech.v == null ? "N/D" : ne(v.fech.v, 1) + " kWh"}</b> (derivado dos valores selados). Saídas = demanda atendida + carga da bateria + exportação.` })),
      pnl("Participação temporal do suprimento [kW]", "s12", legRow(legTemp), host,
        h("p", { class: "note", html: "Áreas empilhadas em degrau: média gravada de cada intervalo [t_k, t_k+1), sem interpolação. Só as injeções são empilhadas; carga da bateria e exportação ficam abaixo de zero (consumo, nunca geração). Faixa inferior: participação de cada fonte nas injeções do intervalo (derivado)." })),
      pnl("Indicadores complementares", "s12", h("div", { class: "mgrid vg-mg", html: compl.map(([a, b, o]) => `<div><span>${esc(a)} <em class="tag ${o === "derivado" ? "i" : ""}">${ORIG[o] || ""}</em></span><b>${b}</b></div>`).join("") }))));
  }
  // séries de suprimento (injeções) por tecnologia; carga e exportação são DESTINOS (abaixo de zero)
  const supr = () => [{ k: "fv", n: "Solar aproveitada", v: A.fvP, c: COR.fv }, { k: "wt", n: "Eólica aproveitada", v: A.wtP, c: COR.wt }, { k: "bat", n: "Descarga da bateria", v: A.pd, c: COR.bat },
    { k: "fc", n: "PEMFC", v: A.fcP, c: COR.fc }, { k: "grid", n: "Importação", v: A.impR, c: COR.grid }].filter((q) => q.v !== undefined);
  // Áreas empilhadas em DEGRAU (cada intervalo é um patamar; ausente interrompe a área e é marcado N/D; nada é interpolado).
  function areas(c, series, y, o = {}) {
    const vivas = series.filter((q) => q.v !== undefined), n = K, sg = o.neg ? -1 : 1;
    if (vivas.some((q) => q.v === null)) c.nd();
    const base = new Array(n).fill(0), falta = Array.from({ length: n }, (_, i) => vivas.some((q) => q.v && q.v[i] == null));
    falta.forEach((f, i) => { if (f) c.add(sv("text", { x: c.x(i + .5), y: y(0) - 4, "text-anchor": "middle", class: "v nd" }, "N/D")); });
    for (const q of vivas) { if (!q.v) continue; let i = 0;
      while (i < n) { if (falta[i]) { i++; continue; } let j = i; while (j < n && !falta[j]) j++;
        const val = (g) => Math.max(0, q.v[g]);          // médias de injeção (≥ 0); −0.0 do solver é desenhado como zero
        let d = `M${c.x(i)},${y(sg * (base[i] + val(i)))}`;
        for (let g = i; g < j; g++) d += `H${c.x(g + 1)}` + (g + 1 < j ? `V${y(sg * (base[g + 1] + val(g + 1)))}` : "");
        d += `V${y(sg * base[j - 1])}`;
        for (let g = j - 1; g >= i; g--) d += `H${c.x(g)}` + (g > i ? `V${y(sg * base[g - 1])}` : "");
        c.add(sv("path", { d: d + "Z", "data-k": q.k, style: `fill:${q.hatch ? `url(#pth-${q.hatch})` : q.c};fill-opacity:${q.hatch ? 1 : .88};stroke:none` }));
        for (let g = i; g < j; g++) base[g] += val(g); i = j; } }
  }
  function lanesTemporais() {
    const S_ = supr(), neg = [{ k: "bat", v: A.pc, hatch: "bat" }, { k: "grid", v: M.conectado ? A.expR : undefined, hatch: "grid" }].filter((q) => q.v !== undefined);
    const tot = Array.from({ length: K }, (_, i) => mais(...S_.map((q) => el(q.v, i)))), hi = teto(maxv(tot, A.demR)), lo = maxv(...neg.map((q) => q.v || [])), mn = lo > 1e-6 ? teto(lo) : 0;
    const pct = S_.map((q) => ({ ...q, v: q.v == null ? null : q.v.map((x, i) => (x == null || tot[i] == null ? null : tot[i] > 1e-9 ? (100 * Math.max(0, x)) / tot[i] : 0)) }));
    return [
      { title: "Suprimento por fonte [kW] · áreas empilhadas (injeções) × demanda total · abaixo de zero: carga da bateria e exportação", h: 220, w: 3, draw(c) {
        const y = c.sc(mn ? -mn * 1.12 : 0, hi * 1.04); c.grid(y, mn ? [-mn, 0, hi / 2, hi] : tk(hi), fd(hi));
        areas(c, S_, y); if (neg.length) areas(c, neg, y, { neg: true }); c.step(A.demR, y, { c: COR.dem, w: 2.2, k: "dem" }); } },
      { title: "Participação de cada fonte nas injeções do intervalo [%] · derivado", h: 110, w: 1.4, draw(c) {
        const y = c.sc(0, 100); c.grid(y, [0, 50, 100], (q) => nf(q, 0)); areas(c, pct, y); } }];
  }

  // ---------------------------------------------------------------- relatório PDF (UI-RESULTADOS-02, melhoria 05)
  // O navegador desenha o relatório com as MESMAS raias, painéis, cartões e gráficos da interface — missão COMPLETA (sem zoom
  // nem janela ampliada), tema claro, largura fixa, num contêiner fora da tela — e serializa cada gráfico como SVG vetorial
  // autocontido (estilos resolvidos em cores explícitas; hachuras como atributos). O servidor confere que o pacote é do MESMO
  // marco (hash dos dados gravados) e só diagrama o PDF: nada é recalculado no servidor nem gravado em banco.
  const RW = 1040, RW_FONTE = 760, RFORMATO = "seeds2-relatorio-partitura";   // RW_FONTE: coluna do gráfico nos painéis (cartões ao lado)
  const txt = (html) => { const d = document.createElement("div"); d.innerHTML = String(html ?? "").replace(/<small>/gi, " <small>").replace(/<br\s*\/?>/gi, " "); return d.textContent.replace(/\s+/g, " ").trim(); };
  const xe = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  let PX = null;                                          // canvas 1 × 1: qualquer cor CSS → RGBA explícito
  function rgba(css) {
    if (!css || css === "none" || css === "transparent") return null;
    if (!PX) { const cv = document.createElement("canvas"); cv.width = cv.height = 1; PX = { cx: cv.getContext("2d", { willReadFrequently: true }), m: new Map() }; }
    if (PX.m.has(css)) return PX.m.get(css);
    const cx = PX.cx; cx.clearRect(0, 0, 1, 1); cx.fillStyle = "#000"; cx.fillStyle = css; cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data;
    const out = d[3] === 0 ? null : [d[0], d[1], d[2], d[3] / 255]; PX.m.set(css, out); return out;
  }
  const hex = (c) => "#" + c.slice(0, 3).map((v) => v.toString(16).padStart(2, "0")).join("");
  const GEOM = ["x", "y", "width", "height", "rx", "x1", "y1", "x2", "y2", "cx", "cy", "r", "points", "d", "dx", "clip-path", "id", "data-k"];   // data-k: identidade da série
  function svgPdf(svg) {
    const raiz = svg.getRootNode(), W = +svg.getAttribute("width"), H = +svg.getAttribute("height"), out = [];
    const pinta = (a, prop, v, opac) => { const m = /url\(["']?#([^"')]+)/.exec(v || "");
      if (m && prop === "fill") { const p = raiz.getElementById ? raiz.getElementById(m[1]) : null, rr = p ? p.querySelectorAll("rect") : [];
        const fundo = rr[0] ? rgba(getComputedStyle(rr[0]).fill) : null, faixa = rr[1] ? rgba(getComputedStyle(rr[1]).fill) : null;
        a.push(`fill="${fundo ? hex(fundo) : "#ffffff"}"`); if (faixa) a.push(`data-hatch="${hex(faixa)}" data-hatch-w="${(rr[1] && +rr[1].getAttribute("width")) || 2}" data-hatch-p="${(p && +p.getAttribute("width")) || 5}"`); return; }
      const c = rgba(v); if (!c) { a.push(`${prop}="none"`); return; }
      a.push(`${prop}="${hex(c)}"`); const o = c[3] * opac; if (o < .999) a.push(`${prop}-opacity="${o.toFixed(3)}"`); };
    const walk = (e) => {
      const tag = e.tagName.toLowerCase();
      if (["title", "desc", "metadata", "pattern", "foreignobject"].includes(tag) || (e.classList && e.classList.contains("cur"))) return;
      const estrut = tag === "defs" || tag === "clippath" || e.closest("clipPath"), cs = estrut ? null : getComputedStyle(e);
      if (cs && (cs.display === "none" || cs.visibility === "hidden")) return;
      const a = [];
      for (const g of GEOM) { const v = e.getAttribute(g); if (v != null && v !== "") a.push(`${g}="${xe(v)}"`); }
      if (cs && tag !== "g" && tag !== "svg") {
        pinta(a, "fill", cs.fill, +cs.fillOpacity || 1);
        if (tag !== "text" || (cs.paintOrder || "").startsWith("stroke")) { pinta(a, "stroke", cs.stroke, +cs.strokeOpacity || 1); const sw = parseFloat(cs.strokeWidth); if (sw >= 0) a.push(`stroke-width="${sw}"`); }
        if (cs.strokeDasharray && cs.strokeDasharray !== "none") a.push(`stroke-dasharray="${xe(cs.strokeDasharray.replace(/px/g, "").replace(/,/g, " "))}"`);
        if (+cs.opacity < .999) a.push(`opacity="${(+cs.opacity).toFixed(3)}"`);
        if (tag === "text") { a.push(`font-size="${parseFloat(cs.fontSize) || 11}"`, `font-weight="${parseInt(cs.fontWeight, 10) || 400}"`, `text-anchor="${cs.textAnchor || "start"}"`);
          if ((cs.paintOrder || "").startsWith("stroke")) a.push('data-halo="1"'); }
      }
      if (tag === "text") { let w = 0; try { w = e.getComputedTextLength(); } catch (_) { /* fora do layout */ }
        const t = e.textContent.replace(/\s*↗$/, ""); if (t !== e.textContent) w = w * t.length / Math.max(1, e.textContent.length);
        out.push(`<text ${a.join(" ")} data-w="${w.toFixed(1)}">${xe(t)}</text>`); return; }
      const nome = tag === "clippath" ? "clipPath" : tag;
      out.push(`<${nome}${a.length ? " " + a.join(" ") : ""}>`); for (const c of e.children) walk(c); out.push(`</${nome}>`);
    };
    for (const c of svg.children) walk(c);
    return `<svg xmlns="${NS}" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${out.join("")}</svg>`;
  }
  async function relatorio(progresso) {
    const salvo = JSON.stringify(S), aviso = progresso || (() => {});
    const box = h("div", { class: "pt partitura pt-rel", "data-theme": "light", "aria-hidden": "true", style: `position:fixed;left:-40000px;top:0;width:${RW}px;height:auto;display:block;padding:0;pointer-events:none;contain:layout` });
    root.parentNode.append(box);
    const sonda = h("i", {}); box.append(sonda);
    const corPdf = (c) => { if (!c) return null; sonda.style.backgroundColor = ""; sonda.style.backgroundColor = c; const q = rgba(getComputedStyle(sonda).backgroundColor); return q ? hex(q) : null; };
    const legPdf = (it) => ({ t: it.t, cor: corPdf(it.c) || "#777777", tipo: it.tipo || "area" });
    let nFig = 0; const pausa = async () => { if (++nFig % 4 === 0) { aviso(nFig); await new Promise((r) => setTimeout(r, 0)); } };
    const svgFig = async (svg, titulo, o = {}) => { await pausa(); return { tipo: "figura", titulo, nota: o.nota || "", legenda: (o.leg || []).filter(Boolean).map(legPdf), fontes: o.fontes || [], svg: svgPdf(svg), w: +svg.getAttribute("width"), h: +svg.getAttribute("height"), cols: o.cols || 1 }; };
    const figura = async (titulo, lanes, o = {}) => {
      const L = lanes.filter(Boolean), base = L.reduce((t, x) => t + x.h + 12, 24), hh = o.h || Math.round(Math.min(600, Math.max(320, base * 1.55)));
      const host = h("div", { style: `width:${o.w || RW}px;height:${hh}px;position:relative` }); box.append(host);
      try { const T = trama(host, { K, lab, lanes: L, padL: o.padL, view: o.view || null, band: o.band || null, fill: true, pat: "pth", label: titulo, major: o.major });
        return await svgFig(T.svg, titulo, o); } finally { host.remove(); }
    };
    const avulsa = async (svg, titulo, o = {}) => { const host = h("div", { style: `width:${+svg.getAttribute("width")}px;position:relative` }, svg); box.append(host); try { return await svgFig(svg, titulo, o); } finally { host.remove(); } };
    const cartao = (e) => { const o = (e && e.__o) || {}, linhas = [...(o.grid || []), ...(o.kv || [])].filter(Boolean).map(([a, b]) => [txt(a), txt(b)]);
      let tabela = null;
      if (o.el && o.el.tagName === "TABLE") tabela = [...o.el.rows].map((r) => [...r.cells].map((c) => txt(c.innerHTML)));
      if (o.el && o.el.classList && o.el.classList.contains("rows")) o.el.querySelectorAll(".rowb").forEach((b) => linhas.push([txt((b.querySelector("span") || {}).innerHTML), txt((b.querySelector("b") || {}).innerHTML)]));
      return { t: txt(o.t), tag: txt(o.tag), big: txt(o.big), sub: txt(o.sub), linhas, nd: (o.nd || []).map(txt), nota: txt(o.note), tabela, acc: corPdf(o.acc) }; };
    const instantaneo = (e) => { const o = (e && e.__o) || {}; return o.inst || /^(Instante|Intervalo) /.test(txt(o.t)); };
    const cartoes = (lista) => ({ tipo: "cartoes", itens: lista.filter(Boolean).filter((e) => !instantaneo(e)).map(cartao) });
    const r = F.rodada, ac = F.aceitacao || {}, ver = F.verificacao, sv2 = F.resumo.sinal_valor_futuro || {}, secoes = [];
    try {
      Object.assign(S, { zoom: 0, band: null, depois: true, pin: false });
      // ---------------- 01 · Operação
      const est = (a) => (a ? ESTADOS[a.estado] || a.estado : "N/D");
      const kOp = [{ t: "Custo realizado", v: rs(F.resumo.custo_realizado_total_R), o: "selado", sub: "liquidado · sem valor futuro" }, { t: "Energia atendida", v: nf(F.resumo.energia_atendida_kWh, 1), u: "kWh", o: "selado" },
        { t: "Déficit", v: nf(F.resumo.energia_nao_atendida_kWh, 2), u: "kWh", o: "selado" }, { t: "Decisões com valor futuro", v: `${sv2.valido ?? "N/D"} de ${M.jan.length}`, o: "selado" },
        { t: "Aceitação algébrica", v: est(ac.algebrica), o: "selado" }, { t: "Aceitação dinâmica", v: est(ac.dinamica), o: "selado" }, { t: "Aceitação física", v: est(ac.fisica), o: "selado" },
        { t: "Evidência ao abrir", v: ver == null ? "N/D" : ver.ok ? `verificada (${ver.itens.length} de ${ver.itens.length})` : "COM PROBLEMAS", o: "servidor", sub: "sem solver" }];
      const legOp = [...M.ord.filter((k) => ["wt", "fv", "bat", "fc", "grid"].includes(k)).map((k) => ({ t: TIPOS[k].n, c: COR[k] })), { t: "demanda realizada", c: COR.dem, tipo: "linha" }, { t: "carga da bateria, exportação e vertimento", c: "var(--ink-3)", tipo: "hachura" }, ...legTar()];
      secoes.push({ id: "operacao", titulo: "Operação", sub: "painel operacional da missão completa", blocos: [{ tipo: "kpis", itens: kOp },
        await figura("Partitura da operação — missão completa", lanesOperacao(), { h: 488, leg: legOp, fontes: [F.fontes.intervalos, F.fontes.fronteiras, F.fontes.janelas], nota: "Médias de intervalo gravadas [t_k, t_k+1) e estados de fronteira (energia da bateria). Injeções acima de zero; carga da bateria e exportação abaixo (hachura). Tarifa: degrau por intervalo, sem interpolação." })] });
      // ---------------- 01 · detalhamento por fonte (todas as fontes, todos os UIDs, todas as vistas do explorador)
      const subs = [];
      for (const k of M.ord.filter((q) => q !== "eco")) {
        const lista = R[k] && R[k].length ? R[k] : [null];
        for (const rec of lista) {
          if (rec) S.uid[k] = rec.uid;
          const vistas = k === "fc" ? [["op", "Operação"], ["curva", "Curva q(P) e B04"], ["din", "Verificação dinâmica"]] : [[null, null]], blocos = [];
          let src = "";
          for (const [tb, nomeTb] of vistas) {
            if (tb) S.tab[k] = tb;
            const d = dash(k); src = d.src;
            if (d.special) {
              const host = h("div", { style: `width:${RW}px;height:560px;position:relative` }); box.append(host);
              try { d.special(host, -1); const corI = (i) => { const m = /(var\(--[^)]+\)|#[0-9a-f]{3,8}\b|rgba?\([^)]*\))/i.exec(i ? i.getAttribute("style") || "" : ""); return m ? corPdf(m[1]) : null; };
                const leg = [...host.querySelectorAll(".chead .leg")].map((l) => { const i = l.querySelector("i"); return { t: l.textContent.trim(), cor: corI(i) || "#777777", tipo: i && i.classList.contains("ln") ? "linha" : /border-radius:50%/.test((i && i.getAttribute("style")) || "") ? "ponto" : "area" }; });
                for (const svg of host.querySelectorAll("svg.trama")) blocos.push({ ...(await svgFig(svg, (nomeTb ? nomeTb + " — " : "") + (svg.getAttribute("aria-label") || "Gráfico"), { fontes: [d.src] })), legenda: leg }); } finally { host.remove(); }
            } else { const L = d.lanes.filter(Boolean), base = L.reduce((t, x) => t + x.h + 12, 24);
              blocos.push({ ...(await figura((nomeTb ? nomeTb + " — " : "") + TIPOS[k].n, L, { w: RW_FONTE, h: Math.round(Math.min(600, Math.max(380, base * 1.7))), leg: d.leg, padL: d.padL, fontes: [d.src] })), lado: true }); }
            blocos.push(cartoes(d.cards(0)));
            if (k === "liq") blocos.push(await avulsa(cascata(cargaLiquida(M), Math.round(RW * .62)), "Balanço da carga líquida — energia da missão (derivado)", { fontes: [d.src] }));
          }
          const nomeEq = k === "dem" ? "Demanda agregada" : k === "grid" ? "Ponto de conexão" : k === "liq" ? "Demanda − renováveis aproveitadas" : rec ? rec.nome : TIPOS[k].n;
          subs.push({ id: `${k}:${rec ? rec.uid : k}`, titulo: `${TIPOS[k].n} — ${nomeEq}`, rotulo: [rec && rec.tag, rec ? rec.uid : k === "grid" ? "PCC" : ""].filter(Boolean).join(" · "), fontes: src, blocos });
        }
      }
      secoes.push({ id: "fontes", titulo: "Operação — detalhamento por fonte", sub: "uma subseção por recurso (UID), na ordem do explorador de recursos", subsecoes: subs });
      // ---------------- 02 · Visão Geral
      const VG = visaoGeral(F, M), v = VG.v;
      const compl = complementares(VG);
      secoes.push({ id: "visao", titulo: "Visão Geral", sub: "síntese energética, econômica e operacional da missão", blocos: [
        { tipo: "kpis", itens: kpisVisao(VG).map((q) => ({ t: q.t, v: txt(q.big), u: q.u ? txt(q.u) : "", o: q.o, sub: q.sub ? txt(q.sub) : "" })) },
        await avulsa(barrasFontes(VG, Math.round(RW * .58)), "Energia por fonte [kWh]", { cols: 2, nota: "Resumo selado da missão; soma de recursos da mesma tecnologia = derivado. Hachura = energia vertida, exportada ou carregada na bateria." }),
        { ...(await avulsa(rosca(VG, 300), "Participação energética nas injeções", { cols: 2, nota: `Denominador: energia injetada no barramento = Σ renováveis aproveitadas + descarga + PEMFC + importação = ${vgFmt(v.inj, 1, " kWh")} (derivado).` + (R.bat.length ? ` A descarga da bateria devolve energia carregada antes (carregada ${vgFmt(v.batC, 1, " kWh")}; descarregada ${vgFmt(v.batD, 1, " kWh")}): não é geração primária.` : "") })),
          fatias: VG.fatias.map(([k, t, x]) => ({ t, cor: corPdf(COR[k]), v: nfu(x, 1, " kWh"), p: v.inj.v == null || x == null ? "N/D" : nfu(razao(x, v.inj.v), 1, " %"), hachura: k === "bat" })) },
        await avulsa(balancoSvg(VG, RW), "Balanço energético da missão", { nota: `Entradas ${vgFmt(v.inj, 2, " kWh")} · saídas ${vgFmt(v.sai, 2, " kWh")} · fechamento (entradas − saídas) ${v.fech.v == null ? "N/D" : ne(v.fech.v, 1) + " kWh"} (derivado dos valores selados).` }),
        await figura("Participação temporal do suprimento", lanesTemporais(), { h: 425, leg: [...supr().map((q) => ({ t: q.n, c: q.c })), { t: "demanda total", c: COR.dem, tipo: "linha" }, R.bat.length ? { t: "carga da bateria (abaixo de zero)", c: COR.bat, tipo: "hachura" } : null, M.conectado ? { t: "exportação (abaixo de zero)", c: COR.grid, tipo: "hachura" } : null], fontes: [F.fontes.intervalos], nota: "Áreas empilhadas em degrau (média gravada de cada intervalo, sem interpolação); só as injeções são empilhadas. Faixa inferior: participação de cada fonte nas injeções do intervalo (derivado)." }),
        { tipo: "tabela", titulo: "Indicadores complementares", colunas: ["Indicador", "Valor", "Origem"], linhas: compl.map(([a, b, o]) => [a, txt(b), ORIG[o] || o]) }] });
      // ---------------- 03 · Decisão
      const TP = tapetes(), blocosD = [], okJ = M.jan.filter((q) => q.ok).length, sol = F.resumo.solver || {};
      blocosD.push({ tipo: "kpis", itens: [{ t: "Decisões do MPC", v: String(M.jan.length), o: "selado" }, { t: "Com valor futuro", v: `${okJ} de ${M.jan.length}`, o: "selado" }, { t: "Janelas ótimas", v: `${sol.janelas_otimas ?? "N/D"} de ${sol.janelas_resolvidas ?? "N/D"}`, o: "selado" },
        { t: "Gap relativo máximo", v: ne(sol.gap_rel_max, 1), o: "selado" }, { t: "Horizonte curto N · bloco m", v: `${r.N} · ${r.m}`, o: "declarado" }, { t: "Horizonte longo H_L", v: String(r.H_L), o: "declarado" }] });
      for (const tp of TP) for (let a = 0; a < M.jan.length; a += 24) { const ch = M.jan.slice(a, a + 24);
        const t0 = Math.max(0, ch[0].k - 1), t1 = Math.min(K, Math.max(...ch.map((q) => q.k + q.Nk)) + 1);
        blocosD.push(await figura(`Tapete de decisões · ${tp.nome} · janelas ${ch[0].j}–${ch[ch.length - 1].j}`, [{ ...decisaoLanes(ch[0], tp, ch, { semDestaque: true }).lanes[0], note: "▁ intervalo aplicado" }], { h: Math.max(170, ch.length * 9 + 56), view: t1 - t0 < K ? [t0, t1] : null, leg: [{ t: "valor planejado (intensidade)", c: tp.cor }, { t: "N/D (plano não gravado)", c: "var(--warn)", tipo: "tracejado" }], fontes: [F.fontes.planos], nota: "Uma linha por janela: o plano de cada decisão nos N intervalos do horizonte; traço inferior = intervalo aplicado; ∅ = decisão sem valor futuro." })); }
      const galeria = [];
      for (const w of M.jan) { const dl = decisaoLanes(w, null, [], { tapete: false }), curtos = ["Energia planejada × executada [kWh]", "Despacho planejado [kW]"];
        const L = dl.lanes.filter(Boolean).map((x, n) => ({ ...x, title: dl.lanes.filter(Boolean).length === 1 ? curtos[1] : curtos[n], note: null }));
        galeria.push(await figura(`Janela ${w.j} · τ = ${lab(w.k)} · ${w.ok ? "com valor futuro" : "sem valor futuro"}`, L, { w: Math.floor(RW / 3) - 6, h: 210, view: [Math.max(0, w.k - 1), Math.min(K, dl.fimJ + 1)], band: [w.k, Math.min(K, dl.fimJ)], cols: 3, major: 4 })); }
      if (galeria.length) blocosD.push({ tipo: "galeria", titulo: "Decisão de cada janela — energia planejada × executada e despacho planejado (cheio = aplicado)", colunas: 3, itens: galeria,
        legenda: [{ t: "executado até τ", c: COR.bat, tipo: "ponto" }, { t: "executado depois (pontilhado)", c: COR.bat, tipo: "pontilhado" }, { t: "plano MPC da janela", c: "var(--ink)", tipo: "ponto" }, { t: "plano de longo prazo", c: "var(--ink-3)", tipo: "tracejado" }, { t: "demanda prevista × realizada", c: "var(--ink)", tipo: "tracejado" }].map(legPdf) });
      const ves = [], semSinal = [];
      for (const w of M.jan) { const C = coordDe(w.j), s = C && C.sinal;
        if (!s || !(s.modos || []).some((m) => (m.pontos || []).length)) { semSinal.push([`j${w.j}`, lab(w.k), !C ? "registro de coordenação não persistido" : !s ? txt(C.motivo || "nenhum sinal produzido") : "sinal sem pontos V(E) gravados"]); continue; }
        const host = h("div", { style: "width:300px;position:relative" }); box.append(host);
        try { sinalVE(host, w, C); const svg = host.querySelector("svg.trama"), nd = [...host.querySelectorAll(".nd")].map((e) => txt(e.innerHTML)), nt = [...host.querySelectorAll(".note")].map((e) => txt(e.innerHTML)).join(" ");
          const cont = /\d+ modo\(s\)[^.]*/.exec(nt), notas = [...nd, cont ? cont[0] : nt].filter(Boolean).join(" ");
          if (svg) ves.push({ ...(await svgFig(svg, `Janela ${w.j} · fronteira ${lab(s.indice_fronteira)} · ${(s.qualidade || {}).estado === "valido" ? "válido" : "indisponível"}`, { cols: 4 })), nota: notas });
          else { const tb = host.querySelector("table"); ves.push({ tipo: "tabela", titulo: `Janela ${w.j} · sinal com ${(s.baterias || []).length} bancos (pontos gravados)`, colunas: tb ? [...tb.rows[0].cells].map((c) => txt(c.innerHTML)) : [], linhas: tb ? [...tb.rows].slice(1).map((rr) => [...rr.cells].map((c) => txt(c.innerHTML))) : [], nota: notas }); } } finally { host.remove(); } }
      if (ves.length) blocosD.push({ tipo: "galeria", titulo: "Sinal de valor futuro V(E) de cada decisão — instrumento do planejador (não é custo realizado)", colunas: 4, itens: ves,
        nota: "V [R$] = custo de continuação estimado a partir da fronteira do sinal, em função da energia armazenada nessa fronteira; linha vertical = energia planejada pelo MPC; × = validações reotimizadas; faixa = domínio do modo escolhido. Instrumento de decisão do planejador: não é custo, não é receita e nunca entra no custo realizado." });
      if (semSinal.length) blocosD.push({ tipo: "tabela", titulo: "Decisões sem sinal de valor futuro utilizável", colunas: ["Janela", "τ", "Motivo registrado"], linhas: semSinal });
      blocosD.push({ tipo: "tabela", titulo: "Decisões do MPC — previsto × realizado por bloco aplicado", colunas: ["j", "τ", "N", "aplic.", "classe", "objetivo MILP [R$]", "operativo previsto [R$]", "futuro estimado [R$]", "previsto no bloco [R$]", "realizado no bloco [R$]", "valor futuro"],
        linhas: M.jan.map((q) => [String(q.j), lab(q.k), String(q.Nk), String(q.ap ?? "N/D"), String(q.classe ?? "N/D").replace(/_/g, " "), nf(q.objetivo, 2), nf(q.custo_operativo_previsto, 2), q.custo_futuro_estimado == null ? "N/D" : nf(q.custo_futuro_estimado, 2), nf(q.planejado_prefixo, 2), nf(q.realizado, 2), q.ok ? "válido" : "indisponível"]),
        nota: "Objetivo, custo operativo previsto e custo futuro estimado são PREVISÕES de cada decisão (as janelas se sobrepõem e não se somam); só o realizado no bloco é liquidado. O custo futuro estimado nunca entra no custo realizado." });
      secoes.push({ id: "decisao", titulo: "Decisão", sub: "EMS hierárquico: decisões MPC, planos, plano de longo prazo e sinais de valor futuro", blocos: blocosD });
      // ---------------- 04 · Economia
      const sPrev = somaT(M.jan.map((q) => q.planejado_prefixo ?? null)), sReal = somaT(M.jan.map((q) => q.realizado ?? null));
      const cc = cartao(cardCusto(K - 1, F.resumo.componentes_R || {}));
      secoes.push({ id: "economia", titulo: "Economia", sub: "custo realizado × previsões da otimização × instrumentos de decisão", blocos: [
        { tipo: "kpis", itens: [{ t: "Custo realizado", v: rs(F.resumo.custo_realizado_total_R), o: "selado" }, ...Object.entries(F.resumo.componentes_R || {}).map(([q, x]) => ({ t: (NOME_C[q] || ["", q.replace(/_/g, " ")])[1], v: rs(x), o: "selado" })),
          M.conectado ? { t: "Preço médio de importação", v: nfu(razao(F.resumo.gasto_importacao_R, F.resumo.energia_importada_kWh, 1), 3, " R$/kWh"), o: "derivado" } : null].filter(Boolean) },
        await figura("Economia da missão", lanesEconomia(), { h: 445, leg: [...legCusto(), ...legTar()], fontes: [F.fontes.intervalos, F.fontes.janelas], nota: "Custo REALIZADO (liquidado) por intervalo e acumulado; bloco aplicado previsto × realizado; objetivo do MILP por decisão (previsão) com o valor futuro estimado em hachura — instrumento de decisão, nunca custo realizado." }),
        { tipo: "cartoes", itens: [{ ...cc, sub: "" }, cartao(cardTres(sPrev, sReal, M.jan.filter((q) => q.ok).length))] }] });
      // ---------------- 05 · Evidência (o servidor acrescenta verificação, auditoria, procedência e arquivos a partir dos dados)
      secoes.push({ id: "evidencia", titulo: "Evidência", sub: "integridade, auditoria, procedência e limitações", blocos: [{ tipo: "avisos", grupos: agruparAvisos(F.avisos || []) }] });
      aviso(nFig);
      return { formato: RFORMATO, versao: 1, hash: F.hash, rodada: r.uid, largura: RW, figuras: nFig, secoes };
    } finally { const v0 = JSON.parse(salvo); for (const q of Object.keys(S)) delete S[q]; Object.assign(S, v0); box.remove(); }
  }

  // ---------------------------------------------------------------- moldura
  function render() {
    HOOKS = []; bus.clear();
    const r = F.rodada, ac = F.aceitacao || {}, ver = F.verificacao, sv2 = F.resumo.sinal_valor_futuro || {}, st = h("footer", { class: "status" });
    const pt = (cls, t) => h("span", { html: `<i class="${cls}"></i>${t}` });
    const paintSt = () => st.replaceChildren(h("span", { html: `<b>RODADA ${esc(r.uid.slice(0, 8))}</b> · concluída · somente leitura` }),
      ac.algebrica ? pt(ac.algebrica.estado === "aprovada" ? "" : "b", "algébrico " + esc(ESTADOS[ac.algebrica.estado] || ac.algebrica.estado)) : null, ac.dinamica ? pt(ac.dinamica.estado === "coerente" ? "" : ac.dinamica.estado === "incoerente" ? "b" : "o", "dinâmico " + esc(ESTADOS[ac.dinamica.estado] || ac.dinamica.estado)) : null, ac.fisica ? pt("o", "físico " + esc(ESTADOS[ac.fisica.estado] || ac.fisica.estado)) : null,
      ver ? pt(ver.ok ? "" : "b", ver.ok ? `evidência verificada (${ver.itens.length} de ${ver.itens.length}) sem solver` : "EVIDÊNCIA COM PROBLEMAS") : null, r.sintetico ? pt("w", "dados sintéticos de ensaio") : null,
      h("span", { class: "grow" }), h("span", { class: "pt-inst", html: `instante <b>${ivl(S.cur)}</b>${S.pin ? " fixado" : ""}` }), h("button", { class: "pill", onclick: () => abrir(S.ex || M.ord[0]) }, "Explorar recursos"));
    paintSt(); HOOKS.push(paintSt);
    const tema = h("button", { class: "tool", title: "Tema claro / escuro", "aria-label": "Alternar tema claro / escuro", onclick: () => { const t = root.dataset.theme === "dark" ? "light" : "dark"; root.dataset.theme = t; try { localStorage.setItem("seeds2.partitura.tema", t); } catch (_) { /* sem armazenamento */ } }, html: ico("M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z") });
    const lentes = h("div", { class: "seg lentes", role: "tablist", "aria-label": "Lente" }, ...LENTES.map(([id, n]) => h("button", { role: "tab", "data-lente": id, "aria-selected": String(S.lens === id), onclick: () => irLente(id) }, n)));
    const bar = h("header", { class: "bar" }, h("div", {}, h("h1", {}, r.cenario || "Rodada"), h("div", { class: "ctx", html: `rodada ${esc(r.uid.slice(0, 8))} · cenário v${r.versao_cenario} · inventário rev. ${r.revisao_inventario} · ${K} intervalos de ${nf(r.delta_min, 0)} min · N ${r.N} · m ${r.m} · H_L ${r.H_L} &nbsp;—&nbsp; <b>${rs(F.resumo.custo_realizado_total_R)}</b> realizados · <b>${nf(F.resumo.energia_atendida_kWh, 0)} kWh</b> atendidos · déficit <b>${nf(F.resumo.energia_nao_atendida_kWh, 1)} kWh</b> · valor futuro em <b>${sv2.valido ?? "N/D"} de ${M.jan.length}</b> decisões` })), h("span", { class: "grow" }), lentes, relBotao(), tema);
    const defs = sv("svg", { width: 0, height: 0, style: "position:absolute", "aria-hidden": "true" }, sv("defs", {}, [["bat", "var(--s-bat)", 2.4], ["wt", "var(--s-wt)", 2], ["fv", "var(--s-fv)", 2], ["grid", "var(--s-grid)", 2], ["eco", "var(--s-eco)", 2]].map(([n, cr, lw]) => sv("pattern", { id: "pth-" + n, width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, [sv("rect", { width: 5, height: 5, style: "fill:var(--surface)" }), sv("rect", { width: lw, height: 5, style: `fill:${cr}` })]))));
    root.dataset.lenteAtiva = S.lens;
    root.replaceChildren(defs, bar, S.lens === "decisao" ? lDecisao() : S.lens === "economia" ? lEconomia() : S.lens === "evidencia" ? lEvidencia() : S.lens === "visao" ? lVisao() : lOperacao(), st);
    if (S.ex) root.append(explorador());
    if (relEl) root.append(relEl);
  }
  root.onkeydown = (e) => { if (!S.ex) return; if (e.key === "Escape") { fechar(); e.stopPropagation(); } else if (/^[1-9]$/.test(e.key) && !/INPUT|SELECT/.test(e.target.tagName) && M.ord[+e.key - 1]) abrir(M.ord[+e.key - 1]); };
  // ---------------------------------------------------------------- geração do relatório (botão, progresso, resposta do servidor)
  // Pedido = botão «Relatório PDF» desta barra OU o botão do painel de exportações (o servidor passa {pedido, estado:"pedido"}).
  // O pacote vai ao servidor pelo gatilho «relatorio»; a resposta volta nos dados do componente ({pedido, estado, msg…}).
  let REL = { estado: null }, relEl = null, ultimoPedido = null;
  function relPinta() {
    if (!REL.estado) { if (relEl) relEl.remove(); relEl = null; return; }
    const fechar = h("button", { class: "tool", title: "Fechar", "aria-label": "Fechar", onclick: () => { REL = { estado: null }; relPinta(); }, html: ico("M6 6l12 12M18 6L6 18") });
    const ir = h("button", { class: "pill", onclick: () => { try { const a = document.querySelector('[class*="exportacoes_v2"]'); if (a) a.scrollIntoView({ block: "center", behavior: "smooth" }); } catch (_) { /* sem área */ } } }, "Ir para o download");
    const ocup = REL.estado === "desenhando" || REL.estado === "enviado";
    const corpo = REL.estado === "desenhando" ? `<b>Preparando o relatório PDF</b><span>desenhando a missão completa no tema claro · ${REL.n || 0} gráficos</span>`
      : REL.estado === "enviado" ? `<b>Diagramando o PDF no servidor</b><span>${REL.figuras} gráficos vetoriais · ${nf(REL.kib, 0)} KiB · nenhum cálculo é refeito</span>`
        : REL.estado === "pronto" ? `<b>Relatório pronto</b><span>${esc(REL.nome || "")}${REL.paginas ? " · " + REL.paginas + " páginas" : ""} — baixe em «Exportações científicas», logo abaixo.</span>`
          : `<b>Relatório não gerado</b><span>${esc(REL.msg || "falha inesperada")}</span>`;
    const novo = h("div", { class: "relbox" + (REL.estado === "erro" ? " erro" : ""), role: "status", "aria-live": "polite", "data-estado": REL.estado },
      ocup ? h("i", { class: "relspin", "aria-hidden": "true" }) : null, h("div", { class: "reltxt", html: corpo }), REL.estado === "pronto" ? ir : null, ocup ? null : fechar);
    if (relEl && relEl.parentNode) relEl.replaceWith(novo); else root.append(novo);
    relEl = novo;
  }
  async function gerarRelatorio(pedido) {
    if (REL.estado === "desenhando" || REL.estado === "enviado") return;
    REL = { estado: "desenhando", n: 0, pedido }; relPinta();
    try {
      const pac = await relatorio((n) => { REL.n = n; relPinta(); });
      pac.pedido = pedido;
      const corpo = JSON.stringify(pac);
      if (!root.__enviar) throw new Error("canal com o servidor indisponível nesta página");
      REL = { estado: "enviado", pedido, figuras: pac.figuras, kib: corpo.length / 1024 }; relPinta();
      root.__enviar(pac);
    } catch (e) { REL = { estado: "erro", pedido, msg: String((e && e.message) || e) }; relPinta(); }
  }
  function relStatus(d) {
    if (!d || !d.pedido) return;
    if (d.estado === "pedido" && d.pedido !== ultimoPedido) { ultimoPedido = d.pedido; gerarRelatorio(d.pedido); return; }
    if (REL.pedido === d.pedido && (d.estado === "pronto" || d.estado === "erro") && REL.estado !== d.estado) { REL = { ...REL, estado: d.estado, msg: d.msg, nome: d.nome, paginas: d.paginas }; relPinta(); }
  }
  function relBotao() {
    return h("button", { class: "pill rel-btn", "data-acao": "relatorio", title: "Gerar o relatório PDF completo desta rodada: missão completa, todas as lentes e todas as fontes (vetorial, tema claro)",
      onclick: () => gerarRelatorio("local-" + Date.now().toString(36)), html: ico("M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6", 15) + "Relatório PDF" });
  }
  return { render, relatorio, relStatus, gerarRelatorio };
}

export default function (component) {
  const { data, parentElement } = component;
  let root = parentElement.querySelector(".pt");
  if (!root) {
    root = h("div", { class: "pt partitura" }); parentElement.appendChild(root);   // «partitura» distingue o instrumento dos outros .pt
    let lw = 0, lh = 0, t = null;
    if (typeof ResizeObserver !== "undefined") new ResizeObserver(() => { const w = root.clientWidth, hgt = root.clientHeight; if (Math.abs(w - lw) < 2 && Math.abs(hgt - lh) < 2) return; lw = w; lh = hgt; clearTimeout(t); t = setTimeout(() => root.__pt && root.__pt.render(), 140); }).observe(root);
  }
  let tema = null; try { tema = localStorage.getItem("seeds2.partitura.tema"); } catch (_) { /* sem armazenamento */ }
  if (tema !== "dark" && tema !== "light") { const m = /rgba?\((\d+)[, ]+(\d+)[, ]+(\d+)/.exec(getComputedStyle(document.body).backgroundColor || ""); tema = m && (0.2126 * m[1] + 0.7152 * m[2] + 0.0722 * m[3]) < 110 ? "dark" : "light"; }
  root.dataset.theme = tema;
  const F = data && data.frame;
  if (!F || F.formato !== "seeds2-trama-frame") { root.__hash = null; root.__pt = null; root.replaceChildren(h("div", { class: "nd", html: "<b>N/D</b> — marco de dados da rodada indisponível" })); return; }
  root.__enviar = typeof component.setTriggerValue === "function" ? (p) => component.setTriggerValue("relatorio", p) : null;   // UI-RESULTADOS-02
  if (root.__hash === F.hash && root.__pt) { root.__pt.relStatus(data.relatorio); return; }   // rerun com o mesmo marco: nada é redesenhado
  const primeira = !root.__hash;
  root.__hash = F.hash; root.__pt = Partitura(root, F); root.__pt.render(); root.__pt.relStatus(data.relatorio);
  // Ao abrir a rodada, o instrumento vem para o topo da janela (o cabeçalho da página continua logo acima).
  if (primeira) setTimeout(() => { try { root.scrollIntoView({ block: "start" }); } catch (_) { /* navegador antigo */ } }, 60);
}
