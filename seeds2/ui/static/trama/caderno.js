// CADERNO DE ENSAIOS (Piso 3D-B2-C) — cenários, versões e rodadas (V1.6 e V2) de UMA microrrede e estudos do Arquivo
// Científico, como estão persistidos. Só lista e navega: {type:"abrir_rodada", run} | {type:"abrir_cenario", sc, tab} |
// {type:"abrir_estudo", study}. Os filtros são estado do navegador (não provocam reruns).
const ESTADOS_CD = ["concluida", "interrompida", "falhou", "em_execucao", "preparada"];
// Filtro PURO das rodadas (executado também em Node).
function filtrarRodadas(rodadas, f) { return (rodadas || []).filter((r) => (!f.motor || r.motor === f.motor) && (!f.estado || r.estado === f.estado) && (!f.cenario || r.cenario_uid === f.cenario)); }
function contarRodadas(rodadas) { const o = {}; for (const r of rodadas || []) o[r.estado] = (o[r.estado] || 0) + 1; return o; }
// Indicadores persistidos de uma rodada → texto das células (PURO; Node). Três situações que nunca se confundem:
// número = gravado; null/ausente = «N/D»; "na" = «não aplicável» (só com evidência, decidida no servidor).
function valInd(v, d, u) { return v === "na" ? "não aplicável" : v == null ? "N/D" : nf(v, d) + (u ? " " + u : ""); }
function celulasInd(r) {
  const x = (r && r.ind) || {};
  if (x.erro) return { malha: "N/D", pcc: "N/D", custo: "N/D", imp: "N/D", h2: "N/D", sinal: "N/D", integ: "resumo ilegível" };
  const malha = x.motor === "V2" ? (x.delta_min == null && x.N == null ? "N/D" : `Δ ${x.delta_min == null ? "N/D" : nf(x.delta_min, 0)} min · N ${x.N ?? "N/D"} · m ${x.m ?? "N/D"} · H_L ${x.H_L ?? "N/D"}`)
    : x.motor === "V1.6" ? `${x.passo_s == null ? "N/D" : nf(x.passo_s, 0)} s · N ${x.N ?? "N/D"}` : "N/D";
  const pcc = x.pcc === "na" ? "não aplicável" : x.pcc ? String(x.pcc).replace(/_/g, " ") : "N/D";
  const custo = x.custo == null ? "N/D" : (x.custo_natureza === "funcao_objetivo_v16" ? "f. objetivo " : "realizado ") + "R$ " + nf(x.custo, 2);
  const s = x.sinal;
  const sinal = s === "na" ? "não aplicável" : s && typeof s === "object" ? `${s.valido ?? "N/D"} válido(s) / ${s.janelas ?? "N/D"} janela(s)` + (s.degradado ? ` · ${s.degradado} degradado(s)` : "") : "N/D";
  const integ = (x.auditoria === true ? "auditoria aprovada · " : x.auditoria === false ? "auditoria NÃO aprovada · " : "") + (x.dados ? x.dados + " arq." : "sem dados");
  return { malha, pcc, custo, imp: valInd(x.energia_importada_kWh, 1, "kWh"), h2: valInd(x.h2_kg, 3, "kg"), sinal, integ };
}
// Diferença formatada (só quando o servidor a calculou: mesmo motor e mesma natureza).
function difTxt(l) { if (l.dif_abs == null) return "—"; const s = (l.dif_abs > 0 ? "+" : "") + nf(l.dif_abs, 2); return l.dif_rel == null ? s : `${s} (${l.dif_rel > 0 ? "+" : ""}${nf(100 * l.dif_rel, 1)} %)`; }

