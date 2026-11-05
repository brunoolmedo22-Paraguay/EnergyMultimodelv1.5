// Comissionamento: indicador de progresso com estado por etapa e navegação direta.
// Estados: pendente | progresso | completa | atencao | bloqueada. Evento: {type:"goto", step}.
const GLYPH = { completa: "✓", atencao: "!", bloqueada: "🔒" };
const LABEL = { pendente: "Não iniciada", progresso: "Em andamento", completa: "Completa", atencao: "Requer informação", bloqueada: "Bloqueada" };
function el(t, c, x) { const e = document.createElement(t); if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; }
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  let root = parentElement.querySelector(".stp");
  if (!root) { root = el("nav", "sd stp"); root.setAttribute("aria-label", "Etapas do comissionamento"); parentElement.appendChild(root); }
  root.innerHTML = "";
  const list = el("ol", "stp-list");
  const n = data.steps.length;
  list.style.setProperty("--n", String(n));
  let last = -1;
  for (let i = 0; i < n; i++) { if (data.steps[i].state === "completa") last = i; else break; }
  list.style.setProperty("--fill", `${Math.max(0, last) / (n - 1) * 100}%`);
  data.steps.forEach((s) => {
    const li = el("li", `stp-item st-${s.state}${s.n === data.current ? " is-current" : ""}`);
    const b = el("button", "stp-btn"); b.type = "button";
    b.disabled = s.state === "bloqueada";
    b.setAttribute("aria-current", s.n === data.current ? "step" : "false");
    b.title = `${s.title} — ${LABEL[s.state]}${s.reason ? ": " + s.reason : ""}`;
    const dot = el("span", "stp-dot", GLYPH[s.state] || String(s.n).padStart(2, "0"));
    const txt = el("span", "stp-txt");
    txt.append(el("span", "stp-ttl", s.title), el("span", "stp-state", s.reason ? `${LABEL[s.state]} · ${s.reason}` : LABEL[s.state]));
    b.append(dot, txt);
    b.addEventListener("click", () => { if (!b.disabled && s.n !== data.current) setTriggerValue("action", { type: "goto", step: s.n, t: Date.now() }); });
    li.appendChild(b);
    list.appendChild(li);
  });
  root.appendChild(list);
}
