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
const nf = (v, d = 1) => (v == null || Number.isNaN(v) ? "N/D" : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }));
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
  const cursor = sv("rect", { x: x(cur), y: 0, width: cw, height: H - axisH, rx: 3, "pointer-events": "none" });
  const mark = sv("path", { "pointer-events": "none", style: "fill:var(--ink)" });
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
  if (o.near) { const tip = h("div", { class: "tip", hidden: true }), ring = sv("circle", { r: 5.5, fill: "none", style: "stroke:var(--ink);stroke-width:1.6", visibility: "hidden" }); svg.append(ring); host.append(tip);
    svg.addEventListener("pointermove", (ev) => { const r = svg.getBoundingClientRect(), mx = (ev.clientX - r.left) * (W / r.width), q = o.near(o.x[0] + ((mx - pl) / (W - pl - pr)) * (o.x[1] - o.x[0])); if (!q) return;
      ring.setAttribute("cx", X(q.x)); ring.setAttribute("cy", Y(q.y)); ring.setAttribute("visibility", "visible"); tip.hidden = false; tip.innerHTML = q.html; const px = (X(q.x) / W) * host.clientWidth; tip.style.left = Math.max(0, px > host.clientWidth * .6 ? px - tip.offsetWidth - 12 : px + 12) + "px"; tip.style.top = "30px"; });
    svg.addEventListener("pointerleave", () => { tip.hidden = true; ring.setAttribute("visibility", "hidden"); }); }
}
