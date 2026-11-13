// FOLHA DE ENSAIO (Piso 3D-B2-D; finalização da Partitura V2) — três partes do mesmo componente, cada uma numa coluna:
//  * índice (padrão): identidade do cenário, as quatro seções com o estado de cada uma e, na seção 03 (motor V2), as
//    subseções do formulário da estratégia — a navegação entre subseções só ROLA a página (âncoras [data-fl-sub]);
//  * "prontidao": acompanhamento do ensaio (versão salva × alterações, estados das seções, preflight da versão salva e
//    a disponibilidade da execução pelas MESMAS razões do botão da seção 04; o botão de executar fica na seção 04);
//  * "regua": régua dos horizontes (Δ, N, m, H_L, K_M) desenhada SÓ com os valores declarados; ausente ⇒ N/D.
// Ações devolvidas: {type:"nav", view, tab} | {type:"abrir_rodada", run}. Nada aqui grava, executa ou calcula o motor.

// Janelas MPC da régua (PURO; testado em Node): a janela j começa em j·m, aplica min(m, K − j·m) intervalos e planeja
// até min(j·m + N, K) (janela reduzida ao fim da missão). Sem K, N ou m não há janelas (nada é inferido).
function janelasRegua(R) {
  const K = R && R.K, N = R && R.N, m = R && R.m;
  if (!(K > 0 && N > 0 && m > 0)) return [];
  const out = [];
  for (let j = 0, k = 0; k < K; j += 1, k += m) out.push({ j, ini: k, apl: Math.min(m, K - k), fim: Math.min(k + N, K), reduzida: k + N > K });
  return out;
}
function durTxt(min) {
  if (!(min > 0)) return "N/D";
  const h = Math.floor(min / 60), r = min % 60;
  return h ? (r ? `${h} h ${r} min` : `${h} h`) : `${r} min`;
}

function folhaIndice(D, ir, root) {
  const c = D.cenario || {}, k = D.constatacoes || {};
  const prontidao = [["erro", "erro(s)", "b"], ["aviso", "aviso(s)", "w"], ["pendente", "pendência(s) do motor", "i"], ["incompleto", "item(ns) não definido(s)", "w"]].filter(([q]) => k[q]).map(([q, t, tom]) => `<span class="tag ${tom}">${k[q]} ${t}</span>`).join(" ");
  const rolar = (sid) => {
    const alvo = document.querySelector(`[data-fl-sub="${sid}"]`);
    root.__forcado = sid;                            // a última subseção pode não chegar ao topo: o destaque segue o clique
    if (alvo) alvo.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  };
  const subs = (D.subsecoes || []).length ? h("div", { class: "fl-subs", role: "list", "aria-label": "Subseções da estratégia" }, ...D.subsecoes.map((s) => h("button", {
    class: "fl-subl", role: "listitem", "data-sub": s.id, onclick: () => rolar(s.id),
    html: `<span class="fl-n">${esc(s.n)}</span><span class="fl-st">${esc(s.titulo)}</span>${s.pend == null ? "" : s.pend ? `<span class="tag w" title="declarações ausentes">${esc(s.pend)}</span>` : '<span class="tag ok" title="sem declarações ausentes">✓</span>'}` }))) : null;
  return h("div", { class: "panel acc fl-cab fl-ind", style: "--acc:var(--ink-3)" },
    h("div", { class: "fl-top" }, h("div", { class: "grow" }, h("div", { class: "eyebrow" }, "Folha de ensaio"), h("h1", { class: "fl-nome" }, c.nome || "Cenário"),
      h("div", { class: "sub fl-ctx", html: `versão ${esc(c.versao)} · motor ${esc(c.motor)} · inventário rev. ${esc(c.revisao ?? "N/D")} · ${esc(D.rodadas ?? 0)} rodada(s) deste cenário` })),
      D.alterado ? h("span", { class: "tag w fl-alt" }, "alterações não salvas") : h("span", { class: "tag ok fl-alt" }, "versão salva")),
    h("nav", { class: "fl-secs", "aria-label": "Seções da folha de ensaio" }, ...(D.secoes || []).map((s) => h("button", { class: "fl-sec", "data-sec": s.id, "aria-current": s.atual ? "step" : null, title: s.detalhe || "",
      onclick: () => { if (!s.atual) ir({ type: "nav", view: "operacao", tab: s.id }); }, html: `<span class="fl-n">${esc(s.n)}</span><span class="fl-t">${esc(s.titulo)}<small><i class="dot ${esc(s.tom)}"></i>${esc(s.estado)}</small></span>` }))),
    subs,
    h("div", { class: "fl-pr", html: `<span class="dim3">Estado inicial:</span> ${prontidao || '<span class="tag ok">sem constatações</span>'}` }),
    h("button", { class: "pill fl-cad", onclick: () => ir({ type: "nav", view: "operacao", tab: "caderno" }) }, "Caderno de ensaios"));
}

