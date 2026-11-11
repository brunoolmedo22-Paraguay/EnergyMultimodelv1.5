// E2E em navegador real (Playwright/Chromium) do PISO 3D-A2-H — curva q(P) da PEMFC na bancada H₂ e bloqueio B04.
// Preparação: python tools/e2e/seed_piso3da2h.py <DIR>; roteiro completo: tools/e2e/run_piso3da2h.sh
// Uso: node tools/e2e/e2e_piso3da2h.js <url> <pasta_capturas>
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const [url, outDir] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
let count = 0;
const log = (...a) => console.log("[3da2h]", ...a);
function assert(c, msg) { if (!c) throw new Error("FALHA: " + msg); count += 1; log("ok —", msg); }
async function ready(p) {
  await p.waitForLoadState("networkidle");
  await p.waitForFunction(() => !document.querySelector('[data-testid="stStatusWidget"]'), null, { timeout: 120000 }).catch(() => {});
  await p.waitForTimeout(700);
}
const visible = async (p, t) => (await p.getByText(t, { exact: false }).count()) > 0;
async function btn(p, name) { await p.getByRole("button", { name }).first().click(); await ready(p); }
async function chart(p, t) {
  return p.evaluate((tt) => {
    const g = [...document.querySelectorAll(".js-plotly-plot")].find((el) => el.layout && el.layout.title && String(el.layout.title.text || "").includes(tt));
    return g ? g._fullData.map((d) => d.name) : null;
  }, t);
}
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; p.on("pageerror", (e) => errs.push(String(e)));
  try {
    await p.goto(url); await ready(p);
    await p.getByText("GESTOR DE MICRORREDES").first().waitFor({ timeout: 120000 });
    const cartao = p.locator('[data-testid="stVerticalBlock"]').filter({ has: p.getByText("Microrrede E2E 3D-A2-H", { exact: true }) })
      .filter({ has: p.getByRole("button", { name: "ABRIR MICRORREDE" }) }).last();
    await cartao.waitFor({ timeout: 60000 });
    await cartao.getByRole("button", { name: "ABRIR MICRORREDE" }).first().click(); await ready(p);
    await p.getByText("Espaço de trabalho cotidiano da microrrede ativa", { exact: false }).waitFor({ timeout: 60000 });
    await btn(p, "ABRIR EXECUÇÃO");
    assert(await visible(p, "AGUARDANDO APROVAÇÃO"), "execução PEMFC bloqueada: certificação B04 aguardando aprovação");
    assert(await visible(p, "curva q(P) do modelo físico"), "curva derivada do modelo físico reportada no preflight");
    assert(await p.getByRole("button", { name: /EXECUTAR MISSÃO V2/ }).isDisabled(), "EXECUTAR MISSÃO V2 desabilitado");
    await p.getByText("AGUARDANDO APROVAÇÃO", { exact: false }).first().scrollIntoViewIfNeeded().catch(() => {});
    await p.mouse.wheel(0, -200); await p.waitForTimeout(600);
    await p.screenshot({ path: path.join(outDir, "p3da2h_01_bloqueio_b04.png") });
    await btn(p, "← Centro de Operação");
    const exp = p.getByText("bancadas individuais dos modelos", { exact: false }).first();
    for (let i = 0; i < 240 && !(await exp.count()); i++) { await p.mouse.wheel(0, 1200); await p.waitForTimeout(500); }
    await exp.waitFor({ timeout: 30000 });
    await exp.scrollIntoViewIfNeeded(); await exp.click(); await ready(p);
    await p.getByRole("button", { name: "ABRIR H₂ / PEMFC" }).first().waitFor({ timeout: 60000 });
    await btn(p, "ABRIR H₂ / PEMFC");
    await btn(p, "Caracterização");
    await p.getByText("H₂ · Curva de consumo do EMS", { exact: false }).first().scrollIntoViewIfNeeded();
    for (let i = 0; i < 60 && !(await chart(p, "Consumo de hidrogênio × potência líquida")); i++) {
      await p.mouse.wheel(0, 600); await p.waitForTimeout(500);
    }
    await ready(p);
    const nomes = await chart(p, "Consumo de hidrogênio × potência líquida");
    assert(nomes && nomes.includes("Modelo físico (H₂ suprido)") && nomes.includes("PWL usada pelo EMS") && nomes.includes("Vértices da PWL"),
      "bancada: modelo físico × PWL do EMS × vértices");
    assert(await visible(p, "não são medições"), "bancada: modelo aproximado identificado (não são medições)");
    for (let i = 0; i < 20 && !(await chart(p, "Erro da aproximação")); i++) { await p.mouse.wheel(0, 500); await p.waitForTimeout(400); }
    assert((await chart(p, "Erro da aproximação")) !== null, "bancada: diagnóstico do erro da aproximação");
    assert(await visible(p, "Não aprovada"), "bancada: certificação B04 declarada NÃO aprovada");
    await p.getByText("H₂ · Curva de consumo do EMS", { exact: false }).first().scrollIntoViewIfNeeded().catch(() => {});
    await p.mouse.wheel(0, 260); await p.waitForTimeout(600);
    await p.screenshot({ path: path.join(outDir, "p3da2h_02_bancada_curva.png") });
    const graf = p.locator(".js-plotly-plot").filter({ has: p.getByText("Consumo de hidrogênio × potência líquida", { exact: false }) }).first();
    await graf.scrollIntoViewIfNeeded(); await p.waitForTimeout(600);
    await graf.screenshot({ path: path.join(outDir, "p3da2h_03_grafico_modelo_pwl.png") });
    assert(errs.length === 0, `sem erros de JavaScript: ${JSON.stringify(errs)}`);
    log(`CONCLUÍDO — ${count} verificações`);
  } catch (e) {
    await p.screenshot({ path: path.join(outDir, "FALHA_3da2h.png") }).catch(() => {});
    console.error(e.message || e); process.exitCode = 1;
  } finally { await b.close(); }
})();
