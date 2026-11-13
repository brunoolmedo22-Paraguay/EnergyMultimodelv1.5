// PLANTA (Piso 3D-B2-B) — o barramento equivalente da microrrede como o modelo o enxerga: o que injeta acima, o que armazena
// ou consome abaixo, um nó por equipamento do INVENTÁRIO (identidade por UID). Com uma rodada V2 concluída escolhida, cada nó
// mostra o valor GRAVADO do intervalo (nada é recalculado). As ligações NÃO representam fluxos: o modelo não calcula ramos.
// Ações devolvidas ao Python: {type:"rodada", run} | {type:"abrir_rodada", run} | {type:"nav", view, tab}.
// UI-REDESIGN-01: identidade das tecnologias = a do GESTOR (ícones ICONES_GESTOR de static/inventory.js e cores --k-* de
// static/kit.css, injetados por seeds2/ui/trama.py). Demanda e PCC não existem no Gestor: ícones próprios no mesmo traço.
// ``cn`` = rótulo curto do tipo no nó (o nome completo ``n`` fica no resumo, no painel e no rótulo acessível).
const TP = { fv: { n: "Solar fotovoltaica", cn: "Solar", c: "var(--k-pv)", ico: "pv", l: 0 }, wt: { n: "Eólica", cn: "Eólica", c: "var(--k-wind)", ico: "wind", l: 0 },
  fc: { n: "PEMFC / Hidrogênio", cn: "H₂ / PEMFC", c: "var(--k-pemfc)", ico: "pemfc", l: 0 }, term: { n: "Térmica", cn: "Térmica", c: "var(--k-thermal)", ico: "thermal", l: 0 },
  outro: { n: "Equipamento", cn: "Equipamento", c: "var(--ink-3)", ico: "outro", l: 0 }, bat: { n: "Bateria", cn: "Bateria", c: "var(--k-battery)", ico: "battery", l: 1 },
  dem: { n: "Carga / Demanda", cn: "Demanda", c: "var(--k-load)", ico: "dem", l: 1 }, grid: { n: "Rede / PCC", cn: "Rede", c: COR.grid, ico: "grid", l: 1 } };
