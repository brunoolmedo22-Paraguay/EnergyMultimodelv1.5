// Verificação E2E em navegador real (Playwright/Chromium) do PISO 3D-A2-R — FV + eólica no motor V2 (MILP–MPC).
//
// Preparação: python tools/e2e/seed_piso3da2r.py <DIR_ORIGEM>   (roteiro completo: tools/e2e/run_piso3da2r.sh)
// Uso:        node tools/e2e/e2e_piso3da2r.js <url> <fase> <pasta_capturas>
// Fases:
//   operar   — Gestor → ABRIR → Execução: preflight V2 apto com o potencial derivado pelos modelos físicos (FV por arranjo,
//              eólica por registro) → EXECUTAR (HiGHS real) → rodada: custo REALIZADO, tabela por UID (utilizável ×
//              aproveitada × vertida), gráficos com a renovável aproveitada e o vertimento, 11 dados gravados → recarga →
//              exportar o estudo.
//   reinicio — servidor NOVO sobre o mesmo diretório: a rodada reabre com o MESMO custo e a evidência verificada.
//   tablet   — rodada em tablet (retrato) sem rolagem horizontal.
//   importar — instalação LIMPA, SEM solver, com motores e MODELOS FÍSICOS sabotados: estudo importado e consultado.
// Nenhum serviço externo é consultado.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const [url, phase, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const shot = (p, name) => p.screenshot({ path: path.join(outDir, name), fullPage: false });
const log = (...a) => console.log(`[${phase}]`, ...a);
const runFile = path.join(outDir, "rodada_v2r.json");
const pkgFile = path.join(outDir, "estudo_v2r.seeds2study.zip");
const MG = "Microrrede E2E 3D-A2-R";
let current = null;
let count = 0;
function assert(c, msg) { if (!c) { throw new Error("FALHA: " + msg); } count += 1; log("ok —", msg); }

async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 120000 }).catch(() => {});
  await p.waitForTimeout(700);
}
async function visible(p, text) { return (await p.getByText(text, { exact: false }).count()) > 0; }
async function btn(p, name) { await p.getByRole("button", { name }).first().click(); await ready(p); }
async function abrirMicrorrede(p, nome) {
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  await p.getByText(nome, { exact: true }).first().waitFor({ timeout: 60000 });
  const cartao = p.locator('[data-testid="stVerticalBlock"]')
    .filter({ has: p.getByText(nome, { exact: true }) })
    .filter({ has: p.getByRole("button", { name: "ABRIR MICRORREDE" }) }).last();
  await cartao.waitFor({ timeout: 60000 });
  await cartao.getByRole("button", { name: "ABRIR MICRORREDE" }).first().click(); await ready(p);
  await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).waitFor({ timeout: 60000 });
  assert(await visible(p, nome), `microrrede aberta: ${nome}`);
}
async function kpi(p, label) {
  return p.evaluate((l) => {
    const k = [...document.querySelectorAll(".sd-kpi")].find((e) => e.querySelector("small") && e.querySelector("small").textContent === l);
    return k ? k.querySelector("b").textContent : null;
  }, label);
}
async function chart(p, titlePart) {
  return p.evaluate((t) => {
    const g = [...document.querySelectorAll(".js-plotly-plot")].find((el) => el.layout && el.layout.title &&
      String(el.layout.title.text || "").includes(t));
    if (!g) return null;
    const r = g.getBoundingClientRect();
    return { traces: g._fullData.map((d) => ({ name: d.name, n: (d.y && d.y.length) || 0, y: d.y ? [...d.y] : [] })), w: r.width };
  }, titlePart);
}
async function waitRun(p, seconds = 240) {
  for (let i = 0; i < seconds * 2; i++) {
    if (await p.getByText("Rodada · imutável").count()) return;
    await p.waitForTimeout(500);
  }
  throw new Error(`FALHA: a rodada V2 não terminou em ${seconds} s`);
}
async function conferirRodada(p, tag, custo) {
  await p.getByText("Custo REALIZADO").first().waitFor({ timeout: 90000 }); await ready(p);
  const c = await kpi(p, "Custo REALIZADO");
  if (custo) { assert(c === custo, `${tag}: custo REALIZADO ${custo}`); } else { assert(/^R\$ [\d.,]+$/.test(c || ""), `${tag}: custo REALIZADO ${c}`); }
  assert(await visible(p, "✓ Evidência verificada"), `${tag}: evidência verificada na reabertura (sem otimizador nem modelos)`);
  assert(!(await visible(p, "EVIDÊNCIA COM PROBLEMAS")), `${tag}: nenhuma falha de integridade`);
  assert(await visible(p, "Renovável (UID)") && await visible(p, "Fotovoltaica") && await visible(p, "Eólica"),
    `${tag}: tabela por UID com FV e eólica`);
  const ren = await chart(p, "Potencial renovável por UID");
  assert(ren && ren.traces.some((t) => t.name.startsWith("Vertida ") && t.y.some((v) => v > 0)) &&
    ren.traces.some((t) => t.name.startsWith("Aproveitada ") && t.y.some((v) => v > 0)), `${tag}: gráfico disponível × aproveitado × vertido`);
  const pot = await chart(p, "Demanda × atendimento por recurso");
  assert(pot && pot.traces.some((t) => t.name.startsWith("Renovável ")), `${tag}: atendimento da carga inclui a renovável aproveitada`);
  return c;
}

