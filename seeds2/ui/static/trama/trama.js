// TRAMA — motor de raias temporais do SEEDS2 (Piso 3D-B0). Uma malha (N intervalos, N + 1 fronteiras), várias raias, um cursor.
// Grandezas de INTERVALO ocupam [τ_g, τ_g+1) (degrau/barra); estados de FRONTEIRA são pontos em τ_k. Nenhum valor é
// interpolado para exibição: o que se desenha e o que se lê são os números recebidos do Python. Passar o mouse, fixar,
// focar e ampliar acontecem só no navegador (nenhum rerun do Streamlit). Sem dependências externas.
const NS = "http://www.w3.org/2000/svg";
function sv(tag, a = {}, kids = []) { const e = document.createElementNS(NS, tag); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); for (const c of [].concat(kids)) if (c != null) e.append(c); return e; }
function h(tag, a = {}, ...kids) {
  const e = document.createElement(tag);
  for (const k in a) { if (a[k] == null || a[k] === false) continue; if (k === "html") e.innerHTML = a[k]; else if (k.startsWith("on")) e.addEventListener(k.slice(2), a[k]); else e.setAttribute(k, a[k] === true ? "" : a[k]); }
  for (const c of kids.flat(2)) if (c != null && c !== false) e.append(c);
  return e;
}
// Formatação (só apresentação): ausente = "N/D"; um zero com sinal negativo — o −0.0 do solver ou um valor negativo que
// ARREDONDA para zero na precisão mostrada — é exibido como zero ("0,0", nunca "-0,0"). Os números gravados não mudam.
const nf = (v, d = 1) => { if (v == null || Number.isNaN(v)) return "N/D"; const s = Number(v).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }); return /^-0(,0*)?$/.test(s) ? s.slice(1) : s; };
const ne = (v, d = 1) => { if (v == null || Number.isNaN(v)) return "N/D"; const s = Number(v).toExponential(d); return /^-0(\.0*)?e[+-]0$/.test(s) ? s.slice(1) : s; };
const COR = { wt: "var(--s-wt)", fv: "var(--s-fv)", bat: "var(--s-bat)", fc: "var(--s-fc)", grid: "var(--s-grid)", dem: "var(--s-dem)", eco: "var(--s-eco)" };
const novoBarramento = () => ({ subs: [], emit(i, src) { this.subs.forEach((f) => f(i, src)); }, clear() { this.subs = []; } });
let TRAMA_ID = 0;

