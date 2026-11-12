// E2E em navegador real (Playwright/Chromium) do PISO 3D-B (B0/B1/B3) — Partitura (motor gráfico Trama) na aplicação Streamlit REAL.
// Preparação: python tools/e2e/seed_piso3db.py <DIR>; roteiro completo: tools/e2e/run_piso3db.sh
// Uso: node tools/e2e/e2e_piso3db_partitura.js <url> <seed_piso3db.json> <pasta_capturas>
// O servidor do roteiro roda SEM solver e com motor e modelos sabotados (tools/e2e/sabotage_v2): tudo o que se vê é lido dos
// dados gravados da rodada. Verifica: montagem, dados × registros, cursor e inspetor, foco por recurso, fixação do instante,
// os sete painéis (PEMFC com as três vistas), troca de instante no painel, retorno com contexto, rerun e recarga, temas,
// resoluções, rodada V1.6 e estudo do Arquivo Científico. 3D-B3: vista clássica recolhida e acessível; lentes Decisão (janela
// com e sem sinal de valor futuro, o que se sabia × o que ocorreu depois), Economia e Evidência sem perder o instante; troca
// de rodada na mesma sessão; sessão nova.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const [base, seedFile, out] = process.argv.slice(2);
const seed = JSON.parse(fs.readFileSync(seedFile, "utf8"));
fs.mkdirSync(out, { recursive: true });
const url = `${base}/?view=operacao&tab=rodada&mg=${seed.mg}&sc=${seed.sc}&run=${seed.run}`;
const brl = (v) => v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
let n = 0; const falhas = [];
const log = (...a) => console.log("[3db]", ...a);
function ok(c, msg) { if (c) { n += 1; log("ok —", msg); } else { falhas.push(msg); log("FALHA —", msg); } }
(async () => {
  const b = await chromium.launch();
  const abrir = async (w, h, tema, destino = url) => {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, locale: "pt-BR", colorScheme: tema });
    const p = await ctx.newPage();
    p.on("pageerror", (e) => falhas.push(`${w}×${h} erro de página: ` + String(e.stack || e).slice(0, 400)));
    p.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) falhas.push("console: " + m.text().slice(0, 300)); });
    await p.goto(destino); return [ctx, p];
  };
  const pronta = async (p) => { await p.locator(".pt svg.trama").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(1500); };
  const foto = (p, nome) => p.screenshot({ path: path.join(out, nome + ".png") });

  // ------------------------------------------------------------------ rodada V2 real, 1768 × 853, claro
  let [ctx, p] = await abrir(1768, 853, "light"); await pronta(p);
  const grafico = p.locator(".pt .stage svg.trama").first(), grande = () => p.locator(".pt .col .card .big").first().innerText().then((t) => t.trim());
  ok(await p.locator(".pt").count() === 1, "Partitura montada na página real da rodada V2");
  ok((await p.locator(".pt .bar h1").innerText()).includes(seed.cenario), "título = nome do cenário gravado");
  ok((await p.locator(".pt .bar .ctx").innerText()).includes("R$ " + brl(seed.custo_R)), `custo realizado do resumo selado: R$ ${brl(seed.custo_R)}`);
  const estado = await p.locator(".pt .status").innerText();
  ok(estado.includes("evidência verificada") && estado.includes("sem solver"), "barra de estado: evidência verificada sem solver");
  ok(estado.includes("algébrico aprovado") && estado.includes("físico não validado"), "aceitações separadas: algébrico aprovado · físico não validado");
  await foto(p, "01_operacao");
  const sobre = async (frac, y = 200) => { const bx = await grafico.boundingBox(); await p.mouse.move(bx.x + 46 + (bx.width - 56) * frac, bx.y + y); await p.waitForTimeout(220); };
  await sobre(18.5 / 24); ok(await grande() === "18h–19h", "cursor sobre o intervalo 18: inspetor mostra 18h–19h");
  ok((await p.locator(".pt .col").innerText()).includes(seed.demanda_18h_kW.toLocaleString("pt-BR", { minimumFractionDigits: 1 })), `inspetor: demanda realizada ${seed.demanda_18h_kW} kW às 18h (valor gravado)`);
  await p.locator(".pt button.leg", { hasText: "PEMFC" }).hover(); await p.waitForTimeout(250);
  ok(await p.locator('.pt .stage svg.trama [data-k="wt"].dim').count() > 0 && await p.locator('.pt .stage svg.trama [data-k="fc"].dim').count() === 0, "foco por recurso: as outras séries recuam");
  await foto(p, "02_foco_pemfc");
  await sobre(18.5 / 24); await p.mouse.down(); await p.mouse.up(); await p.waitForTimeout(250);
  ok((await p.locator(".pt .status").innerText()).includes("fixado"), "clique fixa o instante");
  await p.locator(".pt .rowb", { hasText: "PEMFC" }).click(); await p.locator(".pt .dlg").waitFor(); await p.waitForTimeout(500);
  const dl = await p.locator(".pt .dlg").boundingBox();
  ok(dl.width > 1500 && dl.height > 780 && dl.x < 30 && dl.y < 30, `painel do recurso cobre a janela (${Math.round(dl.width)}×${Math.round(dl.height)})`);
  ok((await p.locator(".pt .dlg .dhead").innerText()).includes("18h–19h"), "painel aberto no instante fixado");
  ok((await p.locator(".pt .dlg .dhead").innerText()).includes("FC-01"), "painel identifica o equipamento por nome, TAG e UID");
  await foto(p, "03_pemfc_operacao");
  await p.locator(".pt .dtools button", { hasText: "Curva q(P)" }).click(); await p.waitForTimeout(600);
  const b04 = await p.locator(".pt .dlg .col").innerText();
  ok(b04.includes("MATEMÁTICA") && b04.includes("não é validação experimental"), "B04 apresentada como certificação matemática, não validação experimental");
  ok(await p.locator(".pt .dlg svg.trama").count() === 2, "curva q(P) e erro da PWL desenhados"); await foto(p, "04_pemfc_curva_b04");
  await p.locator(".pt .dtools button", { hasText: "Verificação dinâmica" }).click(); await p.waitForTimeout(500);
  ok((await p.locator(".pt .dlg .col").innerText()).includes("não é validação física"), "verificação dinâmica: coerência não é validação física"); await foto(p, "05_pemfc_dinamica");
  for (const t of ["Bateria", "Solar", "Eólica", "Rede", "Carga", "Custos"]) {
    await p.locator(".pt .dtools [role=tab]", { hasText: t }).click(); await p.waitForTimeout(450);
    ok(await p.locator(".pt .dlg svg.trama").count() >= 1 && (await p.locator(".pt .dlg .col .card").count()) >= 3, `painel ${t}: gráfico e cartões`); await foto(p, "06_painel_" + t.toLowerCase());
  }
  await p.locator(".pt .dtools [role=tab]", { hasText: "Bateria" }).click(); await p.waitForTimeout(400);
  { const bx = await p.locator(".pt .dlg svg.trama").boundingBox(); await p.mouse.move(bx.x + 70 + (bx.width - 80) * (20.5 / 24), bx.y + 100); await p.mouse.down(); await p.mouse.up(); await p.waitForTimeout(300); }
  ok((await p.locator(".pt .dlg .dhead").innerText()).includes("20h–21h"), "instante trocado dentro do painel (20h–21h)");
  await p.keyboard.press("Escape"); await p.waitForTimeout(300);
  ok(await p.locator(".pt .dlg").count() === 0, "Esc fecha o painel"); ok(await grande() === "20h–21h", "contexto conservado ao fechar: 20h–21h");
  await p.evaluate(() => window.scrollTo(0, 0)); await p.locator("body").press("r"); await p.waitForTimeout(3500);
  ok(await grande() === "20h–21h", "rerun do Streamlit conserva o instante");
  await p.reload(); await pronta(p); ok(await grande() === "20h–21h", "recarga da página conserva o instante");

  // ------------------------------------------------------------------ 3D-B3 · vista clássica recolhida, inteira e acessível
  const classica = p.locator('[data-testid="stExpander"] summary', { hasText: "Vista clássica" }).first();
  ok(await classica.count() === 1 && !(await classica.evaluate((s) => s.parentElement.open)), "vista clássica recolhida por padrão num expansor identificado");
  ok(!(await p.getByText("Custo REALIZADO").first().isVisible()), "conteúdo clássico não ocupa a página enquanto recolhido");
  ok(await p.getByText("Motor V2 experimental").first().isVisible(), "aviso de motor experimental continua visível fora do expansor");

  // ------------------------------------------------------------------ 3D-B3 · lentes (o instante fixado 20h–21h acompanha)
  const inst = async () => (await p.locator(".pt .pt-inst").textContent()).trim(), lado = () => p.locator(".pt .stage .col").textContent();
  const lente = async (id) => { await p.locator(`.pt button[data-lente="${id}"]`).click(); await p.waitForTimeout(800); };
  const ativa = () => p.locator(".pt").getAttribute("data-lente-ativa");
  ok(await p.locator(".pt button[data-lente]").count() === 4, "quatro lentes: Operação, Decisão, Economia, Evidência");
  const i0 = await inst(); ok(i0.includes("20h–21h") && i0.includes("fixado"), "instante de partida: 20h–21h fixado");
  await lente("decisao");
  ok(await inst() === i0 && await ativa() === "decisao", "lente Decisão: o instante fixado é conservado");
  ok((await p.locator(".pt .stage").textContent()).includes("Tapete de decisões"), "Decisão: tapete de decisões do MPC desenhado");
  const janela = async (j) => { await p.locator('.pt select[aria-label="Janela de decisão"]').selectOption(String(j)); await p.waitForTimeout(800); };
  ok(await p.locator('.pt select[aria-label="Janela de decisão"] option').count() === seed.janelas, `Decisão: ${seed.janelas} janelas selecionáveis`);
  await janela(seed.j_com);
  let t = await lado();
  ok(t.includes(`Decisão · janela ${seed.j_com}com valor futuro`) && !t.includes("foi tomada sem valor futuro"), `janela ${seed.j_com}: decisão com sinal de valor futuro válido`);
  ok(await p.locator(".pt .stage .col svg.trama").count() === 1 && t.includes("Instrumento de decisão: não é custo realizado"), "V(E) desenhado a partir dos pontos gravados, rotulado como instrumento de decisão");
  await foto(p, "09_decisao_com_sinal");
  await janela(seed.j_sem);
  t = await lado();
  ok(t.includes(`Decisão · janela ${seed.j_sem}sem valor futuro`) && t.includes("foi tomada sem valor futuro") && t.includes("Custo futuro estimadoN/D"), `janela ${seed.j_sem}: ausência de valor futuro explícita (custo futuro N/D, com o motivo gravado)`);
  ok(t.includes("Sinal indisponível") && t.includes("não foi usado nesta decisão"), "sinal indisponível: pontos avaliados aparecem só como registro");
  await foto(p, "10_decisao_sem_sinal");
  await p.locator(".pt button.pill", { hasText: "Janela do instante" }).click(); await p.waitForTimeout(800);
  t = await lado();
  ok(t.includes("Instante 20h–21h nesta decisão") && t.includes("aplicado") && t.includes("planejado em 20h"), "«Janela do instante»: a decisão que aplicou 20h–21h, com planejado × executado");
  ok(t.includes("o controlador não o conhecia em 20h"), "o executado é rotulado como posterior à decisão");
  await p.locator(".pt button.pill", { hasText: "Mostrando o que ocorreu depois" }).click(); await p.waitForTimeout(800);
  t = await lado();
  ok(t.includes("oculto") && t.includes("só o que era conhecido em 20h") && await inst() === i0, "exploração causal: o que ocorreu depois da decisão pode ser ocultado");
  await foto(p, "11_decisao_so_o_conhecido");
  await p.locator(".pt button.pill", { hasText: "Só o que se sabia na decisão" }).click(); await p.waitForTimeout(500);
  await lente("economia");
  t = await lado();
  ok(await inst() === i0 && await ativa() === "economia", "lente Economia: o instante fixado é conservado");
  ok(t.includes("Três grandezas que não se somam") && t.includes("Custo operacional realizado (missão)R$ " + brl(seed.custo_R)), "Economia: custo realizado separado do objetivo do MILP e do valor futuro");
  ok(t.includes("Σ realizado dos blocos aplicados (derivado)R$ " + brl(seed.custo_R)), "Economia: Σ dos blocos aplicados (derivado) = custo realizado da missão");
  ok(t.includes(`Decisões com valor futuro${seed.n_validas} de ${seed.janelas}`), `Economia: ${seed.n_validas} de ${seed.janelas} decisões com valor futuro`);
  await foto(p, "12_economia");
  await lente("evidencia");
  t = await p.locator(".pt .rolar").textContent();
  ok(await inst() === i0 && await ativa() === "evidencia", "lente Evidência: o instante fixado é conservado");
  ok(/Evidência verificada(\d+) de \1 verificações aprovadas pelo servidor/.test(t), "Evidência: verificação do SERVIDOR exibida (não refeita no navegador)");
  ok(t.includes("Algébricaaprovado") && t.includes("não validado") && t.includes("Nenhuma delas é validação física"), "Evidência: aceitações algébrica, dinâmica e física separadas");
  ok(t.includes("Auditoria independente da missãoAceita"), "Evidência: auditoria independente gravada");
  ok(await p.locator(".pt .rolar tr[data-j]").count() === seed.janelas, "Evidência: solver, gap e critérios por decisão");
  ok(await p.locator(".pt .rolar .panel", { hasText: "Arquivos da evidência" }).locator("tr").count() === seed.arquivos + 1, `Evidência: ${seed.arquivos} arquivos com SHA-256`);
  await p.locator(".pt .rolar .seg button", { hasText: "planos.csv" }).click(); await p.waitForTimeout(600);
  ok((await p.locator(".pt .rolar").textContent()).includes(`v2/planos.csv · ${seed.linhas_planos} linhas`), "Evidência: tabelas originais gravadas consultáveis (planos.csv)");
  await foto(p, "13_evidencia");
  await p.locator(".pt button.pill", { hasText: "Abrir a vista clássica" }).click(); await p.waitForTimeout(2500);
  ok(await classica.evaluate((s) => s.parentElement.open) && await p.getByText("Custo REALIZADO").first().isVisible(), "a Evidência abre a vista clássica (tabelas, descargas e exportações)");
  ok(await p.locator('[data-testid="stDownloadButton"]').count() >= seed.arquivos && await p.locator(".js-plotly-plot").count() >= 2, "vista clássica inteira: descargas e gráficos anteriores");
  ok(await p.locator('[data-testid="stExpander"] [data-testid="stExpander"] summary', { hasText: "Intervalos aplicados" }).count() === 1, "vista clássica inteira: tabelas originais");
  await foto(p, "14_vista_classica_aberta");
  await p.locator(".pt .rolar tr[data-j]").nth(seed.j_sem).click(); await p.waitForTimeout(800);
  ok(await ativa() === "decisao" && (await lado()).includes(`Decisão · janela ${seed.j_sem}sem valor futuro`), "da Evidência para a decisão: a linha do solver abre a janela na lente Decisão");

  // ------------------------------------------------------------------ 3D-B3 · troca de rodada na MESMA sessão do navegador
  await p.goto(`${base}/?view=operacao&tab=rodada&mg=${seed.mg}&sc=${seed.sc2}&run=${seed.run2}`); await pronta(p);
  ok((await p.locator(".pt .bar h1").innerText()).includes(seed.cenario2) && (await p.locator(".pt .bar .ctx").innerText()).includes("R$ " + brl(seed.custo2_R)), `outra rodada (${seed.cenario2}): título e custo próprios`);
  ok(await ativa() === "operacao" && !(await inst()).includes("fixado") && (await inst()).includes("00h–01h"), "outra rodada: estado próprio (lente Operação, instante inicial), nada herdado");
  await foto(p, "15_outra_rodada");
  await p.goto(url); await pronta(p);
  ok(await ativa() === "decisao" && await inst() === i0, "de volta à primeira rodada: lente e instante restaurados");
  await ctx.close();
  // sessão NOVA (outro navegador), servidor sem solver: mesmos dados, estado inicial
  [ctx, p] = await abrir(1768, 853, "light"); await pronta(p);
  ok((await p.locator(".pt .bar .ctx").innerText()).includes("R$ " + brl(seed.custo_R)) && (await p.locator(".pt .pt-inst").textContent()).includes("00h–01h") && await p.locator(".pt").getAttribute("data-lente-ativa") === "operacao", "sessão nova sem solver: mesmos dados gravados, estado inicial");
  await ctx.close();

  // ------------------------------------------------------------------ temas e resoluções
  for (const [w, h, tema] of [[1768, 853, "dark"], [1366, 768, "light"], [2560, 1440, "light"], [400, 850, "light"], [820, 1100, "dark"]]) {
    [ctx, p] = await abrir(w, h, tema); await pronta(p); await p.evaluate(() => sessionStorage.clear());
    const ov = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth); ok(ov <= 1, `${w}×${h}: sem transbordo horizontal (${ov}px)`);
    ok(await p.locator(".pt").getAttribute("data-theme") === tema, `${w}×${h}: tema ${tema} detectado a partir do tema do Streamlit`);
    if (w === 1366) { const bt = p.locator('.pt [aria-label="Alternar tema claro / escuro"]'); await bt.click(); await p.waitForTimeout(300); ok(await p.locator(".pt").getAttribute("data-theme") === "dark", "botão de tema alterna claro → escuro sem rerun"); await bt.click(); await p.evaluate(() => localStorage.clear()); }
    await p.locator(".pt").scrollIntoViewIfNeeded(); await foto(p, `r_${w}x${h}_${tema}`);
    for (const l of ["decisao", "economia", "evidencia"]) {
      await p.locator(`.pt button[data-lente="${l}"]`).click(); await p.waitForTimeout(700);
      const o2 = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth); ok(o2 <= 1, `${w}×${h}: lente ${l} sem transbordo horizontal (${o2}px)`);
      // dentro do componente: nenhum painel ou cartão sai da largura do instrumento (conteúdo cortado também é falha)
      const fora = await p.locator(".pt").evaluate((r) => { const lim = r.getBoundingClientRect().right + 1; return [...r.querySelectorAll(".panel, .card, .bar > *")].filter((e) => e.getBoundingClientRect().right > lim).length; });
      ok(fora === 0, `${w}×${h}: lente ${l} sem painéis cortados dentro do instrumento (${fora})`);
      if (l !== "economia") await foto(p, `r_${w}x${h}_${tema}_${l}`);
    }
    await p.locator('.pt button[data-lente="operacao"]').click(); await p.waitForTimeout(500);
    await p.locator(".pt .status .pill").click(); await p.locator(".pt .dlg").waitFor(); await p.waitForTimeout(500); await foto(p, `r_${w}x${h}_${tema}_painel`);
    await ctx.close();
  }

  // ------------------------------------------------------------------ compatibilidade: rodada V1.6 e estudo arquivado
  [ctx, p] = await abrir(1440, 900, "light", `${base}/?view=operacao&tab=rodada&mg=${seed.v16.mg}&sc=${seed.v16.sc}&run=${seed.v16.run}`);
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(2500);
  ok(await p.locator(".pt").count() === 0 && await p.locator(".js-plotly-plot").count() >= 1, "rodada V1.6: página anterior intacta (gráficos Plotly, sem Partitura)");
  await foto(p, "07_rodada_v16"); await ctx.close();
  [ctx, p] = await abrir(1440, 900, "light", `${base}/?view=arquivo&tab=estudo&study=${seed.estudo}&srun=${seed.run}`);
  await pronta(p);
  ok((await p.locator(".pt .bar .ctx").innerText()).includes("R$ " + brl(seed.custo_R)), "Arquivo Científico: a rodada do estudo arquivado abre na Partitura com o mesmo custo");
  await foto(p, "08_estudo_arquivado"); await ctx.close();

  await b.close();
  if (falhas.length) { log(`${falhas.length} FALHA(S):`); falhas.forEach((f) => log("  ", f)); process.exit(1); }
  log(`CONCLUÍDO — ${n} verificações aprovadas, sem erros de página nem de console`);
})().catch((e) => { console.error(e); process.exit(1); });
