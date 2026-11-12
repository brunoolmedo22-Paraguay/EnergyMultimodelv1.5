// CADERNO DE ENSAIOS (Piso 3D-B2-C) — cenários, versões e rodadas (V1.6 e V2) de UMA microrrede e estudos do Arquivo
// Científico, como estão persistidos. Só lista e navega: {type:"abrir_rodada", run} | {type:"abrir_cenario", sc, tab} |
// {type:"abrir_estudo", study}. Os filtros são estado do navegador (não provocam reruns).
const ESTADOS_CD = ["concluida", "interrompida", "falhou", "em_execucao", "preparada"];
// Filtro PURO das rodadas (executado também em Node).
function filtrarRodadas(rodadas, f) { return (rodadas || []).filter((r) => (!f.motor || r.motor === f.motor) && (!f.estado || r.estado === f.estado) && (!f.cenario || r.cenario_uid === f.cenario)); }
function contarRodadas(rodadas) { const o = {}; for (const r of rodadas || []) o[r.estado] = (o[r.estado] || 0) + 1; return o; }

export default function (component) {
  const { data, parentElement, setTriggerValue } = component, D = data || {}, [root] = raizPt(parentElement, "pg caderno"), sig = JSON.stringify(D);
  const F = root.__F || (root.__F = { motor: "", estado: "", cenario: "" });
  const ir = (a) => setTriggerValue("action", { ...a, t: Date.now() });
  const rot = D.rotulos || {}, cont = (o) => ESTADOS_CD.filter((k) => o[k]).map((k) => `${o[k]} ${(rot[k] || k).toLowerCase()}`).join(" · ") || "nenhuma rodada";
  const desenhar = () => {
    const linhas = filtrarRodadas(D.rodadas, F), tot = contarRodadas(D.rodadas), cen = D.cenarios || [];
    const seg = (chave, ops, rotulo) => h("div", { class: "seg", role: "group", "aria-label": rotulo }, ...ops.map(([v, t]) => h("button", { "aria-pressed": String(F[chave] === v), "data-f": chave + ":" + v, onclick: () => { F[chave] = v; desenhar(); } }, t)));
    const cartao = (c) => h("div", { class: "card cd-cen" + (c.atual ? " acc" : ""), style: c.atual ? "--acc:var(--ink)" : null, "data-sc": c.uid },
      h("h3", { html: `${esc(c.motor === "V2" ? "Motor V2 · MILP–MPC" : "Motor V1.6")}<span class="tag ${c.atual ? "ok" : ""}">${c.atual ? "aberto" : "v" + esc(c.versao)}</span>` }), h("div", { class: "big", style: "font-size:17px;line-height:1.2" }, c.nome),
      h("div", { class: "sub" }, `versão ${c.versao} · atualizado ${c.atualizado || "—"} · inventário rev. ${c.revisao}`), h("div", { class: "sub" }, "Rodadas: " + cont(c.rodadas || {})),
      h("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-top:10px" }, h("button", { class: "pill on cd-folha", onclick: () => ir({ type: "abrir_cenario", sc: c.uid, tab: "inicializacao" }) }, "Abrir a folha de ensaio"),
        h("button", { class: "pill", onclick: () => { F.cenario = F.cenario === c.uid ? "" : c.uid; desenhar(); } }, F.cenario === c.uid ? "Mostrar todas as rodadas" : "Só as rodadas deste cenário")));
    const tabela = h("div", { class: "tabx cd-tab", style: "max-height:none" }, h("table", { class: "runs" }, h("thead", { html: "<tr><th>Cenário · versão</th><th>Rodada</th><th>Motor</th><th>Estado</th><th>Início</th><th>Fim</th><th class=n>Inventário</th><th>Resultado</th><th class=n>Dados</th><th></th></tr>" }),
      h("tbody", {}, ...linhas.map((r) => h("tr", { "data-run": r.uid, "data-motor": r.motor, "data-estado": r.estado },
        h("td", { style: "white-space:normal;min-width:180px" }, `${r.cenario} · v${r.versao}` + (r.cenario_existe ? "" : " (cenário removido)")), h("td", { class: "uid" }, r.uid.slice(0, 8)), h("td", {}, r.motor),
        h("td", { html: `<span class="tag ${esc(r.tom)}">${esc(r.estado_rotulo)}</span>` }), h("td", {}, r.criada || "—"), h("td", {}, r.finalizada || "—"), h("td", { class: "n" }, "rev. " + r.revisao),
        h("td", {}, r.resultado || (r.estado === "concluida" ? "N/D" : "—")), h("td", { class: "n", title: "arquivos de dados gravados com a rodada (SHA-256 conferido na leitura)" }, r.dados ? r.dados + " arq." : "—"),
        h("td", {}, h("button", { class: "pill cd-abrir", style: "height:26px", onclick: () => ir({ type: "abrir_rodada", run: r.uid }) }, r.estado === "concluida" ? "Abrir" : "Diagnóstico")))))));
    root.replaceChildren(h("div", { class: "cd-wrap" },
      h("div", { class: "panel" }, h("div", { class: "chead" }, h("span", { class: "ttl" }, `Cenários · ${cen.length}`), h("span", { class: "dim3" }, "cada cenário guarda todas as suas versões; uma rodada fica presa à versão que executou")),
        cen.length ? h("div", { class: "g2 cd-cens" }, ...cen.map(cartao)) : h("div", { class: "nd", html: "<b>Nenhum cenário</b> nesta microrrede. Crie o primeiro no Centro de Operação." })),
      h("div", { class: "panel" }, h("div", { class: "chead" }, h("span", { class: "ttl" }, `Rodadas · ${linhas.length} de ${(D.rodadas || []).length}`), h("span", { class: "dim3 cd-tot" }, cont(tot)), h("span", { class: "grow" }),
        seg("motor", [["", "todos os motores"], ["V2", "V2"], ["V1.6", "V1.6"]], "Motor"), seg("estado", [["", "todos os estados"], ...ESTADOS_CD.filter((k) => tot[k]).map((k) => [k, rot[k] || k])], "Estado")),
        (D.rodadas || []).length ? (linhas.length ? tabela : h("div", { class: "nd", html: "Nenhuma rodada com este filtro." })) : h("div", { class: "nd", html: "<b>Nenhuma rodada</b> registrada nesta microrrede. As rodadas aparecem aqui depois de executar um cenário." }),
        h("p", { class: "note", html: "Rodadas são imutáveis. O resultado é rotulado pelo motor (V1.6: função objetivo; V2: custo realizado) e só existe em rodadas concluídas; a evidência de uma rodada V2 é verificada pelo servidor ao abri-la." })),
      h("div", { class: "panel" }, h("div", { class: "chead" }, h("span", { class: "ttl" }, `Arquivo Científico · ${(D.estudos || []).length} estudo(s)`), h("span", { class: "dim3" }, "somente leitura · da instalação inteira"), h("span", { class: "grow" }),
        h("button", { class: "pill", onclick: () => ir({ type: "nav", view: "operacao", tab: "arquivo" }) }, "Abrir o Arquivo Científico")),
        (D.estudos || []).length ? h("div", { class: "g2" }, ...D.estudos.map((e) => h("div", { class: "card", "data-study": e.uid }, h("h3", { html: `${e.desta ? "Origem: esta microrrede" : "Origem: " + esc(e.origem)}<span class="tag ${e.verificado ? "ok" : "b"}">${e.verificado ? "verificado" : "não verificado"}</span>` }),
          h("div", { class: "big", style: "font-size:16px;line-height:1.2" }, e.nome), h("div", { class: "sub" }, `${e.versoes} versão(ões) · ${e.rodadas} rodada(s) · importado ${e.importado || "—"}`), h("div", { class: "uid" }, `content_id ${e.content_id}…`),
          h("button", { class: "pill cd-estudo", style: "margin-top:10px", onclick: () => ir({ type: "abrir_estudo", study: e.uid }) }, "Abrir o estudo")))) :
          h("div", { class: "nd", html: "Nenhum estudo arquivado nesta instalação." }))));
  };
  if (root.__sig === sig) return;                           // rerun do Streamlit com os mesmos dados: nada é redesenhado
  root.__sig = sig; if (F.cenario && !(D.cenarios || []).some((c) => c.uid === F.cenario)) F.cenario = "";
  desenhar();
}
