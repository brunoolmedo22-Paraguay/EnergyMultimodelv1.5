// E2E do UI-FINISH-01 em navegador real (Chromium/Playwright) sobre um servidor com HiGHS e os dados de
// tools/e2e/seed_ui_finish.py. Fases: catálogo + bancadas → etapa 04 (cartão de rodada, preflight compacto) → modal
// (overlay/desfoque estável durante ≥ 10 progressos; ocultar/reabrir; cancelar) → exportações (cada gráfico PNG/SVG
// claro/escuro; PDF, ZIP e Excel da rodada; estudo arquivado). Os arquivos baixados vão para <saída>/baixados e são
// conferidos por tools/e2e/check_ui_finish.py.
// Uso: node e2e_ui_finish.js <url> <seed_ui_finish.json> <pasta de saída> <preparo|exportar>
//   preparo  = fases 1–3 (servidor COM solver: a missão longa roda e é cancelada);
//   exportar = fase 4 (servidor SEM solver, motor e modelos sabotados: nenhum documento pode chamar o motor).
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const [base, seedf, out, modo] = process.argv.slice(2);
const s = JSON.parse(fs.readFileSync(seedf, "utf8"));
const caps = path.join(out, "capturas"), baix = path.join(out, "baixados");
fs.mkdirSync(caps, { recursive: true }); fs.mkdirSync(baix, { recursive: true });
let n = 0; const falhas = [], log = (...a) => console.log("[ui-finish]", ...a), res = {};
function ok(c, msg) { if (c) { n += 1; log("ok —", msg); } else { falhas.push(msg); log("FALHA —", msg); } }

