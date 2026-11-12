// BARRA LATERAL SEEDS2 (Piso 3D-B2-A) — navegação da plataforma na linguagem Partitura.
// Trilho estreito (só ícones) que se expande POR CIMA do conteúdo com o mouse ou o foco; em telas estreitas vira uma barra
// inferior. Só navega: {type:"nav", view, tab} | {type:"switch"} (voltar ao Catálogo). A navegação anterior (barra superior)
// continua intacta. Um rerun do Streamlit com os mesmos dados não redesenha nada.
const ICO_SB = {
  catalogo: "M4 5h6v6H4zM14 5h6v6h-6zM4 15h6v4H4zM14 15h6v4h-6z", planta: "M3 12h18M7 12V6M12 12V4M17 12V7M9 12v6M15 12v5",
  ensaios: "M5 4h11l3 3v13H5zM8.5 9.5h7M8.5 13h7M8.5 16.5h4", folha: "M4 6h9M17 6h3M4 12h3M11 12h9M4 18h9M17 18h3M15 4v4M9 10v4M15 16v4",
  rodada: "M3 17l5-6 4 3 5-8 4 5M3 21h18", operacao: "M4 13a8 8 0 0 1 16 0M12 13l4-5M4 17h16", gestao: "M4 7h16M4 12h16M4 17h10M18 15v4M16 17h4",
  simulacao: "M5 4l14 8-14 8z", resultados: "M4 20V10M10 20V4M16 20v-7M21 20H3", arquivo: "M4 7h16v13H4zM4 7l2-3h12l2 3M9 12h6",
  alcance: "M7 3h7l4 4v14H7zM10 12h5M10 16h5", comissionamento: "M12 3v4M12 17v4M3 12h4M17 12h4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", trocar: "M4 8h13l-3.5-3.5M20 16H7l3.5 3.5",
};
export default function (component) {
  const { data, parentElement, setTriggerValue } = component, d = data || {}, [root] = raizPt(parentElement, "sb"), sig = JSON.stringify(d);
  if (root.__sig === sig) return;
  root.__sig = sig;
  const ir = (a) => setTriggerValue("action", { ...a, t: Date.now() });
  const item = (it) => { const b = h("button", { class: "it" + (it.movel ? " mv" : ""), type: "button", title: it.dica || it.rotulo, "data-id": it.id, "aria-current": it.atual ? "page" : null,
    onclick: () => { if (!it.atual || it.acao.type === "switch") ir(it.acao); }, html: `${icoPt(ICO_SB[it.icone] || ICO_SB.operacao)}<span class="lab"><span class="lg">${esc(it.rotulo)}</span><span class="sm">${esc(it.curto || it.rotulo)}</span></span>` });
    return b; };
  const corpo = []; let grupo = null;
  for (const it of d.itens || []) { if (it.grupo && it.grupo !== grupo) corpo.push(h("div", { class: "grp", html: `<span>${esc(it.grupo)}</span>` })); grupo = it.grupo || grupo; corpo.push(item(it)); }
  root.replaceChildren(h("nav", { class: "side-in", "aria-label": "Navegação da plataforma" },
    h("div", { class: "brand", html: `${icoPt(ICO_SB.planta, 24)}<span class="lab">SEEDS2 <small>v${esc(d.versao || "")}</small></span>` }), ...corpo, h("div", { class: "sp" }),
    d.contexto ? h("div", { class: "ctx", title: d.contexto, html: `<span class="lab">${esc(d.contexto)}</span>` }) : null));
}