function trama(host, o) {
  const BUS = o.bus || novoBarramento(), hh = o.lab || ((i) => String(i)), id = ++TRAMA_ID, W = Math.max(host.clientWidth || 0, 300), K = o.K, padL = o.padL ?? 46, padR = o.padR ?? 10, axisH = 20;
  const v0 = o.view ? o.view[0] : 0, v1 = o.view ? o.view[1] : K, cw = (W - padL - padR) / (v1 - v0);
  let total = o.lanes.reduce((a, L) => a + L.h + 12, 4) + axisH;
  const avail = o.fill ? host.clientHeight : 0, sumW = o.lanes.reduce((a, L) => a + (L.w ?? 1), 0), extra = Math.max(0, avail - total);
  const hs = o.lanes.map((L) => L.h + (extra * (L.w ?? 1)) / sumW);
  let H = 4; const tops = hs.map((x) => { const t = H; H += x + 12; return t; }); H += axisH;
  const svg = sv("svg", { class: "trama", width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", tabindex: 0, "aria-label": o.label || "Linha do tempo" });
  const x = (i) => padL + (i - v0) * cw;
  svg.append(sv("defs", {}, sv("clipPath", { id: "trclip" + id }, sv("rect", { x: padL, y: 0, width: W - padL - padR, height: H }))));
  const plot = sv("g", { "clip-path": `url(#trclip${id})` });
  for (let b = Math.ceil(v0); b <= v1; b++) svg.append(sv("line", { x1: x(b), x2: x(b), y1: 0, y2: H - axisH, class: "gr", "stroke-dasharray": b % (o.major || 6) ? "1 5" : null }));
  const passo = Math.max(1, Math.ceil((o.labW || 42) / cw));
  for (let b = Math.ceil(v0); b <= v1; b += passo) svg.append(sv("text", { x: x(b), y: H - 5, "text-anchor": "middle", class: "v" }, hh(b)));
  if (o.band) plot.append(sv("rect", { x: x(o.band[0]), y: 0, width: (o.band[1] - o.band[0]) * cw, height: H - axisH, style: "fill:var(--ink);opacity:.05" }), sv("rect", { x: x(o.band[0]) + .75, y: .75, width: (o.band[1] - o.band[0]) * cw - 1.5, height: H - axisH - 1.5, rx: 4, fill: "none", style: "stroke:var(--ink-3)", "stroke-dasharray": "3 3" }));
  o.lanes.forEach((L, n) => {
    const g = sv("g"), y0 = tops[n], hl = hs[n];
    const tt = sv("text", { x: padL, y: y0 + 11, class: "t" + (L.res ? " lk" : "") }, L.title + (L.res ? "  ↗" : ""));
    if (L.res && o.onRes) { tt.setAttribute("tabindex", 0); tt.setAttribute("role", "button"); const go = (e) => { e.stopPropagation(); o.onRes(L.res); }; tt.addEventListener("click", go); tt.addEventListener("keydown", (e) => { if (e.key === "Enter") go(e); }); }
    svg.append(tt);
    if (L.note && W > 620) svg.append(sv("text", { x: W - padR, y: y0 + 11, "text-anchor": "end" }, L.note));
    const c = {
      g, K, cw, x, W, padL, padR, top: y0 + 20, bot: y0 + hl,
      sc(lo, hi) { const t = this.top, b = this.bot; return (v) => b - ((v - lo) / (hi - lo || 1)) * (b - t); },
      grid(y, ticks, f = (v) => nf(v, 0)) { ticks.forEach((v) => { svg.append(sv("line", { x1: padL, x2: W - padR, y1: y(v), y2: y(v), class: v === 0 ? "ax" : "gr" }), sv("text", { x: padL - 6, y: y(v) + 3.5, "text-anchor": "end", class: "v" }, f(v))); }); },
      stack(series, y, opt = {}) {
        const vivas = series.filter((s) => s.v !== undefined);          // undefined = recurso não aplicável
        if (vivas.some((s) => s.v === null)) this.nd();                   // null = série não persistida ⇒ N/D, nunca zero
        const b0 = opt.b0 || 0;                                            // b0 = intervalo da missão do 1º valor (planos de janela)
        for (let i = 0; i < (opt.n ?? K); i++) { let acc = 0;
          if (vivas.some((s) => s.v && s.v[i] == null)) g.append(sv("text", { x: x(b0 + i + .5), y: y(0) - 4, "text-anchor": "middle", class: "v nd" }, "N/D"));
          for (const s of vivas) { if (!s.v) continue; const v = s.v[i] || 0; if (v <= 1e-6) continue;
            const a = y(opt.neg ? -acc : acc), b = y(opt.neg ? -(acc + v) : acc + v), hg = Math.abs(a - b), gp = hg > 3 ? 1 : 0;
            g.append(sv("rect", { x: x(b0 + i) + 1, y: Math.min(a, b) + gp, width: Math.max(cw - 2, 1), height: Math.max(hg - gp, .8), rx: Math.min(2.5, cw / 6), "data-k": s.k, style: `fill:${s.hatch ? `url(#${o.pat || "h"}-${s.hatch})` : s.c};opacity:${opt.op ? opt.op(i) : 1}` }));
            acc += v; } }
      },
      nd(msg) { if (this._nd) return; this._nd = true; g.append(sv("text", { x: x(v0 + .15), y: this.top + 13, class: "nd" }, "N/D — " + (msg || "série não persistida nesta rodada"))); },
      step(vals, y, st = {}) { if (vals === undefined) return; if (vals === null) return this.nd(); let d = ""; let aberto = false; vals.forEach((v, j) => { if (v == null) { aberto = false; return; } d += `${aberto ? "L" : "M"}${x((st.b0 || 0) + j)},${y(v)}H${x((st.b0 || 0) + j + 1)}`; aberto = true; }); g.append(sv("path", { d, fill: "none", "data-k": st.k, style: `stroke:${st.c || COR.dem};stroke-width:${st.w || 2}`, "stroke-dasharray": st.dash, "stroke-linejoin": "round", opacity: st.op })); },
      front(vals, y, st = {}, b0 = 0) {
        if (vals === undefined) return; if (vals === null) return this.nd();
        const todos = vals.map((v, j) => (v == null ? null : [x(b0 + j), y(v)])), pts = todos.filter(Boolean), trechos = [[]];
        todos.forEach((p) => { if (p) trechos[trechos.length - 1].push(p); else if (trechos[trechos.length - 1].length) trechos.push([]); });   // ausente interrompe a linha
        trechos.filter((t) => t.length).forEach((t) => g.append(sv("polyline", { points: t.map((p) => p.join(",")).join(" "), fill: "none", "data-k": st.k, style: `stroke:${st.c || COR.bat};stroke-width:${st.w || 2}`, "stroke-dasharray": st.dash, opacity: st.op, "stroke-linejoin": "round" })));
        if (st.dots !== false) pts.forEach((p) => g.append(sv("circle", { cx: p[0], cy: p[1], r: st.r || 2.6, "data-k": st.k, style: `fill:${st.hollow ? "var(--surface)" : st.c || COR.bat};stroke:${st.hollow ? st.c || COR.bat : "var(--surface)"};stroke-width:1.5`, opacity: st.op })));
      },
      dots(vals, y, st = {}) { if (!vals) return; vals.forEach((v, i) => { if (v == null) return; g.append(sv("circle", { cx: x(i + .5), cy: y(v), r: st.r || 3, "data-k": st.k, style: `fill:var(--surface);stroke:${st.c || "var(--ink)"};stroke-width:1.6` })); }); },
      hline(v, y, label, st = {}) { svg.append(sv("line", { x1: padL, x2: W - padR, y1: y(v), y2: y(v), style: `stroke:${st.c || "var(--ink-3)"}`, "stroke-dasharray": "5 4" })); if (label) svg.append(sv("text", { x: W - padR - 2, y: y(v) - 4, "text-anchor": "end" }, label)); },
      strip(vals, yy, hgt, col, lab) { if (vals === undefined) return; if (vals === null) return this.nd(); vals.forEach((t, i) => { g.append(sv("rect", { x: x(i) + 1, y: yy, width: Math.max(cw - 2, 1), height: hgt, rx: 3, style: `fill:${col(t, i)}` })); if (lab && cw > 30) { const s = lab(t, i); if (s) g.append(sv("text", { x: x(i + .5), y: yy + hgt / 2 + 3.5, "text-anchor": "middle", class: "v", style: `fill:${s[1] || "var(--ink)"}${s[2] ? ";paint-order:stroke;stroke:var(--surface);stroke-width:3px" : ""}` }, s[0])); } }); },
      text(i, yy, s, a = {}) { g.append(sv("text", { x: x(i), y: yy, ...a }, s)); },
      add(e) { g.append(e); return e; },
      out(e) { svg.append(e); return e; },
    };
    L.draw(c); plot.append(g);
  });
  svg.append(plot);
  let cur = Math.min(K - 1, Math.max(0, o.cur ?? 0)), pinned = !!o.pin;
  const cursor = sv("rect", { x: x(cur), y: 0, width: cw, height: H - axisH, rx: 3, "pointer-events": "none", class: "cur" });
  const mark = sv("path", { "pointer-events": "none", style: "fill:var(--ink)", class: "cur" });
  svg.setAttribute("data-janela", `${hh(Math.max(0, Math.ceil(v0)))}–${hh(Math.min(K, Math.floor(v1)))}` + (v0 > 0 || v1 < K ? " (janela ampliada)" : ""));
  const paint = () => { cursor.setAttribute("x", x(cur)); cursor.setAttribute("style", pinned ? "fill:var(--ink);opacity:.1;stroke:var(--ink);stroke-width:1.2;stroke-opacity:.9" : "fill:var(--ink);opacity:.08"); mark.setAttribute("d", pinned ? `M${x(cur + .5) - 5},0h10l-5,7z` : ""); };
  const tip = o.tip ? h("div", { class: "tip", hidden: true }) : null;
  const showTip = () => { if (!tip) return; tip.hidden = false; tip.innerHTML = o.tip(cur); const px = (x(cur + .5) / W) * host.clientWidth, left = px > host.clientWidth * .6 ? px - tip.offsetWidth - 14 : px + 14; tip.style.left = Math.max(0, left) + "px"; tip.style.top = (o.tipY ?? 26) + "px"; };
  const set = (i, fire = true) => { i = Math.min(K - 1, Math.max(0, i)); if (i === cur) return; cur = i; paint(); if (tip && !tip.hidden) showTip(); if (fire) { if (o.onCur) o.onCur(i); BUS.emit(i, id); } };
  const at = (ev) => { const r = svg.getBoundingClientRect(); return Math.floor(v0 + ((ev.clientX - r.left) * (W / r.width) - padL) / cw); };
  if (o.onCur || o.sync) {
    svg.append(cursor, mark); paint();
    BUS.subs.push((i, src) => { if (src !== id) { cur = Math.min(K - 1, Math.max(0, i)); paint(); } });
    svg.addEventListener("pointermove", (ev) => { const i = at(ev); if (i < 0 || i >= K) return; if (!pinned) set(i); if (tip) showTip(); });
    svg.addEventListener("pointerleave", () => { if (tip) tip.hidden = true; });
    svg.addEventListener("click", (ev) => { const i = at(ev); if (i < 0 || i >= K) return; const was = pinned && i === cur; pinned = false; set(i); pinned = !was; paint(); if (o.onPin) o.onPin(pinned ? i : null); });
    svg.addEventListener("keydown", (ev) => { const k = ev.key;
      if (k === "ArrowRight" || k === "ArrowLeft") { const p = pinned; pinned = false; set(cur + (k === "ArrowRight" ? 1 : -1)); pinned = p; paint(); if (p && o.onPin) o.onPin(cur); ev.preventDefault(); }
      if (k === "Enter" || k === " ") { pinned = !pinned; paint(); if (o.onPin) o.onPin(pinned ? cur : null); ev.preventDefault(); }
      if (k === "Escape" && pinned && o.escSolta !== false) { pinned = false; paint(); if (o.onPin) o.onPin(null); ev.stopPropagation(); } });
  }
  host.replaceChildren(svg); if (tip) host.append(tip);
  if (o.exp) exportavel(host, svg, o.exp);
  const focus = (k) => svg.querySelectorAll("[data-k]").forEach((e) => e.classList.toggle("dim", !!k && e.dataset.k !== k));
  if (o.focus) focus(o.focus);
  return { set, focus, svg };
}
// gráfico XY (não temporal): curva q(P), V(E), erro da aproximação
function xy(host, o) {
  const W = Math.max(host.clientWidth || 0, 280), H = o.h || Math.max(host.clientHeight || 0, 220), pl = 54, pr = 14, pt = 22, pb = 32;
  const svg = sv("svg", { class: "trama", width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.label });
  const X = (v) => pl + ((v - o.x[0]) / (o.x[1] - o.x[0] || 1)) * (W - pl - pr), Y = (v) => H - pb - ((v - o.y[0]) / (o.y[1] - o.y[0] || 1)) * (H - pt - pb);
  const nice = (lo, hi) => { const st = [1, 2, 2.5, 5, 10].map((m) => m * 10 ** Math.floor(Math.log10((hi - lo) / 4))).find((q) => (hi - lo) / q <= 6), out = []; for (let t = Math.ceil(lo / st - 1e-9) * st; t <= hi + 1e-9; t += st) out.push(+t.toFixed(10)); return out; };
  const dec = (ts) => Math.max(0, ...ts.map((t) => (String(t).split(".")[1] || "").length));
  const xt = o.xt || nice(o.x[0], o.x[1]), yt = o.yt || nice(o.y[0], o.y[1]);
  for (const xv of xt) { svg.append(sv("line", { x1: X(xv), x2: X(xv), y1: pt, y2: H - pb, class: "gr" }), sv("text", { x: X(xv), y: H - pb + 14, "text-anchor": "middle", class: "v" }, nf(xv, dec(xt)))); }
  for (const yv of yt) { svg.append(sv("line", { x1: pl, x2: W - pr, y1: Y(yv), y2: Y(yv), class: Math.abs(yv) < 1e-12 ? "ax" : "gr" }), sv("text", { x: pl - 6, y: Y(yv) + 3.5, "text-anchor": "end", class: "v" }, nf(yv, dec(yt)))); }
  svg.append(sv("text", { x: (pl + W - pr) / 2, y: H - 4, "text-anchor": "middle" }, o.xl), sv("text", { x: 4, y: 12, class: "t" }, o.yl));
  o.draw({ svg, X, Y, H, W, pt, pb, pl, pr });
  host.replaceChildren(svg);
  if (o.exp) exportavel(host, svg, o.exp);
  if (o.near) { const tip = h("div", { class: "tip", hidden: true }), ring = sv("circle", { r: 5.5, fill: "none", style: "stroke:var(--ink);stroke-width:1.6", visibility: "hidden" }); svg.append(ring); host.append(tip);
    svg.addEventListener("pointermove", (ev) => { const r = svg.getBoundingClientRect(), mx = (ev.clientX - r.left) * (W / r.width), q = o.near(o.x[0] + ((mx - pl) / (W - pl - pr)) * (o.x[1] - o.x[0])); if (!q) return;
      ring.setAttribute("cx", X(q.x)); ring.setAttribute("cy", Y(q.y)); ring.setAttribute("visibility", "visible"); tip.hidden = false; tip.innerHTML = q.html; const px = (X(q.x) / W) * host.clientWidth; tip.style.left = Math.max(0, px > host.clientWidth * .6 ? px - tip.offsetWidth - 12 : px + 12) + "px"; tip.style.top = "30px"; });
    svg.addEventListener("pointerleave", () => { tip.hidden = true; ring.setAttribute("visibility", "hidden"); }); }
}
// ---- utilitários puros de N/D, partilhados pela Partitura e pelos componentes de página (executados também em Node)
//   número = gravado · null = AUSENTE (N/D; contamina os derivados) · undefined = NÃO APLICÁVEL (omitido)
const agg = (ls, n) => (!ls.length ? undefined : ls.some((a) => a == null) ? null : Array.from({ length: n }, (_, i) => { let s = 0; for (const a of ls) { if (a[i] == null) return null; s += a[i]; } return s; }));
const el = (a, i) => (a == null ? a : a[i]);
const mais = (...xs) => { let s = 0; for (const x of xs) { if (x === null || Number.isNaN(x)) return null; if (x !== undefined) s += x; } return s; };
const vezes = (x, f) => (x == null ? x : x * f);
const menos = (a, b) => (a == null || b == null ? null : a - b);
// razão a ÷ b × f: null se faltar dado; undefined (não aplicável) se o denominador for zero
const razao = (a, b, f = 100) => (a == null || b == null ? null : b ? (f * a) / b : undefined);
const nfu = (v, d = 1, u = "") => (v === undefined ? "—" : v === null || Number.isNaN(v) ? "N/D" : nf(v, d) + u);
const mapa = (a, f) => (a == null ? a : a.map(f));
const conta = (a, f) => (a == null ? null : a.some((v) => v == null) ? null : a.filter(f).length);
const somaT = (a) => (a == null ? a : a.some((v) => v == null) ? null : a.reduce((x, y) => x + y, 0));
const acum = (a, f = 1) => { if (a == null) return a; let s = 0, ok = true; return [0, ...a.map((v) => { if (v == null) ok = false; return ok ? (s += v * f) : null; })]; };
// Termo OPCIONAL do objetivo. Uma série toda vazia só é «não aplicável» (undefined) com EVIDÊNCIA: os termos DECLARADOS
// na estratégia gravada (F.objetivo.termos) não incluem o termo. Termo declarado — ou declaração ilegível — com a série
// vazia/ausente é DADO AUSENTE (null ⇒ N/D). Valores gravados são sempre mostrados, declarado ou não.
const vazia = (a) => a == null || a.every((v) => v == null);
const declarado = (F, t) => (Array.isArray((F.objetivo || {}).termos) ? F.objetivo.termos.includes(t) : null);
const termo = (a, decl) => (!vazia(a) ? a : decl === false ? undefined : null);
const termoAgg = (ls, decl, n) => (!ls.length ? undefined : ls.every(vazia) ? (decl === false ? undefined : null) : agg(ls, n));
const maxv = (...arrs) => Math.max(0, ...arrs.flat().map((v) => (v == null || Number.isNaN(v) ? 0 : v)));
const teto = (v) => { if (!(v > 0)) return 1; const p = 10 ** Math.floor(Math.log10(v)); return [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].map((m) => m * p).find((x) => x >= v * 1.04) || 10 * p; };
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// ---- raiz e tema comuns aos componentes .pt (Partitura, barra lateral, Catálogo, Planta, Caderno, Folha)
function temaPt() {
  let t = null; try { t = localStorage.getItem("seeds2.partitura.tema"); } catch (_) { /* sem armazenamento */ }
  if (t !== "dark" && t !== "light") { const m = /rgba?\((\d+)[, ]+(\d+)[, ]+(\d+)/.exec(getComputedStyle(document.body).backgroundColor || ""); t = m && (0.2126 * m[1] + 0.7152 * m[2] + 0.0722 * m[3]) < 110 ? "dark" : "light"; }
  return t;
}
function raizPt(parentElement, cls) {
  let root = parentElement.querySelector(".pt"); const nova = !root;
  if (nova) { root = h("div", { class: "pt " + cls }); parentElement.appendChild(root); }
  root.dataset.theme = temaPt();
  return [root, nova];
}
const icoPt = (d, s = 20) => `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;

// ---- UI-FINISH-01 (ponto 5): exportar UM gráfico como PNG ou SVG, tema CLARO (publicação, padrão) ou ESCURO — independente
// do tema da tela. O SVG exportado é AUTOCONTIDO: os estilos são resolvidos sob o tema escolhido (num contêiner fora da
// tela, dentro do MESMO shadow root, para valerem as regras de trama.css) e gravados como atributos; padrões de hachura
// referenciados são copiados; cursor, foco (recuo das outras séries) e links «↗» — estado transitório da interface —
// saem; entram cabeçalho (título, identificação da rodada, janela exibida), legenda (a da própria figura) e rodapé
// (fontes; N/D = dado ausente, nunca zero). Os NÚMEROS e as formas são os do gráfico desenhado (dados gravados): nada é
// recalculado. PNG = rasterização desse SVG a 300 ppp (pHYs declarado) com metadados tEXt. Sem fontes embutidas.
const XP_PROPS = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray", "stroke-linecap", "stroke-linejoin",
  "opacity", "visibility", "display", "clip-path", "paint-order", "font-family", "font-size", "font-weight", "font-style", "letter-spacing", "text-anchor", "dominant-baseline"];
const XP_DPI = 300, XP_ESCALA = XP_DPI / 96;
const xpSlug = (t) => String(t || "grafico").normalize("NFKD").replace(/[^\x00-\x7F]/g, "").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 48) || "grafico";
const xpEsc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
function xpNome(meta, tema, ext) { return `seeds2_${xpSlug(meta.rodada || "rodada").slice(0, 8)}_${xpSlug(meta.titulo)}_${tema === "dark" ? "escuro" : "claro"}.${ext}`; }

function svgExport(svg, tema, meta) {
  const ptRoot = svg.closest(".pt"), raiz = svg.getRootNode(), W = +svg.getAttribute("width"), H = +svg.getAttribute("height");
  const box = h("div", { class: (ptRoot ? ptRoot.className : "pt"), "data-theme": tema, "aria-hidden": "true",
    style: `position:fixed;left:-100000px;top:0;width:${W}px;height:auto;pointer-events:none;contain:layout` });
  (ptRoot ? ptRoot.parentNode : document.body).append(box);
  try {
    const cl = svg.cloneNode(true);
    cl.querySelectorAll(".cur").forEach((e) => e.remove());
    cl.querySelectorAll(".dim").forEach((e) => e.classList.remove("dim"));
    cl.querySelectorAll("text").forEach((e) => { if (e.textContent.endsWith("↗")) e.textContent = e.textContent.replace(/\s*↗$/, ""); });
    // padrões referenciados (hachuras) entram no próprio arquivo
    const ids = new Set(); cl.querySelectorAll("[style*='url(#'],[fill*='url(#']").forEach((e) => { for (const m of ((e.getAttribute("style") || "") + (e.getAttribute("fill") || "")).matchAll(/url\(#([^)"']+)\)/g)) ids.add(m[1]); });
    let defs = cl.querySelector("defs"); if (!defs) { defs = sv("defs"); cl.prepend(defs); }
    ids.forEach((id) => { if (cl.querySelector("#" + CSS.escape(id))) return; const src = raiz.getElementById ? raiz.getElementById(id) : null; if (src) defs.append(src.cloneNode(true)); });
    box.append(cl);
    const vars = getComputedStyle(box), cor = (n, d) => (vars.getPropertyValue(n) || "").trim() || d;
    const fundo = cor("--surface", tema === "dark" ? "#1a1a1a" : "#ffffff"), tinta = cor("--ink", tema === "dark" ? "#f3f3f1" : "#111111"), suave = cor("--ink-3", "#777");
    // 1º resolve TODOS os estilos (com as classes ainda presentes: as regras de trama.css dependem de ancestrais como
    // «.trama»), depois grava e só então remove classes — senão os filhos perderiam as regras do pai.
    const todos = [cl, ...cl.querySelectorAll("*")], resolvidos = todos.map((e) => { const cs = getComputedStyle(e), est = [];
      for (const pr of XP_PROPS) { let v = cs.getPropertyValue(pr); if (!v || v === "normal" || (pr === "clip-path" && v === "none")) continue;
        if (/currentcolor/i.test(v)) v = v.replace(/currentcolor/ig, cs.color);             // o Chromium não resolve currentColor no estilo computado
        est.push(`${pr}:${v}`); }
      return est.join(";"); });
    todos.forEach((e, i) => { e.setAttribute("style", resolvidos[i]); e.removeAttribute("class"); e.removeAttribute("tabindex"); });
    // legenda da figura (as amostras e rótulos que a interface mostra junto do gráfico), resolvida no tema escolhido
    const sonda = h("i", {}); box.append(sonda);
    const legenda = (meta.legenda || []).map((it) => { sonda.setAttribute("style", it.estilo || ""); const c = getComputedStyle(sonda); return { t: it.t, c: c.backgroundColor, ht: !!it.ht }; });
    const fam = "DejaVu Sans, Arial, Helvetica, sans-serif", HD = 62, MR = 18, WT = W + MR, linhas = [], larg = WT - 24;
    let atual = [], w = 0; for (const it of legenda) { const lw = 34 + it.t.length * 7.2; if (w + lw > larg && atual.length) { linhas.push(atual); atual = []; w = 0; } atual.push([it, w]); w += lw; } if (atual.length) linhas.push(atual);
    // rodapé quebrado em linhas que cabem na largura (≈ 6,1 px por caractere a 10 px)
    const quebra = (txt) => { const max = Math.max(40, Math.floor((WT - 24) / 6.1)), out = []; let l = ""; for (const p of txt.split(" ")) { if ((l + " " + p).trim().length > max && l) { out.push(l); l = p; } else l = (l + " " + p).trim(); } if (l) out.push(l); return out; };
    const rod = [...quebra(`Fonte: ${(meta.fontes || []).join(" · ")} · N/D = dado ausente na rodada (nunca desenhado como zero).`),
      ...quebra(`SEEDS2 · exportado do gráfico da Partitura · tema ${tema === "dark" ? "escuro" : "claro"}${meta.aviso ? " · " + meta.aviso : ""}`)];
    const LG = linhas.length ? linhas.length * 18 + 8 : 0, FT = 14 + rod.length * 13, TOT = HD + H + LG + FT;
    const out = sv("svg", { xmlns: NS, width: WT, height: TOT, viewBox: `0 0 ${WT} ${TOT}`, "font-family": fam, role: "img", "aria-label": meta.titulo });
    out.append(sv("title", {}, meta.titulo), sv("desc", {}, meta.sub || ""),
      sv("metadata", {}, JSON.stringify({ formato: "seeds2-grafico", versao: 1, tema, titulo: meta.titulo, rodada: meta.rodada, cenario: meta.cenario,
        janela: svg.getAttribute("data-janela"), fontes: meta.fontes, gerado_em: new Date().toISOString(), nota: "Gráfico exportado da Partitura (dados gravados da rodada; nada recalculado)." })),
      sv("rect", { x: 0, y: 0, width: WT, height: TOT, style: `fill:${fundo}` }),
      sv("text", { x: 12, y: 24, style: `fill:${tinta};font-size:15px;font-weight:700` }, meta.titulo),
      sv("text", { x: 12, y: 42, style: `fill:${suave};font-size:11px` }, meta.sub || ""),
      sv("text", { x: 12, y: 56, style: `fill:${suave};font-size:10.5px` }, svg.getAttribute("data-janela") ? `Intervalos exibidos: ${svg.getAttribute("data-janela")}` : ""));
    const corpo = sv("svg", { x: 0, y: HD, width: W, height: H, viewBox: `0 0 ${W} ${H}`, overflow: "hidden" }); [...cl.childNodes].forEach((n) => corpo.append(n)); out.append(corpo);
    linhas.forEach((ln, i) => ln.forEach(([it, x0]) => { const y = HD + H + 14 + i * 18;
      out.append(sv("rect", { x: 12 + x0, y: y - 9, width: 16, height: 10, rx: 2, style: `fill:${it.c};${it.ht ? "fill-opacity:.45" : ""}` }), sv("text", { x: 12 + x0 + 22, y, style: `fill:${tinta};font-size:11px` }, it.t)); }));
    rod.forEach((l, i) => out.append(sv("text", { x: 12, y: HD + H + LG + 18 + i * 13, style: `fill:${suave};font-size:10px` }, l)));
    return { xml: '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(out), W: WT, H: TOT };
  } finally { box.remove(); }
}

const XP_CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function pngChunk(tipo, dados) {
  const b = new Uint8Array(12 + dados.length), dv = new DataView(b.buffer); dv.setUint32(0, dados.length);
  for (let i = 0; i < 4; i++) b[4 + i] = tipo.charCodeAt(i); b.set(dados, 8);
  let c = 0xffffffff; for (let i = 4; i < 8 + dados.length; i++) c = XP_CRC[(c ^ b[i]) & 0xff] ^ (c >>> 8); dv.setUint32(8 + dados.length, (c ^ 0xffffffff) >>> 0); return b;
}
// pHYs (300 ppp = 11811 px/m) + tEXt (latin-1 sem acentos) inseridos logo após o IHDR
function pngMetadados(png, textos) {
  const ppm = Math.round(XP_DPI / 0.0254), phys = new Uint8Array(9), dv = new DataView(phys.buffer); dv.setUint32(0, ppm); dv.setUint32(4, ppm); phys[8] = 1;
  const asc = (s) => Uint8Array.from(String(s).normalize("NFKD").replace(/[^\x20-\x7E]/g, ""), (c) => c.charCodeAt(0));
  const extra = [pngChunk("pHYs", phys), ...Object.entries(textos).map(([k, v]) => { const a = asc(k), b = asc(v), d = new Uint8Array(a.length + 1 + b.length); d.set(a); d.set(b, a.length + 1); return pngChunk("tEXt", d); })];
  const fim = 33, out = new Uint8Array(png.length + extra.reduce((x, c) => x + c.length, 0)); out.set(png.subarray(0, fim)); let p = fim;
  for (const c of extra) { out.set(c, p); p += c.length; } out.set(png.subarray(fim), p); return out;
}
function pngExport(svg, tema, meta) {
  const { xml, W, H } = svgExport(svg, tema, meta);
  return new Promise((ok, falha) => { const img = new Image();
    img.onload = () => { const cv = document.createElement("canvas"); cv.width = Math.round(W * XP_ESCALA); cv.height = Math.round(H * XP_ESCALA); const cx = cv.getContext("2d"); cx.scale(XP_ESCALA, XP_ESCALA); cx.drawImage(img, 0, 0, W, H);
      cv.toBlob((bl) => { if (!bl) return falha(new Error("PNG não gerado")); bl.arrayBuffer().then((ab) => ok({ bytes: pngMetadados(new Uint8Array(ab), { Title: meta.titulo, Software: "SEEDS2", Source: `rodada ${meta.rodada || ""}`, Description: meta.sub || "" }), w: cv.width, h: cv.height })); }, "image/png"); };
    img.onerror = () => falha(new Error("SVG de exportação inválido"));
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml); });
}
function xpBaixar(anc, nome, dados, mime) {
  const url = URL.createObjectURL(new Blob([dados], { type: mime })), a = h("a", { href: url, download: nome, style: "display:none" });
  anc.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 4000);
}
async function exportarGrafico(svg, fmt, tema, meta, anc) {
  if (fmt === "svg") { const { xml } = svgExport(svg, tema, meta); xpBaixar(anc, xpNome(meta, tema, "svg"), xml, "image/svg+xml"); return xml; }
  const r = await pngExport(svg, tema, meta); xpBaixar(anc, xpNome(meta, tema, "png"), r.bytes, "image/png"); return r;
}
function exportavel(host, svg, exp) {
  host.classList.add("xp-host");
  const meta = () => (typeof exp === "function" ? exp(svg) : exp);
  const menu = h("div", { class: "xp-menu", role: "menu", hidden: true, "aria-label": "Exportar este gráfico" });
  const btn = h("button", { class: "xp-btn", type: "button", title: "Exportar este gráfico (PNG ou SVG · tema claro ou escuro)", "aria-label": "Exportar este gráfico", "aria-haspopup": "menu", "aria-expanded": "false",
    html: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg><span>Exportar</span>' });
  const fechar = (foco) => { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); if (foco) btn.focus(); };
  [["png", "light", "PNG · claro (publicação)"], ["png", "dark", "PNG · escuro"], ["svg", "light", "SVG · claro (publicação)"], ["svg", "dark", "SVG · escuro"]].forEach(([f, t, rot]) =>
    menu.append(h("button", { type: "button", role: "menuitem", "data-xp": `${f}-${t}`, onclick: (e) => { e.stopPropagation(); fechar(true); exportarGrafico(svg, f, t, meta(), host).catch((er) => { menu.dataset.erro = String(er.message || er); }); } }, rot)));
  btn.addEventListener("click", (e) => { e.stopPropagation(); const abrir = menu.hidden; menu.hidden = !abrir; btn.setAttribute("aria-expanded", String(abrir)); if (abrir) setTimeout(() => menu.querySelector("button").focus(), 10); });
  menu.addEventListener("keydown", (e) => { const its = [...menu.querySelectorAll("button")], i = its.indexOf(e.target.getRootNode().activeElement || e.target);
    if (e.key === "Escape") { e.stopPropagation(); fechar(true); } else if (e.key === "ArrowDown") { e.preventDefault(); its[(i + 1) % its.length].focus(); } else if (e.key === "ArrowUp") { e.preventDefault(); its[(i - 1 + its.length) % its.length].focus(); } });
  host.addEventListener("pointerdown", (e) => { if (!menu.hidden && !menu.contains(e.target) && e.target !== btn && !btn.contains(e.target)) fechar(false); });
  host.append(btn, menu);
}