(async () => {
  const b = await chromium.launch();
  const nova = async (w, h, extra = {}) => {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, locale: "pt-BR", acceptDownloads: true, ...extra });
    const p = await ctx.newPage();
    p.on("pageerror", (e) => falhas.push(`${w}×${h} erro de página: ` + String(e).slice(0, 300)));
    p.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) falhas.push("console: " + m.text().slice(0, 200)); });
    return p;
  };
  const pronto = async (p) => { await p.waitForTimeout(1500); await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 120000 }).catch(() => {}); await p.waitForTimeout(800); };
  const foto = (p, nome, full = false) => p.screenshot({ path: path.join(caps, nome + ".png"), fullPage: full });
  const baixa = async (p, fn, prefixo = "") => { const [d] = await Promise.all([p.waitForEvent("download", { timeout: 180000 }), fn()]); const f = path.join(baix, prefixo + d.suggestedFilename()); await d.saveAs(f); return f; };

  let p;
  if (modo !== "exportar") {
  // ------------------------------------------------------------------ 1. catálogo e bancadas sem microrrede
  p = await nova(1440, 900);
  await p.goto(base + "/"); await p.locator(".gc-tg").first().waitFor({ timeout: 120000 }); await pronto(p); await p.mouse.move(1300, 120); await p.waitForTimeout(400);
  const cartoes = () => p.evaluate(() => [...document.querySelectorAll('[class*="st-key-mgc_"]')].map((c) => {
    const vis = (e) => !!e && getComputedStyle(e).display !== "none" && e.getBoundingClientRect().height > 0;
    return { h: Math.round(c.getBoundingClientRect().height), det: vis(c.querySelector(".gc-det")), botoes: [...c.querySelectorAll("button")].filter((x) => vis(x) && x.offsetParent !== null).length,
      convite: (c.querySelector(".gc-tg") || {}).textContent || "", aberto: !!c.querySelector(".gc-x[open]") }; }));
  let cs = await cartoes();
  ok(cs.length === 3 && cs.every((c) => !c.det && c.botoes === 0), `catálogo: ${cs.length} cartões recolhidos, sem detalhe e sem NENHUM botão visível`);
  ok(cs.every((c) => c.convite.includes("Passe o mouse ou clique para expandir")), "convite «Passe o mouse ou clique para expandir»");
  await foto(p, "01_catalogo_recolhido");
  const c0 = p.locator('[class*="st-key-mgc_"]').first(), bx = await c0.boundingBox();
  await p.mouse.move(bx.x + bx.width / 2, bx.y + 30); await p.waitForTimeout(400); cs = await cartoes();
  ok(cs[0].det && cs[0].botoes >= 4 && !cs[1].det, `hover expande SÓ o cartão sob o mouse (${cs[0].botoes} ações; ${cs[0].h} px × recolhido ${cs[1].h} px)`);
  await foto(p, "02_catalogo_hover");
  await p.mouse.move(1300, 120); await p.waitForTimeout(400); ok(!(await cartoes())[0].det, "sair do cartão recolhe");
  await c0.locator(".gc-tg").click(); await p.mouse.move(1300, 120); await p.waitForTimeout(400); cs = await cartoes();
  ok(cs[0].det && cs[0].aberto, "clique no convite fixa o cartão aberto (sem abrir nem excluir nada)");
  await c0.locator(".gc-tg").click(); await p.mouse.move(1300, 120); await p.waitForTimeout(400); ok(!(await cartoes())[0].det, "novo clique recolhe");
  await p.mouse.click(1300, 60); const foco = [];
  for (let i = 0; i < 16; i++) { await p.keyboard.press("Tab"); foco.push(await p.evaluate(() => { const a = document.activeElement; return a.tagName + ":" + (a.textContent || "").trim().slice(0, 24); })); }
  ok(!foco.some((f) => /ABRIR MICRORREDE|^BUTTON:.*ZIP$|Excluir/.test(f)), "Tab não alcança ações escondidas dos cartões recolhidos");
  await c0.locator(".gc-tg").focus(); await p.keyboard.press("Enter"); await p.waitForTimeout(300); ok((await cartoes())[0].det, "Enter no convite expande");
  await p.keyboard.press("Tab"); ok(/ABRIR MICRORREDE/.test(await p.evaluate(() => document.activeElement.textContent)), "Tab seguinte vai para ABRIR MICRORREDE");
  await c0.locator(".gc-tg").focus(); await p.keyboard.press("Space"); await p.waitForTimeout(300); ok(!(await cartoes())[0].det, "Espaço recolhe");
  await p.mouse.move(28, 400); await p.waitForTimeout(700); await foto(p, "03_barra_lateral_sem_microrrede");
  const ids = await p.locator(".pt.sb .it").evaluateAll((xs) => xs.map((x) => x.getAttribute("data-id")));
  ok(["bancada_solar", "bancada_wind", "bancada_battery", "bancada_h2", "bancada_thermal"].every((i) => ids.includes(i)) && ids.filter((i) => i.startsWith("bancada_")).length === 5,
     "sem microrrede: as cinco bancadas na barra lateral (sem duplicação)");
  for (const [f, marca] of [["solar", "SOLAR"], ["wind", "EÓLICA"], ["battery", "BATERIA"], ["h2", "HIDROGÊNIO"], ["thermal", "TÉRMICA"]]) {
    await p.goto(base + "/"); await p.locator(".pt.sb .brand").waitFor({ timeout: 120000 }); await pronto(p);
    await p.locator(`.pt.sb .it[data-id="bancada_${f}"]`).click(); await p.waitForTimeout(5000);
    const txt = await p.locator("body").innerText();
    ok(txt.toUpperCase().includes(marca) && (await p.locator(".pt.sb").count()) === 0, `bancada ${f} aberta sem microrrede`);
    await p.getByRole("button", { name: /FONTES DE ENERGIA/ }).first().click(); await p.waitForTimeout(3500);
    ok((await p.locator(".gc-tg").count()) > 0, `bancada ${f}: «← FONTES DE ENERGIA» volta ao catálogo`);
  }
  await p.context().close();
  const pm = await nova(390, 844, { isMobile: true, hasTouch: true });
  await pm.goto(base + "/"); await pm.locator(".gc-tg").first().waitFor({ timeout: 120000 }); await pronto(pm);
  ok(await pm.locator(".st-key-gestor_bancadas_movel").isVisible() && (await pm.locator(".st-key-gestor_bancadas_movel button").count()) === 5, "celular: bancadas no fim do catálogo");
  await pm.locator('[class*="st-key-mgc_"] .gc-tg').first().tap(); await pm.waitForTimeout(400);
  ok(await pm.locator('[class*="st-key-mgc_"]').first().getByRole("button", { name: "ABRIR MICRORREDE" }).isVisible(), "celular: toque no convite expande");
  ok(await pm.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), "celular: sem rolagem horizontal");
  await foto(pm, "04_catalogo_celular_expandido", true); await pm.context().close();

  // ------------------------------------------------------------------ 2. etapa 04: cartão de rodada e preflight compacto
  for (const [nome, sc, w, h, apto] of [["apta_1440", s.exp, 1440, 900, true], ["apta_1366", s.exp, 1366, 768, true], ["bloqueada_1440", s.bloq, 1440, 900, false], ["apta_390", s.exp, 390, 844, true]]) {
    p = await nova(w, h, w < 500 ? { isMobile: true, hasTouch: true } : {});
    await p.goto(`${base}/?view=operacao&tab=execucao&mg=${s.lab}&sc=${sc}`); await p.locator(".st-key-fl_cta").waitFor({ timeout: 180000 }); await pronto(p); await p.mouse.move(w - 4, h - 4);
    const g = await p.evaluate(() => { const r = (e) => e && e.getBoundingClientRect(), f = r(document.querySelector(".st-key-seeds_folha")), c = r(document.querySelector(".st-key-fl_cta")), sc = r(document.querySelector(".st-key-fl_col_secao"));
      return { fy: f.y + f.height, cy: c.y, cx: c.x, fx: f.x, sy: sc.y, sx: sc.x, estado: document.querySelector('[data-rc="estado"]').innerText.replace(/\s+/g, " "),
        bloq: (document.querySelector('[data-pf="bloqueios"]') || {}).innerText || "", resumo: (document.querySelector('[data-pf="resumo"]') || {}).innerText.replace(/\s+/g, " ") }; });
    const run = p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ });
    ok((await run.count()) === 1 && (await p.locator(".st-key-fl_cta").getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).count()) === 1, `${nome}: UM botão EXECUTAR, dentro do cartão de rodada`);
    ok(g.cy >= g.fy - 2 && Math.abs(g.cx - g.fx) < 40, `${nome}: cartão logo abaixo da Folha (Folha termina em ${Math.round(g.fy)}, cartão começa em ${Math.round(g.cy)})`);
    if (w < 500) ok(g.cy < g.sy, `${nome}: no celular o cartão vem ANTES do conteúdo da seção`);
    ok(apto ? (/Pronto para executar/.test(g.estado) && await run.isEnabled()) : (/Execução bloqueada/.test(g.estado) && await run.isDisabled() && /Revisar/.test(g.estado)),
       `${nome}: estado do cartão = preflight real (${g.estado.slice(0, 80)})`);
    ok(apto || /Estratégia MILP–MPC/.test(g.bloq), `${nome}: bloqueio visível com texto e orientação`);
    const exp = p.getByText(/Ver \d+ verificações aprovadas/); ok((await exp.count()) === 1, `${nome}: verificações aprovadas recolhidas («${(await exp.first().innerText()).slice(0, 34)}…»)`);
    res["etapa04_" + nome] = g; await foto(p, "05_etapa04_" + nome); await p.context().close();
  }

  // ------------------------------------------------------------------ 3. modal: overlay estável, ocultar/reabrir, cancelar
  p = await nova(1440, 900);
  await p.goto(`${base}/?view=operacao&tab=execucao&mg=${s.lab}&sc=${s.longa}`); await p.locator(".st-key-fl_cta").waitFor({ timeout: 180000 }); await pronto(p); await p.mouse.move(800, 400);
  await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).click(); await p.locator(".pt.mx .mx-card").waitFor({ timeout: 60000 }); await p.waitForTimeout(1500);
  const quadros = []; let antes = "";
  for (let i = 0; quadros.length < 30 && i < 120; i++) {
    const info = await p.evaluate(() => { const f = [...document.querySelectorAll("*")].map((e) => e.shadowRoot && e.shadowRoot.querySelector(".pt.mx .mx-fundo")).find(Boolean); const c = f && getComputedStyle(f);
      return { stale: !!document.querySelector('.st-key-seeds_execucao[data-stale="true"]'), op: c && c.opacity, bf: c && c.backdropFilter, disp: c && c.display, txt: (f && f.querySelector(".mx-prog-t") || {}).textContent }; });
    const arq = path.join(out, `q${String(quadros.length).padStart(2, "0")}.png`); await p.screenshot({ path: arq }); quadros.push({ ...info, arq });
    if (info.txt !== antes) antes = info.txt;
  }
  fs.writeFileSync(path.join(out, "modal_quadros.json"), JSON.stringify(quadros));
  const textos = new Set(quadros.map((q) => q.txt));
  ok(textos.size >= 10, `modal: ${textos.size} progressos DISTINTOS observados (≥ 10)`);
  ok(quadros.every((q) => q.disp === "grid" && q.op === "1" && /blur/.test(q.bf)), "modal: overlay visível com o mesmo desfoque em todos os quadros (estilo computado)");
  ok(quadros.some((q) => q.stale), `modal: ${quadros.filter((q) => q.stale).length} quadro(s) capturado(s) DURANTE a atualização do fragmento (stale)`);
  await foto(p, "06_modal_em_execucao");
  await p.getByRole("button", { name: "OCULTAR PAINEL" }).click(); await p.waitForTimeout(600);
  ok(!(await p.locator(".pt.mx .mx-card").isVisible()), "ocultar não cancela: painel oculto, rodada segue");
  await p.locator(".st-key-fl_cta").getByRole("button", { name: "VER PROGRESSO DA RODADA" }).click(); await p.waitForTimeout(3000);
  ok(await p.locator(".pt.mx .mx-card").isVisible(), "cartão de rodada «VER PROGRESSO DA RODADA» reabre o modal");
  ok(/Em execução/.test(await p.locator('[data-rc="estado"]').innerText()) && await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).isDisabled(), "durante a rodada: cartão «Em execução», executar desabilitado");
  await p.getByRole("button", { name: "CANCELAR EXECUÇÃO" }).click(); await p.getByRole("button", { name: "SIM, CANCELAR" }).click();
  for (let i = 0; i < 200; i++) { if ((await p.locator(".pt.mx .mx-titulo").textContent()) === "Cancelada") break; await p.waitForTimeout(300); }
  await p.waitForTimeout(800); await p.locator(".pt.mx .mx-acoes").getByRole("button", { name: "FECHAR" }).click(); await p.waitForTimeout(3500);
  ok(/Pronto para executar/.test(await p.locator('[data-rc="estado"]').innerText()) && await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).isEnabled(), "após cancelar e FECHAR: cartão volta a «Pronto»");
  await p.context().close();
  }
  if (modo !== "preparo") {
  // ------------------------------------------------------------------ 4. exportações
  p = await nova(1440, 900, { colorScheme: "dark" });
  await p.goto(`${base}/?view=operacao&tab=rodada&mg=${s.lab}&sc=${s.exp}&run=${s.run}`); await p.locator(".pt.partitura svg.trama").first().waitFor({ timeout: 120000 }); await pronto(p); await p.mouse.move(1100, 650);
  const xb = p.locator(".pt.partitura .stage .xp-btn").first(); ok(await xb.isVisible(), "Partitura: botão Exportar no gráfico");
  await xb.click(); await p.waitForTimeout(300); await foto(p, "07_menu_exportar_grafico");
  const arqs = [];
  for (const v of ["png-light", "png-dark", "svg-light", "svg-dark"]) {
    if (!(await p.locator(".pt.partitura .stage .xp-menu").isVisible())) await xb.click();
    arqs.push(await baixa(p, () => p.locator(`.pt.partitura .stage .xp-menu [data-xp="${v}"]`).click()));
  }
  await p.locator(".pt.partitura .rowb", { hasText: "Bateria" }).first().click(); await p.locator(".pt.partitura .dlg").waitFor(); await p.waitForTimeout(900);
  const db = p.locator(".pt.partitura .dlg .xp-btn").first();
  await db.click(); arqs.push(await baixa(p, () => p.locator('.pt.partitura .dlg .xp-menu [data-xp="png-light"]').first().click(), "bateria_"));
  await db.click(); arqs.push(await baixa(p, () => p.locator('.pt.partitura .dlg .xp-menu [data-xp="svg-dark"]').first().click(), "bateria_"));
  await foto(p, "08_painel_bateria"); await p.keyboard.press("Escape"); await p.waitForTimeout(500);
  ok(arqs.length === 6, `6 imagens de gráfico baixadas (${arqs.map((f) => path.basename(f)).join(", ")})`);
  const area = p.locator('[class*="exportacoes_v2"]'); await area.scrollIntoViewIfNeeded(); await p.waitForTimeout(500);
  const rot = await area.getByRole("button").allInnerTexts();
  ok(["GERAR RELATÓRIO PDF", "BAIXAR TODAS AS FIGURAS (ZIP)", "EXPORTAR TABELAS EXCEL (.xlsx)"].every((r) => rot.includes(r)), "área de exportações visível com os três botões");
  await foto(p, "09_area_exportacoes");
  for (const [r, d] of [["GERAR RELATÓRIO PDF", "BAIXAR RELATÓRIO PDF"], ["BAIXAR TODAS AS FIGURAS (ZIP)", "BAIXAR FIGURAS (PNG + SVG)"], ["EXPORTAR TABELAS EXCEL (.xlsx)", "BAIXAR DADOS EXCEL"]]) {
    await area.getByRole("button", { name: r }).click(); const bt = area.getByRole("button", { name: d }); await bt.waitFor({ timeout: 180000 }); await p.waitForTimeout(400);
    arqs.push(await baixa(p, () => bt.click()));
  }
  await foto(p, "10_exportacoes_prontas"); await p.context().close();
  p = await nova(1440, 900);
  await p.goto(`${base}/?view=arquivo&tab=estudo&study=${s.estudo}&srun=${s.run}`); await p.locator(".pt.partitura svg.trama").first().waitFor({ timeout: 120000 }); await pronto(p);
  const aq = p.locator('[class*="exportacoes_v2"]'); await aq.scrollIntoViewIfNeeded();
  await aq.getByRole("button", { name: "EXPORTAR TABELAS EXCEL (.xlsx)" }).click(); const bq = aq.getByRole("button", { name: "BAIXAR DADOS EXCEL" }); await bq.waitFor({ timeout: 180000 });
  arqs.push(await baixa(p, () => bq.click(), "estudo_")); ok(true, "estudo arquivado: Excel exportado sem a microrrede");
  await p.context().close();
  res.arquivos = arqs.map((f) => path.basename(f));
  }
  fs.writeFileSync(path.join(out, `e2e_ui_finish_${modo || "tudo"}.json`), JSON.stringify({ verificacoes: n, falhas, ...res }, null, 1));
  await b.close();
  if (falhas.length) { console.error("FALHAS:\n" + falhas.join("\n")); process.exit(1); }
  log(`CONCLUÍDO — ${n} verificações aprovadas, sem erros de página nem de console`);
})().catch((e) => { console.error(e); process.exit(1); });