const ICO_PL = Object.assign({
  dem: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 15.5L16 6l11 9.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M8 13.5V26h16V13.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M17.2 14.5l-3.4 5.2h3.6l-2.6 4.8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  grid: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3l-7 26M16 3l7 26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M8 10h16M6.5 16.5h19M10.5 23h11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M12.5 10l7 6.5M19.5 10l-7 6.5" stroke="currentColor" stroke-width="1.2" opacity=".6"/></svg>`,
  outro: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="7" y="7" width="18" height="18" rx="4" fill="none" stroke="currentColor" stroke-width="2"/></svg>`,
}, typeof ICONES_GESTOR !== "undefined" ? ICONES_GESTOR : {});
const PAINEL = { fv: "fv", wt: "wt", fc: "fc", bat: "bat", dem: "dem", grid: "grid" };
// Modelo PURO da planta (executado também em Node): nós do inventário + séries gravadas da rodada por UID, com a mesma regra
// de N/D da Partitura (null = ausente; undefined = o equipamento não participou da rodada / não há rodada).
function modeloPlanta(D) {
  const R = D.rodada || null, K = R ? R.K : 0, S = R ? R.series || {} : {}, loc = R ? R.local || [] : [];
  const multi = new Set(loc.map((s) => String(s).slice(0, 10))).size > 2, semMin = loc.every((s) => String(s).slice(14, 16) === "00");
  const rot = loc.map((s) => { const t = String(s), hm = semMin ? t.slice(11, 13) + "h" : t.slice(11, 16); return multi && t.slice(11, 16) === "00:00" ? t.slice(8, 10) + "/" + t.slice(5, 7) : hm; });
  const col = (ids, g, n = K) => agg(ids.map((u) => (S[u] || {})[g] ?? null), n);       // intervalos: K valores; fronteiras: K + 1
  const nos = (D.nos || []).map((n) => {
    const ids = !R ? [] : n.prefixo ? Object.keys(S).filter((u) => u === n.uid || u.startsWith(n.prefixo)) : (n.uids || []).filter((u) => u in S), participa = ids.length > 0;
    let p, extra = {};
    if (!participa) p = undefined;
    else if (n.tipo === "bat") { const pd = col(ids, "pd"), pc = col(ids, "pc"); p = pd == null || pc == null ? null : pd.map((v, i) => menos(v, pc[i])); extra = { e: col(ids, "e", K + 1), pd, pc }; }
    else { p = col(ids, "p"); if (n.tipo === "fc") extra = { u: ids.length === 1 ? (S[ids[0]].u ?? null) : undefined }; else extra = { pot: col(ids, "pot") }; }
    return { ...n, ids, participa, p, ...extra };
  });
  const dem = { uid: "demanda", tipo: "dem", nome: "Demanda agregada", tag: "", habilitado: true, resumo: "", detalhes: [["Origem", (D.demanda || {}).origem || "não declarada"]], ids: [], participa: !!R, p: R ? (R.demanda || {}).realizada ?? null : undefined };
  const con = R ? !!(R.pcc || {}).conectado : !!(D.pcc || {}).conectada;
  const grid = con ? { uid: "PCC", tipo: "grid", nome: "Ponto de conexão", tag: "PCC", habilitado: true, resumo: "", detalhes: [["Conexão", R ? "conectado nesta rodada" : "conectada (inventário)"]], ids: [], participa: !!R,
    p: !R ? undefined : (R.pcc.imp == null || R.pcc.exp == null ? null : R.pcc.imp.map((v, i) => menos(v, R.pcc.exp[i]))), tar: R ? R.pcc.tarifa ?? null : undefined } : null;
  const todos = nos.concat([dem], grid ? [grid] : []);
  return { K, rot, nos: todos, cima: todos.filter((n) => TP[n.tipo].l === 0), baixo: todos.filter((n) => TP[n.tipo].l === 1), conectado: con };
}
const kwTxt = (n, i) => { const v = el(n.p, i); return v === undefined ? "—" : v === null ? "N/D" : (n.tipo === "bat" && v < 0 ? "−" : "") + nf(Math.abs(v), 1) + " kW"; };
function estadoTxt(n, i) {
  if (!n.habilitado) return "desabilitado no inventário";
  if (n.p === undefined) return n.tipo === "dem" || n.tipo === "grid" ? "" : "não participou desta rodada";
  const v = el(n.p, i);
  if (n.tipo === "bat") { const a = el(n.e, i), b = el(n.e, i + 1); return `${nf(a, 0)} → ${nf(b, 0)} kWh · ${v == null ? "N/D" : v < -1e-6 ? "carga" : v > 1e-6 ? "descarga" : "repouso"}`; }
  if (n.tipo === "fc") { const u = el(n.u, i); return u === undefined ? "" : u == null ? "estado N/D" : u ? "ligada" : "desligada"; }
  if (n.tipo === "fv" || n.tipo === "wt") return "potencial " + nf(el(n.pot, i), 1) + " kW";
  if (n.tipo === "grid") return n.tar === undefined ? "" : "tarifa " + nf(el(n.tar, i), 2) + " R$/kWh";
  if (n.tipo === "dem") return "realizada (média do intervalo)";
  return "";
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component, D = data || {}, [root] = raizPt(parentElement, "pg planta");
  const M = modeloPlanta(D), R = D.rodada || null, chave = "seeds2.planta." + ((D.microrrede || {}).uid || ""), sig = JSON.stringify([D.nos, D.escolhida, R && R.hash, D.rodadas]);
  const S = root.__S || { sel: null, cur: 0 };
  if (!root.__S) { try { Object.assign(S, JSON.parse(sessionStorage.getItem(chave) || "{}")); } catch (_) { /* sem armazenamento */ } root.__S = S; }
  if (root.__sig === sig) return;                           // rerun do Streamlit com os mesmos dados: nada é redesenhado
  root.__sig = sig;
  S.cur = Math.min(Math.max(0, M.K - 1), Math.max(0, S.cur | 0)); if (S.sel && !M.nos.some((n) => n.uid === S.sel)) S.sel = null;
  const salvar = () => { try { sessionStorage.setItem(chave, JSON.stringify(S)); } catch (_) { /* idem */ } }, ir = (a) => setTriggerValue("action", { ...a, t: Date.now() });
  const lab = (b) => M.rot[b] ?? String(b), ivl = (i) => `${lab(i)}–${lab(i + 1)}`, kvh = (rows) => rows.filter(Boolean).map(([a, b]) => `<span>${esc(a)}</span><b>${esc(b)}</b>`).join("");
  const wrap = h("div", { class: "panel acc host pl-host", style: "--acc:var(--ink-3)" }), col = h("div", { class: "col" }), pop = h("div", { class: "pop", hidden: true }), refs = {};
  const abrirPainel = (n) => { const k = PAINEL[n.tipo]; if (!R || !k) return;
    try { const c = "seeds2.partitura." + R.uid, st = JSON.parse(sessionStorage.getItem(c) || "{}"); st.ex = k; st.lens = "operacao"; st.cur = S.cur; st.pin = true; if (n.ids.length) st.uid = { ...(st.uid || {}), [k]: n.ids[0] }; sessionStorage.setItem(c, JSON.stringify(st)); } catch (_) { /* sem armazenamento: a rodada abre sem o painel */ }
    ir({ type: "abrir_rodada", run: R.uid }); };
  const cartoes = () => { const n = M.nos.find((x) => x.uid === S.sel), mg = D.microrrede || {}, hab = (D.nos || []).filter((x) => x.habilitado).length;
    const sel = h("select", { class: "sel", style: "max-width:100%;width:100%", "aria-label": "Rodada mostrada na planta", onchange: (e) => ir({ type: "rodada", run: e.target.value }) },
      h("option", { value: "", selected: !D.escolhida }, "Só o inventário (sem rodada)"), ...(D.rodadas || []).map((r) => h("option", { value: r.uid, selected: r.uid === D.escolhida }, r.rotulo)));
    col.replaceChildren(...[
      h("div", { class: "card acc", style: "--acc:var(--ink)" }, h("h3", { html: "Microrrede" }), h("div", { class: "big", style: "font-size:19px" }, mg.nome || "Sem nome"),
        h("div", { class: "kv", html: kvh([["Inventário", "rev. " + (mg.revisao ?? "N/D")], ["Modo declarado", mg.modo || "não declarado"], ["Equipamentos", `${(D.nos || []).length} · ${hab} habilitado(s)`], ["Conexão à rede", M.conectado ? "PCC presente" : "sem PCC (isolada)"]]) })),
      h("div", { class: "card" }, h("h3", { html: `Rodada na planta${R ? '<span class="tag ok">valores gravados</span>' : ""}` }), (D.rodadas || []).length ? sel : null,
        !(D.rodadas || []).length ? h("div", { class: "nd", html: "<b>Sem rodada V2 concluída</b> nesta microrrede: a Planta mostra o inventário. Execute um ensaio para ver os valores gravados por equipamento." }) : null,
        D.rodada_indisponivel ? h("div", { class: "nd", html: "<b>N/D</b> — a evidência desta rodada não pôde ser verificada: a Planta mostra só o inventário." }) : null,
        R ? h("div", {}, h("div", { class: "big pl-inst", style: "font-size:20px;margin-top:8px" }, ivl(S.cur)), h("div", { class: "sub" }, `médias do intervalo · ${M.K} intervalos de ${nf(R.delta_min, 0)} min`),
          h("input", { type: "range", class: "pl-t", min: 0, max: M.K - 1, value: S.cur, style: "width:100%;accent-color:var(--ink);margin:8px 0 2px", "aria-label": "Instante", oninput: (e) => { S.cur = +e.target.value; salvar(); upd(S.cur); } }),
          R.revisao != null && mg.revisao != null && R.revisao !== mg.revisao ? h("div", { class: "nd", html: `<b>Atenção</b> — a rodada usou o inventário rev. ${esc(R.revisao)}; o inventário atual é rev. ${esc(mg.revisao)}.` }) : null,
          h("button", { class: "pill", style: "margin-top:8px", onclick: () => ir({ type: "abrir_rodada", run: R.uid }) }, "Abrir esta rodada na Partitura")) : null),
      n ? h("div", { class: "card acc", style: `--acc:${TP[n.tipo].c}` }, h("h3", { html: `${esc(TP[n.tipo].n)}<span class="tag">selecionado</span>` }), h("div", { class: "big", style: "font-size:18px" }, n.nome),
        h("div", { class: "uid" }, [n.tag, n.uid].filter(Boolean).join(" · ")), h("div", { class: "kv", html: kvh((n.detalhes || []).concat(R && n.p !== undefined ? [[`Em ${ivl(S.cur)}`, kwTxt(n, S.cur)], ["Estado", estadoTxt(n, S.cur) || "—"]] : [])) }),
        !n.habilitado ? h("div", { class: "nd", html: "Equipamento <b>desabilitado</b> no inventário." }) : null,
        R && n.p === undefined && n.habilitado ? h("div", { class: "nd", html: "Este equipamento <b>não participou</b> da rodada escolhida (não há valores gravados para o UID dele)." }) : null,
        h("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-top:10px" }, R && PAINEL[n.tipo] && n.p !== undefined ? h("button", { class: "pill on pl-abrir", onclick: () => abrirPainel(n) }, "Abrir o painel na rodada") : null,
          n.tipo !== "dem" && n.tipo !== "grid" ? h("button", { class: "pill", onclick: () => ir({ type: "nav", view: "gestao" }) }, "Ver no inventário") : null)) :
        h("div", { class: "card" }, h("h3", { html: "Equipamento" }), h("p", { class: "note", html: "Passe o mouse ou use Tab para destacar um equipamento; clique ou Enter o seleciona." })),
      h("div", { class: "card" }, h("h3", { html: "Como ler" }), h("p", { class: "note", html: "A microrrede é desenhada como o modelo a enxerga: um <b>barramento equivalente</b>, o que injeta acima, o que armazena ou consome abaixo. As ligações só indicam que o equipamento está no barramento: <b>não há ramos nem fluxos por linha</b>, porque o modelo não os calcula." + (R ? " Com uma rodada, cada nó mostra a potência média GRAVADA do intervalo; ligação apagada = potência gravada nula; tracejada = dado ausente." : "") }))].filter(Boolean)); };
  let upd = () => {};
  const desenhar = () => {
    // nó = cartão com o ícone da tecnologia num CÍRCULO claro (identidade do Gestor), nome, tipo, nominal do inventário e o
    // estado; a ligação desce/sobe até o barramento e termina num ponto de conexão. Sem setas nem fluxos.
    const nMax = Math.max(M.cima.length, M.baixo.length, 1), Wd = Math.max(wrap.clientWidth - 28, 300), bw = Math.max(236, Math.min(290, (Wd - 40) / nMax - 20)), W = Math.max(Wd, nMax * (bw + 20) + 40), bh = 104, H = 446, yb = H / 2, ys = [yb - bh - 60, yb + 60];
    const s = sv("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "group", "aria-label": "Planta: barramento equivalente único", class: "pl-svg", style: "display:block" });
    s.append(sv("line", { x1: 24, x2: W - 24, y1: yb, y2: yb, class: "pl-barra", "stroke-linecap": "round" }), sv("text", { x: 30, y: yb - 14, class: "pl-bus" }, "BARRAMENTO EQUIVALENTE"));
    const curto = (t, n) => (String(t).length > n ? String(t).slice(0, n - 1) + "…" : String(t)), cab = Math.max(12, Math.floor((bw - 96) / 7.2));
    [M.cima, M.baixo].forEach((fila, row) => fila.forEach((n, j) => { const x = (W * (2 * j + 1)) / (2 * fila.length), y = ys[row], up = !row, tp = TP[n.tipo], c = tp.c, x0 = x - bw / 2, tx = x0 + 82;
      const g = sv("g", { class: "node" + (n.habilitado ? "" : " dis") + (S.sel === n.uid ? " sel" : ""), tabindex: 0, role: "button", "data-uid": n.uid, "data-tipo": n.tipo, "aria-label": `${tp.n} · ${n.nome}${n.resumo ? " · " + n.resumo : ""}: selecionar`, style: `--k:${c}` });
      const yc = up ? y + bh : y, wire = sv("line", { class: "wire", x1: x, x2: x, y1: yc, y2: yb, style: `stroke:${c}` }), pw = sv("text", { x: x0 + bw - 16, y: y + 69, "text-anchor": "end", class: "pw" }), sb = sv("text", { x: tx, y: y + 88, class: "sb" });
      const ic = sv("g", { class: "ico", transform: `translate(${x0 + 18} ${y + bh / 2 - 23})` });
      ic.append(sv("circle", { cx: 23, cy: 23, r: 23, class: "ico-fundo" })); const gi = sv("g", { transform: "translate(8 8)" }); gi.innerHTML = ICO_PL[tp.ico] || ICO_PL.outro;
      const isv = gi.firstElementChild; if (isv) { isv.setAttribute("width", 30); isv.setAttribute("height", 30); } ic.append(gi);
      g.append(wire, sv("circle", { cx: x, cy: yb, r: 5, class: "pino" }), sv("rect", { class: "bx", x: x0, y, width: bw, height: bh, rx: 16 }), ic,
        sv("text", { x: tx, y: y + 27, class: "tp" }, curto([tp.cn, n.tag].filter(Boolean).join(" · ").toUpperCase(), cab + 2)),
        sv("text", { x: tx, y: y + 48, class: "nm" }, curto(n.nome, cab)),
        sv("text", { x: tx, y: y + 69, class: "rs" }, n.resumo ? curto(n.resumo, R ? Math.max(6, cab - 6) : cab + 6) : n.tipo === "dem" && !R ? "agregada da microrrede" : ""), pw, sb);
      refs[n.uid] = { g, wire, pw, sb, n };
      const on = () => { Object.values(refs).forEach((o) => o.g.classList.toggle("off", o.n.uid !== n.uid)); g.classList.add("on"); const b = g.querySelector("rect.bx").getBoundingClientRect(), pr = wrap.getBoundingClientRect();
        pop.hidden = false; pop.innerHTML = `<div class="eyebrow" style="color:${c}">${esc(tp.n)}</div><b class="pn">${esc(n.nome)}</b><div class="uid">${esc([n.tag, n.uid].filter(Boolean).join(" · "))}</div><div class="kv" style="margin-top:8px">${kvh((n.detalhes || []).concat(R && n.p !== undefined ? [[`Em ${ivl(S.cur)}`, kwTxt(n, S.cur)]] : []))}</div><p class="note">${esc(estadoTxt(n, S.cur) || (R ? "" : "inventário salvo"))}</p><p class="note" style="color:var(--ink-2)">Clique ou Enter seleciona</p>`;
        const lx = b.left - pr.left + wrap.scrollLeft; pop.style.left = Math.max(8, lx + b.width + 12 > wrap.scrollLeft + pr.width - 262 ? lx - 262 : lx + b.width + 12) + "px"; pop.style.top = Math.max(8, Math.min(H - pop.offsetHeight - 8, b.top - pr.top)) + "px"; };
      const off = () => { Object.values(refs).forEach((o) => o.g.classList.remove("off", "on")); pop.hidden = true; };
      const escolher = () => { S.sel = S.sel === n.uid ? null : n.uid; salvar(); Object.values(refs).forEach((o) => o.g.classList.toggle("sel", o.n.uid === S.sel)); cartoes(); };
      g.addEventListener("pointerenter", on); g.addEventListener("pointerleave", off); g.addEventListener("focus", on); g.addEventListener("blur", off);
      g.addEventListener("click", escolher); g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); escolher(); } });
      s.append(g); }));
    if (!(D.nos || []).length) s.append(sv("text", { x: W / 2, y: ys[0] + bh / 2, "text-anchor": "middle", class: "pl-vazio" }, "Inventário sem equipamentos: nada injeta no barramento."));
    upd = (i) => { Object.values(refs).forEach((o) => { const n = o.n, v = el(n.p, i); o.pw.textContent = R ? kwTxt(n, i) : ""; o.sb.textContent = curto(estadoTxt(n, i), cab + 6);
      o.wire.style.opacity = !R || n.p === undefined ? (n.habilitado ? .6 : .2) : v == null ? .8 : Math.abs(v) > 1e-6 ? 1 : .22; o.wire.setAttribute("stroke-dasharray", R && n.p !== undefined && v == null ? "4 4" : ""); });
      const t = col.querySelector(".pl-inst"); if (t) t.textContent = ivl(i); const sl = col.querySelector(".pl-t"); if (sl && +sl.value !== i) sl.value = i; if (S.sel) { const k = col.querySelector(".card.acc .kv"); if (k && R) cartoes(); } };
    wrap.replaceChildren(s, pop); upd(S.cur);
  };
  cartoes(); root.replaceChildren(h("div", { class: "stage pl-stage" }, wrap, col));
  setTimeout(desenhar);
  if (!root.__ro && typeof ResizeObserver !== "undefined") { let lw = 0, t = null; root.__ro = new ResizeObserver(() => { const w = root.clientWidth; if (Math.abs(w - lw) < 2) return; lw = w; clearTimeout(t); t = setTimeout(() => root.__redesenha && root.__redesenha(), 140); }); root.__ro.observe(root); }
  root.__redesenha = desenhar;
}
