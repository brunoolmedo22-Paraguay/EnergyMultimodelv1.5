// Barra superior SEEDS2: marca + microrrede ativa, navegação principal, TROCAR MICRORREDE e estado de salvamento.
// Eventos: {type:"nav", view} | {type:"switch"} (volta ao Gestor de microrredes).
function el(t, c, x) { const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; }
const SWAP = `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M4 8h13l-3.5-3.5M20 16H7l3.5 3.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const LOGO = `<svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
<rect x="2" y="2" width="28" height="28" rx="8" fill="currentColor" opacity=".13"/>
<path d="M6 16h20" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
<path d="M10 16V9M16 16V7M22 16V10M12 16v7M20 16v6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" opacity=".75"/>
<circle cx="10" cy="8" r="2" fill="currentColor"/><circle cx="16" cy="6" r="2" fill="currentColor"/><circle cx="22" cy="9" r="2" fill="currentColor"/>
<rect x="10" y="23" width="4" height="3" rx="1" fill="currentColor"/><circle cx="20" cy="23.5" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`;
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  let root = parentElement.querySelector(".tb");
  if (!root) {
    root = el("header", "sd tb");
    const brand = el("button", "tb-brand"); brand.type = "button";
    const logo = el("span", "tb-logo"); logo.innerHTML = LOGO;
    const name = el("span", "tb-name");
    const title = el("b", null, "SEEDS2"); const ver = el("span", "tb-ver"); title.appendChild(ver);
    const site = el("span", "tb-site");
    name.append(title, site);
    brand.append(logo, name);
    brand.addEventListener("click", () => setTriggerValue("action", { type: "nav", view: root.__ctl.home, t: Date.now() }));
    const nav = el("nav", "tb-nav"); nav.setAttribute("aria-label", "Navegação principal");
    const save = el("div", "tb-save"); save.setAttribute("role", "status"); save.setAttribute("aria-live", "polite");
    const sw = el("button", "tb-switch"); sw.type = "button";
    sw.innerHTML = `${SWAP}<span>TROCAR MICRORREDE</span>`;
    sw.setAttribute("aria-label", "Trocar microrrede: voltar ao Gestor de microrredes");
    sw.title = "Voltar ao Gestor de microrredes (os dados da microrrede não são alterados)";
    sw.addEventListener("click", () => setTriggerValue("action", { type: "switch", t: Date.now() }));
    const right = el("div", "tb-right"); right.append(sw, save);
    root.append(brand, nav, right);
    parentElement.appendChild(root);
    root.__ctl = { nav, save, ver, site, brand, sw, home: "inicio" };
  }
  const c = root.__ctl;
  root.classList.toggle("sd-light", !!data.force_light);
  c.home = data.home || "inicio";
  c.ver.textContent = `v${data.version}`;
  c.site.textContent = data.site || "Nenhuma microrrede aberta";
  c.sw.hidden = !data.switch;
  c.site.title = data.site_title || "";
  c.brand.setAttribute("aria-label", `SEEDS2 — ${data.site || "início"}`);
  c.nav.innerHTML = "";
  for (const [v, t] of data.items) {
    const b = el("button", `tb-link${v === data.view ? " on" : ""}`, t); b.type = "button";
    b.setAttribute("aria-current", v === data.view ? "page" : "false");
    b.addEventListener("click", () => { if (v !== data.view) setTriggerValue("action", { type: "nav", view: v, t: Date.now() }); });
    c.nav.appendChild(b);
  }
  const s = data.save || {};
  c.save.className = `tb-save s-${s.state || "novo"}`;
  c.save.textContent = s.text || "";
  c.save.title = s.title || "";
  c.save.hidden = !s.text;
}
