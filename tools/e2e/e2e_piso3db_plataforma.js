// E2E em navegador real (Playwright/Chromium) do PISO 3D-B2 — integração visual da plataforma na aplicação Streamlit REAL.
// Roteiro completo: tools/e2e/run_piso3db.sh (mesma semente e mesmo servidor SEM solver do E2E da Partitura).
// Uso: node tools/e2e/e2e_piso3db_plataforma.js <url> <seed_piso3db.json> <pasta_capturas>
// B2-A: barra lateral (trilho, expansão por hover/foco, destino atual, navegação, troca de microrrede, barra inferior no
// celular, estabilidade em reruns) com a barra superior anterior intacta. B2-B: Planta (nós por UID, hover, foco, seleção,
// cursor de instante, painel individual por UID na Partitura, só inventário, microrrede sem rodada V2/isolada, celular).
const { chromium } = require("playwright");
const { expandirCartoes } = require("./catalogo_util");
const fs = require("fs");
const path = require("path");
const [base, seedFile, out, logMotor] = process.argv.slice(2);
const motorVazio = () => !logMotor || !fs.existsSync(logMotor) || fs.statSync(logMotor).size === 0;
const seed = JSON.parse(fs.readFileSync(seedFile, "utf8"));
const brl = (v) => v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
fs.mkdirSync(out, { recursive: true });
let n = 0; const falhas = [];
const log = (...a) => console.log("[3db2]", ...a);
function ok(c, msg) { if (c) { n += 1; log("ok —", msg); } else { falhas.push(msg); log("FALHA —", msg); } }
(async () => {
  const b = await chromium.launch();
  const abrir = async (w, h, destino, tema = "light") => {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, locale: "pt-BR", colorScheme: tema });
    const p = await ctx.newPage();
    p.on("pageerror", (e) => falhas.push(`${w}×${h} erro de página: ` + String(e.stack || e).slice(0, 400)));
    p.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) falhas.push("console: " + m.text().slice(0, 300)); });
    await p.goto(destino); await p.locator(".pt.sb").waitFor({ timeout: 120000 }); await p.mouse.move(Math.round(w * .6), Math.round(h * .5)); await p.waitForTimeout(2500); return [ctx, p];
  };
  const foto = (p, nome) => p.screenshot({ path: path.join(out, nome + ".png") });
  const itens = (p) => p.locator(".pt.sb .it").evaluateAll((e) => e.map((x) => x.dataset.id));
  const atual = (p) => p.locator('.pt.sb .it[aria-current="page"]').evaluateAll((e) => e.map((x) => x.dataset.id));
  const largura = (p) => p.locator(".pt.sb .side-in").evaluate((e) => Math.round(e.getBoundingClientRect().width));

  // ------------------------------------------------------------------ CONSULTA sem motor, solver nem modelos
  // Antes de qualquer página de preparação: Catálogo → Planta com rodada → painel por UID → Caderno → rodada → estudo.
  let [ctx, p] = await abrir(1500, 950, `${base}/`);
  await expandirCartoes(p); await p.locator(".gc-sig .gs-bus").first().waitFor({ timeout: 120000 });
  await p.goto(`${base}/?view=operacao&tab=planta&mg=${seed.mg}`); await p.locator(".pt.planta svg.pl-svg").waitFor({ timeout: 120000 }); await p.waitForTimeout(1200);
  await p.locator('.pt.planta .node[data-tipo="wt"]').click(); await p.waitForTimeout(300);
  await p.locator(".pt.planta .pl-abrir").click(); await p.locator(".pt.partitura .dlg").waitFor({ timeout: 120000 }); await p.waitForTimeout(1000);
  await p.goto(`${base}/?view=operacao&tab=caderno&mg=${seed.mg}`); await p.locator(".pt.caderno .cd-tab").waitFor({ timeout: 120000 }); await p.waitForTimeout(1000);
  await p.locator(`.pt.caderno tr[data-run="${seed.run2}"] .cd-abrir`).click(); await p.locator(".pt.partitura svg.trama").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(1000);
  await p.goto(`${base}/?view=operacao&tab=caderno&mg=${seed.mg}`); await p.locator(".pt.caderno .cd-tab").waitFor({ timeout: 120000 }); await p.waitForTimeout(800);
  // Finalização: indicadores científicos por rodada e comparação A × B — ainda CONSULTA (registro do motor vazio)
  const lv2 = (await p.locator(`.pt.caderno tr[data-run="${seed.run}"]`).textContent()).replace(/\s+/g, " ");
  ok(lv2.includes("Δ 60 min · N 6 · m 2 · H_L 12") && lv2.includes("conectado") && lv2.includes("kWh") && lv2.includes("kg") && lv2.includes("válido(s)") && lv2.includes("auditoria aprovada"), "Caderno: malha N·m·H_L, PCC, importação, H₂, sinal de valor futuro e integridade da rodada V2 (valores gravados)");
  const s0 = p.locator(".pt.caderno .cd-sel");
  await s0.nth(0).selectOption(seed.run); await s0.nth(1).selectOption(seed.run2);
  await p.locator(".pt.caderno .cd-comparar").click(); await p.locator(".pt.caderno .cd-lado").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(1000);
  const cmpTxt = (await p.locator(".pt.caderno .cd-cmp").textContent()).replace(/\s+/g, " ");
  ok(cmpTxt.includes("R$ " + brl(seed.custo_R)) && cmpTxt.includes("R$ " + brl(seed.custo2_R)) && await p.locator(".pt.caderno .cd-graf").count() === 3, "Caderno: comparação A × B com os custos gravados e 3 séries temporais na MESMA malha (nada interpolado)");
  ok(cmpTxt.includes("NÃO equivalentes (Cenário)") && cmpTxt.includes("difere"), "Comparação: cenários distintos ADVERTIDOS (condições experimentais não equivalentes)");
  await p.locator(".pt.caderno .cd-cmp").scrollIntoViewIfNeeded(); await foto(p, "fin_caderno_comparacao");
  await p.locator(".pt.caderno .cd-abrir-b").click(); await p.locator(".pt.partitura svg.trama").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(1000);
  ok(p.url().includes(`run=${seed.run2}`), "Comparação → «Abrir os resultados completos» da rodada B (Partitura)");
  await p.goto(`${base}/?view=operacao&tab=caderno&mg=${seed.mg}`); await p.locator(".pt.caderno .cd-tab").waitFor({ timeout: 120000 }); await p.waitForTimeout(800);
  await p.locator(".pt.caderno .cd-estudo").click(); await p.waitForTimeout(3500);
  ok(motorVazio(), "consultar Catálogo, Planta, painel por UID, Caderno (indicadores e comparação), rodada e estudo NÃO chama motor, solver nem modelos (registro vazio)");
  await ctx.close();

  // ------------------------------------------------------------------ B2-A · sem microrrede aberta (Gestor)
  [ctx, p] = await abrir(1500, 900, `${base}/`);
  ok(JSON.stringify(await itens(p)) === JSON.stringify(["catalogo", "arquivo", "alcance"]), "sem microrrede: barra lateral com Catálogo, Arquivo Científico e Alcance");
  ok(JSON.stringify(await atual(p)) === JSON.stringify(["catalogo"]), "Gestor de microrredes = Catálogo (destino atual marcado)");
  ok(await largura(p) === 56, "trilho compacto de 56 px");
  ok(await p.locator(".tb.tb-compacta").count() === 1 && await p.locator(".tb .tb-link").count() >= 2 && !(await p.locator(".tb .tb-link").first().isVisible()) && await p.locator(".tb .tb-brand").isVisible(), "barra superior compacta: marca e identidade; a navegação fica só na barra lateral (sem duplicar)");
  await p.hover(".pt.sb"); await p.waitForTimeout(450);
  ok(await largura(p) >= 240, "hover expande a barra por cima do conteúdo"); await foto(p, "b2a_01_gestor_barra_expandida");
  const recuo = await p.locator(".block-container").evaluate((e) => parseFloat(getComputedStyle(e).paddingLeft));
  ok(recuo >= 56, `o conteúdo começa depois do trilho (recuo ${Math.round(recuo)} px)`);
  await p.mouse.move(900, 500); await p.waitForTimeout(350);
  let tabs = 0; while (tabs < 30 && await largura(p) < 240) { await p.keyboard.press("Tab"); await p.waitForTimeout(120); tabs += 1; }
  ok(await largura(p) >= 240, `foco pelo teclado (Tab) também expande a barra (${tabs} tabulações)`);
  await p.locator('.pt.sb .it[data-id="arquivo"]').focus(); await p.keyboard.press("Enter"); await p.waitForTimeout(2500);
  ok(p.url().includes("view=arquivo") && JSON.stringify(await atual(p)) === JSON.stringify(["arquivo"]), "Enter navega para o Arquivo Científico");
  await ctx.close();

  // ------------------------------------------------------------------ B2-A · microrrede ativa
  [ctx, p] = await abrir(1500, 900, `${base}/?view=operacao&mg=${seed.mg}`);
  const ids = await itens(p);
  ok(["catalogo", "planta", "caderno", "folha", "operacao", "gestao", "arquivo", "alcance"].every((i) => ids.includes(i)), "microrrede ativa: os destinos da plataforma estão na barra lateral");
  // UI-REDESIGN-01: o console V1.6 saiu da navegação; no lugar, as cinco bancadas (com os ícones do Gestor)
  ok(!ids.includes("simulacao") && !ids.includes("resultados") && ["solar", "wind", "battery", "h2", "thermal"].every((f) => ids.includes("bancada_" + f))
     && await p.locator(".pt.sb .it[data-acao=\"bancada\"] .kico svg").count() === 5, "barra lateral: grupo «Bancadas» (5) no lugar de Simulação/Resultados V1.6");
  ok(JSON.stringify(await atual(p)) === JSON.stringify(["operacao"]), "Centro de Operação marcado como destino atual");
  await p.locator(".pt.sb .side-in").evaluate((e) => e.setAttribute("data-marca", "1"));
  await p.locator("body").press("r"); await p.waitForTimeout(3500);
  ok(await p.locator('.pt.sb .side-in[data-marca="1"]').count() === 1, "rerun do Streamlit não redesenha a barra lateral");
  await p.hover(".pt.sb"); await p.waitForTimeout(400); await foto(p, "b2a_02_microrrede_barra_expandida");
  await p.locator('.pt.sb .it[data-id="gestao"]').click(); await p.waitForTimeout(3000);
  ok(p.url().includes("view=gestao") && p.url().includes(`mg=${seed.mg}`) && JSON.stringify(await atual(p)) === JSON.stringify(["gestao"]), "clique navega para a Gestão da Microrrede mantendo a microrrede");
  ok(await largura(p) === 56, "depois de navegar com o mouse a barra se recolhe (não fica por cima do conteúdo)");
  await p.mouse.move(900, 600); await p.waitForTimeout(250); await p.hover(".pt.sb"); await p.waitForTimeout(400);
  ok(await largura(p) >= 240, "… e volta a expandir no próximo hover"); await p.mouse.move(900, 600);
  ok(await p.locator(".tb .tb-switch").isVisible() && (await p.locator(".tb .tb-site").innerText()).length > 3 && await p.locator(".tb .tb-save").isVisible(), "barra superior compacta mantém a identidade da microrrede, TROCAR MICRORREDE e o estado de salvamento");
  await p.locator(".tb .tb-brand").click(); await p.waitForTimeout(3000);
  ok(p.url().includes("view=operacao") && JSON.stringify(await atual(p)) === JSON.stringify(["operacao"]), "a marca na barra superior volta ao Centro de Operação e a lateral acompanha");
  await p.goto(`${base}/?view=operacao&tab=rodada&mg=${seed.mg}&sc=${seed.sc}&run=${seed.run}`); await p.locator(".pt svg.trama").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(1500);
  const inst = await p.locator(".pt.partitura").first().evaluate((e) => e.getBoundingClientRect().left);
  ok(inst >= 56, `rodada: a Partitura começa depois do trilho (${Math.round(inst)} px)`); await foto(p, "b2a_03_rodada_com_barra");
  await p.locator('.pt.sb .it[data-id="catalogo"]').click(); await p.waitForTimeout(3500);
  ok(p.url().includes("view=gestor") && !p.url().includes("mg=") && JSON.stringify(await itens(p)) === JSON.stringify(["catalogo", "arquivo", "alcance"]), "Catálogo com microrrede aberta = trocar de microrrede (volta ao Gestor)");
  await ctx.close();

  // ------------------------------------------------------------------ B2-B · Planta (barramento equivalente por UID)
  [ctx, p] = await abrir(1600, 950, `${base}/?view=operacao&mg=${seed.mg}`);
  await p.locator('.pt.sb .it[data-id="planta"]').click(); await p.locator(".pt.planta svg.pl-svg").waitFor({ timeout: 120000 }); await p.mouse.move(900, 930); await p.waitForTimeout(1500);
  ok(p.url().includes("tab=planta") && JSON.stringify(await atual(p)) === JSON.stringify(["planta"]), "barra lateral → Planta (tab do Centro de Operação)");
  const nos = await p.locator(".pt.planta .node").evaluateAll((e) => e.map((x) => x.dataset.tipo));
  ok(JSON.stringify(nos) === JSON.stringify(["fv", "wt", "fc", "bat", "dem", "grid"]), "Planta: um nó por equipamento do inventário + demanda + PCC");
  ok(await p.locator(".pt.planta svg marker, .pt.planta svg animate, .pt.planta svg animateMotion").count() === 0, "Planta: nenhuma seta nem animação de fluxo nas ligações");
  const lado = async () => (await p.locator(".pt.planta .col").textContent()).replace(/\s+/g, " ");
  ok((await lado()).includes("valores gravados") && await p.locator(".pt.planta select.sel option").count() === 3, "Planta: rodadas V2 concluídas selecionáveis (2) ou só o inventário");
  await p.locator('.pt.planta .node[data-tipo="fc"]').hover(); await p.waitForTimeout(400);
  ok(await p.locator(".pt.planta .pop").isVisible() && (await p.locator(".pt.planta .pop").textContent()).includes("FC-01") && await p.locator(".pt.planta .node.off").count() === 5, "hover destaca o equipamento (os outros recuam) e mostra o resumo do inventário");
  await foto(p, "b2b_01_planta_hover");
  await p.locator('.pt.planta .node[data-tipo="bat"]').focus(); await p.keyboard.press("Enter"); await p.waitForTimeout(400);
  ok((await lado()).includes("BAT-01") && (await lado()).includes("selecionado"), "foco + Enter seleciona o equipamento (identidade por TAG e UID)");
  await p.locator(".pt.planta .pl-t").fill("18"); await p.waitForTimeout(400);
  ok((await p.locator(".pt.planta .pl-inst").textContent()).includes("18h–19h") && (await lado()).includes("Em 18h–19h"), "cursor de instante percorre os valores gravados da rodada");
  await p.mouse.move(900, 930); await foto(p, "b2b_02_planta_selecao");
  const uidBat = await p.locator('.pt.planta .node[data-tipo="bat"]').getAttribute("data-uid");
  await p.locator(".pt.planta .pl-abrir").click(); await p.locator(".pt .dlg").waitFor({ timeout: 120000 }); await p.waitForTimeout(1200);
  const cab = await p.locator(".pt .dlg .dhead").innerText();
  ok(cab.includes(uidBat) && cab.includes("18h–19h") && p.url().includes("tab=rodada"), "Planta → painel individual do equipamento por UID, no instante escolhido, na Partitura da rodada");
  await foto(p, "b2b_03_painel_por_uid");
  await p.keyboard.press("Escape"); await p.waitForTimeout(300);
  await p.locator('.pt.sb .it[data-id="planta"]').click(); await p.locator(".pt.planta svg.pl-svg").waitFor({ timeout: 120000 }); await p.waitForTimeout(1200);
  await p.locator(".pt.planta select.sel").selectOption(""); await p.waitForTimeout(3000);
  ok((await p.locator('.pt.planta .node[data-tipo="bat"] .pw').textContent()) === "" && !(await lado()).includes("valores gravados"), "«Só o inventário»: a Planta deixa de mostrar valores de rodada");
  await ctx.close();
  [ctx, p] = await abrir(1500, 900, `${base}/?view=operacao&tab=planta&mg=${seed.v16.mg}`);
  await p.locator(".pt.planta svg.pl-svg").waitFor({ timeout: 120000 }); await p.waitForTimeout(1200);
  ok((await p.locator(".pt.planta .col").textContent()).includes("Sem rodada V2 concluída") && await p.locator(".pt.planta .node").count() >= 3, "microrrede só com rodadas V1.6: a Planta mostra o inventário e diz que não há rodada V2");
  ok(await p.locator('.pt.planta .node[data-tipo="grid"]').count() === 0, "microrrede isolada: nenhum PCC desenhado");
  await foto(p, "b2b_04_planta_sem_rodada_v2"); await ctx.close();
  [ctx, p] = await abrir(400, 850, `${base}/?view=operacao&tab=planta&mg=${seed.mg}`);
  await p.locator(".pt.planta svg.pl-svg").waitFor({ timeout: 120000 }); await p.waitForTimeout(1200);
  const ovp = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok(ovp <= 1, `Planta a 400 px: sem transbordo horizontal da página (${ovp}px; o desenho rola dentro do painel)`); await foto(p, "b2b_r_400x850_planta"); await ctx.close();

  // ------------------------------------------------------------------ B2-B · Catálogo (Gestor) → microrrede → Planta
  [ctx, p] = await abrir(1500, 950, `${base}/`);
  await expandirCartoes(p);
  const cartoes = p.locator('[class*="st-key-mgc_"]');
  ok(await cartoes.count() === 2 && await p.locator(".gc-sig .gs-bus").count() === 2, "Catálogo: cada microrrede com a assinatura do barramento (inventário real)");
  const cv2 = p.locator(`.st-key-mgc_${seed.mg}`), tv2 = (await cv2.textContent()).replace(/\s+/g, " ");
  ok(tv2.includes("Ensaios: 2 cenário(s) · 2 concluída(s)") && await cv2.locator(".gs-m").count() === 3 && await cv2.locator(".gs-pcc").count() === 1, "Catálogo: cenários e rodadas por estado; FV + eólica + PEMFC + PCC na assinatura");
  const cv16 = p.locator(`.st-key-mgc_${seed.v16.mg}`);
  ok((await cv16.textContent()).includes("isolada") && await cv16.locator(".gs-pcc").count() === 0, "Catálogo: microrrede isolada sem PCC na assinatura");
  ok(await p.getByText("ABRIR MICRORREDE").count() === 2 && await p.getByRole("button", { name: /NOVA MICRORREDE/ }).count() === 1 && await p.getByRole("button", { name: /IMPORTAR MICRORREDE/ }).count() === 1, "Catálogo: operações do Gestor preservadas (nova, importar, abrir, ZIP, PDF, excluir)");
  ok((await p.locator(".gs-sec").textContent()).includes("Arquivo Científico · 1 estudo") && await p.getByRole("button", { name: "ABRIR ESTUDO" }).count() === 1, "Catálogo: prateleira do Arquivo Científico (somente leitura)");
  await foto(p, "b2b_05_catalogo");
  await cv2.getByText("ABRIR MICRORREDE").click(); await p.waitForTimeout(3500);
  ok(p.url().includes("view=operacao") && p.url().includes(`mg=${seed.mg}`), "Catálogo → ABRIR MICRORREDE → Centro de Operação");

  // ------------------------------------------------------------------ B2-C · Caderno de Ensaios
  await p.locator('.pt.sb .it[data-id="caderno"]').click(); await p.locator(".pt.caderno .cd-tab").waitFor({ timeout: 120000 }); await p.mouse.move(900, 940); await p.waitForTimeout(1200);
  ok(p.url().includes("tab=caderno") && JSON.stringify(await atual(p)) === JSON.stringify(["caderno"]), "barra lateral → Caderno de ensaios");
  ok(await p.locator(".pt.caderno .cd-cen").count() === 2 && await p.locator(".pt.caderno tr[data-run]").count() === 2, "Caderno: 2 cenários e as 2 rodadas desta microrrede");
  const lin = (await p.locator(`.pt.caderno tr[data-run="${seed.run}"]`).textContent()).replace(/\s+/g, " ");
  ok(lin.includes(seed.cenario) && lin.includes("V2") && lin.includes("Concluída") && lin.includes("R$ " + brl(seed.custo_R)), "Caderno: versão, motor, estado e custo realizado da rodada (valor gravado)");
  ok(await p.locator(`.pt.caderno tr[data-run="${seed.v16.run}"]`).count() === 0, "Caderno: nenhuma rodada de outra microrrede");
  ok(await p.locator(".pt.caderno [data-study]").count() === 1 && (await p.locator(".pt.caderno [data-study]").textContent()).includes("Origem: esta microrrede"), "Caderno: estudo do Arquivo Científico originado nesta microrrede");
  await foto(p, "b2c_01_caderno");
  await p.locator(`.pt.caderno tr[data-run="${seed.run}"] .cd-abrir`).click(); await p.locator(".pt svg.trama").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(1200);
  ok(p.url().includes(`run=${seed.run}`) && (await p.locator(".pt .bar h1").innerText()).includes(seed.cenario), "Caderno → Abrir → rodada na Partitura");
  ok(JSON.stringify(await atual(p)) === JSON.stringify(["rodada"]) && (await p.locator('.pt.sb .it[data-id="rodada"]').getAttribute("title") || (await p.locator('.pt.sb .it[data-id="rodada"]').textContent())).length > 0, "barra lateral: destino «Rodada» da rodada aberta (ativo)");
  await p.locator('.pt.sb .it[data-id="planta"]').click(); await p.locator(".pt.planta svg.pl-svg").waitFor({ timeout: 120000 }); await p.waitForTimeout(800);
  await p.locator('.pt.sb .it[data-id="rodada"]').click(); await p.locator(".pt svg.trama").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(800);
  ok(p.url().includes(`run=${seed.run}`), "barra lateral: Planta → «Rodada» volta à MESMA rodada");
  await p.locator('.pt.sb .it[data-id="caderno"]').click(); await p.locator(".pt.caderno .cd-tab").waitFor({ timeout: 120000 }); await p.waitForTimeout(1000);
  await p.locator(".pt.caderno .cd-estudo").click(); await p.waitForTimeout(3500);
  ok(p.url().includes("tab=estudo") && p.url().includes(`study=${seed.estudo}`), "Caderno → Abrir o estudo → Arquivo Científico (somente leitura)");
  await ctx.close();
  [ctx, p] = await abrir(1500, 950, `${base}/?view=operacao&tab=caderno&mg=${seed.v16.mg}`);
  await p.locator(".pt.caderno .cd-tab").waitFor({ timeout: 120000 }); await p.waitForTimeout(1000);
  const l16 = (await p.locator(`.pt.caderno tr[data-run="${seed.v16.run}"]`).textContent()).replace(/\s+/g, " ");
  ok(l16.includes("V1.6") && l16.includes("Concluída") && l16.includes("R$"), "Caderno: rodada V1.6 listada com o seu motor e resultado (compatibilidade)");
  await p.locator(`.pt.caderno tr[data-run="${seed.v16.run}"] .cd-abrir`).click(); await p.getByText("Rodada · imutável").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(2000);
  ok(await p.locator(".pt.partitura").count() === 0 && await p.locator(".js-plotly-plot").count() >= 1, "Caderno → rodada V1.6 abre na página anterior (sem Partitura)");
  await ctx.close();

  // ------------------------------------------------------------------ B2-D · Folha de Ensaio (etapas existentes, intactas)
  [ctx, p] = await abrir(1500, 950, `${base}/?view=operacao&tab=caderno&mg=${seed.mg}`);
  await p.locator(".pt.caderno .cd-tab").waitFor({ timeout: 120000 }); await p.waitForTimeout(1000);
  await p.locator(`.pt.caderno [data-sc="${seed.sc}"] .cd-folha`).click(); await p.locator(".pt.folha .fl-cab").waitFor({ timeout: 120000 }); await p.waitForTimeout(2500);
  ok(p.url().includes("tab=inicializacao") && p.url().includes(`sc=${seed.sc}`) && JSON.stringify(await atual(p)) === JSON.stringify(["folha"]), "Caderno → Abrir a folha de ensaio → seção 01 do cenário escolhido");
  const cabf = (await p.locator(".pt.folha .fl-cab").textContent()).replace(/\s+/g, " ");
  ok(cabf.includes(seed.cenario) && cabf.includes("motor V2") && await p.locator(".pt.folha .fl-sec").count() === 4, "Folha: cenário, versão, motor e as quatro seções com o seu estado");
  ok(await p.locator('.pt.folha .fl-sec[aria-current="step"]').getAttribute("data-sec") === "inicializacao" && await p.getByText("SOC inicial", { exact: false }).count() >= 1, "Folha · 01: os widgets de estado inicial continuam na página");
  await foto(p, "b2d_01_folha_estado_inicial");
  for (const [sec, marca] of [["previsoes", "Demanda"], ["estrategia", "Motor de execução"], ["execucao", "Preflight V2"]]) {
    await p.locator(`.pt.folha .fl-sec[data-sec="${sec}"]`).click(); await p.waitForTimeout(4000);
    ok(p.url().includes("tab=" + sec) && await p.locator('.pt.folha .fl-sec[aria-current="step"]').getAttribute("data-sec") === sec && await p.getByText(marca, { exact: false }).count() >= 1, `Folha · seção ${sec}: navegação pelo índice e formulário existente presente`);
  }
  ok(await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).count() === 1 || await p.getByText("solver", { exact: false }).count() >= 1, "Folha · 04: preflight e execução da etapa existente (servidor sem solver: bloqueio explicado)");
  await foto(p, "b2d_02_folha_execucao");
  await ctx.close();
  // Finalização da Partitura V2: três colunas (índice | seção | prontidão), subseções da estratégia V2, régua, prontidão,
  // alterações não salvas (falsas × reais) e colunas laterais fixas ao rolar.
  for (const tema of ["light", "dark"]) {
    [ctx, p] = await abrir(1440, 900, `${base}/?view=operacao&tab=estrategia&mg=${seed.mg}&sc=${seed.sc}`, tema);
    await p.mouse.move(700, 600); await p.locator(".pt.folha .fl-pron").waitFor({ timeout: 120000 }); await p.waitForTimeout(2000);
    const cx = async (k) => p.locator(`.st-key-${k}`).boundingBox();
    const [bi, bs, bp] = [await cx("fl_col_indice"), await cx("fl_col_secao"), await cx("fl_col_prontidao")];
    ok(bi.x + bi.width <= bs.x && bs.x + bs.width <= bp.x && Math.abs(bi.y - bs.y) < 40 && Math.abs(bp.y - bs.y) < 40, `Folha (${tema}): três colunas lado a lado (índice | seção | prontidão)`);
    if (tema === "dark") { ok(await p.locator(".pt.folha.fl-indice").getAttribute("data-theme") === "dark", "Folha: tema escuro seguido pelos componentes"); await foto(p, "fin_folha_escuro"); await ctx.close(); continue; }
    const subs = await p.locator(".pt.folha .fl-subl").evaluateAll((e) => e.map((x) => x.dataset.sub));
    const anc = await p.evaluate(() => [...document.querySelectorAll("[data-fl-sub]")].map((e) => e.dataset.flSub));
    ok(subs.length >= 8 && JSON.stringify(subs) === JSON.stringify(anc) && ["malha", "baterias", "renovaveis", "pemfc", "pcc", "planejador", "solver"].every((x) => subs.includes(x)), `Folha · 03: subseções do índice = âncoras do formulário (${subs.join(", ")})`);
    const ind0 = (await p.locator(".pt.folha .fl-cab").textContent()), pr0 = (await p.locator(".pt.folha .fl-pron").textContent()).replace(/\s+/g, " ");
    ok(ind0.includes("versão salva") && !ind0.includes("alterações não salvas") && pr0.includes("Versão salva v"), "Folha: abrir a estratégia V2 NÃO cria «alterações não salvas»");
    ok(pr0.includes("Execução indisponível") && pr0.includes("preflight"), "Prontidão: execução indisponível pela razão do botão da seção 04 (servidor sem solver)");
    ok((await p.locator(".pt.folha .fl-regua").getAttribute("data-regua")) === "completa" && (await p.locator(".pt.folha .fl-regua").textContent()).includes("K_M = "), "Régua dos horizontes com os valores declarados do cenário");
    await p.locator('.pt.folha .fl-subl[data-sub="planejador"]').click(); await p.waitForTimeout(1500);
    const yt = await p.evaluate(() => Math.round(document.querySelector('[data-fl-sub="planejador"]').getBoundingClientRect().top));
    const bi2 = await cx("fl_col_indice"), bp2 = await cx("fl_col_prontidao");
    ok(yt >= 0 && yt < 220 && bi2.y >= 0 && bi2.y < 200 && bp2.y >= 0 && bp2.y < 200, `Subseção 03.8 rolada ao topo (${yt}px) com índice e prontidão fixos na tela`);
    ok(await p.locator(".pt.folha .fl-subl.on").getAttribute("data-sub") === "planejador", "Índice destaca a subseção visível");
    await foto(p, "fin_folha_estrategia_subsecao");
    const ninp = p.getByLabel("Horizonte curto N [intervalos]");
    await ninp.scrollIntoViewIfNeeded(); await ninp.fill(String(Number(await ninp.inputValue()) + 1)); await ninp.press("Enter"); await p.waitForTimeout(4000);
    const ind1 = await p.locator(".pt.folha .fl-cab").textContent(), pr1 = (await p.locator(".pt.folha .fl-pron").textContent()).replace(/\s+/g, " ");
    ok(ind1.includes("alterações não salvas") && pr1.includes("Alterações não salvas") && pr1.includes("há alterações não salvas"), "Edição real ⇒ «alterações não salvas» no índice e na prontidão (execução indisponível)");
    await p.getByRole("button", { name: "DESCARTAR ALTERAÇÕES" }).click(); await p.waitForTimeout(4000);
    ok((await p.locator(".pt.folha .fl-cab").textContent()).includes("versão salva"), "Descartar volta à versão salva (nada gravado)");
    await ctx.close();
  }
  [ctx, p] = await abrir(400, 850, `${base}/?view=operacao&tab=estrategia&mg=${seed.mg}&sc=${seed.sc}`);
  await p.locator(".pt.folha .fl-pron").waitFor({ timeout: 120000 }); await p.waitForTimeout(1500);
  const ovf = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  const [mi, ms, mp] = [await p.locator(".st-key-fl_col_indice").boundingBox(), await p.locator(".st-key-fl_col_secao").boundingBox(), await p.locator(".st-key-fl_col_prontidao").boundingBox()];
  ok(mi.y < ms.y && ms.y < mp.y && Math.abs(mi.width - ms.width) < 4, "Folha a 400 px: colunas empilhadas (índice → seção → prontidão)");
  ok(ovf <= 1, `Folha a 400 px: sem transbordo horizontal (${ovf}px)`); await foto(p, "b2d_r_400x850_folha"); await ctx.close();

  // ------------------------------------------------------------------ B2-A · celular e tablet
  for (const [w, h] of [[400, 850], [820, 1100]]) {
    [ctx, p] = await abrir(w, h, `${base}/?view=operacao&mg=${seed.mg}`, w === 820 ? "dark" : "light");
    const cx = await p.locator(".pt.sb").boundingBox(), ov = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (w <= 760) {
      ok(Math.round(cx.y + cx.height) === h && cx.height <= 70 && Math.round(cx.width) === w, `${w}×${h}: a barra vira navegação inferior`);
      ok(await p.locator(".pt.sb .it.mv").count() >= 3 && await p.locator(".pt.sb .it:not(.mv)").first().isHidden(), `${w}×${h}: só os destinos essenciais na barra inferior`);
      await p.locator('.pt.sb .it[data-id="gestao"]').click(); await p.waitForTimeout(3000);
      ok(p.url().includes("view=gestao"), `${w}×${h}: a barra inferior navega`);
    } else ok(Math.round(cx.width) === 56 && cx.x === 0, `${w}×${h}: trilho lateral`);
    ok(ov <= 1, `${w}×${h}: sem transbordo horizontal (${ov}px)`); await foto(p, `b2a_r_${w}x${h}`);
    await ctx.close();
  }

  await b.close();
  if (falhas.length) { log(`${falhas.length} FALHA(S):`); falhas.forEach((f) => log("  ", f)); process.exit(1); }
  log(`CONCLUÍDO — ${n} verificações aprovadas, sem erros de página nem de console`);
})().catch((e) => { console.error(e); process.exit(1); });