async function operar(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const p = await ctx.newPage(); current = p;
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  await p.goto(url); await ready(p);
  await abrirMicrorrede(p, MG);
  await btn(p, "ABRIR EXECUÇÃO");
  assert(await visible(p, "Apto para o motor V2"), "preflight V2 apto");
  assert(await visible(p, "Modelo FV 2"), "potencial FV derivado pelo modelo físico (por arranjo)");
  assert(await visible(p, "Curva do catálogo"), "potencial eólico derivado pela curva do catálogo");
  assert(await visible(p, "disponível ≠ despachada"), "potencial disponível distinto da potência despachada");
  assert(await visible(p, "Previsão climática: 12 × 1 subamostra"), "clima nos instantes exatos da missão");
  await shot(p, "p3da2r_01_preflight.png");
  await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).click();
  await waitRun(p); await ready(p);
  const custo = await conferirRodada(p, "rodada", null);
  assert(await p.getByRole("button", { name: "Baixar" }).count() === 11, "11 dados gravados (inclui v2/renovaveis.json)");
  assert(await visible(p, "v2/renovaveis.json"), "derivação renovável gravada com a rodada");
  fs.writeFileSync(runFile, JSON.stringify({ custo, link: p.url() }));
  await shot(p, "p3da2r_02_rodada.png");
  await p.reload(); await ready(p);
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 60000 });
  await conferirRodada(p, "recarga", custo);
  await btn(p, "← Execução do cenário");
  await btn(p, "← Centro de Operação"); await btn(p, "ABRIR ARQUIVO CIENTÍFICO");
  await p.getByText("Estudos científicos portáteis").first().waitFor({ timeout: 60000 });
  await btn(p, "PREPARAR EXPORTAÇÃO");
  const [dl] = await Promise.all([p.waitForEvent("download", { timeout: 60000 }),
    p.getByRole("button", { name: "EXPORTAR CENÁRIO COMPLETO" }).first().click()]);
  await dl.saveAs(pkgFile);
  assert(fs.readFileSync(pkgFile).subarray(0, 2).toString("latin1") === "PK", `estudo exportado (${fs.statSync(pkgFile).size} bytes)`);
  assert(errs.length === 0, `sem erros de JavaScript: ${JSON.stringify(errs)}`);
  await ctx.close();
}

async function reinicio(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  const info = JSON.parse(fs.readFileSync(runFile, "utf8"));
  await p.goto(info.link.replace(/^https?:\/\/[^/]+/, url.replace(/\/$/, ""))); await ready(p);
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 120000 });
  await conferirRodada(p, "após reinício do servidor", info.custo);
  await shot(p, "p3da2r_03_reaberta.png");
}

async function tablet(b) {
  const ctx = await b.newContext({ viewport: { width: 820, height: 1180 }, deviceScaleFactor: 2, hasTouch: true });
  const p = await ctx.newPage(); current = p;
  const info = JSON.parse(fs.readFileSync(runFile, "utf8"));
  await p.goto(info.link.replace(/^https?:\/\/[^/]+/, url.replace(/\/$/, ""))); await ready(p);
  await p.getByText("Rodada · imutável").first().waitFor({ timeout: 120000 });
  await conferirRodada(p, "tablet", info.custo);
  const ov = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  assert(ov <= 1, `tablet retrato: sem rolagem horizontal da página (${ov}px)`);
  await shot(p, "p3da2r_04_tablet.png");
  await ctx.close();
}

async function importar(b) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); current = p;
  const info = JSON.parse(fs.readFileSync(runFile, "utf8"));
  await p.goto(url); await ready(p);
  await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
  assert(await visible(p, "Nenhuma microrrede registrada"), "instalação limpa: nenhuma microrrede");
  await btn(p, "ARQUIVO CIENTÍFICO");
  await p.getByText("Estudos científicos portáteis").first().waitFor({ timeout: 60000 });
  await p.locator('input[type="file"]').first().setInputFiles(pkgFile); await ready(p);
  await p.getByText("Verificação concluída", { exact: false }).first().waitFor({ timeout: 60000 });
  await p.getByText("Confirmo a importação deste estudo", { exact: false }).click(); await ready(p);
  await btn(p, "CONFIRMAR IMPORTAÇÃO");
  await p.getByText("Verificado na importação").first().waitFor({ timeout: 60000 });
  await btn(p, "ABRIR ESTUDO");
  await p.getByText("Estudo arquivado · somente leitura").first().waitFor({ timeout: 60000 });
  await p.locator('[data-testid="stRadio"] label').filter({ hasText: "Rodadas e resultados" }).first().click(); await ready(p);
  await btn(p, "Consultar");
  await conferirRodada(p, "estudo arquivado (sem solver nem modelos)", info.custo);
  await shot(p, "p3da2r_05_estudo_arquivado.png");
  await p.goto(url); await ready(p);
  assert(await visible(p, "Nenhuma microrrede registrada"), "importar e consultar não criou microrrede");
}

(async () => {
  const b = await chromium.launch();
  try {
    await { operar, reinicio, tablet, importar }[phase](b);
    log(`CONCLUÍDO — ${count} verificações`);
  } catch (e) {
    if (current) await current.screenshot({ path: path.join(outDir, `FALHA_${phase}.png`), fullPage: false }).catch(() => {});
    throw e;
  } finally {
    await b.close();
  }
})().catch((e) => { console.error(e.message || e); process.exit(1); });
