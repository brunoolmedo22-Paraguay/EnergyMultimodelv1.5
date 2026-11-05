// Início: acesso às áreas funcionais (Gestão da Microrrede, Simulação, Resultados, futuro Centro de Operação).
// Evento: {type:"open", view}.
const ICONS = {
  manage: `<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 24h32" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><path d="M14 24V13M24 24V10M34 24V14M18 24v11M30 24v10" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" opacity=".7"/><circle cx="14" cy="11" r="3" fill="currentColor"/><circle cx="24" cy="8" r="3" fill="currentColor"/><circle cx="34" cy="12" r="3" fill="currentColor"/><rect x="15" y="35" width="6" height="5" rx="1.5" fill="currentColor"/><circle cx="30" cy="37" r="3" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>`,
  sim: `<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M6 40h36" stroke="currentColor" stroke-width="2" opacity=".45" stroke-linecap="round"/><path d="M8 34c5-14 9-20 14-20s7 12 12 12 5-6 7-9" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><circle cx="22" cy="14" r="2.8" fill="currentColor"/><circle cx="34" cy="26" r="2.8" fill="currentColor"/></svg>`,
  res: `<svg viewBox="0 0 48 48" aria-hidden="true"><rect x="8" y="8" width="32" height="32" rx="5" fill="none" stroke="currentColor" stroke-width="2.6"/><rect x="14" y="26" width="5" height="9" rx="1" fill="currentColor"/><rect x="21.5" y="18" width="5" height="17" rx="1" fill="currentColor" opacity=".8"/><rect x="29" y="22" width="5" height="13" rx="1" fill="currentColor" opacity=".6"/></svg>`,
  ops: `<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="15" fill="none" stroke="currentColor" stroke-width="2.6"/><path d="M24 14v10l7 5" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" fill="none"/></svg>`,
};
function el(t, c, x) { const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; }
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  let root = parentElement.querySelector(".ar");
  if (!root) { root = el("div", "sd ar"); parentElement.appendChild(root); }
  root.innerHTML = "";
  root.style.setProperty("--n", String(Math.min(data.cards.length, 4)));
  data.cards.forEach((c, i) => {
    const card = el("button", `ar-card ar-${c.kind}${c.available ? "" : " dev"}`); card.type = "button";
    card.style.animationDelay = `${i * 45}ms`;
    card.setAttribute("aria-label", `${c.eyebrow}: ${c.title}. ${c.action || ""}`);
    if (!c.available) card.setAttribute("aria-disabled", "true");
    const head = el("div", "ar-head");
    const ic = el("span", "ar-icon"); ic.innerHTML = ICONS[c.kind] || "";
    head.append(ic, el("span", `ar-pill ${c.pill_tone || (c.available ? "ok" : "dev")}`, c.pill || (c.available ? "Disponível" : "Próximo piso")));
    card.append(head, el("span", "ar-eyebrow", c.eyebrow), el("span", "ar-title", c.title), el("span", "ar-desc", c.description));
    if (c.available) {
      const act = el("span", "ar-action"); act.append(el("span", "", c.action), el("span", "ar-arrow", "→"));
      card.appendChild(act);
      card.addEventListener("click", () => setTriggerValue("action", { type: "open", view: c.view, t: Date.now() }));
    }
    root.appendChild(card);
  });
}