function folhaProntidao(D, ir) {
  const sec = D.secoes || [], linha = (s) => h("div", { class: "fl-chk", "data-chk": s.id, html: `<i class="dot ${esc(s.tom)}"></i><span><b>${esc(s.n)} · ${esc(s.titulo)}</b><small>${esc(s.estado)}${s.detalhe ? " — " + esc(s.detalhe) : ""}</small></span>` });
  const ver = D.alterado
    ? h("div", { class: "fl-ver w", html: `<b>Alterações não salvas</b><small>A verificação e a execução usam sempre a versão <b>salva</b> v${esc(D.versao)}. Salve na seção para incluí-las.</small>` })
    : h("div", { class: "fl-ver ok", html: `<b>Versão salva v${esc(D.versao)}</b><small>Sem alterações pendentes nesta sessão.</small>` });
  const pend = (D.pendencias || []).length ? h("div", { class: "fl-pend", html: `<div class="eyebrow">Declarações ausentes (estratégia V2)</div>` + D.pendencias.map((p) => `<div class="fl-pl"><span class="fl-n">${esc(p.n)}</span> ${esc(p.titulo)} <span class="tag w">${esc(p.pend)}</span></div>`).join("") }) : null;
  const veredito = h("div", { class: "fl-vd " + (D.executavel ? "ok" : "b"), "data-exec": D.executavel ? "sim" : "nao", html: D.executavel
    ? `<b>Pronto para executar a versão salva v${esc(D.versao)}</b><small>Preflight da versão salva aprovado.</small>`
    : `<b>Execução indisponível</b><small>${esc(D.motivo || "")}.</small>` });
  const acoes = [];
  if (D.tab !== "execucao") acoes.push(h("button", { class: "pill on fl-ir04", onclick: () => ir({ type: "nav", view: "operacao", tab: "execucao" }) }, "Preflight e execução (04)"));
  else acoes.push(h("div", { class: "sub fl-aqui" }, "O preflight completo e o botão de execução estão nesta seção."));
  if (D.ativa) acoes.push(h("button", { class: "pill fl-ativa", onclick: () => ir({ type: "abrir_rodada", run: D.ativa }) }, "Acompanhar a rodada em execução"));
  else if (D.ultima) acoes.push(h("button", { class: "pill fl-ult", onclick: () => ir({ type: "abrir_rodada", run: D.ultima.uid }), title: D.ultima.uid }, `Última rodada · v${D.ultima.versao} · ${D.ultima.estado}`));
  return h("div", { class: "panel fl-pron" }, h("div", { class: "eyebrow" }, "Prontidão do ensaio"), ver, h("div", { class: "fl-chks" }, ...sec.map(linha)), pend, veredito,
    h("div", { class: "fl-acoes" }, ...acoes),
    h("div", { class: "sub dim3" }, "Estados idênticos aos do painel do Centro de Operação; a compatibilidade com o motor é decidida pelo preflight da versão salva."));
}

