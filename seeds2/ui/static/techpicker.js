// Catálogo visual de tecnologias (primeiro passo de "Adicionar equipamento"). Evento: {type:"pick", kind}.
// Ícones idênticos aos do inventário (inventory.js).
const ICONS = {
  pv: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 22l4-12h14l4 12z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M7 16h18M14 10l-2 12M18 10l2 12" stroke="currentColor" stroke-width="1.5" opacity=".7"/><path d="M16 22v5M11 27h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
  wind: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 14v15M13 29h6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="16" cy="12" r="2" fill="currentColor"/><path d="M16 10c-1-4 0-7 2-8 1 3 0 6-2 8zM18 13c4 1 6 3 6 5-3 0-5-2-6-5zM14 13c-3 2-6 3-8 2 1-3 5-3 8-2z" fill="currentColor" opacity=".85"/></svg>`,
  battery: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="9" width="20" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><rect x="25" y="13" width="3" height="6" rx="1" fill="currentColor"/><rect x="8" y="12" width="5" height="8" rx="1" fill="currentColor" opacity=".8"/><rect x="14" y="12" width="5" height="8" rx="1" fill="currentColor" opacity=".45"/></svg>`,
  pemfc: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="6" y="7" width="14" height="18" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 7v18M13 7v18M16 7v18" stroke="currentColor" stroke-width="1.3" opacity=".6"/><path d="M20 12h4c2 0 3 1 3 3v2c0 2-1 3-3 3h-4" fill="none" stroke="currentColor" stroke-width="2"/><text x="23" y="30" font-size="7" fill="currentColor" font-weight="700">H₂</text></svg>`,
  thermal: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="14" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M23 18h3v8M9 14V9h4v5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M11 6c0-2 2-2 2-4M15 8c0-2 2-2 2-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".7"/><circle cx="14" cy="20" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`,
};
function el(t, c, x) { const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; }
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  let root = parentElement.querySelector(".tp");
  if (!root) { root = el("div", "sd tp"); root.setAttribute("role", "list"); parentElement.appendChild(root); }
  root.innerHTML = "";
  data.cards.forEach((c, i) => {
    const b = el("button", `tp-card k-${c.kind}`); b.type = "button"; b.setAttribute("role", "listitem");
    b.style.animationDelay = `${i * 40}ms`;
    b.dataset.kind = c.kind;
    b.setAttribute("aria-label", `${c.name}. ${c.description}. Escolher esta tecnologia.`);
    const ic = el("span", "tp-icon"); ic.innerHTML = ICONS[c.kind] || "";
    const act = el("span", "tp-act"); act.append(el("b", null, "Escolher"), el("span", null, "→"));
    b.append(ic, el("span", "tp-name", c.name), el("span", "tp-desc", c.description), act);
    b.addEventListener("click", () => setTriggerValue("action", { type: "pick", kind: c.kind, t: Date.now() }));
    root.appendChild(b);
  });
}