export default function (component) {
  const { data, parentElement, setTriggerValue } = component, D = data || {}, [root] = raizPt(parentElement, "pg caderno"), sig = JSON.stringify(D);
  const F = root.__F || (root.__F = { motor: "", estado: "", cenario: "" });
  const ir = (a) => setTriggerValue("action", { ...a, t: Date.now() });
  const rot = D.rotulos || {}, cont = (o) => ESTADOS_CD.filter((k) => o[k]).map((k) => `${o[k]} ${(rot[k] || k).toLowerCase()}`).join(" · ") || "nenhuma rodada";
  // ---- comparador A × B: a escolha volta ao servidor ({type:"comparar"}), que compara os registros PERSISTIDOS
  const comparador = () => {
    const todas = D.rodadas || [], C = D.comparacao || null, sel = (C && C.sel) || root.__sel || ["", ""];
    const op = (v) => h("select", { class: "sel cd-sel", "aria-label": "Rodada", onchange: (e) => { sel[v] = e.target.value; root.__sel = sel; } },
      h("option", { value: "" }, "— escolher —"), ...todas.map((r) => h("option", { value: r.uid, selected: sel[v] === r.uid ? "" : null }, `${r.cenario} · v${r.versao} · ${r.uid.slice(0, 8)} · ${r.motor} · ${(r.estado_rotulo || r.estado).toLowerCase()}`)));
    const topo = h("div", { class: "chead" }, h("span", { class: "ttl" }, "Comparar rodadas"), h("span", { class: "dim3" }, "a partir dos registros gravados · sem solver nem modelos"));
    if (todas.length < 2) return h("div", { class: "panel cd-cmp" }, topo, h("div", { class: "nd" }, "São necessárias pelo menos duas rodadas nesta microrrede."));
    const escolha = h("div", { class: "cd-cmp-sel" }, h("label", {}, h("b", {}, "A "), op(0)), h("label", {}, h("b", {}, "B "), op(1)),
      h("button", { class: "pill on cd-comparar", onclick: () => { if (sel[0] && sel[1] && sel[0] !== sel[1]) ir({ type: "comparar", a: sel[0], b: sel[1] }); } }, "Comparar"));
    const corpo = [];
    if (C && C.erro) corpo.push(h("div", { class: "nd" }, C.erro));
    else if (C && C.a) {
      const card = (x, l) => h("div", { class: "card cd-lado", "data-lado": l }, h("h3", { html: `Rodada ${l} · ${esc(x.motor)}<span class="tag">${esc(x.estado_rotulo)}</span>` }),
        h("div", { class: "big", style: "font-size:15px;line-height:1.2" }, `${x.cenario} · v${x.versao}`), h("div", { class: "uid" }, x.uid), h("div", { class: "sub" }, `${x.criada || "—"} · inventário rev. ${x.revisao}`),
        h("button", { class: "pill cd-abrir-" + l.toLowerCase(), style: "margin-top:8px", onclick: () => ir({ type: "abrir_rodada", run: x.uid }) }, "Abrir os resultados completos"));
      corpo.push(h("div", { class: "g2" }, card(C.a, "A"), card(C.b, "B")));
      if ((C.advertencias || []).length) corpo.push(h("div", { class: "cd-adv", html: C.advertencias.map((t) => `<div><span class="tag w">aviso</span> ${esc(t)}</div>`).join("") }));
      corpo.push(h("div", { class: "tabx", style: "max-height:none" }, h("table", { class: "runs cd-cond", html: "<thead><tr><th>Condição experimental</th><th>A</th><th>B</th><th></th></tr></thead><tbody>" +
        (C.condicoes || []).map((c) => `<tr data-igual="${c.igual ? 1 : 0}"><td>${esc(c.item)}</td><td>${esc(c.a ?? "N/D")}</td><td>${esc(c.b ?? "N/D")}</td><td>${c.igual ? '<span class="tag ok">igual</span>' : '<span class="tag w">difere</span>'}</td></tr>`).join("") + "</tbody>" })));
      const cel = (v, u) => (typeof v === "number" ? (u === "R$" ? "R$ " + nf(v, 2) : nf(v, u === "kg" ? 3 : 2) + (u ? " " + u : "")) : v === "na" ? "não aplicável" : v == null ? "N/D" : esc(v));
      corpo.push(h("div", { class: "tabx", style: "max-height:none" }, h("table", { class: "runs cd-ind", html: "<thead><tr><th>Indicador (persistido)</th><th class=n>A</th><th class=n>B</th><th class=n>B − A</th><th>Observação</th></tr></thead><tbody>" +
        (C.linhas || []).map((l) => `<tr data-k="${esc(l.chave)}"><td style="white-space:normal;min-width:220px">${esc(l.rotulo)}</td><td class=n>${cel(l.a, l.unidade)}</td><td class=n>${cel(l.b, l.unidade)}</td><td class=n>${esc(difTxt(l))}</td><td style="white-space:normal">${esc(l.nota || "")}</td></tr>`).join("") + "</tbody>" })));
      const T = C.temporal || {};
      if (T.ok) corpo.push(h("div", { class: "cd-temp" }, h("div", { class: "eyebrow" }, "Comparação temporal · mesma malha (instantes idênticos; nada interpolado)"), ...(T.series || []).map((sr) => graficoDuplo(sr, T.instantes))));
      else corpo.push(h("div", { class: "nd cd-temp-off", html: "<b>Comparação temporal não disponível:</b> " + esc(T.motivo || "N/D") + ". A comparação de metadados e indicadores acima continua válida." }));
    } else corpo.push(h("div", { class: "nd" }, "Escolha as rodadas A e B e clique em Comparar."));
    return h("div", { class: "panel cd-cmp" }, topo, escolha, ...corpo);
  };
  // duas séries sobre os MESMOS instantes (A cheia, B tracejada); valor ausente interrompe a linha (nunca vira zero)
  const graficoDuplo = (sr, inst) => {
    const W = 380, H = 130, x0 = 46, x1 = W - 8, y0 = 12, y1 = H - 22, n = inst.length, vals = [...sr.a, ...sr.b].filter((v) => v != null);
    const lo = Math.min(0, ...vals), hi = Math.max(lo + 1e-9, ...vals), X = (i) => x0 + (x1 - x0) * (n > 1 ? i / (n - 1) : 0), Y = (v) => y1 - (y1 - y0) * (v - lo) / (hi - lo);
    const linha = (arr, cls) => { let d = "", pen = false; arr.forEach((v, i) => { if (v == null) { pen = false; return; } d += (pen ? "L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1); pen = true; }); return sv("path", { d, class: cls, fill: "none" }); };
    return h("div", { class: "cd-graf", "data-serie": sr.chave }, h("div", { class: "sub" }, `${sr.rotulo} [${sr.unidade}] — A cheia · B tracejada`),
      sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "cd-svg", role: "img", "aria-label": sr.rotulo }, [sv("line", { x1: x0, x2: x1, y1: y1, y2: y1, class: "cd-eixo" }),
        sv("text", { x: x0 - 6, y: y0 + 8, "text-anchor": "end", class: "cd-tx" }, nf(hi, 1)), sv("text", { x: x0 - 6, y: y1, "text-anchor": "end", class: "cd-tx" }, nf(lo, 1)),
        sv("text", { x: x0, y: H - 6, class: "cd-tx" }, String(inst[0] || "").slice(0, 16).replace("T", " ")), sv("text", { x: x1, y: H - 6, "text-anchor": "end", class: "cd-tx" }, String(inst[n - 1] || "").slice(0, 16).replace("T", " ")),
        linha(sr.a, "cd-la"), linha(sr.b, "cd-lb")]));
  };
  const desenhar = () => {
    const linhas = filtrarRodadas(D.rodadas, F), tot = contarRodadas(D.rodadas), cen = D.cenarios || [];
    const seg = (chave, ops, rotulo) => h("div", { class: "seg", role: "group", "aria-label": rotulo }, ...ops.map(([v, t]) => h("button", { "aria-pressed": String(F[chave] === v), "data-f": chave + ":" + v, onclick: () => { F[chave] = v; desenhar(); } }, t)));
    const cartao = (c) => h("div", { class: "card cd-cen" + (c.atual ? " acc" : ""), style: c.atual ? "--acc:var(--ink)" : null, "data-sc": c.uid },
      h("h3", { html: `${esc(c.motor === "V2" ? "Motor V2 · MILP–MPC" : "Motor V1.6")}<span class="tag ${c.atual ? "ok" : ""}">${c.atual ? "aberto" : "v" + esc(c.versao)}</span>` }), h("div", { class: "big", style: "font-size:17px;line-height:1.2" }, c.nome),
      h("div", { class: "sub" }, `versão ${c.versao} · atualizado ${c.atualizado || "—"} · inventário rev. ${c.revisao}`), h("div", { class: "sub" }, "Rodadas: " + cont(c.rodadas || {})),
      h("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-top:10px" }, h("button", { class: "pill on cd-folha", onclick: () => ir({ type: "abrir_cenario", sc: c.uid, tab: "inicializacao" }) }, "Abrir a folha de ensaio"),
        h("button", { class: "pill", onclick: () => { F.cenario = F.cenario === c.uid ? "" : c.uid; desenhar(); } }, F.cenario === c.uid ? "Mostrar todas as rodadas" : "Só as rodadas deste cenário")));
    const tabela = h("div", { class: "tabx cd-tab", style: "max-height:none" }, h("table", { class: "runs" }, h("thead", { html: "<tr><th>Cenário · versão</th><th>Rodada</th><th>Motor</th><th>Estado</th><th>Início</th><th>Fim</th><th class=n>Inventário</th><th>Resultado</th><th>Malha</th><th>PCC</th><th class=n>Importação</th><th class=n>H₂</th><th>Sinal de valor futuro</th><th>Integridade</th><th class=n>Dados</th><th></th></tr>" }),
      h("tbody", {}, ...linhas.map((r) => h("tr", { "data-run": r.uid, "data-motor": r.motor, "data-estado": r.estado },
        h("td", { style: "white-space:normal;min-width:180px" }, `${r.cenario} · v${r.versao}` + (r.cenario_existe ? "" : " (cenário removido)")), h("td", { class: "uid" }, r.uid.slice(0, 8)), h("td", {}, r.motor),
        h("td", { html: `<span class="tag ${esc(r.tom)}">${esc(r.estado_rotulo)}</span>` }), h("td", {}, r.criada || "—"), h("td", {}, r.finalizada || "—"), h("td", { class: "n" }, "rev. " + r.revisao),
        h("td", {}, r.resultado || (r.estado === "concluida" ? "N/D" : "—")), ...((c) => [h("td", { class: "cd-malha" }, c.malha), h("td", {}, c.pcc), h("td", { class: "n" }, c.imp), h("td", { class: "n" }, c.h2), h("td", {}, c.sinal), h("td", { class: "cd-integ" }, c.integ)])(celulasInd(r)),
        h("td", { class: "n", title: "arquivos de dados gravados com a rodada (SHA-256 conferido na leitura)" }, r.dados ? r.dados + " arq." : "—"),
        h("td", {}, h("button", { class: "pill cd-abrir", style: "height:26px", onclick: () => ir({ type: "abrir_rodada", run: r.uid }) }, r.estado === "concluida" ? "Abrir" : "Diagnóstico")))))));
    root.replaceChildren(h("div", { class: "cd-wrap" },
      h("div", { class: "panel" }, h("div", { class: "chead" }, h("span", { class: "ttl" }, `Cenários · ${cen.length}`), h("span", { class: "dim3" }, "cada cenário guarda todas as suas versões; uma rodada fica presa à versão que executou")),
        cen.length ? h("div", { class: "g2 cd-cens" }, ...cen.map(cartao)) : h("div", { class: "nd", html: "<b>Nenhum cenário</b> nesta microrrede. Crie o primeiro no Centro de Operação." })),
      h("div", { class: "panel" }, h("div", { class: "chead" }, h("span", { class: "ttl" }, `Rodadas · ${linhas.length} de ${(D.rodadas || []).length}`), h("span", { class: "dim3 cd-tot" }, cont(tot)), h("span", { class: "grow" }),
        seg("motor", [["", "todos os motores"], ["V2", "V2"], ["V1.6", "V1.6"]], "Motor"), seg("estado", [["", "todos os estados"], ...ESTADOS_CD.filter((k) => tot[k]).map((k) => [k, rot[k] || k])], "Estado")),
        (D.rodadas || []).length ? (linhas.length ? tabela : h("div", { class: "nd", html: "Nenhuma rodada com este filtro." })) : h("div", { class: "nd", html: "<b>Nenhuma rodada</b> registrada nesta microrrede. As rodadas aparecem aqui depois de executar um cenário." }),
        h("p", { class: "note", html: "Rodadas são imutáveis. O resultado é rotulado pelo motor (V1.6: função objetivo; V2: custo realizado) e só existe em rodadas concluídas; a evidência de uma rodada V2 é verificada pelo servidor ao abri-la." })),
      comparador(),
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
