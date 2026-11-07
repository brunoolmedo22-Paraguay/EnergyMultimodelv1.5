// Verificação E2E em navegador real (Playwright/Chromium) do PISO 2D-B — Relatórios científicos, Excel e figuras.
//
// Preparação:
//   ORIGEM:  python tools/e2e/seed_piso2db.py <DIR_ORIGEM>   (rodada REAL concluída + rodada falha)
//            SEEDS2_DATA_DIR=<DIR_ORIGEM> python -m streamlit run app.py --server.headless true --server.port <porta>
//   DESTINO: SEEDS2_DATA_DIR=<DIR_VAZIO> com o motor sabotado:
//            PYTHONPATH=tools/e2e/sabotage SEEDS2_E2E_ROOT=<raiz> SEEDS2_E2E_ENGINE_LOG=<arquivo> python -m streamlit run app.py …
// Uso:
//   node tools/e2e/e2e_piso2db_relatorios.js <url> <fase> <pasta_saida> <e2e_origem.json>
// Fases (o roteiro troca/reinicia o servidor ENTRE as fases):
//   local    — ORIGEM: Gestor → ABRIR → Execução → rodada concluída → EXPORTAR RELATÓRIO PDF / DADOS EXCEL / FIGURAS
//              (downloads reais) → figura SVG individual → rodada falha → diagnóstico PDF (figuras desabilitadas) →
//              Arquivo Científico → exportar o estudo (.seeds2study.zip).
//   importar — DESTINO vazio: ARQUIVO CIENTÍFICO → importar → ABRIR ESTUDO → rodada concluída → os MESMOS três documentos.
//   reinicio — DESTINO após kill -9 + reinício: link direto → mesma rodada → PDF e Excel novamente.
//   tablet   — painel de exportação em tablet retrato/paisagem (sem rolagem horizontal) + geração de PDF.
// Os arquivos baixados ficam em <pasta_saida>/downloads/<fase>_*; conferência: tools/e2e/check_piso2db_downloads.py.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const [url, phase, outDir, originPath] = process.argv.slice(2);
const dlDir = path.join(outDir, "downloads");
fs.mkdirSync(dlDir, { recursive: true });
const pkgFile = path.join(outDir, "estudo_exportado.seeds2study.zip");
const linkFile = path.join(outDir, "link_estudo.txt");
const origin = JSON.parse(fs.readFileSync(originPath, "utf8"));
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: false });
const log = (...a) => console.log(`[${phase}]`, ...a);
let current = null;
let count = 0;
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } count += 1; log("ok —", msg); }

async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 180000 }).catch(() => {});
  await p.waitForTimeout(900);
}
async function noErrors(p, tag) { assert(await p.locator('[data-testid="stException"]').count() === 0, `${tag}: nenhuma exceção`); }
async function overflow(p) { return p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); }
async function btn(p, name, exact = false) { await p.getByRole("button", { name, exact }).first().click(); await ready(p); }
async function visible(p, text) { return p.getByText(text, { exact: false }).first().isVisible().catch(() => false); }
async function section(p, name) {
  await p.locator('[data-testid="stRadio"] label').filter({ hasText: name }).first().click(); await ready(p);
}
function magic(file) { return fs.readFileSync(file).subarray(0, 4).toString("latin1"); }

// Gera um documento (clique em EXPORTAR …), espera o botão BAIXAR … e salva o download real.
async function exportDoc(p, exportLabel, downloadLabel, prefix) {
  await p.getByRole("button", { name: exportLabel, exact: true }).first().scrollIntoViewIfNeeded();
  await btn(p, exportLabel, true);
  const dbtn = p.getByRole("button", { name: downloadLabel, exact: true }).first();
  await dbtn.waitFor({ timeout: 180000 });
  const [dl] = await Promise.all([p.waitForEvent("download", { timeout: 120000 }), dbtn.click()]);
  const name = dl.suggestedFilename();
  assert(/^[A-Za-z0-9_.]+$/.test(name), `${exportLabel}: nome de arquivo seguro (${name})`);
  const file = path.join(dlDir, `${prefix}_${name}`);
  await dl.saveAs(file);
  return { name, file, size: fs.statSync(file).size };
}

