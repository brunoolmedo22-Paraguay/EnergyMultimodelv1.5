// Inventário da microrrede: cartões por equipamento com os três níveis de estado
// (registrado → tecnicamente configurado → compatível com a simulação), busca e filtro no cliente.
// Eventos: {type:"open", id} | {type:"add"}.
const ICONS = {
  pv: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 22l4-12h14l4 12z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M7 16h18M14 10l-2 12M18 10l2 12" stroke="currentColor" stroke-width="1.5" opacity=".7"/><path d="M16 22v5M11 27h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
  wind: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 14v15M13 29h6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="16" cy="12" r="2" fill="currentColor"/><path d="M16 10c-1-4 0-7 2-8 1 3 0 6-2 8zM18 13c4 1 6 3 6 5-3 0-5-2-6-5zM14 13c-3 2-6 3-8 2 1-3 5-3 8-2z" fill="currentColor" opacity=".85"/></svg>`,
  battery: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="9" width="20" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><rect x="25" y="13" width="3" height="6" rx="1" fill="currentColor"/><rect x="8" y="12" width="5" height="8" rx="1" fill="currentColor" opacity=".8"/><rect x="14" y="12" width="5" height="8" rx="1" fill="currentColor" opacity=".45"/></svg>`,
  pemfc: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="6" y="7" width="14" height="18" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 7v18M13 7v18M16 7v18" stroke="currentColor" stroke-width="1.3" opacity=".6"/><path d="M20 12h4c2 0 3 1 3 3v2c0 2-1 3-3 3h-4" fill="none" stroke="currentColor" stroke-width="2"/><text x="23" y="30" font-size="7" fill="currentColor" font-weight="700">H₂</text></svg>`,
  thermal: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="14" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M23 18h3v8M9 14V9h4v5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M11 6c0-2 2-2 2-4M15 8c0-2 2-2 2-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".7"/><circle cx="14" cy="20" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`,
};
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.textContent = text; return e; }

function build(parent) {
  const root = el("div", "sd inv");
  const bar = el("div", "inv-bar");
  const search = el("input", "sd-input inv-search"); search.type = "search"; search.placeholder = "Buscar por nome, TAG, referência ou id…";
  search.setAttribute("aria-label", "Buscar equipamentos");
  const fKind = el("select", "sd-select"); fKind.setAttribute("aria-label", "Filtrar por tecnologia");
  const fState = el("select", "sd-select"); fState.setAttribute("aria-label", "Filtrar por estado na simulação");
  const count = el("span", "inv-count");
  bar.append(search, fKind, fState, count);
  const grid = el("div", "inv-grid"); grid.setAttribute("role", "list");
  root.append(bar, grid);
  parent.appendChild(root);
  const ctl = { root, grid, search, fKind, fState, count, data: null, send: null };
  root.__ctl = ctl;
  const rerender = () => render(ctl);
  search.addEventListener("input", rerender); fKind.addEventListener("change", rerender); fState.addEventListener("change", rerender);
  return root;
}

function fill(sel, items, allLabel) {
  const cur = sel.value; sel.innerHTML = "";
  const all = el("option", null, allLabel); all.value = ""; sel.appendChild(all);
  for (const [v, t] of items) { const o = el("option", null, t); o.value = v; sel.appendChild(o); }
  sel.value = items.some(([v]) => v === cur) ? cur : "";
}

function card(d, send, i, readonly) {
  const c = el("article", `inv-card k-${d.kind}${d.enabled ? "" : " is-off"}`); c.setAttribute("role", "listitem"); c.tabIndex = 0;
  c.style.animationDelay = `${Math.min(i, 12) * 30}ms`; c.dataset.id = d.id;
  const head = el("div", "inv-head");
  const ttl = el("div");
  ttl.append(el("div", "inv-kind", d.kind_label), el("h3", "inv-name", d.name), el("div", "inv-sub", d.reference_label || "Referência técnica não declarada"));
  const ic = el("div", "inv-icon"); ic.innerHTML = ICONS[d.kind] || "";
  head.append(ttl, ic);
  const states = el("div", "inv-states");
  for (const s of d.badges) { const b = el("span", `sd-badge ${s.tone}`, s.text); if (s.title) b.title = s.title; states.appendChild(b); }
  const meta = el("div", "inv-meta");
  for (const [k, v] of d.facts) { const b = el("div", "inv-kv"); b.append(el("span", "k", k), el("span", "v", v)); b.title = `${k}: ${v}`; meta.appendChild(b); }
  const parts = [head, states, meta];
  if (d.reason) parts.push(el("div", `inv-reason ${d.reason_tone || ""}`, d.reason));
  const foot = el("div", "inv-foot");
  foot.append(el("span", "sd-chip", d.id), el("span", null, d.tag ? `TAG ${d.tag}` : ""));
  parts.push(foot);
  c.append(...parts);
  if (!readonly) {
    const open = () => send && send("action", { type: "open", id: d.id, t: Date.now() });
    c.addEventListener("click", open);
    c.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    c.setAttribute("aria-label", `${d.kind_label}: ${d.name}. Abrir para editar.`);
  }
  return c;
}

function addCard(send, empty) {
  const c = el("article", `inv-card inv-add${empty ? " big" : ""}`); c.setAttribute("role", "listitem"); c.tabIndex = 0;
  c.setAttribute("aria-label", "Adicionar equipamento");
  c.append(el("div", "plus", "+"), el("div", "add-t", "Adicionar equipamento"),
    el("div", "add-s", empty ? "Ainda não há equipamentos registrados. Basta um nome e a tecnologia; os parâmetros técnicos podem ser completados depois."
                             : "Solar, eólica, bateria, PEMFC ou térmica. Várias unidades da mesma tecnologia são permitidas."));
  const go = () => send && send("action", { type: "add", t: Date.now() });
  c.addEventListener("click", go);
  c.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
  return c;
}

function render(ctl) {
  const d = ctl.data; if (!d) return;
  const q = ctl.search.value.trim().toLowerCase();
  const rows = d.items.filter((x) => (!q || [x.name, x.tag, x.reference_label, x.id].join(" ").toLowerCase().includes(q))
    && (!ctl.fKind.value || x.kind === ctl.fKind.value) && (!ctl.fState.value || x.sim_status === ctl.fState.value));
  ctl.grid.innerHTML = "";
  rows.forEach((x, i) => ctl.grid.appendChild(card(x, ctl.send, i, d.readonly)));
  const empty = d.items.length === 0;
  if (!d.readonly && !q && !ctl.fKind.value && !ctl.fState.value) ctl.grid.appendChild(addCard(ctl.send, empty));
  else if (!rows.length) ctl.grid.appendChild(el("div", "inv-none", empty ? "Nenhum equipamento registrado." : "Nenhum equipamento corresponde à busca ou aos filtros."));
  ctl.count.textContent = empty ? "" : `${rows.length} de ${d.items.length}`;
}

export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  let root = parentElement.querySelector(".inv");
  if (!root) root = build(parentElement);
  const ctl = root.__ctl;
  ctl.send = setTriggerValue; ctl.data = data;
  fill(ctl.fKind, data.kinds, "Todas as tecnologias");
  fill(ctl.fState, data.states, "Todos os estados");
  render(ctl);
}
