// Barra superior SEEDS2: marca, navegação principal (agrupada: operação · gestão física · resultados), link
// secundário de documentação (Alcance), identidade da microrrede ativa (como um "perfil") com TROCAR MICRORREDE
// e estado de salvamento.
// Eventos: {type:"nav", view} | {type:"switch"} (volta ao Gestor de microrredes).
function el(t, c, x) { const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; }
const SWAP = `<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M4 8h13l-3.5-3.5M20 16H7l3.5 3.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const DOC = `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M7 3h7l4 4v14H7z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M10 12h5M10 16h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
const LOGO = `<svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
<rect x="2" y="2" width="28" height="28" rx="8" fill="currentColor" opacity=".13"/>
<path d="M6 16h20" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
<path d="M10 16V9M16 16V7M22 16V10M12 16v7M20 16v6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" opacity=".75"/>
<circle cx="10" cy="8" r="2" fill="currentColor"/><circle cx="16" cy="6" r="2" fill="currentColor"/><circle cx="22" cy="9" r="2" fill="currentColor"/>
<rect x="10" y="23" width="4" height="3" rx="1" fill="currentColor"/><circle cx="20" cy="23.5" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`;
function initials(name) {
  const w = String(name || "").replace(/[^\p{L}\p{N}\s]/gu, " ").trim().split(/\s+/).filter(Boolean);
  if (!w.length) return "·";
  return (w.length === 1 ? w[0].slice(0, 2) : w[0][0] + w[1][0]).toUpperCase();
}
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  let root = parentElement.querySelector(".tb");
  if (!root) {
    root = el("header", "sd tb");
    const brand = el("button", "tb-brand"); brand.type = "button";
    const logo = el("span", "tb-logo"); logo.innerHTML = LOGO;
    const name = el("span", "tb-name");
    const title = el("b", null, "SEEDS2"); const ver = el("span", "tb-ver"); title.appendChild(ver);
    name.append(title);
    brand.append(logo, name);
    brand.addEventListener("click", () => setTriggerValue("action", { type: "nav", view: root.__ctl.home, t: Date.now() }));
    const nav = el("nav", "tb-nav"); nav.setAttribute("aria-label", "Navegação principal");
    const aux = el("nav", "tb-aux"); aux.setAttribute("aria-label", "Documentação");
    // Identidade da microrrede ativa: contexto operativo (não é uma seção do menu).
    const mg = el("div", "tb-mg"); mg.setAttribute("role", "group"); mg.setAttribute("aria-label", "Microrrede ativa");
    const av = el("span", "tb-av"); av.setAttribute("aria-hidden", "true");
    const who = el("span", "tb-who");
    const site = el("span", "tb-site"); const sub = el("span", "tb-sub");
    who.append(site, sub);
    const sw = el("button", "tb-switch"); sw.type = "button";
    sw.innerHTML = `${SWAP}<span>TROCAR MICRORREDE</span>`;
    sw.setAttribute("aria-label", "Trocar microrrede: voltar ao Gestor de microrredes");
    sw.title = "Voltar ao Gestor de microrredes (os dados da microrrede não são alterados)";
    sw.addEventListener("click", () => setTriggerValue("action", { type: "switch", t: Date.now() }));
    mg.append(av, who, sw);
    const save = el("div", "tb-save"); save.setAttribute("role", "status"); save.setAttribute("aria-live", "polite");
    const right = el("div", "tb-right"); right.append(aux, mg, save);
    root.append(brand, nav, right);
    parentElement.appendChild(root);
    root.__ctl = { nav, aux, save, ver, site, sub, av, mg, brand, sw, home: "operacao" };
  }
  const c = root.__ctl;
  root.classList.toggle("sd-light", !!data.force_light);
  c.home = data.home || "operacao";
  c.ver.textContent = `v${data.version}`;
  c.site.textContent = data.site || "Nenhuma microrrede aberta";
  c.site.title = data.site_title || "";
  c.sub.textContent = data.site_sub || "";
  c.sub.hidden = !data.site_sub;
  c.av.textContent = data.switch ? initials(data.mg_name || data.site) : "–";
  c.mg.classList.toggle("open", !!data.switch);
  c.sw.hidden = !data.switch;
  c.brand.setAttribute("aria-label", `SEEDS2 — ${data.site || "início"}`);
  c.nav.innerHTML = "";
  let group = null;
  for (const it of data.items) {
    const [v, t, g] = it;
    if (group !== null && g && g !== group) c.nav.appendChild(el("span", "tb-sep"));
    group = g || group;
    const b = el("button", `tb-link${v === data.view ? " on" : ""}`, t); b.type = "button";
    b.setAttribute("aria-current", v === data.view ? "page" : "false");
    b.addEventListener("click", () => { if (v !== data.view) setTriggerValue("action", { type: "nav", view: v, t: Date.now() }); });
    c.nav.appendChild(b);
  }
  c.aux.innerHTML = "";
  for (const [v, t] of (data.aux || [])) {
    const b = el("button", `tb-doc${v === data.view ? " on" : ""}`); b.type = "button";
    b.innerHTML = DOC; b.appendChild(el("span", "", t));
    b.title = "Documentação: alcance e limitações desta versão";
    b.setAttribute("aria-current", v === data.view ? "page" : "false");
    b.addEventListener("click", () => { if (v !== data.view) setTriggerValue("action", { type: "nav", view: v, t: Date.now() }); });
    c.aux.appendChild(b);
  }
  const s = data.save || {};
  c.save.className = `tb-save s-${s.state || "novo"}`;
  c.save.textContent = s.text || "";
  c.save.title = s.title || "";
  c.save.hidden = !s.text;
}