async function exportAll(p, prefix) {
  assert(await visible(p, "Exportações científicas"), "painel Exportações científicas visível");
  assert(await visible(p, "não executa modelos nem o EMS"), "painel declara: documento derivado, sem executar o motor");
  const pdf = await exportDoc(p, "EXPORTAR RELATÓRIO PDF", "BAIXAR RELATÓRIO PDF", prefix);
  assert(magic(pdf.file) === "%PDF" && pdf.name.endsWith(".pdf") && pdf.size > 50000, `PDF baixado (${pdf.size} bytes)`);
  const xl = await exportDoc(p, "EXPORTAR DADOS EXCEL", "BAIXAR DADOS EXCEL", prefix);
  assert(magic(xl.file).startsWith("PK") && xl.name.endsWith(".xlsx"), `Excel baixado (${xl.size} bytes)`);
  const fg = await exportDoc(p, "EXPORTAR FIGURAS", "BAIXAR FIGURAS (PNG + SVG)", prefix);
  assert(magic(fg.file).startsWith("PK") && fg.name.endsWith(".zip"), `ZIP de figuras baixado (${fg.size} bytes)`);
  return { pdf, xl, fg };
}

// ------------------------------------------------------------------ ORIGEM (rodada local)
async function local(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  await btn(p, "ABRIR MICRORREDE");
  await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).waitFor({ timeout: 60000 });
  await btn(p, "ABRIR EXECUÇÃO");
  await p.getByText("Rodadas registradas").first().waitFor({ timeout: 60000 });
  await p.getByRole("button", { name: "Abrir", exact: true }).nth(1).click(); await ready(p);   // concluída (mais antiga)
  assert(await visible(p, "Rodada · imutável"), "rodada concluída aberta (somente leitura)");
  assert(await visible(p, origin.cost), `custo original exibido (${origin.cost})`);
  assert(await p.locator('[data-testid="stDownloadButton"]').count() === 0, "nada é gerado ao abrir a rodada (sob demanda)");
  await p.getByText("Exportações científicas").first().scrollIntoViewIfNeeded();
  await shot(p, "p2db_01_painel_local.png");
  await exportAll(p, "local");
  const sel = p.locator('[data-testid="stSelectbox"]').filter({ hasText: "Figura individual" }).first();
  await sel.locator("input").first().click(); await p.keyboard.type("svg/01_demanda");
  await p.getByRole("option").filter({ hasText: "svg/01_demanda_potencia_por_fonte.svg" }).first().click(); await ready(p);
  const [dl] = await Promise.all([p.waitForEvent("download", { timeout: 60000 }),
    p.getByRole("button", { name: "BAIXAR FIGURA SELECIONADA", exact: true }).click()]);
  const svgFile = path.join(dlDir, `local_individual_${dl.suggestedFilename()}`);
  await dl.saveAs(svgFile);
  assert(dl.suggestedFilename() === "01_demanda_potencia_por_fonte.svg" && fs.readFileSync(svgFile, "utf8").includes("<svg"),
    `figura individual SVG baixada (${dl.suggestedFilename()})`);
  await shot(p, "p2db_02_downloads_local.png");
  await noErrors(p, "rodada local");
  // rodada falha → diagnóstico
  await btn(p, "← Execução do cenário");
  await p.getByRole("button", { name: "Abrir", exact: true }).nth(0).click(); await ready(p);
  assert(await visible(p, "Rodada falhou"), "rodada falha aberta");
  assert(await p.getByRole("button", { name: "EXPORTAR FIGURAS", exact: true }).isDisabled(), "falha: figuras desabilitadas (sem séries)");
  const dg = await exportDoc(p, "EXPORTAR DIAGNÓSTICO PDF", "BAIXAR RELATÓRIO PDF", "local_falha");
  assert(dg.name.startsWith("seeds2_diagnostico_") && magic(dg.file) === "%PDF", `diagnóstico PDF baixado (${dg.name})`);
  await shot(p, "p2db_03_diagnostico.png");
  // exportar o estudo (Piso 2D-A) para a instalação limpa
  await btn(p, "← Execução do cenário");
  await btn(p, "← Centro de Operação");
  await btn(p, "ABRIR ARQUIVO CIENTÍFICO");
  await p.getByText("Estudos científicos portáteis").first().waitFor({ timeout: 60000 });
  await btn(p, "PREPARAR EXPORTAÇÃO");
  const [pk] = await Promise.all([p.waitForEvent("download", { timeout: 60000 }),
    p.getByRole("button", { name: "EXPORTAR CENÁRIO COMPLETO" }).first().click()]);
  await pk.saveAs(pkgFile);
  assert(magic(pkgFile).startsWith("PK") && pk.suggestedFilename().endsWith(".seeds2study.zip"), "estudo exportado (.seeds2study.zip)");
  await noErrors(p, "local");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