function folhaRegua(R, titulo) {
  R = R || {};
  const nd = (v) => (v == null ? "N/D" : String(v)), d = R.delta_min, K = R.K, jan = janelasRegua(R);
  const fatos = h("div", { class: "fl-rfatos", html: [
    ["Passo Δ", d == null ? "N/D" : d + " min"], ["Missão", R.duracao_min == null ? "N/D" : durTxt(R.duracao_min) + (K != null ? ` · K_M = ${K}` : "")],
    ["Horizonte curto N", R.N == null ? "N/D" : `${R.N}` + (d ? ` · ${durTxt(R.N * d)}` : "")], ["Bloco aplicado m", R.m == null ? "N/D" : `${R.m}` + (d ? ` · ${durTxt(R.m * d)}` : "")],
    ["Horizonte longo H_L", R.H_L == null ? "N/D" : `${R.H_L}` + (d ? ` · ${durTxt(R.H_L * d)}` : "")], ["Janelas MPC", jan.length ? String(jan.length) : "N/D"]]
    .map(([a, b]) => `<span class="fl-rf"><small>${esc(a)}</small><b>${esc(b)}</b></span>`).join("") });
  const rel = (R.relacoes || []).length ? h("div", { class: "fl-rrel", html: R.relacoes.map(([t, ok, det]) => `<span class="tag ${ok ? "ok" : "b"}" title="${esc(det)}">${ok ? "✓" : "✕"} ${esc(t)}</span>`).join(" ") }) : null;
  let corpo;
  if (!(K > 0 && R.N > 0 && R.m > 0)) {
    corpo = h("div", { class: "fl-rvazio" }, "Régua incompleta — " + ((R.faltam || []).length ? "não declarado(s): " + R.faltam.join(", ") : "a duração da missão não é múltipla de Δ") + ". Nenhum valor é presumido.");
  } else {
    const W = 760, x0 = 132, x1 = W - 10, esc_ = (k) => x0 + (x1 - x0) * Math.min(k, K) / K, hL = R.H_L;
    const mostrar = jan.length <= 4 ? jan : [jan[0], jan[1], jan[2], jan[jan.length - 1]];
    const linhas = 2 + mostrar.length + (jan.length > 4 ? 1 : 0), Hh = 30 + linhas * 30 + 14;
    const kids = [];
    const rot = (y, t) => sv("text", { x: 4, y: y + 13, class: "fl-rt" }, t);
    // eixo da missão: K_M intervalos (marcas a cada intervalo até 96; senão a cada ⌈K/48⌉)
    const passo = K <= 96 ? 1 : Math.ceil(K / 48);
    kids.push(rot(20, `Missão · K_M = ${K}`), sv("rect", { x: x0, y: 22, width: x1 - x0, height: 14, rx: 3, class: "fl-rm" }));
    for (let k = 0; k <= K; k += passo) kids.push(sv("line", { x1: esc_(k), x2: esc_(k), y1: 36, y2: k % (passo * 4) === 0 ? 44 : 40, class: "fl-rtk" }));
    for (const k of [0, Math.round(K / 2), K]) kids.push(sv("text", { x: esc_(k), y: 56, class: "fl-rx", "text-anchor": k === 0 ? "start" : k === K ? "end" : "middle" }, d ? durTxt(k * d).replace("N/D", "0") : String(k)));
    let y = 64;
    if (hL > 0) {
      kids.push(rot(y, `Planejador · H_L = ${hL}`), sv("rect", { x: x0, y: y + 2, width: esc_(hL) - x0, height: 14, rx: 3, class: "fl-rhl" }));
      if (hL > K) kids.push(sv("text", { x: x1, y: y + 13, class: "fl-rx", "text-anchor": "end" }, "H_L > K_M"));
      y += 30;
    }
    for (const w of mostrar) {
      if (jan.length > 4 && w === jan[jan.length - 1]) { kids.push(sv("text", { x: x0, y: y + 13, class: "fl-rx" }, `… ${jan.length - 4} janela(s) intermediária(s) …`)); y += 30; }
      kids.push(rot(y, `Janela ${w.j + 1} · τ${w.j ? "₀+" + w.j + "m" : "₀"}`), sv("rect", { x: esc_(w.ini), y: y + 2, width: Math.max(2, esc_(w.fim) - esc_(w.ini)), height: 14, rx: 3, class: "fl-rn" }),
        sv("rect", { x: esc_(w.ini), y: y + 2, width: Math.max(2, esc_(w.ini + w.apl) - esc_(w.ini)), height: 14, rx: 3, class: "fl-ra" }));
      if (w.reduzida) kids.push(sv("text", { x: esc_(w.ini) - 5, y: y + 13, class: "fl-rx", "text-anchor": "end" }, `reduzida: ${w.fim - w.ini} < N`));
      y += 30;
    }
    corpo = sv("svg", { class: "fl-rsvg", viewBox: `0 0 ${W} ${Hh}`, role: "img", "aria-label": "Régua dos horizontes da missão" }, kids);
  }
  return h("div", { class: "panel fl-regua", "data-regua": jan.length ? "completa" : "incompleta" },
    h("div", { class: "eyebrow" }, titulo || "Régua dos horizontes (declarados)"), fatos, corpo,
    h("div", { class: "fl-rleg", html: '<span><i class="sw fl-ra"></i>bloco aplicado (m)</span><span><i class="sw fl-rn"></i>horizonte curto planejado (N)</span><span><i class="sw fl-rhl"></i>horizonte longo do planejador (H_L)</span>' }),
    rel, h("div", { class: "sub dim3" }, `A cada janela o MPC planeja N intervalos e aplica só os m primeiros; o planejador olha H_L intervalos à frente. Fim da missão: ${nd(R.terminal)}; cobertura: ${nd(R.cobertura)}. As relações acima são as que o preflight V2 verifica — aqui só são exibidas.`));
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component, D = data || {};
  const parte = D.parte || "indice", [root] = raizPt(parentElement, "pg folha fl-" + parte), sig = JSON.stringify(D);
  if (root.__sig === sig) return;
  root.__sig = sig;
  const ir = (a) => setTriggerValue("action", { ...a, t: Date.now() });
  root.replaceChildren(parte === "prontidao" ? folhaProntidao(D, ir) : parte === "regua" ? folhaRegua(D.regua, D.titulo) : folhaIndice(D, ir, root));
  if (parte === "indice" && !root.__spy) {           // subseção visível em destaque no índice (só leitura da rolagem)
    let pend = false;
    root.__spy = () => { if (pend) return; pend = true; requestAnimationFrame(() => {
      pend = false;
      const alvos = [...document.querySelectorAll("[data-fl-sub]")]; let atual = null;
      for (const a of alvos) if (a.getBoundingClientRect().top < 160) atual = a.dataset.flSub;
      const f = root.__forcado && document.querySelector(`[data-fl-sub="${root.__forcado}"]`);
      if (f && f.getBoundingClientRect().top >= 0 && f.getBoundingClientRect().top < innerHeight) atual = root.__forcado;
      for (const b of root.querySelectorAll(".fl-subl")) b.classList.toggle("on", b.dataset.sub === (atual || (alvos[0] && alvos[0].dataset.flSub)));
    }); };
    document.addEventListener("scroll", root.__spy, { capture: true, passive: true });
    for (const ev of ["wheel", "touchmove", "keydown"]) document.addEventListener(ev, () => { root.__forcado = null; }, { capture: true, passive: true });
  }
  if (root.__spy) root.__spy();
}
