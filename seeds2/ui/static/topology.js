// Esquema da microrrede gerado EXCLUSIVAMENTE a partir da configuração salva (não é um desenho decorativo):
// fontes acima do barramento comum; armazenamento e demanda abaixo; rede elétrica declarada à direita.
// Não representa fluxo de potência, tensões, proteções ou transitórios.
const NS = "http://www.w3.org/2000/svg";
const COLORS = { pv: "#E0891E", wind: "#2F6FED", battery: "#3C9D5D", pemfc: "#0E7C86", thermal: "#D1495B", load: "#7A4FD1", grid: "#5B6B7C" };
const GLYPH = { representado: "✓", incompativel: "!", incompleto: "!", desabilitado: "–" };
const GLYPH_C = { representado: "#2E8B57", incompativel: "#C2364A", incompleto: "#C77700", desabilitado: "#5B6B7C" };
function s(tag, attrs, text) { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v); if (text !== undefined) e.textContent = text; return e; }
function clip(t, n) { t = String(t || ""); return t.length > n ? t.slice(0, n - 1) + "…" : t; }

function node(g, x, y, w, h, n, delay) {
  const c = COLORS[n.kind] || "#5B6B7C";
  const grp = s("g", { class: "topo-node", style: `animation-delay:${delay}ms` });
  const off = n.enabled === false;
  grp.append(s("rect", { x, y, width: w, height: h, rx: 11, fill: "var(--sd-card)", stroke: off ? "#9AA6B2" : c,
    "stroke-width": 1.6, "stroke-dasharray": off ? "5 4" : "none", opacity: off ? .7 : 1 }));
  grp.append(s("rect", { x, y, width: 5, height: h, rx: 2.5, fill: off ? "#9AA6B2" : c }));
  grp.append(s("text", { x: x + 14, y: y + 18, "font-size": 10, "font-weight": 700, fill: c, "letter-spacing": ".08em" }, clip(n.kind_label.toUpperCase(), 22)));
  grp.append(s("text", { x: x + 14, y: y + 36, "font-size": 13, "font-weight": 650, fill: "var(--sd-text)" }, clip(n.name, 22)));
  grp.append(s("text", { x: x + 14, y: y + 53, "font-size": 11, fill: "var(--sd-muted)" }, clip(n.detail || "", 27)));
  if (n.sim_status) {
    const gc = GLYPH_C[n.sim_status] || "#5B6B7C";
    grp.append(s("circle", { cx: x + w - 14, cy: y + 15, r: 8, fill: gc, opacity: .15 }));
    grp.append(s("text", { x: x + w - 14, y: y + 19, "font-size": 11, "font-weight": 800, fill: gc, "text-anchor": "middle" }, GLYPH[n.sim_status] || ""));
    const t = s("title", {}, n.sim_label || ""); grp.append(t);
  }
  g.append(grp);
}

export default function (component) {
  const { data, parentElement } = component;
  let root = parentElement.querySelector(".topo");
  if (!root) { root = document.createElement("div"); root.className = "sd topo"; parentElement.appendChild(root); }
  root.innerHTML = "";
  const top = data.nodes.filter((n) => n.role !== "storage");
  const bottom = data.nodes.filter((n) => n.role === "storage");
  bottom.push({ kind: "load", kind_label: "Demanda", name: data.load.label, detail: data.load.detail, enabled: true });
  const W = 176, H = 64, GAP = 18, PAD = 26;
  const gridOn = data.grid.state === "conectada";
  const cols = Math.max(top.length, bottom.length, 2);
  const width = Math.max(PAD * 2 + cols * W + (cols - 1) * GAP + (gridOn ? W + 40 : 0), 640);
  const busY = 172, topY = 40, botY = busY + 76, height = botY + H + 40;
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, class: "topo-svg", role: "img",
    style: `max-width:${width}px`,                        // nunca amplia além do tamanho natural (texto legível)
    "aria-label": `Esquema da microrrede: ${data.nodes.length} equipamento(s) ligados ao ${data.bus.label}` });
  const busX1 = PAD, busX2 = width - PAD - (gridOn ? W + 30 : 0);
  const layer = s("g");
  const place = (list, y, up) => {
    const span = list.length * W + (list.length - 1) * GAP;
    const x0 = PAD + Math.max(0, (busX2 - busX1 - span) / 2);
    list.forEach((n, i) => {
      const x = x0 + i * (W + GAP), cx = x + W / 2;
      const y1 = up ? y + H : y, y2 = busY;
      const off = n.enabled === false;
      layer.append(s("line", { x1: cx, y1, x2: cx, y2, stroke: off ? "#9AA6B2" : (COLORS[n.kind] || "#5B6B7C"), "stroke-width": 2,
        "stroke-dasharray": off ? "5 4" : "none" }));
      if (n.coupling) {
        const ly = up ? (y1 + y2) / 2 + 4 : (y1 + y2) / 2 + 4;
        layer.append(s("rect", { x: cx + 6, y: ly - 11, width: Math.min(150, n.coupling.length * 6.1 + 10), height: 16, rx: 5, fill: "var(--sd-bg)", opacity: .92 }));
        layer.append(s("text", { x: cx + 11, y: ly + 1, "font-size": 10.5, fill: "var(--sd-muted)" }, clip(n.coupling, 24)));
      }
      node(layer, x, y, W, H, n, i * 40);
    });
  };
  place(top, topY, true);
  place(bottom, botY, false);
  svg.append(s("rect", { x: busX1, y: busY - 5, width: busX2 - busX1, height: 10, rx: 5, fill: "var(--sd-accent)", opacity: .9 }));
  const busTxt = `${data.bus.label} · ${data.bus.kind_label}${data.bus.voltage ? " · " + data.bus.voltage : ""}`;
  svg.append(s("rect", { x: busX1, y: busY + 9, width: Math.min(busTxt.length * 6.6 + 14, busX2 - busX1), height: 19, rx: 6,
    fill: "var(--sd-card)", stroke: "var(--sd-accent)", "stroke-opacity": .35 }));
  svg.append(s("text", { x: busX1 + 7, y: busY + 22.5, "font-size": 11.5, "font-weight": 700, fill: "var(--sd-accent)" }, clip(busTxt, 70)));
  if (gridOn) {
    const gx = width - PAD - W, gy = busY - H / 2;
    svg.append(s("line", { x1: busX2, y1: busY, x2: gx, y2: busY, stroke: COLORS.grid, "stroke-width": 2, "stroke-dasharray": "6 5" }));
    node(svg, gx, gy, W, H, { kind: "grid", kind_label: "Rede elétrica", name: "Conexão declarada", detail: "não modelada pelo EMS atual", enabled: true }, 0);
  }
  svg.append(layer);
  root.appendChild(svg);
  const lg = document.createElement("div"); lg.className = "topo-legend";
  const item = (html) => { const sp = document.createElement("span"); sp.innerHTML = html; lg.appendChild(sp); };
  item('<i class="lg-line"></i>Ligação declarada ao barramento');
  item('<i class="lg-line dash"></i>Desabilitado / não modelado');
  item(`<b style="color:${GLYPH_C.representado}">✓</b> Representado no EMS`);
  item(`<b style="color:${GLYPH_C.incompativel}">!</b> Excluído da simulação (motivo no inventário)`);
  root.appendChild(lg);
  const note = document.createElement("div"); note.className = "topo-note";
  note.textContent = "Esquema lógico de barramento comum, coerente com o balanço de potência do EMS. Não calcula fluxo de potência, tensões, proteções nem transitórios elétricos.";
  root.appendChild(note);
}
