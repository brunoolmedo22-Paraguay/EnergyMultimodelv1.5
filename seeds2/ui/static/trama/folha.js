// FOLHA DE ENSAIO (Piso 3D-B2-D) — cabeçalho da folha acima de cada etapa do cenário: identidade (cenário, versão, motor),
// índice das seções com o estado de cada uma, prontidão e alterações não salvas. Só navega entre seções ({type:"nav"});
// os formulários, validações, preflight e execução são os das etapas existentes, logo abaixo.
export default function (component) {
  const { data, parentElement, setTriggerValue } = component, D = data || {}, [root] = raizPt(parentElement, "pg folha"), sig = JSON.stringify(D);
  if (root.__sig === sig) return;
  root.__sig = sig;
  const c = D.cenario || {}, k = D.constatacoes || {}, ir = (a) => setTriggerValue("action", { ...a, t: Date.now() });
  const prontidao = [["erro", "erro(s)", "b"], ["aviso", "aviso(s)", "w"], ["pendente", "pendência(s) do motor", "i"], ["incompleto", "item(ns) não definido(s)", "w"]].filter(([q]) => k[q]).map(([q, t, tom]) => `<span class="tag ${tom}">${k[q]} ${t}</span>`).join(" ");
  root.replaceChildren(h("div", { class: "panel acc fl-cab", style: "--acc:var(--ink-3)" },
    h("div", { class: "fl-top" }, h("div", { class: "grow" }, h("div", { class: "eyebrow" }, "Folha de ensaio"), h("h1", { class: "fl-nome" }, c.nome || "Cenário"),
      h("div", { class: "sub fl-ctx", html: `versão ${esc(c.versao)} · motor ${esc(c.motor)} · inventário rev. ${esc(c.revisao ?? "N/D")} · ${esc(D.rodadas ?? 0)} rodada(s) deste cenário` })),
      D.alterado ? h("span", { class: "tag w fl-alt" }, "alterações não salvas") : h("span", { class: "tag ok fl-alt" }, "versão salva"),
      h("button", { class: "pill", onclick: () => ir({ type: "nav", view: "operacao", tab: "caderno" }) }, "Caderno de ensaios")),
    h("nav", { class: "fl-secs", "aria-label": "Seções da folha de ensaio" }, ...(D.secoes || []).map((s) => h("button", { class: "fl-sec", "data-sec": s.id, "aria-current": s.atual ? "step" : null, title: s.detalhe || "",
      onclick: () => { if (!s.atual) ir({ type: "nav", view: "operacao", tab: s.id }); }, html: `<span class="fl-n">${esc(s.n)}</span><span class="fl-t">${esc(s.titulo)}<small><i class="dot ${esc(s.tom)}"></i>${esc(s.estado)}</small></span>` }))),
    h("div", { class: "fl-pr", html: `<span class="dim3">Prontidão do estado inicial:</span> ${prontidao || '<span class="tag ok">sem constatações</span>'} <span class="dim3">· a compatibilidade com o motor é decidida pelo preflight, na seção 04.</span>` })));
}
