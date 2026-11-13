// EXECUÇÃO EM ANDAMENTO (UI-RUNNING-01) — modal de acompanhamento de UMA rodada do motor V2.
// Só MOSTRA o estado que o servidor já grava (fase, k de n intervalos, janelas; desfecho e mensagem reais), recebido a cada
// ciclo do fragmento existente. Nada é estimado: porcentagem só quando ``determinado``; 100 % só com a rodada concluída.
// «Ocultar painel» é estado do navegador (a rodada continua no servidor); «Cancelar execução» devolve {type:"cancelar"} e o
// servidor decide. Ações: {type:"cancelar"|"diagnostico"|"fechar", run}. A estrutura é montada UMA vez por rodada e só
// atualizada (a animação não reinicia e o foco não é roubado a cada ciclo).
const MARCA_MX = "M3 12h18M7 12V6M12 12V4M17 12V7M9 12v6M15 12v5";
const REDE_MX = `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3l-7 26M16 3l7 26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M8 10h16M6.5 16.5h19M10.5 23h11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
const TITULOS_MX = { andamento: "Simulação em andamento", concluida: "Concluída", cancelando: "Cancelamento solicitado", cancelada: "Cancelada" };
const PILULA_MX = { andamento: ["Em execução", "i"], concluida: ["Concluída", "ok"], cancelando: ["Cancelando", "w"], cancelada: ["Cancelada", "w"], falha: ["Encerrada", "b"] };
const ROTULO_FASE_MX = { fila: "Fila", montagem: "Montagem", missao: "Missão MPC", auditoria: "Auditoria", gravando: "Gravação" };

// Texto do progresso (PURO; testado em Node): nunca inventa porcentagem nem tempo restante.
function progressoMx(D) {
  const pct = D.determinado && D.fracao != null ? Math.floor(100 * D.fracao) : null;
  let rotulo;
  if (D.situacao === "concluida") rotulo = D.n ? `Intervalos ${D.n} de ${D.n} · missão concluída e gravada` : "Missão concluída e gravada";
  else if (D.situacao !== "andamento") rotulo = D.k != null && D.n ? `Parou em ${D.k} de ${D.n} intervalos` : "Sem progresso registrado";
  else if (D.fase === "missao" && D.k != null && D.n) rotulo = `Intervalo ${D.k} de ${D.n}` + (D.janelas != null ? ` · ${D.janelas} janela(s) resolvida(s)` : "");
  else rotulo = D.fase_rotulo || "Em execução";
  return { pct, rotulo, largura: D.situacao === "concluida" ? 100 : pct };
}

const ESPERA_RESPOSTA_MX = 20000;
const SEM_RESPOSTA_MX = "O servidor não respondeu ao pedido de cancelamento; nada indica que a rodada tenha sido cancelada. A execução continua.";
function atualizarMsgMx(root) {
  // mensagem do desfecho (gravada) OU a recusa/falta de resposta ao pedido de cancelamento (a execução segue)
  const D = root.__D || {}, msg = root.querySelector(".mx-msg"), r = D.situacao === "andamento" ? root.__recusa : null;
  const texto = D.mensagem || (r ? "Cancelamento NÃO realizado — " + r.mensagem : "");
  msg.hidden = !texto; msg.textContent = texto;
  msg.className = "mx-msg " + (D.situacao === "falha" ? "b" : "w");
  if (r) msg.dataset.recusa = r.situacao; else delete msg.dataset.recusa;
}
function svgMx(G) {
  // mini-diagrama ABSTRATO (decorativo): fontes → barramento → armazenamento/rede, pulsos delicados. Não representa fluxos.
  const no = (x, y, k, cor, ico) => `<g class="mx-no" style="--kc:${cor}" transform="translate(${x - 17} ${y - 17})"><circle cx="17" cy="17" r="17" class="mx-nf"/><g transform="translate(6 6)" class="mx-ni">${(ico || "").replace("<svg ", '<svg width="22" height="22" ')}</g></g>`;
  const fio = (d, cor, i, saida) => `<path d="${d}" class="mx-fio" style="--kc:${cor}"/><path d="${d}" class="mx-pulso${saida ? " sai" : ""}" style="--kc:${cor};animation-delay:${-0.55 * i}s"/>`;
  return `<svg viewBox="0 0 260 150" class="mx-svg" aria-hidden="true" focusable="false">
    <defs><linearGradient id="mxg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--ink)" stop-opacity=".15"/><stop offset=".5" stop-color="var(--ink)" stop-opacity=".9"/><stop offset="1" stop-color="var(--ink)" stop-opacity=".15"/></linearGradient></defs>
    ${fio("M51 28 C 90 28, 100 52, 128 60", "var(--k-pv)", 0)}${fio("M51 75 L 128 75", "var(--k-wind)", 1)}${fio("M51 122 C 90 122, 100 98, 128 90", "var(--k-pemfc)", 2)}
    ${fio("M132 64 C 160 52, 175 44, 209 44", "var(--k-battery)", 3, true)}${fio("M132 86 C 160 98, 175 106, 209 106", "var(--s-grid)", 4, true)}
    <rect x="125" y="18" width="10" height="114" rx="5" class="mx-bus"/><rect x="125" y="18" width="10" height="114" rx="5" class="mx-bus-brilho"/>
    ${no(34, 28, "pv", "var(--k-pv)", G.pv)}${no(34, 75, "wind", "var(--k-wind)", G.wind)}${no(34, 122, "pemfc", "var(--k-pemfc)", G.pemfc)}
    ${no(226, 44, "battery", "var(--k-battery)", G.battery)}${no(226, 106, "grid", "var(--s-grid)", REDE_MX)}</svg>`;
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component, D = data || {};
  const [root] = raizPt(parentElement, "pg mx");
  const G = typeof ICONES_GESTOR !== "undefined" ? ICONES_GESTOR : {};
  const chave = "seeds2.execucao.oculto." + D.run, ir = (a) => setTriggerValue("action", { run: D.run, t: Date.now(), ...a });
  const lerOculto = () => { try { return sessionStorage.getItem(chave); } catch (_) { return null; } };
  const gravarOculto = (v) => { try { if (v == null) sessionStorage.removeItem(chave); else sessionStorage.setItem(chave, v); } catch (_) { /* sem armazenamento */ } };
  const sig = JSON.stringify(D);
  if (root.__sig === sig && root.__run === D.run) return;
  root.__sig = sig;

  if (root.__run !== D.run) {                                   // estrutura montada uma vez por rodada
    root.__run = D.run; root.__confirmar = false; root.__aberto = null; root.__pedido = null; root.__recusa = null;
    root.innerHTML = `
      <div class="mx-faixa" hidden><span class="mx-faixa-t"><i class="mx-led"></i><span class="mx-faixa-txt"></span></span><button type="button" class="pill on mx-reabrir">ACOMPANHAR EXECUÇÃO</button></div>
      <div class="mx-fundo" hidden><div class="mx-card" role="dialog" aria-modal="true" aria-labelledby="mx-titulo" aria-describedby="mx-desc" tabindex="-1">
        <header class="mx-cab"><span class="mx-marca">${icoPt(MARCA_MX, 22)}<b>SEEDS2</b><span class="mx-sub">RUNNING SIMULATION</span></span><span class="tag mx-pilula"></span></header>
        <div class="mx-corpo">
          <div class="mx-anim">${svgMx(G)}</div>
          <div class="mx-info">
            <h2 id="mx-titulo" class="mx-titulo"></h2>
            <div class="mx-cen"></div>
            <div class="mx-meta"></div>
            <ol class="mx-fases" aria-label="Fases da execução"></ol>
          </div>
        </div>
        <div class="mx-prog">
          <div class="mx-prog-l"><span class="mx-prog-t" id="mx-desc" aria-live="polite"></span><span class="mx-pct"></span></div>
          <div class="mx-barra" role="progressbar" aria-labelledby="mx-desc" aria-valuemin="0" aria-valuemax="100"><span class="mx-cheio"></span></div>
          <div class="mx-hor" aria-hidden="true"><span class="mx-hor-feito"></span><span class="mx-hor-jan"></span></div>
          <div class="mx-hor-l dim3"></div>
        </div>
        <footer class="mx-rod">
          <div class="mx-msg" role="status" hidden></div>
          <span class="mx-nota dim3"></span>
          <span class="mx-acoes"></span>
        </footer>
      </div></div>`;
    const fundo = root.querySelector(".mx-fundo"), card = root.querySelector(".mx-card");
    card.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); root.__ocultar(); return; }
      if (e.key !== "Tab") return;                              // foco preso no diálogo
      const f = [...card.querySelectorAll("button:not([disabled])")]; if (!f.length) { e.preventDefault(); return; }
      const sr = card.getRootNode(), at = sr.activeElement || document.activeElement, i = f.indexOf(at);
      if (e.shiftKey && (i <= 0)) { e.preventDefault(); f[f.length - 1].focus(); } else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
    });
    fundo.addEventListener("mousedown", (e) => { if (e.target === fundo) root.__ocultar(); });   // clique fora = ocultar (nunca cancelar)
    root.querySelector(".mx-reabrir").addEventListener("click", () => { gravarOculto(null); root.__mostrar(true); });
  }
  const P = progressoMx(D), fundo = root.querySelector(".mx-fundo"), card = root.querySelector(".mx-card"), faixa = root.querySelector(".mx-faixa");
  root.__ocultar = () => { gravarOculto(D.situacao); root.__mostrar(false); };
  root.__mostrar = (abrir) => {
    const antes = root.__aberto; root.__aberto = abrir; fundo.hidden = !abrir; faixa.hidden = abrir;
    if (abrir && !antes) {                                       // foco no diálogo ao abrir (repetido: um rerun pode tomá-lo)
      const focar = () => { const sr = card.getRootNode(); if (!card.contains(sr.activeElement)) (card.querySelector(".mx-pri") || card).focus({ preventScroll: true }); };
      [30, 350, 900].forEach((t) => setTimeout(() => { if (root.__aberto) focar(); }, t));
    }
    if (!abrir && antes) setTimeout(() => root.querySelector(".mx-reabrir").focus({ preventScroll: true }), 30);
  };
  // conteúdo
  const titulo = D.situacao === "falha" ? D.titulo_falha || "Falha na execução" : TITULOS_MX[D.situacao] || "Simulação em andamento";
  root.querySelector(".mx-titulo").textContent = titulo;
  const [pt, pc] = PILULA_MX[D.situacao] || PILULA_MX.andamento; const pil = root.querySelector(".mx-pilula"); pil.textContent = pt; pil.className = "tag mx-pilula " + pc;
  root.querySelector(".mx-cen").textContent = `${D.cenario} · versão ${D.versao}`;
  root.querySelector(".mx-meta").innerHTML = `rodada <span class="uid">${esc(D.curto)}…</span> · ` + esc([D.motor, D.N != null && D.m != null ? `N = ${D.N} · m = ${D.m}${D.H_L != null ? ` · H_L = ${D.H_L}` : ""}` : null, D.inicio ? `iniciada ${D.inicio}` : null].filter(Boolean).join(" · "));
  root.classList.toggle("parado", D.situacao !== "andamento");          // animação só enquanto a missão roda
  const ia = (D.fases || []).indexOf(D.fase);
  root.querySelector(".mx-fases").innerHTML = (D.fases || []).map((f, i) => `<li class="${D.situacao === "concluida" || (D.situacao === "andamento" && i < ia) ? "ok" : D.situacao === "andamento" && i === ia ? "on" : ""}"${D.situacao === "andamento" && i === ia ? ' aria-current="step"' : ""}>${esc(ROTULO_FASE_MX[f] || f)}</li>`).join("");
  root.querySelector(".mx-prog-t").textContent = P.rotulo;
  root.querySelector(".mx-pct").textContent = P.pct != null ? P.pct + " %" : "";
  const barra = root.querySelector(".mx-barra"), cheio = root.querySelector(".mx-cheio");
  barra.classList.toggle("indet", P.largura == null && D.situacao === "andamento"); barra.classList.toggle("parada", D.situacao !== "andamento" && D.situacao !== "concluida");
  if (P.largura != null) { cheio.style.width = P.largura + "%"; barra.setAttribute("aria-valuenow", String(P.largura)); } else { cheio.style.width = ""; barra.removeAttribute("aria-valuenow"); }
  barra.setAttribute("aria-valuetext", P.rotulo);
  // horizonte recedente REAL: aplicado 0..k e a janela de N intervalos a partir de k (só com N, k e n gravados)
  const hor = root.querySelector(".mx-hor"), hl = root.querySelector(".mx-hor-l");
  if (D.n && D.k != null && D.N) {
    hor.hidden = false; hl.hidden = false; const f = Math.min(D.k, D.n) / D.n, w = Math.min(D.N, Math.max(0, D.n - D.k)) / D.n;
    root.querySelector(".mx-hor-feito").style.width = 100 * f + "%"; const jan = root.querySelector(".mx-hor-jan"); jan.style.left = 100 * f + "%"; jan.style.width = 100 * w + "%";
    hl.textContent = D.situacao === "andamento" && D.k < D.n ? `Horizonte MPC: próxima janela de ${Math.min(D.N, D.n - D.k)} intervalo(s) a partir de ${D.k}` : "Horizonte MPC";
  } else { hor.hidden = true; hl.hidden = true; }
  // pedido de cancelamento: só a RESPOSTA do servidor ao MESMO pedido (``pedido`` = id enviado) o resolve
  const R = D.resposta_cancelamento;
  if (D.situacao !== "andamento") { root.__pedido = null; root.__recusa = null; }
  else if (root.__pedido && R && R.pedido === root.__pedido && R.situacao !== "solicitado") {
    root.__pedido = null; root.__recusa = { situacao: R.situacao, mensagem: R.mensagem };      // recusado: nada foi cancelado
  }
  root.__D = D;
  atualizarMsgMx(root);
  root.querySelector(".mx-nota").textContent = D.situacao === "andamento" ? "A execução continua no servidor mesmo que o painel seja ocultado ou a página recarregada."
    : D.situacao === "cancelando" ? "A janela em curso termina no solver e é descartada; nenhum resultado será gravado."
      : D.situacao === "concluida" ? "Abrindo os resultados gravados…" : "Nenhum resultado foi gravado como concluído.";
  // ações (relidas do estado MAIS RECENTE a cada ciclo e a cada clique; a confirmação do cancelamento é local)
  const renderAcoes = (focar) => {
    const X = root.__D, acoes = root.querySelector(".mx-acoes");
    // só recria os botões quando o CONJUNTO de ações muda (recriar a cada ciclo tiraria o foco do teclado)
    const assin = JSON.stringify([X.situacao, X.cancelavel, X.motivo_cancelamento, !!root.__confirmar, !!root.__pedido]);
    if (!focar && acoes.__assin === assin) return;
    acoes.__assin = assin;
    const btn = (t, cls, f, extra = {}) => h("button", { type: "button", class: "pill " + cls, onclick: f, ...extra }, t);
    const lista = [];
    if (X.situacao === "andamento" && root.__confirmar && X.cancelavel) {
      const sim = btn("SIM, CANCELAR", "mx-perigo on", () => {
        if (root.__pedido) return;                                // um pedido por vez (sem cliques duplicados)
        const id = Date.now(); root.__confirmar = false; root.__pedido = id; root.__recusa = null;
        ir({ type: "cancelar", t: id }); atualizarMsgMx(root); renderAcoes(true);
        setTimeout(() => {                                         // sem resposta do servidor ⇒ nada indica cancelamento
          if (root.__pedido !== id || !root.__D || root.__D.situacao !== "andamento") return;
          root.__pedido = null; root.__recusa = { situacao: "sem_resposta", mensagem: SEM_RESPOSTA_MX };
          atualizarMsgMx(root); renderAcoes(true);
        }, ESPERA_RESPOSTA_MX);
      });
      lista.push(h("span", { class: "mx-conf" }, "Cancelar esta rodada? A janela em curso termina e é descartada; nada é gravado."),
        btn("VOLTAR", "mx-pri", () => { root.__confirmar = false; renderAcoes(true); }), sim);
      acoes.replaceChildren(...lista); if (focar) setTimeout(() => sim.focus({ preventScroll: true }), 20); return;
    }
    root.__confirmar = false;
    if (X.situacao === "andamento" && root.__pedido) {      // pedido enviado: o servidor confirma no próximo ciclo
      lista.push(btn("OCULTAR PAINEL", "mx-pri", () => root.__ocultar()), btn("CANCELAMENTO SOLICITADO…", "mx-perigo", null, { disabled: true }));
    } else if (X.situacao === "andamento") {
      lista.push(btn("OCULTAR PAINEL", "mx-pri", () => root.__ocultar()),
        btn("CANCELAR EXECUÇÃO", "mx-perigo", () => { root.__confirmar = true; root.__recusa = null; atualizarMsgMx(root); renderAcoes(true); },
          X.cancelavel ? {} : { disabled: true, title: X.motivo_cancelamento || "Cancelamento indisponível para esta execução" }));
      if (!X.cancelavel && X.motivo_cancelamento) lista.push(h("span", { class: "mx-motivo dim3" }, X.motivo_cancelamento));
    } else if (X.situacao === "concluida") {
      lista.push(btn("OCULTAR PAINEL", "mx-pri", () => root.__ocultar()));
    } else {
      lista.push(btn("FECHAR", "mx-pri", () => { root.__ocultar(); ir({ type: "fechar" }); }),
        btn("VER DIAGNÓSTICO", "on", () => ir({ type: "diagnostico" }), X.situacao === "cancelando" ? { disabled: true, title: "Aguardando a janela em curso terminar" } : {}));
    }
    acoes.replaceChildren(...lista);
    if (focar) { const b = acoes.querySelector("button:not([disabled])"); if (b) setTimeout(() => b.focus({ preventScroll: true }), 20); }
  };
  renderAcoes(false);
  root.querySelector(".mx-faixa-txt").textContent = `${titulo} · ${P.rotulo}`;
  // UI-FINISH-01: pedido explícito de reabrir (cartão de rodada «VER PROGRESSO DA RODADA»): esquece o «oculto» uma vez
  if (D.abrir != null && D.abrir !== root.__abrirVisto) { root.__abrirVisto = D.abrir; gravarOculto(null); }
  // visível? oculto vale só enquanto o desfecho não muda (uma falha/cancelamento/conclusão reabre o painel)
  root.__mostrar(lerOculto() !== D.situacao);
}
