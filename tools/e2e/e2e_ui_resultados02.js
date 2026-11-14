// E2E do UI-RESULTADOS-02 (navegador real sobre o servidor Streamlit): exemplo C4 restaurado.
//   abertura em Operação → tarifa escalonada → Visão Geral (e reabertura volta a Operação) → painéis Solar, Bateria, Rede e
//   Carga líquida (demanda de referência) → tela AMPLIADA (6 h) → «Relatório PDF» da Partitura → download no painel →
//   pedido pelo botão do painel → download. Capturas para a evidência; resultado em <saída>/e2e_ui_resultados02.json.
// Uso: node e2e_ui_resultados02.js <porta> <seed.json> <saída> [pasta de capturas]
const { chromium } = require("playwright"); const fs = require("fs"); const path = require("path");
const [porta, seedf, out, caps] = process.argv.slice(2), s = JSON.parse(fs.readFileSync(seedf, "utf8")), base = `http://localhost:${porta}`;
fs.mkdirSync(path.join(out, "baixados"), { recursive: true }); if (caps) fs.mkdirSync(caps, { recursive: true });
const falhas = [], res = {}; let n = 0;
const ok = (c, m) => { console.log((c ? "ok — " : "FALHA — ") + m); if (c) n++; else falhas.push(m); };
(async () => {
  const b = await chromium.launch(), ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true }), p = await ctx.newPage(), erros = [];
  p.on("pageerror", (e) => erros.push(e.message)); p.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) erros.push("console: " + m.text()); });
  const foto = async (nome) => { if (caps) await p.screenshot({ path: path.join(caps, nome + ".png") }); };
  const url = `${base}/?view=operacao&tab=rodada&mg=${s.mg}&sc=${s.sc}&run=${s.run}`, pt = p.locator(".pt.partitura").first();
  const abrir = async () => { await p.goto(url); await p.locator(".pt.partitura svg.trama").first().waitFor({ timeout: 180000 }); await p.waitForTimeout(1500); };
  await abrir();
  ok(await pt.getAttribute("data-lente-ativa") === "operacao", "abertura da rodada na lente Operação");
  ok(await p.locator('.pt.partitura .stage svg.trama path[data-k="tar"]').count() === 1, "Operação: tarifa como curva escalonada (uma curva)");
  ok(await p.locator('.pt.partitura .stage svg.trama [data-k="tarmuda"]').count() === 2, "Operação: dois inícios de período tarifário marcados (18:00 e 21:00)");
  await p.locator('.pt.partitura .stage').scrollIntoViewIfNeeded(); await foto("01_operacao_tarifa");
  await p.locator('.pt.partitura [data-lente="visao"]').click(); await p.waitForTimeout(1500);
  ok(await p.locator(".pt.partitura .kpi").count() >= 6, "Visão Geral: KPIs desenhados");
  ok(await p.locator(".pt.partitura .vg svg.trama").count() === 4, "Visão Geral: energia por fonte, participação, balanço e participação temporal");
  const vg = (await pt.textContent()).replace(/\s+/g, " ");
  ok(vg.includes("Σ injeções") && vg.includes("Denominador") && !vg.includes("N/D"), "Visão Geral: denominador explícito e nenhum N/D no exemplo C4");
  await foto("02_visao_geral"); await p.locator(".pt.partitura .rolar").evaluate((e) => { e.scrollTop = e.scrollHeight; }); await p.waitForTimeout(400); await foto("02b_visao_geral_temporal");
  await abrir(); ok(await pt.getAttribute("data-lente-ativa") === "operacao", "reaberta depois da Visão Geral: volta à Operação");
  await p.locator(".pt.partitura .status .pill").click(); await p.locator(".pt.partitura .dlg").waitFor(); await p.waitForTimeout(800);
  for (const [aba, foto_] of [["Solar", "03_painel_solar"], ["Bateria", "04_painel_bateria"], ["Rede", "05_painel_rede"], ["Carga líquida", "06_painel_carga_liquida"]]) {
    await p.locator(`.pt.partitura .dtools [role="tab"]`, { hasText: new RegExp(`^${aba}$`) }).click(); await p.waitForTimeout(900);
    const dem = await p.locator('.pt.partitura .dlg svg.trama [data-k="demref"]').count();
    if (aba !== "Carga líquida") ok(dem === 1, `painel ${aba}: demanda total de referência no gráfico de potência`);
    else ok((await p.locator(".pt.partitura .dlg .dbody").textContent()).includes("Fechamento do balanço"), "painel Carga líquida: demanda × carga líquida, compensação e fechamento");
    await foto(foto_);
  }
  await p.keyboard.press("Escape"); await p.waitForTimeout(400);
  await p.locator('.pt.partitura .stage .seg button', { hasText: "6 h" }).click(); await p.waitForTimeout(600);
  ok(/janela ampliada/.test(await p.locator(".pt.partitura .stage svg.trama").first().getAttribute("data-janela")), "tela AMPLIADA (6 h) antes de gerar o relatório");
  const t0 = Date.now(); await p.locator('.pt.partitura [data-acao="relatorio"]').click();
  await p.locator('.pt.partitura .relbox[data-estado="pronto"], .pt.partitura .relbox[data-estado="erro"]').waitFor({ timeout: 300000 });
  res.ms_partitura = Date.now() - t0;
  ok(await p.locator(".pt.partitura .relbox").getAttribute("data-estado") === "pronto", `relatório pelo botão da Partitura pronto em ${res.ms_partitura} ms`);
  await foto("07_relatorio_pronto");
  const area = p.locator('[class*="exportacoes_v2"]'); await area.scrollIntoViewIfNeeded();
  const bt = area.getByRole("button", { name: "BAIXAR RELATÓRIO PDF" }); await bt.waitFor({ timeout: 60000 }); await foto("08_exportacoes");
  const [dl] = await Promise.all([p.waitForEvent("download"), bt.click()]); const dest = path.join(out, "baixados", "partitura_" + dl.suggestedFilename()); await dl.saveAs(dest);
  res.pdf_partitura = dest; ok(/^seeds2_relatorio_C4_/.test(dl.suggestedFilename()), `PDF baixado (${dl.suggestedFilename()})`);
  ok(await area.getByRole("button", { name: "BAIXAR TODAS AS FIGURAS (ZIP)" }).count() === 1 && await area.getByRole("button", { name: "EXPORTAR TABELAS EXCEL (.xlsx)" }).count() === 1, "figuras ZIP e Excel continuam no painel");
  await abrir(); const a2 = p.locator('[class*="exportacoes_v2"]'); await a2.scrollIntoViewIfNeeded();
  const t1 = Date.now(); await a2.getByRole("button", { name: "GERAR RELATÓRIO PDF" }).click();
  const b2 = a2.getByRole("button", { name: "BAIXAR RELATÓRIO PDF" }); await b2.waitFor({ timeout: 300000 }); res.ms_painel = Date.now() - t1;
  const [dl2] = await Promise.all([p.waitForEvent("download"), b2.click()]); const dest2 = path.join(out, "baixados", "painel_" + dl2.suggestedFilename()); await dl2.saveAs(dest2);
  res.pdf_painel = dest2; ok(true, `relatório pelo botão do painel pronto em ${res.ms_painel} ms`);
  ok(erros.length === 0, "sem erros de página nem de console" + (erros.length ? ": " + erros.slice(0, 3).join(" | ") : ""));
  fs.writeFileSync(path.join(out, "e2e_ui_resultados02.json"), JSON.stringify({ verificacoes: n, falhas, ...res }, null, 1));
  await b.close();
  if (falhas.length) { console.error("FALHAS:\n" + falhas.join("\n")); process.exit(1); }
  console.log(`CONCLUÍDO — ${n} verificações aprovadas`);
})().catch((e) => { console.error(e); process.exit(1); });
