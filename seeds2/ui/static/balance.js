// Esquema LÓGICO do balanço energético (gerado da configuração salva). NÃO é um diagrama unifilar:
// não há barramentos, tensões, conversores nem conexões físicas — apenas a agregação de potência/energia
// que o EMS realiza: fontes e armazenamento → balanço agregado → atendimento da demanda.
const GLYPH = { representado: "✓", incompativel: "!", incompleto: "!", desabilitado: "–" };
const ARROW = `<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M6 20h24" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/><path d="M24 13l8 7-8 7" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
function el(t, c, x) { const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; }
function src(n, i) {
  const d = el("div", `bal-src k-${n.kind}${n.enabled ? "" : " off"}`); d.style.animationDelay = `${i * 35}ms`;
  d.title = n.status_label || "";
  const tx = el("div", "tx"); tx.append(el("b", null, n.name), el("small", null, `${n.kind_label}${n.detail ? " · " + n.detail : ""}`));
  d.append(el("span", "bal-dot"), tx);
  if (n.status) { const s = el("span", `bal-st ${n.status}`, GLYPH[n.status] || ""); s.setAttribute("aria-label", n.status_label || ""); d.appendChild(s); }
  return d;
}
export default function (component) {
  const { data, parentElement } = component;
  let root = parentElement.querySelector(".bal");
  if (!root) { root = el("div", "sd bal"); parentElement.appendChild(root); }
  root.innerHTML = "";
  const flow = el("div", "bal-flow"); flow.setAttribute("role", "img");
  flow.setAttribute("aria-label", `Esquema lógico do balanço energético: ${data.sources.length + data.storage.length} fonte(s) e armazenamento → balanço agregado → demanda`);
  const c1 = el("div", "bal-col");
  c1.appendChild(el("div", "bal-h", "Fontes"));
  if (!data.sources.length) c1.appendChild(el("div", "bal-empty", "Nenhuma fonte registrada."));
  data.sources.forEach((n, i) => c1.appendChild(src(n, i)));
  c1.appendChild(el("div", "bal-h", "Armazenamento"));
  if (!data.storage.length) c1.appendChild(el("div", "bal-empty", "Nenhum armazenamento registrado."));
  data.storage.forEach((n, i) => c1.appendChild(src(n, i + data.sources.length)));
  const a1 = el("div", "bal-arrow"); a1.innerHTML = ARROW;
  const c2 = el("div", "bal-col");
  const core = el("div", "bal-core");
  core.append(el("b", null, "Balanço energético agregado"), el("span", null, data.core_note));
  c2.appendChild(core);
  const a2 = el("div", "bal-arrow"); a2.innerHTML = ARROW;
  const c3 = el("div", "bal-col");
  c3.appendChild(el("div", "bal-h", "Demanda"));
  const sink = el("div", "bal-sink"); sink.append(el("b", null, "Atendimento da demanda"), el("small", null, data.demand_note));
  c3.appendChild(sink);
  if (data.grid) {
    const g = el("div", "bal-grid"); g.append(el("b", null, data.grid.title), el("span", null, data.grid.note));
    c3.appendChild(g);
  }
  flow.append(c1, a1, c2, a2, c3);
  root.appendChild(flow);
  const lg = el("div", "bal-legend");
  for (const [k, t] of [["representado", "Representado no EMS"], ["incompleto", "Configuração incompleta"], ["incompativel", "Não representável"], ["desabilitado", "Desabilitado"]]) {
    const s = el("span"); s.append(el("i", `bal-st ${k}`, GLYPH[k]), el("span", null, t)); lg.appendChild(s);
  }
  root.appendChild(lg);
  root.appendChild(el("div", "bal-note", data.scope_note));
}