// ------------------------------------------------------------------ DESTINO (instalação limpa, motor sabotado)
async function openRun(p) {
  await section(p, "Rodadas e resultados");
  const b = p.getByRole("button", { name: "Consultar", exact: true });
  await b.nth(1).click(); await ready(p);                                   // a concluída
  assert(await visible(p, origin.cost), `custo idêntico à origem (${origin.cost})`);
}

async function importar(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  assert(await visible(p, "Nenhuma microrrede registrada"), "instalação limpa: nenhuma microrrede");
  await btn(p, "ARQUIVO CIENTÍFICO");
  await p.locator('input[type="file"]').first().setInputFiles(pkgFile); await ready(p);
  await p.getByText("Verificação concluída", { exact: false }).first().waitFor({ timeout: 60000 });
  await p.getByText("Confirmo a importação deste estudo", { exact: false }).click(); await ready(p);
  await btn(p, "CONFIRMAR IMPORTAÇÃO");
  await p.getByText("Verificado na importação").first().waitFor({ timeout: 60000 });
  await btn(p, "ABRIR ESTUDO");
  await p.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 60000 });
  await openRun(p);
  fs.writeFileSync(linkFile, p.url());
  assert(await visible(p, "estudo arquivado"), "painel: origem = estudo arquivado");
  await p.getByText("Exportações científicas").first().scrollIntoViewIfNeeded();
  await shot(p, "p2db_10_painel_arquivo.png");
  await exportAll(p, "arquivo");
  await shot(p, "p2db_11_downloads_arquivo.png");
  await noErrors(p, "importar");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

async function reinicio(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(fs.readFileSync(linkFile, "utf8").trim()); await ready(p);
  await p.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 120000 });
  assert(await visible(p, origin.cost), "após reinício: link direto reabre a mesma rodada (mesmo custo)");
  assert(await p.locator('[data-testid="stDownloadButton"]').count() === 0, "após reinício: nenhum documento pré-gerado");
  const pdf = await exportDoc(p, "EXPORTAR RELATÓRIO PDF", "BAIXAR RELATÓRIO PDF", "reinicio");
  assert(magic(pdf.file) === "%PDF", "após reinício: PDF gerado do arquivo");
  const xl = await exportDoc(p, "EXPORTAR DADOS EXCEL", "BAIXAR DADOS EXCEL", "reinicio");
  assert(magic(xl.file).startsWith("PK"), "após reinício: Excel gerado do arquivo");
  await noErrors(p, "reinício");
  assert(errs.length === 0, "sem erros de JavaScript: " + JSON.stringify(errs));
  await ctx.close();
}

async function tablet(b) {
  const link = fs.readFileSync(linkFile, "utf8").trim();
  for (const [w, h, tag] of [[820, 1180, "retrato"], [1180, 820, "paisagem"]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, acceptDownloads: true });
    const p = await ctx.newPage(); current = p;
    await p.goto(link); await ready(p);
    await p.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 60000 });
    await p.getByText("Exportações científicas").first().scrollIntoViewIfNeeded();
    assert(await overflow(p) <= 1, `tablet ${tag}: sem rolagem horizontal`);
    for (const lb of ["EXPORTAR RELATÓRIO PDF", "EXPORTAR DADOS EXCEL", "EXPORTAR FIGURAS"]) {
      const bb = await p.getByRole("button", { name: lb, exact: true }).first().boundingBox();
      assert(bb && bb.x >= 0 && bb.x + bb.width <= w + 1, `tablet ${tag}: botão ${lb} dentro da tela`);
    }
    const pdf = await exportDoc(p, "EXPORTAR RELATÓRIO PDF", "BAIXAR RELATÓRIO PDF", `tablet_${tag}`);
    assert(magic(pdf.file) === "%PDF", `tablet ${tag}: PDF baixado`);
    assert(await overflow(p) <= 1, `tablet ${tag}: sem rolagem horizontal após gerar`);
    await shot(p, `p2db_30_tablet_${tag}.png`);
    await ctx.close();
  }
}

(async () => {
  const b = await chromium.launch();
  try {
    await { local, importar, reinicio, tablet }[phase](b);
    log(`CONCLUÍDO — ${count} verificações`);
  } catch (e) {
    if (current) await current.screenshot({ path: path.join(outDir, `FALHA_${phase}.png`), fullPage: false }).catch(() => {});
    throw e;
  } finally {
    await b.close();
  }
})().catch((e) => { console.error(e.message || e); process.exit(1); });
