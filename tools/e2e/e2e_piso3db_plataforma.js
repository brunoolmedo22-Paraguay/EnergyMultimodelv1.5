// E2E em navegador real (Playwright/Chromium) do PISO 3D-B2 — integração visual da plataforma na aplicação Streamlit REAL.
// Roteiro completo: tools/e2e/run_piso3db.sh (mesma semente e mesmo servidor SEM solver do E2E da Partitura).
// Uso: node tools/e2e/e2e_piso3db_plataforma.js <url> <seed_piso3db.json> <pasta_capturas>
// B2-A: barra lateral (trilho, expansão por hover/foco, destino atual, navegação, troca de microrrede, barra inferior no
// celular, estabilidade em reruns) com a barra superior anterior intacta.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const [base, seedFile, out] = process.argv.slice(2);
const seed = JSON.parse(fs.readFileSync(seedFile, "utf8"));
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

  // ------------------------------------------------------------------ B2-A · sem microrrede aberta (Gestor)
  let [ctx, p] = await abrir(1500, 900, `${base}/`);
  ok(JSON.stringify(await itens(p)) === JSON.stringify(["catalogo", "arquivo", "alcance"]), "sem microrrede: barra lateral com Catálogo, Arquivo Científico e Alcance");
  ok(JSON.stringify(await atual(p)) === JSON.stringify(["catalogo"]), "Gestor de microrredes = Catálogo (destino atual marcado)");
  ok(await largura(p) === 56, "trilho compacto de 56 px");
  ok(await p.locator(".tb .tb-link").count() >= 2, "barra superior anterior continua na página (navegação preservada)");
  await p.hover(".pt.sb"); await p.waitForTimeout(450);
  ok(await largura(p) >= 240, "hover expande a barra por cima do conteúdo"); await foto(p, "b2a_01_gestor_barra_expandida");
  const recuo = await p.locator(".block-container").evaluate((e) => parseFloat(getComputedStyle(e).paddingLeft));
  ok(recuo >= 56, `o conteúdo começa depois do trilho (recuo ${Math.round(recuo)} px)`);
  await p.mouse.move(900, 500); await p.waitForTimeout(350);
  await p.locator('.pt.sb .it[data-id="arquivo"]').focus(); await p.waitForTimeout(350);
  ok(await largura(p) >= 240, "foco pelo teclado também expande a barra");
  await p.keyboard.press("Enter"); await p.waitForTimeout(2500);
  ok(p.url().includes("view=arquivo") && JSON.stringify(await atual(p)) === JSON.stringify(["arquivo"]), "Enter navega para o Arquivo Científico");
  await ctx.close();

  // ------------------------------------------------------------------ B2-A · microrrede ativa
  [ctx, p] = await abrir(1500, 900, `${base}/?view=operacao&mg=${seed.mg}`);
  const ids = await itens(p);
  ok(["catalogo", "operacao", "gestao", "arquivo", "simulacao", "resultados", "alcance"].every((i) => ids.includes(i)), "microrrede ativa: todos os destinos anteriores estão na barra lateral");
  ok(JSON.stringify(await atual(p)) === JSON.stringify(["operacao"]), "Centro de Operação marcado como destino atual");
  await p.locator(".pt.sb .side-in").evaluate((e) => e.setAttribute("data-marca", "1"));
  await p.locator("body").press("r"); await p.waitForTimeout(3500);
  ok(await p.locator('.pt.sb .side-in[data-marca="1"]').count() === 1, "rerun do Streamlit não redesenha a barra lateral");
  await p.hover(".pt.sb"); await p.waitForTimeout(400); await foto(p, "b2a_02_microrrede_barra_expandida");
  await p.locator('.pt.sb .it[data-id="gestao"]').click(); await p.waitForTimeout(3000);
  ok(p.url().includes("view=gestao") && p.url().includes(`mg=${seed.mg}`) && JSON.stringify(await atual(p)) === JSON.stringify(["gestao"]), "clique navega para a Gestão da Microrrede mantendo a microrrede");
  await p.locator(".tb .tb-link", { hasText: "Centro de Operação" }).click(); await p.waitForTimeout(3000);
  ok(p.url().includes("view=operacao") && JSON.stringify(await atual(p)) === JSON.stringify(["operacao"]), "a barra superior continua navegando e a lateral acompanha");
  await p.goto(`${base}/?view=operacao&tab=rodada&mg=${seed.mg}&sc=${seed.sc}&run=${seed.run}`); await p.locator(".pt svg.trama").first().waitFor({ timeout: 120000 }); await p.waitForTimeout(1500);
  const inst = await p.locator(".pt:not(.sb)").first().evaluate((e) => e.getBoundingClientRect().left);
  ok(inst >= 56, `rodada: a Partitura começa depois do trilho (${Math.round(inst)} px)`); await foto(p, "b2a_03_rodada_com_barra");
  await p.locator('.pt.sb .it[data-id="catalogo"]').click(); await p.waitForTimeout(3500);
  ok(p.url().includes("view=gestor") && !p.url().includes("mg=") && JSON.stringify(await itens(p)) === JSON.stringify(["catalogo", "arquivo", "alcance"]), "Catálogo com microrrede aberta = trocar de microrrede (volta ao Gestor)");
  await ctx.close();

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
